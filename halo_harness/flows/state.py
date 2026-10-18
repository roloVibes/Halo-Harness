"""halo_harness.flows.state -- a flow run on disk, `~/.halo/flows/runs/<run-id>/`:

    flow.json      {name, version, run, created, source, project, budget_usd,
                    intake, spec, overrides, status, cost_usd,
                    steps: [{id, kind, state}]}   state: pending|running|
                    waiting|done|failed|skipped
    steps/<n>.json {id, kind, started, finished, cost_usd, output, error, rounds}
                   (n = the step's 1-based position in the flow)
    steps/<n>.gate.json / steps/<n>.answer.json   an open human gate (gates.py)
    events.jsonl   {ts, elapsed_s, step, kind, text, data}; kind: state|step|
                   gate|post|metric|report|note
    stop.json      {reason, ts}: the runner stops between steps (and inside a gate)
    report.json    report.py

`Flow` is the runner's handle (the shape of orchestra/run.py's): step
states in flow.json, the timed log appended under a lock, and the event
pump: `on_event(entry)` sees every new line, `feed(Event)` gets the
session-feed event `flow_<kind>` (every kind but note).
"""

from __future__ import annotations

import secrets
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import jsonl
from halo_harness.work.states import words

STEP_STATES = words("step")  # pending running waiting done failed skipped: a step's words (work/states.py, 3.1.2.0 R1)
EVENT_KINDS = ("state", "step", "gate", "post", "metric", "report", "note")
FEED_KINDS = {k: f"flow_{k}" for k in EVENT_KINDS if k != "note"}


class StopFlow(Exception):
    """Raised by a step (or the runner) to stop the run with a reason."""


def runs_dir(state_dir=None) -> Path:
    from halo_harness.flows.spec import flows_dir
    return flows_dir(state_dir) / "runs"


def new_run_id(clock: Callable = time.time) -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(clock())) + "-" + secrets.token_hex(2)


def project_slug(spec: dict, intake: dict) -> str:
    from halo_harness.design.store import slugify
    from halo_harness.flows.spec import render_vars
    raw = str(render_vars(spec.get("project") or "", intake) or "").strip()
    return slugify(raw or str(intake.get("project") or "") or str(spec.get("name") or "flow"))


def new_run(spec: dict, intake: Optional[dict] = None, *, source: str = "", state_dir=None,
            clock: Callable = time.time, overrides: Optional[dict] = None) -> Path:
    intake = dict(intake or {})
    root = runs_dir(state_dir)
    while True:
        run_id = new_run_id(clock)
        run_dir = root / run_id
        if not run_dir.exists():
            break
    (run_dir / "steps").mkdir(parents=True)
    budget = intake.get("budget_usd") if isinstance(intake.get("budget_usd"), (int, float)) else spec.get("budget_usd")
    data = {"name": spec.get("name"), "version": spec.get("version"), "run": run_id, "created": round(clock(), 3),
            "source": str(source), "project": project_slug(spec, intake),
            "budget_usd": float(budget) if isinstance(budget, (int, float)) else None, "intake": intake,
            "spec": spec, "overrides": dict(overrides or {}), "status": "pending", "cost_usd": 0.0,
            "steps": [{"id": s.get("id"), "kind": s.get("kind"), "state": "pending"} for s in spec.get("steps") or []]}
    jsonl.write_json(run_dir / "flow.json", data)
    return run_dir


def step_path(run_dir, n: int) -> Path:
    return Path(run_dir) / "steps" / f"{int(n)}.json"


def read_step(run_dir, n: int) -> dict:
    return jsonl.read_json(step_path(run_dir, n), {}) or {}


def write_step(run_dir, n: int, record: dict) -> None:
    jsonl.write_json(step_path(run_dir, n), record)


def stop_path(run_dir) -> Path:
    return Path(run_dir) / "stop.json"


def request_stop(run_dir, reason: str = "stopped by the user") -> None:
    jsonl.write_json(stop_path(run_dir), {"reason": reason, "ts": time.time()})


def stop_requested(run_dir) -> Optional[str]:
    data = jsonl.read_json(stop_path(run_dir), None)
    return str(data.get("reason") or "stopped by the user") if isinstance(data, dict) else None


def read_flow(run_dir) -> dict:
    return jsonl.read_json(Path(run_dir) / "flow.json", {}) or {}


def read_events(run_dir, since: int = 0) -> list:
    return jsonl.read_lines(Path(run_dir) / "events.jsonl")[max(0, int(since)):]


