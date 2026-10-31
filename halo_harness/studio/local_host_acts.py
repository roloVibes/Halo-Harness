"""halo_harness.studio.local_host_acts -- Studio acts on a host-served machine through its `halo host` (Halo 3.3.7.0 R2;
docs/STUDIO-local.md "Hosts").

    host_controls(url, name) -> {ok, via: "host", host, host_url, grants, cap, asks, manage, request, why} | None
        None when no paired host serves that url; ok when this peer holds `control` there (under the host machine's
        fleet.allow_control: `ask` queues each request for its owner first, `none` keeps it a monitor)
    send(ctl, act, fields) -> (status, answer)        fleet/hub_host_cmd.send through this peer's own pair key
    waiter(ctl, job_id, save_card_as=None) -> a runner for local_probe_job / local_bench_job.start: the host's job,
                                                     read through `GET job/<id>`, becomes this Studio's probe / bench
                                                     frames
    request(url, name, grant="control") -> (status, answer)   the Hosts card's "request control": a pending row there
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Callable, Optional

FOLLOW_S = 1.0
FOLLOW_MAX_S = 3 * 3600.0


def _client(url: str, name: str = ""):
    from halo_harness.ollama_steward.host_client import for_host
    return for_host(SimpleNamespace(url=url, name=name))


def _port(url: str) -> int:
    from halo_harness.ollama_steward.host_client import _addr_port
    return _addr_port(url)[1]


def host_controls(url: str, name: str) -> Optional[dict]:
    from halo_harness.host.grants import holds
    from halo_harness.ollama_steward.host_client import HostError, _usable
    hc = _client(url, name)
    if hc is None:
        return None
    base = {"ok": False, "via": "host", "host": hc.addr, "host_url": url, "grants": list(hc.entry.get("grants") or ["view"]),
            "cap": None, "asks": False, "manage": False, "request": False}
    if not _usable(hc):
        return {**base, "why": f"served by halo host at {hc.addr}: it did not answer a moment ago"}
    try:
        me = hc.me()
    except HostError as e:
        return {**base, "why": f"served by halo host at {hc.addr}: {e}"}
    grants, cap = list(me.get("grants") or ["view"]), me.get("cap")
    base.update(grants=grants, cap=cap, asks=bool(me.get("asks")), manage=holds(grants, "manage"),
                pending=[p for p in me.get("pending") or [] if p.get("state") == "pending"])
    if cap == "none":
        return {**base, "why": f"served by halo host at {hc.addr}: fleet.allow_control is none there, so it is strictly "
                               "a monitor (view only for every peer)"}
    if holds(grants, "control"):
        return {**base, "ok": True, "why": "", "via_line": f"halo host at {hc.addr}" + (
            " (its owner is asked first)" if me.get("asks") else "")}
    who = me.get("name") or "this peer"
    return {**base, "request": True, "why": f"served by halo host at {hc.addr}: {who} holds {', '.join(grants)} there; "
            f"Load, Unload, probe and bench through it need `control` (`halo host grant {who} control` on that machine, "
            "or Request control here)"}


def send(ctl: dict, act: str, fields: dict) -> "tuple[int, dict]":
    from halo_harness.fleet.hub_host_cmd import send as host_send
    url = str(ctl.get("host_url") or "")
    hc = _client(url)
    if hc is None:
        return 409, {"error": ctl.get("why") or "no paired halo host serves it now"}
    return host_send(hc, act, fields, port=_port(url))  # a missing grant comes back as the host's own 403 line


def wait(ctl: dict, job_id: str, on: Callable[[dict], None]) -> dict:
    """The host's job read through `GET job/<id>` until it ends -> its result; each step handed to `on`."""
    from halo_harness.ollama_steward.host_client import HostError
    hc = _client(str(ctl.get("host_url") or ""))
    if hc is None:
        return {"ok": False, "say": "the host's job could not be followed (no paired host serves it now)"}
    end, seen = time.monotonic() + FOLLOW_MAX_S, None
    while time.monotonic() < end:
        try:
            job = hc.get(f"job/{job_id}").get("job") or {}
        except HostError as e:
            return {"ok": False, "say": f"the host's job {job_id}: {e}"}
        if job.get("done"):
            return {**(job.get("result") or {}), "ok": bool(job.get("ok")), "say": job.get("say")}
        mark = (job.get("step"), job.get("say"))
        if mark != seen:
            seen = mark
            on(job)
        time.sleep(FOLLOW_S)
    return {"ok": False, "say": f"the host's job {job_id} was still running after {int(FOLLOW_MAX_S)} s"}


def waiter(ctl: dict, job_id: str, *, save_card_as: Optional[str] = None) -> Callable:
    """A runner for studio/local_probe_job.start / local_bench_job.start: the host already runs the job; this waits on
    it and hands each step on (a probe's `on_status`, a bench's `on_line`). A bench's speed card is kept here too,
    under this machine's name for the host (`save_card_as`), so its fit badge and Benchmarks read it."""
    def run(host, model, **kw):
        def on(job: dict) -> None:
            if kw.get("on_status"):
                kw["on_status"]({"step": job.get("step"), "of": job.get("of"), "say": job.get("say")})
            elif kw.get("on_line") and job.get("say"):
                kw["on_line"](str(job["say"]))
        got = wait(ctl, job_id, on)
        if got.get("ok") and save_card_as and got.get("windows") is not None:
            from halo_harness.providers.local_bench_runs import save
            save(kw.get("state_dir"), {**got, "host": save_card_as, "via": f"halo host at {ctl.get('host')}"})
        from halo_harness.ollama_steward.host_client import _CACHE
        for k in [k for k in _CACHE if isinstance(k, tuple) and k[1] == "profiles"]:
            _CACHE.pop(k, None)
        return got
    return run


def puller(ctl: dict, job_id: str) -> Callable:
    """A `pull` for studio/local_pull_job.start: the host already pulls; each of its job's steps becomes a status line
    here ({status, total, completed}), its end the pull's answer."""
    def run(host, name, on_status=None, cancel=None):
        def on(job: dict) -> None:
            if on_status is not None:
                on_status({"status": job.get("say") or "pulling", "total": job.get("of"), "completed": job.get("step")})
        return wait(ctl, job_id, on)
    return run


def request(url: str, name: str, grant: str = "control") -> "tuple[int, dict]":
    from halo_harness.ollama_steward.host_client import _CACHE, HostError
    hc = _client(url, name)
    if hc is None:
        return 404, {"error": f"no paired halo host serves {name or url}"}
    try:
        got = hc.request_grant(grant, "asked from the Hosts card")
    except HostError as e:
        return (e.status or 502), {"error": str(e)}
    _CACHE.pop((hc.url, "me"), None)
    return (202 if got.get("queued") else 200), {**got, "ok": True, "line": got.get("line")}
