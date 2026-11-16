"""halo_harness.crew.map_events -- what a session on a map says as it runs, for the lit Map (Halo 3.6.0.0 R4;
docs/STUDIO-map.md "While a session runs").

Frames on the session's feed (the agent tree's listeners: remote/agent_frames.py publishes them; Studio asks
every session for them, studio/feed_kinds.py), each also one `receipt` node in the session's log (kind "map") so
History replays the very same events (`recorded`, read by studio/live_recording_api.py):

    map_hop    a hand-off: {map, line?, from, to, name, kind, when, why, task, state, off, t, agent_id?, aid?, workflow?,
               t0?, error?, background?, chain?}; state start | end | skipped (a chain's line not taken). 3.6.0.2 R48:
               `from` is the REAL caller's box (`caller_box`); `to` a box, `workflow:{W}` (the Workflow tool's door,
               crew/flow_door.py) or `made-up:{aid}` (a call on no line); `off` only off the default map with no line
    map_step   a workflow box's step runner, in a session: {map, box, workflow, kind, t, ...} -- kind start | step |
               agent | check | end with crew/runner.py's own fields (the Try it record reads the same)
    map_card   a Builder card main parked for the person: {id, changes} (crew/changes.py `public` rows: the ghosts the
               Map draws); {id, done: true} once it is answered or dismissed
    builder_done  3.6.0.2 R25: every Builder card, AFTER its files are written (or not): {id, outcome, wrote, undo,
               next, this_session, maps, t} (`builder_done`); its receipt in the log is the same without `maps`

A spawned agent's row carries `crew: {map, box, line?, agent, saved, workflow?, step?, made_up?}` (agent/
agent_registry.py FIELDS; 3.6.0.2 R13): the box it runs for (a workflow's step: its caller's box, the workflow and the
step), the agent it runs and whether that is a saved agent; `made_up` only for `general-purpose` or a name no spec
knows. Every frame goes to the TOP session's feed and log, and none once the session is closed (`close`, called by
agent/loop.py Session.close_runtimes). The log also gets one `map_start` node
(the map, its file -- scope, path, content hash, R50 -- and when) so a finished session's replay knows the map it ran on. Nothing here calls a model, and a failure
to publish never stops a hand-off.
"""

from __future__ import annotations

import json
import time

TASK = 120


def _first(text) -> str:
    line = next((x.strip() for x in str(text or "").splitlines() if x.strip()), "")
    return line if len(line) <= TASK else line[: TASK - 3] + "..."


def _log(session, event: str, data: dict) -> None:
    log = getattr(session, "log", None)
    if log is None or not hasattr(log, "_append"):
        return
    try:
        log._append({"type": "receipt", "kind": "map", "event": event, "data": data})
    except Exception:
        pass


def closed(session) -> bool:
    return bool(getattr(session, "_map_closed", False))


def close(session) -> None:
    """The session ended (Session.close_runtimes): no frame from it reaches the page or its log any more (R48)."""
    try:
        session._map_closed = True
    except Exception:
        pass


def _top(session):
    """The session whose feed and log the page reads: the root of the tree `session` is in."""
    if session is None:
        return None
    try:
        from halo_harness.agent.agent_registry import tree_for
        tree = tree_for(session)
        return tree.session_of(tree.root_id) or session
    except Exception:
        return session


def publish(session, event: str, data: dict, *, log: bool = True) -> dict:
    """One frame on the top session's feed (as main's) and, by default, the same in its log; nothing once closed."""
    top = _top(session)
    if closed(session) or closed(top):
        return data
    try:
        from halo_harness.agent.agent_registry import agent_key, tree_for
        tree_for(top)._emit(event, agent_key(top), data)
    except Exception:
        pass
    if log:
        _log(top, event, data)
    return data


def caller_box(runtime) -> str:
    """R48: the REAL caller's box -- the calling session's row's `crew.box`, else the nearest parent row's, else main."""
    session = getattr(runtime, "parent", None)
    try:
        from halo_harness.agent.agent_registry import agent_key, tree_for
        tree, aid = tree_for(session), agent_key(session)
        for _ in range(32):
            r = tree.row(aid) if aid else None
            if not r:
                break
            if (r.get("crew") or {}).get("box"):
                return str(r["crew"]["box"])
            aid = r.get("parent")
    except Exception:
        pass
    return "main"


def _off(mc, line: str) -> bool:
    """R48: a hand-off off the lines -- not the default map, and no line followed (decided here only)."""
    from halo_harness.crew.compile import is_default
    return not line and not is_default(getattr(mc, "map", None))


def identity(mc) -> dict:
    """3.6.0.2 R50: the FILE the control follows now -- {scope, path, hash} of the version it holds (taken when it was
    compiled, crew/compile.py; a refresh brings the new file's); all None when not on a map. Reads no file."""
    c = getattr(mc, "map", None) if getattr(mc, "is_map", False) else None
    return {k: (getattr(c, k, "") or None) if isinstance(getattr(c, k, None), str) else None
            for k in ("scope", "path", "hash")}


def started(session, mc) -> None:
    """The map this session runs on, once, in its log (a replay reads it); its `t` stays on the session (3.6.0.2 R40:
    F1, the status row's `map_since`, crew/map_facts.py) and its file: scope, path, content hash (R50)."""
    t = round(time.time(), 3)
    try:
        session._map_started_at = t
    except Exception:
        pass
    _log(session, "map_start", {"map": getattr(mc, "map_name", ""), **identity(mc), "t": t})


