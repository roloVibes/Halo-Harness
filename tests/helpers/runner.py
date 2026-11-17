"""tests.helpers.runner -- the Ctx/@test/run_all/exit-code pattern, copied
in SPIRIT (not byte-for-byte -- test_bridge.py's own Ctx is proxy-specific:
BridgeProc/MockUpstream/dbx_bridge fixtures this suite has no use for) from
test_bridge.py's house style: stdlib only, a single global TESTS registry
per test MODULE (each test_*.py file gets its own registry+run_all via
`new_registry()`, so tests/run_all.py can import every test_*.py module and
run each one's tests without them colliding in one shared list), nonzero
exit on any real failure, gate on the exit code -- never on printed text.

Usage in a test_*.py file:

    from tests.helpers.runner import new_registry

    test, TESTS = new_registry()

    @test
    def test_something(ctx):
        ctx.check("1 == 1", 1 == 1)

    if __name__ == "__main__":
        import sys
        from tests.helpers.runner import Ctx, run_all, print_results
        ctx = Ctx()
        results, passed, failed, skipped = run_all(TESTS, ctx)
        sys.exit(print_results(results, passed, failed, skipped))
"""

from __future__ import annotations

import os

# (No HALO_CLAUDE_EXE default here: the Claude Code launcher tests in
# test_bridge.py read that variable as a bare executable path, so a quoted
# "python fake.py" value broke them on CI. The connector modules that need
# the fake claude set BRIDGE_CLAUDE_EXE themselves.)
import shutil
import tempfile
import threading
import time
import traceback
from typing import Callable

# 3.6.0.1 (test-rig batch 2): variables that move Claude's or Halo's config/state OUT of the scratch home
# (`claude_config_dir()`/`claude_json_path()` follow CLAUDE_CONFIG_DIR over home(); the governor follows
# GOVERNOR_STATE_DIR over bridge_home()). A developer who keeps several Claude profiles has CLAUDE_CONFIG_DIR set in
# the shell, and a test that writes `.claude.json`, settings, agents or skills would write into that REAL folder.
# They are removed from this process's environment the moment the rig is imported (every test module imports it), so
# every child a test starts inherits the clean environment; tests/run_all.py removes them again before each module
# (a module that set one and did not restore it cannot hand it to the next). A test that needs one sets it itself, to
# a folder under its own scratch home. What was set before the scrub is kept here for run_all's real-folder watch.
REAL_HOME_MOVERS = ("CLAUDE_CONFIG_DIR", "GOVERNOR_STATE_DIR")
REAL_HOME_MOVERS_AT_START = {k: os.environ[k] for k in REAL_HOME_MOVERS if k in os.environ}


def scrub_real_home_movers() -> "list[str]":
    """Remove every REAL_HOME_MOVERS variable from os.environ; returns the names that were set."""
    gone = [k for k in REAL_HOME_MOVERS if k in os.environ]
    for k in gone:
        os.environ.pop(k, None)
    return gone


scrub_real_home_movers()

# NEW (post-H9 acceptance): a real Linux run of this suite left thousands
# of /tmp/addrule-*, /tmp/rolo*, /tmp/tmp* directories behind -- the
# overwhelmingly common `Path(tempfile.mkdtemp(prefix=...))` pattern used
# throughout this test suite (and a few real halo_harness/ code paths
# exercised BY it) has no matching cleanup anywhere. Rather than hand-edit
# cleanup into every one of the many call sites (error-prone, and every
# FUTURE test would need to remember it too), `tempfile.mkdtemp` itself is
# monkeypatched, process-wide, to record every directory it creates;
# `cleanup_tracked_temp_dirs()` removes them all at once, best-effort, at
# the very end of a suite run (tests/run_all.py, test_bridge.py,
# test_tui.py's own `__main__` blocks) -- safe because nothing runs AFTER
# that point that could still need one of them.
_tracked_temp_dirs: "list[str]" = []
_tracked_lock = threading.Lock()
_real_mkdtemp = tempfile.mkdtemp
_tracking_installed = False


