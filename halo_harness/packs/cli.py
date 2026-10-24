"""halo_harness.packs.cli -- `halo pack ...` (docs/PACKS.md, docs/COMMANDS-packs.md).

    halo pack list [--available] [--json]             every pack here: id, version, state, scope, source, what it offers;
                                                      --available: and what the sources hold that is not installed
    halo pack inspect <id|path> [--json]              the manifest, what it offers, its permissions and which are granted, problems
    halo pack install <path|git url|id> [--project] [--json]
                                                      copy it into ~/.halo/packs/<id>/ (or .halo/packs/<id>/), disabled
    halo pack enable <id> [--grant NAME ...] [--grant-all] [--json]
                                                      turn it on; grant what it requests (mcp:<server>, hooks, bash, network, home-write)
    halo pack grant <id> NAME [NAME ...] [--off] [--json]
                                                      give an enabled pack more of what it requests, or take grants back (--off)
    halo pack disable <id> [--json]                   nothing of it runs from now on; its files stay
    halo pack update <id> [--dry-run] [--json]        from its source: its migration notes first, then the new version
                                                      swapped in, the old one kept as <id>.previous (--dry-run: say it, change nothing)
    halo pack rollback <id> [--json]                  back to the version the last update replaced (<id>.previous)
    halo pack remove <id> [--keep-config] [--json]    the pack's own files only; yours stay and are listed
    halo pack sources [add|remove <folder|git url>] [--json]
                                                      where a bare id is looked for: config packs.sources, then the packs Halo ships
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

VERBS = ("list", "inspect", "install", "enable", "grant", "disable", "update", "rollback", "remove", "sources", "doctor")
USAGE = __doc__.split("\n\n")[1]


def _parser(verb: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo pack {verb}")
    if verb == "list":
        p.add_argument("--available", action="store_true",
                       help="also list what packs.sources and the packs Halo ships hold that is not installed")
    if verb == "inspect":
        p.add_argument("target", help="an installed pack's id, or a pack folder")
    if verb == "install":
        p.add_argument("source", help="a pack folder, a git url, or an id found in packs.sources or the packs Halo ships")
        p.add_argument("--project", action="store_true", help="install into this repo's .halo/packs/ instead of ~/.halo/packs/")
    if verb in ("enable", "grant", "disable", "update", "rollback", "remove"):
        p.add_argument("id")
    if verb == "update":
        p.add_argument("--dry-run", action="store_true",
                       help="print the migration notes and what would change; change nothing")
    if verb == "enable":
        p.add_argument("--grant", action="append", default=[], metavar="NAME",
                       help="grant one permission the pack requests (repeat for several)")
        p.add_argument("--grant-all", action="store_true", help="grant every permission the pack requests")
    if verb == "grant":
        p.add_argument("names", nargs="+", metavar="NAME", help="a permission the pack requests")
        p.add_argument("--off", action="store_true", help="take the grants back instead")
    if verb == "remove":
        p.add_argument("--keep-config", action="store_true",
                       help="keep the pack's record and grants for a later install")
    if verb == "sources":
        p.add_argument("action", nargs="?", choices=("add", "remove"), help="add or remove one entry of packs.sources")
        p.add_argument("source", nargs="?", help="a folder of packs, a pack's folder or a git url")
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
    more = None
    if args.available:
        from halo_harness.packs.sources import available
        more = available(cwd=cwd)
    if args.json:
        print(json.dumps({"packs": rows, **({"available": more} if more is not None else {})}, indent=2, ensure_ascii=False))
    else:
        print("\n".join(CV.list_lines(rows) + (CV.available_lines(more) if more is not None else [])))
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
    data = CV.inspect_payload(pack, snap, cwd=cwd)
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str) if args.json else "\n".join(CV.inspect_lines(data)))
    return 0


def _sources(args, cwd) -> int:
    from halo_harness.packs import cli_views as CV
    from halo_harness.packs import sources as SRC
    if args.action:
        if not args.source:
            return _err(f"halo pack sources {args.action} needs a folder or a git url", 2)
        return _done(args, *(SRC.add if args.action == "add" else SRC.remove)(args.source))
    rows = SRC.listing(cwd=cwd)
    print(json.dumps({"sources": rows}, indent=2, ensure_ascii=False) if args.json else "\n".join(CV.sources_lines(rows)))
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
    if verb in ("list", "inspect", "doctor", "sources"):
        return {"list": _list, "inspect": _inspect, "doctor": _doctor, "sources": _sources}[verb](args, cwd)
    if verb == "install":
        from halo_harness.packs.install import install
        return _done(args, *install(args.source, project=args.project, cwd=cwd))
    if verb == "update":
        from halo_harness.packs.install import update
        return _done(args, *update(args.id, dry_run=args.dry_run, cwd=cwd))
    if verb == "rollback":
        from halo_harness.packs.rollback import rollback
        return _done(args, *rollback(args.id, cwd=cwd))
    if verb == "remove":
        from halo_harness.packs.remove import remove
        return _done(args, *remove(args.id, keep_config=args.keep_config, cwd=cwd))
    from halo_harness.packs import grants as G
    if verb == "disable":
        return _done(args, *G.disable(args.id))
    if verb == "grant":
        return _done(args, *G.grant(args.id, args.names, on=not args.off, cwd=cwd))
    return _done(args, *G.enable_id(args.id, grant=args.grant, grant_all=args.grant_all, cwd=cwd))
