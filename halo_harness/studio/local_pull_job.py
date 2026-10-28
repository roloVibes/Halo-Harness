"""halo_harness.studio.local_pull_job -- Halo 3.3.5.0 R3: Local's pull jobs
(the routes are studio/local_control_api.py; the Setup check job's pattern:
studio/setup_check_job.py). One job per host + name: a second request for the
same name while it runs joins it. A job on a host this machine serves is a
daemon thread calling providers/ollama_control.pull; a job on a host a fleet
member serves is that member's own job (fleet/control_models.py starts it
there), its frames relayed back with the member's ledger push
(fleet/control_pulls.py -> `take_remote`). Either way the server does the
work, so a pull outlives the page that started it. Every change publishes

    {session_id: "local", event: "pull", ts, data: {job, host, name, status, digest, total, completed, percent,
     speed, eta, done, error, ok, cancelled, say, via, started}}

(at most four a second while bytes move; every status change and the end at
once). `current()` lists the jobs running and the last finished ones for a
page that opens later; after a pull succeeds the catalog caches are dropped
(studio/local_catalog.reset, studio/ollama_hosts_view.reset_cache, the
provider's own), so the Library row says "installed on <host>" and the
Models row appears on the next read. `<state>/ollama/pulls.json` keeps the
same views for the member's push.
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Callable, Optional

KEEP_DONE = 20
FRAME_EVERY_S = 0.25
SPEED_WINDOW_S = 5.0
FILE = "pulls.json"
_lock = threading.Lock()
_jobs: dict = {}  # id -> job
_seq = [0]


def _key(host: str, name: str) -> str:
    from halo_harness.providers.ollama import normalize_ollama_model_name
    return f"{host.lower()}|{normalize_ollama_model_name(name) or name}"


def view(job: dict) -> dict:
    keys = ("job", "host", "name", "status", "digest", "total", "completed", "percent", "speed", "eta", "done", "error",
            "ok", "cancelled", "say", "via", "started", "remote")
    return {k: job.get(k) for k in keys}


def current() -> dict:
    with _lock:
        jobs = sorted(_jobs.values(), key=lambda j: -j["started"])
        return {"jobs": [view(j) for j in jobs], "running": sum(1 for j in jobs if not j["done"])}


def get(job_id: str) -> Optional[dict]:
    with _lock:
        j = _jobs.get(job_id)
        return view(j) if j else None


def _find(host: str, name: str) -> Optional[dict]:
    k = _key(host, name)
    return next((j for j in _jobs.values() if not j["done"] and j["key"] == k), None)


def _new(host: str, name: str, via: str, publish, state_dir, remote: bool) -> dict:
    _seq[0] += 1
    jid = f"pull-{time.strftime('%H%M%S')}-{_seq[0]}"
    job = {"job": jid, "key": _key(host, name), "host": host, "name": name, "status": "starting", "digest": None,
           "total": None, "completed": None, "percent": None, "speed": None, "eta": None, "done": False, "error": None,
           "ok": False, "cancelled": False, "say": f"pulling {name} on {host}", "via": via, "started": round(time.time(), 3),
           "remote": remote, "layers": {}, "samples": [], "sent": 0.0, "cancel": threading.Event(), "publish": publish,
           "state_dir": state_dir}
    done = [j for j in _jobs.values() if j["done"]]
    for old in sorted(done, key=lambda j: j["started"])[:max(0, len(done) - KEEP_DONE + 1)]:
        _jobs.pop(old["job"], None)
    _jobs[jid] = job
    return job


def _measure(job: dict, obj: dict, now: float) -> None:
    if obj.get("status"):
        job["status"] = obj["status"]
    d = obj.get("digest")
    if d and isinstance(obj.get("total"), int):
        job["layers"][d] = (obj["total"], obj.get("completed") or 0)
        job["digest"] = d
    if job["layers"]:
        total = sum(t for t, _c in job["layers"].values())
        done = sum(min(c, t) for t, c in job["layers"].values())
        job.update(total=total, completed=done, percent=round(100.0 * done / total, 1) if total else None)
        job["samples"] = [s for s in job["samples"] if now - s[0] <= SPEED_WINDOW_S] + [(now, done)]
        t0, c0 = job["samples"][0]
        speed = (done - c0) / (now - t0) if now - t0 > 0.2 else job.get("speed")
        job["speed"] = round(speed) if speed else speed
        job["eta"] = round((total - done) / speed) if speed and total >= done else None


def _send(job: dict, force: bool = False) -> None:
    now = time.monotonic()
    if not force and now - job["sent"] < FRAME_EVERY_S:
        return
    job["sent"] = now
    data = view(job)
    if job.get("publish") is not None:
        try:
            job["publish"]({"session_id": "local", "event": "pull", "ts": time.time(), "data": data})
        except Exception:
            pass
    if job.get("state_dir") is not None and not job.get("remote"):
        _write(job["state_dir"])


def _write(state_dir) -> None:
    from halo_harness.ollama_steward.ledger import ledger_dir
    path = ledger_dir(state_dir) / FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"at": time.time(), **current()}, default=str), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass


def read_file(state_dir) -> list:
    from halo_harness.ollama_steward.ledger import ledger_dir
    try:
        return list(json.loads((ledger_dir(state_dir) / FILE).read_text(encoding="utf-8")).get("jobs") or [])
    except (OSError, ValueError, AttributeError):
        return []


def after_change() -> None:
    """The caches every model list reads, dropped: the next read sees what the server has now."""
    from halo_harness.providers.ollama import reset_catalog_cache
    from halo_harness.studio import local_catalog, ollama_hosts_view
    reset_catalog_cache()
    local_catalog.reset()
    ollama_hosts_view.reset_cache()


def _finish(job: dict, got: dict) -> None:
    with _lock:
        job.update(done=True, ok=bool(got.get("ok")), cancelled=bool(got.get("cancelled")), error=got.get("error"),
                   say=got.get("say") or job["say"], eta=None if got.get("ok") else job["eta"])
        if job["ok"]:
            job.update(percent=100.0, status="success", eta=0)
    if job["ok"]:
        after_change()
    _send(job, force=True)


def start(host, name: str, publish: Optional[Callable] = None, *, state_dir=None, pull=None) -> dict:
    """Pull `name` onto `host` (this machine serves it); the job's view, `joined` when it was running already."""
    with _lock:
        hit = _find(host.name, name)
        if hit is not None:
            return {**view(hit), "joined": True}
        job = _new(host.name, name, "this machine", publish, state_dir, False)
    from halo_harness.providers.ollama_control import pull as do_pull
    fn = pull or do_pull

    def on(obj: dict) -> None:
        with _lock:
            before = job["status"]
            _measure(job, obj, time.monotonic())
        _send(job, force=obj.get("status") != before and not obj.get("total"))

    def body() -> None:
        try:
            got = fn(host, name, on_status=on, cancel=job["cancel"])
        except Exception as e:
            got = {"ok": False, "error": type(e).__name__, "say": f"the pull of {name} stopped: {e}"}
        _finish(job, got)

    threading.Thread(target=body, name=f"halo-local-{job['job']}", daemon=True).start()
    _send(job, force=True)
    return {**view(job), "joined": False}