def read_run(run_dir) -> dict:
    """Everything a status view needs: flow.json, each step's record, the
    open gate (or None), the report (or None) and the event count."""
    from halo_harness.flows import gates
    run_dir = Path(run_dir)
    flow = read_flow(run_dir)
    steps = [read_step(run_dir, i + 1) for i in range(len(flow.get("steps") or []))]
    return {"flow": flow, "steps": steps, "gate": gates.open_gate(run_dir),
            "report": jsonl.read_json(run_dir / "report.json", None), "events": len(read_events(run_dir))}


def list_runs(state_dir=None) -> list:
    root = runs_dir(state_dir)
    out = []
    for d in sorted(root.iterdir()) if root.is_dir() else []:
        flow = read_flow(d) if d.is_dir() else {}
        if flow:
            out.append({"run": d.name, "name": flow.get("name"), "status": flow.get("status"),
                        "cost_usd": flow.get("cost_usd") or 0.0, "project": flow.get("project"), "path": str(d)})
    return out


def find_run(ref: str, state_dir=None) -> Optional[Path]:
    """A run folder by id, unique id prefix, a path, or `last`."""
    root = runs_dir(state_dir)
    ref = str(ref or "").strip()
    runs = sorted(d for d in root.iterdir() if (d / "flow.json").is_file()) if root.is_dir() else []
    if ref in ("", "last"):
        return runs[-1] if runs else None
    if (Path(ref) / "flow.json").is_file():
        return Path(ref)
    hits = [d for d in runs if d.name == ref] or [d for d in runs if d.name.startswith(ref)]
    return hits[0] if len(hits) == 1 else None


class Flow:
    """flow.json plus the timed log and the event pump."""

    def __init__(self, run_dir, on_event: Optional[Callable] = None, feed: Optional[Callable] = None,
                 clock: Callable = time.time):
        self.run_dir = Path(run_dir)
        self.path = self.run_dir / "flow.json"
        self.events_path = self.run_dir / "events.jsonl"
        self.on_event, self.feed, self.clock = on_event, feed, clock
        self.lock = threading.RLock()
        self.seen = len(read_events(self.run_dir))
        self.created = float(read_flow(self.run_dir).get("created") or time.time())

    def data(self) -> dict:
        return read_flow(self.run_dir)

    def update(self, **fields) -> dict:
        with self.lock:
            data = self.data()
            data.update(fields)
            jsonl.write_json(self.path, data)
            return data

    def state_of(self, step_id: str) -> str:
        return next((s.get("state") for s in self.data().get("steps") or [] if s.get("id") == step_id), "")

    def log(self, kind: str, text: str, step: Optional[str] = None, **data) -> dict:
        if kind not in EVENT_KINDS:
            raise ValueError(f"flow event kind must be one of {', '.join(EVENT_KINDS)}, got {kind!r}")
        with jsonl.locked(self.events_path):
            ts = time.time()
            entry = {"ts": round(ts, 3), "elapsed_s": round(max(0.0, ts - self.created), 3), "step": step,
                     "kind": kind, "text": str(text), "data": dict(data)}
            jsonl.append_line(self.events_path, entry)
        self.pump()
        return entry

    def set(self, step_id: str, state: str, text: str = "") -> None:
        if state not in STEP_STATES:
            raise ValueError(f"step state must be one of {', '.join(STEP_STATES)}, got {state!r}")
        with self.lock:
            data = self.data()
            row = next((s for s in data.get("steps") or [] if s.get("id") == step_id), None)
            if row is None or row.get("state") == state:
                return
            row["state"] = state
            jsonl.write_json(self.path, data)
            self.log("state", f"{step_id} {state}" + (f": {text}" if text else ""), step=step_id, state=state)

    def pump(self) -> None:
        with self.lock:
            new = read_events(self.run_dir, since=self.seen)
            self.seen += len(new)
        for entry in new:
            if self.on_event is not None:
                self.on_event(entry)
            if self.feed is not None and entry.get("kind") in FEED_KINDS:
                try:
                    self.feed(feed_event(entry, self.run_dir.name))
                except Exception:
                    pass


def feed_event(entry: dict, run: str):
    """The session-feed event for one log line (`flow_<kind>`, data = the line plus `run`)."""
    from halo_harness import events as feed
    return feed.Event(FEED_KINDS[entry["kind"]], dict(entry, run=run))


def format_line(entry: dict) -> str:
    step = entry.get("step") or ""
    return f"+{float(entry.get('elapsed_s') or 0):8.1f}s  {step:<10} {entry.get('kind', ''):<6} {entry.get('text', '')}"
