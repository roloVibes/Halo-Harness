"""halo_harness.studio.sessions_api -- the live sessions Studio can answer
(Halo 3.0.4.0 round R5). Same guard as every Studio route.

    GET  sessions                 [{session_id, title, cwd, mode, kind, started, pid, harness, project, parent,
                                    status, busy, pending, model, agents, status_age_s}]
    POST sessions/<sid>/command {cmd: answer|interrupt|steer|submit|shutdown|pause|resume, kind?, request_id?,
                                 action?, instruction?, text?, reason?, agent_id?, ...}
                                  -> {ok, result}; 404 for a session not in the registry, 502 with the socket's error
    sessions/<sid>/agents...      the agent tree, one agent's tail and its commands (studio/fleet_api.py, 3.0.5.0)

The rows come from `remote/registry.list_live()` (never an endpoint or a
token) plus each session's `status` over its control socket: every call
has a `STATUS_TIMEOUT_S` timeout, they run side by side on their own
threads, the request waits at most `STATUS_WAIT_S` for them and a session
that has not answered keeps its last cached status (`status_age_s` says how
old). A status is reused for `STATUS_TTL_S`; `agents` counts the sub-agents
running right now (3.0.5.0). `status` is `waiting` (a
permission, question, plan or approval card is open), `busy`, `idle` or
`unknown`. A command is forwarded as the control protocol's request
(`remote/protocol.py`): an `answer` with `kind: approval` resolves an org
position's approval card in a TUI session the way the phone bridge does.
"""

from __future__ import annotations

import re
import threading
import time

STATUS_TIMEOUT_S = 1.0
STATUS_WAIT_S = 1.5
STATUS_TTL_S = 2.0
COMMAND_TIMEOUT_S = 5.0
COMMANDS = ("answer", "interrupt", "steer", "submit", "shutdown", "pause", "resume")
FLEET_COMMANDS = ("shutdown", "pause", "resume")  # 3.0.5.0: sent with by = fleet.name, via = Studio
ANSWER_FIELDS = ("kind", "request_id", "action", "instruction", "scope", "message", "rule", "answer", "approved",
                 "feedback", "mode_after")
_cache: dict = {}
_lock = threading.Lock()


def _list_live() -> list:
    from halo_harness.remote import registry
    # a private session never registers; an entry marked private anyway is never shown
    return [r for r in registry.list_live() if isinstance(r, dict) and r.get("session_id") and not r.get("private")]


def _client(entry: dict, timeout: float):
    from halo_harness.remote.client import ControlClient, default_token_for
    return ControlClient(str(entry.get("endpoint") or ""), default_token_for(entry), timeout=timeout)


def _fetch(entry: dict) -> None:
    client = None
    try:
        client = _client(entry, STATUS_TIMEOUT_S)
        resp = client.call("status")
        data = resp.get("result") if resp.get("ok") and isinstance(resp.get("result"), dict) else None
    except Exception:
        data = None
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
    if data is not None:
        data = {k: v for k, v in data.items() if k not in ("token", "endpoint")}
        with _lock:
            _cache[entry["session_id"]] = (time.monotonic(), data)


def statuses(entries: list) -> dict:
    """{session_id: (age_s, status dict)} -- fresh calls for stale ones, at most STATUS_WAIT_S of waiting."""
    now = time.monotonic()
    with _lock:
        stale = [e for e in entries if now - _cache.get(e["session_id"], (-1e9, None))[0] >= STATUS_TTL_S]
    threads = [threading.Thread(target=_fetch, args=(e,), daemon=True, name="halo-studio-status") for e in stale]
    for t in threads:
        t.start()
    deadline = time.monotonic() + STATUS_WAIT_S
    for t in threads:
        t.join(max(0.0, deadline - time.monotonic()))
    now = time.monotonic()
    with _lock:
        return {e["session_id"]: (round(now - _cache[e["session_id"]][0], 2), _cache[e["session_id"]][1])
                for e in entries if e["session_id"] in _cache}


def _state(data) -> str:
    if not isinstance(data, dict):
        return "unknown"
    pending = data.get("pending") if isinstance(data.get("pending"), dict) else {}
    if any(pending.get(k) for k in ("permission", "question", "plan", "approval")):
        return "waiting"
    return "busy" if data.get("busy") else "idle"


def list_sessions(req):
    entries = _list_live()
    got = statuses(entries)
    rows = []
    for e in sorted(entries, key=lambda r: (r.get("started") or 0, r.get("session_id"))):
        age, data = got.get(e["session_id"], (None, None))
        from halo_harness.remote.registry import public_entry
        row = public_entry(e)
        row.update(status=_state(data), busy=bool((data or {}).get("busy")), pending=(data or {}).get("pending"),
                   model=(data or {}).get("model"), agents=(data or {}).get("agents"), status_age_s=age)
        rows.append(row)
    return 200, rows


def post_command(req):
    sid = req.params["sid"]
    cmd = str(req.body.get("cmd") or "")
    if cmd not in COMMANDS:
        return 422, {"error": f"cmd is one of {', '.join(COMMANDS)}, got {cmd!r}", "problems": []}
    if cmd in FLEET_COMMANDS:
        from halo_harness.studio import fleet_api
        fields = {**fleet_api.caller(), "reason": str(req.body.get("reason") or "")}
        if req.body.get("agent_id"):
            fields["agent_id"] = str(req.body["agent_id"])
        status, result = fleet_api.forward(sid, cmd, fields)
        with _lock:
            _cache.pop(sid, None)
        return (200, {"ok": True, "result": result}) if status == 200 else (status, result)
    entry = next((e for e in _list_live() if e.get("session_id") == sid), None)
    if entry is None:
        return 404, {"error": f"no live session {sid!r}"}
    fields = {}
    if cmd == "answer":
        fields = {k: req.body[k] for k in ANSWER_FIELDS if k in req.body}
    elif cmd in ("steer", "submit"):
        fields = {"text": str(req.body.get("text") or "")}
    client = None
    try:
        client = _client(entry, COMMAND_TIMEOUT_S)
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
    with _lock:
        _cache.pop(sid, None)  # the next list asks again
    return 200, {"ok": True, "result": resp.get("result")}


ROUTES = [("GET", r"^sessions$", list_sessions),
          ("POST", r"^sessions/(?P<sid>[A-Za-z0-9_.:-]+)/command$", post_command)]
from halo_harness.studio.fleet_api import ROUTES as _FLEET_ROUTES  # noqa: E402  (3.0.5.0: the agent routes)
ROUTES[len(ROUTES):] = _FLEET_ROUTES


def dispatch_sessions(req):
    for method, pattern, fn in ROUTES:
        m = re.match(pattern, req.path)
        if m and method == req.method:
            req.params = dict(m.groupdict())
            return fn(req)
    if any(re.match(p, req.path) for _, p, _ in ROUTES):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
