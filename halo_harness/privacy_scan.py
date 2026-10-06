"""halo_harness.privacy_scan -- the scan ENGINE behind `halo audit privacy`
(halo_harness/audit_cli.py): one `scan_text_content` function applies every
rule in halo_harness.privacy_rules to a blob of text exactly once, called
identically by the working-tree walk and the history walk below so the two
modes can never find different things for the same reason. Report lines
never carry the leaked value itself -- `_masked_excerpt` always substitutes
`<redacted>` for the matched span before anything is printed, logged, or
written to JSON.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from halo_harness.privacy_rules import (
    CIDR_SUFFIX_RE, DOT_LOCAL_RE, EMAIL_RE, EXTENDED_SCAN_ROOTS, EXTENDED_SCAN_TERMS,
    HOME_PATH_RE, JUNK_PATH_RE, KNOWN_LEAKED_PATH_FRAGMENTS, LAN_IP_RE, LINK_LOCAL_IP_RE,
    REMOVED_NAMES, STATE_DIR_MARKER, email_is_exempt, home_path_name_is_real, is_junk_path,
    is_self_excluded, load_allowlist,
)
from halo_harness.redact import _BEARER_RE, _TOKEN_PATTERNS

BINARY_SKIP_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".ttf", ".woff",
                         ".woff2", ".whl", ".zip")


def _line_no(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _masked_excerpt(text: str, start: int, end: int, *, context: int = 24) -> str:
    """Context is clamped to the CURRENT LINE only -- never a blind
    character-offset window. A window that crossed a newline used to
    pull in whatever sits on the next/previous line, which can be a
    SECOND, unrelated secret this isn't even the finding for (measured:
    a `machine-name` match one line above a planted e-mail address came
    back with that e-mail's local part sitting in its own "masked"
    excerpt)."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    left_bound = max(line_start, start - context)
    right_bound = min(line_end, end + context)
    left = text[left_bound:start]
    right = text[end:right_bound]
    prefix = "..." if left_bound > line_start else ""
    suffix = "..." if right_bound < line_end else ""
    return f"{prefix}{left}<redacted>{right}{suffix}"


def _extend_path_token(text: str, end: int) -> int:
    j = end
    while j < len(text) and text[j] not in " \t\n\r\"'`<>|":
        j += 1
    return j


