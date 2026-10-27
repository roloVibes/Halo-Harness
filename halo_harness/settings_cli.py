"""halo_harness.settings_cli -- `halo settings [group] [--terminal] [--list]` (Halo 3.3.3.0 R2): the door into
Studio's Settings section, where every key of `~/.halo/config.json` has a row (halo_harness/settings_catalog.py).

On a real terminal `halo settings` opens Halo Studio on Settings (`halo settings fleet` on its Fleet page:
`?mode=settings&group=fleet`, studio/settings_door.py), as `halo setup` opens Setup. `--terminal` prints the
group's rows instead, one `key = value (default ...)` line each through the catalog (every group with no group
named); so does a box where no browser can open, after the URL, and a run with no TTY. `--list` prints the
groups. Nothing here writes: `halo config set` (or the Settings page) changes a key.
"""

from __future__ import annotations

import argparse
import json
import sys

USAGE = "usage: halo settings [group] [--terminal] [--list]"


def _word(value) -> str:
    return "unset" if value is None else json.dumps(value)


def group_lines(group: str = "") -> "list[str]":
    """The `--terminal` listing: a heading per group, then `key = value (default ...)` per row."""
    from halo_harness.settings_catalog import GROUPS, rows
    from halo_harness.studio.settings_values import values
    from halo_harness.theme import load_config
    saved = values(load_config())
    out: list = []
    for gid, title in GROUPS:
        if group and gid != group:
            continue
        out.append(f"{title} (Settings -> {title})")
        for r in (x for x in rows() if x.group == gid):
            v = saved[r.key]
            if r.kind == "keyed":
                set_entries = [e for e in v["entries"] if e["set"]]
                if not set_entries:
                    out.append(f"  {r.key} = no entry set (default {_word(r.default)})")
                for e in set_entries:
                    shown = "set, hidden" if r.secret else _word(e["value"])
                    out.append(f"  {e['key']} = {shown} (default {_word(r.default)})")
            elif not v["set"]:
                out.append(f"  {r.key} = {_word(r.default)} (default)")
            else:
                shown = "set, hidden" if v["masked"] else _word(v["value"])
                out.append(f"  {r.key} = {shown} (default {_word(r.default)})")
        out.append("")
    return out[:-1] if out and out[-1] == "" else out


def _print_groups() -> int:
    from halo_harness.settings_catalog import groups
    for g in groups():
        print(f"{g['id']:<11} {g['title']} ({g['count']} key{'s' if g['count'] != 1 else ''})")
    return 0


def _open_in_studio(group: str) -> bool:
    from halo_harness.studio.settings_door import SettingsTarget
    from halo_harness.studio.setup_door import cli_door
    cli = "halo settings" + (f" {group}" if group else "") + " --terminal"
    return cli_door(SettingsTarget(group=group), terminal_cli=cli, fallback="listing")


def cmd_settings(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="halo settings", description="Open Halo Studio on its Settings section: "
                                     "every ~/.halo/config.json key, one page per group, each with its help, its "
                                     "default and its halo config set line.")
    parser.add_argument("group", nargs="?", default="", help="the group whose page opens (fleet, ollama, ...; --list names them)")
    parser.add_argument("--terminal", action="store_true", help="print the group's keys here (key = value (default ...)) instead of opening Studio")
    parser.add_argument("--list", action="store_true", help="print the groups and how many keys each holds")
    args = parser.parse_args(argv)
    if args.list:
        return _print_groups()
    from halo_harness.studio.settings_door import group_word
    group, why = group_word(args.group)
    if group is None:
        print(f"halo settings: {why}", file=sys.stderr)
        return 2
    if not args.terminal and sys.stdin.isatty() and sys.stdout.isatty() and _open_in_studio(group):
        return 0
    print("\n".join(group_lines(group)))
    return 0
