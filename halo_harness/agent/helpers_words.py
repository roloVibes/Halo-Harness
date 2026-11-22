"""halo_harness.agent.helpers_words -- what main is told about handing work out, on Auto (3.6.0.10 MW, rules M4, M6, M7):

    on_auto(session) -> bool        a top session on Auto that may hand work out (else today's line, byte for byte)
    frozen(session) -> str | None   M1 and M2: when to hand work out, the kinds THIS session can start (his own first),
                                    made at the session's first shaping and kept byte-equal; made again only when
                                    main's model changes. None: not on Auto, or the block does not fit (today's line).
    remind(session) -> str          M10: the line a LOCAL main on Auto reads after the mode line at each task, or ""
    one_shot(session) -> bool       `halo -p` with one prompt: the window ladder sizes its first ask (3.6.0.12 OS:
                                    with the tool block of the window it asks; it reads the block like any session)
    tail(session, tools) -> str     per request, after the tools are capped (agent/prompt_wire.py): M3 when the request
                                    sends the Workflow tool and it lists his workflows; nothing else
    kinds_tail(session) -> str      M8: the end of the Agent and Task tools' words on Auto (their cloud copy)
    told(session) -> dict | None    M9: `kinds_told`, `kinds_more` for the status row (what main read)

The lean system text (agent/prompt_lean_system.py) writes `frozen` in place of today's delegate line. The frozen part
names no tool but Agent, which every request that sends a tool sends. The tail never tells main to propose a helper or a
workflow: those words live in ONE place, the Builder tool's own (tools/builder_tool.py), whose Auto form `on_auto` picks
once at the session's start (crew/session_start.tool_state; MW batch 4, the owner's answer of 2026-11-21).
"""

from __future__ import annotations

from typing import Optional

M1 = ("- Hand work out instead of doing it all yourself: give each part of a job that can run on its own (a search or "
      "survey, a plan, a review, a test run, mechanical edits, a file your model cannot read) to a helper with the Agent "
      "tool; helpers on one job share one `task`; run independent parts in parallel; keep judgement and the final "
      "review yourself.")
M2_HEAD = "- Helpers you can start now (`subagent_type`): "
M2_END = ". With no `subagent_type` Halo picks a kind from your words."
M2_MORE = " and {n} more (a wrong name lists them all)"
KINDS_HEAD = " Helpers you can start (`subagent_type`): "  # M8: the Agent and Task tools' words on Auto (cloud copy)
M3 = "- The Workflow tool lists workflows you can run by `name`: run one when it fits the whole job."
M10 = ("If this job has parts that can run on their own, hand each one to a helper with the Agent tool before you work "
       "on it yourself (one call per part; `subagent_type` names the helper). A small job you do yourself.")
_KEPT = "_helpers_block"  # the session's frozen block: (main's model, the text or None)


def _has(session, name: str) -> bool:
    reg = getattr(session, "tool_registry", None)
    get = getattr(reg, "get", None)
    return True if get is None else get(name) is not None


def on_auto(session) -> bool:
    """A top session (depth 0) on the default map, Auto, with no restriction on the kinds it starts, the Agent tool
    registered, a model that takes tools, and the block not turned off (`_helpers_off`, the gym's "before")."""
    if getattr(session, "_helpers_off", False) or getattr(session, "agent_type_restriction", None) is not None:
        return False
    runtime = getattr(session, "agent_runtime", None)
    if runtime is None or getattr(runtime, "depth", None) != 0:
        return False
    from halo_harness.crew.map_control import PlainMap  # his map, roles off, an `--agent` session: not Auto
    from halo_harness.crew.store import is_auto
    control = getattr(session, "team_control", None)
    if not isinstance(control, PlainMap) or not is_auto(getattr(control, "name", None)) or not _has(session, "Agent"):
        return False
    try:
        from halo_harness.agent.prompt_lean import no_tools
        return not no_tools(session)
    except Exception:
        return True


def longest_tail() -> str:
    return "\n\n" + M3


