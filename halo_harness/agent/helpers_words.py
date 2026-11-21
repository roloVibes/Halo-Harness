"""halo_harness.agent.helpers_words -- what main is told about handing work out, on Auto (3.6.0.10 MW, rules M4, M6, M7):

    on_auto(session) -> bool        a top session on Auto that may hand work out (else today's line, byte for byte)
    frozen(session) -> str | None   M1 and M2: when to hand work out, the kinds THIS session can start (his own first),
                                    made at the session's first shaping and kept byte-equal; made again only when
                                    main's model changes. None: not on Auto, or the block does not fit (today's line).
    tail(session, tools) -> str     per request, after the tools are capped (agent/prompt_wire.py): M3 when the request
                                    sends the Workflow tool and it lists his workflows, M4 when it sends the Builder

The lean system text (agent/prompt_lean_system.py) writes `frozen` in place of today's delegate line. The frozen part
names no tool but Agent, which every request that sends a tool sends. No tool's own words change here (A3), and
nothing here changes which tools go out (A2).
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
M3 = "- The Workflow tool lists workflows you can run by `name`: run one when it fits the whole job."
M4 = ("- Unasked, you may propose a helper or a workflow for work that will come back, with the Builder tool; nothing "
      "is written until the person approves its card.")
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
    return "\n\n" + M3 + "\n" + M4


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


def tail(session, tools) -> str:
    """The lines for THIS request's tools (after the cap), "" when none apply or the session reads today's line."""
    if not tools or frozen(session) is None:
        return ""
    sent = {t.get("name") for t in tools if isinstance(t, dict)}
    lines = []
    if "Workflow" in sent:
        from halo_harness.crew.flow_door import tail as flows
        if flows():
            lines.append(M3)
    if "Builder" in sent:
        lines.append(M4)
    return "\n\n" + "\n".join(lines) if lines else ""
