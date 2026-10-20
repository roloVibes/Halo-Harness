"""halo_harness.remote.agent_control -- the control socket's agent-level
commands (Halo 3.0.5.0 "Fleet" round R1). Wire shapes:

    agents                                 -> {agents: [row, ...]}       the session's live agent tree
    agent_tail   {agent_id, n=100, kinds?} -> {agent_id, events: [...]}  that agent's last n entries
    agent_steer  {agent_id, text, mode?, handoff?} -> {agent_id, mode, delivered}  nudge (default) | redirect;
                                           handoff: a Take over (a redirect recorded as a hand-off, 3.0.5.0 R4)
    agent_stop   {agent_id, reason?}       -> {agent_id, stopping: [...]}  the main agent: the turn interrupt
    pause        {agent_id?, reason?}      -> {paused}                   omitted: the whole session
    resume       {agent_id?}               -> {resumed, was_paused}
    shutdown     {reason?}                 -> {shutdown: true}           the session ends after the current tool call
    agent_follow {agent_id, on=true}       -> {agent_id, following}      agent_event frames for it while on

Rows and entries: agent/agent_registry.py, agent/agent_transcript.py.
"main" (or the session id) is the main agent, `job:<id>` a background Bash
job. Every command takes `by` (Studio sends `fleet.name`) and `via` (default
"Studio"); those that act on an agent are recorded in its own transcript (a
`meta` node `{"fleet": {cmd, by, via, ...}}`), its parent's transcript and the
TUI get one line for a steer, stop or pause. A steer is a user-role note read
before the agent's next model call: it never widens a permission, answers a
card or skips a gate.
"""

from __future__ import annotations

from halo_harness.agent import agent_registry
from halo_harness.agent.agent_transcript import first_line, one_line
from halo_harness.remote.base import HandleError

AGENT_CMDS = ("agents", "agent_tail", "agent_steer", "agent_stop", "pause", "resume", "shutdown", "agent_follow")
STEER_MODES = ("nudge", "redirect")
FINISHED = ("done", "failed", "stopped")


def _str(req: dict, key: str) -> str:
    v = req.get(key)
    return v if isinstance(v, str) else ""


def _caller(req: dict) -> tuple:
    by = " ".join(_str(req, "by").split())[:64] or "a remote client"
    via = " ".join(_str(req, "via").split())[:32] or "Studio"
    return by, via


def _tree(handle):
    return agent_registry.tree_for(handle.session)


def _resolve(handle, tree, req: dict, *, optional: bool = False):
    raw = _str(req, "agent_id").strip()
    if not raw:
        if optional:
            return None
        raise HandleError('agent_id is required ("main" is the main agent; `agents` lists the rest)')
    if raw in (agent_registry.MAIN, handle.session_id, tree.root_id):
        return tree.root_id
    if raw.startswith("job:") and any(r["agent_id"] == raw for r in tree.public_rows()):
        return raw
    if tree.row(raw) is None:
        raise HandleError(f"no agent {raw!r} in this session (`agents` lists them)")
    return raw


def _session(handle, tree, aid: str):
    return handle.session if aid == tree.root_id else tree.session_of(aid)


def _label(tree, aid: str) -> str:
    row = tree.row(aid) or {}
    return "the main agent" if aid == tree.root_id else f"{row.get('name') or 'agent'} ({aid})"


def _announce(handle, line: str) -> None:
    if hasattr(handle, "controller"):
        handle._note(line)  # the TUI transcript, and the feed through the controller's tap
        return
    try:
        from halo_harness import events
        handle.hub.publish(events.system_note(f"(remote) {line}"))
    except Exception:
        pass


def _record(handle, tree, aid: str, cmd: str, by: str, via: str, **extra) -> None:
    log = getattr(_session(handle, tree, aid), "log", None)
    if log is not None:
        try:
            log.append_meta(fleet={"cmd": cmd, "by": by, "via": via, "agent_id": aid, **extra})
        except Exception:
            pass


def _parent_line(handle, tree, aid: str, line: str) -> None:
    parent = (tree.row(aid) or {}).get("parent")
    log = getattr(_session(handle, tree, parent), "log", None) if parent else None
    if log is not None:
        try:
            log.append_meta(fleet_note=line)
        except Exception:
            pass
    _announce(handle, line)


def _live_child(tree, aid: str):
    if aid.startswith("job:"):
        raise HandleError("a background job takes no steer or pause; agent_stop ends it")
    state = tree.state_of(aid)
    if state in FINISHED:
        raise HandleError(f"agent {aid} has finished ({state}); its parent is where to steer next")
    return tree.session_of(aid)


