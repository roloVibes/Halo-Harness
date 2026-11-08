"""halo_harness.packs.cli_test -- `halo pack test <folder | installed id>` (Halo 3.3.12.0 R4; docs/COMMANDS-packs.md
"halo pack test").

    halo pack test <folder|id> [--kinds a,b,...] [--timeout S] [--verbose] [--json]

Every check `halo_harness.ext.testing.run` makes, in a scratch home and project of its own: the manifest, the doctor
on an installed copy, each kind's checks. One line per failure (`<file>: <what> -- <fix>`), one per skipped check
(`skip <file>: <what>`), then `RESULT: N checks, N passed, N failed`. Exit 0 every check passed (skips allowed), 1 a
check failed, 2 usage. An installed id is tested from its folder; nothing of the installed pack is changed. `--json`
is one object: {pack, ok, checks, passed, failed, skipped, result}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo pack test")
    p.add_argument("target", help="a pack folder, or the id of a pack installed here")
    p.add_argument("--kinds", default="", metavar="KINDS", help="only these kinds' checks (the manifest and doctor always)")
    p.add_argument("--timeout", type=float, default=10.0, metavar="S", help="each hook, server and policy: seconds")
    p.add_argument("--verbose", action="store_true", help="print the checks that passed too")
    p.add_argument("--cwd", default=None, metavar="DIR", help="act as if run from DIR (for an installed id)")
    p.add_argument("--json", action="store_true", help="print JSON")
    return p


def folder_of(target: str, cwd=None) -> "tuple[Path | None, str]":
    folder = Path(target).expanduser()
    if folder.is_dir():
        return folder.resolve(), ""
    from halo_harness.packs.discover import find
    from halo_harness.packs.names import is_valid_pack_id
    pack = find(target, cwd=cwd) if is_valid_pack_id(target) else None
    if pack is None:
        return None, f"{target!r} is neither a pack folder nor a pack installed here (halo pack list)"
    return Path(pack.root), ""


def cmd(argv) -> int:
    from halo_harness.ext import testing
    from halo_harness.packs.scaffold.kinds import parse
    try:
        args = parser().parse_args(list(argv))
    except SystemExit as e:
        return int(e.code or 0)
    kinds, bad = parse(args.kinds)
    if bad:
        print(f"halo pack: {bad[0]}", file=sys.stderr)
        return 2
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()
    folder, why = folder_of(args.target, cwd=cwd)
    if folder is None:
        print(f"halo pack: {why}", file=sys.stderr)
        return 1
    report = testing.run(folder, kinds=kinds, timeout_s=args.timeout)
    if args.json:
        print(json.dumps(report.as_json(), indent=2, ensure_ascii=False))
    else:
        print(f"halo pack test {report.pack} ({folder.as_posix()})")
        print(report.text(passed=args.verbose))
    return report.exit_code
