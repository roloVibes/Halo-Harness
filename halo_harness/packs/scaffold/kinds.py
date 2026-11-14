"""halo_harness.packs.scaffold.kinds -- what `halo pack new --kinds` takes (Halo 3.3.12.0 R4).

Each kind is one folder of `halo_harness/templates/pack-kit/kinds/<kind>/`: `manifest.yaml` (the pack.yaml it adds,
merged) and `files/` (the files it writes; `dot-x` is written as `.x`, and a JSON file two kinds both write is merged).
The base (`pack-kit/base/`) is always written: pack.yaml's head, `.claude-plugin/plugin.json`, `HALO-PACK.md`,
`CHANGELOG.md`, `tests/pack_test.py`, the README and the entry command `commands/<id>.md`.

    KINDS                the kinds, in the order the README lists them
    WHAT                 one line per kind (the usage, the README)
    expand(asked)        the kinds asked for plus the ones they need (teams: agents; workflows: agents, artifacts,
                         skills), in KINDS order, and the lines saying what was added
    themes_known()       whether this Halo reads `contributes.themes` (3.3.12.0 R2)
"""

from __future__ import annotations

from pathlib import Path

KINDS = ("agents", "teams", "skills", "commands", "hooks", "mcp", "events", "artifacts", "workflows", "studio",
         "bundle", "capabilities", "policy", "modes", "setup", "themes", "integration")
WHAT = {
    "agents": "two bios (a lead and a checker) with every section a bio has",
    "teams": "a lineup with two roles, two tiers and an acceptance block",
    "skills": "two skills, one the workflow cites",
    "commands": "a second slash command beside the entry command",
    "hooks": "a PostToolUse hook that appends a line to the pack's data folder",
    "mcp": "a stdio MCP server with one tool that answers",
    "events": "an event kind with its schema and a sample",
    "artifacts": "an artifact schema with a sample",
    "workflows": "a two-stage workflow that uses both roles and ends in the pack's artifact",
    "studio": "a Studio section (a markdown panel, a table over data:rows.json, a bundle panel) and a page the pack "
              "draws itself (a view with api.lib) over its own routes (server/routes.py)",
    "bundle": "a bundle: block -- the local model the pack keeps ready, its reservation and routing",
    "capabilities": "a capability with an inspector line",
    "policy": "a policy hook with its mode: it denies one sample call and allows another",
    "modes": "a runtime mode of the pack",
    "setup": "a Setup block of each kind (a form, a check, a note)",
    "themes": "a palette of the pack's own (every token, AA-clean, a posture)",
    "integration": "an open-source tool wrapped: requires: rg, a command, an MCP server and a hook that use it",
}
NEEDS = {"teams": ("agents",), "workflows": ("agents", "artifacts", "skills")}


def kit_dir() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "templates" / "pack-kit"


def themes_known() -> bool:
    from halo_harness.schemas.pack_yaml import CONTRIBUTION_KEYS
    return "themes" in CONTRIBUTION_KEYS


def themes_line() -> str:
    return ("themes: this Halo does not read contributes.themes yet (a pack's own palettes arrive with 3.3.12.0 R2); "
            "the kind is left out")


def parse(text: str) -> "tuple[list[str], list[str]]":
    """`--kinds a,b c` as kinds, and one line per word that is not a kind."""
    words = (text or "").replace(",", " ").split()
    bad = [w for w in words if w not in KINDS]
    if bad:
        return [], [f"--kinds: {', '.join(bad)} is not a kind; the kinds are {', '.join(KINDS)}"]
    return list(dict.fromkeys(words)), []


def expand(asked) -> "tuple[list[str], list[str]]":
    chosen, lines = set(asked), []
    for kind in list(asked):
        added = [k for k in NEEDS.get(kind, ()) if k not in chosen]
        if added:
            chosen.update(added)
            lines.append(f"{kind} brings {', '.join(added)} (it uses them)")
    return [k for k in KINDS if k in chosen], lines
