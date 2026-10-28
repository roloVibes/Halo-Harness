"""halo_harness.fleet.control -- commands from a hub, applied as this
harness's owner allows (Halo 3.0.5.0 "Fleet" round R2).

relay_runtime.py verifies the hub's signature on each `command` doc and
hands it here with the session's handle and that hub's policy:

    status, agents                      answered (rows scrubbed for the share level)
    doctor                              answered: the read-only health subset (fleet/health.py, 3.0.5.0 R4)
    capabilities {refresh?}             answered: this harness's capability catalog from its cache, gathered
                                        afresh when older than an hour or on refresh (fleet/capabilities.py, 3.0.6.0 R6)
    recall {query, k}                   answered from this harness's own index (recall_fleet.py, 3.1.2.0 R3): the
                                        hits only, never the index; refused under fleet.recall.share: false
    coach_library {entry}               answered: one entry of this harness's coach library (entry.json, EXPERIENCE.md,
                                        overlay.json, files/; at most 256 KB), under the same switch as recall
                                        (orchestra/coach_library_share.py, 3.1.6.0 R3)
    knowledge {id} | {kind, all}        answered: findings / decisions of this harness, scrubbed, under the same
                                        switch as recall (knowledge/share.py, 3.1.8.0 R4)
    agent_tail, agent_follow, tail      answered when this hub's share is `full`
    agent_steer, agent_stop, pause,     fleet.allow_control `none`: refused, with the reason the hub shows;
    resume, shutdown, steer, interrupt  `ask` (the default): a card in the owner's TUI, "<name> on <hub>
                                        wants to steer <agent>: <text>" [allow] [deny] (no answer in
                                        ASK_TIMEOUT_S, or a print-mode session: denied); `all`: applied
    answer                              only with allow_control `all` AND fleet.allow_answers true, scope
                                        `once` (a hub never learns a rule), never the fleet card itself
    note                                a person's message (`fleet.message`), shown to the owner without
                                        asking unless allow_control is `none`; the model never sees it
    run_task                            3.0.6.0 R7: run one part of a mission here (fleet/mission_worker.py), under
                                        allow_control like steer: `ask` cards "<hub> asks to run mission <m> part
                                        <n> here: <title> (claims: ...)", `none` refuses, `all` starts it
    ollama_load, ollama_unload          3.3.5.0 R1: a model on a host this machine serves (fleet/control_models.py),
                                        under allow_control like steer

Applied commands run through remote/agent_control.py with `by` = the person
at the hub and `via` = "hub <name>", so the session's transcript records
who did what; a refusal is recorded too. The owner's permission engine runs
for every agent as before.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from halo_harness.fleet import identity, protocol
from halo_harness.remote.base import HandleError

ASK_TIMEOUT_S = 120.0
ASK_PREFIX = "fleet-ask:"
VERBS = {"agent_steer": "steer", "agent_stop": "stop", "pause": "pause", "resume": "resume",
         "shutdown": "shut down", "steer": "steer", "interrupt": "interrupt"}
ANSWER_KEYS = ("kind", "request_id", "target", "id", "action", "instruction", "message", "answer", "approved",
               "feedback", "mode_after")


class Refused(Exception):
    pass


def policy(entry: Optional[dict]) -> dict:
    return {"share": identity.share(entry), "allow_control": identity.allow_control(entry),
            "allow_answers": identity.allow_answers()}


def _clean(value, n: int = 64) -> str:
    return " ".join(str(value or "").split())[:n]


def _agent_cmd(handle, cmd: str, **fields):
    from halo_harness.remote import agent_control
    return agent_control.run(handle, {"cmd": cmd, **fields})


def _record(handle, **fleet) -> None:
    log = getattr(handle.session, "log", None)
    if log is not None:
        try:
            log.append_meta(fleet=fleet)
        except Exception:
            pass


def _label(handle, fields: dict) -> str:
    aid = str(fields.get("agent_id") or "")
    if not aid or aid in ("main", handle.session_id):
        return "the main agent" if aid else "this session"
    try:
        from halo_harness.agent.agent_registry import tree_for
        row = tree_for(handle.session).row(aid) or {}
    except Exception:
        row = {}
    return f"{row.get('name') or 'agent'} ({aid})"


def describe(handle, cmd: str, fields: dict, by: str, hub: str) -> str:
    if cmd == "run_task":
        from halo_harness.fleet.mission_worker import describe as describe_task
        return describe_task(fields, hub)
    if cmd in protocol.MODEL_CMDS:  # 3.3.5.0 R1: the Local tab's Load / Unload
        from halo_harness.fleet.control_models import describe as describe_model
        return describe_model(cmd, fields, by, hub)
    what = " ".join(" ".join(str(fields.get(k) or "").split()) for k in ("text", "reason")).strip()
    target = "the main agent" if cmd in ("steer", "interrupt") else _label(handle, fields)
    if cmd == "shutdown":
        target = "this session"
    line = f"{by} on {hub} wants to {VERBS.get(cmd, cmd)} {target}"
    return f"{line}: {what[:300]}" if what else line


def ask_owner(handle, text: str, cid: str, interim: Optional[Callable] = None,
              timeout: float = ASK_TIMEOUT_S) -> str:
    """The owner's answer from a card in the TUI: `allow`, `deny`, or `timeout`."""
    from halo_harness import events
    controller = getattr(handle, "controller", None)
    rid = ASK_PREFIX + cid
    slot = {"event": threading.Event(), "answer": None}
    waiters = handle.session._question_waiters
    waiters[rid] = slot
    try:
        controller.events.put(events.Event("question", {"id": rid, "name": "Fleet", "input": {
            "question": text, "header": "Fleet", "options": ["allow", "deny"]}}))
        if interim is not None:
            interim()
        if not slot["event"].wait(timeout):
            return "timeout"
        answer = slot.get("answer")
        if isinstance(answer, dict):
            answer = next(iter(answer.values()), None)
        return str(answer or "").strip().lower()
    finally:
        waiters.pop(rid, None)


