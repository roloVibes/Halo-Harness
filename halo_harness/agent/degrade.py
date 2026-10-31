"""halo_harness.agent.degrade -- Halo 3.3.6.0 R4: the degradation ladder
(plans/local-model-fit-brief.md Part G10): when a local model fails, one
explicit pass down the rungs, each rung one visible line, never a loop.

    rungs() -> the ordered list (`local.ladder`; default RUNGS; "off" or [] -> none)
    step(session, turn_no, trigger, body=None) -> a generator of events; returns the action or None
        {"rung", "do": "note" | "rebuild" | "stop", "note"?}   None: the ladder is off or this turn's pass is spent
    ledger_rungs(session) -> this turn's rungs taken [{rung, trigger, line}] | None   (the ledger line's `ladder`)
    note_body(body, note) -> body with one more user message (the repair rung's re-ask)
    midturn(session, turn_no) -> a generator: the `tool_failures` trigger between tool rounds

The rungs, in the default order:
    repair       the dialect's repair loop: the call asked once more with what was wrong (an empty reply, no
                 JSON); for bad tool arguments the repair round already is this rung
    smaller-ask  one re-send with the lean profile and the tool budget's top tools (SMALL_TOOLS)
    other-local  placement's nearest probed model with tools that shares the card with the resident one
                 (its profile's co_resides_with), else any other probed one, through the switch step
    cloud        only when `routing.escalation` (agent/escalation.py's policy) allows: its `to`, its triggers
                 (a trigger outside `when` or `ask: true` makes it the next rung); never a second policy
    ask          one question to the user with what was tried; the turn ends there
Triggers: `local_failure`'s empty reply and no-tools reply, the server log's cut twice and crash
(agent/ollama_log_recovery.py), escalation's low_confidence / tool_failures / context_overflow. One pass per
turn: a rung is taken at most once a turn, the next failure takes the next rung, and after the last nothing
more is tried. The worst case adds four calls to a turn (repair, a smaller ask, another local model, cloud).
"""

from __future__ import annotations

import logging
from typing import Optional

from halo_harness import events

log = logging.getLogger("bridge")

RUNGS = ("repair", "smaller-ask", "other-local", "cloud", "ask")
TRIGGERS = ("empty", "no-tools", "no-json", "cut-twice", "crash", "low_confidence", "tool_failures", "context_overflow")
REPAIRABLE = ("empty", "no-json")
SMALL_TOOLS = 6
NOTES = {"empty": "Your last reply was empty. Answer now, in plain text (or with one tool call).",
         "no-json": "Your last reply did not parse as JSON. Reply with the JSON object only, no prose, no fence."}
WORDS = {"empty": "an empty reply", "no-tools": "no tool call from a model without tool calling",
         "no-json": "a reply that did not parse", "cut-twice": "the prompt cut twice", "crash": "the server crashed",
         "low_confidence": "an unsure answer", "tool_failures": "two failed tool calls",
         "context_overflow": "the window overflowed"}


def rungs() -> list:
    try:
        from halo_harness.theme import get_config_value
        raw = get_config_value("local.ladder", default=None)
    except Exception:
        raw = None
    if raw is None:
        return list(RUNGS)
    if raw is False or (isinstance(raw, str) and raw.strip().lower() in ("off", "none", "")):
        return []
    items = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
    out = [str(x).strip().lower() for x in items if str(x).strip().lower() in RUNGS]
    return [] if any(str(x).strip().lower() == "off" for x in items) else list(dict.fromkeys(out))


def _pass(session, turn_no) -> dict:
    p = getattr(session, "_ladder_pass", None)
    if not isinstance(p, dict) or p.get("turn") != turn_no:
        p = {"turn": turn_no, "i": 0, "taken": [], "small": False}
        session._ladder_pass = p
    return p


def ledger_rungs(session) -> Optional[list]:
    p = getattr(session, "_ladder_pass", None)
    if not isinstance(p, dict) or p.get("turn") != getattr(session, "turn_count", None) or not p.get("taken"):
        return None
    return [{k: t.get(k) for k in ("rung", "trigger", "line")} for t in p["taken"]]


def small_ask(session) -> bool:
    """The smaller-ask rung is in force for this turn (agent/prompt_lean.py reads it: lean on, SMALL_TOOLS)."""
    p = getattr(session, "_ladder_pass", None)
    return isinstance(p, dict) and p.get("small") and p.get("turn") == getattr(session, "turn_count", None)


def note_body(body: dict, note: str) -> dict:
    out = dict(body or {})
    out["messages"] = list(out.get("messages") or []) + [{"role": "user", "content": note}]
    return out


def _other_local(session) -> Optional[str]:
    from halo_harness.providers.ollama import ollama_names_match
    from halo_harness.providers.placement import profile_for_ref, with_tools
    ref = getattr(session, "model_ref", None)
    me = getattr(ref, "model", "") or ""
    cands = [r for r in with_tools(getattr(session, "state_dir", None)) if not ollama_names_match(
        r.split(":", 1)[-1].rsplit("@", 1)[0], me)]
    mine = profile_for_ref(ref, getattr(session, "state_dir", None)) or {}
    beside = (mine.get("resident") or {}).get("co_resides_with") or []
    near = [r for r in cands if any(ollama_names_match(r.split(":", 1)[-1].rsplit("@", 1)[0], b) for b in beside)]
    return (near or cands or [None])[0]


