"""halo_harness.studio.local_verify_job -- Halo 3.3.6.0 R2: Download and verify (plans/local-model-fit-brief.md
F4): one job that pulls a library row onto a host (studio/local_pull_job.py, its `pull` frames), runs the battery on
the new tag (studio/local_probe_job.py, its `probe` frames: the profile is written to the capability cache), then
offers the role ("assign `verify` to ol:<model>@<host>?" -> POST local/library/assign, the teams path). Every
stage change publishes

    {session_id: "local", event: "verify", ts, data: {job, host, name, stage: "pull" | "probe" | "offer" | "done",
     pull_job, probe_job, done, ok, say, role, offer {role, ref, ok, why, line} | None, started, error}}

so the Jobs list shows both stages. Nothing downloads until the button is pressed; a host a fleet member serves
runs Pull and Probe on that member (the two buttons), not this job.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

KEEP_DONE = 20
POLL_S = 0.2
PULL_MAX_S = 6 * 3600.0
PROBE_MAX_S = 1800.0
KEYS = ("job", "host", "name", "stage", "pull_job", "probe_job", "done", "ok", "say", "role", "offer", "started", "error")
_lock = threading.Lock()
_jobs: dict = {}
_seq = [0]


def view(job: dict) -> dict:
    return {k: job.get(k) for k in KEYS}


def current() -> dict:
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda j: -j["started"])
        return {"jobs": [view(j) for j in jobs], "running": sum(1 for j in jobs if not j["done"])}


def _send(job: dict) -> None:
    if job.get("publish") is not None:
        try:
            job["publish"]({"session_id": "local", "event": "verify", "ts": time.time(), "data": view(job)})
        except Exception:
            pass


def _wait(read: Callable[[], Optional[dict]], limit: float) -> Optional[dict]:
    t0 = time.monotonic()
    while time.monotonic() - t0 < limit:
        v = read()
        if v is None or v.get("done"):
            return v
        time.sleep(POLL_S)
    return read()


def _probe_view(job_id: str) -> Optional[dict]:
    from halo_harness.studio.local_probe_job import current as probes
    return next((j for j in probes()["jobs"] if j.get("job") == job_id), None)


def offer_for(role: str, host: str, model: str, profile: Optional[dict]) -> Optional[dict]:
    """The role offer after the probe: ok when the battery says the model holds the role's placement gate."""
    if not role:
        return None
    from halo_harness.models_library.presets import PRESETS, preset_for_role
    from halo_harness.providers.placement import verdict
    preset = preset_for_role(role)
    place = (PRESETS.get(preset) or {}).get("role") or role
    v = verdict(profile, place) if profile else {"ok": None, "why": "not probed"}
    ref = f"ol:{model}@{host}"
    ok = v["ok"] is not False and profile is not None
    return {"role": role, "ref": ref, "ok": ok, "why": v.get("why") or "",
            "line": f"assign `{role}` to {ref}?" if ok else f"{model} is not ready for `{role}`: {v.get('why')}"}


def _new(host: str, name: str, role: str, publish) -> dict:
    _seq[0] += 1
    job = {"job": f"verify-{time.strftime('%H%M%S')}-{_seq[0]}", "host": host, "name": name, "stage": "pull",
           "pull_job": None, "probe_job": None, "done": False, "ok": False, "say": f"pulling {name} on {host}",
           "role": role, "offer": None, "started": round(time.time(), 3), "error": None, "publish": publish}
    done = [j for j in _jobs.values() if j["done"]]
    for old in sorted(done, key=lambda j: j["started"])[:max(0, len(done) - KEEP_DONE + 1)]:
        _jobs.pop(old["job"], None)
    _jobs[job["job"]] = job
    return job


def _end(job: dict, ok: bool, say: str, **more) -> None:
    with _lock:
        job.update(done=True, ok=ok, say=say, **more)
    _send(job)


def start(host, name: str, publish: Optional[Callable] = None, *, state_dir=None, role: str = "",
          pull=None, runner=None) -> dict:
    """Pull `name` onto `host`, probe it, offer `role`; the job's view (`joined` when one runs for it already)."""
    from halo_harness.studio import local_probe_job as Q
    from halo_harness.studio import local_pull_job as P
    with _lock:
        hit = next((j for j in _jobs.values() if not j["done"] and j["host"] == host.name and j["name"] == name), None)
        if hit is not None:
            return {**view(hit), "joined": True}
        job = _new(host.name, name, role, publish)

    def body() -> None:
        try:
            pv = P.start(host, name, publish, state_dir=state_dir, pull=pull)
            with _lock:
                job["pull_job"] = pv["job"]
            _send(job)
            got = _wait(lambda: P.get(pv["job"]), PULL_MAX_S) or {}
            if not got.get("ok"):
                return _end(job, False, got.get("say") or f"the pull of {name} stopped", error=got.get("error") or "pull")
            with _lock:
                job.update(stage="probe", say=f"pulled; probing {name} on {host.name} (about 8 requests, 1-3 minutes)")
            qv = Q.start(host, name, publish, state_dir=state_dir, runner=runner)
            with _lock:
                job["probe_job"] = qv["job"]
            _send(job)
            pr = _wait(lambda: _probe_view(qv["job"]), PROBE_MAX_S) or {}
            if not pr.get("ok"):
                return _end(job, False, pr.get("say") or pr.get("error") or "the probe stopped", error="probe")
            offer = offer_for(role, host.name, name, pr.get("profile"))
            _end(job, True, f"pulled and probed: {pr.get('say') or 'profile written'}", stage="offer" if offer else "done",
                 offer=offer)
        except Exception as e:  # the job says where it stopped; the page keeps its rows
            _end(job, False, f"download and verify stopped: {type(e).__name__}: {e}", error=type(e).__name__)

    threading.Thread(target=body, name=f"halo-local-{job['job']}", daemon=True).start()
    _send(job)
    return {**view(job), "joined": False}


def reset() -> None:
    with _lock:
        _jobs.clear()
