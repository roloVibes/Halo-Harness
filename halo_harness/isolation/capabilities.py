"""halo_harness.isolation.capabilities -- `tools.capabilities` (Halo 3.1.8.0 R5).

A lineup (whole: `tools.capabilities`; per tier: `tiers[i].tools.capabilities`;
per member: `agents[i].tools.capabilities`) or a bio (`tools.capabilities`)
names the capabilities its agent may use. `TABLE` maps every tool name in
the registry to one capability; an MCP tool `mcp__<server>__<tool>` (and a
claude.ai connector `connector__<slug>`) is `mcp:<server>`; any other name
is `other`. An agent whose lineup or bio declares the list is built with
only the tools of those capabilities (the registry is narrowed before the
model sees the tool list); no list = every tool, as before. The list only
ever narrows: `tools.allow`/`deny`, `--disallowedTools`, deny rules and the
permission mode still apply to what is left.

Which list wins, nearest first: the member's card, its tier, its bio, the
lineup's own. The label says where it came from: "by lineup <name>" or
"by bio <name>".
"""

from __future__ import annotations

import os
from typing import Optional

CAPABILITIES = ("read", "edit", "bash", "web", "agent", "mcp", "media", "recall", "other")
TABLE = {
    "read": ("Read", "Glob", "Grep"),
    "edit": ("Edit", "Write", "NotebookEdit", "OrchestraClaim", "OrchestraClaims", "OrchestraRelease", "OrchestraNote"),
    "bash": ("Bash", "BashOutput", "PowerShell", "TaskStop"),
    "web": ("WebFetch", "WebSearch"),
    "agent": ("Agent", "Task", "TaskCreate", "TaskList", "TaskUpdate"),
    "mcp": ("ToolSearch", "ListMcpResourcesTool", "ReadMcpResourceTool"),
    "media": ("Media",),
    "recall": ("Skill", "TodoWrite"),
}
_BY_TOOL = {tool: cap for cap, tools in TABLE.items() for tool in tools}
CAPS_ENV, CAPS_BY_ENV = "HALO_TOOLS_CAPS", "HALO_TOOLS_CAPS_BY"  # a worker's list, set by its run (isolation/lane.py)
OPT_INS_ENV = "HALO_OPT_INS"  # the run's report lines for that worker (names only), one per line


def _norm(cap: str) -> str:
    if not cap.startswith("mcp:"):
        return cap
    from halo_harness.mcp.manager import sanitize_name
    return "mcp:" + sanitize_name(cap[4:].strip())


def capability_of(name: str) -> str:
    """The one capability a tool name belongs to (`mcp:<server>` for an MCP or connector tool)."""
    if name.startswith("mcp__"):
        return "mcp:" + name[5:].split("__", 1)[0]
    if name.startswith("connector__"):
        return _norm("mcp:" + name[len("connector__"):])
    return _BY_TOOL.get(name, "other")


def allowed(name: str, caps) -> bool:
    cap, wanted = capability_of(name), {_norm(c) for c in caps or ()}
    if cap.startswith("mcp:"):
        return "mcp" in wanted or cap in wanted
    if cap == "mcp":  # ToolSearch and the resource tools: any MCP entry keeps them
        return any(c == "mcp" or c.startswith("mcp:") for c in wanted)
    return cap in wanted


def filter_names(names, caps) -> list:
    return [n for n in names if allowed(n, caps)]


def problems(caps, where: str) -> "list[str]":
    """One line per entry that is not a capability; [] when valid or absent."""
    if caps is None:
        return []
    if not isinstance(caps, list) or not all(isinstance(c, str) and c.strip() for c in caps):
        return [f'"{where}" must be a list of {", ".join(CAPABILITIES)} or mcp:<server>']
    return [f'"{where}" {c!r} is not one of {", ".join(CAPABILITIES)} or mcp:<server>' for c in caps
            if c not in CAPABILITIES and not (c.startswith("mcp:") and c[4:].strip())]


def caps_of(section) -> Optional[list]:
    """`section.capabilities` as a list of strings, or None when not declared."""
    caps = section.get("capabilities") if isinstance(section, dict) else None
    return [str(c).strip() for c in caps if str(c).strip()] if isinstance(caps, list) else None


def line(caps, by: str) -> str:
    """'tools: read, edit, bash (by bio reviewer)'."""
    return f"tools: {', '.join(caps) or '(none)'}" + (f" (by {by})" if by else "")


def _key(entry: dict) -> Optional[str]:
    alias = entry.get("as")
    return alias if isinstance(alias, str) and alias else entry.get("role")


def _tier_tools(template: dict, alias: Optional[str]):
    tiers = template.get("tiers") if isinstance(template.get("tiers"), list) else []
    for tier in tiers:
        if isinstance(tier, dict) and alias and alias in (tier.get("members") or []):
            return tier.get("tools")
    return None


