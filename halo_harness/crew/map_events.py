"""halo_harness.crew.map_events -- what a session on a map says as it runs, for the lit Map (Halo 3.6.0.0 R4;
docs/STUDIO-map.md "While a session runs").

Three frames on the session's feed (the agent tree's listeners: remote/agent_frames.py publishes them; Studio asks
every session for them, studio/feed_kinds.py), each also one `receipt` node in the session's log (kind "map") so
History replays the very same events (`recorded`, read by studio/live_recording_api.py):

    map_hop    a hand-off on a line the person drew: {map, line, from, to, name, kind, when, why, task, state, t,
               agent_id?, t1?, error?, background?, chain?}; state start | end | skipped (a chain's line not taken)
    map_step   a workflow box's step runner, in a session: {map, box, workflow, kind, t, ...} -- kind start | step |
               agent | check | end with crew/runner.py's own fields (the Try it record reads the same)
    map_card   a Builder card main parked for the person: {id, changes} (crew/changes.py `public` rows: the ghosts the
               Map draws); {id, done: true} once it is answered or dismissed

A spawned agent's row carries `crew: {map, box, line?, made_up?}` (agent/agent_registry.py FIELDS): the box it runs
for, or, for a helper main made up for the task, the box that started it. The log also gets one `map_start` node
(the map and when) so a finished session's replay knows the map it ran on. Nothing here calls a model, and a failure
to publish never stops a hand-off.
"""

from __future__ import annotations

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


def publish(session, event: str, data: dict, *, log: bool = True) -> dict:
    """One frame on the session's feed (as main's) and, by default, the same in its log."""
    try:
        from halo_harness.agent.agent_registry import agent_key, tree_for
        tree_for(session)._emit(event, agent_key(session), data)
    except Exception:
        pass
    if log:
        _log(session, event, data)
    return data


def started(session, mc) -> None:
    """The map this session runs on, once, in its log (a replay reads it)."""
    _log(session, "map_start", {"map": getattr(mc, "map_name", ""), "t": round(time.time(), 3)})


def hop(runtime, mc, h: dict, why: str, task: str, state: str, **extra) -> dict:
    line = str(h.get("line") or "")
    data = {"map": mc.map_name, "line": line, "from": line.split(" -> ")[0] if " -> " in line else "main", "to": h.get("box"),
            "name": h.get("name"), "kind": h.get("kind"), "when": _when(h.get("when")), "why": why, "task": _first(task),
            "state": state, "t": round(time.time(), 3)}
    data.update({k: v for k, v in extra.items() if v not in (None, "", False)})
    return publish(getattr(runtime, "parent", None), "map_hop", data)


def _when(w) -> str:
    try:
        from halo_harness.crew.map_when import words
        return words(w)
    except Exception:
        return str(w or "")


def tag(runtime, child, mc, box: str, *, line: str = "", made_up: bool = False) -> str:
    """The child's row says the box it runs for (a made-up helper: the box that started it). Its agent id."""
    aid = str(getattr(child, "agent_id", "") or "")
    if not aid:
        return ""
    crew = {"map": mc.map_name, "box": box}
    if line:
        crew["line"] = line
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
