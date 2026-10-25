"""halo_harness.studio.start_job -- the one `halo start` Studio runs (Halo
3.1.1.0 R1): `POST /api/start` (studio/start_api.py) starts it.

The start runs in this process on a daemon thread, the same as
`halo start --yes` (no Enter between steps, the plan approved, the real
models you configured; `HALO_START_FAKE=1` in Studio's environment runs the
fake ones). Every frame the engine emits is kept and published on Studio's
live feed as a `start` frame:

    {session_id: "start:<job id>", event: "start", ts,
     data: {job, step: 1..7, total: 7, key, title, why, command, state, lines}}

and when the start ends one more:

    data: {job, key: "summary", state: "finished", summary: {ok, stopped_at, reason, lineup, repo, run, report, coach}}

(3.2.2.0 R1: a start that failed on an error its steps did not expect also
carries `error_log`, the file holding the traceback; the reason is the one
`<Type>: <message>` line.)

`current()` is the job as `GET /api/start` shows it (the latest frame per
step, the summary once there); `stop()` asks the running start to end.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

_lock = threading.Lock()
_state: dict = {"job": None}  # the one job, by reference


def _public(job: Optional[dict]) -> Optional[dict]:
    if not job:
        return None
    frames = sorted(job["frames"].values(), key=lambda f: f["step"])
    thread = job.get("thread")
    return {"job": job["id"], "running": bool(thread is not None and thread.is_alive()), "fake": job["fake"],
            "started": job["started"], "steps": frames, "summary": job.get("summary")}


def current() -> Optional[dict]:
    with _lock:
        return _public(_state["job"])


def running() -> bool:
    with _lock:
        t = (_state["job"] or {}).get("thread")
        return bool(t is not None and t.is_alive())


def stop() -> bool:
    with _lock:
        job = _state["job"] or {}
        run = job.get("run")
        alive = job.get("thread") is not None and job["thread"].is_alive()
    if run is not None and alive:
        run.cancel()
        return True
    return False


def start(state_dir, publish: Optional[Callable[[dict], None]] = None) -> dict:
    """Start the job; its public view. The caller checked that none runs."""
    from halo_harness.start.engine import Options, StartRun
    from halo_harness.start.errors import failed_summary
    job_id = time.strftime("%Y%m%d-%H%M%S")
    job: dict = {"id": job_id, "frames": {}, "summary": None, "started": round(time.time(), 3)}

    def send(data: dict) -> None:
        if publish is None:
            return
        try:
            publish({"session_id": f"start:{job_id}", "event": "start", "data": dict(data, job=job_id),
                     "ts": time.time()})
        except Exception:
            pass

    def on_frame(frame: dict) -> None:
        with _lock:
            job["frames"][frame["key"]] = frame
        send(frame)

    def finish(summary: dict) -> None:
        short = {k: v for k, v in summary.items() if k != "steps"}
        with _lock:
            job["summary"] = short
        send({"key": "summary", "state": "finished", "summary": short})

    try:
        run = StartRun(Options(yes=True, state_dir=state_dir, studio=False), emit=on_frame)
    except Exception as e:  # 3.2.2.0 R1: the start could not be built: the job ends at once with the one line
        job.update(run=None, fake=False, thread=None)
        with _lock:
            _state["job"] = job
        finish(failed_summary(state_dir, None, e))
        return current() or {}
    job.update(run=run, fake=run.fake)

    def body() -> None:
        try:
            summary = run.run()
        except Exception as e:  # anything the engine did not turn into a failed step
            summary = failed_summary(state_dir, run.run_dir, e)
        finish(summary)

    job["thread"] = threading.Thread(target=body, name=f"halo-studio-start-{job_id}", daemon=True)
    with _lock:
        _state["job"] = job
    job["thread"].start()
    return current() or {}
