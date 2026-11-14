"""halo_harness.crew.map_session -- what the session builder does with the map in use (Halo 3.6.0.0 R3).

`headless.build_session` (the one builder: print mode, the terminal, Studio's sessions) calls these when no `--agent`
and no bare session:

    prepare(cli_flags, cwd) -> (Compiled | None, lines)   the map (`--map`, config `crew.map`) compiled; a map with a
                                                          problem gives None and its problem lines (said on stderr;
                                                          the session runs as with no map)
    model(c) -> str | None                                main's model (None: `auto`, the session's own, as today)
    instructions(c) -> str                                main's instructions, added to the system prompt
    narrow(registry, catalog, c)                          main's tools: the kinds its `uses` does not list are taken
                                                          out (read / edit / bash / web); every other tool stays;
                                                          Agent / Task only with an agent to hand to, Workflow only with
                                                          a workflow to hand to
    agents(discovered, c) -> (agents, restriction)        the map's agent specs over the discovered ones; the Agent tool
                                                          may spawn exactly main's agents
With no map in use, nothing here changes anything: the session runs exactly as before 3.6.0.0 R3.
"""

from __future__ import annotations

from typing import Optional

KINDS = {"read": ("Read", "Glob", "Grep"), "edit": ("Edit", "Write", "NotebookEdit"),
         "bash": ("Bash", "PowerShell", "BashOutput", "TaskStop"), "web": ("WebFetch", "WebSearch")}


def prepare(cli_flags: Optional[dict], cwd) -> "tuple[object, list]":
    from halo_harness.crew.compile import for_session
    try:
        return for_session((cli_flags or {}).get("map"), cwd=cwd)
    except Exception as e:  # a compile bug never stops a session: it runs as with no map, and says why
        return None, [f"halo: the map could not be read ({type(e).__name__}: {e}), so this session runs as with no map"]


def model(c) -> Optional[str]:
    return (c.main or {}).get("model") if c is not None else None


def instructions(c) -> str:
    text = str((c.main or {}).get("instructions") or "").strip() if c is not None else ""
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


def agents(discovered: dict, c) -> "tuple[dict, set]":
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
