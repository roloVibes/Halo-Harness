"""halo_harness.filelock -- a small advisory lock around a read-modify-write
of one shared state file (vibes/review.md finding 92).

`state.json`, `update-check.json` and `history.jsonl` are touched by every
halo process on the machine (two terminals, a background `--bg` run, the
launch-time update worker). Atomic replace keeps each write whole, but two
processes that each read, change and write back still lose one of the
changes; holding this lock across the read-modify-write fixes that.

The lock is on a sidecar file (`<target>.lock`), never on the target itself,
so `os.replace` of the target keeps working. It is advisory and best-effort:
if the lock cannot be taken within `timeout` seconds (a stuck holder, a
read-only directory) the body still runs and `acquired` is False, because a
state-file write must never hang or fail a launch. A filesystem without
locking (flock answers ENOSYS / ENOLCK / ...) runs the body at once, without
waiting the timeout. Do not nest two locks on the same file in one thread.
"""
from __future__ import annotations

import errno
import os
import time
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: msvcrt below
    fcntl = None

#: What flock() answers while another process holds the lock: worth a retry.
#: Any other error (ENOSYS, ENOLCK, EOPNOTSUPP, EINVAL: Lustre without the
#: flock mount option, NFS with no lock service) means this filesystem has no
#: locks at all; waiting the whole timeout for one only slows every launch.
_HELD_ERRNOS = frozenset(e for e in (getattr(errno, "EWOULDBLOCK", None), errno.EAGAIN,
                                     errno.EACCES, errno.EINTR) if e is not None)


def lock_unsupported(err: OSError) -> bool:
    """True when a failed POSIX flock() means "no locks on this filesystem",
    False when it means "held by someone else, try again"."""
    return getattr(err, "errno", None) not in _HELD_ERRNOS


def _try_lock(fh):
    """True: taken. False: held elsewhere, retry. None: this filesystem has
    no locks, do not wait."""
    try:
        if fcntl is not None:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError as e:
        return None if fcntl is not None and lock_unsupported(e) else False
    except ImportError:
        return None


def _unlock(fh) -> None:
    try:
        if fcntl is not None:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        else:
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except (OSError, ImportError):
        pass


@contextmanager
def file_lock(target, timeout: float = 5.0):
    """Hold an exclusive advisory lock for `target` while the body runs.
    Yields True when the lock was taken, False when the body runs without
    it."""
    lock_path = Path(str(target) + ".lock")
    fh = None
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(lock_path, "a+b")
    except OSError:
        fh = None
    acquired = False
    if fh is not None:
        deadline = time.monotonic() + max(0.0, timeout)
        while True:
            got = _try_lock(fh)
            if got:
                acquired = True
                break
            if got is None or time.monotonic() >= deadline:
                break
            time.sleep(0.02)
    try:
        yield acquired
    finally:
        if fh is not None:
            if acquired:
                _unlock(fh)
            try:
                fh.close()
            except OSError:
                pass
