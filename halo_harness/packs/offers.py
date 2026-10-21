"""halo_harness.packs.offers -- the names a pack offers, by kind (Halo
3.2.0.0 R1): what `halo pack list` counts, `halo pack inspect` lists and
packs/conflicts.py compares.

    offers(pack) -> {"bios": ["doc-review--reviewer", ...], "lineups": [...],
                     "agents": ["doc-helper"], "skills": ["doc-review:check-links"],
                     "commands": ["doc-review:review"], "mcp": ["plugin_doc-review_lint"],
                     "hooks": ["PostToolUse"]}

Each list is read from the pack's folder the way the session reads it (the
plugin layout's own discovery for skills, commands, agents, hooks and MCP).
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.packs import names as N

KINDS = ("bios", "lineups", "agents", "skills", "commands", "mcp", "hooks")
LABELS = {"bios": ("bio", "bios"), "lineups": ("lineup", "lineups"), "agents": ("agent", "agents"),
          "skills": ("skill", "skills"), "commands": ("command", "commands"),
          "mcp": ("MCP server", "MCP servers"), "hooks": ("hook event", "hook events")}


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def offers(pack) -> "dict[str, list[str]]":
    from halo_harness.packs.contribute import folder_names
    root = Path(pack.root)
    source = N.pack_source(pack.id)
    out = {"bios": sorted(folder_names(root / "agents", source)),
           "lineups": sorted(folder_names(root / "teams", source, skip=".team.yaml"))}

    def agents():
        from halo_harness.config.agents_md import _load_dir_agents
        return sorted(_load_dir_agents(root / "agents", source=f"plugin:{root}"))

    def skills():
        from halo_harness.commands.skills import _discover_skills_tree
        return sorted(c.name for c in _discover_skills_tree(root / "skills", exclude_synced=False, name_prefix=pack.id))

    def commands():
        from halo_harness.commands.custom import _discover_dir
        return sorted(c.name for c in _discover_dir(root / "commands", source="plugin", name_prefix=pack.id))

    def mcp():
        from halo_harness.config.plugins import plugin_server_name
        from halo_harness.packs.manifest import mcp_servers
        return sorted(plugin_server_name(pack.id, s) for s in mcp_servers(root))

    def hooks():
        from halo_harness.hooks import load_plugin_hooks
        return sorted(load_plugin_hooks(root))

    for kind, fn in (("agents", agents), ("skills", skills), ("commands", commands), ("mcp", mcp), ("hooks", hooks)):
        out[kind] = _safe(fn, [])
    return out


def summary(found: dict) -> str:
    """`2 bios, 1 lineup, 1 skill, ...`, or `nothing`."""
    parts = []
    for kind in KINDS:
        n = len(found.get(kind) or [])
        if n:
            one, many = LABELS[kind]
            parts.append(f"{n} {one if n == 1 else many}")
    return ", ".join(parts) or "nothing"
