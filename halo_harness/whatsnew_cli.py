"""halo_harness.whatsnew_cli -- `halo whatsnew` and the TUI's `/whatsnew` (Halo 3.3.16.2, docs/COMMANDS.md,
halo_harness/whatsnew.py).

    halo whatsnew [<version>] [--since <version>] [--full] [--summary]

No argument: the entry of the installed version -- its two-sentence summary and each `###` heading with its first
line; `<version>` another entry; `--full` the whole entry; `--since 3.3.15.0` every entry after that one (newest
first); `--summary` the summary alone (what `halo update` prints after it installs). The text comes from the
CHANGELOG entries the package ships (halo_harness/data/changelog.md). Exit 0 shown, 1 not there, 2 usage.
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, Optional

from halo_harness import whatsnew as W

MORE = "halo whatsnew for the rest"


def _vkey(version: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in str(version).split("."))


def _brief(e: W.Entry) -> "list[str]":
    lines = [f"Halo {e.version} ({e.date})", "", W.summary(e.body) or "(no summary line in this entry)"]
    for title, first in W.headings(e.body):
        lines += ["", f"{title}:", f"  {first}" if first else "  -"]
    return lines


def _full(e: W.Entry) -> "list[str]":
    return [f"Halo {e.version} ({e.date})", "", e.body.strip()]


def text_for(version: str = "", *, since: str = "", full: bool = False, only_summary: bool = False,
             installed: Optional[str] = None, rows: "Optional[list]" = None) -> "tuple[int, str]":
    rows = W.load() if rows is None else rows
    if not rows:
        return 1, ("no changelog ships with this install (halo_harness/data/changelog.md is missing); "
                   "the project's CHANGELOG.md has every entry")
    if since:
        newer = [e for e in rows if _vkey(e.version) > _vkey(since)]
        if not newer:
            return 1, f"no entry after {since} here (the newest is {rows[0].version})"
        return 0, "\n\n".join("\n".join((_full if full else _brief)(e)) for e in newer)
    if not installed:
        from halo_harness import __version__ as installed
    want = version or installed
    entry = next((e for e in rows if e.version == want), None)
    note = ""
    if entry is None and version:
        known = ", ".join(e.version for e in rows[:6])
        return 1, f"no entry for {version} in the shipped changelog (it has {known}, ...)"
    if entry is None:
        entry, note = rows[0], f"(no dated entry for {want} yet: the newest shipped entry follows)\n\n"
    if only_summary:
        return 0, W.summary(entry.body)
    return 0, note + "\n".join((_full if full else _brief)(entry)) + ("" if full else f"\n\n{MORE} (--full)")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo whatsnew", description="What a version changed (the shipped CHANGELOG entries).")
    p.add_argument("version", nargs="?", default="", help="a version (default: the installed one)")
    p.add_argument("--since", default="", metavar="VERSION", help="every entry after this version")
    p.add_argument("--full", action="store_true", help="the whole entry, not the summary and headings")
    p.add_argument("--summary", action="store_true", help="the two-sentence summary only")
    return p


def cmd_whatsnew(argv) -> int:
    try:
        a = _parser().parse_args(list(argv))
    except SystemExit as e:
        return int(e.code or 0)
    code, text = text_for(a.version, since=a.since, full=a.full, only_summary=a.summary)
    print(text, file=sys.stdout if code == 0 else sys.stderr)
    return code


def slash_text(args: str, facade=None) -> str:
    """The TUI's `/whatsnew [<version>] [--since V] [--full]`: the same text as the command."""
    import contextlib
    import io
    words = str(args or "").split()
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            a = _parser().parse_args(words)
    except SystemExit:
        return "usage: /whatsnew [<version>] [--since <version>] [--full] [--summary] (as halo whatsnew)"
    return text_for(a.version, since=a.since, full=a.full, only_summary=a.summary)[1]


def after_update(returncode: int, before: dict, after_line: str, *, run_fn: Callable) -> int:
    """`halo update`'s last lines once it installed a newer version: the new version's summary (from the new
    install's own `halo whatsnew --summary`) and where the rest is. The exit code it was going to return."""
    if returncode != 0:
        return 1
    old = str((before or {}).get("version") or "")
    if old and old in str(after_line or "").split():
        return 0
    try:
        got = run_fn(["halo", "whatsnew", "--summary"], capture_output=True, text=True, timeout=15)
        text = (got.stdout or "").strip() if getattr(got, "returncode", 1) == 0 else ""
    except Exception:
        text = ""
    if text:
        print(f"halo update: what is new -- {text}")
    print(f"halo update: {MORE}")
    for line in stale_packs(run_fn):  # 3.4.1.0 R5 (defect 30): last, a pack older than the one the new Halo ships
        print(f"halo update: {line}")
    return 0


def stale_packs(run_fn: Callable) -> "list[str]":
    """The new install's word on every installed pack older than the one it ships (`halo pack list --json`, its
    `ships`); [] when it cannot say (an older Halo, a failed run)."""
    import json
    try:
        got = run_fn(["halo", "pack", "list", "--json"], capture_output=True, text=True, timeout=30)
        rows = json.loads(got.stdout or "{}").get("packs") or [] if getattr(got, "returncode", 1) == 0 else []
    except Exception:
        return []
    from halo_harness.packs.shipped_newer import note
    return [note(r["id"], r.get("version") or "?", r["ships"]) for r in rows if isinstance(r, dict) and r.get("ships") and r.get("id")]
