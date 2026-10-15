"""halo_harness.fleet.hub_mission -- the hub port's mission routes (Halo
3.0.6.0 "Fleet Missions" round R7), called from fleet/hub_http.py:

    POST /fleet/v1/mission_files   a member's signed list | get | put on a mission folder (fleet/mission_files.py);
                                   the body may be as large as fleet.mission.max_file_mb allows (base64)
    POST /fleet/v1/local/mission   loopback + the hub's admin token: `{op, ...}` for `halo fleet mission` when
                                   the hub runs in a `halo fleet serve` process (fleet/mission_api.py `admin`)
"""

from __future__ import annotations

from halo_harness.fleet import mission as M
from halo_harness.fleet import protocol

OVERHEAD = 65_536


def _body(handler, limit: int) -> bytes:
    n = int(handler.headers.get("Content-Length") or 0)
    if n > limit:
        raise ValueError(f"body too large ({n} bytes; this route takes {limit})")
    return handler.rfile.read(n) if n > 0 else b""


def serve(handler, route: str):
    hub = handler.hub
    if route == "local/mission":
        if not handler._admin():
            return None
        try:
            body = protocol.decode(_body(handler, 4_000_000))
        except ValueError as e:
            return handler._json(400, {"error": str(e)})
        from halo_harness.fleet.mission_api import admin
        status, out = admin(hub.home, hub, body)
        return handler._json(status, out)
    limit = int(M.max_file_bytes(hub.home) * 4 / 3) + OVERHEAD
    try:
        raw = _body(handler, limit)
    except ValueError as e:
        handler.close_connection = True
        return handler._json(413, {"error": str(e)})
    hid = handler._signed(raw)
    if not hid:
        return None
    try:
        body = protocol.decode(raw)
    except ValueError as e:
        return handler._json(400, {"error": f"bad request: {e}"})
    from halo_harness.fleet.mission_files import serve as files
    status, out = files(hub.home, hid, body)
    return handler._json(status, protocol.doc(**out) if status == 200 else out)
