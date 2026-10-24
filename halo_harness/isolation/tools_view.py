"""halo_harness.isolation.tools_view -- `/tools` (Halo 3.1.8.0 R5): the tools this session's agent sees.

One line per capability (isolation/capabilities.py's table) with the tool
names in it, then which lineup or bio narrowed the list ("tools: read,
edit, bash (by lineup ci)"), or that nothing did. The same line is the
agent row's in Studio's Agent panel.
"""

from __future__ import annotations


def tools_text(names, opt_ins=None) -> str:
    from halo_harness.isolation.capabilities import CAPABILITIES, capability_of
    groups: dict = {}
    for name in sorted(names):
        groups.setdefault(capability_of(name), []).append(name)
    order = [c for c in CAPABILITIES if c in groups] + sorted(c for c in groups if c not in CAPABILITIES)
    lines = [f"{len(list(names))} tools this session's agent sees:"]
    lines += [f"  {cap:<14} {', '.join(groups[cap])}" for cap in order]
    narrowed = [ln for ln in opt_ins or [] if str(ln).startswith("tools:")]
    lines.append(f"Narrowed to {narrowed[0]}" if narrowed else
                 "Nothing narrows the list (tools.capabilities on a lineup or bio does: docs/ISOLATION.md).")
    lines += [str(ln) for ln in opt_ins or [] if not str(ln).startswith("tools:")]
    return "\n".join(lines)


def tools_command(args: str, facade) -> str:
    session = getattr(facade, "session", None)
    registry = getattr(session, "tool_registry", None) or getattr(facade, "tool_registry", None)
    names = registry.names() if registry is not None else []
    return tools_text(names, getattr(session, "opt_ins", None))
