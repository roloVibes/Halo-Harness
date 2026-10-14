"""halo_harness.orchestra.gitops -- the few git calls the run pipeline makes.

Every call runs `git` with an argument list (never a shell), captures text
as UTF-8, and never raises for a git failure: `git(...)` returns a
`CompletedProcess` and the helpers turn a nonzero exit into `GitError` only
where the pipeline cannot go on without the result.

Branch names: the finished branch is `orchestra/<run-id>`; a worker's branch
is `orchestra/<run-id>-worker-<n>`. (A ref `orchestra/<run-id>/worker-<n>`
cannot live beside a branch `orchestra/<run-id>`: git stores refs as files,
so one name cannot be both a file and a folder.)
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

GIT_TIMEOUT_S = 120
_IDENTITY = ("-c", "user.name=Halo Orchestra", "-c", "user.email=orchestra@halo.local")


class GitError(RuntimeError):
    pass


def _env() -> dict:
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(key, None)
    return env


def git(args: list, cwd, *, identity: bool = False, timeout: int = GIT_TIMEOUT_S) -> subprocess.CompletedProcess:
    """Run `git <args>` in `cwd`. Never raises; a missing git or a timeout
    comes back as returncode 1 with the reason in stderr."""
    argv = ["git", *(_IDENTITY if identity else ()), *[str(a) for a in args]]
    try:
        return subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, env=_env())
    except (OSError, subprocess.SubprocessError) as e:
        return subprocess.CompletedProcess(argv, 1, "", f"git: {e}")


def check(args: list, cwd, *, identity: bool = False) -> str:
    """`git(...)` that raises GitError with git's own last line on failure."""
    result = git(args, cwd, identity=identity)
    if result.returncode != 0:
        text = (result.stderr or result.stdout or "").strip().splitlines()
        raise GitError(f"git {' '.join(str(a) for a in args[:3])}: {text[-1] if text else 'failed'}")
    return result.stdout


def head(cwd, ref: str = "HEAD") -> str:
    return check(["rev-parse", ref], cwd).strip()


def branch_exists(repo, branch: str) -> bool:
    return git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], repo).returncode == 0


def finished_branch(run_id: str) -> str:
    return f"orchestra/{run_id}"


def worker_branch(run_id: str, lane: int) -> str:
    return f"orchestra/{run_id}-worker-{int(lane)}"


def worktree_add(repo, path, branch: str, base: str) -> Path:
    """A worktree at `path` on `branch`; the branch is created at `base` when
    it does not exist yet, and an existing worktree at `path` is reused."""
    path = Path(path)
    if (path / ".git").exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    git(["worktree", "prune"], repo)  # forget a worktree folder that was deleted by hand
    if branch_exists(repo, branch):
        check(["worktree", "add", str(path), branch], repo)
    else:
        check(["worktree", "add", "-b", branch, str(path), base], repo)
    return path


def worktree_remove(repo, path) -> bool:
    result = git(["worktree", "remove", "--force", str(path)], repo)
    return result.returncode == 0


def commit_all(cwd, message: str) -> Optional[str]:
    """Stage everything in the worktree and commit; the new sha, or None
    when there was nothing to commit."""
    check(["add", "-A", "--", ".", ":(exclude,glob)**/__pycache__/**", ":(exclude,glob)**/*.pyc"], cwd)
    if git(["diff", "--cached", "--quiet"], cwd).returncode == 0:
        return None
    check(["commit", "--no-verify", "-q", "-m", message], cwd, identity=True)
    return head(cwd)


def shortstat(repo, base: str, branch: str) -> int:
    """Lines changed (insertions + deletions) on `branch` since `base`."""
    out = git(["diff", "--shortstat", f"{base}...{branch}"], repo).stdout
    total = 0
    for part in out.split(","):
        words = part.split()
        if len(words) >= 2 and words[0].isdigit() and ("insertion" in words[1] or "deletion" in words[1]):
            total += int(words[0])
    return total


def is_ancestor(repo, ancestor: str, ref: str) -> bool:
    return git(["merge-base", "--is-ancestor", ancestor, ref], repo).returncode == 0


def merge_no_ff(cwd, branch: str, message: str) -> subprocess.CompletedProcess:
    """`git merge --no-ff` with diff3 conflict markers (ours, base, theirs)."""
    return git(["-c", "merge.conflictStyle=diff3", "merge", "--no-ff", "--no-edit", "-m", message, branch],
               cwd, identity=True)


def merge_in_progress(cwd) -> bool:
    return git(["rev-parse", "--verify", "--quiet", "MERGE_HEAD"], cwd).returncode == 0


def merge_abort(cwd) -> None:
    git(["merge", "--abort"], cwd)


def conflicted_files(cwd) -> list:
    out = git(["diff", "--name-only", "--diff-filter=U"], cwd).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def commit_merge(cwd) -> str:
    check(["commit", "--no-verify", "--no-edit", "-q"], cwd, identity=True)
    return head(cwd)


def show(repo, ref: str, path: str) -> Optional[str]:
    """The text of `path` at `ref`, or None when it is not there."""
    result = git(["show", f"{ref}:{path}"], repo)
    return result.stdout if result.returncode == 0 else None


def log_oneline(repo, ref: str, limit: int = 50) -> list:
    out = git(["log", "--oneline", f"-{int(limit)}", ref], repo).stdout
    return [line for line in out.splitlines() if line.strip()]


def merges_on(repo, ref: str, base: str) -> list:
    """Merge commits on `ref` since `base`, oldest first: `[sha, subject]`."""
    out = git(["log", "--merges", "--reverse", "--format=%H %s", f"{base}..{ref}"], repo).stdout
    return [line.split(" ", 1) for line in out.splitlines() if line.strip()]