def _cloud(session, trigger: str) -> "tuple[Optional[str], str]":
    """(the policy's `to` when it allows this trigger now, else None; the reason)."""
    from halo_harness.agent.escalation import load_escalation_policy, role_escalation_enabled
    policy = load_escalation_policy()
    if policy is None:
        return None, "no routing.escalation policy"
    table = getattr(getattr(session, "agent_runtime", None), "role_table", None)
    if not role_escalation_enabled(getattr(session, "role_name", None), table):
        return None, "this role's escalation is off"
    if trigger in ("low_confidence", "tool_failures", "context_overflow") and trigger not in policy.when:
        return None, f"routing.escalation.when has no {trigger}"
    if policy.ask:
        return None, f"routing.escalation asks first (switch by hand: /model {policy.to})"
    return policy.to, ""


def _switch(session, to: str, turn_no: int):
    from halo_harness.agent.preflight import _switch as switch_via_step
    yield from switch_via_step(session, to, turn_no)


def step(session, turn_no: int, trigger: str, body: Optional[dict] = None):
    order = rungs()
    if not order:
        return None
    p = _pass(session, turn_no)
    while p["i"] < len(order):
        rung = order[p["i"]]
        p["i"] += 1
        n = p["i"]
        act, line = None, ""
        if rung == "repair":
            if trigger not in REPAIRABLE:
                continue
            act, line = {"do": "note", "note": NOTES[trigger]}, f"rung {n}: repair -- asked again: {NOTES[trigger].lower()}"
        elif rung == "smaller-ask":
            before = len((body or {}).get("tools") or [])
            p["small"] = True
            act = {"do": "rebuild"}
            line = (f"rung {n}: a smaller ask -- {min(before, SMALL_TOOLS)} tools instead of {before}, the lean prompt"
                    if before else f"rung {n}: a smaller ask -- the lean prompt")
        elif rung == "other-local":
            alt = _other_local(session)
            if not alt:
                yield events.turn_marker("ladder", f"↳ rung {n}: another local model -- none probed with tools here; "
                                                   "next rung", turn=turn_no)
                p["taken"].append({"rung": rung, "trigger": trigger, "line": "none probed with tools", "skipped": True})
                continue
            line = f"rung {n}: another local model -- {alt}"
            yield events.turn_marker("ladder", f"↳ {line}", turn=turn_no)
            try:
                yield from _switch(session, alt, turn_no)
            except Exception:
                log.debug("degrade: the switch to %s failed", alt, exc_info=True)
                continue
            p["taken"].append({"rung": rung, "trigger": trigger, "line": line})
            return {"rung": rung, "do": "rebuild"}
        elif rung == "cloud":
            to, why = _cloud(session, trigger)
            if not to:
                yield events.turn_marker("ladder", f"↳ rung {n}: cloud -- not taken: {why}", turn=turn_no)
                p["taken"].append({"rung": rung, "trigger": trigger, "line": f"not taken: {why}", "skipped": True})
                continue
            line = f"rung {n}: cloud -- {to} (routing.escalation)"
            yield events.turn_marker("ladder", f"↳ {line}", turn=turn_no)
            try:
                yield from _switch(session, to, turn_no)
            except Exception:
                log.debug("degrade: the switch to %s failed", to, exc_info=True)
                continue
            p["taken"].append({"rung": rung, "trigger": trigger, "line": line})
            return {"rung": rung, "do": "rebuild"}
        elif rung == "ask":
            did = ", ".join(t["rung"] for t in p["taken"] if not t.get("skipped")) or "nothing else"
            line = (f"rung {n}: ask -- {WORDS.get(trigger, trigger)} on {getattr(session.model_ref, 'raw', 'this model')}; "
                    f"tried {did}. What next: another model (/model), a smaller task, or go on as it is?")
            p["taken"].append({"rung": rung, "trigger": trigger, "line": line})
            yield events.error(line, turn=turn_no, err_type="local_model")
            return {"rung": rung, "do": "stop"}
        if act is not None:
            p["taken"].append({"rung": rung, "trigger": trigger, "line": line})
            yield events.turn_marker("ladder", f"↳ {line}", turn=turn_no)
            return {"rung": rung, **act}
    return None


def midturn(session, turn_no: int):
    """`tool_failures` between tool rounds: a rung is taken once the turn's failures reach the threshold again."""
    from halo_harness.agent.escalation import TOOL_FAILURE_THRESHOLD, count_tool_failures_since
    from halo_harness.model import is_local_model_ref
    if not is_local_model_ref(getattr(session, "model_ref", None)) or not rungs():
        return
    n = count_tool_failures_since(session.log.nodes(), getattr(session, "_turn_log_start_idx", 0))
    p = _pass(session, turn_no)
    if n < TOOL_FAILURE_THRESHOLD * (1 + p.get("fail_steps", 0)):
        return
    p["fail_steps"] = p.get("fail_steps", 0) + 1
    act = yield from step(session, turn_no, "tool_failures", None)
    if act and act["do"] == "stop":
        session._ladder_stop = True
