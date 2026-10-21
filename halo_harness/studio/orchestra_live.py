"""halo_harness.studio.orchestra_live -- the one Orchestra run Studio drives
(Halo 3.0.3.0 round R4).

`start(run_dir, goal, ...)` runs `orchestra.run.run()` (or, for a dry run,
the lead's split check alone) on a daemon thread, so no request thread ever
waits on a model. A second thread tails the run's `events.jsonl` every
`TAIL_S` seconds and publishes each new state / claim / merge / gate /
report line on Studio's live feed as `orchestra_<kind>` with
`session_id: "orchestra:<run-id>"` (the lines a worker child process writes
reach the feed the same way as the runner's own). `note` lines stay in the
file. One run at a time: `live_id()` names it while it runs.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import jsonl

TAIL_S = 0.25
_lock = threading.Lock()
_live: dict = {}


def live_id() -> Optional[str]:
    with _lock:
        t = _live.get("thread")
        return _live.get("run_id") if t is not None and t.is_alive() else None


def frame_of(run_id: str, entry: dict) -> Optional[dict]:
    kind = run_events.FEED_KINDS.get(entry.get("kind"))
    if kind is None:
        return None
    return {"session_id": f"orchestra:{run_id}", "event": kind, "data": dict(entry, run=run_id),
            "turn": None, "agent_id": None, "ts": entry.get("ts") or time.time()}


def tail(run_dir: Path, publish: Callable, done: threading.Event, since: int = 0) -> None:
    """Publish every new line until `done` is set, then the last ones."""
    seen = since
    while True:
        finished = done.is_set()
        for entry in run_events.read(run_dir, since=seen):
            seen += 1
            frame = frame_of(run_dir.name, entry)
            if frame is not None:
                try:
                    publish(frame)
                except Exception:
                    pass
        if finished:
            return
        done.wait(TAIL_S)


def dry_split(run_dir: Path, goal, call: Callable) -> dict:
    """The lead's split, checked by code, nothing claimed: dry_run.json and one state line."""
    from halo_harness.orchestra.goal import repo_root_of
    from halo_harness.orchestra.run import goal_units
    from halo_harness.orchestra.split import StopRun, parse_answer, split_prompt, validate_jobs
    out = {"jobs": [], "problems": [], "stop": "", "cost_usd": 0.0}
    try:
        units = goal_units(repo_root_of(run_dir), goal)
        answer = call(split_prompt(goal, units))
        text = answer.get("text") if isinstance(answer, dict) else answer
        out["cost_usd"] = float(answer.get("cost_usd") or 0.0) if isinstance(answer, dict) else 0.0
        data = parse_answer(str(text or ""))
        if isinstance(data, dict) and data.get("stop"):
            out["stop"] = str(data["stop"])
        else:
            out["problems"] = validate_jobs(data, [u.key for u in units], goal.workers, getattr(goal, "handoffs", None))
            if not out["problems"]:
                out["jobs"] = [{"id": f"job-{i}", "worker": i, "title": j["title"], "claims": list(j["claims"])}
                               for i, j in enumerate(data["jobs"], 1)]
    except StopRun as e:
        out["stop"] = str(e)
    jsonl.write_json(run_dir / "dry_run.json", out)
    text = (f"dry run: the lead would stop: {out['stop']}" if out["stop"] else
            f"dry run: the split does not pass the check: {out['problems'][0]}" if out["problems"] else
            f"dry run: {len(out['jobs'])} job(s), nothing claimed")
    run_events.log(run_dir, "state", text, step="split", dry_run=True, jobs=len(out["jobs"]))
    return out


def _work(run_dir: Path, goal, model, dry_run: bool, runner, done: threading.Event) -> None:
    try:
        if runner is not None:
            kwargs = runner(run_dir, goal, model)
        else:
            from halo_harness.orchestra.adapters import model_call, real_adapters
            kwargs = {"model_calls": model_call(model, goal.lead, cwd=run_dir)} if dry_run else \
                real_adapters(run_dir, goal, model)
        if dry_run:
            dry_split(run_dir, goal, kwargs["model_calls"])
        else:
            from halo_harness.orchestra.run import run
            from halo_harness.supervise.heartbeat import Beat
            with Beat(run_dir, by="studio"):  # 3.1.8.0 R1: the runner heartbeat (supervise/heartbeat.py)
                run(run_dir, **kwargs)
    except Exception as e:  # the run log says what went wrong; Studio stays up
        try:
            run_events.log(run_dir, "state", f"the runner stopped on an error: {type(e).__name__}: {e}",
                           step="runner", error=f"{type(e).__name__}: {e}")
        except OSError:
            pass
    finally:
        done.set()


def start(run_dir, goal, *, model: Optional[str] = None, dry_run: bool = False, runner=None,
          publish: Optional[Callable] = None) -> bool:
    """Start the run on its threads; False when another run is still live."""
    run_dir = Path(run_dir)
    done = threading.Event()
    with _lock:
        t = _live.get("thread")
        if t is not None and t.is_alive():
            return False
        worker = threading.Thread(target=_work, args=(run_dir, goal, model, dry_run, runner, done),
                                  name=f"halo-orchestra-{run_dir.name}", daemon=True)
        _live.update(run_id=run_dir.name, thread=worker, done=done, run_dir=run_dir)
        worker.start()
    if publish is not None:
        threading.Thread(target=tail, args=(run_dir, publish, done), name=f"halo-orchestra-feed-{run_dir.name}",
                         daemon=True).start()
    return True


def wait(timeout: float = 30.0) -> bool:
    """Tests: wait for the live run to end. True when it did."""
    with _lock:
        t = _live.get("thread")
    if t is None:
        return True
    t.join(timeout)
    return not t.is_alive()