def resolve(template: Optional[dict], lineup: str, alias: Optional[str], bio: Optional[dict],
            bio_name: str = "") -> "tuple[Optional[list], str]":
    """`(caps, by)` for one member: its card, its tier, its bio, the lineup's own; `(None, "")` when none declares."""
    template = template if isinstance(template, dict) else {}
    agents = [e for e in template.get("agents") or [] if isinstance(e, dict)]
    entry = next((e for e in agents if alias and _key(e) == alias), None) or {}
    bio_by = f"bio {bio_name or (bio or {}).get('name') or '?'}"
    for source, by in ((entry.get("tools"), f"lineup {lineup}"), (_tier_tools(template, alias), f"lineup {lineup}"),
                       ((bio or {}).get("tools"), bio_by), (template.get("tools"), f"lineup {lineup}")):
        caps = caps_of(source)
        if caps is not None:
            return caps, by
    return None, ""


def narrow(registry, caps, catalog=None) -> "list[str]":
    """Remove, in place, every tool of `registry` (and of the session catalog's registry, wire names and
    deferred pool) whose capability is not in `caps`. The names removed."""
    removed = [n for n in registry.names() if not allowed(n, caps)]
    for n in removed:
        registry.remove_tool(n)
    if catalog is not None:
        if getattr(catalog, "registry", None) is not None and catalog.registry is not registry:
            for n in [n for n in catalog.registry.names() if not allowed(n, caps)]:
                catalog.registry.remove_tool(n)
        catalog.names[:] = [n for n in catalog.names if allowed(n, caps)]
        for n in [n for n in list(catalog.deferred) if not allowed(n, caps)]:
            catalog.deferred.pop(n, None)
    return removed


def _main_of(name: str, cwd) -> "tuple[Optional[list], str]":
    from halo_harness.agents_yaml import resolve_agent_bio
    from halo_harness.teams_tiers import main_key
    from halo_harness.teams_yaml import resolve_team_template
    template = resolve_team_template(name, cwd=cwd)
    if not template:
        return None, ""
    entry = next((e for e in template.get("agents") or [] if isinstance(e, dict) and e.get("role") == "main"), {})
    bio = resolve_agent_bio(entry.get("agent"), cwd=cwd) if entry.get("agent") else None
    return resolve(template, name, main_key(template.get("agents")), bio, entry.get("agent") or "")


def session_caps(*, team: Optional[str], agent: Optional[str], cwd=None, env=None) -> "tuple[Optional[list], str]":
    """The top session's list: an Orchestra worker's comes from its run (CAPS_ENV); else the lineup's main
    (card, tier, bio, lineup), else the `--agent` bio's. Never raises."""
    env = os.environ if env is None else env
    try:
        from halo_harness.orchestra.workers import LANE_ENV
        if env.get(LANE_ENV):
            raw = env.get(CAPS_ENV)
            return ([c for c in raw.split(",") if c], env.get(CAPS_BY_ENV, "")) if raw is not None else (None, "")
        from halo_harness.teams_runtime import active_team_name
        name = active_team_name(team)
        caps, by = _main_of(name, cwd) if name else (None, "")
        if caps is not None:
            return caps, by
        if agent:
            from halo_harness.agents_yaml import resolve_agent_bio
            caps = caps_of((resolve_agent_bio(agent, cwd=cwd) or {}).get("tools"))
            if caps is not None:
                return caps, f"bio {agent}"
    except Exception:
        return None, ""
    return None, ""


def narrow_session(registry, catalog, *, team: Optional[str], agent: Optional[str], cwd=None) -> "list[str]":
    """build_session's one call: narrow the top session's tools; the opt-in lines its agent row shows."""
    caps, by = session_caps(team=team, agent=agent, cwd=cwd)
    lines = [ln for ln in os.environ.get(OPT_INS_ENV, "").split("\n") if ln.strip() and not ln.startswith("tools:")]
    if caps is None:
        return lines
    narrow(registry, caps, catalog)
    return lines + [line(caps, by)]


def narrow_member(registry, team_control, alias: Optional[str]):
    """A sub-agent under a lineup: `(registry, opt-in lines or None)`, the member's list applied in place."""
    if team_control is None:
        return registry, None
    try:
        entry = team_control.assignment_for(alias) or {}
        caps, by = resolve(team_control.template, team_control.name, alias, team_control.bio_for(alias),
                           entry.get("agent") or "")
    except Exception:
        return registry, None
    if caps is None:
        return registry, None
    narrow(registry, caps)
    return registry, [line(caps, by)]


def children_line(lineup: Optional[str], holder=None) -> str:
    """The Agent tool description's sentence: what each member of the lineup may use ('' when none declares)."""
    cached = getattr(holder, "_caps_children", None)
    if cached is not None and cached[0] == lineup:
        return cached[1]
    text = ""
    try:
        from halo_harness.agents_yaml import resolve_agent_bio
        from halo_harness.teams_yaml import resolve_team_template
        template = resolve_team_template(lineup) if lineup else None
        parts = []
        for e in [e for e in (template or {}).get("agents") or [] if isinstance(e, dict) and e.get("role") != "main"]:
            caps, _by = resolve(template, lineup, _key(e), resolve_agent_bio(e["agent"]) if e.get("agent") else None)
            if caps is not None:
                parts.append(f"{_key(e)}: {', '.join(caps) or '(none)'}")
        if parts:
            text = f" Under lineup {lineup} each member sees only the tools of its capabilities: {'; '.join(parts)}."
    except Exception:
        text = ""
    if holder is not None:
        try:
            holder._caps_children = (lineup, text)
        except Exception:
            pass
    return text
