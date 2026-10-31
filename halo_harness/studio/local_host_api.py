"""halo_harness.studio.local_host_api -- Halo 3.3.7.0 R2: Local's routes for `halo host` grants (dispatched by
studio/local_api.dispatch_local; docs/STUDIO-local.md "Hosts").

    POST local/host/<name>/request-control       the Hosts card's "Request control": a pending row on the paired
                                                 host that serves <name> (its owner answers it there)
    GET  local/host-pending                      on the host machine: the requests queued for its owner under
                                                 fleet.allow_control: ask (host/grants.pending), the peers
    POST local/host-pending/<id>/allow | deny    the owner's answer (host/grants.answer); an allowed `grant` row
                                                 adds the grant, an allowed op runs once when the peer sends it again
    POST local/host/<name>/server-line {op, value?}   a stated action through the host (set_kv_cache_type,
                                                 set_flash_attn, restart_ollama): the exact line for that host's OS,
                                                 applied: false -- Halo never runs it
    GET  local/offline?session=<id>              a session's offline promise (agent/offline_promise.py): the
                                                 Session header's chip
"""

from __future__ import annotations

import re
import urllib.parse

_REQ = re.compile(r"^local/host/(?P<name>[^/]+)/request-control$")
_LINE = re.compile(r"^local/host/(?P<name>[^/]+)/server-line$")
STATED = {"set_kv_cache_type": ("control", "value"), "set_flash_attn": ("control", "on"), "restart_ollama": ("manage", "")}
_ANSWER = re.compile(r"^local/host-pending/(?P<id>[^/]+)/(?P<act>allow|deny)$")


def get_pending(req):
    from halo_harness.host import grants
    from halo_harness.host.state import read_info
    rows = grants.pending(req.state_dir)
    return 200, {"pending": rows, "cap": grants.cap(req.state_dir), "running": read_info(req.state_dir) is not None,
                 "peers": grants.peers(req.state_dir) if rows else []}


def post_answer(req, pid: str, allow: bool):
    from halo_harness.host import grants
    ok, line = grants.answer(req.state_dir, pid, allow)
    return (200, {"ok": True, "say": line}) if ok else (404, {"error": line})


def post_request(req, name: str):
    from halo_harness.providers.ollama import resolve_ollama_host
    from halo_harness.studio.local_host_acts import request
    host = resolve_ollama_host(name)
    if host is None:
        return 404, {"error": f"no host named {name!r} here"}
    code, out = request(host.url, host.name, "control")
    if code >= 400:
        return code, out
    from halo_harness.studio import ollama_hosts_view as V
    V.reset_cache()
    return 200, {**out, "say": out.get("line") or "asked"}


def post_line(req, name: str):
    from halo_harness.ollama_steward.host_client import HostError
    from halo_harness.providers.ollama import resolve_ollama_host
    from halo_harness.studio.local_host_acts import _client, _port
    body = req.body if isinstance(req.body, dict) else {}
    op = str(body.get("op") or "")
    if op not in STATED:
        return 422, {"error": f"server-line takes {{op: {' | '.join(STATED)}, value?}}"}
    host = resolve_ollama_host(name)
    hc = _client(host.url, host.name) if host is not None else None
    if hc is None:
        return 404, {"error": f"no paired halo host serves {name!r}"}
    grant, key = STATED[op]
    params = {key: body.get("value") if key == "value" else body.get("value") in (True, "on", "1", "true")} if key else {}
    served = hc.served_name(_port(host.url))
    if served:
        params["host"] = served
    try:
        got = hc.act(grant, op, params)
    except HostError as e:
        return (e.status or 502), {"error": str(e)}
    if got.get("queued"):
        return 202, {"ok": False, "say": got.get("line"), "pending": got.get("pending")}
    return 200, {**got, "say": got.get("line")}


def get_offline(req):
    """3.3.7.0 R2 (G15): GET local/offline?session=<id> -> the session's offline promise (agent/offline_promise.py)."""
    from halo_harness.agent.offline_promise import promise
    from halo_harness.safe_id import is_safe_session_id
    sid = str(req.query.get("session") or "").strip()
    if not sid or not is_safe_session_id(sid):
        return 422, {"error": "offline takes ?session=<id>"}
    return 200, promise(req.state_dir, sid)


def dispatch_host(req):
    """The answer for a route of this file, else None."""
    if req.path == "local/offline":
        return get_offline(req) if req.method == "GET" else (405, {"error": "method not allowed"})
    if req.path == "local/host-pending":
        return get_pending(req) if req.method == "GET" else (405, {"error": "method not allowed"})
    m = _ANSWER.match(req.path)
    if m:
        if req.method != "POST":
            return 405, {"error": "method not allowed"}
        return post_answer(req, urllib.parse.unquote(m.group("id")), m.group("act") == "allow")
    m = _LINE.match(req.path)
    if m:
        if req.method != "POST":
            return 405, {"error": "method not allowed"}
        return post_line(req, urllib.parse.unquote(m.group("name")))
    m = _REQ.match(req.path)
    if m:
        if req.method != "POST":
            return 405, {"error": "method not allowed"}
        return post_request(req, urllib.parse.unquote(m.group("name")))
    return None
