"""halo_harness.privacy_commits -- `halo audit privacy --commits` (3.4.1.2, F8): what the file scans never read.

Every commit of every ref the clone has (`git log --all`): the author's and the committer's e-mail address, and the
message body. It reports

- every address that is not a GitHub noreply one, masked (`ab...@cd...`), with how many commits carry it;
- every term of the owner's private list (halo_harness.privacy_rules) found in a message, as `term #n`.

Old commits are a report only (their fix is a history rewrite, the owner's call): a finding FAILS the audit only
when the commit is not yet on `origin/master` (the commits a push would send). With no `origin/master` every commit
reachable from HEAD counts as new. Nothing here prints an address or a term in full.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from halo_harness import privacy_rules as rules

_SEP, _END = "\x1f", "\x1e"


def _git(repo: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout if r.returncode == 0 else ""


def mask_address(addr: str) -> str:
    """`ab...@cd...`: enough to tell two addresses apart in a report, never the address."""
    local, _, domain = addr.strip().partition("@")
    return f"{local[:2]}...@{domain[:2]}..."


def new_commits(repo: Path) -> "set[str]":
    """The commits a push of HEAD would send: HEAD's, minus `origin/master`'s (all of HEAD's without it)."""
    has_origin = bool(_git(repo, "rev-parse", "--verify", "--quiet", "origin/master").strip())
    args = ["rev-list", "HEAD"] + (["--not", "origin/master"] if has_origin else [])
    return {ln.strip() for ln in _git(repo, *args).splitlines() if ln.strip()}


def _terms() -> "list[tuple[int, str, bool]]":
    """(number, term, case-insensitive) for every term of the owner's list, numbered as the file scan numbers them."""
    exact = [(n, t, False) for n, t in enumerate(rules.REMOVED_NAMES, 1)]
    ci = [(n, t, True) for n, t in enumerate(rules.EXTENDED_SCAN_TERMS, len(rules.REMOVED_NAMES) + 1)]
    return exact + ci


def scan_commits(repo: Path) -> dict:
    """{"commits": n, "addresses": [{"address": masked, "commits": n, "new": k}], "findings": [...]} where a
    finding is {"kind", "commit", "excerpt", "new"} (kind `commit-email` or `commit-message`; excerpt masked)."""
    out = _git(repo, "log", "--all", f"--format=%H{_SEP}%ae{_SEP}%ce{_SEP}%B{_END}")
    fresh = new_commits(repo)
    terms = _terms()
    per_addr: "dict[str, dict]" = {}
    findings: "list[dict]" = []
    count = 0
    for record in out.split(_END):
        bits = record.strip("\n").split(_SEP, 3)
        if len(bits) != 4 or not bits[0].strip():
            continue
        sha, author, committer, body = bits[0].strip(), bits[1], bits[2], bits[3]
        count += 1
        is_new = sha in fresh
        for addr in sorted({author.strip(), committer.strip()} - {""}):
            if rules.is_noreply_address(addr):
                continue
            row = per_addr.setdefault(addr.lower(), {"address": mask_address(addr), "commits": 0, "new": 0})
            row["commits"] += 1
            row["new"] += int(is_new)
            if is_new:
                findings.append({"kind": "commit-email", "commit": sha, "new": True,
                                 "excerpt": f"author/committer {mask_address(addr)} is not a noreply address"})
        lower = body.lower()
        for n, term, ci in terms:
            hay, needle = (lower, term.lower()) if ci else (body, term)
            if needle and needle in hay:
                findings.append({"kind": "commit-message", "commit": sha, "new": is_new, "term": n,
                                 "excerpt": f"the message carries term #{n}"})
    return {"commits": count, "addresses": sorted(per_addr.values(), key=lambda r: -r["commits"]),
            "findings": findings}


def failing(report: dict) -> "list[dict]":
    """The findings that fail the audit: those on commits not yet on origin/master."""
    return [f for f in report["findings"] if f.get("new")]


def render(report: dict) -> str:
    lines = [f"commits read: {report['commits']} (every ref; author, committer, message)"]
    for row in report["addresses"]:
        lines.append(f"  address {row['address']}: {row['commits']} commit(s), {row['new']} not yet on origin/master")
    old: "dict[int, int]" = {}
    for f in report["findings"]:
        if f["kind"] == "commit-message" and not f.get("new"):
            old[f["term"]] = old.get(f["term"], 0) + 1
    for n, k in sorted(old.items()):
        lines.append(f"  term #{n}: in {k} older commit message(s) (history: the owner's call)")
    for f in failing(report):
        lines.append(f"{f['commit'][:12]}: {f['kind']}: {f['excerpt']}")
    if not failing(report):
        lines.append("commits: nothing to fix in commits that are not yet on origin/master")
    return "\n".join(lines) + "\n"
