"""halo_harness.crew.trial_flow -- Try it for a workflow (Halo 3.6.0.0 R2; docs/STUDIO-workflows.md "Try it").

    start_flow(wf, agents, request, *, cwd, state_dir, publish) -> record

The same throwaway run as an agent's Try it (crew/trial.py: the record in <state>/crew/.try/<id>.json, its `crew`
frames, Stop, seen, the Attention row), with the step runner in place of one agent: `python -m
halo_harness.crew.try_flow` in a throwaway copy of the project (crew/trial_run.py), each agent a child of a print-mode
session there (crew/runner_session.py), so an ask is answered no and listed. The cost band is in the record before
the first call. Each line the run prints (a step, an agent, a check, the end) is folded into the record as it comes:

    {..., kind: workflow, workflow, steps: [{n, name, state, why, rounds, stop, cost_usd, agents: [{name, state,
     cost_usd, seconds, text, error}]}], checks: [{n, round, yes, line}], line}

A record is always written through store.write_text (a page polls it); a failure in this thread is caught, written
into the record and ends the run with a plain line.
"""

from __future__ import annotations

import json
import secrets
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.crew import flow_cost, trial, trial_run


def start_flow(wf: dict, agents: dict, request: str, *, cwd, state_dir=None, publish: Optional[Callable] = None,
               model: str = "") -> dict:
    tid = "t" + secrets.token_hex(5)
    name = str(wf.get("name"))
    est = flow_cost.band(wf, lambda n: agents.get(n), state_dir)
    rec = {"id": tid, "kind": "workflow", "agent": name, "workflow": name, "request": request, "state": "running",
           "started": time.time(), "ended": None, "where": "", "reply": "", "used": {}, "denied": [], "cost_usd": None,
           "turns": None, "seconds": None, "now": "starting", "seen": False, "error": "", "line": "",
           "estimate": {"usd": est["high"] if not est["unknown"] else None, "line": est["line"]},
           "model": "", "model_line": "each agent on its own model", "steps": [], "checks": []}
    trial._save(rec, state_dir)
    th = threading.Thread(target=_run, args=(rec, wf, agents, request, cwd, state_dir, publish, model),
                          name=f"crew-try-{tid}", daemon=True)
    th.start()
    return trial._public(rec)


def _step(rec: dict, n: int) -> dict:
    for s in rec["steps"]:
        if s["n"] == n:
            return s
    s = {"n": n, "name": "", "state": "waiting", "why": "", "rounds": 0, "stop": "", "cost_usd": 0.0, "agents": []}
    rec["steps"].append(s)
    return s


def fold(line: str, rec: dict) -> bool:
    """One line of the run's output into the record; True when the page should hear it."""
    try:
        ev = json.loads(line)
    except ValueError:
        return False
    if not isinstance(ev, dict) or "crew" not in ev:
        return False
    kind = ev.pop("crew")
    if kind == "start":
        rec["steps"] = [{"n": i, "name": n, "state": "waiting", "why": "", "rounds": 0, "stop": "", "cost_usd": 0.0, "agents": []}
                        for i, n in enumerate(ev.get("steps") or [], 1)]
        rec["now"] = "running"
    elif kind == "step":
        s = _step(rec, int(ev.get("n") or 0))
        s.update({k: ev[k] for k in ("name", "state", "why", "rounds", "stop", "cost_usd") if k in ev})
        rec["now"] = f"step {s['n']}: {s['name']} ({s['state']})"
    elif kind == "agent":
        s = _step(rec, int(ev.get("n") or 0))
        row = {k: ev.get(k) for k in ("name", "state", "round", "cost_usd", "seconds", "text", "error")}
        s["agents"] = [a for a in s["agents"] if a.get("name") != row["name"]] + [row]
        for t, k in (ev.get("used") or {}).items():
            rec["used"][t] = rec["used"].get(t, 0) + int(k or 0)
    elif kind == "check":
        rec["checks"].append({k: ev.get(k) for k in ("n", "round", "yes", "line")})
    elif kind == "end":
        rec["line"] = str(ev.get("line") or "")
        rec["reply"] = str(ev.get("text") or "")
        rec["cost_usd"] = ev.get("cost_usd")
        rec["flow_state"] = ev.get("state")
        if ev.get("problems"):
            rec["error"] = "; ".join(ev["problems"][:3])
    else:
        return False
    return True


def _run(rec: dict, wf: dict, agents: dict, request: str, cwd, state_dir, publish, model: str) -> None:
    copy, repo, spec = None, None, None
    try:
        copy, rec["where"], repo = trial_run.throwaway(cwd)
        fd, path = tempfile.mkstemp(prefix="halo-flow-", suffix=".json")
        spec = Path(path)
        with open(fd, "w", encoding="utf-8") as f:
            json.dump({"workflow": wf, "agents": agents, "request": request, "model": model}, f)
        proc = trial_run.spawn([sys.executable, "-m", "halo_harness.crew.try_flow", str(spec)], copy)
        with trial._LOCK:
            trial.RUNNING[rec["id"]] = (proc, rec)
        rec["now"] = "running"
        trial._emit(rec, state_dir, publish)
        for line in proc.stdout:
            if fold(line, rec):
                trial._emit(rec, state_dir, publish)
        err = proc.stderr.read() if proc.stderr else ""
        code = proc.wait()
        stopped = rec.get("state") == "stopping"
        flow = rec.get("flow_state")
        rec["state"] = "stopped" if stopped else ("done" if code == 0 and flow == "done" else "failed")
        if rec["state"] == "failed" and not rec.get("line"):
            rec["error"] = rec.get("error") or " ".join(err.split())[-600:] or f"the run ended with {code}"
        elif rec["state"] == "failed":
            rec["error"] = rec.get("error") or rec["line"]
    except Exception as e:
        rec["state"], rec["error"] = "failed", f"{type(e).__name__}: {e}"
    finally:
        with trial._LOCK:
            trial.RUNNING.pop(rec["id"], None)
        if copy is not None:
            trial_run.drop(copy, repo)
        if spec is not None:
            spec.unlink(missing_ok=True)
        rec["ended"] = time.time()
        rec["seconds"] = round(rec["ended"] - rec["started"], 1)
        rec["now"] = ""
        for s in rec.get("steps") or []:
            if s.get("state") in ("running", "waiting") and rec["state"] != "done":
                s["state"] = "stopped" if s.get("state") == "running" else "not run"
        try:
            trial._emit(rec, state_dir, publish)
        except Exception as e:  # the record could not be written: say so where the page reads it next
            rec["error"] = f"the record could not be written: {type(e).__name__}: {e}"
