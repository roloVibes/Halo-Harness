"""halo_harness.studio.fleet_view_api -- Studio's `fleet/*` routes, the core's half (Halo 3.4.0.0 C: the fleet left the
core for the shipped `fleet` pack; before, studio/fleet_hub_api.py answered all of them).

Session, Agents -> Live, the attention chip and the replay read this machine's sessions through these routes, so they
answer with the pack off:

    GET  fleet                                      this harness alone (peers/local_view.py's snapshot), with
                                                    `fleet_pack`: whether the pack runs here
    POST fleet/<harness>/<sid>/command              a command to one of this harness's sessions
    POST fleet/<harness>/<sid>/agents/<aid>/command one of its agents (studio/fleet_api.py)
    GET  fleet/history                              past runs by role or bio (studio/fleet_api.py)
    fleet/attention[/answer], fleet/costs, fleet/caps, fleet/conflicts      studio/fleet_panels_api.py
    fleet/<h>/<sid>/agents/<aid>/handoff                                    studio/fleet_handoff_api.py
    fleet/<h>/<sid>/recording, fleet/recordings/<name>, fleet/replay        studio/fleet_recording_api.py

When the fleet pack runs here, its server/fleet_hub_api.py answers every `fleet/*` route instead (the hub's merged
view, the members, pairing, health, the digest, capabilities, missions, recall across the fleet), the core's among
them. With the pack off any other `fleet/*` route is 404 with the line that says how to turn the pack on, and a
command for another harness is 409 with it.
"""

from __future__ import annotations

import re


def _pack(cwd=None, state_dir=None):
    from halo_harness.packs import fleet_door
    return fleet_door.module("server/fleet_hub_api.py", cwd=cwd, state_dir=state_dir)


def _line() -> str:
    from halo_harness.packs import fleet_door
    return fleet_door.line()


def view_for(server, state_dir) -> dict:
    """The fleet as Studio sees it: the pack's (its hub's merged view) when it runs here, else this harness alone."""
    pack = _pack(getattr(server, "cwd", None), state_dir)
    if pack is not None:
        return pack.view_for(server, state_dir)
    from halo_harness.peers.local_view import snapshot
    return {"harnesses": [snapshot()], "hub": {"serving": False, "name": None, "members": 0, "online": 0,
                                               "pair_code_active": False}}


def get_fleet(req):
    """The view, and `fleet_pack`: whether the pack runs here (Studio shows its Fleet doors only then)."""
    pack = _pack(req.cwd, req.state_dir)
    view = pack.view_for(req.server, req.state_dir) if pack is not None else view_for(req.server, req.state_dir)
    return 200, {**view, "fleet_pack": pack is not None}


def _local(hid: str) -> bool:
    from halo_harness.peers.identity import harness
    return hid == "local" or hid == harness()["id"]


def post_session_command(req):
    pack = _pack(req.cwd, req.state_dir)
    if pack is not None:
        return pack.post_session_command(req)
    if not _local(req.params["hid"]):
        return 409, {"error": f"{req.params['hid']} is another harness: {_line()}"}
    from halo_harness.studio.sessions_api import post_command
    req.params = {"sid": req.params["sid"]}
    return post_command(req)


def post_agent_command(req):
    pack = _pack(req.cwd, req.state_dir)
    if pack is not None:
        return pack.post_agent_command(req)
    if not _local(req.params["hid"]):
        return 409, {"error": f"{req.params['hid']} is another harness: {_line()}"}
    from halo_harness.studio.fleet_api import post_agent_command as local_agent
    req.params = {"sid": req.params["sid"], "aid": req.params["aid"]}
    return local_agent(req)


def _routes() -> list:
    from halo_harness.studio.fleet_api import get_history
    from halo_harness.studio.fleet_handoff_api import ROUTES as handoff
    from halo_harness.studio.fleet_panels_api import ROUTES as panels
    from halo_harness.studio.fleet_recording_api import ROUTES as recording
    return ([("GET", r"^fleet$", get_fleet),
             ("POST", rf"^fleet/(?P<hid>{_ID})/(?P<sid>{_ID})/command$", post_session_command),
             ("POST", rf"^fleet/(?P<hid>{_ID})/(?P<sid>{_ID})/agents/(?P<aid>{_ID})/command$", post_agent_command),
             ("GET", r"^fleet/history$", get_history)] + panels + handoff + recording)


_ID = r"[A-Za-z0-9_.:-]+"


def dispatch_fleet(req):
    if req.path == "fleet" and req.method == "GET":
        return get_fleet(req)
    pack = _pack(req.cwd, req.state_dir)
    if pack is not None:
        return pack.dispatch_fleet(req)
    routes = _routes()
    for method, pattern, fn in routes:
        m = re.match(pattern, req.path)
        if m and method == req.method:
            req.params = dict(m.groupdict())
            return fn(req)
    if any(re.match(p, req.path) for _, p, _ in routes):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path} ({_line()})"}
