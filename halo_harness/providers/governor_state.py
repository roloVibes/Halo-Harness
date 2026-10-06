"""halo_harness.providers.governor_state -- Halo 2.0.5 round 4: the
Governor's persistence layer, split out of the core module so neither
file passes the house ~700-line ceiling.

What lives here (REVIEW.md items 1-8 made while porting the vendored kit
in plans/governor-import/governor-kit -- the kit is never imported):

- state_dir/paths: `<halo state dir>/governor/` (BRIDGE_TEST_HOME /
  BRIDGE_STATE_DIR scope it in tests), `GOVERNOR_STATE_DIR` still wins as
  an override so Halo can share one limiter with another tool on the box.
- the cross-platform lock (fcntl.flock / msvcrt byte-range) behind ONE
  context manager with a lock TIMEOUT (item 4): on expiry one warning,
  the degraded flag, and an in-process fallthrough for that call rather
  than a hang.
- one process-level RLock per bucket key plus a deep-copied in-process
  fallback view (item 5) -- sub-agents run on threads in this process.
- atomic state save with retry, schema version, corrupt-file recovery
  (reset with a warning, item from the older brief's port list).
- wall-clock reads with clock-jump CLAMPS (item 1): a cooldown in the
  future beyond the ladder's maximum, and refill intervals past 60 s, are
  clamped on load, so an NTP jump or a VM pause can neither freeze the
  fleet nor mint a token burst.
- the jsonl call log with 1 MB rotation (item 8).

Pure stdlib. No network. Never raises out of a state call: a Governor
that cannot persist still enforces its limits in-process (fail-loud, not
fail-silent -- `is_degraded()` carries the reason).
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import threading
import time
import warnings
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import fcntl
    _HAVE_FLOCK = True
except ImportError:  # pragma: no cover (Windows)
    fcntl = None
    _HAVE_FLOCK = False

if os.name == "nt":  # pragma: no cover (Windows)
    import msvcrt
    _HAVE_MSVCRT = True
else:
    msvcrt = None
    _HAVE_MSVCRT = False

#: Schema stamp in every state file; a mismatch resets the bucket.
STATE_SCHEMA = 2

#: One warning per process, then the flag (REVIEW item 4 / the older
#: brief's "loud warning"): a limiter that is not persisting is not
#: shared across sessions -- say so, never reset silently.
DEGRADED: Dict[str, Any] = {"degraded": False, "reason": None}

#: In-process fallback view, used only while degraded. Deep-copied on
#: read (REVIEW item 5) so two threads never share one dict.
_MEM_STATE: Dict[str, Dict[str, Any]] = {}

#: Process-level serialization per bucket key (REVIEW item 5).
_KEY_RLOCKS: Dict[str, "threading.RLock"] = {}
_KEY_RLOCKS_GUARD = threading.Lock()

#: REVIEW item 4: how long to fight for the cross-process lock before
#: warning once and falling through to the in-process view.
LOCK_TIMEOUT_S = 30.0

#: REVIEW item 1: the maximum cooldown the exponential ladder can produce
#: (cooldown_base 2.0 * 2^6) -- a wall-clock cooldown further in the
#: future than this (+ cap) is a clock jump, clamped on load.
MAX_LADDER_COOLDOWN_S = 2.0 * (2 ** 6)

#: REVIEW item 1: a refill interval longer than this is a clock jump; the
#: bucket refills for at most this much elapsed wall time.
MAX_REFILL_INTERVAL_S = 60.0

#: REVIEW item 8: rotate the per-bucket jsonl call log at this size.
LOG_ROTATE_BYTES = 1_000_000


def warn_once(message: str) -> None:
    """One `warnings.warn` per process per reason -- the fail-loud half
    of every degradation path in this module."""
    reason = message.splitlines()[0][:300]
    if DEGRADED["degraded"] and DEGRADED.get("reason") == reason:
        return
    DEGRADED["degraded"] = True
    DEGRADED["reason"] = reason
    warnings.warn(message, stacklevel=2)


def is_degraded() -> "Optional[str]":
    """None when state is persisting normally; otherwise the reason it
    is not (the one-line form, for `halo doctor` and `/gov`)."""
    return DEGRADED["reason"] if DEGRADED["degraded"] else None


def reset_degraded_for_tests() -> None:
    """The suite's per-test reset: clear the flag AND the in-process
    mirror (a fresh state dir must not inherit the previous test's
    cooldown -- the kit's own conftest did this for pytest)."""
    DEGRADED.update({"degraded": False, "reason": None})
    _MEM_STATE.clear()


def state_dir() -> Path:
    """`GOVERNOR_STATE_DIR` (the share-with-another-tool override) wins;
    otherwise `<halo state dir>/governor/`, scoped by BRIDGE_TEST_HOME /
    BRIDGE_STATE_DIR exactly like every other piece of Halo state."""
    override = os.environ.get("GOVERNOR_STATE_DIR")
    if override:
        base = Path(override)
    else:
        from halo_harness.config.paths import bridge_home
        base = Path(bridge_home()) / "governor"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        warn_once(f"governor: cannot create state dir {base}: {e}; "
                  "falling back to IN-PROCESS only limiting (not shared across sessions)")
    return base


def _safe(key: str) -> str:
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16] + "_" + "".join(
        c if c.isalnum() else "-" for c in key)[:40]


