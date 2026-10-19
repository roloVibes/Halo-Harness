"""halo_harness.config_where -- `halo config where [--json]` and `/config where`:
every file that sets something for this repo and this home, in one table.

Groups, in this order: Halo's config (`~/.halo/config.json`, `routes.json`),
the env files (names only), Claude Code's `settings.json` layers, the MCP
server files, the active lineup and the lineups it extends, the lineup and
bio folders, the team file, the Databricks team preset. Inside a
group the row with rank 1 is the one the resolver reads first; `wins` and
`loses` say which file decides each key two files set (halo_harness/where/).

`where_rows(cwd, state_dir=...)` is the data (`--json` prints it, Studio's
doctor route and `halo doctor --config` read it); `render(rows)` is the text.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

GROUPS = (("config", "Halo's config"), ("env", "Env files (variable names only)"),
          ("settings", "settings.json (Claude Code's; Halo reads them)"), ("mcp", "MCP servers"),
          ("lineup", "Active lineup"), ("lineups", "Lineup folders"), ("bios", "Bio folders"),
          ("team", "Team file"), ("team-preset", "Databricks team preset"))


def _active_lineup(state_dir: Path) -> str:
    try:
        data = json.loads((state_dir / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    name = data.get("team") if isinstance(data, dict) else None
    return name.strip() if isinstance(name, str) else ""


def where_rows(cwd=None, *, state_dir=None, settings_flag: Optional[str] = None) -> list:
    """Every row (halo_harness/where/rows.py has the shape), grouped as GROUPS."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.where.claude_files import claude_rows
    from halo_harness.where.halo_files import halo_rows
    from halo_harness.where.yaml_files import yaml_rows
    cwd = Path(cwd if cwd is not None else Path.cwd()).resolve()
    state = Path(state_dir) if state_dir is not None else bridge_home()
    rows = halo_rows(cwd, state) + claude_rows(cwd, settings_flag) + yaml_rows(cwd, state, _active_lineup(state))
    order = {kind: i for i, (kind, _title) in enumerate(GROUPS)}
    return sorted(rows, key=lambda r: (order.get(r["kind"], 99), r["rank"]))


def _sets_text(row: dict, limit: int = 8) -> str:
    names = row["sets"]
    if not names:
        return "-"
    shown = ", ".join(names[:limit])
    return shown + (f" (+{len(names) - limit} more)" if len(names) > limit else "")


def render(rows: list, *, cwd=None) -> str:
    """The text table: one block per group, one line per file, then a line
    per key another file decides."""
    from halo_harness.config.paths import home
    here = Path(cwd).resolve() if cwd is not None else Path.cwd().resolve()
    lines = [f"halo config where -- repo {here.as_posix()}, home {home().as_posix()} (~)",
             "Rank 1 is the file the resolver reads first; 'wins' / 'loses to' name who decides a key two files set."]
    width = max([len(r["file"]) for r in rows] + [24])
    for kind, title in GROUPS:
        group = [r for r in rows if r["kind"] == kind]
        if not group:
            continue
        lines.append("")
        lines.append(title)
        for r in group:
            state = "yes" if r["exists"] else "no"
            if r["exists"] and not r["read"]:
                state = "yes, not read"
            lines.append(f"  {r['rank']}. {r['file']:<{width}}  {r['scope']:<7}  {state:<13}  {_sets_text(r)}")
            if r["note"]:
                lines.append(f"     {r['note']}")
            if r["wins"]:
                lines.append(f"     wins: {', '.join(r['wins'])}")
            for entry in r["loses"]:
                lines.append(f"     {entry['key']}: loses to {entry['to']}")
    return "\n".join(lines)


def cmd_config_where(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="halo config where", add_help=True,
                                     description="List every file that sets something for this repo and home: "
                                                 "what each sets and which one wins when two set the same key.")
    parser.add_argument("--json", action="store_true", help="Print the rows as JSON")
    parser.add_argument("--cwd", default=None, metavar="DIR", help="List the files as if run from DIR")
    args = parser.parse_args(argv)
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()
    rows = where_rows(cwd)
    if args.json:
        print(json.dumps({"cwd": str(cwd), "rows": rows}, indent=2))
    else:
        print(render(rows, cwd=cwd))
    sys.stdout.flush()
    return 0
