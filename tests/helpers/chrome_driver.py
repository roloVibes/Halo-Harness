"""tests.helpers.chrome_driver -- the one base every headless Chrome driver
stands on (Halo 3.1.0.0 round R1): tests/helpers/studio_*.py and the
tools/capture_*.py renders.

* `scope_home()` first thing: `ensure_scoped_state_dir_once`, so a driver
  started with BRIDGE_* scrubbed (tests/test_studio_ui.py's `_json_of`)
  never reaches the real `~/.halo`; a scratch home the driver made itself is
  removed when it ends.
* `find_chrome()`: `HALO_CHROME` (or an explicit path) first, then the usual
  install paths and names on PATH; a named browser that does not exist raises
  ChromeNotFound (3.6.0.1: never the person's own installed Chrome instead).
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
  3.3.8.1: a step's TimeoutError runs the whole session once more in a fresh
  process (tests/helpers/driver_retry.py), `retried` in `out`.

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
import re
import tempfile
import time
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
# 3.3.12.0 R1: a dark system on every runner (preferredColorScheme 0): an unset `theme` draws holo, as before
# fx jb3: no keychain is ever asked (a scratch HOME on macOS has none and Chrome blocked at its first page load):
# --use-mock-keychain acts on macOS, --password-store=basic on Linux; each is ignored elsewhere
HEADLESS = ("--headless=new", "--disable-gpu", "--hide-scrollbars", "--blink-settings=preferredColorScheme=0", "--password-store=basic",
            "--use-mock-keychain")


EXTRA_FLAGS: list = []  # 3.3.9.0 R3: a driver's own flags (the voice driver's fake microphone), set in its process only


def headless_flags() -> tuple:
    """HEADLESS (+ EXTRA_FLAGS), plus `--no-sandbox` when this process runs as root (Chrome will not start as root
    with its sandbox on: a Kali root shell); never otherwise, and never on Windows (no geteuid). Read at each launch."""
    return HEADLESS + tuple(EXTRA_FLAGS) + (("--no-sandbox",) if getattr(os, "geteuid", lambda: -1)() == 0 else ())


class ChromeNotFound(RuntimeError):
    """A browser was named (`explicit` or HALO_CHROME) and it names nothing (3.6.0.1)."""


def find_chrome(explicit: str = "") -> "str | None":
    """A Chrome/Chromium binary: `explicit`, else `HALO_CHROME`, else the
    install paths, then PATH. None when there is none. A browser that was
    named (a path, or a bare command name on PATH) is used or nothing:
    naming one that does not exist raises ChromeNotFound, never a silent
    fall-back to the person's own installed Chrome (3.6.0.1)."""
    from halo_harness.browser_find import named_browser
    for label, cand in (("the browser given", explicit), ("HALO_CHROME names a browser that",
                                                           os.environ.get("HALO_CHROME", ""))):
        if cand:
            found = named_browser(cand)
            if not found:
                raise ChromeNotFound(f"{label} does not exist: {cand} (fix or unset it)")
            return found
    for cand in CHROME_CANDIDATES:
        if Path(cand).exists():
            return cand
    for name in CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


SCRUBBED_PREFIXES = ("HALO_", "OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_")
KEPT_VARS = ("HALO_CHROME", "HALO_DRIVER_NO_RETRY")  # the browser; 3.3.8.1: the retry's off switch


from tests.helpers.ollama_pin import REFUSED_OLLAMA, pinned_ollama_host  # noqa: E402,F401  (3.3.5.0 R3)


