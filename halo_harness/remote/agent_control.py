"""halo_harness.remote.agent_control -- the control socket's agent-level
commands (Halo 3.0.5.0 "Fleet" round R1). Wire shapes:

    agents                                 -> {agents: [row, ...]}       the session's live agent tree
    agent_tail   {agent_id, n=100, kinds?} -> {agent_id, events: [...]}  that agent's last n entries
    agent_steer  {agent_id, text, mode?, handoff?, from_agent?} -> {agent_id, mode, delivered}  nudge (default) | redirect;
                                           handoff: a Take over (a redirect recorded as a hand-off, 3.0.5.0 R4)
    agent_stop   {agent_id, reason?}       -> {agent_id, stopping: [...]}  the main agent: the turn interrupt
    pause        {agent_id?, reason?}      -> {paused}                   omitted: the whole session
    resume       {agent_id?}               -> {resumed, was_paused}
    shutdown     {reason?}                 -> {shutdown: true}           the session ends after the current tool call
    agent_follow {agent_id, on=true}       -> {agent_id, following}      agent_event frames for it while on

Rows and entries: agent/agent_registry.py, agent/agent_transcript.py.
"main" (or the session id) is the main agent, `job:<id>` a background Bash
job. Every command takes `via` (default "Studio"; 3.6.0.2 P3: a `by` a client
sends is never read, and no line or record names a user or host); those that
act on an agent are recorded in its own transcript (a `meta` node
`{"control": {cmd, via, ...}}`), its parent's transcript and the
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


def _caller(req: dict) -> str:
    """The request's via (3.6.0.2 P3: the only name a line or record carries; `by` is never read)."""
    return " ".join(_str(req, "via").split())[:32] or "Studio"


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


def _record(handle, tree, aid: str, cmd: str, via: str, **extra) -> None:
    log = getattr(_session(handle, tree, aid), "log", None)
    if log is not None:
        try:
            log.append_meta(control={"cmd": cmd, "via": via, "agent_id": aid, **extra})
        except Exception:
            pass


def _parent_line(handle, tree, aid: str, line: str) -> None:
    parent = (tree.row(aid) or {}).get("parent")
    log = getattr(_session(handle, tree, parent), "log", None) if parent else None
    if log is not None:
        try:
            log.append_meta(control_note=line)
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
    via = _caller(req)
    aid = _resolve(handle, tree, req)
    handoff = {"handoff": "take_over"} if req.get("handoff") else {}  # 3.0.5.0 R4: Fleet's Take over
    if handoff:
        mode = "redirect"
    head = f"[{'hand-off' if handoff else 'steer'} from {via}] "
    note = head + (text if mode == "nudge" else "Redirect: the rest of your current task is replaced. "
                   f"Your task is now: {text}")
    from halo_harness.live.talk import on_steer  # 3.3.16.2: another agent's steer (`from_agent`) is a talk
    if aid == tree.root_id:
        on_steer(tree, req, aid, text)
        result = handle.submit(note)
        _record(handle, tree, aid, "agent_steer", via, mode=mode, text=one_line(text, 400), **handoff)
        if handoff:
            _announce(handle, f"the main agent taken over from {via}: {one_line(text, 80)}")
        return {"agent_id": aid, "mode": mode, "delivered": "steer" if result.get("steered") else "turn", **result}
    _live_child(tree, aid)
    on_steer(tree, req, aid, text)
    tree.controls.post(aid, note, cut_by=via if mode == "redirect" else None)
    delivered = "inbox"
    if mode == "redirect":
        tree.update(aid, task=first_line(text))
    _record(handle, tree, aid, "agent_steer", via, mode=mode, text=one_line(text, 400), **handoff)
    verb = "taken over" if handoff else "steered"
    _parent_line(handle, tree, aid, f"{_label(tree, aid)} {verb} from {via}: {one_line(text, 80)}")
    return {"agent_id": aid, "mode": mode, "delivered": delivered}


def cmd_stop(handle, tree, req: dict) -> dict:
    via = _caller(req)
    reason = " ".join(_str(req, "reason").split())[:300] or "no reason given"
    aid = _resolve(handle, tree, req)
    if aid == tree.root_id:
        _record(handle, tree, aid, "agent_stop", via, reason=reason)
        return {"agent_id": aid, **handle.interrupt()}
    if aid.startswith("job:"):
        killer = getattr(getattr(handle.session, "job_registry", None), "kill", None)
        ok, message = killer(aid[4:]) if callable(killer) else (False, "no job registry in this session")
        _announce(handle, f"background job {aid[4:]} stopped from {via}: {reason}")
        return {"agent_id": aid, "stopped": bool(ok), "message": message}
    state = tree.state_of(aid)
    if state in FINISHED:
        raise HandleError(f"agent {aid} has already finished ({state})")
    ids = tree.controls.stop(aid, reason, via)
    _record(handle, tree, aid, "agent_stop", via, reason=reason)
    _parent_line(handle, tree, aid, f"{_label(tree, aid)} stopped from {via}: {reason}")
    return {"agent_id": aid, "stopping": ids}


def cmd_pause(handle, tree, req: dict, on: bool) -> dict:
    via = _caller(req)
    aid = _resolve(handle, tree, req, optional=True)
    if aid is not None and aid != tree.root_id:
        _live_child(tree, aid)
    target = aid or tree.root_id
    if not on:
        had = tree.controls.resume(aid)
        _record(handle, tree, target, "resume", via, scope="agent" if aid else "session")
        _announce(handle, f"{_label(tree, aid) if aid else 'the session'} resumed from {via}")
        return {"resumed": aid or "session", "was_paused": had}
    fresh = tree.controls.pause(aid, via)
    reason = " ".join(_str(req, "reason").split())[:120]  # 3.0.5.0 R4: "cap" when a spend cap paused it
    _record(handle, tree, target, "pause", via, scope="agent" if aid else "session", **({"reason": reason} if reason else {}))
    why = f": {reason}" if reason else ""
    if fresh and aid and aid != tree.root_id:
        _parent_line(handle, tree, aid, f"{_label(tree, aid)} paused from {via}{why}")
    elif fresh:
        _announce(handle, f"the session paused from {via}{why} (each agent holds at its next tool boundary)")
    return {"paused": aid or "session"}


def cmd_shutdown(handle, tree, req: dict, conn=None) -> dict:
    """3.6.0.4 S3-1: the session's end (which closes this socket) begins once this answer went out (`conn.then`,
    control_socket), so a caller never reads 'control socket closed' for a shutdown that worked."""
    via = _caller(req)
    reason = " ".join(_str(req, "reason").split())[:300] or "no reason given"
    tree.controls.begin_shutdown(reason, via)
    _record(handle, tree, tree.root_id, "shutdown", via, reason=reason)
    end = lambda: handle.control_shutdown(f"shut down from {via}: {reason}")  # noqa: E731
    if conn is not None:
        conn.then = end
    else:
        end()
    return {"shutdown": True}


def run(handle, req: dict, conn=None) -> dict:
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
        return cmd_shutdown(handle, tree, req, conn)
    if cmd == "agent_follow":
        aid = _resolve(handle, tree, req)
        on = req.get("on", True) is not False
        _record(handle, tree, aid, "agent_follow", _caller(req), on=on)
        return {"agent_id": aid, "following": tree.follow(aid, on)}
    raise HandleError(f"unknown agent cmd {cmd!r}")
