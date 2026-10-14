"""halo_harness.studio.fleet_hub_api -- Studio's fleet routes (Halo 3.0.5.0
"Fleet" round R2), the same loopback + token guard as every Studio route.

    GET  fleet                       the hub's merged view (fleet/hub_state.py): every harness (this one
                                     first, `local: true`), its sessions and agent trees, and `hub`
    GET  fleet/commands/<cid>        one command's state: sent | asked | done | refused | error
    POST fleet/hub {action: start | stop, port?, bind?, name?, tls?}   the hub inside Studio's process
    POST fleet/<harness>/<sid>/command {cmd: steer | interrupt | shutdown | pause | resume | answer, text?,
                                        reason?, agent_id?, wait_s?, ...answer fields}
    POST fleet/<harness>/<sid>/agents/<aid>/command {cmd: steer | stop | pause | resume | follow | tail,
                                                     text?, mode?, reason?, on?, n?, wait_s?}

A command for this harness takes the direct path (studio/sessions_api.py,
studio/fleet_api.py); one for a member goes through the hub to that
member's relay and answers 200 (done), 202 (`asked`: the owner's card is
open; the outcome comes as a `fleet` frame and on `fleet/commands/<cid>`),
403 (refused, with the member's reason), 404, 409 (no hub here, or the
member is not connected), 502 or 504; a `halo fleet serve` running in
another process is reached over its loopback admin route. Studio sends
`by` = `fleet.name`.
Without a hub in this process the view is this harness alone (or the view
of a `halo fleet serve` running in another process).
"""

from __future__ import annotations

import re

from halo_harness.studio.sessions_api import ANSWER_FIELDS

SESSION_CMDS = ("steer", "interrupt", "shutdown", "pause", "resume", "answer")
AGENT_CMDS = {"steer": "agent_steer", "stop": "agent_stop", "pause": "pause", "resume": "resume",
              "follow": "agent_follow", "tail": "agent_tail"}


def _hub(req):
    return getattr(req.server, "fleet_hub", None)


def attach(server, hub) -> None:
    """Studio's hub: its member frames go to the live feed (studio/events.py)."""
    server.fleet_hub = hub

    def sink(frame: dict) -> None:
        bridge = getattr(server, "events", None)
        if bridge is not None:
            bridge.publish(frame)
    hub.state.sinks.append(sink)


def start_hub(server, *, home, port=None, bind="0.0.0.0", name=None, tls_on=None, local_view=None):
    from halo_harness.fleet.hub import HubServer
    hub = HubServer(home, port=port, bind=bind, name=name, tls_on=tls_on, local_view=local_view).start()
    attach(server, hub)
    return hub


def start_for_flag(server, state_dir) -> str:
    """`halo studio --fleet`: start the hub in Studio's process; the line to print."""
    from halo_harness.fleet import tls
    from halo_harness.fleet.hub import FleetOffline
    try:
        hub = start_hub(server, home=state_dir)
    except (FleetOffline, OSError, RuntimeError) as e:
        return f"Fleet hub: not started ({e})."
    how = f"TLS, fingerprint {tls.short(hub.fingerprint)}" if hub.fingerprint else "HMAC-signed HTTP, no TLS"
    return f"Fleet hub at {hub.url()} ({how}); `halo fleet pair` makes a code for another harness."


def _info(hub) -> dict:
    return {"serving": True, "name": hub.name, "url": hub.url(), "port": hub.port, "bind": hub.bind,
            "tls": bool(hub.fingerprint), "fingerprint": hub.fingerprint}


def get_fleet(req):
    hub = _hub(req)
    if hub is not None:
        return 200, hub.state.view()
    from halo_harness.fleet.hub import running_view
    other = running_view(req.state_dir)
    if other:
        return 200, other
    from halo_harness.fleet.local_view import snapshot
    return 200, {"harnesses": [snapshot()], "hub": {"serving": False, "name": None, "members": 0, "online": 0,
                                                     "pair_code_active": False}}


def get_command(req):
    hub = _hub(req)
    got = hub.state.commands.get(req.params["cid"]) if hub is not None else None
    return (200, got) if got else (404, {"error": f"no command {req.params['cid']!r} on this hub"})


def post_hub(req):
    body = req.body if isinstance(req.body, dict) else {}
    action, hub = str(body.get("action") or "start"), _hub(req)
    if action == "stop":
        if hub is not None:
            hub.stop()
            req.server.fleet_hub = None
        return 200, {"ok": True, "serving": False}
    if action != "start":
        return 422, {"error": f"action is start or stop, got {action!r}", "problems": []}
    if hub is not None:
        return 200, {"ok": True, "already": True, **_info(hub)}
    from halo_harness.fleet.hub import FleetOffline
    port = body.get("port")
    try:
        hub = start_hub(req.server, home=req.state_dir, port=int(port) if port not in (None, "") else None,
                        bind=str(body.get("bind") or "0.0.0.0"), name=body.get("name") or None,
                        tls_on=body.get("tls") if isinstance(body.get("tls"), bool) else None)
    except FleetOffline as e:
        return 409, {"error": str(e)}
    except (OSError, ValueError, RuntimeError) as e:
        return 409, {"error": f"the hub did not start: {e}"}
    return 200, {"ok": True, **_info(hub)}


