"""halo_harness.studio.fleet_send -- a session command sent the way the Fleet
routes send it (Halo 3.0.5.0 "Fleet" round R4; 3.1.0.0 R2 cut it out of
fleet_watch_io.py): this harness's through its control socket
(studio/fleet_api.py), a member's through the hub (in this process, or a
`halo fleet serve` reached over its loopback admin route).
"""

from __future__ import annotations

from halo_harness.studio.fleet_watch_sources import by, is_local


def session_cmd(server, home, hid: str, sid: str, cmd: str, fields: dict, wait_s: float = 5.0):
    """`(status, body)` of one session command, this harness's or a member's."""
    if is_local(server, hid):
        from halo_harness.studio import fleet_api
        status, result = fleet_api.forward(sid, cmd, {**fleet_api.caller(), **fields})
        return (200, {"ok": True, "result": result}) if status == 200 else (status, result)
    return member_cmd(server, home, hid, sid, cmd, fields, wait_s)


def member_cmd(server, home, hid: str, sid: str, cmd: str, fields: dict, wait_s: float = 5.0):
    hub = getattr(server, "fleet_hub", None)
    if hub is None:
        from halo_harness.fleet.hub import running_call
        got = running_call(home, "POST", "local/command", {"harness": hid, "session_id": sid, "cmd": cmd,
                                                           "fields": fields, "wait_s": wait_s}, timeout=wait_s + 5.0)
        return got if got else (409, {"error": "no fleet hub runs here (`halo studio --fleet`, or `halo fleet serve`)"})
    return hub.state.commands.send(hid, sid, cmd, fields, by=by(hub.home), wait_s=wait_s)
