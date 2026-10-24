"""tests.helpers.chrome_driver -- the one base every headless Chrome driver
stands on (Halo 3.1.0.0 round R1): tests/helpers/studio_*.py and the
tools/capture_*.py renders.

* `scope_home()` first thing: `ensure_scoped_state_dir_once`, so a driver
  started with BRIDGE_* scrubbed (tests/test_studio_ui.py's `_json_of`)
  never reaches the real `~/.halo`; a scratch home the driver made itself is
  removed when it ends.
* `find_chrome()`: `HALO_CHROME` (or an explicit path) first, then the usual
  install paths and names on PATH.
* `headless_flags()`: the launch flags every Chrome here starts with (cdp.Chrome,
  `one_shot`, tools/capture_screens.py); `--no-sandbox` only as root (3.2.1.0 R5).
* exactly one headless Chrome at a time: `cdp.Chrome` and `one_shot` hold
  the file lock of tests/helpers/chrome_lock.py.
* `emulate_motion(c, value)`: the page's prefers-reduced-motion pinned, so a
  check of an animation reads the same on every runner (3.1.5.0 R3).
* `Driver.run(steps)`: each `(fn, args)` in turn; a step that raises records
  `failed` ("<step>: <error>") and stops; a step that returns a dict adds it
  to `out`. `Driver.main()` finds Chrome, opens it, enters `session(c)`
  (which yields the steps), runs them, closes everything and prints `out`
  as the last stdout line (exit 0; 1 when a step failed; 2 without Chrome).

A subclass implements `session(c)`; see `SmokeDriver` below
(`python -m tests.helpers.chrome_driver smoke`: Studio over the scoped home,
the shell's title).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for _p in (str(REPO), str(REPO / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from tests.helpers.chrome_lock import chrome_lock  # noqa: E402

CHROME_CANDIDATES = (
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome")
HEADLESS = ("--headless=new", "--disable-gpu", "--hide-scrollbars")


def headless_flags() -> tuple:
    """HEADLESS, plus `--no-sandbox` when this process runs as root (Chrome will not start as root with its
    sandbox on: a Kali root shell); never otherwise, and never on Windows (no geteuid). Read at each launch."""
    return HEADLESS + (("--no-sandbox",) if getattr(os, "geteuid", lambda: -1)() == 0 else ())


def find_chrome(explicit: str = "") -> "str | None":
    """A Chrome/Chromium binary: `explicit`, then `HALO_CHROME`, then the
    install paths, then PATH. None when there is none."""
    for cand in (explicit, os.environ.get("HALO_CHROME", "")):
        if cand and Path(cand).exists():
            return cand
    for cand in CHROME_CANDIDATES:
        if Path(cand).exists():
            return cand
    for name in CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


SCRUBBED_PREFIXES = ("HALO_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_")


def driver_env(repo: "Path | None" = None) -> dict:
    """The environment a driver subprocess runs in: every provider and harness
    variable scrubbed (the driver scopes its own scratch home) except
    `HALO_CHROME`, which names the browser; PYTHONPATH = the repo, no
    background network."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUBBED_PREFIXES) or k == "HALO_CHROME"}
    env["PYTHONPATH"] = str(repo or REPO)
    env["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    return env


def scope_home() -> "Path | None":
    """Scope this process's home before anything reads it. Returns the
    scratch home when this call made it (the caller removes it), else None
    (a home was already scoped: the test's, a rig's, run_all's)."""
    before = (os.environ.get("BRIDGE_TEST_HOME"), os.environ.get("BRIDGE_STATE_DIR"))
    from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
    ensure_scoped_state_dir_once()
    after = os.environ.get("BRIDGE_TEST_HOME")
    if before == (None, None) and after:
        return Path(after)
    return None


def open_chrome(width: int = 1500, height: int = 900, exe: "str | None" = None):
    """A `cdp.Chrome` (it holds the Chrome lock until `close()`), or None without Chrome."""
    exe = exe or find_chrome()
    if not exe:
        return None
    from tests.helpers.cdp import Chrome
    return Chrome(exe, width=width, height=height)


def emulate_motion(c, value: str = "no-preference") -> None:
    """The page's `prefers-reduced-motion`, the same on every runner (3.1.5.0 R3: a Windows runner image with
    animations off makes headless Chrome report `reduce`, which turns the motion off by design). Set it before
    `c.go`: the emulation holds across navigations of the page. `value` is "no-preference" or "reduce"."""
    c.call("Emulation.setEmulatedMedia", media="", features=[{"name": "prefers-reduced-motion", "value": value}])


def one_shot(args: list, timeout: int = 90) -> "subprocess.CompletedProcess | None":
    """One `--dump-dom` / `--screenshot` run of headless Chrome under the lock
    (a throwaway profile); None without Chrome. Output decoded as utf-8."""
    exe = find_chrome()
    if not exe:
        return None
    with chrome_lock():
        profile = tempfile.mkdtemp(prefix="halo-chrome-")
        cmd = [exe, *headless_flags(), f"--user-data-dir={profile}", "--virtual-time-budget=6000", *args]
        try:
            return subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        finally:
            shutil.rmtree(profile, ignore_errors=True)


class Driver:
    """The base of a headless Chrome driver; subclasses implement `session`."""

    no_chrome = {"error": "no Chrome found"}  # the JSON line without Chrome (exit 2)
    width, height = 1500, 900

    def __init__(self, argv=None, *, chrome_cls=None, find=None, lock_path=None):
        self.argv = list(argv or [])
        self.out: dict = {}
        self._made_home = scope_home()  # first thing: nothing below may read the real home
        self._chrome_cls = chrome_cls  # test seam: a stand-in for cdp.Chrome
        self._find = find or find_chrome
        self._lock_path = lock_path

    @contextmanager
    def session(self, c):
        """Seed and serve what the steps need, yield the steps, clean up. Override."""
        yield ()

    def run(self, steps, emit: bool = True) -> dict:
        """Each `(fn, args)` in order; the first that raises is recorded as `failed` and stops the run."""
        for fn, args in steps:
            try:
                got = fn(*args)
            except Exception as e:  # what it saw so far still prints; the test names the step
                self.out["failed"] = f"{getattr(fn, '__name__', 'step')}: {type(e).__name__}: {e}"[:400]
                traceback.print_exc(limit=6, file=sys.stderr)
                break
            if isinstance(got, dict) and got is not self.out:
                self.out.update(got)
        if emit:
            print(json.dumps(self.out))
        return self.out

    def _chrome(self, exe):
        if self._chrome_cls is not None:
            return self._chrome_cls(exe, self.width, self.height)
        from tests.helpers.cdp import Chrome
        return Chrome(exe, width=self.width, height=self.height, lock_path=self._lock_path)

    def main(self) -> int:
        exe = self._find()
        if not exe and self._chrome_cls is None:
            print(json.dumps(self.no_chrome))
            self._drop_home()
            return 2
        try:
            with chrome_lock(self._lock_path):  # the whole run, rig and Chrome, is one turn of the lock
                c = self._chrome(exe)
                try:
                    with self.session(c) as steps:
                        self.run(steps, emit=False)
                        try:
                            c.go("about:blank")
                        except Exception:
                            pass
                finally:
                    c.close()
        except Exception as e:
            self.out.setdefault("failed", f"setup: {type(e).__name__}: {e}"[:400])
            traceback.print_exc(limit=6, file=sys.stderr)
        finally:
            self._drop_home()
        print(json.dumps(self.out))
        return 1 if "failed" in self.out else 0

    def _drop_home(self) -> None:
        if self._made_home is not None:
            shutil.rmtree(self._made_home, ignore_errors=True)
            if os.environ.get("BRIDGE_TEST_HOME") == str(self._made_home):
                os.environ.pop("BRIDGE_TEST_HOME", None)
            self._made_home = None


class SmokeDriver(Driver):
    """Studio over this process's scoped home; the shell's title and where the home was."""

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        srv, url = serve(state)
        try:
            yield ((self.page, (c, url, state)),)
        finally:
            srv.shutdown()
            srv.server_close()

    def page(self, c, url: str, state: Path) -> dict:
        c.go(url)
        c.wait("document.title.includes('Halo Studio') && document.querySelectorAll('[data-testid=\"section-tab\"]').length > 0", 40)
        return {"title": c.js("document.title"), "tabs": c.js("document.querySelectorAll('[data-testid=\"section-tab\"]').length"),
                "state": str(state)}


if __name__ == "__main__":
    if sys.argv[1:2] != ["smoke"]:
        print("usage: python -m tests.helpers.chrome_driver smoke", file=sys.stderr)
        sys.exit(2)
    sys.exit(SmokeDriver(sys.argv[2:]).main())