def driver_env(repo: "Path | None" = None) -> dict:
    """The environment a driver subprocess runs in: every provider and harness
    variable scrubbed (the driver scopes its own scratch home) except
    `HALO_CHROME`, which names the browser; PYTHONPATH = the repo, no
    background network; `OLLAMA_HOST` pinned (pinned_ollama_host)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUBBED_PREFIXES) or k in KEPT_VARS}
    env["PYTHONPATH"] = str(repo or REPO)
    env["BRIDGE_TEST_NO_BACKGROUND_NET"] = "1"
    env["OLLAMA_HOST"] = pinned_ollama_host(env.get("OLLAMA_HOST"))
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


#: 3.6.0.4 S batch 2: how long a close waits for the processes of its own Chrome to go before it ends them by pid
CLOSE_BOUND_S = 10.0


def _scan_all() -> dict:
    from tests.helpers.leftovers import scan
    return scan(lambda _pid, _start: True)


def _end_by_pid(p) -> bool:
    from tests.helpers.leftovers import end_one
    return end_one(p)


_clock, _sleep = time.monotonic, time.sleep


def _carries_profile(cmd: str, profile: str) -> bool:
    """`cmd` holds `--user-data-dir=<a folder named as profile's last segment>` (quoted or not, any slashes; the
    folder name is mkdtemp's, unique; a parent folder may be written in its short or long form)."""
    name = os.path.basename(os.path.normpath(profile))
    flags = re.IGNORECASE if os.name == "nt" else 0
    pattern = re.compile(r"(?:^|[\\/=])" + re.escape(name) + r"(?=$|[\s\"'])", flags)
    for part in (cmd or "").split("--user-data-dir=")[1:]:
        if pattern.search(part.split(" --", 1)[0].strip()):
            return True
    return False


def end_profile_processes(profile: str, *, bound_s: "float | None" = None, scan=None, end=None, clock=None,
                          sleep=None) -> list:
    """3.6.0.4 S batch 2: every process whose command line carries THIS driver's throwaway `--user-data-dir` (the
    browser and its helpers: a utility, the crash handler) is gone when this returns. Waits up to CLOSE_BOUND_S for
    them to go by themselves, then ends by pid (its start time matched, tests/helpers/leftovers.end_one) each still
    there, the newest first. Never by name, never another profile's Chrome. Returns the processes it ended."""
    scan, end = scan or _scan_all, end or _end_by_pid
    clock, sleep = clock or _clock, sleep or _sleep
    deadline = clock() + (CLOSE_BOUND_S if bound_s is None else bound_s)
    me = os.getpid()

    def mine() -> list:
        try:
            table = scan()
        except OSError:  # no look at the table this time: tests/run_all.py's leftover check still names what is left
            return []
        return [p for p in table.values() if p.pid != me and _carries_profile(p.cmd, profile)]

    left = mine()
    while left and clock() < deadline:
        sleep(0.25)
        left = mine()
    for p in sorted(left, key=lambda p: p.start, reverse=True):
        end(p)
    return left


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
            from tests.helpers.leftovers import rig_browser_env  # 3.6.0.1: this browser's helpers are the rig's
            return subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout,
                                  env=rig_browser_env())
        finally:
            end_profile_processes(profile)  # 3.6.0.4 S batch 2: its helpers too, before the lock goes
            shutil.rmtree(profile, ignore_errors=True)


class Driver:
    """The base of a headless Chrome driver; subclasses implement `session`."""

    no_chrome = {"error": "no Chrome found"}  # the JSON line without Chrome (exit 2)
    width, height = 1500, 900

    def __init__(self, argv=None, *, chrome_cls=None, find=None, lock_path=None):
        self.argv = list(argv or [])
        self.out: dict = {}
        self._made_home = scope_home()  # first thing: nothing below may read the real home
        self._own_home = self._made_home is not None  # 3.3.8.1: a retry scopes a fresh one (driver_retry.after)
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
        from tests.helpers.driver_retry import after  # 3.3.8.1: a step's TimeoutError runs the session once more
        self.out = after(self.out, own_home=self._own_home, real_chrome=self._chrome_cls is None)
        print(json.dumps(self.out))
        return 1 if "failed" in self.out else 0

    def _drop_home(self) -> None:
        if self._made_home is not None:
            shutil.rmtree(self._made_home, ignore_errors=True)
            # BRIDGE_TEST_HOME stays pointed at the (gone) scratch path: an atexit hook that runs after this
            # (headless._stop_managed_local_servers_quietly) must land in scratch, never in the real ~/.halo
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
