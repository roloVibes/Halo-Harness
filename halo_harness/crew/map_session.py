"""halo_harness.crew.map_session -- what the session builder does with the map in use (Halo 3.6.0.0 R3).

`headless.build_session` (the one builder: print mode, the terminal, Studio's sessions) calls these when no `--agent`
and no bare session:

    prepare(cli_flags, cwd) -> (Compiled | None, lines)   the map (`--map`, config `crew.map`) compiled; a map with a
                                                          problem gives its problem lines (said on stderr) and the
                                                          `starter` map instead (3.6.0.0 R5: every session is on a map)
    model(c) -> str | None                                main's model (None: `auto`, the session's own, as today)
    instructions(c) -> str                                main's instructions, added to the system prompt
    narrow(registry, catalog, c)                          main's tools: the kinds its `uses` does not list are taken
                                                          out (read / edit / bash / web); every other tool stays;
                                                          Agent / Task only with an agent to hand to, Workflow only with
                                                          a workflow to hand to
    agents(discovered, c) -> (agents, restriction)        the map's agent specs over the discovered ones; the Agent tool
                                                          may spawn exactly main's agents
With no map set, the session runs on the shipped `starter` map (crew/compile.py DEFAULT_MAP, 3.6.0.0 R5) as a drawing
(crew/compile.py is_default): no model or instructions from its main, no tool taken out, every discovered agent kept
and winning over a starter agent of the same name.
"""

from __future__ import annotations

import dataclasses
from typing import Optional

from halo_harness.crew.compile import is_default

KINDS = {"read": ("Read", "Glob", "Grep"), "edit": ("Edit", "Write", "NotebookEdit"),
         "bash": ("Bash", "PowerShell", "BashOutput", "TaskStop"), "web": ("WebFetch", "WebSearch")}


def prepare(cli_flags: Optional[dict], cwd) -> "tuple[object, list]":
    from halo_harness.crew.compile import for_session
    try:
        return for_session((cli_flags or {}).get("map"), cwd=cwd)
    except Exception as e:  # a compile bug never stops a session: it runs as with no map, and says why
        return None, [f"halo: the map could not be read ({type(e).__name__}: {e}), so this session runs as with no map"]


def model(c) -> Optional[str]:
    if c is None or is_default(c):
        return None  # the default map: the session's own model, as a plain session
    return (c.main or {}).get("model")


def instructions(c) -> str:
    if c is None or is_default(c):
        return ""  # 3.6.0.0 R5 fix: the default map adds nothing to the system prompt
    text = str((c.main or {}).get("instructions") or "").strip()
    if not text:
        return ""
    return f"Your instructions (the map {c.name}, its main agent {c.main.get('agent')}):\n{text}"


def removed_names(names, c) -> list:
    uses = set((c.main or {}).get("uses") or [])
    out = [n for kind, tools in KINDS.items() if kind not in uses for n in tools if n in names]
    if not c.agent_targets():
        out += [n for n in ("Agent", "Task") if n in names]
    if not c.workflow_targets() and "Workflow" in names:
        out.append("Workflow")
    return out


def narrow(registry, catalog, c) -> list:
    if is_default(c):
        return []  # 3.6.0.0 R5 fix: the default map takes no tool out (Workflow stays, as for a plain session)
    gone = removed_names(registry.names(), c)
    for n in gone:
        registry.remove_tool(n)
    if catalog is not None:
        if getattr(catalog, "registry", None) is not None and catalog.registry is not registry:
            for n in [n for n in gone if catalog.registry.get(n) is not None]:
                catalog.registry.remove_tool(n)
        catalog.names[:] = [n for n in catalog.names if n not in gone]
        for n in gone:
            getattr(catalog, "deferred", {}).pop(n, None)
    return gone


def plain_spec(spec):
    """A starter agent on the default map, as the lineup card it draws: its model from the role table (your
    `halo roles point <role> <model>` wins; else the card's `auto` pick with its bio's needs), its role the card's
    alias, no worktree of its own."""
    from halo_harness.crew.map_control import plain_role
    return dataclasses.replace(spec, model=None, role=plain_role(spec.name), isolation=None)


def agents(discovered: dict, c) -> "tuple[dict, set]":
    if is_default(c):
        # 3.6.0.0 R5 fix (M2): every agent the session discovers stays spawnable and wins over a starter agent of the
        # same name (built-ins, ~/.claude/agents, a project's, a pack's, --agents JSON); the starter's fill in the rest
        merged = {n: plain_spec(sp) for n, sp in c.specs.items()}
        merged.update(discovered or {})
        return merged, set()
    merged = dict(discovered or {})
    merged.update(c.specs)
    # 3.6.0.0 R4: `general-purpose` stays spawnable for the helper main makes up when no line claims a task
    # (crew/map_run.py: a call naming no agent, no When fired); it gets main's own tools and mode, never more.
    return merged, set(c.agent_targets()) | ({"general-purpose"} if "general-purpose" in merged else set())


def line(c) -> str:
    """The one line `/status` and the session's row say: the map in use."""
    return f"Map: {c.name} ({len(c.handoffs)} line{'' if len(c.handoffs) == 1 else 's'} from main)" if c is not None else ""


def tool_tail(mc, kind: str) -> str:
    """What the Agent (`agent`) or Workflow (`workflow`) tool's description adds on a map: each target and its When."""
    from halo_harness.crew.map_when import words
    c = getattr(mc, "map", None)
    if c is None:
        return ""
    bits = []
    for h in c.handoffs:
        if h["kind"] != kind:
            continue
        body = (c.agents if kind == "agent" else c.workflows).get(h["name"]) or {}
        does = str(body.get("does") or body.get("for") or "").strip()[:90]
        bits.append(f"{h['name']} ({words(h['when'])}{'; ' + does if does else ''})")
    if not bits:
        return ""
    key = "subagent_type" if kind == "agent" else "name"
    return (f" This session runs on the map {c.name}: hand {kind} work ({key}) only to these -- {'; '.join(bits)}. "
            "A line that says when routes a call that names no target; the runtime follows the map's chains itself.")
