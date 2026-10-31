"""halo_harness.studio.local_tune_api -- Halo 3.3.6.0 R5: the tuning report and the changes with their scopes
(dispatched by studio/local_api.dispatch_local; docs/STUDIO-local-routes.md). Never a model call; nothing here changes
a server's settings: a server-side option is its exact line, for you to run.

    GET  local/host/<name>/tune                  ollama_steward/tune_report.report_for, with `cli` (halo local tune)
    POST local/host/<name>/tune/apply {id, scope?, session_id?}   a Halo-side option landed with its scope (keep unless
                                                 named); `session` with no session_id ends with the newest live session
    POST local/changes/apply {key, field, to, scope?, why?, session_id?}   one profile change of yours (the KV dial's
                                                 Apply), agent_proposals.land_user
    GET  local/changes?host=&all=                the changes (in force; `all`: reverted too), each with its line
    POST local/changes/revert {id | "all", scope?, host?}           put one or all back; the lines say what
    POST local/changes/scope {id, scope, session_id?}               a change's scope changed
"""

from __future__ import annotations

import re
import urllib.parse

_TUNE = re.compile(r"^local/host/(?P<name>[^/]+)/tune(?P<apply>/apply)?$")


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _session(body: dict):
    """(session_id, its pid): the one named, else the newest live session on this machine."""
    sid = str(body.get("session_id") or "").strip()
    try:
        from halo_harness.remote.registry import list_live
        rows = sorted(list_live(), key=lambda e: -(e.get("started") or 0))
    except Exception:
        rows = []
    hit = next((r for r in rows if r.get("session_id") == sid), None) if sid else (rows[0] if rows else None)
    return (sid or (hit or {}).get("session_id")) or None, (hit or {}).get("pid")


def get_tune(req, name: str):
    from halo_harness.ollama_steward.tune_report import report_for
    from halo_harness.providers.ollama import resolve_ollama_host
    if resolve_ollama_host(name) is None:
        return 404, {"error": f"no host named {name!r} here"}
    return 200, {**report_for(req.state_dir, name), "cli": f"halo local tune --host {name}"}


def post_apply(req, name: str):
    from halo_harness.ollama_steward import tune_lines
    body = _body(req)
    oid, scope = str(body.get("id") or "").strip(), str(body.get("scope") or "keep")
    if not oid:
        return 422, {"error": "apply takes {id, scope}", "problems": ["id: the option's id from the report"]}
    sid, pid = _session(body) if scope == "session" else (None, None)
    got = tune_lines.apply(req.state_dir, name, oid, scope=scope, session_id=sid, session_pid=pid)
    got["cli"] = f"halo local tune --host {name} --apply {oid} --scope {scope}"
    return (200 if got["ok"] else 409), ({**got} if got["ok"] else {"error": "; ".join(got["lines"]), **got})


def post_change(req):
    from halo_harness.ollama_steward.agent_proposals import land_user
    body = _body(req)
    scope = str(body.get("scope") or "keep")
    sid, pid = _session(body) if scope == "session" else (None, None)
    to = body.get("to")
    got = land_user(req.state_dir, {"key": body.get("key"), "field": body.get("field"), "to": to}, scope=scope,
                    by=str(body.get("by") or "user")[:20], why=str(body.get("why") or "")[:200], session_id=sid,
                    session_pid=pid)
    return (200 if got["ok"] else 422), (got if got["ok"] else {"error": got["line"], **got})


def get_changes(req):
    from halo_harness.ollama_steward import changes as C
    host = str(req.query.get("host") or "").strip()
    every = str(req.query.get("all") or "").lower() in ("1", "true", "yes")
    rows = [r for r in C.read(req.state_dir) if (every or not r.get("reverted_at"))
            and (not host or str(r.get("host")).lower() == host.lower())]
    rows.sort(key=lambda r: str(r.get("at")), reverse=True)
    return 200, {"changes": [{**r, "line": C.line_of(r), "scope_words": C.WORDS.get(r.get("scope"), "")} for r in rows],
                 "scopes": [{"id": s, "words": C.WORDS[s]} for s in C.SCOPES], "cli": "halo local changes"}


def post_revert(req):
    from halo_harness.ollama_steward import changes as C
    body = _body(req)
    which = str(body.get("id") or "").strip()
    if not which:
        return 422, {"error": "revert takes {id} (or id \"all\")", "problems": ["id: a change's id, or all"]}
    lines = C.revert(req.state_dir, which, "reverted from Studio", scope=body.get("scope") or None,
                     host=body.get("host") or None)
    return 200, {"ok": True, "lines": lines, "cli": f"halo local revert {'--all' if which == 'all' else which}"}


def post_scope(req):
    from halo_harness.ollama_steward import changes as C
    body = _body(req)
    scope = str(body.get("scope") or "")
    sid = _session(body)[0] if scope == "session" else None
    line = C.rescope(req.state_dir, str(body.get("id") or ""), scope, sid)
    ok = not line.startswith(("no change", "session needs")) and "is not a scope" not in line
    return (200 if ok else 422), ({"ok": True, "line": line} if ok else {"error": line})


ROUTES = {("GET", "local/changes"): get_changes, ("POST", "local/changes/revert"): post_revert,
          ("POST", "local/changes/scope"): post_scope, ("POST", "local/changes/apply"): post_change}


def dispatch_tune(req):
    """The answer for a route of this file, else None."""
    fn = ROUTES.get((req.method, req.path))
    if fn is not None:
        return fn(req)
    if any(p == req.path for _m, p in ROUTES):
        return 405, {"error": "method not allowed"}
    m = _TUNE.match(req.path)
    if not m:
        return None
    name = urllib.parse.unquote(m.group("name"))
    if m.group("apply"):
        return post_apply(req, name) if req.method == "POST" else (405, {"error": "method not allowed"})
    return get_tune(req, name) if req.method == "GET" else (405, {"error": "method not allowed"})
