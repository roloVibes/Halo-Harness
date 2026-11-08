"""halo_harness.packs.cli_new -- `halo pack new <id>` (Halo 3.3.12.0 R4; docs/COMMANDS-packs.md "halo pack new").

    halo pack new <id> [--kinds a,b,...] [--all] [--dir FOLDER] [--name TEXT] [--description TEXT] [--author TEXT]
                       [--github | --no-github] [--license SPDX] [--json]

Writes `<FOLDER>/<id>/` (the current folder by default): a complete pack with one working example of each kind asked
for (packs/scaffold/kinds.py WHAT), its entry command `/<id>`, a README written from the manifest, HALO-PACK.md and
tests/pack_test.py; with --github (the default) also LICENSE, .gitignore and a GitHub Actions workflow that runs
`halo pack test .`. Exit 0 written, 1 could not (one line: a folder already there, a bad id), 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys


def parser() -> argparse.ArgumentParser:
    from halo_harness.packs.scaffold.kinds import KINDS, WHAT
    p = argparse.ArgumentParser(prog="halo pack new", formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="kinds:\n" + "\n".join(f"  {k:<12} {WHAT[k]}" for k in KINDS))
    p.add_argument("id", help="the pack's id: lower-case letters, digits and single hyphens (my-checks)")
    p.add_argument("--kinds", default="", metavar="KINDS", help="the parts to write, comma separated (see below)")
    p.add_argument("--all", action="store_true", help="every kind")
    p.add_argument("--dir", default=None, metavar="FOLDER", help="where the pack's folder goes (default: here)")
    p.add_argument("--name", default="", help="the pack's name (default: the id in words)")
    p.add_argument("--description", default="", help="one sentence: what the pack does")
    p.add_argument("--author", default="", help="the author pack.yaml and LICENSE name")
    p.add_argument("--github", dest="github", action="store_true", default=True,
                   help="also LICENSE, .gitignore and .github/workflows/pack-test.yml (the default)")
    p.add_argument("--no-github", dest="github", action="store_false", help="leave the GitHub files out")
    p.add_argument("--license", default="MIT", metavar="SPDX", help="the license id (default MIT)")
    p.add_argument("--cwd", default=None, metavar="DIR", help="act as if run from DIR (the default --dir)")
    p.add_argument("--json", action="store_true", help="print JSON")
    return p


def cmd(argv) -> int:
    from halo_harness.packs.scaffold import new
    from halo_harness.packs.scaffold.kinds import parse
    try:
        args = parser().parse_args(list(argv))
    except SystemExit as e:
        return int(e.code or 0)
    kinds, bad = parse(args.kinds)
    if bad:
        print(f"halo pack: {bad[0]}", file=sys.stderr)
        return 2
    ok, lines = new(args.id, kinds=kinds, all_kinds=args.all, folder=args.dir or args.cwd, github=args.github,
                    license_id=args.license, name=args.name, description=args.description, author=args.author)
    if args.json:
        print(json.dumps({"ok": ok, "lines": lines}, indent=2, ensure_ascii=False))
    elif ok:
        print("\n".join(lines))
    else:
        for line in lines:
            print(f"halo pack: {line}", file=sys.stderr)
    return 0 if ok else 1
