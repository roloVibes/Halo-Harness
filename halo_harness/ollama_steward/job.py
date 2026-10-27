"""halo_harness.ollama_steward.job -- Halo 3.3.4.0 R4: the steward runs on
its own, one job per state dir.

`StewardJob(state_dir, host=None)` owns the server-log tail and the
`/api/ps` poll (`server_log.watch`, on its own daemon thread, for the host
this machine serves) and a timer: every `ollama.steward.every_s` (300 s)
while calls flow (a ledger line in the last FLOW_S) or at once when an event
with `notify` fires, `run_once` = the rules (`rules.gather` + `run_rules`)
-> `steward.run` (the mode's changes) -> the agent's note (agent.py) when a
model is configured and something is new. Each `say` is a `note` line in
`<state>/ollama/steward.jsonl` (notes.py) and, through `publish` (Studio's
`bridge_for(server).publish_local`), a frame:

    {session_id: "ollama:steward", event: "steward", ts,
     data: {stage: "finding" | "change" | "note" | "idle", say, data}}

`current(state_dir)` is the job's view for a page that opens later (the
frames so far). One instance per state dir: an OS lock on
`<state>/ollama/steward-job.lock`, held while the job runs; a second job
does not start and names the holder (job_state.py: where, pid, since). It starts
with Studio (studio/server.py) and the fleet hub (fleet/hub.py) unless
`ollama.steward.job` is false; `halo ollama steward --watch` runs it in the
foreground; `halo ollama steward status` reads job_state.py.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from halo_harness.ollama_steward import job_state

EVERY_S = 300.0
FLOW_S = 900.0
TICK_S = 5.0
FRAMES = 50
_JOBS: dict = {}  # str(state_dir) -> the running StewardJob of this process


def every_s() -> float:
    from halo_harness.ollama_steward.agent import _cfg
    v = _cfg("ollama.steward.every_s", EVERY_S)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else EVERY_S


def enabled() -> bool:
    from halo_harness.ollama_steward.agent import _cfg
    return _cfg("ollama.steward.job", True) is not False


class StewardJob:
    def __init__(self, state_dir, host=None, *, where: str = "watch", publish: Optional[Callable] = None,
                 say: Optional[Callable] = None, clock: Callable = time.time, caller: Optional[Callable] = None,
                 readers: Optional[dict] = None, watch: Optional[Callable] = None, model=None) -> None:
        self.state_dir, self.host, self.where = state_dir, host, where
        self.publish, self.say_out, self.clock = publish, say, clock
        self.caller, self.readers, self.watch_fn, self._model = caller, readers, watch, model
        self.stop_event, self.wake = threading.Event(), threading.Event()
        self.frames: list = []
        self.notify = 0
        self.last_run: Optional[float] = None
        self.idle = False
        self.lock = None
        self.threads: list = []

    # ---- the frames -----------------------------------------------------------------------
    def emit(self, stage: str, say: str, data: Optional[dict] = None, *, note: bool = True, **kw) -> Optional[dict]:
        from halo_harness.ollama_steward import notes
        row = notes.append(self.state_dir, stage, say, data=data, where=self.where, now=self.clock(), **kw) \
            if note else None
        frame = {"session_id": "ollama:steward", "event": "steward", "ts": self.clock(),
                 "data": {"stage": stage, "say": say, "data": data or {}}}
        self.frames = (self.frames + [frame])[-FRAMES:]
        if self.say_out is not None:
            self.say_out(say)
        if self.publish is not None:
            try:
                self.publish(frame)
            except Exception:
                pass
        return row

    # ---- when it runs ---------------------------------------------------------------------
    def on_event(self, ev: dict) -> None:
        if ev.get("notify") and ev.get("severity") in ("warn", "error"):
            self.notify += 1
            self.wake.set()

    def due(self, now: float) -> "tuple[bool, str]":
        if self.notify:
            return True, f"{self.notify} server events"
        if self.last_run is not None and now - self.last_run < every_s():
            return False, "not yet"
        last = job_state.last_call_at(self.state_dir)
        if last is None or now - last > FLOW_S:
            return False, "no calls in the last 15 minutes"
        return True, "calls flow"

    def tick(self, now: Optional[float] = None) -> Optional[dict]:
        now = self.clock() if now is None else now
        ok, why = self.due(now)
        if ok:
            return self.run_once(now)
        if why.startswith("no calls") and not self.idle:
            self.idle = True
            self.emit("idle", f"steward idle: {why}")
            job_state.update(self.state_dir, idle=why)
        return None

    # ---- one pass -------------------------------------------------------------------------
    def model(self) -> "tuple[Optional[str], str]":
        if self._model is not None:
            return self._model if isinstance(self._model, tuple) else (self._model, "given")
        from halo_harness.ollama_steward.agent import choose_model
        return choose_model(state_dir=self.state_dir)

    def run_once(self, now: Optional[float] = None) -> dict:
        from halo_harness.ollama_steward import agent, steward
        from halo_harness.ollama_steward.rules import format_finding, gather, run_rules
        now = self.clock() if now is None else now
        notify, self.notify, self.last_run, self.idle = self.notify, 0, now, False
        ctx = gather(self.state_dir, **(self.readers if self.readers is not None else job_state.readers()))
        found = run_rules(ctx)
        said: list = []
        done = steward.run(self.state_dir, found=found, say=said.append, now=now)
        named = job_state.noted_findings(self.state_dir, now)
        for f in found:
            if f["id"] not in named:
                self.emit("finding", format_finding(f)[0], {"finding": f["id"], "severity": f["severity"],
                                                             "key": f["key"]}, attention=f["severity"] == "error")
        for r in done["rolled_back"] + done["applied"]:
            self.emit("change", r["say"], {"change": r["id"], "key": r["key"], "kind": r["kind"]}, attention=True)
        for r in done["proposed"]:
            self.emit("change", f"steward proposes: {r['field']} {r.get('from')} -> {r['to']} for {r['key']} "
                                f"({r['why']}); halo ollama steward apply {r['id']}",
                      {"change": r["id"], "key": r["key"], "kind": "proposal"})
        model, model_why = self.model()
        note = None
        if model:
            go, why = agent.due(self.state_dir, done, notify=notify, now=now)
            if go:
                extra: list = []
                note, _outcomes = agent.write_note(self.state_dir, ctx, done, model=model, caller=self.caller,
                                                   say=extra.append, where=self.where, now=now)
                for line in extra:
                    stage = "change" if line.startswith(("steward:", "steward proposes")) else "finding"
                    self.emit(stage, line, {"from": "model"}, attention=line.startswith("steward:"))
                if note is not None:
                    self.emit("note", note["say"], {"note": note["id"], "lines": note["lines"], "cost": note["cost"],
                                                    "attention": note["attention"]}, note=False)
        counts = {k: len(done[k]) for k in ("findings", "applied", "proposed", "rolled_back")}
        job_state.update(self.state_dir, last_run={"at": now, "mode": done["mode"], **counts}, model=model,
                         model_why=model_why, idle=None, **({"last_note": {"at": now, "line": note["say"]}}
                                                            if note else {}))
        return {**done, "note": note, "model": model}

    # ---- the threads ----------------------------------------------------------------------
    def start(self) -> "tuple[bool, str]":
        held, why = job_state.acquire(self.state_dir, where=self.where)
        if not held:
            return False, why
        self.lock = held
        _JOBS[str(self.state_dir)] = self
        model, model_why = self.model()
        job_state.update(self.state_dir, model=model, model_why=model_why)
        host = self.host if self.host is not None else job_state.served_host()
        if host is not None and self.watch_fn is not False:
            fn = self.watch_fn or job_state.default_watch
            t = threading.Thread(target=lambda: fn(self.state_dir, host, self.stop_event, on_event=self.on_event),
                                 name="halo-steward-watch", daemon=True)
            self.threads.append(t)
            t.start()
        t = threading.Thread(target=self._loop, name="halo-steward-timer", daemon=True)
        self.threads.append(t)
        t.start()
        return True, f"steward job running ({self.where}); model: {model or model_why}"

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self.tick()
            except Exception as e:  # the job outlives one bad pass
                job_state.update(self.state_dir, error=f"{type(e).__name__}: {e}"[:300])
            self.wake.wait(TICK_S)
            self.wake.clear()

    def stop(self) -> None:
        self.stop_event.set()
        self.wake.set()
        if _JOBS.get(str(self.state_dir)) is self:
            _JOBS.pop(str(self.state_dir), None)
        if self.lock is not None:
            job_state.release(self.state_dir, self.lock)
            self.lock = None


def current(state_dir) -> Optional[dict]:
    """The running job of this process for `state_dir`: {where, frames} (a page's catch-up), or None."""
    job = _JOBS.get(str(state_dir))
    return {"where": job.where, "frames": list(job.frames)} if job is not None else None


def start_for(state_dir, *, where: str, publish: Optional[Callable] = None) -> Optional[StewardJob]:
    """Studio's and the hub's start: None when the job is off, background reads are off, or another holds it."""
    from halo_harness.config.paths import background_net_disabled
    if not enabled() or background_net_disabled() or str(state_dir) in _JOBS:
        return None
    job = StewardJob(state_dir, where=where, publish=publish)
    try:
        ok, _why = job.start()
    except Exception:
        return None
    return job if ok else None
