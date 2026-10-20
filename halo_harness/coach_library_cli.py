"""halo_harness.coach_library_cli -- `halo coach library` (Halo 3.1.6.0 R3; the
library itself: orchestra/coach_library.py):

    halo coach library [list] [--json]              every entry: id, when, project, lineup, source, the title
    halo coach library show <entry> [--json]        its EXPERIENCE.md and the files it keeps
    halo coach library forget <entry> [--yes]       deletes the entry's folder (after y/N)
    halo coach library fetch <harness> <entry> [--json]
                                                    another harness's entry, through the hub this machine runs,
                                                    written here under the same id (never over one that is here)

`halo coach` catches `library` before it parses a run (coach_cli.cmd_coach).
An entry is born when a coach card's Apply writes (`halo coach <run> --apply
<id>`, Studio's Apply), and a probe card's Apply too. Exit codes: 0 done, 1 no
such entry / refused / nothing written, 2 usage, 3 no hub here (fetch).
"""

from __future__ import annotations

import argparse
import json
import sys
import time

BORN = ("the library is empty: an entry is born when a coach card's Apply writes "
        "(halo coach <run> --apply <id>, or Apply in Studio's Coach tab)")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo coach library", description="The coach's improvement library: one entry per "
                                "Apply, with when it applies, the lessons, the evidence and the files it wrote.")
    sub = p.add_subparsers(dest="verb")
    ls = sub.add_parser("list", help="every entry: id, when, project, lineup, source, the title (the default)")
    ls.add_argument("--json", action="store_true", help="the entries as JSON")
    show = sub.add_parser("show", help="one entry's EXPERIENCE.md and the files it keeps")
    show.add_argument("entry", help="the entry id (e-<yyyymmdd>-<4 hex>)")
    show.add_argument("--json", action="store_true", help="entry.json, EXPERIENCE.md and the files as JSON")
    forget = sub.add_parser("forget", help="delete one entry's folder (after y/N)")
    forget.add_argument("entry", help="the entry id")
    forget.add_argument("--yes", action="store_true", help="skip the y/N")
    fetch = sub.add_parser("fetch", help="take another harness's entry through the hub this machine runs")
    fetch.add_argument("harness", help="the harness's name or id (halo fleet who)")
    fetch.add_argument("entry", help="its entry id (halo recall --fleet finds them: kind coach_library)")
    fetch.add_argument("--json", action="store_true", help="the result as JSON")
    return p


def _when(ts) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts or 0)))


def _project(e: dict) -> str:
    p = e.get("project") or {}
    return str(p.get("name") or "-") + (f" ({p['remote']})" if p.get("remote") else "")


def cmd_list(as_json: bool) -> int:
    from halo_harness.orchestra.coach_library import entries
    rows = entries()
    if as_json:
        print(json.dumps({"entries": rows}, indent=2, ensure_ascii=False, default=str))
        return 0
    if not rows:
        print(BORN)
        return 0
    for e in rows:
        marks = (" (undone)" if e.get("undone") else "") + (f" (from {e['from']})" if e.get("from") else "")
        print(f"{e['id']}  {_when(e.get('ts'))}  {_project(e)}  {e.get('lineup') or '-'}  {e.get('source')}  "
              f"{e.get('title') or ''}{marks}")
    return 0


def _missing(entry: str) -> int:
    print(f"halo coach library: no entry {entry!r} (halo coach library lists them)", file=sys.stderr)
    return 1


def cmd_show(entry: str, as_json: bool) -> int:
    from halo_harness.orchestra import coach_library as L
    e = L.read(entry)
    if e is None:
        return _missing(entry)
    text, files = L.text_of(entry, L.EXPERIENCE), L.stored_files(entry)
    if as_json:
        print(json.dumps({"entry": e, "experience": text, "files": files}, indent=2, ensure_ascii=False, default=str))
        return 0
    state = "undone (kept, never cited)" if e.get("undone") else "cited for runs like it"
    print(f"{e['id']}  {_when(e.get('ts'))}  {e.get('source')}  {state}" + (f"  from {e['from']}" if e.get("from") else ""))
    print("")
    print(text.rstrip("\n"))
    print("")
    print(f"files kept in {L.entry_dir(entry) / L.FILES}:" if files else "files kept: none")
    for f in e.get("files") or []:
        kept = "kept" if f.get("path") in files else f"not kept ({f.get('bytes')} bytes)"
        print(f"  {f.get('path')}  ({f.get('scope')} {f.get('target')} {f.get('name')}, {kept})")
    return 0


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except (EOFError, OSError):
        return False


def cmd_forget(entry: str, yes: bool) -> int:
    from halo_harness.orchestra import coach_library as L
    if L.read(entry) is None:
        return _missing(entry)
    if not yes and not _confirm(f"Forget {entry} (deletes {L.entry_dir(entry)})? [y/N] "):
        print("nothing deleted")
        return 1
    L.forget(entry)
    print(f"forgot {entry}: its folder is deleted")
    return 0


def cmd_fetch(harness: str, entry: str, as_json: bool) -> int:
    from halo_harness.orchestra.coach_library_share import fetch
    rc, out = fetch(harness, entry)
    if as_json:
        print(json.dumps({"ok": rc == 0, **out}, indent=2, ensure_ascii=False, default=str))
    elif rc == 0:
        print(f"fetched {out['entry']} from {out['from']}: {out['path']} ({len(out['files'])} file(s)); "
              f"the coach cites it for runs like it")
    else:
        print(f"halo coach library fetch: {out.get('error')}", file=sys.stderr)
    return rc


def cmd_library(argv: list) -> int:
    try:
        a = _parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0) and 2
    verb = a.verb or "list"
    if verb == "list":
        return cmd_list(getattr(a, "json", False))
    from halo_harness.orchestra.coach_library import valid_id
    if not valid_id(a.entry):
        print(f"halo coach library {verb}: {a.entry!r} is not an entry id (e-<yyyymmdd>-<4 hex>)", file=sys.stderr)
        return 2
    if verb == "show":
        return cmd_show(a.entry, a.json)
    if verb == "forget":
        return cmd_forget(a.entry, a.yes)
    return cmd_fetch(a.harness, a.entry, a.json)
