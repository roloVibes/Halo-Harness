"""halo_harness.audit_cli -- `halo audit privacy [--history] [--json]
[--since <rev>]` (2.0.4 round 1): scans the working tree (default) or
every distinct blob reachable from history (`--history`) for the privacy
rules halo_harness.privacy_rules/halo_harness.privacy_scan define and
tests/test_privacy_scan.py shares -- real user-profile paths, LAN/link-
local IP literals, `.local` hostnames, known machine/vendor names, stray
`%SystemDrive%`-style cache files, key/token shapes, e-mail addresses, and
any real path under the state dir. Wired the way `halo doctor`/`halo
bugreport` are: halo_harness/cli.py dispatches `argv[0] == "audit"` to
`cmd_audit` here before the main parser ever sees the rest of argv.

Exit 1 when anything is found (working-tree OR history mode), 0 when
clean -- a CI-friendly gate, not just a report. Every excerpt this prints
or serializes has already had the matched span replaced with
`<redacted>` by halo_harness.privacy_scan; nothing here ever holds the
real value.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from halo_harness.privacy_scan import scan_history, scan_working_tree, summarize_history
from halo_harness.worktree import repo_root


def _render_text(findings: "list[dict]", *, history: bool) -> str:
    lines = []
    for f in findings:
        prefix = f"{f.get('commit') or '?'}:{f['path']}" if history else f['path']
        lines.append(f"{prefix}:{f['line']}: {f['kind']}: {f['excerpt']}")
    if not lines:
        return "halo audit privacy: clean -- nothing found.\n"
    out = "\n".join(lines) + "\n"
    if history:
        summary = summarize_history(findings)
        out += f"\n--- summary ({len(findings)} finding(s)) ---\n"
        out += f"distinct paths to purge entirely: {len(summary['purge_entirely'])}\n"
        for item in summary["purge_entirely"]:
            out += f"  purge: {item['path']} (first seen: {item.get('commit') or '?'})\n"
        out += f"paths needing text replacement: {len(summary['text_replacements'])}\n"
        for item in summary["text_replacements"]:
            out += (f"  replace in: {item['path']} ({item['count']} finding(s): "
                     f"{', '.join(item['kinds'])}; first seen: {item.get('commit') or '?'})\n")
    return out


def cmd_audit(argv: "list[str]") -> int:
    if not argv or argv[0] != "privacy":
        print("usage: halo audit privacy [--history] [--json] [--since REV] [--cwd DIR]", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(
        prog="halo audit privacy", add_help=True,
        description="Scan for real paths, addresses, hostnames, machine names, key/token shapes, and "
                     "e-mail addresses before they reach a public repo.")
    parser.add_argument("--history", action="store_true",
                         help="Scan every distinct blob reachable from HEAD instead of just the working tree")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of text lines")
    parser.add_argument("--since", default=None, metavar="REV",
                         help="With --history, only commits in REV..HEAD instead of every commit reachable from HEAD")
    parser.add_argument("--cwd", default=None, metavar="DIR",
                         help="Repo directory to scan (default: the current directory)")
    args = parser.parse_args(argv[1:])

    start_dir = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    repo = repo_root(start_dir) or start_dir

    findings = scan_history(repo, since=args.since) if args.history else scan_working_tree(repo)

    if args.json:
        payload = {
            "mode": "history" if args.history else "working-tree",
            # The repo's own NAME only -- never the absolute path, which
            # on a real machine starts with the same real home-profile
            # path (`C:\Users\<name>\...`/`/home/<name>/...`) this whole
            # command exists to catch; a report this command itself
            # produces must not reintroduce that leak.
            "repo": repo.name,
            "clean": not findings,
            "findings": findings,
        }
        if args.history:
            payload["summary"] = summarize_history(findings)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_render_text(findings, history=args.history), end="")

    return 1 if findings else 0