def paths(key: str) -> Tuple[Path, Path, Path]:
    """`(state.json, lock, log.jsonl)` for one bucket key."""
    base = state_dir() / _safe(key)
    return base.with_suffix(".json"), base.with_suffix(".lock"), base.with_suffix(".log.jsonl")


def _rlock_for(key: str) -> "threading.RLock":
    with _KEY_RLOCKS_GUARD:
        lk = _KEY_RLOCKS.get(key)
        if lk is None:
            lk = threading.RLock()
            _KEY_RLOCKS[key] = lk
        return lk


class LockFailed(Exception):
    """The cross-process lock could not be taken within LOCK_TIMEOUT_S.
    Callers fall through to the in-process view for THIS call (never a
    hang, never a silent full-budget reset)."""


class _Lock:
    """The one cross-platform critical section: `flock` on POSIX,
    `msvcrt.locking` byte-range on Windows, a timeout on both (REVIEW
    item 4). Entering ALSO takes the per-key process RLock (item 5) so
    two threads of this process serialize even while degraded."""

    def __init__(self, key: str):
        self._key = key
        self._p = paths(key)[1]
        self._fd = None
        self._proc_lock = _rlock_for(key)

    def __enter__(self):
        self._proc_lock.acquire()
        try:
            self._fd = os.open(str(self._p), os.O_CREAT | os.O_RDWR, 0o644)
            deadline = time.monotonic() + LOCK_TIMEOUT_S
            if _HAVE_FLOCK:
                import select
                while True:
                    try:
                        fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        return self
                    except OSError:
                        if time.monotonic() >= deadline:
                            self._release_fd()
                            raise LockFailed(f"lock {self._p} contended for {LOCK_TIMEOUT_S:.0f}s")
                        time.sleep(0.05)
            elif _HAVE_MSVCRT:  # pragma: no cover (Windows)
                if os.fstat(self._fd).st_size == 0:
                    os.write(self._fd, b"\0")  # a byte-range lock needs a byte to bite on
                while True:
                    os.lseek(self._fd, 0, os.SEEK_SET)
                    try:
                        msvcrt.locking(self._fd, msvcrt.LK_LOCK, 1)  # waits ~10s itself
                        return self
                    except OSError:
                        if time.monotonic() >= deadline:
                            self._release_fd()
                            raise LockFailed(f"lock {self._p} contended for {LOCK_TIMEOUT_S:.0f}s")
                        time.sleep(0.1)
            return self
        except Exception:
            self._proc_lock.release()
            raise

    def _release_fd(self) -> None:
        if self._fd is None:
            return
        try:
            if _HAVE_FLOCK:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            elif _HAVE_MSVCRT:  # pragma: no cover (Windows)
                os.lseek(self._fd, 0, os.SEEK_SET)
                try:
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass  # closing the handle releases the lock anyway
        except OSError:
            pass
        finally:
            os.close(self._fd)
            self._fd = None

    def __exit__(self, *exc_info):
        try:
            self._release_fd()
        finally:
            self._proc_lock.release()
        return False


def clamp_state_for_clock_jumps(st: Dict[str, Any], now: float,
                                retry_after_cap: float = 120.0) -> None:
    """REVIEW item 1, applied on every load: wall time is necessary
    across processes, but a jump (NTP, sleep/resume, a VM pause) must
    not leave `cooldown_until` far in the future (fleet frozen) or
    refill a huge token burst. A cooldown further out than the ladder's
    own maximum (plus the Retry-After cap, the only legitimate way past
    it) is clamped; a refill interval past 60 s refills for 60 s."""
    max_cd = MAX_LADDER_COOLDOWN_S + float(retry_after_cap)
    cd = st.get("cooldown_until", 0.0)
    if cd - now > max_cd:
        st["cooldown_until"] = now + max_cd
    last = st.get("last_refill", now)
    if last < now - MAX_REFILL_INTERVAL_S:
        st["last_refill"] = now - MAX_REFILL_INTERVAL_S


