"""halo_harness.host.jobs -- the host's frames and jobs (Halo 3.3.7.0 R2; host/routes_act.py starts them).

    Bus()                         the frames a `GET stream` sends beside the server events: publish(kind, data) ->
                                  {seq, type, ts, data}; since(seq) -> the frames after it (the newest KEEP)
    Jobs(bus)                     one job per op request that runs long (`rerun_battery`, `bench`, `verify_twin`,
                                  `pull`): start(op, host, model, fn, by) -> the job's view; fn(on) runs on a daemon
                                  thread, `on({step?, of?, say?, ...})` updates the job and publishes a `job` frame;
                                  the job ends with the result fn returns ({ok, say, ...}); get(id) / list()

A job's view: {job, op, host, model, by, started, step, of, say, lines, done, ok, error, result}. The thread runs
inside host_client.serving() (no read in it goes through another host). Nothing here calls a model.
"""

from __future__ import annotations

import itertools
import threading
import time
from typing import Callable, Optional

KEEP = 400
KEEP_JOBS = 40
KEEP_LINES = 40


class Bus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._seq = itertools.count(1)
        self.frames: list = []

    def publish(self, kind: str, data) -> dict:
        with self._lock:
            frame = {"seq": next(self._seq), "type": kind, "ts": time.time(), "data": data}
            self.frames = (self.frames + [frame])[-KEEP:]
        return frame

    def since(self, seq: int) -> list:
        with self._lock:
            return [f for f in self.frames if f["seq"] > seq]

    def last_seq(self) -> int:
        with self._lock:
            return self.frames[-1]["seq"] if self.frames else 0


VIEW = ("job", "op", "host", "model", "by", "started", "step", "of", "say", "lines", "done", "ok", "error", "result")


class Jobs:
    def __init__(self, bus: Bus) -> None:
        self.bus = bus
        self._lock = threading.Lock()
        self._jobs: dict = {}
        self._seq = itertools.count(1)

    def view(self, job: dict) -> dict:
        return {k: (list(job[k]) if k == "lines" else job.get(k)) for k in VIEW}

    def _frame(self, job: dict) -> None:
        self.bus.publish("job", self.view(job))

    def running(self, op: str, host: str, model: str) -> Optional[dict]:
        from halo_harness.providers.ollama import ollama_names_match
        with self._lock:
            return next((self.view(j) for j in self._jobs.values() if not j["done"] and j["op"] == op
                         and j["host"] == host and ollama_names_match(j["model"], model)), None)

    def start(self, op: str, host: str, model: str, fn: Callable, *, by: str = "", say: str = "") -> dict:
        hit = self.running(op, host, model)
        if hit is not None:
            return {**hit, "joined": True}
        with self._lock:
            job = {"job": f"{op}-{time.strftime('%H%M%S')}-{next(self._seq)}", "op": op, "host": host, "model": model,
                   "by": by, "started": round(time.time(), 3), "step": 0, "of": None, "say": say, "lines": [],
                   "done": False, "ok": False, "error": None, "result": None}
            done = sorted((j for j in self._jobs.values() if j["done"]), key=lambda j: j["started"])
            for old in done[:max(0, len(done) - KEEP_JOBS + 1)]:
                self._jobs.pop(old["job"], None)
            self._jobs[job["job"]] = job

        def on(d: dict) -> None:
            with self._lock:
                for k in ("step", "of"):
                    if d.get(k) is not None:
                        job[k] = d[k]
                if d.get("say"):
                    job["say"] = str(d["say"])[:300]
                    job["lines"] = (job["lines"] + [job["say"]])[-KEEP_LINES:]
            self._frame(job)

        def body() -> None:
            from halo_harness.ollama_steward.host_client import serving
            try:
                with serving():
                    got = fn(on) or {}
            except Exception as e:
                got = {"ok": False, "say": f"{op} of {model} stopped: {type(e).__name__}: {e}"[:300]}
            with self._lock:
                ok = bool(got.get("ok"))
                job.update(done=True, ok=ok, error=None if ok else str(got.get("say") or got.get("error") or "")[:300],
                           result=got, say=str(got.get("say") or job["say"] or ("done" if ok else "stopped"))[:300])
            self._frame(job)

        threading.Thread(target=body, name=f"halo-host-{job['job']}", daemon=True).start()
        self._frame(job)
        return {**self.view(job), "joined": False}

    def get(self, jid: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(jid)
            return self.view(job) if job else None

    def list(self) -> list:
        with self._lock:
            return [self.view(j) for j in sorted(self._jobs.values(), key=lambda j: -j["started"])]

    def wait(self, jid: str, timeout: float = 10.0) -> Optional[dict]:
        """The tests' helper: the job's view once it is done (or as it stands at the timeout)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            v = self.get(jid)
            if v is None or v["done"]:
                return v
            time.sleep(0.05)
        return self.get(jid)


class Acts:
    """A host process's frames and jobs (one per HostService)."""

    def __init__(self) -> None:
        self.bus = Bus()
        self.jobs = Jobs(self.bus)


_OF_LOCK = threading.Lock()


def of(svc) -> Acts:
    with _OF_LOCK:
        got = getattr(svc, "_acts", None)
        if got is None:
            got = svc._acts = Acts()
        return got
