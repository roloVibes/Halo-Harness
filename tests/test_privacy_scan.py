"""tests.test_privacy_scan -- W5 (2026-10-02, from the first privacy pass;
see plans/2.0.9-review-privacy-brief.md section C) and its W5b follow-up:
guards the content scrub `tests/helpers/fake_home.py`, `test_memory.py`,
`test_frontmatter.py`, `test_loop_headless.py`, `test_mcp_catalog.py`,
`test_paths.py`, `docs/harness/ACCEPTANCE-2026-09-25.md` and
`docs/harness/INSTALL.md` just went through so it cannot quietly
regress. Scans the TRACKED tree only (`git ls-files` -- history is a
separate question, now covered by `halo audit privacy --history`; see
plans/2.0.4-history-rewrite-plan.md) for: LAN addresses, real home paths,
the exact machine/project/hobby-gear/work-tool names this pass removed,
and key-shaped fragments outside `tests/privacy_scan_allowlist.txt`'s
known fakes.

2.0.4 round 1: the rule set moved to halo_harness.privacy_rules (behind
`halo audit privacy`) and is only imported here, so the two never drift
apart; the home-path check is the audit's own (any real account name, via
`home_path_name_is_real`'s placeholder list). 3.4.1.2 (F8): the name terms
cover the whole tree and a report names a term by its number, never the
term (tests/test_privacy_gate.py prints whether the name checks are on).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from halo_harness.redact import _BEARER_RE, _TOKEN_PATTERNS
# 2.0.4 round 1: the rule set below USED to be defined locally in this
# file; it now lives in halo_harness.privacy_rules (the production module
# behind `halo audit privacy`) and is only imported here, so the audit
# command and this regression guard can never quietly drift apart again.
# Aliased under the old local names so every call site below (and every
# `plans/*privacy*` reference to this file) still reads the same way.
from halo_harness.privacy_rules import (
    EXTENDED_SCAN_TERMS as _EXTENDED_SCAN_TERMS,
    NAME_CHECK_EXEMPT_RELPATHS as _NAME_CHECK_EXEMPT,
    HOME_PATH_RE as _HOME_PATH_RE,
    KNOWN_LEAKED_PATH_FRAGMENTS as _KNOWN_LEAKED_PATH_FRAGMENTS,
    LAN_IP_RE as _LAN_IP_RE,
    REMOVED_NAMES as _REMOVED_NAMES,
    home_path_name_is_real as _home_path_name_is_real,
    is_self_excluded as _is_self_excluded,
    load_allowlist as _shared_load_allowlist,
)

REPO_DIR = Path(__file__).resolve().parent.parent
ALLOWLIST_PATH = REPO_DIR / "tests" / "privacy_scan_allowlist.txt"
test, TESTS = new_registry()


def _tracked_files() -> "list[Path]":
    """`git ls-files` PLUS `git ls-files --others --exclude-standard` (2.0.3
    round 4 fix-pass note: a worker's own NEW, still-untracked files went
    unscanned until staged -- two "Bearer <fake-token>" literals in a new
    test slipped through the worker's own full run this way and only
    surfaced at review) in a git checkout; otherwise (the tar copy the
    Kali suite runs from, a source archive) a walk of the tree minus the
    directories git never tracks, so the scan runs on every copy the
    suites run from instead of erroring out where there is no `.git`."""
    # This file names every banned string, so it is the one tracked file
    # the scan must never read (untracked while it was written, which hid
    # the self-match until the first git-less run on the Kali copy).
    self_path = Path(__file__).resolve()
    try:
        tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=str(REPO_DIR), check=True)
        untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
                                    capture_output=True, text=True, cwd=str(REPO_DIR), check=True)
        lines = list(dict.fromkeys(tracked.stdout.splitlines() + untracked.stdout.splitlines()))
        return [REPO_DIR / line for line in lines if line.strip() and (REPO_DIR / line).resolve() != self_path]
    except (OSError, subprocess.CalledProcessError):
        pass
    skip_dirs = {".git", "__pycache__", ".venv", "venv", "build", "dist", "wheels", "node_modules",
                 ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".eggs"}
    files: "list[Path]" = []
    for root, dirs, names in os.walk(REPO_DIR):
        dirs[:] = sorted(d for d in dirs if d not in skip_dirs and not d.endswith(".egg-info"))
        for name in names:
            if name.endswith((".pyc", ".pyo")):
                continue
            candidate = Path(root) / name
            if candidate.resolve() == self_path:
                continue
            files.append(candidate)
    return files


def _load_allowlist() -> "set[str]":
    return _shared_load_allowlist(REPO_DIR)


def _rel_posix(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_DIR).as_posix()
    except ValueError:
        return str(path)


# Binary content a text scan should never try to decode -- an SVG
# snapshot's own normalized content is still plain text and IS scanned (a
# real leak could hide there too); these genuinely aren't text.
_SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".ttf", ".woff", ".woff2", ".whl", ".zip")


def _read_text(path: Path) -> Optional[str]:
    if path.suffix.lower() in _SKIP_SUFFIXES or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


@test
def test_no_lan_addresses_anywhere_in_the_tracked_tree(ctx: Ctx):
    """2.0.4 round 1: `tests/test_audit_privacy.py` now legitimately
    plants a real-shaped RFC1918 address as a fixture (`halo audit
    privacy`'s own `lan-ip` kind needs something that shape to detect) --
    excluded the same way this file has always excluded itself."""
    problems = []
    for path in _tracked_files():
        if _is_self_excluded(_rel_posix(path)):
            continue
        text = _read_text(path)
        if not text:
            continue
        for m in _LAN_IP_RE.finditer(text):
            line_no = text.count("\n", 0, m.start()) + 1
            problems.append(f"{path.relative_to(REPO_DIR)}:{line_no}: LAN address {m.group(0)!r}")
    ctx.check("no LAN addresses found:\n  " + "\n  ".join(problems), not problems)


@test
def test_no_real_home_paths_anywhere_in_the_tracked_tree(ctx: Ctx):
    """Generalized in 2.0.4 round 1 to use the SAME `_HOME_PATH_RE` +
    `_home_path_name_is_real` check `halo audit privacy` runs (any real
    account name, not just the one this pass originally found), plus the
    specific longer fragment (`/home/kali/Documents`) a bare username
    check alone would miss -- `_KNOWN_LEAKED_PATH_FRAGMENTS`. Files that
    legitimately NAME these strings as data (this module, the shared rule
    module itself) are excluded the same way `_tracked_files()` already
    excludes this file."""
    problems = []
    for path in _tracked_files():
        if _is_self_excluded(_rel_posix(path)):
            continue
        text = _read_text(path)
        if not text:
            continue
        for m in _HOME_PATH_RE.finditer(text):
            if not _home_path_name_is_real(m.group(1)):
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            problems.append(f"{path.relative_to(REPO_DIR)}:{line_no}: real home path (account {m.group(1)!r})")
        for fragment in _KNOWN_LEAKED_PATH_FRAGMENTS:
            idx = text.find(fragment)
            while idx != -1:
                line_no = text.count("\n", 0, idx) + 1
                problems.append(f"{path.relative_to(REPO_DIR)}:{line_no}: known leaked path fragment {fragment!r} is back")
                idx = text.find(fragment, idx + 1)
    ctx.check("no real home paths found:\n  " + "\n  ".join(problems), not problems)


@test
def test_no_removed_machine_or_project_names_regress(ctx: Ctx):
    problems = []
    allowed = _load_allowlist()
    for path in _tracked_files():
        if _is_self_excluded(_rel_posix(path)):
            continue
        text = _read_text(path)
        if not text:
            continue
        if _rel_posix(path) in _NAME_CHECK_EXEMPT:
            continue
        for n, name in enumerate(_REMOVED_NAMES, 1):
            if name in allowed:
                continue
            idx = text.find(name)
            if idx == -1:
                continue
            line_no = text.count("\n", 0, idx) + 1  # 3.4.1.2: the term's number, never the term (the list is private)
            problems.append(f"{path.relative_to(REPO_DIR)}:{line_no}: private term #{n} is back")
    ctx.check("no removed machine/project names regressed:\n  " + "\n  ".join(problems), not problems)


def _extended_scan_files() -> "list[Path]":
    out: "list[Path]" = []
    for path in _tracked_files():
        rel = _rel_posix(path)
        if _is_self_excluded(rel):
            continue
        if rel not in _NAME_CHECK_EXEMPT:  # 3.4.1.2 (F8): the whole tree, not five roots
            out.append(path)
    return out


@test
def test_no_hobby_gear_vendor_or_owner_name_terms_case_insensitive(ctx: Ctx):
    """Release review finding 38 / W6b section C: a broader net than
    `_REMOVED_NAMES` above -- case-insensitive, generic substrings for the
    owner's hobby gear/vendor names and the owner's own first/last name,
    across the whole tracked tree since 3.4.1.2 (LICENSE names its holder
    on purpose: privacy_rules.NAME_CHECK_EXEMPT_RELPATHS)."""
    problems = []
    allow_lower = {a.lower() for a in _load_allowlist()}
    for path in _extended_scan_files():
        text = _read_text(path)
        if not text:
            continue
        lower = text.lower()
        for n, term in enumerate(_EXTENDED_SCAN_TERMS, len(_REMOVED_NAMES) + 1):
            needle = term.lower()
            if needle in allow_lower:
                continue
            idx = lower.find(needle)
            while idx != -1:
                line_no = text.count("\n", 0, idx) + 1
                problems.append(f"{path.relative_to(REPO_DIR)}:{line_no}: private term #{n} found")
                idx = lower.find(needle, idx + 1)
    ctx.check("no hobby-gear/vendor/owner-name terms found:\n  " + "\n  ".join(problems), not problems)


@test
def test_no_key_shaped_fragments_outside_the_allowlist(ctx: Ctx):
    allowed = _load_allowlist()
    ctx.check("the allowlist file itself exists", ALLOWLIST_PATH.exists())
    problems = []
    for path in _tracked_files():
        if path == ALLOWLIST_PATH:
            continue  # its own exact fake values would obviously "match"
        text = _read_text(path)
        if not text:
            continue
        for pat in _TOKEN_PATTERNS:
            for m in pat.finditer(text):
                if m.group(0) in allowed:
                    continue
                line_no = text.count("\n", 0, m.start()) + 1
                problems.append(f"{path.relative_to(REPO_DIR)}:{line_no}: key-shaped fragment "
                                 f"{m.group(0)!r} (not in tests/privacy_scan_allowlist.txt)")
        for m in _BEARER_RE.finditer(text):
            if m.group(0) in allowed:
                continue
            line_no = text.count("\n", 0, m.start()) + 1
            problems.append(f"{path.relative_to(REPO_DIR)}:{line_no}: bearer-token-shaped fragment "
                             f"{m.group(0)!r} (not in tests/privacy_scan_allowlist.txt)")
    ctx.check("no un-allowlisted key-shaped fragments found:\n  " + "\n  ".join(problems), not problems)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
