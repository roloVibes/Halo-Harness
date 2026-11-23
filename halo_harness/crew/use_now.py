"""halo_harness.crew.use_now -- an agent saved while a session runs, usable in that session at once (Halo 3.6.0.15 UN,
the design's rule U1): the VALIDATED body goes into the running top session's agents (`agent/subagent.py`
`AgentRuntime.agents`, the very dict every helper of the session shares) at main's next model call, never a restart.

    can_take(session) -> bool                    the session main is told kinds in (`agent/helpers_words.on_auto`)
    put(session, body, scope, sha256, *, note=True) -> (took, why)
                                                 queue a body; why is "" (queued), "same" (the body it already runs),
                                                 "map", "off", "problems", "built-in", "outranked", "tool:<T>", "mode"
    gone(session, name, scope) -> bool           queue taking back an agent whose file was deleted
    back(session, name) -> bool                  queue putting back what the session started with (an undo)
    take(session) -> list[dict]                  apply what is queued, in order: [{name, change: added | edited | gone
                                                 | back, ...}]; called before each of main's model calls (crew/kinds_note)
    started_with(session) -> dict                the agents the session started with
    added(session) -> list                       the names a take added, not taken back since

No thread, no timer, no socket, no file read: every input arrives as an argument. The state lives on the top session,
made on first use only (a session nothing is ever put to gains no attribute): `_kinds_pending` (name -> change, in queue
order), `_start_specs` (name -> its start spec, or None), `_kinds_added`, `_kinds_sha` (name -> the body's sha256). No
line a person or a model reads is written here: crew/ready_now.py and crew/kinds_note.py hold the words.
"""

from __future__ import annotations

_OUTRANK = ("cli-agents", "managed")  # and every "project:" source (a project's .claude/agents): agents_md.discover_agents


def can_take(session) -> bool:
    from halo_harness.agent.helpers_words import on_auto
    return on_auto(session)


def _not_auto(session) -> str:
    from halo_harness.crew.compile import is_default
    tc = getattr(session, "team_control", None)
    return "map" if getattr(tc, "is_map", False) and not is_default(getattr(tc, "map", None)) else "off"


def _outranks(source: str, scope: str) -> bool:
    return source.startswith("project:") or source in _OUTRANK or (scope == "yours" and source == "crew:project")


def _catalog(session) -> list:
    """The names a spawn resolves a helper's tools against (agent/subagent.py: the catalog, else the registry)."""
    cat = getattr(session, "session_catalog", None)
    names = cat.names if cat is not None else session.tool_registry.names()
    return list(names() if callable(names) else names)


def _tool_why(uses, names: list) -> str:
    from halo_harness.crew.spec import TOOLS
    for u in uses or []:
        u = str(u)
        if u in TOOLS:
            ok, first = any(t in names for t in TOOLS[u]), TOOLS[u][0]
        elif u.startswith("skill:"):
            ok, first = "Skill" in names, "Skill"
        elif u.startswith("mcp:"):
            prefix = f"mcp__{u[len('mcp:'):]}__"
            ok, first = any(str(n).startswith(prefix) for n in names), prefix + "*"
        else:
            continue
        if not ok:
            return f"tool:{first}"
    return ""


def _current(session, name: str):
    pending = (getattr(session, "_kinds_pending", None) or {}).get(name)
    if pending and pending.get("op") == "put":
        return pending["spec"]
    return session.agent_runtime.agents.get(name)


def _queue(session, name: str, change: dict) -> None:
    pending = session.__dict__.setdefault("_kinds_pending", {})
    pending.pop(name, None)  # a later change of a name replaces its earlier one and moves to the end
    pending[name] = change


