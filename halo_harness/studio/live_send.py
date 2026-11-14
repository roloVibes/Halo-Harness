"""halo_harness.studio.live_send -- a session command sent the way the Live routes send it (Halo 3.0.5.0 R4;
3.1.0.0 R2): through this harness's control socket (studio/live_agents_api.py).
"""

from __future__ import annotations

from halo_harness.studio.live_watch_sources import is_local


def session_cmd(server, home, hid: str, sid: str, cmd: str, fields: dict, wait_s: float = 5.0):
    """`(status, body)` of one session command on this harness (404 for another one)."""
    if not is_local(server, hid):
        return 404, {"error": f"{hid} is not this harness: Studio drives this machine's sessions"}
    from halo_harness.studio import live_agents_api
    status, result = live_agents_api.forward(sid, cmd, {**live_agents_api.caller(), **fields})
    return (200, {"ok": True, "result": result}) if status == 200 else (status, result)
