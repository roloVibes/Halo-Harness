"""The fleet pack's health and digest routes (Halo 3.0.5.0 "Fleet" round R4 in studio/fleet_panels_api.py; the
pack's since 3.4.0.0 C), answered through server/fleet_hub_api.py's ROUTES:

    GET  fleet/health[?refresh=1]    {harnesses: [{id, name, local, online, cached, status, version, providers,
                                                   disk, sockets, studio, checked, note?}]}  60 s cache
    GET  fleet/digest?since=<2h | 45m | 1d | unix seconds or ms | ISO>   fleet/digest.py's digest (default 1d)

A member's health is its `status` and `doctor` answers through the hub (one
live session of it, read-only: `doctor` is in the protocol's READ_CMDS).
"""

from __future__ import annotations

import threading

from halo_harness.ext import core as _core
send = _core.module("studio.fleet_send")
sources = _core.module("studio.fleet_watch_sources")
MEMBER_WAIT_S, _watcher = (_core.get("studio.fleet_panels_api", n) for n in ("MEMBER_WAIT_S", "_watcher"))


def _member_health(req, h: dict, refresh: bool) -> dict:
    from ..fleet import health
    sids = [s.get("session_id") for s in h.get("sessions") or [] if s.get("session_id")]
    if not h.get("online") or not sids:
        return {"status": "unknown", "note": "offline" if not h.get("online") else "no live session to ask", "cached": False}

    def fetch() -> dict:
        got = {}
        for cmd in ("status", "doctor"):
            status, body = send.member_cmd(req.server, req.state_dir, str(h["id"]), sids[0], cmd, {}, MEMBER_WAIT_S)
            got[cmd] = (body or {}).get("result") if status == 200 else None
        out = health.member_subset(got["status"], got["doctor"])
        if got["doctor"] is None:
            out["note"] = "the member did not answer `doctor` (an older Halo, or the hub could not reach it)"
        return out
    value, hit = health.cached(f"member:{h['id']}", fetch, refresh)
    return {**value, "cached": hit}


def get_health(req):
    from ..fleet import health
    refresh = str(req.query.get("refresh") or "") in ("1", "true", "yes")
    view = sources.view(req.server, req.state_dir)
    rows: list = [None] * len(view.get("harnesses") or [])

    def one(i: int, h: dict) -> None:
        base = {k: h.get(k) for k in ("id", "name", "local", "online", "version", "host", "os")}
        if h.get("local"):
            value, hit = health.cached("local", health.subset, refresh)
            rows[i] = {**value, **base, "cached": hit}
        else:
            rows[i] = {**base, **_member_health(req, h, refresh), "id": h.get("id"), "name": h.get("name")}
    threads = [threading.Thread(target=one, args=(i, h), daemon=True, name="halo-fleet-health")
               for i, h in enumerate(view.get("harnesses") or [])]
    for t in threads:
        t.start()
    for t in threads:
        t.join(2 * MEMBER_WAIT_S + 4)
    return 200, {"harnesses": [r for r in rows if r is not None], "cache_s": health.CACHE_S}


def get_digest(req):
    from ..fleet import digest
    identity = _core.module("peers.identity")
    try:
        since = digest.parse_since(req.query.get("since") or "1d")
    except ValueError as e:
        return 422, {"error": str(e), "problems": []}
    w = _watcher(req)
    w.snapshot()
    live = [s.get("session_id") for h in w.view.get("harnesses") or [] if h.get("local") for s in h.get("sessions") or []]
    return 200, digest.compute(w.home, since, local_id=w.local_id, local_name=identity.fleet_name(w.home), live_ids=live)


ROUTES = [("GET", r"^fleet/health$", get_health),
          ("GET", r"^fleet/digest$", get_digest)]
