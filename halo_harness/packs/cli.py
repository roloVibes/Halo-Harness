"""halo_harness.packs.cli -- `halo pack ...` (docs/PACKS.md, docs/COMMANDS-packs.md).

    halo pack list [--json]                           every pack here: id, version, state, scope, source, what it offers
    halo pack inspect <id|path> [--json]              the manifest, what it offers, its permissions and which are granted, problems
    halo pack install <path|git url> [--project] [--json]
                                                      copy it into ~/.halo/packs/<id>/ (or .halo/packs/<id>/), disabled
    halo pack enable <id> [--grant NAME ...] [--grant-all] [--json]
                                                      turn it on; grant what it requests (mcp:<server>, hooks, bash, network, home-write)
    halo pack disable <id> [--json]                   nothing of it runs from now on; its files stay
    halo pack update <id> [--json]                    from its source, through the journal; migration notes printed
    halo pack remove <id> [--keep-config] [--json]    the pack's own files only; yours stay and are listed
    halo pack doctor [--json]                         every problem, one line each

Every verb takes `--cwd DIR` (act as if run from DIR: its `.halo/packs/`).
Exit codes: 0 done, 1 could not (the reason on stderr; for doctor: problems
found), 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VERBS = ("list", "inspect", "install", "enable", "disable", "update", "remove", "doctor")
USAGE = __doc__.split("\n\n")[1]


def _parser(verb: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo pack {verb}")
    if verb == "inspect":
        p.add_argument("target", help="an installed pack's id, or a pack folder")
    if verb == "install":
        p.add_argument("source", help="a pack folder or a git url")
        p.add_argument("--project", action="store_true", help="install into this repo's .halo/packs/ instead of ~/.halo/packs/")
    if verb in ("enable", "disable", "update", "remove"):
        p.add_argument("id")
    if verb == "enable":
        p.add_argument("--grant", action="append", default=[], metavar="NAME",
                       help="grant one permission the pack requests (repeat for several)")
        p.add_argument("--grant-all", action="store_true", help="grant every permission the pack requests")
    if verb == "remove":
        p.add_argument("--keep-config", action="store_true",
                       help="keep the pack's record and grants for a later install")
    p.add_argument("--cwd", default=None, metavar="DIR", help="act as if run from DIR")
    p.add_argument("--json", action="store_true", help="print JSON")
    return p


def _err(text: str, code: int = 1) -> int:
    print(f"halo pack: {text}", file=sys.stderr)
    return code


def _done(args, ok: bool, lines: "list[str]") -> int:
    if args.json:
        print(json.dumps({"ok": ok, "lines": lines}, indent=2, ensure_ascii=False))
        return 0 if ok else 1
    if ok:
        print("\n".join(lines))
        return 0
    for line in lines:
        print(f"halo pack: {line}", file=sys.stderr)
    return 1


def _list(args, cwd) -> int:
    from halo_harness.packs import cli_views as CV
    from halo_harness.packs.registry import snapshot
    rows = CV.list_rows(snapshot(cwd=cwd))
    if args.json:
        print(json.dumps({"packs": rows}, indent=2, ensure_ascii=False))
    else:
        print("\n".join(CV.list_lines(rows)))
    return 0


def _inspect(args, cwd) -> int:
    from halo_harness.packs import cli_views as CV
    from halo_harness.packs.discover import read_pack
    from halo_harness.packs.names import is_valid_pack_id
    from halo_harness.packs.registry import snapshot
    snap = snapshot(cwd=cwd)
    pack = snap.pack(args.target) if is_valid_pack_id(args.target) else None
    if pack is None:
        folder = Path(args.target).expanduser()
        if not folder.is_dir():
            return _err(f"{args.target!r} is neither an installed pack (halo pack list) nor a folder")
        pack = read_pack(folder.resolve(), "source", folder_is_id=False)
    data = CV.inspect_payload(pack, snap)
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str) if args.json else "\n".join(CV.inspect_lines(data)))
    return 0


def _doctor(args, cwd) -> int:
    from halo_harness.packs.doctor import problems
    found = problems(cwd=cwd)
    if args.json:
        print(json.dumps({"problems": found}, indent=2, ensure_ascii=False))
        return 1 if found else 0
    print("halo pack doctor")
    for f in found:
        tag = "[ERROR]" if f["severity"] == "blocks" else "[WARN]"
        print(f"  {tag} {f['text']}" + (f" -> {f['fix']}" if f["fix"] else ""))
    blocks = sum(1 for f in found if f["severity"] == "blocks")
    print(f"RESULT: {len(found)} problem(s) ({blocks} error(s), {len(found) - blocks} warning(s)).")
    return 1 if found else 0


def _find(pack_id: str, cwd):
    from halo_harness.packs.discover import find
    return find(pack_id, cwd=cwd)


def cmd_pack(argv: list) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("usage:\n" + USAGE)
        return 0 if argv else 2
    verb = argv[0]
    if verb not in VERBS:
        return _err(f"unknown verb {verb!r}; one of {', '.join(VERBS)}", 2)
    try:
        args = _parser(verb).parse_args(argv[1:])
    except SystemExit as e:
        return int(e.code or 0)
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()
    if verb == "list":
        return _list(args, cwd)
    if verb == "inspect":
        return _inspect(args, cwd)
    if verb == "doctor":
        return _doctor(args, cwd)
    if verb == "install":
        from halo_harness.packs.install import install
        return _done(args, *install(args.source, project=args.project, cwd=cwd))
    if verb == "update":
        from halo_harness.packs.install import update
        return _done(args, *update(args.id, cwd=cwd))
    if verb == "remove":
        from halo_harness.packs.remove import remove
        return _done(args, *remove(args.id, keep_config=args.keep_config, cwd=cwd))
    if verb == "disable":
        from halo_harness.packs.grants import disable
        return _done(args, *disable(args.id))
    pack = _find(args.id, cwd)
    if pack is None:
        return _done(args, False, [f"no pack {args.id!r} here (halo pack list; halo pack install <path|git url>)"])
    from halo_harness.packs.grants import enable
    return _done(args, *enable(pack, grant=args.grant, grant_all=args.grant_all))