def load(key: str, params: Dict[str, Any], now: float) -> Dict[str, Any]:
    """The bucket state: the on-disk JSON when readable, else the
    deep-copied in-process view, else a fresh default. Corrupt JSON
    resets the bucket WITH a warning (never a crash); operator-tunable
    fields re-sync from `params` on every load so a raised quota takes
    effect immediately."""
    p = paths(key)[0]
    st: "Optional[Dict[str, Any]]" = None
    try:
        with open(p, "r", encoding="utf-8") as fh:
            st = json.load(fh)
        if not isinstance(st, dict) or st.get("schema") != STATE_SCHEMA:
            st = None
    except FileNotFoundError:
        pass
    except ValueError:
        # corrupt (or an older schema): reset the bucket WITH a plain
        # warning, but NOT the degraded flag -- persistence itself works
        # fine, the file's CONTENT was bad; degrade is only for "cannot
        # write state at all".
        import warnings
        warnings.warn(f"governor: state file {p.name} is corrupt (or an old schema) "
                      "-- bucket reset to defaults")
        st = None
    except OSError:
        pass
    if st is None:
        st = copy.deepcopy(_MEM_STATE.get(key)) if key in _MEM_STATE else None
        if st is None:
            from halo_harness.providers.governor import default_state
            st = default_state(key, params, now)
    ceiling = float(params.get("rate_rps", st.get("rate_ceiling", 2.0)))
    st["rate_ceiling"] = ceiling
    st["max_inflight"] = int(params.get("max_inflight", st.get("max_inflight", 2)))
    st["rate_floor"] = float(params.get("rate_floor", st.get("rate_floor", 0.25)))
    st["burst"] = float(params.get("burst", st.get("burst", ceiling)))
    st.setdefault("inflight", {})
    st.setdefault("waiters", {})
    st.setdefault("rate", ceiling)
    st.setdefault("tokens", 0.0)
    st.setdefault("last_refill", now)
    st.setdefault("cooldown_until", 0.0)
    clamp_state_for_clock_jumps(st, now, float(params.get("retry_after_cap", 120.0)))
    return st


def _replace(tmp: Path, target: Path) -> None:
    """`os.replace` with retry: on Windows the target can be transiently
    held open by an unlocked reader (`inspect`), which makes replace
    raise PermissionError."""
    for _ in range(50):
        try:
            os.replace(tmp, target)
            return
        except PermissionError:
            time.sleep(0.02)
    os.replace(tmp, target)  # still contended after ~1s: surface the error


def save(key: str, st: Dict[str, Any]) -> None:
    """Persist under the (already-held) lock. On failure: one warning,
    the degraded flag, and the in-process mirror keeps the limits alive
    for THIS process -- never a silent reset to full budget."""
    p = paths(key)[0]
    st["updated"] = time.time()
    tmp = p.with_name(p.name + f".tmp.{os.getpid()}")
    try:
        st["schema"] = STATE_SCHEMA
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(st, fh)
        _replace(tmp, p)
        _MEM_STATE[key] = copy.deepcopy(st)  # deep copy: the caller keeps mutating `st`
    except OSError as e:
        warn_once(f"governor: cannot persist state ({e}); rate limiting falls back to "
                  "IN-PROCESS only -- it is NOT shared across sessions. Fix the governor "
                  "state dir or its permissions.")
        _MEM_STATE[key] = copy.deepcopy(st)
        try:
            tmp.unlink()
        except OSError:
            pass


def append_log(key: str, record: Dict[str, Any]) -> None:
    """One JSON line per call, rotated at 1 MB to one `.1` generation
    (the same policy as the MCP logs). Never raises; called INSIDE the
    bucket lock (append-mode writes are not atomic on Windows)."""
    p = paths(key)[2]
    try:
        if p.exists() and p.stat().st_size > LOG_ROTATE_BYTES:
            rotated = p.with_name(p.name + ".1")
            try:
                rotated.unlink()
            except OSError:
                pass
            os.replace(p, rotated)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
    except OSError:
        pass


def read_recent_calls(key: str, limit: int = 30) -> "list[Dict[str, Any]]":
    p = paths(key)[2]
    out: "list[Dict[str, Any]]" = []
    try:
        with open(p, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except (FileNotFoundError, OSError, ValueError):
        return out
    for ln in lines[-limit:]:
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out