def one_shot(session) -> bool:
    """A session the window ladder sizes by its prompt: every session that is not marked as taking more turns
    (agent/ollama_window_truth.many_turns, the ladder's OWN rule, asked here so the two can never differ): `halo -p`
    with one prompt (headless.run_print_mode sets `many_turns` False), and any session that sets neither mark. The
    terminal app, and Studio's and remote sessions through the same Controller, mark the session `interactive`;
    `-p --input-format stream-json` sets `many_turns` True. 3.6.0.12 OS: such a session's first ask carries the tool
    block of the window it asks (prompt_wire.one_shot_shaper), so on Auto it reads the same block every session reads."""
    from halo_harness.agent.ollama_window_truth import many_turns
    return not many_turns(session)


def _make(session) -> Optional[str]:
    if not on_auto(session):
        return None
    from halo_harness.agent.prompt_composition import tokens_of
    from halo_harness.crew.kinds import CAP, block, kinds
    rows = kinds(getattr(session.agent_runtime, "agents", None), getattr(session, "agent_type_restriction", None))
    return block(rows, M1, M2_HEAD, M2_END, M2_MORE, CAP - tokens_of(longest_tail()))


def frozen(session) -> Optional[str]:
    model = getattr(getattr(session, "model_ref", None), "raw", None)
    kept = getattr(session, _KEPT, None)
    if isinstance(kept, tuple) and kept[0] == model:
        return kept[1]
    try:
        text = _make(session)
    except Exception:
        text = None
    try:
        setattr(session, _KEPT, (model, text))
    except Exception:
        pass
    return text


def remind(session) -> str:
    """M10 (3.6.0.14 MW2): the line a LOCAL main on Auto reads at every task, after the permission mode line
    (agent/mode_notice.turn_line); "" for everyone else (a cloud main, his map, a helper, the block off or not
    fitting). It follows `frozen`, so it is the same bytes every turn and changes only with main's model."""
    try:
        from halo_harness.model import is_local_ref_string
        if not is_local_ref_string(getattr(getattr(session, "model_ref", None), "raw", None)):
            return ""
        return M10 if on_auto(session) and frozen(session) is not None else ""
    except Exception:
        return ""


def kinds_tail(session) -> str:
    """M8: the end of the Agent and Task tools' words on a top Auto session (set at the start, crew/session_start.py
    `tool_state`, so it is byte-equal for the session): the kinds and the clause, in the room M2's line has in the lean
    block (the same names give way the same way). The lean copy of those tools drops it (tools/lean_descriptions.py)."""
    try:
        if not on_auto(session):
            return ""
        from halo_harness.agent.prompt_composition import tokens_of
        from halo_harness.crew.kinds import CAP, block, kinds
        rows = kinds(getattr(session.agent_runtime, "agents", None), getattr(session, "agent_type_restriction", None))
        room = CAP - tokens_of(longest_tail()) - tokens_of(M1 + "\n")
        return block(rows, None, KINDS_HEAD, M2_END, M2_MORE, room) or ""
    except Exception:
        return ""


def told(session) -> Optional[dict]:
    """M9: the kinds main was told, for the status row (never sent to a model): `kinds_told` the names it read,
    `kinds_more` how many it read as " and {n} more". A lean session's once its block is frozen (its first request);
    a cloud session's from the Agent tool's words (fixed at the start). None when main was told none."""
    try:
        from halo_harness.agent.prompt_lean import active
        lean = active(session)
    except Exception:
        lean = False
    if lean:
        kept = getattr(session, _KEPT, None)
        text = kept[1] if isinstance(kept, tuple) else None
    else:
        reg = getattr(session, "tool_registry", None)
        text = getattr(reg.get("Agent") if reg is not None else None, "kinds_tail", "")
    if not text:
        return None
    import re
    from halo_harness.crew.kinds import kinds, names
    listed = names(kinds(getattr(session.agent_runtime, "agents", None), getattr(session, "agent_type_restriction", None)))
    m = re.search(re.escape(M2_MORE).replace(r"\{n\}", r"(\d+)"), text)
    more = int(m.group(1)) if m else 0
    return {"kinds_told": listed[:len(listed) - more], "kinds_more": more}


def tail(session, tools) -> str:
    """M3 when THIS request (after the cap) sends the Workflow tool and it lists his workflows; "" otherwise, and
    always "" when the session reads today's line."""
    if not tools or frozen(session) is None:
        return ""
    sent = {t.get("name") for t in tools if isinstance(t, dict)}
    if "Workflow" in sent:
        from halo_harness.crew.flow_door import tail as flows
        if flows():
            return "\n\n" + M3
    return ""
