"""halo_harness.update_checkout -- the git half of `halo update` for a clone
the installer made. The one-liner installers `git checkout --detach <tag>`,
so a plain `git pull --ff-only` can never succeed there ("You are not
currently on a branch"); a detached clone is moved with `fetch --tags` plus
`checkout --detach <target>` instead. Every probe goes through the caller's
`run_fn` and is best-effort (any failure reads as "not detached").
"""

from __future__ import annotations

from typing import Callable, Optional


def _git(run_fn: Callable, checkout: str, *args: str):
    return run_fn(["git", "-C", checkout, *args], capture_output=True, text=True, timeout=5)


def is_detached(checkout: str, run_fn: Callable) -> bool:
    """True only when `git symbolic-ref -q HEAD` exits 1 (HEAD is not a
    branch). Any other outcome -- a branch, a failed probe, no git --
    is False so the ordinary pull path stays the default."""
    try:
        return _git(run_fn, checkout, "symbolic-ref", "-q", "HEAD").returncode == 1
    except Exception:
        return False


def exact_tag(checkout: str, run_fn: Callable) -> Optional[str]:
    """The tag HEAD sits exactly on (`git describe --exact-match --tags`),
    else None."""
    try:
        r = _git(run_fn, checkout, "describe", "--exact-match", "--tags", "HEAD")
        if r.returncode == 0:
            return (r.stdout or "").strip() or None
    except Exception:
        pass
    return None


def sync_cmd(checkout: str, quote: Callable[[str], str], *, detached: bool,
             target: Optional[str]) -> str:
    """The shell command that brings the clone to the wanted source: the
    old fast-forward pull on a branch, `fetch --tags --force` plus
    `checkout --detach <target>` (a tag, or `origin/<branch>`) on a
    detached clone."""
    where = quote(checkout)
    if not detached:
        return f"git -C {where} pull --ff-only"
    return (f"git -C {where} fetch --tags --force origin && "
            f"git -C {where} checkout --detach {target or 'origin/master'}")


def pick_target(channel: Optional[str], avail: Optional[dict], to: Optional[str] = None) -> Optional[str]:
    """The ref a detached clone should move to: an explicit `--to`, else
    the newest tag on `stable`, else `origin/<branch>` on `main`."""
    if to:
        return to
    avail = avail or {}
    ref = avail.get("ref")
    if channel == "stable":
        return ref or None
    return f"origin/{ref}" if ref else None