def _local(req, hid: str) -> bool:
    hub = _hub(req)
    if hid == "local":
        return True
    if hub is not None:
        return hid == hub.state.identity.get("id")
    from halo_harness.fleet.identity import harness
    return hid == harness()["id"]


def _send(req, hid: str, sid: str, cmd: str, fields: dict):
    """Through Studio's own hub, else through a `halo fleet serve` running on this machine."""
    try:
        wait_s = float(req.body.get("wait_s") or 5.0)
    except (TypeError, ValueError):
        wait_s = 5.0
    hub = _hub(req)
    if hub is None:
        from halo_harness.fleet.hub import running_call
        got = running_call(req.state_dir, "POST", "local/command", {"harness": hid, "session_id": sid, "cmd": cmd,
                                                                    "fields": fields, "wait_s": wait_s},
                           timeout=wait_s + 5.0)
        return got if got else (409, {"error": "no fleet hub runs here (`halo studio --fleet`, or `halo fleet serve`)"})
    from halo_harness.fleet.identity import fleet_name
    return hub.state.commands.send(hid, sid, cmd, fields, by=fleet_name(hub.home), wait_s=wait_s)


def post_session_command(req):
    hid, sid = req.params["hid"], req.params["sid"]
    body = req.body if isinstance(req.body, dict) else {}
    if _local(req, hid):
        from halo_harness.studio.sessions_api import post_command
        req.params = {"sid": sid}
        return post_command(req)
    cmd = str(body.get("cmd") or "")
    if cmd not in SESSION_CMDS:
        return 422, {"error": f"cmd is one of {', '.join(SESSION_CMDS)}, got {cmd!r}", "problems": []}
    if cmd == "answer":
        fields = {k: body[k] for k in ANSWER_FIELDS if k in body}
    elif cmd == "steer":
        fields = {"text": str(body.get("text") or "").strip()}
        if not fields["text"]:
            return 422, {"error": "a steer needs text", "problems": []}
    else:
        fields = {k: str(body[k]) for k in ("reason", "agent_id") if body.get(k)}
    return _send(req, hid, sid, cmd, fields)


def post_agent_command(req):
    hid, sid, aid = req.params["hid"], req.params["sid"], req.params["aid"]
    body = req.body if isinstance(req.body, dict) else {}
    if _local(req, hid):
        from halo_harness.studio.fleet_api import post_agent_command as local_agent
        req.params = {"sid": sid, "aid": aid}
        return local_agent(req)
    cmd = str(body.get("cmd") or "")
    if cmd not in AGENT_CMDS:
        return 422, {"error": f"cmd is one of {', '.join(AGENT_CMDS)}, got {cmd!r}", "problems": []}
    fields = {"agent_id": aid}
    if cmd == "steer":
        text, mode = str(body.get("text") or "").strip(), str(body.get("mode") or "nudge")
        if not text or mode not in ("nudge", "redirect"):
            return 422, {"error": "a steer needs text and mode nudge or redirect", "problems": []}
        fields.update(text=text, mode=mode)
    elif cmd == "stop":
        fields["reason"] = str(body.get("reason") or "")
    elif cmd == "follow":
        fields["on"] = body.get("on", True) is not False
    elif cmd == "tail":
        fields["n"] = int(body.get("n") or 100) if str(body.get("n") or "100").isdigit() else 100
    return _send(req, hid, sid, AGENT_CMDS[cmd], fields)


_ID = r"[A-Za-z0-9_.:-]+"
ROUTES = [("GET", r"^fleet$", get_fleet),
          ("GET", rf"^fleet/commands/(?P<cid>{_ID})$", get_command),
          ("POST", r"^fleet/hub$", post_hub),
          ("POST", rf"^fleet/(?P<hid>{_ID})/(?P<sid>{_ID})/command$", post_session_command),
          ("POST", rf"^fleet/(?P<hid>{_ID})/(?P<sid>{_ID})/agents/(?P<aid>{_ID})/command$", post_agent_command)]


def dispatch_fleet(req):
    for method, pattern, fn in ROUTES:
        m = re.match(pattern, req.path)
        if m and method == req.method:
            req.params = dict(m.groupdict())
            return fn(req)
    if any(re.match(p, req.path) for _, p, _ in ROUTES):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
