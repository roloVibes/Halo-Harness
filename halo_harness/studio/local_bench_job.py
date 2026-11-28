"""halo_harness.studio.local_bench_job -- Halo 3.3.6.0 R5: the Local tab's bench jobs (providers/local_bench.py; the
routes are studio/local_bench_api.py; the pattern is studio/local_probe_job.py's). One job per host + model: a second
ask while it runs joins it. A job is a daemon thread here (a host this machine reaches); every line it says publishes

    {session_id: "local", event: "bench", ts, data: {job, host, model, quick, line, lines, done, ok, error, card,
     started, cost}}

`current(host=None)` lists the jobs running and the last ended ones for a page that opens later.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional
from halo_harness.newest_first import newest_first  # 3.3.8.1: a same-ms tie, the later row first

KEEP_DONE = 20
KEEP_LINES = 40
_lock = threading.Lock()
_jobs: dict = {}
_seq = [0]
KEYS = ("job", "host", "model", "quick", "line", "lines", "done", "ok", "error", "card", "started", "cost", "kind")


def view(job: dict) -> dict:
    return {k: (list(job[k]) if k == "lines" else job.get(k)) for k in KEYS}


def current(host: Optional[str] = None) -> dict:
    with _lock:
        jobs = newest_first((j for j in _jobs.values() if not host or j["host"] == host), lambda j: j["started"])
        return {"jobs": [view(j) for j in jobs], "running": sum(1 for j in jobs if not j["done"])}


def running_on(host: str) -> Optional[dict]:
    with _lock:
        return next((view(j) for j in _jobs.values() if not j["done"] and j["host"] == host), None)


def _send(job: dict) -> None:
    if job.get("publish") is not None:
        try:
            job["publish"]({"session_id": "local", "event": "bench", "ts": time.time(), "data": view(job)})
        except Exception:
            pass


def start(host, model: str, publish: Optional[Callable] = None, *, state_dir=None, quick: bool = False, cost: str = "",
          card=None, runner: Optional[Callable] = None, kind: str = "bench") -> dict:
    """Bench `model` on `host`; the job's view, `joined` when it was running already. 3.6.0.25 T: `kind` "sweep" is
    the sweep (providers/local_sweep_run.sweep, `runner`), which gets the job's Stop (`stop(host, model)`)."""
    from halo_harness.providers.ollama import ollama_names_match
    with _lock:
        hit = next((j for j in _jobs.values() if not j["done"] and j["host"] == host.name and j["kind"] == kind
                    and ollama_names_match(j["model"], model)), None)
        if hit is not None:
            return {**view(hit), "joined": True}
        _seq[0] += 1
        job = {"job": f"bench-{time.strftime('%H%M%S')}-{_seq[0]}", "host": host.name, "model": model, "quick": quick,
               "line": cost, "lines": [], "done": False, "ok": False, "error": None, "card": None,
               "started": round(time.time(), 3), "cost": cost, "kind": kind, "publish": publish,
               "stop": threading.Event()}
        done = [j for j in _jobs.values() if j["done"]]
        for old in sorted(done, key=lambda j: j["started"])[:max(0, len(done) - KEEP_DONE + 1)]:
            _jobs.pop(old["job"], None)
        _jobs[job["job"]] = job
    from halo_harness.providers.local_bench import bench
    fn = runner or bench

    def said(line: str) -> None:
        with _lock:
            job["line"] = line
            job["lines"] = (job["lines"] + [line])[-KEEP_LINES:]
        _send(job)

    def body() -> None:
        try:
            more = {"stop": job["stop"]} if kind != "bench" else {"quick": quick}
            got = fn(host, model, card=card, state_dir=state_dir, on_line=said, check_busy=False, **more)
        except Exception as e:
            got = {"ok": False, "say": f"the {kind} of {model} stopped: {type(e).__name__}: {e}"}
        ok = bool(got.get("ok"))
        with _lock:
            job.update(done=True, ok=ok, error=None if ok else got.get("say"), card=got if ok else None,
                       line=got.get("say") if kind != "bench" else (f"benched: up to {(got.get('max_gpu_window') or 0) // 1024}k on the GPU, reply reserve "
                             f"{got.get('reserve_floor') or 'over 512'}" if ok else got.get("say") or "the bench stopped"))
        if ok:
            from halo_harness.studio.local_pull_job import after_change
            after_change()
        _send(job)

    threading.Thread(target=body, name=f"halo-local-{job['job']}", daemon=True).start()
    _send(job)
    return {**view(job), "joined": False}


def stop(host: str, model: str, kind: str = "sweep") -> bool:
    """3.6.0.25 T: the Stop of a running sweep: it ends after the running load and keeps what was measured."""
    from halo_harness.providers.ollama import ollama_names_match
    with _lock:
        hit = next((j for j in _jobs.values() if not j["done"] and j["host"] == host and j["kind"] == kind
                    and ollama_names_match(j["model"], model)), None)
    if hit is None:
        return False
    hit["stop"].set()
    return True
