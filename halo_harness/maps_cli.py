"""halo_harness.maps_cli -- `halo maps` (Halo 3.6.0.0 R3, docs/COMMANDS-agents.md "halo maps").

    halo maps list            every map: yours, this project's (a trusted folder), the starters; the one in use marked
    halo maps show <name>     main, each box, each line with its When in words, what waits under "Not connected yet",
                              the cap, the problems (studio_show's own text)
    halo maps use <name>      new sessions run on it (config `crew.map`); `--off` goes back to the default (the starter
                              map drawn, no rules of its own); `--none` is One model for everything (roles off, no map)
    halo maps copy <name> [--as <new>]  your own copy of one (a starter, a pack's, the project's), to edit
    halo maps edit <name>     your $VISUAL / $EDITOR on your map's file; else Studio, Agents -> 3 · Map, on it

Editing a map is Studio's Map tab (`halo studio`, Agents -> 3 · Map) or its builder box; `--map <name>` runs one session
on a map without changing config.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo maps", description="Your maps: what main hands work to, and when.")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list", help="every map, the one in use marked")
    show = sub.add_parser("show", help="one map in words")
    show.add_argument("name")
    cp = sub.add_parser("copy", help="your own copy of one (a starter, a pack's, the project's), to edit")
    cp.add_argument("name")
    cp.add_argument("--as", dest="as_name", default=None, metavar="NAME", help="the copy's name (default my-<name>)")
    use = sub.add_parser("use", help="new sessions run on this map (config crew.map)")
    use.add_argument("name", nargs="?")
    use.add_argument("--off", action="store_true", help="stop using a map of your choice: new sessions run as by default")
    use.add_argument("--none", action="store_true", help="One model for everything: no map, main does every job (roles off)")
    edit = sub.add_parser("edit", help="open it in your editor, or in Studio")
    edit.add_argument("name")
    return p


def cmd_maps(argv) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as e:
        return int(e.code or 0)
    cwd = Path.cwd()
    from halo_harness.crew import store
    from halo_harness.crew.compile import in_use
    if args.cmd in (None, "list"):
        used, source = in_use(None, cwd)
        seen = set()
        for r in store.rows("map", cwd=cwd):
            if r["name"] in seen:
                continue
            seen.add(r["name"])
            mark = "*" if r["name"] == used else " "
            bad = f"  problem: {r['_problems'][0]}" if r["_problems"] else ""
            print(f"{mark} {r['name']:<20} {r['_scope']:<8} {len(r.get('boxes') or [])} boxes, {len(r.get('lines') or [])} lines{bad}")
        print(f"in use: {used} ({source})" if used else "in use: none (One model for everything: roles off)")
        return 0
    if args.cmd == "copy":  # 3.6.0.0 R5d: own_copy
        from halo_harness.crew_cli_parts import copy
        return copy("map", args.name, args.as_name, cwd)
    if args.cmd == "edit":  # 3.6.0.0 R5
        from halo_harness.crew_cli_parts import edit
        return edit("map", args.name, cwd)
    if args.cmd == "show":
        if store.find("map", args.name, cwd=cwd) is None:
            print(f"halo maps show: no map named {args.name!r} (halo maps list)", file=sys.stderr)
            return 1
        from halo_harness.crew.tools_show import studio_show
        print(studio_show({"what": "map", "name": args.name}, {"cwd": cwd, "state_dir": None})["text"])
        return 0
    if not (args.off or args.none) and args.name:
        args.name, said = store.resolve("map", args.name, cwd=cwd)  # 3.6.0.0 R5c: a pack's map named bare
        if said:
            print(said, file=sys.stderr)
    if not (args.off or args.none) and (not args.name or store.find("map", args.name, cwd=cwd) is None):
        print(f"halo maps use: no map named {args.name!r} (halo maps list)", file=sys.stderr)
        return 1
    from halo_harness.crew.changes import write_all
    from halo_harness.crew.changes_map import ONE_MODEL, config_path, config_text
    from halo_harness.crew.compile import DEFAULT_MAP
    choice = ONE_MODEL if args.none else None if args.off else args.name
    undo_id = write_all({config_path(): config_text(choice)})
    said = ("One model for everything: no map, main does every job on your model (roles off)." if args.none else
            f"New sessions run as by default (the {DEFAULT_MAP} map draws what they do; no map of yours is set)."
            if choice in (None, DEFAULT_MAP) else f"New sessions run on the map {args.name}; a running session keeps its own.")
    print(said + f" (undo id {undo_id}: Studio's builder Undo puts it back)")
    return 0
