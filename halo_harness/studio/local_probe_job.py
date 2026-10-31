"""halo_harness.studio.local_probe_job -- Halo 3.3.6.0 R1: the Local tab's
probe jobs (the battery, providers/capability_battery.py; the routes are
studio/local_probe_api.py; the pattern is studio/local_pull_job.py's). One
job per host + model: a second ask while it runs joins it. A job on a host
this machine serves is a daemon thread here; a job on a host a fleet member
serves is that member's own (fleet/control_models.py `ollama_probe`), its
profile reaching this machine with the member's ledger push
(fleet/control_probes.py). Every step publishes

    {session_id: "local", event: "probe", ts, data: {job, host, model, step, of, probe, say, done, ok,
     error, profile, started, via, cost}}

`current()` lists the jobs running and the last ended ones for a page that
opens later.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

KEEP_DONE = 20
_lock = threading.Lock()
_jobs: dict = {}
_seq = [0]
KEYS = ("job", "host", "model", "step", "of", "probe", "say", "done", "ok", "error", "profile", "started", "via", "cost",
        "remote", "kind")


def view(job: dict) -> dict:
    return {k: job.get(k) for k in KEYS}


def current() -> dict:
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda j: -j["started"])
        return {"jobs": [view(j) for j in jobs], "running": sum(1 for j in jobs if not j["done"])}


def _find(host: str, model: str) -> Optional[dict]:
    from halo_harness.providers.ollama import ollama_names_match
    return next((j for j in _jobs.values() if not j["done"] and j["host"] == host
                 and ollama_names_match(j["model"], model)), None)


def _new(host: str, model: str, via: str, publish, remote: bool) -> dict:
    from halo_harness.providers.capability_battery import cost_line
    _seq[0] += 1
    job = {"job": f"probe-{time.strftime('%H%M%S')}-{_seq[0]}", "host": host, "model": model, "step": 0, "of": 6,
           "probe": "", "say": cost_line(model, host), "done": False, "ok": False, "error": None, "profile": None,
           "started": round(time.time(), 3), "via": via, "cost": cost_line(model, host), "remote": remote,
           "kind": "probe", "publish": publish}
    done = [j for j in _jobs.values() if j["done"]]
    for old in sorted(done, key=lambda j: j["started"])[:max(0, len(done) - KEEP_DONE + 1)]:
        _jobs.pop(old["job"], None)
    _jobs[job["job"]] = job
    return job


def _send(job: dict) -> None:
    if job.get("publish") is not None:
        try:
            job["publish"]({"session_id": "local", "event": "probe", "ts": time.time(), "data": view(job)})
        except Exception:
            pass


def compact(p: Optional[dict]) -> Optional[dict]:
    """The profile without its raw evidence (the page's form)."""
    if not isinstance(p, dict):
        return None
    return {k: v for k, v in p.items() if k not in ("evidence",)}


def finish(job: dict, got: dict) -> None:
    with _lock:
        ok = bool(got.get("ok"))
        job.update(done=True, ok=ok, error=None if ok else (got.get("error") or got.get("say")),
                   profile=compact(got) if ok else None, step=job.get("of") if ok else job.get("step"),
                   say=(f"probed: {got.get('sits')} · {'agentic-ready' if got.get('agentic_ready') else 'not agentic-ready'}"
                        if ok else got.get("say") or "the probe stopped"))
    if ok:
        from halo_harness.studio.local_pull_job import after_change
        after_change()
    _send(job)


def start(host, model: str, publish: Optional[Callable] = None, *, state_dir=None, force: bool = False,
          runner: Optional[Callable] = None) -> dict:
    """Probe `model` on `host` (this machine serves it); the job's view, `joined` when it was running already."""
    with _lock:
        hit = _find(host.name, model)
        if hit is not None:
            return {**view(hit), "joined": True}
        job = _new(host.name, model, "this machine", publish, False)
    from halo_harness.providers.capability_battery import run
    from halo_harness.providers.fit_meter import host_card_of
    fn = runner or run

    def on(d: dict) -> None:
        with _lock:
            job.update(step=d.get("step") or job["step"], of=d.get("of") or job["of"], probe=d.get("probe") or "",
                       say=d.get("say") or job["say"])
        _send(job)

    def body() -> None:
        try:
            got = fn(host, model, card=host_card_of(host, read=True), on_status=on, state_dir=state_dir, force=force)
        except Exception as e:
            got = {"ok": False, "say": f"the probe of {model} stopped: {type(e).__name__}: {e}"}
        finish(job, got)

    threading.Thread(target=body, name=f"halo-local-{job['job']}", daemon=True).start()
    _send(job)
    return {**view(job), "joined": False}


def start_remote(host_name: str, model: str, send: Callable[[dict], "tuple[int, dict]"], via: str,
                 publish: Optional[Callable] = None, *, member: str = "") -> "tuple[int, dict]":
    """The member's own job, started through `send({})`; its profile arrives with the member's ledger push."""
    with _lock:
        hit = _find(host_name, model)
        if hit is not None:
            return 200, {**view(hit), "joined": True}
    code, answer = send({})
    if code not in (200, 202) or not (answer or {}).get("ok", True):
        return (code if code not in (200, 202) else 409), {"error": (answer or {}).get("error") or "the member did not start it"}
    with _lock:
        job = _new(host_name, model, via, publish, True)
        job.update(member=member, say=f"probing on {member or host_name}: the profile comes with its next ledger push")
    _send(job)
    return 200, {**view(job), "joined": False}


def take_remote(member: str, profile: dict) -> Optional[str]:
    """A member's profile onto the hub's job for that model; the hub's name for the host (None: no job asked)."""
    from halo_harness.providers.ollama import ollama_names_match
    with _lock:
        job = next((j for j in _jobs.values() if j.get("remote") and not j["done"] and j.get("member") == member
                    and ollama_names_match(j["model"], profile.get("model"))), None)
    if job is None:
        return None
    finish(job, {**profile, "ok": True, "host": job["host"]})
    return job["host"]


def reset() -> None:
    with _lock:
        _jobs.clear()
