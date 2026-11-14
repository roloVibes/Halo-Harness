"""halo_harness.studio.live_api -- Studio's `live/*` routes: this machine's sessions as Session, Agents -> Live, the
attention chip and the replay read them (Halo 3.0.5.0 R2; 3.5.0.0: named `live/`, this machine only).

    GET  live                                       this harness and its live sessions (peers/local_view.py's snapshot)
    POST live/<harness>/<sid>/command               a command to one of this harness's sessions (`local` or its id)
    POST live/<harness>/<sid>/agents/<aid>/command  one of its agents (studio/live_agents_api.py)
    GET  live/history                               past runs by role or bio (studio/live_agents_api.py)
    live/attention[/answer], live/costs, live/caps, live/conflicts      studio/live_panels_api.py
    live/<h>/<sid>/agents/<aid>/handoff                                 studio/live_handoff_api.py
    live/<h>/<sid>/recording, live/recordings/<name>, live/replay       studio/live_recording_api.py

A `<harness>` other than this one is 404: Halo drives this machine's sessions (another machine's models are Local's).
"""

from __future__ import annotations

import re


def view_for(server, state_dir) -> dict:
    """This harness and its sessions, as Studio's watcher and Session read them."""
    from halo_harness.peers.local_view import snapshot
    return {"harnesses": [snapshot()]}


def get_live(req):
    return 200, view_for(req.server, req.state_dir)


def _local(hid: str) -> bool:
    from halo_harness.peers.identity import harness
    return hid == "local" or hid == harness()["id"]


def _other(hid: str):
    return 404, {"error": f"{hid} is not this harness: Studio drives this machine's sessions"}


def post_session_command(req):
    if not _local(req.params["hid"]):
        return _other(req.params["hid"])
    from halo_harness.studio.sessions_api import post_command
    req.params = {"sid": req.params["sid"]}
    return post_command(req)


def post_agent_command(req):
    if not _local(req.params["hid"]):
        return _other(req.params["hid"])
    from halo_harness.studio.live_agents_api import post_agent_command as local_agent
    req.params = {"sid": req.params["sid"], "aid": req.params["aid"]}
    return local_agent(req)


_ID = r"[A-Za-z0-9_.:-]+"
ROUTES = [("GET", r"^live$", get_live),
          ("POST", rf"^live/(?P<hid>{_ID})/(?P<sid>{_ID})/command$", post_session_command),
          ("POST", rf"^live/(?P<hid>{_ID})/(?P<sid>{_ID})/agents/(?P<aid>{_ID})/command$", post_agent_command)]


def _routes() -> list:
    from halo_harness.studio.live_agents_api import get_history
    from halo_harness.studio.live_handoff_api import ROUTES as handoff
    from halo_harness.studio.live_panels_api import ROUTES as panels
    from halo_harness.studio.live_recording_api import ROUTES as recording
    return ROUTES + [("GET", r"^live/history$", get_history)] + panels + handoff + recording


def dispatch_live(req):
    routes = _routes()
    for method, pattern, fn in routes:
        m = re.match(pattern, req.path)
        if m and method == req.method:
            req.params = dict(m.groupdict())
            return fn(req)
    if any(re.match(p, req.path) for _, p, _ in routes):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