def scan_text_content(text: str, *, rel_path: str, allowlist: "set[str]") -> "list[dict]":
    """Every content-based rule, applied once. Returns a list of
    {kind, line, excerpt} dicts (no path/commit -- the caller attaches
    those). `rel_path` is a posix-style path relative to the repo root,
    used only to scope the extended (case-insensitive) machine-name pass
    the same way the original regression guard scoped it."""
    findings: "list[dict]" = []

    for m in LAN_IP_RE.finditer(text):
        if CIDR_SUFFIX_RE.match(text[m.end():m.end() + 4]):
            continue  # a `/`-plus-digits CIDR suffix means a RANGE is being described, not a host literal
        if m.group(0) in allowlist:
            continue
        findings.append({"kind": "lan-ip", "line": _line_no(text, m.start()),
                          "excerpt": _masked_excerpt(text, m.start(), m.end())})

    for m in LINK_LOCAL_IP_RE.finditer(text):
        if CIDR_SUFFIX_RE.match(text[m.end():m.end() + 4]):
            continue
        if m.group(0) in allowlist:
            continue
        findings.append({"kind": "link-local-ip", "line": _line_no(text, m.start()),
                          "excerpt": _masked_excerpt(text, m.start(), m.end())})

    for m in HOME_PATH_RE.finditer(text):
        name = m.group(1)
        if name in allowlist or not home_path_name_is_real(name):
            continue
        token_end = _extend_path_token(text, m.end())
        kind = "state-dir-path" if STATE_DIR_MARKER in text[m.start():token_end] else "home-path"
        findings.append({"kind": kind, "line": _line_no(text, m.start()),
                          "excerpt": _masked_excerpt(text, m.start(1), m.end(1))})

    for fragment in KNOWN_LEAKED_PATH_FRAGMENTS:
        idx = text.find(fragment)
        while idx != -1:
            if fragment not in allowlist:
                findings.append({"kind": "home-path", "line": _line_no(text, idx),
                                  "excerpt": _masked_excerpt(text, idx, idx + len(fragment))})
            idx = text.find(fragment, idx + 1)

    for m in DOT_LOCAL_RE.finditer(text):
        if m.group(0) in allowlist:
            continue
        findings.append({"kind": "dot-local-hostname", "line": _line_no(text, m.start()),
                          "excerpt": _masked_excerpt(text, m.start(), m.end())})

    for name in REMOVED_NAMES:
        idx = text.find(name)
        while idx != -1:
            findings.append({"kind": "machine-name", "line": _line_no(text, idx),
                              "excerpt": _masked_excerpt(text, idx, idx + len(name))})
            idx = text.find(name, idx + 1)

    if any(rel_path == root or rel_path.startswith(root) for root in EXTENDED_SCAN_ROOTS):
        lower = text.lower()
        for term in EXTENDED_SCAN_TERMS:
            idx = lower.find(term)
            while idx != -1:
                findings.append({"kind": "machine-name", "line": _line_no(text, idx),
                                  "excerpt": _masked_excerpt(text, idx, idx + len(term))})
                idx = lower.find(term, idx + 1)

    for m in EMAIL_RE.finditer(text):
        addr = m.group(0)
        if addr in allowlist or email_is_exempt(addr):
            continue
        findings.append({"kind": "email", "line": _line_no(text, m.start()),
                          "excerpt": _masked_excerpt(text, m.start(), m.end())})

    for pat in _TOKEN_PATTERNS:
        for m in pat.finditer(text):
            if m.group(0) in allowlist:
                continue
            findings.append({"kind": "token", "line": _line_no(text, m.start()),
                              "excerpt": _masked_excerpt(text, m.start(), m.end())})

    for m in _BEARER_RE.finditer(text):
        if m.group(0) in allowlist:
            continue
        findings.append({"kind": "bearer-token", "line": _line_no(text, m.start()),
                          "excerpt": _masked_excerpt(text, m.start(), m.end())})

    return findings


def _git(args: "list[str]", cwd: Path) -> "subprocess.CompletedProcess":
    try:
        return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return subprocess.CompletedProcess(["git", *args], 1, "", f"git: {e}")


def _read_text(path: Path) -> Optional[str]:
    if path.suffix.lower() in BINARY_SKIP_SUFFIXES or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except Exception:
        return None


def _mask_path_for_display(path_text: str) -> str:
    """A junk-path finding's own path can ALSO embed a real username (a
    stray cache file under someone's real profile dir, not just a generic
    `%SystemDrive%\\...` system path) -- mask that one span if so."""
    m = HOME_PATH_RE.search(path_text)
    if m and home_path_name_is_real(m.group(1)):
        return path_text[:m.start(1)] + "<redacted>" + path_text[m.end(1):]
    return path_text