def _read(handle, cmd: str, share: str, fields: Optional[dict] = None) -> dict:
    if cmd == "capabilities":  # 3.0.6.0 R6: read-only; the cache, refreshed when stale or asked
        from halo_harness.fleet import capabilities
        return capabilities.current(refresh_now=(fields or {}).get("refresh") is True)
    if cmd == "doctor":  # 3.0.5.0 R4: read-only, nothing written (fleet/health.py)
        from halo_harness.fleet.health import cached, subset
        return cached("doctor", subset)[0]
    if cmd == "agents":
        rows = _agent_cmd(handle, "agents").get("agents") or []
        return {"agents": [protocol.scrub_agent(r, share) for r in rows]}
    return protocol.scrub_session(handle.status())


def _full(handle, cmd: str, fields: dict, by: str, via: str) -> dict:
    if cmd == "tail":
        n = fields.get("n") if isinstance(fields.get("n"), int) else 20
        return {"markdown": handle.tail(max(1, min(n, 200)))}
    if cmd == "agent_tail":
        return _agent_cmd(handle, "agent_tail", **{k: fields[k] for k in ("agent_id", "n", "kinds") if k in fields})
    return _agent_cmd(handle, "agent_follow", agent_id=fields.get("agent_id"), on=fields.get("on", True) is not False,
                      by=by, via=via)


def _act(handle, cmd: str, fields: dict, by: str, via: str) -> dict:
    if cmd == "interrupt":
        _record(handle, cmd="interrupt", by=by, via=via)
        return handle.interrupt()
    if cmd == "steer":
        cmd, fields = "agent_steer", {"agent_id": "main", "text": fields.get("text"), "mode": "nudge"}
    keep = {"agent_steer": ("agent_id", "text", "mode", "handoff"), "agent_stop": ("agent_id", "reason"),
            "pause": ("agent_id", "reason"), "resume": ("agent_id",), "shutdown": ("reason",)}[cmd]
    return _agent_cmd(handle, cmd, by=by, via=via, **{k: fields[k] for k in keep if fields.get(k) is not None})


def _answer(handle, fields: dict, pol: dict) -> dict:
    if pol["allow_control"] != "all" or not pol["allow_answers"]:
        raise Refused("cards on this harness are answered on this harness, not from a hub "
                      "(that takes fleet.allow_control: all and fleet.allow_answers: true)")
    req = {k: fields[k] for k in ANSWER_KEYS if k in fields}
    if any(str(req.get(k) or "").startswith(ASK_PREFIX) for k in ("request_id", "target", "id")):
        raise Refused("a hub never answers the card that asks about its own command")
    req.update(scope="once", rule="")
    from halo_harness.remote.protocol import _answer as answer_card
    return answer_card(handle, req)


