"""halo_harness.packs.conflicts -- one name offered twice (Halo 3.2.0.0 R1).

Two active packs offering the same bio, lineup, skill, command or MCP
server name (after namespacing: `<id>--<name>`, `<id>:<name>`,
`plugin_<id>_<server>`), and a pack offering a bio or lineup name your own
project or home folder already has. Yours is always the one used (the pack
tier comes after the project and home folders); the first pack in run order
wins over a later one. Each clash is one line; nothing is overridden
without one.

    conflict_lines(active_packs, cwd=..., state_dir=...)   # ["bio doc-review--writer: ...", ...]
"""

from __future__ import annotations

from pathlib import Path

_KIND_WORD = {"bios": "bio", "lineups": "lineup", "skills": "skill", "commands": "command", "mcp": "MCP server",
              "agents": "agent"}


def _yours(kind: str, name: str, *, cwd, state_dir) -> str:
    """The path of your own project or home bio/lineup of that name, or ''."""
    from halo_harness import agents_yaml as A
    from halo_harness import teams_yaml as T
    dirs = ([(A.project_agents_dir(cwd), "project"), (A.user_agents_dir(state_dir), "user")] if kind == "bios"
            else [(T.project_teams_dir(cwd), "project"), (T.user_teams_dir(state_dir), "user")])
    for d, _label in dirs:
        p = Path(d) / f"{name}.yaml"
        if p.is_file():
            return str(p)
    return ""


def _user_skill_and_command_names(cwd) -> "dict[str, set[str]]":
    """Skills and commands from your project and home `.claude` folders (no plugins)."""
    out = {"skills": set(), "commands": set()}
    try:
        from halo_harness.commands.skills import discover_all_skills
        out["skills"] = set(discover_all_skills(Path(cwd if cwd is not None else Path.cwd())))
    except Exception:
        pass
    try:
        from halo_harness.commands.custom import _discover_dir
        from halo_harness.config.paths import home
        base = Path(cwd if cwd is not None else Path.cwd())
        for d, src in ((base / ".claude" / "commands", "project"), (home() / ".claude" / "commands", "user")):
            out["commands"] |= {c.name for c in _discover_dir(d, source=src)}
    except Exception:
        pass
    return out


def conflict_lines(active, *, cwd=None, state_dir=None) -> "list[str]":
    from halo_harness.packs.offers import offers
    seen: "dict[tuple[str, str], str]" = {}
    lines: "list[str]" = []
    yours = None
    for pack in active:
        found = offers(pack)
        for kind in ("bios", "lineups", "skills", "commands", "mcp", "agents"):
            for name in found.get(kind) or []:
                key = (kind, name)
                if key in seen:
                    lines.append(f"{_KIND_WORD[kind]} {name}: offered by packs {seen[key]} and {pack.id}; "
                                 f"{seen[key]}'s is used")
                    continue
                seen[key] = pack.id
                if kind in ("bios", "lineups"):
                    mine = _yours(kind, name, cwd=cwd, state_dir=state_dir)
                    if mine:
                        lines.append(f"{_KIND_WORD[kind]} {name}: your {mine} has the name pack {pack.id} offers; "
                                     "yours is used")
                elif kind in ("skills", "commands"):
                    yours = yours if yours is not None else _user_skill_and_command_names(cwd)
                    if name in yours[kind]:
                        lines.append(f"{_KIND_WORD[kind]} {name}: one of your own has the name pack {pack.id} "
                                     "offers; yours is used")
    return lines
