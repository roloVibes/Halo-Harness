"""tests.test_chrome_root_flags -- Halo 3.2.1.0 round R5: Chrome as root.

Chrome will not start as root with its sandbox on (a Kali root shell), so
every headless Chrome the suite and the capture tools start adds
`--no-sandbox` when `os.geteuid() == 0`, and only then:

1. `chrome_driver.headless_flags()`: HEADLESS as it is for a normal user and
   on Windows (no `os.geteuid`), HEADLESS + `--no-sandbox` for root.
2. The three launches read it at launch time: `cdp.Chrome` (the drivers),
   `chrome_driver.one_shot` (`--dump-dom` / `--screenshot`) and
   `tools/capture_screens.render_png`.

No Chrome is started: `subprocess.Popen` / `subprocess.run` are stand-ins
that record the command line. Run: python -m tests.test_chrome_root_flags
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()
_MISSING = object()


@contextmanager
def _euid(value):
    """`os.geteuid` returns `value` inside the block (None: there is no `os.geteuid`, as on Windows)."""
    saved = getattr(os, "geteuid", _MISSING)
    if value is None:
        if saved is not _MISSING:
            del os.geteuid
    else:
        os.geteuid = lambda: value
    try:
        yield
    finally:
        if saved is _MISSING:
            if hasattr(os, "geteuid"):
                del os.geteuid
        else:
            os.geteuid = saved


class _Stop(RuntimeError):
    pass


@contextmanager
def _record(module, attr: str, result=None):
    """`module.subprocess.<attr>` records each command line; it raises _Stop when `result` is None."""
    seen: list = []
    real = getattr(subprocess, attr)

    def fake(cmd, *a, **kw):
        seen.append(list(cmd))
        if result is None:
            raise _Stop("recorded")
        return result

    setattr(module.subprocess, attr, fake)
    try:
        yield seen
    finally:
        setattr(module.subprocess, attr, real)


@test
def test_headless_flags_hold_no_sandbox_only_for_root(ctx: Ctx):
    from tests.helpers.chrome_driver import HEADLESS, headless_flags
    with _euid(0):
        got_root = headless_flags()
    with _euid(1000):
        got_user = headless_flags()
    with _euid(None):
        got_windows = headless_flags()
    ctx.check(f"root: HEADLESS + --no-sandbox, got {got_root}", got_root == HEADLESS + ("--no-sandbox",))
    ctx.check(f"a normal user: HEADLESS as it is, got {got_user}", got_user == HEADLESS and "--no-sandbox" not in got_user)
    ctx.check(f"no geteuid (Windows): HEADLESS as it is, got {got_windows}", got_windows == HEADLESS)
    ctx.check("HEADLESS itself never holds it", "--no-sandbox" not in HEADLESS)


@test
def test_the_cdp_chrome_launch_reads_it_at_launch(ctx: Ctx):
    from tests.helpers import cdp
    lock = Path(tempfile.mkdtemp(prefix="chrome-root-lock-")) / "chrome.lock"
    lines = {}
    for label, euid in (("root", 0), ("user", 1000), ("windows", None)):
        with _euid(euid), _record(cdp, "Popen") as seen:
            try:
                cdp.Chrome("fake-chrome", lock_path=lock)
            except _Stop:
                pass
        lines[label] = seen[0] if seen else []
    ctx.check(f"root: the DevTools Chrome starts with --no-sandbox, got {lines['root']}",
              lines["root"][:1] == ["fake-chrome"] and "--no-sandbox" in lines["root"] and "--headless=new" in lines["root"])
    ctx.check(f"a normal user: no --no-sandbox, got {lines['user']}",
              "--headless=new" in lines["user"] and "--no-sandbox" not in lines["user"])
    ctx.check("no geteuid: no --no-sandbox", bool(lines["windows"]) and "--no-sandbox" not in lines["windows"])
    from tests.helpers.chrome_lock import chrome_lock
    with chrome_lock(lock, timeout=2):
        ctx.check("the lock is free again after each stopped start", True)


@test
def test_one_shot_and_capture_screens_read_it_too(ctx: Ctx):
    from tests.helpers import chrome_driver
    done = subprocess.CompletedProcess(["x"], 0, "", "")
    real_find = chrome_driver.find_chrome
    chrome_driver.find_chrome = lambda explicit="": "fake-chrome"
    try:
        for euid, want in ((0, True), (1000, False)):
            with _euid(euid), _record(chrome_driver, "run", result=done) as seen:
                chrome_driver.one_shot(["--dump-dom", "about:blank"])
            ctx.check(f"one_shot as euid {euid}: --no-sandbox {'there' if want else 'absent'}, got {seen}",
                      len(seen) == 1 and ("--no-sandbox" in seen[0]) == want and "--dump-dom" in seen[0])
    finally:
        chrome_driver.find_chrome = real_find
    repo = Path(__file__).resolve().parent.parent
    if str(repo / "tools") not in sys.path:
        sys.path.insert(0, str(repo / "tools"))
    import capture_screens
    svg = Path(tempfile.mkdtemp(prefix="chrome-root-svg-")) / "a.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>', encoding="utf-8")
    for euid, want in ((0, True), (1000, False)):
        with _euid(euid), _record(capture_screens, "run", result=done) as seen:
            capture_screens.render_png("fake-chrome", svg, svg.with_suffix(".png"), 1)
        ctx.check(f"capture_screens.render_png as euid {euid}: --no-sandbox {'there' if want else 'absent'}, got {seen}",
                  len(seen) == 1 and ("--no-sandbox" in seen[0]) == want and seen[0][0] == "fake-chrome")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
