"""halo_harness.blocks_cli -- `halo blocks` (Halo 3.3.16.3 "Blocks", docs/COMMANDS-workflows.md "halo blocks"):
the block templates you can start from, and the blocks a lineup has.

    halo blocks list [--json]                         the templates (name, kind, title, who is inside), then the
                                                      active lineup's blocks: its squares with their when line and
                                                      its tiers with their purpose
    halo blocks add <template> [--as <name>] [--lineup <name>]
                                                      a square template: a square of yours wired to main; a tier
                                                      template: a tier added to the lineup (a shipped one copied
                                                      to yours first)
    halo blocks show <name> [--lineup <name>]         a template, or a block of the lineup (a square ref or a tier)

Exit codes: 0 done, 1 not found or refused, 2 a bad request.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VERBS = ("list", "add", "show")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo blocks", description="Block templates and the blocks a lineup has (docs/WORKFLOWS-squares.md).")
    sub = p.add_subparsers(dest="cmd")
    ls = sub.add_parser("list", help="the templates, then the lineup's blocks")
    ls.add_argument("--json", action="store_true")
    ad = sub.add_parser("add", help="add a template's block to a lineup")
    ad.add_argument("template")
    ad.add_argument("--as", dest="as_", default=None, help="the new square's name (a square template)")
    sh = sub.add_parser("show", help="a template, or a block of the lineup")
    sh.add_argument("name")
    for s in (ls, ad, sh):
        s.add_argument("--lineup", default=None, help="the lineup (default: the active one)")
        s.add_argument("--repo", default=None, help="the repo root (default: the current folder)")
    return p


def cmd_blocks(argv) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as e:
        return int(e.code or 0)
    if args.cmd is None:
        parser.print_help()
        return 0
    repo = Path(args.repo or ".").resolve()
    from halo_harness.workflows import blocks as B
    if args.cmd == "add":
        ok, line, _info = B.add(args.template, args.as_, args.lineup, cwd=repo)
        print(line if ok else f"halo blocks add: {line}", file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1
    from halo_harness.workflows.blocks_show import lineup_blocks
    if args.cmd == "list":
        temps = [B.summary(t) for t in (B.load(n)[0] for n in B.names()) if t]
        mine = lineup_blocks(args.lineup, repo)
        if args.json:
            print(json.dumps({"templates": temps, "lineup": mine}, indent=2, default=str))
            return 0
        print("block templates (halo blocks add <name>):")
        for t in temps:
            who = ", ".join(a["bio"] for a in t["agents"])
            print(f"  {t['name']:<14} {t['kind']:<6} {t['title']} -- {who}")
        print(f"lineup {mine['lineup']}:")
        for line in mine["lines"]:
            print(f"  {line}")
        return 0
    t, _why = B.load(args.name)
    if t is not None:
        s = B.summary(t)
        print(f"{s['name']} ({s['kind']} template): {s['title']}")
        print(f"  does      {s['does']}")
        print(f"  inside    {', '.join(a['bio'] + ' on ' + a['model'] for a in s['agents'])}")
        print(f"  costs     {s['costs']}")
        print(f"  adds as   {s['as']}" + (f" (wired to main for {', '.join(s['covers'])})" if s["covers"] else ""))
        print(f"  file      {s['path']}")
        return 0
    mine = lineup_blocks(args.lineup, repo)
    hit = [b for b in mine["blocks"] if b["name"] == args.name]
    if not hit:
        print(f"halo blocks show: no template and no block {args.name!r} on lineup {mine['lineup']} (halo blocks list)", file=sys.stderr)
        return 1
    for line in hit[0]["detail"]:
        print(line)
    return 0
