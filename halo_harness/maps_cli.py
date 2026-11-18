"""halo_harness.maps_cli -- `halo maps` (Halo 3.6.0.0 R3, docs/COMMANDS-agents.md "halo maps").

    halo maps list            every map: yours, this project's (a trusted folder), then the ones that ship with Halo; the one in use marked
    halo maps show <name>     main, each box, each line with its When in words, what waits under "Not connected yet",
                              the cap, the problems (studio_show's own text)
    halo maps use <name>      new sessions run on it (config `crew.map`); `--off` goes back to Auto (the default: main
                              picks who works on each task); `--none` is One model for everything (roles off, no map)
    halo maps copy <name> [--as <new>]  your own copy of one (one that ships with Halo, a pack's, the project's), to edit
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
    cp = sub.add_parser("copy", help="your own copy of one (one that ships with Halo, a pack's, the project's), to edit")
    cp.add_argument("name")
    cp.add_argument("--as", dest="as_name", default=None, metavar="NAME", help="the copy's name (default my-<name>)")
    use = sub.add_parser("use", help="new sessions run on this map (config crew.map)")
    use.add_argument("name", nargs="?")
    use.add_argument("--off", action="store_true", help="goes back to Auto (the default)")
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
        print(f"{'*' if source == 'default' else ' '} {'auto':<20} {'default':<8} main picks who works on each task")
        seen = set()
        for r in store.rows("map", cwd=cwd):
            auto = store.is_auto(r["name"])  # 3.6.0.5 W4/A4: his old auto/starter file is listed, never in use
            if auto and r["_scope"] == "starter":
                continue  # the shipped default: its row is the first one
            key = (r["name"], False) if auto else r["name"]
            if key in seen:
                continue
            seen.add(key)
            mark = "*" if r["name"] == used and not auto else " "
            bad = f"  problem: {r['_problems'][0]}" if r["_problems"] else ""
            print(f"{mark} {r['name']:<20} {store.scope_words(r['_scope'], short=True):<8} {len(r.get('boxes') or [])} boxes, {len(r.get('lines') or [])} lines{bad}")
            gone = store.dangling_line(r, cwd=cwd) if r["_scope"] != "starter" and not r["_problems"] else ""
            if gone:  # 3.6.0.0 R5d: a copy of a pack's map outlives the pack
                print(f"    {gone}")
        print("in use: Auto (the default)" if source == "default" else
              f"in use: {used} ({source})" if used else "in use: none (One model for everything: roles off)")
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
    if not (args.off or args.none) and args.name and not store.is_auto(args.name):
        args.name, said = store.resolve("map", args.name, cwd=cwd)  # 3.6.0.0 R5c: a pack's map named bare
        if said:
            print(said, file=sys.stderr)
    if not (args.off or args.none) and (not args.name or store.find("map", args.name, cwd=cwd) is None):
        print(f"halo maps use: no map named {args.name!r} (halo maps list)", file=sys.stderr)
        return 1
    from halo_harness.crew.changes import write_all
    from halo_harness.crew.changes_map import ONE_MODEL, config_path, config_text
    choice = ONE_MODEL if args.none else None if args.off else args.name
    from halo_harness.theme import CorruptConfigError
    try:
        text = config_text(choice)
    except CorruptConfigError as e:  # 3.6.0.0 fx: a config.json that does not parse is never rewritten as {crew}
        print(f"halo maps use: {e}", file=sys.stderr)
        return 2
    from halo_harness.crew.map_session import configured_mode, start_modes, starts_said
    resolved = configured_mode(cwd)
    before = start_modes(cwd)
    undo_id = write_all({config_path(): text})
    said = ("One model for everything: no map, main does every job on your model (roles off)." if args.none else
            "New sessions run on Auto (the default); no map of yours is set."
            if choice is None or store.is_auto(choice) else f"New sessions run on the map {args.name}; a running session keeps its own.")
    after, here = start_modes(cwd), True  # 3.6.0.1: said when the mode new sessions start in changes (jf-mapuse: and outside)
    line = ""
    if choice is not None and choice != ONE_MODEL and not store.is_auto(choice):  # batch01 #2: what its main does to your permission mode
        from halo_harness.crew.compile import compile_map
        from halo_harness.crew.map_session import main_mode
        _m, line = main_mode(compile_map(args.name, cwd=cwd), resolved)
        if line and _m != resolved and before[0][1] == resolved:
            here = False  # main's line below already says the new mode and the old one ("your own mode was ...")
    moved = starts_said(before, after, here)
    said = f"{said[:-1]}; {moved}." if moved else said
    print(said + f" (undo id {undo_id}: Studio's builder Undo puts it back)")
    if line:
        print(line[len("halo: "):] if line.startswith("halo: ") else line)
    return 0