def start_remote(host_name: str, name: str, send: Callable[[dict], "tuple[int, dict]"], via: str,
                 publish: Optional[Callable] = None, *, member: str = "", member_host: str = "") -> "tuple[int, dict]":
    """The member's own job started through `send({cancel?})`; the hub's job follows its relayed frames."""
    with _lock:
        hit = _find(host_name, name)
        if hit is not None:
            return 200, {**view(hit), "joined": True}
    code, answer = send({})  # 202: the member's owner is asked first (fleet.allow_control: ask)
    if code not in (200, 202) or not (answer or {}).get("ok", True):
        return (code if code not in (200, 202) else 409), {"error": (answer or {}).get("error") or "the member did not start it"}
    with _lock:
        job = _new(host_name, name, via, publish, None, True)
        job.update(sender=send, member=member, member_host=member_host or host_name)
    _send(job, force=True)
    return 200, {**view(job), "joined": False}


def take_remote(member: str, data: dict) -> bool:
    """One of the member's job views (its ledger push: its own host name) onto the hub's job for it."""
    name, mhost = str(data.get("name") or ""), str(data.get("host") or "")
    with _lock:
        job = next((j for j in _jobs.values() if j.get("remote") and not j["done"] and j.get("member") == member
                    and j.get("member_host") == mhost and j["key"].split("|", 1)[1] == _key(mhost, name).split("|", 1)[1]), None)
        if job is None:
            return False
        for k in ("status", "digest", "total", "completed", "percent", "speed", "eta", "error", "say"):
            if data.get(k) is not None:
                job[k] = data[k]
        finished = bool(data.get("done"))
    if finished:
        _finish(job, data)
    else:
        _send(job, force=True)
    return True


def cancel(job_id: str) -> Optional[dict]:
    """Ask the job to stop; its view (None: no such job)."""
    with _lock:
        job = _jobs.get(job_id)
    if job is None:
        return None
    if not job["done"]:
        if job.get("remote") and job.get("sender"):
            job["sender"]({"cancel": True})
        else:
            job["cancel"].set()
    return view(job)


def reset() -> None:
    """Test seam: every job forgotten (running ones asked to stop)."""
    with _lock:
        for j in _jobs.values():
            j["cancel"].set()
        _jobs.clear()