def cmd_steer(handle, tree, req: dict) -> dict:
    text = _str(req, "text").strip()
    if not text:
        raise HandleError("empty steer")
    mode = _str(req, "mode") or "nudge"
    if mode not in STEER_MODES:
        raise HandleError(f"steer mode must be one of {', '.join(STEER_MODES)}, got {mode!r}")
    by, via = _caller(req)
    aid = _resolve(handle, tree, req)
    handoff = {"handoff": "take_over"} if req.get("handoff") else {}  # 3.0.5.0 R4: Fleet's Take over
    if handoff:
        mode = "redirect"
    head = f"[{'hand-off' if handoff else 'steer'} from {by} via {via}] "
    note = head + (text if mode == "nudge" else "Redirect: the rest of your current task is replaced. "
                   f"Your task is now: {text}")
    if aid == tree.root_id:
        result = handle.submit(note)
        _record(handle, tree, aid, "agent_steer", by, via, mode=mode, text=one_line(text, 400), **handoff)
        if handoff:
            _announce(handle, f"the main agent taken over from {via} by {by}: {one_line(text, 80)}")
        return {"agent_id": aid, "mode": mode, "delivered": "steer" if result.get("steered") else "turn", **result}
    _live_child(tree, aid)
    tree.controls.post(aid, note, cut_by=f"{by} from {via}" if mode == "redirect" else None)
    delivered = "inbox"
    if mode == "redirect":
        tree.update(aid, task=first_line(text))
    _record(handle, tree, aid, "agent_steer", by, via, mode=mode, text=one_line(text, 400), **handoff)
    verb = "taken over" if handoff else "steered"
    _parent_line(handle, tree, aid, f"{_label(tree, aid)} {verb} from {via} by {by}: {one_line(text, 80)}")
    return {"agent_id": aid, "mode": mode, "delivered": delivered}


def cmd_stop(handle, tree, req: dict) -> dict:
    by, via = _caller(req)
    reason = " ".join(_str(req, "reason").split())[:300] or "no reason given"
    aid = _resolve(handle, tree, req)
    if aid == tree.root_id:
        _record(handle, tree, aid, "agent_stop", by, via, reason=reason)
        return {"agent_id": aid, **handle.interrupt()}
    if aid.startswith("job:"):
        killer = getattr(getattr(handle.session, "job_registry", None), "kill", None)
        ok, message = killer(aid[4:]) if callable(killer) else (False, "no job registry in this session")
        _announce(handle, f"background job {aid[4:]} stopped from {via} by {by}: {reason}")
        return {"agent_id": aid, "stopped": bool(ok), "message": message}
    state = tree.state_of(aid)
    if state in FINISHED:
        raise HandleError(f"agent {aid} has already finished ({state})")
    ids = tree.controls.stop(aid, by, reason, via)
    _record(handle, tree, aid, "agent_stop", by, via, reason=reason)
    _parent_line(handle, tree, aid, f"{_label(tree, aid)} stopped from {via} by {by}: {reason}")
    return {"agent_id": aid, "stopping": ids}


def cmd_pause(handle, tree, req: dict, on: bool) -> dict:
    by, via = _caller(req)
    aid = _resolve(handle, tree, req, optional=True)
    if aid is not None and aid != tree.root_id:
        _live_child(tree, aid)
    target = aid or tree.root_id
    if not on:
        had = tree.controls.resume(aid)
        _record(handle, tree, target, "resume", by, via, scope="agent" if aid else "session")
        _announce(handle, f"{_label(tree, aid) if aid else 'the session'} resumed from {via} by {by}")
        return {"resumed": aid or "session", "was_paused": had}
    fresh = tree.controls.pause(aid, by, via)
    reason = " ".join(_str(req, "reason").split())[:120]  # 3.0.5.0 R4: "cap" when a spend cap paused it
    _record(handle, tree, target, "pause", by, via, scope="agent" if aid else "session", **({"reason": reason} if reason else {}))
    why = f": {reason}" if reason else ""
    if fresh and aid and aid != tree.root_id:
        _parent_line(handle, tree, aid, f"{_label(tree, aid)} paused from {via} by {by}{why}")
    elif fresh:
        _announce(handle, f"the session paused from {via} by {by}{why} (each agent holds at its next tool boundary)")
    return {"paused": aid or "session"}


def cmd_shutdown(handle, tree, req: dict) -> dict:
    by, via = _caller(req)
    reason = " ".join(_str(req, "reason").split())[:300] or "no reason given"
    tree.controls.begin_shutdown(by, reason, via)
    _record(handle, tree, tree.root_id, "shutdown", by, via, reason=reason)
    handle.fleet_shutdown(f"shut down from {via} by {by}: {reason}")
    return {"shutdown": True}


def run(handle, req: dict) -> dict:
    cmd = req.get("cmd")
    tree = _tree(handle)
    if cmd == "agents":
        return {"agents": tree.public_rows()}
    if cmd == "agent_tail":  # remote/agent_tail.py (3.0.5.0 R4: split out to keep this file small)
        from halo_harness.remote.agent_tail import cmd_tail
        return cmd_tail(handle, tree, req)
    if cmd == "agent_steer":
        return cmd_steer(handle, tree, req)
    if cmd == "agent_stop":
        return cmd_stop(handle, tree, req)
    if cmd in ("pause", "resume"):
        return cmd_pause(handle, tree, req, cmd == "pause")
    if cmd == "shutdown":
        return cmd_shutdown(handle, tree, req)
    if cmd == "agent_follow":
        aid = _resolve(handle, tree, req)
        on = req.get("on", True) is not False
        by, via = _caller(req)
        _record(handle, tree, aid, "agent_follow", by, via, on=on)
        return {"agent_id": aid, "following": tree.follow(aid, on)}
    raise HandleError(f"unknown agent cmd {cmd!r}")
