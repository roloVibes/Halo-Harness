"""tests.helpers.firefox_driver -- a REAL Firefox for the browser tests that must see what Firefox sends (Halo 3.6.0.6 PF:
Firefox's plain reload looks to Studio exactly like a link, tests/test_studio_owner_tab_firefox.py). Firefox is driven
over WebDriver BiDi, its own remote agent on a loopback port it picks (`--remote-debugging-port 0`), through the
websocket of tests/helpers/cdp.py: its pointer and key actions are trusted events, its navigation is the address bar's.
It runs with a throwaway profile (never a person's) in a hidden display of its own (Xvfb, its number chosen by Xvfb)
or, without Xvfb, headless; the browser and the display end by pid with `close()`.

    find_firefox() -> path | None          firefox-esr or firefox on PATH (HALO_FIREFOX names one)
    Firefox(exe)                           .go(url)  .js(expr)  .wait(expr, timeout)  .click_on(expr)  .call(...)
                                           .press_keys("ctrl+r")  (xdotool in its own display; None when it cannot)
    FirefoxDriver                          the base of a driver (tests/helpers/chrome_driver.Driver): the JSON line
                                           {"skip": "no Firefox found"} and exit 2 without Firefox

`call("Page.enable")` and `call("Page.addScriptToEvaluateOnNewDocument", source=...)` are taken as a preload script, so
the page-error collector is added the one way every driver adds it (tests/helpers/studio_session.collect_page_errors).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.cdp import Chrome  # noqa: E402  (its websocket)
from tests.helpers.chrome_driver import Driver  # noqa: E402

PREFS = ("browser.shell.checkDefaultBrowser", False), ("browser.aboutwelcome.enabled", False), \
    ("datareporting.policy.dataSubmissionEnabled", False), ("browser.startup.homepage_override.mstone", "ignore"), \
    ("toolkit.telemetry.reportingpolicy.firstRun", False), ("browser.tabs.warnOnClose", False), \
    ("app.normandy.enabled", False), ("browser.sessionstore.resume_from_crash", False), \
    ("trailhead.firstrun.didSeeAboutWelcome", True), ("termsofuse.acceptedVersion", 999), \
    ("termsofuse.bypassNotification", True), ("browser.preonboarding.enabled", False), \
    ("startup.homepage_welcome_url", ""), ("browser.startup.page", 0), ("network.proxy.type", 0)


def find_firefox() -> "str | None":
    named = os.environ.get("HALO_FIREFOX")
    if named:
        return named if os.path.exists(named) else None
    return shutil.which("firefox-esr") or shutil.which("firefox")


def _end(proc) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
        try:
            proc.wait(timeout=10)
        except Exception:
            pass


class Firefox(Chrome):
    """One Firefox over WebDriver BiDi (the websocket and `wait` of cdp.Chrome; the rest is BiDi's)."""

    def __init__(self, exe: str, width: int = 1500, height: int = 900, lock_path=None):  # noqa: D401 (no Chrome start)
        from tests.helpers.chrome_lock import lock_for
        from tests.helpers.leftovers import rig_browser_env
        self._lock = lock_for(lock_path)  # one browser at a time, Chrome or Firefox
        self._lock.acquire()
        self._locked = True
        self.proc = self.xvfb = None
        self.sock = None
        self.buf = b""
        self.seq = 0
        self.down = False
        self._navigated = True
        self.display = ""
        try:
            self.profile = tempfile.mkdtemp(prefix="halo-ff-")
            with open(os.path.join(self.profile, "user.js"), "w", encoding="utf-8") as f:
                f.writelines(f"user_pref({json.dumps(k)}, {json.dumps(v)});\n" for k, v in PREFS)
            env = {**rig_browser_env(), "MOZ_CRASHREPORTER_DISABLE": "1"}
            headless = not (shutil.which("Xvfb") and shutil.which("xdotool"))
            if not headless:
                self.display = self._start_xvfb(width, height)
                env["DISPLAY"] = self.display
            log = open(os.path.join(self.profile, "stderr.txt"), "wb")
            self.proc = subprocess.Popen([exe, *(["-headless"] if headless else []), "-profile", self.profile, "--no-remote",
                                          "--new-instance", "--width", str(width), "--height", str(height),
                                          "--remote-debugging-port", "0", "about:blank"],
                                         stdout=subprocess.DEVNULL, stderr=log, env=env)
            log.close()
            self._connect(f"ws://127.0.0.1:{self._port()}/session")
            self.call("session.new", capabilities={})
            self.ctx = self.call("browsingContext.getTree")["contexts"][0]["context"]
        except Exception:
            self.close()
            raise

    def _start_xvfb(self, width: int, height: int) -> str:
        r, w = os.pipe()
        self.xvfb = subprocess.Popen(["Xvfb", "-displayfd", str(w), "-screen", "0", f"{width}x{height + 100}x24", "-nolisten",
                                      "tcp"], pass_fds=(w,), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(w)
        with os.fdopen(r) as f:
            n = f.readline().strip()
        if not n.isdigit():
            raise RuntimeError("Xvfb did not say its display")
        return f":{n}"

    def _port(self) -> int:
        path = os.path.join(self.profile, "stderr.txt")
        deadline = time.time() + 90
        while time.time() < deadline:
            try:
                text = Path(path).read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            for line in text.splitlines():
                if "WebDriver BiDi listening on ws://" in line:
                    return int(line.rsplit(":", 1)[1].strip().strip("/"))
            if self.proc.poll() is not None:
                raise RuntimeError(f"Firefox ended at its start: {text[-300:]!r}")
            time.sleep(0.1)
        raise RuntimeError("Firefox did not open its remote port")

    def call(self, method: str, **params):
        if method == "Page.enable":
            return {}
        if method == "Page.addScriptToEvaluateOnNewDocument":  # studio_session.collect_page_errors, a driver's watcher
            return self.call("script.addPreloadScript", functionDeclaration="() => {\n" + params["source"] + "\n}")
        if method == "Input.insertText":  # typed into the focused field, key by key
            keys = [{"type": t, "value": ch} for ch in params["text"] for t in ("keyDown", "keyUp")]
            self.call("input.performActions", context=self.ctx, actions=[{"type": "key", "id": "kb", "actions": keys}])
            return self.call("input.releaseActions", context=self.ctx)
        self.seq += 1
        mid = self.seq
        self._send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            m = json.loads(self._recv())
            if m.get("id") == mid:
                if m.get("type") == "error":
                    raise RuntimeError(f"{method}: {m.get('error')}: {m.get('message')}")
                return m.get("result", {})

    def go(self, url: str) -> None:
        """As the address bar takes an address (a new one, or the same page with another fragment)."""
        self.call("browsingContext.navigate", context=self.ctx, url=url, wait="none")

    def js(self, expr: str):
        src = json.dumps(expr)
        r = self.call("script.evaluate", target={"context": self.ctx}, awaitPromise=True, resultOwnership="none",
                      expression=f"Promise.resolve((0, eval)({src})).then((v) => JSON.stringify(v === undefined ? null : v))")
        if r.get("type") == "exception":
            raise RuntimeError(f"{expr[:80]}: {r.get('exceptionDetails', {}).get('text')}")
        value = (r.get("result") or {}).get("value")
        return json.loads(value) if isinstance(value, str) else None

    def click(self, x: float, y: float) -> None:
        """A real press: BiDi's pointer actions are trusted events with the person's activation."""
        self.call("input.performActions", context=self.ctx, actions=[{"type": "pointer", "id": "mouse",
                  "parameters": {"pointerType": "mouse"}, "actions": [
                      {"type": "pointerMove", "x": int(x), "y": int(y), "origin": "viewport"},
                      {"type": "pointerDown", "button": 0}, {"type": "pointerUp", "button": 0}]}])
        self.call("input.releaseActions", context=self.ctx)
        self.pointer = [round(x), round(y)]

    def press_keys(self, keys: str) -> "bool | None":
        """A browser key (e.g. "ctrl+r") pressed for real in this Firefox's own display (xdotool); None headless."""
        if not self.display:
            return None
        env = {**os.environ, "DISPLAY": self.display}
        wins = subprocess.run(["xdotool", "search", "--onlyvisible", "--pid", str(self.proc.pid)], capture_output=True,
                              text=True, env=env, timeout=20).stdout.split()
        if not wins:
            return False
        subprocess.run(["xdotool", "windowfocus", "--sync", wins[-1]], env=env, timeout=20, capture_output=True)
        subprocess.run(["xdotool", "key", "--clearmodifiers", keys], env=env, timeout=20, capture_output=True)
        return True

    def close(self) -> None:
        try:
            if self.sock is not None:
                try:
                    self.call("browser.close")
                except Exception:
                    pass
                try:
                    self.sock.close()
                except Exception:
                    pass
            if self.proc is not None:
                try:
                    self.proc.wait(timeout=15)
                except Exception:
                    _end(self.proc)
                self._end_profile_children()
            _end(self.xvfb)
            shutil.rmtree(getattr(self, "profile", ""), ignore_errors=True)
        finally:
            self._release()

    def _end_profile_children(self) -> None:
        """Any process still carrying this throwaway profile (by pid, its start time matched), never by name."""
        from tests.helpers.leftovers import end_one, scan
        try:
            left = [p for p in scan(lambda _pid, _start: True).values() if p.pid != os.getpid() and self.profile in (p.cmd or "")]
        except OSError:
            return
        for p in left:
            end_one(p)


class FirefoxDriver(Driver):
    """The base of a Firefox driver; subclasses implement `session(c)` as a Chrome driver does."""

    no_chrome = {"skip": "no Firefox found"}

    def __init__(self, argv=None):
        super().__init__(argv, find=find_firefox)

    def _chrome(self, exe):
        return Firefox(exe, width=self.width, height=self.height, lock_path=self._lock_path)