def _tracking_mkdtemp(*args, **kwargs) -> str:
    path = _real_mkdtemp(*args, **kwargs)
    with _tracked_lock:
        _tracked_temp_dirs.append(path)
    return path


def install_temp_dir_tracking() -> None:
    """Idempotent -- safe to call from more than one suite entry point in
    the same process (it never has been, but costs nothing to guard)."""
    global _tracking_installed
    if _tracking_installed:
        return
    tempfile.mkdtemp = _tracking_mkdtemp
    _tracking_installed = True


def cleanup_tracked_temp_dirs() -> int:
    """Removes every directory `tempfile.mkdtemp` created since
    `install_temp_dir_tracking()` was installed -- best-effort (a
    directory a test already removed itself, or one a background thread/
    still-live subprocess has a handle open on, most commonly on Windows,
    is silently skipped rather than raising). Returns how many were
    actually removed. Safe to call more than once (the tracked list is
    drained on each call, so a second call has nothing left to do)."""
    with _tracked_lock:
        paths = list(_tracked_temp_dirs)
        _tracked_temp_dirs.clear()
    removed = 0
    for path in paths:
        try:
            if not os.path.isdir(path):
                continue
            shutil.rmtree(path, ignore_errors=True)
            if not os.path.isdir(path):
                removed += 1
        except Exception:
            pass
    return removed


class SkipTest(Exception):
    """Raise from inside a test to mark it SKIP (not FAIL) -- e.g. a
    fixture that needs something not present on this machine."""


class Ctx:
    """Minimal test context: a check() counter/assertion helper. Individual
    test_*.py files attach whatever fixtures they need as plain attributes
    (e.g. `ctx.home = ...`, `ctx.mock = ...`) rather than this class trying
    to anticipate every suite's fixture shape up front."""

    def __init__(self):
        self.checks = 0

    def check(self, description: str, condition: bool) -> None:
        self.checks += 1
        if not condition:
            raise AssertionError(description)


def new_registry():
    """Return a fresh (test_decorator, TESTS_list) pair, private to whatever
    module calls this -- each test_*.py file gets its own registry so
    importing several of them into tests/run_all.py never merges their
    test lists together."""
    registry: list = []

    def test(fn: Callable) -> Callable:
        registry.append((fn.__name__, fn))
        return fn

    return test, registry


# 3.6.0.2 P5 batch 4 (the decisions' F-D): the two card times of tui/keys.py (a card shown within 1.5 s of a key into
# the box waits; a card answers no key in its first 0.6 s) are turned OFF for every test by this one variable, which
# only tui/keys.card_times reads -- the older modules answer cards right after showing them. A test marked
# `@real_card_timing` (tests/test_card_keys.py) runs with the product's real times.
CARD_TIMES_OFF_ENV = "HALO_TEST_CARD_TIMES_OFF"


def real_card_timing(fn: Callable) -> Callable:
    fn.real_card_timing = True
    return fn