def hop(runtime, mc, h: dict, why: str, task: str, state: str, **extra) -> dict:
    line = str(h.get("line") or "")
    data = {"map": mc.map_name, **({"line": line} if line else {}),
            "from": line.split(" -> ")[0] if " -> " in line else caller_box(runtime), "to": h.get("box"),
            "name": h.get("name"), "kind": h.get("kind"), "when": _when(h.get("when")) if h.get("when") else "", "why": why,
            "task": _first(task), "state": state, "off": _off(mc, line), "t": round(time.time(), 3)}
    data.update({k: v for k, v in extra.items() if v not in (None, "", False)})
    return publish(getattr(runtime, "parent", None), "map_hop", data)


def _when(w) -> str:
    try:
        from halo_harness.crew.map_when import words
        return words(w)
    except Exception:
        return str(w or "")


def tag(runtime, child, mc, box: str, *, line: str = "", made_up: bool = False, agent: str = "", saved=None,
        workflow: str = "", step=None) -> str:
    """The child's row says the box it runs for (a made-up helper: the box that started it), the agent it runs and
    whether that is a saved agent, a workflow's step its workflow and step (R13). Its agent id."""
    aid = str(getattr(child, "agent_id", "") or "")
    if not aid:
        return ""
    crew = {"map": mc.map_name, "box": box}
    if line:
        crew["line"] = line
    if agent:
        crew["agent"] = agent
    if saved is not None:
        crew["saved"] = bool(saved)
    if workflow:
        crew["workflow"] = workflow
    if step is not None:
        crew["step"] = step
    if made_up:
        crew["made_up"] = True
    try:
        from halo_harness.agent.agent_registry import tree_for
        tree_for(getattr(runtime, "parent", None)).update(aid, crew=crew)
    except Exception:
        pass
    return aid


def step_emit(runtime, mc, box: str, workflow: str):
    """The step runner's `emit` for a workflow box in a session: each event a `map_step` frame."""
    session = getattr(runtime, "parent", None)

    def emit(kind: str, data: dict) -> None:
        body = {k: v for k, v in (data or {}).items() if k != "text"}
        if (data or {}).get("text"):
            body["said"] = _first(data["text"])
        publish(session, "map_step", {"map": mc.map_name, "box": box, "workflow": workflow, "kind": kind,
                                      "t": round(time.time(), 3), **body})
    return emit


def card(session, request_id: str, preview: dict) -> None:
    """A Builder card main parked: its change rows, so the Map draws them as ghosts ("answer it in the session")."""
    try:
        from halo_harness.crew.changes import public
        rows = public(list(preview.get("rows") or []))
    except Exception:
        rows = []
    if any(str(r.get("target") or "").startswith("map:") for r in rows):
        publish(session, "map_card", {"id": request_id, "changes": rows, "t": round(time.time(), 3)}, log=False)


def card_done(session, request_id: str) -> None:
    publish(session, "map_card", {"id": request_id, "done": True, "t": round(time.time(), 3)}, log=False)


MAP_BODY_MAX = 65536  # 3.6.0.2 R25/R28: a bigger map's body is left out of the frame; the page fetches it


def _next_map():
    """F4: the map new sessions use (config `crew.map`), None when unset."""
    try:
        from halo_harness.theme import get_config_value
        name = get_config_value("crew.map", default=None)
    except Exception:
        return None
    return name.strip() if isinstance(name, str) and name.strip() else None


def _this_map(session):
    """F2: the map this session runs on (its `team_control.map_name` when it is a map), else None."""
    for s in (_top(session), session):
        tc = getattr(s, "team_control", None)
        if tc is not None and getattr(tc, "is_map", False):
            return getattr(tc, "map_name", None) or None
    return None


def _bodies(session, wrote: list) -> dict:
    """`{name: body}` of each map the card wrote, as `GET crew/map/<name>` gives it; one over 64 KB is left out."""
    from halo_harness.crew import store
    out = {}
    for w in wrote:
        if w.get("kind") != "map" or w.get("removed"):
            continue
        try:
            body = store.read(store.path_for("map", w["name"], cwd=getattr(session, "cwd", None)))
            if body is None:
                continue
            body = store.clean(body)
            if len(json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")) <= MAP_BODY_MAX:
                out[w["name"]] = body
        except Exception:
            continue
    return out


def builder_done(session, request_id: str, outcome) -> dict:
    """3.6.0.2 R25: a Builder card was answered and its files are written (or not): `{id, outcome: applied | left |
    failed, wrote: [{kind, name, added}], undo, next, this_session, maps, t}` on the feed; the same without `maps` as
    a receipt in the log and on the session (`_builder_built`, the status row's "built"). Never raises."""
    try:
        got = outcome if isinstance(outcome, dict) else {}
        wrote = [dict(w) for w in got.get("wrote") or []]
        receipt = {"id": request_id, "outcome": got.get("outcome") or "left", "wrote": wrote,
                   "undo": got.get("undo") or None, "next": _next_map(), "this_session": _this_map(session),
                   "t": round(time.time(), 3)}
        try:
            session._builder_built = receipt
        except Exception:
            pass
        data = {**receipt, "maps": _bodies(session, wrote)}
        publish(session, "builder_done", data, log=False)
        top = _top(session)
        if not (closed(session) or closed(top)):
            _log(top, "builder_done", receipt)
        return data
    except Exception:
        return {}


def recorded(path) -> dict:
    """`{map, events: [{event, data}]}` from a session's log: what the lit Map replays (in order)."""
    from halo_harness.live.history import read_nodes
    out: dict = {"map": None, "events": []}
    for node in read_nodes(path) if path else []:
        if not isinstance(node, dict) or node.get("type") != "receipt" or node.get("kind") != "map":
            continue
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        if node.get("event") == "map_start":
            out["map"] = out["map"] or data.get("map")
        elif node.get("event") in ("map_hop", "map_step"):
            out["events"].append({"event": node["event"], "data": data})
            out["map"] = out["map"] or data.get("map")
    return out
