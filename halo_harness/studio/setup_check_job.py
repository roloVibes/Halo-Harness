"""halo_harness.studio.setup_check_job -- the Check block's one background job
(Halo 3.3.0.0 R3, Studio's Setup section): `POST setup/check` starts it
(studio/setup_check_api.py). The start_job pattern: one job in this process,
on a daemon thread, every frame kept and published on Studio's live feed.

The ticked checks run in checks/catalog.py's order through `checks.run_many`
(doctor, catalog, hello, the steward, the gym, then the enabled packs' Setup checks: 3.4.0.0 B, the guided first
run is the first-run pack's). Each check publishes

    {session_id: "setup:<job id>", event: "setup", ts,
     data: {job, key, title, state: running | done | failed, lines}}

when it starts and when it ends, and the job ends on one more:

    data: {job, key: "summary", state: "finished", ok, stopped, results: [{key, title, ok, lines}]}

which is also written to `<state>/studio/last-check.json` (the status strip's
"Last check"). `current()` is the job as `GET setup/check` shows it (the
latest frame per check, the summary once there); `stop()` ends the list
before the next check.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

_lock = threading.Lock()
_state: dict = {"job": None}
POLL_S = 0.5


def _public(job: Optional[dict]) -> Optional[dict]:
    if not job:
        return None
    from halo_harness.checks.catalog import KEYS
    order = {k: i for i, k in enumerate(KEYS)}
    frames = sorted(job["frames"].values(), key=lambda f: order.get(f["key"], 99))
    thread = job.get("thread")
    return {"job": job["id"], "running": bool(thread is not None and thread.is_alive()), "started": job["started"],
            "keys": list(job["keys"]), "checks": frames, "summary": job.get("summary")}


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
        alive = job.get("thread") is not None and job["thread"].is_alive()
        if alive:
            job["stop"] = True
    return bool(alive)


def start(keys, ctx, state_dir, publish: Optional[Callable[[dict], None]] = None) -> dict:
    """Start the job on `keys` (known keys; the caller checked that none runs); its public view."""
    from halo_harness.checks import catalog as C
    from halo_harness.studio.setup_check_state import write_last_check
    keys = C.ordered(keys)
    job_id = time.strftime("%Y%m%d-%H%M%S")
    job: dict = {"id": job_id, "keys": keys, "frames": {}, "summary": None, "started": round(time.time(), 3), "stop": False}

    def send(data: dict) -> None:
        if publish is None:
            return
        try:
            publish({"session_id": f"setup:{job_id}", "event": "setup", "data": dict(data, job=job_id), "ts": time.time()})
        except Exception:
            pass

    def frame(key: str, state: str, lines: list) -> None:
        f = {"job": job_id, "key": key, "title": C.check(key)["title"], "state": state, "lines": list(lines)}
        with _lock:
            job["frames"][key] = f
        send(f)

    def each(key, ok, lines) -> None:
        if ok is None:
            frame(key, "running", [C.detail_line(C.check(key), ctx)])
        else:
            frame(key, "done" if ok else "failed", lines)

    def body() -> None:
        results = []
        try:
            results = [list(r) for r in C.run_many(keys, ctx, on_each=each, stop=lambda: bool(job.get("stop")))]
        except Exception as e:  # anything run_many did not turn into a failed check
            results.append(["error", False, [f"{type(e).__name__}: {e}"]])
        stopped = len(results) < len(keys)
        rows = [{"key": k, "title": C.check(k)["title"] if k in C.KEYS or C.known_key(k) else k, "ok": bool(ok),
                 "lines": list(lines)}
                for k, ok, lines in results]
        summary = {"ok": bool(rows) and not stopped and all(r["ok"] for r in rows), "stopped": stopped, "results": rows}
        try:
            write_last_check(state_dir, {"when": round(time.time(), 3), **summary})
        except OSError:
            pass
        with _lock:
            job["summary"] = summary
        send({"key": "summary", "state": "finished", **summary})

    job["thread"] = threading.Thread(target=body, name=f"halo-studio-setup-check-{job_id}", daemon=True)
    with _lock:
        _state["job"] = job
    job["thread"].start()
    return current() or {}
