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
        term = f" (term #{f['term']})" if f.get("term") else ""
        lines.append(f"{prefix}:{f['line']}: {f['kind']}{term}: {f['excerpt']}")
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
        print("usage: halo audit privacy [--history | --commits | --replays] [--json] [--since REV] [--cwd DIR]",
              file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(
        prog="halo audit privacy", add_help=True,
        description="Scan for real paths, addresses, hostnames, machine names, key/token shapes, and "
                     "e-mail addresses before they reach a public repo.")
    parser.add_argument("--history", action="store_true",
                         help="Scan every distinct blob reachable from any ref the clone has, not the working tree")
    parser.add_argument("--commits", action="store_true",
                         help="Read every commit's author and committer address and message (3.4.1.2); fails only "
                              "on commits not yet on origin/master")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of text lines")
    parser.add_argument("--since", default=None, metavar="REV",
                         help="With --history, leave out everything REV reaches")
    parser.add_argument("--replays", action="store_true",
                         help="Scan this home's saved replays (~/.halo/replays/*.halo-replay) instead: the rules above, "
                              "plus this machine's home path, user name and machine name (3.4.1.1)")
    parser.add_argument("--cwd", default=None, metavar="DIR",
                         help="Repo directory to scan (default: the current directory)")
    args = parser.parse_args(argv[1:])

    start_dir = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    repo = repo_root(start_dir) or start_dir

    from halo_harness.privacy_rules import name_checks_line
    not_checked: "list[str]" = []
    if args.commits:  # 3.4.1.2 (F8): the addresses and messages the file scans never read
        from halo_harness import privacy_commits as pc
        report = pc.scan_commits(repo)
        failing = pc.failing(report)
        if args.json:
            print(json.dumps({"mode": "commits", "repo": repo.name, "clean": not failing, "name_checks":
                              name_checks_line(), **report}, ensure_ascii=False, indent=2))
        else:
            print(name_checks_line())
            print(pc.render(report), end="")
        return 1 if failing else 0
    if args.replays:  # 3.4.1.1 (56): a replay is made to be handed on; its own folder, its own check
        from halo_harness.live.replay_private import audit
        from halo_harness.providers.config import default_state_dir
        findings = audit(default_state_dir())
    else:
        findings = scan_history(repo, since=args.since) if args.history else scan_working_tree(repo, not_checked)

    if args.json:
        payload = {
            "mode": "replays" if args.replays else "history" if args.history else "working-tree",
            # The repo's own NAME only -- never the absolute path, which
            # on a real machine starts with the same real home-profile
            # path (`C:\Users\<name>\...`/`/home/<name>/...`) this whole
            # command exists to catch; a report this command itself
            # produces must not reintroduce that leak.
            "repo": repo.name,
            "clean": not findings,
            "name_checks": name_checks_line(),
            "not_checked": len(not_checked),
            "findings": findings,
        }
        if args.history:
            payload["summary"] = summarize_history(findings)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if not args.replays:
            print(name_checks_line())
        if not_checked:
            print(f"not checked: {len(not_checked)} file(s) that are not text (images, fonts, archives; SVG is text "
                  f"and is checked)")
        print(_render_text(findings, history=args.history), end="")

    return 1 if findings else 0