def run_all(tests: list, ctx: Ctx):
    """Run every (name, fn) in `tests` against `ctx`, catching SkipTest ->
    SKIP, AssertionError -> FAIL (message only), anything else -> FAIL
    (with a short traceback). Returns (results, passed, failed, skipped)
    exactly like test_bridge.py's own run_all.

    Test hygiene (round B fix pass, notes file): running one test_*.py
    module directly (`python tests/test_x.py`) is NOT hermetic by
    itself -- only `tests/run_all.py`'s own top-level scoping protected a
    module that never calls `ensure_scoped_state_dir_once()`/`ensure_
    default_provider_credentials()` itself. A standalone run of the MCP
    manager tests wrote fake-server logs into the REAL `~/.halo/mcp/`
    this way (found and removed 2026-10-03). Every test_*.py file's own
    `__main__` block calls this SAME function, whether run standalone or
    via `tests/run_all.py` -- scoping it here, before any test actually
    runs, covers both: `BRIDGE_TEST_HOME` only when NEITHER state-dir var
    is already set (never clobbers a more specific scheme a file/earlier
    import already put in place -- same no-op rule `ensure_scoped_state_
    dir_once` itself documents), `BRIDGE_TEST_NO_BACKGROUND_NET` via
    `setdefault` (never overrides a file that deliberately sets it to
    something else first)."""
    from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
    ensure_scoped_state_dir_once()
    os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
    # Halo 2.0.2 round C: same backstop as BRIDGE_TEST_NO_BACKGROUND_NET
    # just above -- see provider_env_defaults.ensure_default_provider_
    # credentials' own comment on this exact var.
    os.environ.setdefault("BRIDGE_TEST_DRAIN_TICK_WINDOW_S", "0.15")
    results = []
    passed = failed = skipped = 0
    for name, fn in tests:
        t0 = time.monotonic()
        homes = {k: os.environ.get(k) for k in _HOME_VARS}
        card_times_before = os.environ.get(CARD_TIMES_OFF_ENV)
        if getattr(fn, "real_card_timing", False):
            os.environ.pop(CARD_TIMES_OFF_ENV, None)
        else:
            os.environ[CARD_TIMES_OFF_ENV] = "1"
        try:
            fn(ctx)
            retried = str(getattr(ctx, "retried", "") or "")  # 3.3.8.1: tests/helpers/driver_got.py sets it
            results.append((name, "PASS", f"driver retried once: {retried}" if retried else "", time.monotonic() - t0))
            passed += 1
        except SkipTest as e:
            results.append((name, "SKIP", str(e), time.monotonic() - t0))
            skipped += 1
        except AssertionError as e:
            results.append((name, "FAIL", str(e), time.monotonic() - t0))
            failed += 1
        except SystemExit as e:
            # 2.0.6 round 13 (the test-runner SystemExit fix): SystemExit
            # is a BaseException, not an Exception -- one test tripping
            # argparse's parser.error() (or a stray sys.exit() on an
            # in-process path) used to escape this handler and kill the
            # WHOLE suite run, every later module unrun. It is a FAILED
            # TEST now, and the run continues. KeyboardInterrupt stays
            # uncaught on purpose (a deliberate Ctrl+C must still abort).
            results.append((name, "FAIL", f"SystemExit({e.code}) -- a test tried to exit the "
                                          "process; counted as a failure, suite continues",
                            time.monotonic() - t0))
            failed += 1
        except Exception as e:
            detail = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=6)}"
            results.append((name, "FAIL", detail, time.monotonic() - t0))
            failed += 1
        finally:
            _keep_a_home(homes)
            if card_times_before is None:
                os.environ.pop(CARD_TIMES_OFF_ENV, None)
            else:
                os.environ[CARD_TIMES_OFF_ENV] = card_times_before
    return results, passed, failed, skipped


_HOME_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")


def _keep_a_home(before: dict) -> None:
    """3.6.0.0 fx jb7: a test that ends with NO state-dir variable set (its teardown popped the BRIDGE_TEST_HOME it
    had set over the module's own) gets back the one it found, so the module's later tests never run on the real
    `~/.halo` (CI's shard 3 created it: test_w6a_release_fixes' `_end` popped the home, and a later test's
    run_streamed wrote the shell ledger, run/children.json, under the real home). A test that leaves any home set
    is left alone."""
    if any(k in os.environ for k in _HOME_VARS):
        return
    for k, v in before.items():
        if v is not None:
            os.environ[k] = v


def print_results(results, passed: int, failed: int, skipped: int, *, label: str = "tests") -> int:
    """Print one line per test plus a RESULT summary line; returns the
    process exit code (0 iff failed == 0)."""
    for name, status, detail, dt in results:
        line = f"[{status}] {name} ({dt:.2f}s)"
        if detail and status != "PASS":
            line += f": {detail}"
        elif detail:
            line += f" ({detail})"
        print(line)
    total = passed + failed + skipped
    print("-" * 74)
    print(f"RESULT: {total} {label}, {passed} passed, {failed} failed, {skipped} skipped")
    return 0 if failed == 0 else 1