def tracked_and_untracked_files(repo_dir: Path) -> "list[str]":
    """Repo-relative POSIX paths: git-tracked + untracked-but-not-ignored
    (generalizes tests/test_privacy_scan.py's own `_tracked_files` to any
    repo) -- a plain walk (minus directories git never tracks) when there
    is no `.git` at all, so the scan still runs on a source-archive copy."""
    tracked = _git(["ls-files"], repo_dir)
    untracked = _git(["ls-files", "--others", "--exclude-standard"], repo_dir)
    if tracked.returncode == 0 and untracked.returncode == 0:
        lines = list(dict.fromkeys(tracked.stdout.splitlines() + untracked.stdout.splitlines()))
        return [line for line in lines if line.strip()]
    skip_dirs = {".git", "__pycache__", ".venv", "venv", "build", "dist", "wheels",
                 "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".eggs"}
    out: "list[str]" = []
    for root, dirs, names in os.walk(repo_dir):
        dirs[:] = sorted(d for d in dirs if d not in skip_dirs and not d.endswith(".egg-info"))
        for name in sorted(names):
            if name.endswith((".pyc", ".pyo")):
                continue
            out.append((Path(root) / name).resolve().relative_to(repo_dir).as_posix())
    return out


def scan_working_tree(repo_dir: Path) -> "list[dict]":
    """Default (non-`--history`) mode: every tracked + untracked,
    non-ignored file as it sits on disk right now."""
    allowlist = load_allowlist(repo_dir)
    findings: "list[dict]" = []
    for rel in tracked_and_untracked_files(repo_dir):
        if is_self_excluded(rel):
            continue
        if is_junk_path(rel):
            findings.append({"kind": "junk-path", "path": rel, "line": 0,
                              "excerpt": _mask_path_for_display(rel), "commit": None})
            continue
        text = _read_text(repo_dir / rel)
        if not text:
            continue
        for f in scan_text_content(text, rel_path=rel, allowlist=allowlist):
            f["path"] = rel
            f["commit"] = None
            findings.append(f)
    return findings


def _git_batch(args: "list[str]", cwd: Path, input_text: str) -> bytes:
    try:
        result = subprocess.run(["git", *args], cwd=str(cwd), input=input_text.encode("utf-8"),
                                 capture_output=True, timeout=180)
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        return b""


def distinct_blobs_and_paths(repo_dir: Path, *, since: Optional[str] = None) -> "tuple[list, dict]":
    """Every blob reachable from HEAD (or every blob new since `since`),
    deduplicated by blob id -- "scan each distinct blob once" -- plus every
    path each one was ever recorded at. `git rev-list --objects` lists
    trees and commits too; `cat-file --batch-check` filters down to blobs
    only (a tree's "path" is a directory name and must never be read as a
    file's text)."""
    range_args = [f"{since}..HEAD"] if since else ["--all"]
    objects = _git(["rev-list", "--objects", *range_args], repo_dir)
    if objects.returncode != 0:
        return [], {}
    all_paths: "dict[str, set]" = {}
    order: "list[str]" = []
    for line in objects.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split(" ", 1)
        sha = parts[0]
        path = parts[1] if len(parts) == 2 else ""
        if sha not in all_paths:
            order.append(sha)
            all_paths[sha] = set()
        if path:
            all_paths[sha].add(path)
    if not order:
        return [], {}
    check_out = _git_batch(["cat-file", "--batch-check=%(objectname) %(objecttype)"], repo_dir,
                            "\n".join(order) + "\n").decode("utf-8", "replace")
    blob_ids = [bits[0] for bits in (ln.split() for ln in check_out.splitlines()) if len(bits) == 2 and bits[1] == "blob"]
    blob_id_set = set(blob_ids)
    paths_by_blob = {sha: paths for sha, paths in all_paths.items() if sha in blob_id_set}
    return blob_ids, paths_by_blob


def _blob_contents(blob_ids: "list[str]", repo_dir: Path) -> "dict[str, str]":
    """One `git cat-file --batch` call for every distinct blob -- far
    faster than a subprocess per commit/rule. Binary/non-UTF-8 blobs are
    silently skipped (text scan only, same as the working-tree walk)."""
    if not blob_ids:
        return {}
    out = _git_batch(["cat-file", "--batch"], repo_dir, "\n".join(blob_ids) + "\n")
    pos, n = 0, len(out)
    contents: "dict[str, str]" = {}
    while pos < n:
        nl = out.find(b"\n", pos)
        if nl == -1:
            break
        header = out[pos:nl].decode("utf-8", "replace")
        pos = nl + 1
        parts = header.split()
        if len(parts) == 3 and parts[1] != "missing":
            sha, size = parts[0], int(parts[2])
            blob = out[pos:pos + size]
            pos += size + 1
            try:
                contents[sha] = blob.decode("utf-8")
            except UnicodeDecodeError:
                pass
    return contents


def _earliest_commit_for_blobs(blob_ids: "set[str]", repo_dir: Path, *, since: Optional[str] = None) -> "dict[str, tuple]":
    """`(commit, path)` of the FIRST commit (oldest) that wrote each blob
    id at some path -- one `git log --raw` walk for every blob of
    interest, not one subprocess per blob. `git log` is newest-first, so
    letting a later (older-commit) line unconditionally overwrite an
    earlier (newer-commit) one leaves the OLDEST match standing once the
    whole walk finishes. `--no-abbrev` is required: `--raw` shortens blob
    ids to 7 characters by default, which then never equal the full ids
    `rev-list --objects`/`cat-file --batch-check` use (measured: every
    lookup silently missed and every finding read back `commit: null`
    until this flag was added)."""
    range_args = [f"{since}..HEAD"] if since else ["--all"]
    result = _git(["log", "--raw", "--no-abbrev", "--format=COMMIT:%H", *range_args], repo_dir)
    mapping: "dict[str, tuple]" = {}
    current_commit = None
    for line in result.stdout.splitlines():
        if line.startswith("COMMIT:"):
            current_commit = line[len("COMMIT:"):].strip()
            continue
        if not line.startswith(":") or "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        bits = meta.split()
        if len(bits) < 4:
            continue
        new_sha = bits[3]
        if new_sha in blob_ids:
            mapping[new_sha] = (current_commit, path)
    return mapping


def _earliest_commit_for_path(path: str, repo_dir: Path, *, since: Optional[str] = None) -> Optional[str]:
    range_args = [f"{since}..HEAD"] if since else ["--all"]
    result = _git(["log", "--diff-filter=A", "--format=%H", "--follow", *range_args, "--", path], repo_dir)
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    return lines[-1] if lines else None


def scan_history(repo_dir: Path, *, since: Optional[str] = None) -> "list[dict]":
    """`--history` mode: every distinct blob reachable from HEAD (or new
    since `since`), each scanned exactly once, reported at the EARLIEST
    commit:path that introduced it."""
    allowlist = load_allowlist(repo_dir)
    blob_ids, paths_by_blob = distinct_blobs_and_paths(repo_dir, since=since)
    findings: "list[dict]" = []

    junk_paths = {p for paths in paths_by_blob.values() for p in paths if is_junk_path(p)}
    for path in sorted(junk_paths):
        commit = _earliest_commit_for_path(path, repo_dir, since=since)
        findings.append({"kind": "junk-path", "path": path, "line": 0,
                          "excerpt": _mask_path_for_display(path), "commit": commit})

    contents = _blob_contents(blob_ids, repo_dir)
    per_blob_findings: "dict[str, list]" = {}
    for sha, text in contents.items():
        paths = paths_by_blob.get(sha) or set()
        rel = sorted(paths)[0] if paths else "<unknown>"
        if is_self_excluded(rel):
            continue
        found = scan_text_content(text, rel_path=rel, allowlist=allowlist)
        if found:
            for f in found:
                f["path"] = rel
            per_blob_findings[sha] = found

    commit_map = _earliest_commit_for_blobs(set(per_blob_findings), repo_dir, since=since)
    for sha, found in per_blob_findings.items():
        commit, logged_path = commit_map.get(sha, (None, None))
        for f in found:
            f["commit"] = commit
            if logged_path:
                f["path"] = logged_path
            findings.append(f)
    return findings


def summarize_history(findings: "list[dict]") -> dict:
    """Groups `scan_history`'s flat finding list into the two buckets the
    rewrite plan needs: paths to purge entirely (the `junk-path` kind --
    the path itself is the problem) versus paths that stay, with specific
    lines/literals needing text replacement."""
    purge: "dict[str, dict]" = {}
    replace: "dict[str, dict]" = {}
    for f in findings:
        if f["kind"] == "junk-path":
            purge.setdefault(f["path"], {"commit": f.get("commit"), "excerpt": f["excerpt"]})
        else:
            entry = replace.setdefault(f["path"], {"kinds": set(), "count": 0, "commit": f.get("commit")})
            entry["kinds"].add(f["kind"])
            entry["count"] += 1
            if f.get("commit") and not entry.get("commit"):
                entry["commit"] = f["commit"]
    return {
        "purge_entirely": [{"path": p, **v} for p, v in sorted(purge.items())],
        "text_replacements": [{"path": p, "kinds": sorted(v["kinds"]), "count": v["count"], "commit": v["commit"]}
                               for p, v in sorted(replace.items())],
    }
