"""halo_harness.studio.fleet_api -- Studio's agent-level routes on a live
session (Halo 3.0.5.0 "Fleet" round R1), mounted under `sessions/` by
studio/sessions_api.py; the same guard as every Studio route.

    GET  sessions/<sid>/agents                       -> {agents: [row, ...]}
    GET  sessions/<sid>/agents/<aid>/tail?n=&kinds=  -> {agent_id, events: [entry, ...]}
    POST sessions/<sid>/agents/<aid>/command {cmd: steer|stop|pause|resume|follow,
                                              text?, mode?, reason?, on?}  -> {ok, result}

Rows, entries and command semantics are the control socket's
(remote/agent_control.py). Studio sends `by` = `fleet.name` and `via` =
"Studio". 404: no such live session; 422: a bad command or parameter; 502:
the session refused (its own error) or could not be reached.
"""

from __future__ import annotations

COMMAND_TIMEOUT_S = 5.0
AGENT_COMMANDS = {"steer": "agent_steer", "stop": "agent_stop", "pause": "pause", "resume": "resume",
                  "follow": "agent_follow"}


def caller() -> dict:
    from halo_harness.remote.fleet_identity import fleet_name
    return {"by": fleet_name(), "via": "Studio"}


def forward(sid: str, cmd: str, fields: dict):
    """`(200, result)` or `(404 | 502, {error})`: one request on `sid`'s socket."""
    from halo_harness.remote import registry
    from halo_harness.remote.client import ControlClient, default_token_for
    entry = next((e for e in registry.list_live() if isinstance(e, dict) and e.get("session_id") == sid), None)
    if entry is None:
        return 404, {"error": f"no live session {sid!r}"}
    client = None
    try:
        client = ControlClient(str(entry.get("endpoint") or ""), default_token_for(entry), timeout=COMMAND_TIMEOUT_S)
        resp = client.call(cmd, **fields)
    except Exception as e:  # refused, closed, timed out
        return 502, {"error": f"session {sid}: {type(e).__name__}: {e}"}
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
    if not resp.get("ok"):
        return 502, {"error": str(resp.get("error") or "the session refused the command")}
    return 200, resp.get("result") if isinstance(resp.get("result"), dict) else {}


def get_agents(req):
    return forward(req.params["sid"], "agents", {})


def get_tail(req):
    raw = str(req.query.get("n") or "100")
    if not raw.isdigit() or not 1 <= int(raw) <= 500:
        return 422, {"error": f"n is a whole number from 1 to 500, got {raw!r}", "problems": []}
    fields = {"agent_id": req.params["aid"], "n": int(raw)}
    kinds = [k.strip() for k in str(req.query.get("kinds") or "").split(",") if k.strip()]
    if kinds:
        fields["kinds"] = kinds
    return forward(req.params["sid"], "agent_tail", fields)


def post_agent_command(req):
    body = req.body if isinstance(req.body, dict) else {}
    cmd = str(body.get("cmd") or "")
    if cmd not in AGENT_COMMANDS:
        return 422, {"error": f"cmd is one of {', '.join(AGENT_COMMANDS)}, got {cmd!r}", "problems": []}
    fields = {"agent_id": req.params["aid"], **caller()}
    if cmd == "steer":
        text, mode = str(body.get("text") or "").strip(), str(body.get("mode") or "nudge")
        if not text:
            return 422, {"error": "a steer needs text", "problems": []}
        if mode not in ("nudge", "redirect"):
            return 422, {"error": f"mode is nudge or redirect, got {mode!r}", "problems": []}
        fields.update(text=text, mode=mode)
    elif cmd == "stop":
        fields["reason"] = str(body.get("reason") or "")
    elif cmd == "follow":
        fields["on"] = body.get("on", True) is not False
    status, result = forward(req.params["sid"], AGENT_COMMANDS[cmd], fields)
    return (200, {"ok": True, "result": result}) if status == 200 else (status, result)


ROUTES = [("GET", r"^sessions/(?P<sid>[A-Za-z0-9_.:-]+)/agents$", get_agents),
          ("GET", r"^sessions/(?P<sid>[A-Za-z0-9_.:-]+)/agents/(?P<aid>[A-Za-z0-9_.:-]+)/tail$", get_tail),
          ("POST", r"^sessions/(?P<sid>[A-Za-z0-9_.:-]+)/agents/(?P<aid>[A-Za-z0-9_.:-]+)/command$", post_agent_command)]