def run(handle, msg: dict, pol: dict, interim: Optional[Callable] = None) -> dict:
    """`{state: done, result}` | `{state: refused | error, error}` for one command doc."""
    cmd = str(msg.get("cmd") or "")
    fields = msg.get("fields") if isinstance(msg.get("fields"), dict) else {}
    by, hub = _clean(msg.get("by")) or "someone", _clean(msg.get("hub")) or "a hub"
    via = f"hub {hub}"
    try:
        if cmd not in protocol.FLEET_CMDS:
            raise Refused(f"{cmd!r} is not a fleet command")
        if cmd in protocol.READ_CMDS:
            return {"state": "done", "result": _read(handle, cmd, pol["share"], fields)}
        if cmd in protocol.RECALL_CMDS:  # 3.1.2.0 R3: this box's own index answers; only the hits leave it
            from halo_harness import recall_fleet
            from halo_harness.orchestra import coach_library_share  # 3.1.6.0 R3: one entry of the coach library
            try:
                from halo_harness.knowledge import share as knowledge_share  # 3.1.8.0 R4: findings and decisions
                answer = {"recall": recall_fleet.answer, "knowledge": knowledge_share.answer}.get(cmd, coach_library_share.answer)
                return {"state": "done", "result": answer(fields, by=by, hub=hub)}
            except recall_fleet.Shut as e:
                raise Refused(str(e)) from None
        if cmd in protocol.FULL_CMDS:
            if pol["share"] != "full":
                raise Refused(f"this harness shares `{pol['share']}` with {hub}; {cmd} needs share full")
            return {"state": "done", "result": _full(handle, cmd, fields, by, via)}
        if cmd == "answer":
            return {"state": "done", "result": _answer(handle, fields, pol)}
        level, me = pol["allow_control"], identity.fleet_name()
        if level == "none":
            raise Refused(f"control from a hub is off on {me} (fleet.allow_control: none)")
        if cmd == "note":  # 3.0.5.0 R4: a message from Fleet's People panel: the owner reads it, nothing runs
            from halo_harness.remote.protocol import _message
            return {"state": "done", "result": _message(handle, {"text": fields.get("text"), "by": by})}
        if cmd == "run_task":  # 3.2.0.0 R4: a part whose pack does not run here is refused before anyone is asked
            from halo_harness.fleet.mission_worker import TaskError, pack_check
            try:
                pack_check(fields, cwd=getattr(handle, "cwd", None), home=identity.home())
            except TaskError as e:
                raise Refused(str(e)) from None
        if level == "ask":
            if getattr(handle, "controller", None) is None:
                raise Refused(f"{me}'s {getattr(handle, 'kind', 'print')} session has no one to ask, so a hub's "
                              f"{cmd} is denied under fleet.allow_control: ask (all applies it)")
            cid = ("mission-" if cmd == "run_task" else "") + str(msg.get("cid") or "x")  # R7: a mission_ask row
            said = ask_owner(handle, describe(handle, cmd, fields, by, hub), cid, interim)
            if said != "allow":
                raise Refused(f"no answer from {me}'s owner in {int(ASK_TIMEOUT_S)} s; denied" if said == "timeout"
                              else f"{me}'s owner denied the {cmd} from {by}")
            handle._note(f"allowed {cmd} from {by} on {hub}")
        if cmd == "run_task":
            from halo_harness.fleet.mission_worker import accept
            return {"state": "done", "result": accept(handle, fields, by=by, hub=hub, entry=pol.get("hub_entry"))}
        if cmd in protocol.MODEL_CMDS:  # 3.3.5.0 R1 (fleet/control_models.py): this machine's own host only
            from halo_harness.fleet import control_models
            try:
                return {"state": "done", "result": control_models.run({**fields, "cmd": cmd})}
            except ValueError as e:
                raise Refused(str(e)) from None
        return {"state": "done", "result": _act(handle, cmd, fields, by, via)}
    except Refused as e:
        _record(handle, cmd=cmd, by=by, via=via, refused=str(e))
        handle._note(f"refused {cmd} from {by} on {hub}: {e}")
        return {"state": "refused", "error": str(e)}
    except HandleError as e:
        return {"state": "error", "error": str(e)}
    except Exception as e:  # a bad command must never take the relay down
        return {"state": "error", "error": f"{type(e).__name__}: {e}"}
