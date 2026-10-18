"""tests.helpers.chrome_lock -- one headless Chrome at a time (Halo 3.1.0.0
round R1): a file lock under the scratch root (`<temp>/halo-tests/
chrome.lock`), so two drivers in one process (two threads) or in two
processes never have a Chrome open at the same time. Every Chrome the suite
or the capture tools start takes it: `tests.helpers.cdp.Chrome` from its
start to `close()`, the one-shot `--dump-dom` / `--screenshot` runs
(`chrome_driver.one_shot`, `tools/capture_screens.render_png`) around the
subprocess.

The lock is re-entrant within one thread (a driver that holds it while it
also runs a one-shot render does not wait on itself); the operating system
drops it when a process dies, so a killed driver never leaves it stuck.
stdlib only: `fcntl.flock` on POSIX, `msvcrt.locking` on Windows.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

DEFAULT_TIMEOUT_S = 900.0  # a driver run is a few minutes; a test's own subprocess timeout fires first
_POLL_S = 0.1


def scratch_root() -> Path:
    """The suite's shared scratch root: the same path for every process on
    this box (a scrubbed child environment keeps TEMP/TMPDIR)."""
    root = Path(tempfile.gettempdir()) / "halo-tests"
    root.mkdir(parents=True, exist_ok=True)
    return root


def default_lock_path() -> Path:
    return scratch_root() / "chrome.lock"


class _FileLock:
    """One lock file; re-entrant per thread, exclusive across threads and processes."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._threads = threading.Lock()
        self._owner = None
        self._depth = 0
        self._fh = None

    def acquire(self, timeout: float = DEFAULT_TIMEOUT_S) -> None:
        me = threading.get_ident()
        if self._owner == me:
            self._depth += 1
            return
        deadline = time.monotonic() + timeout
        if not self._threads.acquire(timeout=max(0.0, timeout)):
            raise TimeoutError(f"waited {timeout:.0f}s for the headless Chrome lock {self.path} (another driver in this process)")
        try:
            self._lock_file(deadline)
        except BaseException:
            self._threads.release()
            raise
        self._owner, self._depth = me, 1

    def release(self) -> None:
        if self._owner != threading.get_ident():
            raise RuntimeError("the headless Chrome lock is held by another thread")
        self._depth -= 1
        if self._depth:
            return
        self._owner = None
        try:
            self._unlock_file()
        finally:
            self._threads.release()

    @property
    def held(self) -> bool:
        return self._owner == threading.get_ident()

    # -- the file -------------------------------------------------------------------
    def _lock_file(self, deadline: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+b")
        start, said = time.monotonic(), False
        while True:
            if _try_lock(fh):
                self._fh = fh
                return
            if time.monotonic() >= deadline:
                fh.close()
                raise TimeoutError(f"waited for the headless Chrome lock {self.path} (another process holds it)")
            if not said and time.monotonic() - start > 2:
                print(f"waiting for the headless Chrome lock {self.path} (one Chrome at a time)", file=sys.stderr)
                said = True
            time.sleep(_POLL_S)

    def _unlock_file(self) -> None:
        fh, self._fh = self._fh, None
        if fh is None:
            return
        try:
            _unlock(fh)
        finally:
            fh.close()


if os.name == "nt":
    import msvcrt

    def _try_lock(fh) -> bool:
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    def _unlock(fh) -> None:
        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
else:
    import fcntl

    def _try_lock(fh) -> bool:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _unlock(fh) -> None:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass


_LOCKS: dict = {}
_LOCKS_GUARD = threading.Lock()


def lock_for(path: "Path | None" = None) -> _FileLock:
    """The process-wide lock object for `path` (default: the scratch root's chrome.lock)."""
    key = str(Path(path) if path is not None else default_lock_path())
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = _LOCKS[key] = _FileLock(Path(key))
        return lock


@contextmanager
def chrome_lock(path: "Path | None" = None, timeout: float = DEFAULT_TIMEOUT_S):
    """Hold the headless Chrome lock for the `with` body."""
    lock = lock_for(path)
    lock.acquire(timeout)
    try:
        yield lock
    finally:
        lock.release()
