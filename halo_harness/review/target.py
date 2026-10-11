"""halo_harness.review.target -- resolve `[target]` into a `ReviewTarget`.

Forms: nothing (the current branch against its merge base with the default
branch; a dirty tree adds the working-tree changes), a diff range `a..b`, a
branch or other ref, a pull request (`#123` or `123`, through `gh`), or paths
and globs (reviewed as-is, no diff).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from halo_harness.review.target_model import ReviewTarget, TargetError
from halo_harness.review.target_paths import MAX_FILE_BYTES as _MAX_FILE_BYTES, paths_target as _paths_target

__all__ = ["ReviewTarget", "TargetError", "resolve_target"]

_MAX_UNTRACKED = 40
_GIT_TIMEOUT_S = 60


def _run(cmd: "list[str]", cwd: Path) -> "tuple[int, str, str]":
    try:
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, timeout=_GIT_TIMEOUT_S)
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: command not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"{cmd[0]}: timed out after {_GIT_TIMEOUT_S} s"
    return (r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace"))


def _git(cwd: Path, *args: str) -> "tuple[int, str, str]":
    return _run(["git", *args], cwd)


def _names(out: str) -> "list[str]":
    return [n for n in out.split("\0") if n]


def _is_repo(cwd: Path) -> bool:
    rc, out, _ = _git(cwd, "rev-parse", "--is-inside-work-tree")
    return rc == 0 and out.strip() == "true"


def _verify_ref(cwd: Path, ref: str) -> bool:
    return bool(ref) and not ref.startswith("-") and _git(cwd, "rev-parse", "--verify", "--quiet", ref + "^{commit}")[0] == 0


def _default_branch(cwd: Path) -> Optional[str]:
    rc, out, _ = _git(cwd, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    if rc == 0 and out.strip() and _verify_ref(cwd, out.strip()):
        return out.strip()
    for name in ("main", "master", "trunk", "develop"):
        for ref in (name, f"origin/{name}"):
            if _verify_ref(cwd, ref):
                return ref
    return None


def _sha(cwd: Path, ref: str) -> str:
    return _git(cwd, "rev-parse", ref + "^{commit}")[1].strip()


def _dirty(cwd: Path) -> bool:
    return bool(_git(cwd, "status", "--porcelain")[1].strip())


def _untracked_diff(cwd: Path) -> "tuple[str, list[str]]":
    """Synthetic new-file diffs for untracked files (a dirty tree's new files)."""
    names = _names(_git(cwd, "ls-files", "--others", "--exclude-standard", "-z")[1])[:_MAX_UNTRACKED]
    parts, used = [], []
    for name in names:
        p = cwd / name
        try:
            if not p.is_file() or p.stat().st_size > _MAX_FILE_BYTES:
                continue
            data = p.read_bytes()
        except OSError:
            continue
        if b"\0" in data:
            continue
        lines = data.decode("utf-8", "replace").splitlines()
        body = "".join(f"+{ln}\n" for ln in lines)
        parts.append(f"diff --git a/{name} b/{name}\nnew file mode 100644\n--- /dev/null\n+++ b/{name}\n"
                     f"@@ -0,0 +1,{len(lines)} @@\n{body}")
        used.append(name)
    return "".join(parts), used


def _diff_against(cwd: Path, base: str, *, include_untracked: bool) -> "tuple[str, list[str]]":
    rc, text, err = _git(cwd, "diff", "--no-color", "--no-ext-diff", "-U3", base)
    if rc != 0:
        raise TargetError(f"git diff failed: {err.strip() or 'unknown error'}")
    files = _names(_git(cwd, "diff", "--name-only", "-z", base)[1])
    if include_untracked:
        extra, used = _untracked_diff(cwd)
        text += extra
        files += [f for f in used if f not in files]
    return text, files


def _worktree_target(cwd: Path, why: str) -> ReviewTarget:
    text, files = _diff_against(cwd, "HEAD", include_untracked=True)
    if not text.strip():
        raise TargetError(f"nothing to review: {why} and the working tree is clean "
                          f"(give a range such as HEAD~1..HEAD, a branch, a PR number, or paths)")
    return ReviewTarget("worktree", "working tree vs HEAD", text, files, base="HEAD", head="working tree", cwd=str(cwd))


def _default_target(cwd: Path) -> ReviewTarget:
    default = _default_branch(cwd)
    if default is None:
        return _worktree_target(cwd, "no default branch was found to compare against")
    head_name = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")[1].strip() or "HEAD"
    base = _git(cwd, "merge-base", default, "HEAD")[1].strip()
    if not base or base == _sha(cwd, "HEAD"):
        return _worktree_target(cwd, f"{head_name} has no commits beyond {default}")
    text, files = _diff_against(cwd, base, include_untracked=True)
    if not text.strip():
        raise TargetError(f"nothing to review: {head_name} matches {default}")
    return ReviewTarget("branch", f"{head_name} vs {default} (merge base {base[:8]})", text, files,
                        base=base, head=head_name, cwd=str(cwd))


def _range_target(cwd: Path, spec: str) -> ReviewTarget:
    sep = "..." if "..." in spec else ".."
    left, _, right = spec.partition(sep)
    left, right = left or "HEAD", right or "HEAD"
    for ref in (left, right):
        if not _verify_ref(cwd, ref):
            raise TargetError(f"unknown revision {ref!r} in range {spec!r}")
    rc, text, err = _git(cwd, "diff", "--no-color", "--no-ext-diff", "-U3", f"{left}{sep}{right}")
    if rc != 0:
        raise TargetError(f"git diff failed: {err.strip() or 'unknown error'}")
    if not text.strip():
        raise TargetError(f"nothing to review: {spec} has no differences")
    files = _names(_git(cwd, "diff", "--name-only", "-z", f"{left}{sep}{right}")[1])
    return ReviewTarget("range", spec, text, files, base=left, head=right, cwd=str(cwd))


def _ref_target(cwd: Path, ref: str) -> ReviewTarget:
    default = _default_branch(cwd)
    if default is None:
        raise TargetError(f"no default branch found to compare {ref!r} against; give a range such as main..{ref}")
    base = _git(cwd, "merge-base", default, ref)[1].strip()
    if not base or base == _sha(cwd, ref):
        raise TargetError(f"nothing to review: {ref} has no commits beyond {default}")
    rc, text, err = _git(cwd, "diff", "--no-color", "--no-ext-diff", "-U3", base, ref)
    if rc != 0:
        raise TargetError(f"git diff failed: {err.strip() or 'unknown error'}")
    files = _names(_git(cwd, "diff", "--name-only", "-z", base, ref)[1])
    return ReviewTarget("branch", f"{ref} vs {default} (merge base {base[:8]})", text, files,
                        base=base, head=ref, cwd=str(cwd))


def _pr_target(cwd: Path, number: str) -> ReviewTarget:
    gh = shutil.which("gh")
    if gh is None:
        raise TargetError("reviewing a pull request needs the GitHub CLI (`gh`) on PATH")
    rc, text, err = _run([gh, "pr", "diff", number], cwd)
    if rc != 0:
        raise TargetError(f"gh pr diff {number} failed: {err.strip() or 'unknown error'}")
    if not text.strip():
        raise TargetError(f"nothing to review: PR #{number} has an empty diff")
    meta: dict = {}
    rc, out, _ = _run([gh, "pr", "view", number, "--json", "number,title,headRefName,baseRefName,files,url"], cwd)
    if rc == 0:
        try:
            parsed = json.loads(out)
            meta = parsed if isinstance(parsed, dict) else {}
        except ValueError:
            meta = {}
    files = [f.get("path") for f in (meta.get("files") or []) if isinstance(f, dict) and f.get("path")]
    target = ReviewTarget("pr", f"PR #{meta.get('number') or number}: {meta.get('title') or ''}".rstrip(": ").strip(),
                          text, files, base=meta.get("baseRefName"), head=meta.get("headRefName"), cwd=str(cwd))
    if not target.files:
        target.files = list(target.file_diffs())
    return target


def resolve_target(tokens: "list[str]", cwd: Path) -> ReviewTarget:
    """Raises `TargetError` with a user-facing message when nothing can be reviewed."""
    cwd = Path(cwd)
    tokens = [t for t in (tokens or []) if t]
    if not tokens:
        if not _is_repo(cwd):
            raise TargetError("not inside a git repository -- give paths or a glob to review files as they are")
        return _default_target(cwd)
    if len(tokens) > 1:
        return _paths_target(cwd, tokens)
    tok = tokens[0]
    if tok.startswith("#") and tok[1:].isdigit():
        return _pr_target(cwd, tok[1:])
    if tok.isdigit():
        return _pr_target(cwd, tok)
    full = tok if os.path.isabs(tok) else str(cwd / tok)
    is_file, exists = os.path.isfile(full), os.path.exists(full)
    if any(c in tok for c in "*?["):
        return _paths_target(cwd, tokens)
    if _is_repo(cwd) and not is_file:
        if ".." in tok and not exists:
            return _range_target(cwd, tok)
        if _verify_ref(cwd, tok):
            return _ref_target(cwd, tok)
    if exists:
        return _paths_target(cwd, tokens)
    raise TargetError(f"{tok!r} is not a revision range, a branch, a PR number, or an existing path")