def put(session, body: dict, scope: str, sha256: str, *, note: bool = True) -> "tuple[bool, str]":
    from halo_harness.config.agents_md import BUILTIN_NAMES
    from halo_harness.crew import store
    from halo_harness.crew.formats import agent_problems
    from halo_harness.crew.map_session import RANK
    from halo_harness.crew.spec import agent_spec
    if not can_take(session):
        return False, _not_auto(session)
    name = body.get("name") if isinstance(body, dict) else None
    if not isinstance(body, dict) or agent_problems(store.clean(body), name=str(name or "")):
        return False, "problems"
    if name in BUILTIN_NAMES:
        return False, "built-in"
    cur = _current(session, name)
    if cur is not None and _outranks(str(getattr(cur, "source", "") or ""), scope):
        return False, "outranked"
    spec = agent_spec(store.clean(body), source=f"crew:{scope}")
    why = _tool_why(body.get("uses"), _catalog(session))
    if why:
        return False, why
    mode = getattr(getattr(session, "permission_engine", None), "mode", "default")
    if mode != "plan" and RANK.get(spec.permission_mode, 99) > RANK.get(mode, 1):
        return False, "mode"
    with session.agent_runtime.lock:
        pending = getattr(session, "_kinds_pending", None) or {}
        if sha256 == (getattr(session, "_kinds_sha", None) or {}).get(name) and name not in pending:
            return True, "same"
        _queue(session, name, {"op": "put", "spec": spec, "sha": sha256, "scope": scope, "note": note})
    return True, ""


def gone(session, name: str, scope: str) -> bool:
    runtime = session.agent_runtime
    with runtime.lock:
        pending = (getattr(session, "_kinds_pending", None) or {}).get(name)
        cur = runtime.agents.get(name)
        if not (pending and pending.get("op") == "put") and \
                (cur is None or str(getattr(cur, "source", "") or "") != f"crew:{scope}"):
            return False  # the deleted file is not what this session runs
        _queue(session, name, {"op": "gone", "scope": scope})
    return True


def _changed(session, name: str) -> bool:
    starts = getattr(session, "_start_specs", None) or {}
    return name in starts and session.agent_runtime.agents.get(name) is not starts[name]


def back(session, name: str) -> bool:
    with session.agent_runtime.lock:
        pending = (getattr(session, "_kinds_pending", None) or {}).get(name)
        if not (_changed(session, name) or (pending and pending.get("op") == "put")):
            return False
        _queue(session, name, {"op": "back"})
    return True


def _undo(session, name: str, change: str) -> dict:
    added = session.__dict__.setdefault("_kinds_added", [])
    if name in added:
        added.remove(name)
    session.__dict__.setdefault("_kinds_sha", {}).pop(name, None)
    return {"name": name, "change": change}


def take(session) -> "list[dict]":
    if not getattr(session, "_kinds_pending", None):
        return []
    runtime = session.agent_runtime
    agents = runtime.agents  # changed IN PLACE: every helper's runtime shares this dict (agent/subagent.py)
    out: list = []
    with runtime.lock:
        pending = session._kinds_pending
        starts = session.__dict__.setdefault("_start_specs", {})
        added = session.__dict__.setdefault("_kinds_added", [])
        shas = session.__dict__.setdefault("_kinds_sha", {})
        while pending:
            name = next(iter(pending))
            ch = pending.pop(name)
            op = ch.get("op")
            if op == "put":
                if name not in starts:
                    starts[name] = agents.get(name)
                spec = ch["spec"]
                agents[name] = spec
                shas[name] = ch.get("sha")
                start = starts[name]
                if start is not None and getattr(start, "source", None) == spec.source:
                    out.append({"name": name, "change": "edited"})  # main read this name at its start
                elif name not in added:
                    added.append(name)
                    out.append({"name": name, "change": "added", "note": ch.get("note", True), "spec": spec})
            elif op == "gone":
                cur = agents.get(name)
                scope_src = f"crew:{ch.get('scope')}"
                if cur is None or (name not in starts and getattr(cur, "source", None) != scope_src):
                    continue  # never taken, or not what this session runs
                if name not in starts:
                    starts[name] = cur
                start = starts[name]
                if start is not None and getattr(start, "source", None) != scope_src:
                    agents[name] = start
                    out.append(_undo(session, name, "back"))
                else:
                    agents.pop(name, None)
                    out.append(_undo(session, name, "gone"))
            elif op == "back":
                if not _changed(session, name):
                    continue
                start = starts[name]
                if start is None:
                    agents.pop(name, None)
                    out.append(_undo(session, name, "gone"))
                else:
                    agents[name] = start
                    out.append(_undo(session, name, "back"))
    return out


def started_with(session) -> dict:
    agents = session.agent_runtime.agents
    starts = getattr(session, "_start_specs", None)
    if not starts:
        return agents
    out = dict(agents)
    for name, spec in starts.items():
        if spec is None:
            out.pop(name, None)
        else:
            out[name] = spec
    return out


def added(session) -> list:
    return list(getattr(session, "_kinds_added", None) or [])
