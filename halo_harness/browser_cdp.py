"""halo_harness.browser_cdp -- Halo's own browser (3.6.0.6 W, the owner: "WE NEED THE HARNESS TO RUN AND CONTROL
BROWSERS", "SEAMLESSLY"): one Chrome, Chromium, Edge or Brave already on this machine (browser_find.py), started
headless by Halo itself and driven over the DevTools protocol, with no other product in between and nothing to
install or download. Standard library only.

THE CONNECTION IS A PIPE, NEVER A PORT: `--remote-debugging-pipe`; on Linux and macOS descriptors 3 and 4 (handed on
by a few lines of Python that exec the browser, so nothing runs between fork and exec), on Windows two inherited pipe handles
(browser_pipe_win.py). Messages are JSON ended by a zero byte. Nothing listens on any network.

THE PROFILE: `kept` (the default, setting `browser.profile`) is Halo's own folder `<halo home>/browser/profile`,
kept between sessions so a sign-in made once is there next time -- never the person's own browser's profile; one
browser at a time uses it (a lock held while it runs: when another session holds it, this one starts clean and its
first answer says so). `clean` is a throwaway folder `<halo home>/browser/clean-<pid>-<n>`, removed at the end; one a
hard end left behind is removed by the next start.

THE CLOSING RULE: started through Halo's own spawn (subprocess_safe.Popen: the owner marker and the reaper on POSIX,
Halo's Job object on Windows), in the ledger as `browser` while it runs, and closed on every way out (closing.on_close):
`Browser.close`, a wait, then every process that still carries the profile ended BY PID (POSIX) or every process of
the browser's own Job (Windows, browser_pipe_win.end_job); then a clean profile is removed. A hard end of Halo closes
the pipe, and the browser ends itself on its closed pipe (and the reaper / the Job end what is left).

    Browser(profile="kept"|"clean").start()     find, spawn, attach to its page (raises NoBrowser, BrowserError)
    .open(url) -> bool                          navigate; wait for the load up to LOAD_WAIT_S (False: went on)
    .page() -> {title, url, text}               the page's title, address and visible text
    .controls() -> (rows, total)                what can be pressed or typed into: {n, kind, words}, CONTROLS_MAX
    .press(target) / .type_into(target, text, enter) / .key(name) / .scroll(where) / .back() / .js(expr)
    .screenshot() -> PNG bytes                  the page as it shows
    .close()                                    as above; idempotent
"""

from __future__ import annotations

import base64
import itertools
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

LOAD_WAIT_S = 15.0
CALL_WAIT_S = 30.0
START_WAIT_S = 60.0  # a cold start on a slow Windows CI runner; a healthy start answers in well under a second
CLOSE_WAIT_S = 5.0
CONTROLS_MAX = 80
WIDTH, HEIGHT = 1280, 800
HEADLESS = ("--headless=new", "--disable-gpu", "--hide-scrollbars")
FLAGS = ("--no-first-run", "--no-default-browser-check", "--password-store=basic", "--use-mock-keychain",
         f"--window-size={WIDTH},{HEIGHT}")
PROFILES = ("kept", "clean")
IN_USE = "Another session is using Halo's browser profile; this one starts clean (not signed in)."
_SEQ = itertools.count(1)


class BrowserError(RuntimeError):
    """A plain sentence a person (and the model) reads: what went wrong and what to do next."""


class NoBrowser(BrowserError):
    """No browser on this machine (browser_find.none_found())."""


def browser_home(home=None) -> Path:
    if home is not None:
        return Path(home) / "browser"
    from halo_harness.config.paths import bridge_home
    return bridge_home() / "browser"


def profile_setting() -> str:
    """`browser.profile`: kept (the default) or clean."""
    try:
        from halo_harness.theme import get_config_value
        v = str(get_config_value("browser.profile", default="kept") or "kept").strip().lower()
    except Exception:
        v = "kept"
    return v if v in PROFILES else "kept"


# -- processes that carry a profile (POSIX; never by name) -------------------------------------------------------------

def _carries(args: "list[str]", profile: str) -> bool:
    want = os.path.normpath(profile)
    return any(a.startswith("--user-data-dir=") and os.path.normpath(a.split("=", 1)[1].strip("'\"")) == want
               for a in args)


def profile_pids(profile: str) -> "list[int]":
    """Every process (not this one) whose command line carries `--user-data-dir=<profile>`: /proc on Linux, `ps` on
    macOS (and on Linux under HALO_TEST_NO_PROC, the macOS path). [] on Windows (the browser's Job holds its
    processes there)."""
    if os.name == "nt":
        return []
    me, out = os.getpid(), []
    if sys.platform.startswith("linux") and not os.environ.get("HALO_TEST_NO_PROC") and os.path.isdir("/proc"):
        for d in os.listdir("/proc"):
            if not d.isdigit() or int(d) == me:
                continue
            try:
                with open(f"/proc/{d}/cmdline", "rb") as f:
                    args = [a.decode("utf-8", "replace") for a in f.read().split(b"\0") if a]
            except OSError:
                continue
            if _carries(args, profile):
                out.append(int(d))
        return out
    return _ps_pids(profile)


def _ps_pids(profile: str) -> "list[int]":
    """profile_pids on macOS (and under HALO_TEST_NO_PROC): `ps` prints a command line as one text, so the profile is
    matched whole there too: followed by a space or the end, never by more of a longer folder name."""
    me, out = os.getpid(), []
    try:
        text = subprocess.run(["ps", "-axww", "-o", "pid=,command="], capture_output=True, text=True,
                              timeout=10).stdout
    except Exception:
        return []
    whole = re.compile(re.escape(f"--user-data-dir={os.path.normpath(profile)}") + r"(?=\s|$)")
    for line in text.splitlines():
        pid, _, cmd = line.strip().partition(" ")
        if pid.isdigit() and int(pid) != me and whole.search(cmd):
            out.append(int(pid))
    return out


def end_profile_pids(profile: str, wait_s: float = CLOSE_WAIT_S) -> "list[int]":
    """Wait up to `wait_s` for the profile's processes to go by themselves, then end each one left BY PID."""
    end = time.monotonic() + wait_s
    left = profile_pids(profile)
    while left and time.monotonic() < end:
        time.sleep(0.1)
        left = profile_pids(profile)
    for pid in left:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    return left


def sweep_clean_profiles(home=None) -> None:
    """A clean profile whose session is gone (a hard end) is removed at the next start; never one still in use."""
    from halo_harness.children import pid_running
    root = browser_home(home)
    try:
        folders = [p for p in root.iterdir() if p.is_dir() and p.name.startswith("clean-")]
    except OSError:
        return
    for p in folders:
        m = re.match(r"clean-(\d+)-", p.name)
        if m and int(m.group(1)) != os.getpid() and not pid_running(int(m.group(1))) and not profile_pids(str(p)):
            shutil.rmtree(p, ignore_errors=True)


# -- the pipe -----------------------------------------------------------------------------------------------------------

class _Pipe:
    """JSON messages ended by a zero byte over two file descriptors; a reader thread files each answer by id."""

    def __init__(self, rfd: int, wfd: int):
        self.rfd, self.wfd = rfd, wfd
        self.answers: dict = {}
        self.events: list = []
        self.closed = False
        self.cv = threading.Condition()
        self._wlock = threading.Lock()
        threading.Thread(target=self._read, name="halo-browser-pipe", daemon=True).start()

    def _read(self) -> None:
        buf = b""
        try:
            while True:
                chunk = os.read(self.rfd, 1 << 16)
                if not chunk:
                    break
                buf += chunk
                while b"\0" in buf:
                    raw, buf = buf.split(b"\0", 1)
                    try:
                        msg = json.loads(raw.decode("utf-8", "replace"))
                    except ValueError:
                        continue
                    with self.cv:
                        if "id" in msg:
                            self.answers[msg["id"]] = msg
                        else:
                            self.events = (self.events + [msg])[-200:]
                        self.cv.notify_all()
        except OSError:
            pass
        with self.cv:
            self.closed = True
            self.cv.notify_all()

    def call(self, method: str, params: dict, session: Optional[str], timeout: float) -> dict:
        mid = next(_SEQ)
        msg = {"id": mid, "method": method, "params": params}
        if session:
            msg["sessionId"] = session
        data = json.dumps(msg).encode("utf-8") + b"\0"
        with self._wlock:
            try:
                view = memoryview(data)
                while view:
                    view = view[os.write(self.wfd, view):]
            except OSError as e:
                raise BrowserError("The browser has closed. Call open to start it again.") from e
        end = time.monotonic() + timeout
        with self.cv:
            while mid not in self.answers:
                if self.closed:
                    raise BrowserError("The browser has closed. Call open to start it again.")
                left = end - time.monotonic()
                if left <= 0:
                    raise BrowserError(f"The browser did not answer {method} in {timeout:.0f} s.")
                self.cv.wait(min(left, 0.5))
            got = self.answers.pop(mid)
        if "error" in got:
            raise BrowserError(f"{method}: {got['error'].get('message', got['error'])}")
        return got.get("result") or {}

    def close(self) -> None:
        for fd in (self.wfd, self.rfd):
            try:
                os.close(fd)
            except OSError:
                pass


# The few lines that run between this Python's spawn and the browser's exec: the two pipe ends become 3 and 4 (any fd
# number, which /bin/sh's redirections cannot promise above 9), then exec replaces it (the pid is the browser's).
_TRAMPOLINE = ("import fcntl, os, sys\n"
               "r, w = (fcntl.fcntl(int(a), fcntl.F_DUPFD, 10) for a in sys.argv[1:3])\n"  # clear of 3 and 4
               "os.dup2(r, 3); os.dup2(w, 4)\n"
               "os.set_inheritable(3, True); os.set_inheritable(4, True)\n"
               "for fd in {r, w, int(sys.argv[1]), int(sys.argv[2])} - {3, 4}:\n"
               "    os.close(fd)\n"
               "os.execv(sys.argv[3], sys.argv[3:])\n")


def _posix_spawn(argv: list, popen):
    """A tiny Python step puts the two pipe ends at descriptors 3 and 4 and execs the browser (its pid is the
    browser's); no code runs in the forked child before exec (no preexec_fn in a process with threads)."""
    import sys as _sys
    to_child_r, to_child_w = os.pipe()
    from_child_r, from_child_w = os.pipe()
    try:
        proc = popen([_sys.executable, "-I", "-S", "-c", _TRAMPOLINE, str(to_child_r), str(from_child_w), argv[0],
                      "--remote-debugging-pipe", *argv[1:]], pass_fds=(to_child_r, from_child_w),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)  # a Ctrl+C at the terminal stops a turn, never the browser
    except BaseException:
        os.close(from_child_r)
        os.close(to_child_w)
        raise
    finally:
        os.close(to_child_r)
        os.close(from_child_w)
    return proc, from_child_r, to_child_w, None


# -- the page's own scripts -----------------------------------------------------------------------------------------------

_LIST_JS = r"""(() => {
  const sel = 'a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button], [role=link],' +
    ' [role=checkbox], [role=radio], [role=tab], [role=menuitem], [role=option], [role=switch], [role=textbox],' +
    ' [contenteditable=""], [contenteditable=true], [onclick]';
  const seen = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !e.disabled; };
  const kind = (e) => { const t = e.tagName.toLowerCase(), ty = (e.getAttribute('type') || '').toLowerCase();
    const role = e.getAttribute('role');
    if (role) return role === 'textbox' ? 'text box' : role;
    if (t === 'a') return 'link';
    if (t === 'button' || ['button', 'submit', 'reset', 'image'].includes(ty)) return 'button';
    if (t === 'input' && ['checkbox', 'radio', 'range', 'color', 'file', 'date'].includes(ty)) return ty;
    if (t === 'input' || t === 'textarea' || e.isContentEditable) return 'text box';
    if (t === 'select') return 'list';
    if (t === 'summary') return 'button';
    return 'clickable'; };
  const words = (e) => (e.getAttribute('aria-label') || e.innerText || e.value || e.getAttribute('placeholder') ||
    e.getAttribute('title') || e.getAttribute('name') || e.getAttribute('alt') || e.getAttribute('href') || '')
    .replace(/\s+/g, ' ').trim().slice(0, 80);
  const all = Array.from(document.querySelectorAll(sel)).filter(seen);
  window.__haloControls = all;
  return {total: all.length, rows: all.slice(0, %d).map((e, i) => ({n: i + 1, kind: kind(e), words: words(e)}))};
})()""" % CONTROLS_MAX

_FIND_JS = r"""((how, what) => {
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
  let e = null;
  if (how === 'n') { const l = window.__haloControls; if (!l) return 'stale'; e = l[what - 1] || null;
    if (e && !e.isConnected) return 'stale'; }
  else if (how === 'css') { try { e = document.querySelector(what); } catch (x) { return 'badcss'; } }
  else { const want = norm(what);
    const l = window.__haloControls && window.__haloControls.every((x) => x.isConnected) ? window.__haloControls : [];
    const label = (x) => norm(x.getAttribute('aria-label') || x.innerText || x.value || x.getAttribute('placeholder') ||
      x.getAttribute('title') || x.getAttribute('name'));
    e = l.find((x) => label(x) === want) || l.find((x) => label(x).includes(want)) || null;
    if (!e) { const w = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT); let n;
      while ((n = w.nextNode())) { if (norm(n.innerText) === want) { e = n; break; } } } }
  if (!e) return 'none';
  window.__haloTarget = e;
  const r0 = e.getBoundingClientRect();
  if (r0.top < 0 || r0.left < 0 || r0.bottom > innerHeight || r0.right > innerWidth) e.scrollIntoView({block: 'center', inline: 'center'});
  const r = e.getBoundingClientRect();
  return [r.left + r.width / 2, r.top + r.height / 2, r.width, r.height];
})"""

# key name -> (code, windowsVirtualKeyCode, text)
KEYS = {"Enter": ("Enter", 13, "\r"), "Tab": ("Tab", 9, ""), "Escape": ("Escape", 27, ""),
        "Backspace": ("Backspace", 8, ""), "Delete": ("Delete", 46, ""), "Space": ("Space", 32, " "),
        "ArrowUp": ("ArrowUp", 38, ""), "ArrowDown": ("ArrowDown", 40, ""), "ArrowLeft": ("ArrowLeft", 37, ""),
        "ArrowRight": ("ArrowRight", 39, ""), "PageUp": ("PageUp", 33, ""), "PageDown": ("PageDown", 34, ""),
        "Home": ("Home", 36, ""), "End": ("End", 35, "")}
MODIFIERS = {"alt": 1, "control": 2, "ctrl": 2, "meta": 4, "cmd": 4, "command": 4, "shift": 8}


def parse_key(name: str) -> "tuple[str, str, int, str, int]":
    """'Control+a' -> (key, code, virtual key code, text, modifier bits); BrowserError for a name it does not know."""
    parts = [p for p in re.split(r"\+(?=.)", str(name or "").strip()) if p]
    if not parts:
        raise BrowserError("key needs `text`: a key's name, as Enter, Tab, Escape, ArrowDown, PageDown or Control+a.")
    mods = 0
    for m in parts[:-1]:
        bit = MODIFIERS.get(m.lower())
        if bit is None:
            raise BrowserError(f"Unknown key '{name}'. Use Enter, Tab, Escape, ArrowDown, PageDown, or a key with "
                               f"Control/Shift/Alt/Meta, as Control+a.")
        mods |= bit
    key = parts[-1]
    named = {k.lower(): k for k in KEYS}
    if key.lower() in named:
        key = named[key.lower()]
        code, vk, text = KEYS[key]
        if key == "Space":
            key = " "
    elif len(key) == 1:
        ch = key.upper() if mods & 8 and key.isalpha() else key
        code = f"Key{key.upper()}" if key.isalpha() else f"Digit{key}" if key.isdigit() else ""
        vk, text, key = ord(key.upper()), ch, ch
    else:
        raise BrowserError(f"Unknown key '{name}'. Use Enter, Tab, Escape, ArrowDown, PageDown, or a key with "
                           f"Control/Shift/Alt/Meta, as Control+a.")
    if mods & (1 | 2 | 4):
        text = ""
    return key, code, vk, text, mods


class Browser:
    """ONE browser: Halo's child, on a pipe, with Halo's kept profile or a clean one (see the module docstring)."""

    def __init__(self, profile: Optional[str] = None, *, home=None, exe: Optional[str] = None, popen=None,
                 show: bool = False):
        self.want = profile if profile in PROFILES else profile_setting()
        self.home, self.exe, self.show = home, exe, show
        self.popen = popen
        self.proc = None
        self.pipe: Optional[_Pipe] = None
        self.job = None
        self.session: Optional[str] = None
        self.profile: Optional[str] = None
        self.kind: Optional[str] = None
        self.name: Optional[str] = None
        self.notes: "list[str]" = []
        self._lock_fh = None
        self._closed = False
        self._mu = threading.RLock()

    # -- start -----------------------------------------------------------------------------------------------------
    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None and self.pipe is not None and not self.pipe.closed

    def start(self) -> "Browser":
        with self._mu:
            if self.running:
                return self
            if self.proc is not None:  # it ended under us (closed by a person, crashed): start afresh
                self.close()
            self._closed = False
            if self.exe:
                from halo_harness.browser_find import label_of
                self.name = label_of(self.exe)
            else:
                from halo_harness.browser_find import find_browser, none_found
                got = find_browser()
                if not got:
                    raise NoBrowser(none_found())
                self.name, self.exe = got
            root = browser_home(self.home)
            root.mkdir(parents=True, exist_ok=True)
            sweep_clean_profiles(self.home)
            self._pick_profile(root)
            try:
                self._spawn()
                self._attach()
            except BaseException:
                self.close()
                raise
            return self

    def _pick_profile(self, root: Path) -> None:
        self.notes = []
        if self.want == "kept":
            kept = root / "profile"
            fh = open(root / "profile.lock", "a+b")
            from halo_harness.filelock import _try_lock
            took = _try_lock(fh)
            if took is False:
                fh.close()
                self.notes.append(IN_USE)
            else:
                self._lock_fh = fh
                kept.mkdir(parents=True, exist_ok=True)
                end_profile_pids(str(kept))  # a browser a hard-ended session left on it (POSIX; the lock was free)
                self.profile, self.kind = str(kept), "kept"
                return
        clean = root / f"clean-{os.getpid()}-{next(_SEQ)}-{int(time.time() * 1000) % 100000}"
        clean.mkdir(parents=True, exist_ok=True)
        self.profile, self.kind = str(clean), "clean"

    def argv(self) -> list:
        extra = ("--no-sandbox",) if getattr(os, "geteuid", lambda: -1)() == 0 else ()  # a root shell (Kali)
        return [self.exe, *(() if self.show else HEADLESS), *FLAGS, *extra, f"--user-data-dir={self.profile}",
                "about:blank"]

    def _spawn(self) -> None:
        from halo_harness import subprocess_safe
        popen = self.popen or subprocess_safe.Popen
        if os.name == "nt":
            from halo_harness.browser_pipe_win import spawn
            self.proc, rfd, wfd, self.job = spawn(self.argv(), popen, show=self.show)
        else:
            self.proc, rfd, wfd, self.job = _posix_spawn(self.argv(), popen)
        self.pipe = _Pipe(rfd, wfd)
        try:
            from halo_harness import children, closing
            children.register(self.proc.pid, "browser", [self.exe, f"--user-data-dir={self.profile}"])
            closing.on_close(self.close)
        except Exception:
            pass

    def _attach(self) -> None:
        try:
            got = self.pipe.call("Target.getTargets", {}, None, START_WAIT_S)
        except BrowserError as e:
            code = self.proc.poll()
            if code is not None:
                raise BrowserError(f"{self.name} did not start: it ended with code {code}.") from e
            raise
        pages = [t for t in got.get("targetInfos") or [] if t.get("type") == "page"]
        target = next((t["targetId"] for t in pages if t.get("url") == "about:blank"), None) or \
            (pages[0]["targetId"] if pages else None)
        if target is None:
            target = self.pipe.call("Target.createTarget", {"url": "about:blank"}, None, CALL_WAIT_S)["targetId"]
        self.session = self.pipe.call("Target.attachToTarget", {"targetId": target, "flatten": True}, None,
                                      CALL_WAIT_S)["sessionId"]
        self.call("Page.enable")

    # -- calls -------------------------------------------------------------------------------------------------------
    def call(self, method: str, timeout: float = CALL_WAIT_S, **params) -> dict:
        if self.pipe is None:
            raise BrowserError("The browser is not running. Call open first.")
        return self.pipe.call(method, params, self.session, timeout)

    def eval(self, expr: str, timeout: float = CALL_WAIT_S):
        r = self.call("Runtime.evaluate", timeout, expression=expr, returnByValue=True, awaitPromise=True,
                      userGesture=True)
        if r.get("exceptionDetails"):
            d = r["exceptionDetails"]
            raise BrowserError("The script failed: " + str((d.get("exception") or {}).get("description")
                                                          or d.get("text") or d)[:500])
        res = r.get("result") or {}
        return res.get("value") if "value" in res else (None if res.get("type") == "undefined" else
                                                        res.get("description"))

    def wait_loaded(self, wait_s: float = LOAD_WAIT_S) -> bool:
        end = time.monotonic() + wait_s
        while True:
            try:
                if self.eval("document.readyState", timeout=max(1.0, end - time.monotonic())) == "complete":
                    return True
            except BrowserError:
                pass
            if time.monotonic() >= end:
                return False
            time.sleep(0.1)

    # -- what the tool does ---------------------------------------------------------------------------------------------
    def open(self, url: str, wait_s: float = LOAD_WAIT_S) -> bool:
        url = str(url or "").strip()
        if not url:
            raise BrowserError("open needs `url`: the address to open.")
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url):
            url = "https://" + url
        r = self.call("Page.navigate", url=url)
        if r.get("errorText"):
            raise BrowserError(f"The page did not open: {r['errorText']} ({url}).")
        return self.wait_loaded(wait_s)

    def page(self) -> dict:
        got = self.eval("({title: document.title, url: location.href, "
                        "text: document.body ? document.body.innerText : ''})") or {}
        return {"title": str(got.get("title") or ""), "url": str(got.get("url") or ""), "text": str(got.get("text") or "")}

    def controls(self) -> "tuple[list, int]":
        got = self.eval(_LIST_JS) or {}
        return list(got.get("rows") or []), int(got.get("total") or 0)

    def _locate(self, target) -> "tuple[float, float]":
        t = str(target if target is not None else "").strip()
        if not t:
            raise BrowserError("This needs `target`: a number from the list, the control's words, or css:<selector>.")
        if t.isdigit():
            how, what = "n", int(t)
        elif t.lower().startswith("css:"):
            how, what = "css", t[4:].strip()
        else:
            how, what = "words", t
        got = self.eval(f"{_FIND_JS}({json.dumps(how)}, {json.dumps(what)})")
        if got == "stale":
            raise BrowserError("The list is from an earlier page. Call read to see the list.")
        if got == "badcss":
            raise BrowserError(f"'{what}' is not a CSS selector. Write css: and a selector, as css:#login.")
        if not isinstance(got, list):
            raise BrowserError(f"No control matches '{t}'. Call read to see the list.")
        x, y, w, h = got
        if not (w and h):
            raise BrowserError(f"'{t}' is not on the page where it can be pressed. Call read to see the list.")
        return x, y

    def _mouse(self, kind: str, x: float, y: float) -> None:
        held = kind == "mousePressed"
        self.call("Input.dispatchMouseEvent", type=kind, x=x, y=y, button="none" if kind == "mouseMoved" else "left",
                  buttons=1 if held else 0, clickCount=0 if kind == "mouseMoved" else 1)

    def _settle(self) -> None:
        """After an action: a moment for a navigation to begin, then its load (up to LOAD_WAIT_S)."""
        time.sleep(0.3)
        self.wait_loaded()

    def press(self, target) -> None:
        x, y = self._locate(target)
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            self._mouse(kind, x, y)
        self._settle()

    def type_into(self, target, text: str, enter: bool = False) -> None:
        if target not in (None, ""):
            x, y = self._locate(target)
            for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
                self._mouse(kind, x, y)
            self.eval("(() => { const e = document.activeElement; if (!e) return 0;"
                      " if (e.select && 'value' in e) e.select(); else if (e.isContentEditable)"
                      " document.execCommand('selectAll'); return 1; })()")
        self.call("Input.insertText", text=str(text or ""))
        if enter:
            self.key("Enter")
        else:
            time.sleep(0.05)

    def key(self, name: str) -> None:
        key, code, vk, text, mods = parse_key(name)
        down = {"type": "keyDown" if text else "rawKeyDown", "key": key, "code": code, "windowsVirtualKeyCode": vk,
                "modifiers": mods}
        if text:
            down["text"] = text
        self.call("Input.dispatchKeyEvent", **down)
        self.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=code, windowsVirtualKeyCode=vk, modifiers=mods)
        self._settle()

    def scroll(self, where: str) -> None:
        w = str(where or "").strip().lower()
        if w in ("top", "bottom"):
            self.eval("window.scrollTo(0, %s)" % ("0" if w == "top" else "document.documentElement.scrollHeight"))
        elif w in ("up", "down"):
            dy = HEIGHT * 0.8 * (1 if w == "down" else -1)
            self.call("Input.dispatchMouseEvent", type="mouseWheel", x=WIDTH / 2, y=HEIGHT / 2, deltaX=0, deltaY=dy)
        else:
            raise BrowserError("scroll takes `text`: up, down, top or bottom.")
        time.sleep(0.2)

    def back(self) -> None:
        h = self.call("Page.getNavigationHistory")
        i, entries = int(h.get("currentIndex") or 0), h.get("entries") or []
        if i <= 0 or i >= len(entries) + 1 or not entries:
            raise BrowserError("There is no page before this one.")
        self.call("Page.navigateToHistoryEntry", entryId=entries[i - 1]["id"])
        self._settle()

    def js(self, expr: str) -> str:
        if not str(expr or "").strip():
            raise BrowserError("js needs `text`: the JavaScript to run in the page.")
        v = self.eval(str(expr))
        time.sleep(0.1)
        return v if isinstance(v, str) else "undefined" if v is None else json.dumps(v, ensure_ascii=False)

    def screenshot(self) -> bytes:
        return base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"])

    # -- close -----------------------------------------------------------------------------------------------------------
    def close(self) -> None:
        with self._mu:
            if self._closed:
                return
            self._closed = True
            proc, pipe = self.proc, self.pipe
            if pipe is not None and not pipe.closed:
                try:
                    pipe.call("Browser.close", {}, None, 3.0)
                except Exception:
                    pass
            if proc is not None:
                try:
                    proc.wait(timeout=CLOSE_WAIT_S)
                except Exception:
                    try:
                        proc.kill()
                        proc.wait(timeout=CLOSE_WAIT_S)
                    except Exception:
                        pass
            if pipe is not None:
                pipe.close()
            if self.job is not None:
                from halo_harness.browser_pipe_win import end_job
                end_job(self.job)
            if self.profile:
                end_profile_pids(self.profile)
            if proc is not None:
                try:
                    from halo_harness import children
                    children.unregister(proc.pid)
                except Exception:
                    pass
            if self.kind == "clean" and self.profile:
                for _ in range(20):  # Windows lets go of a folder a moment after its processes end
                    shutil.rmtree(self.profile, ignore_errors=True)
                    if not os.path.exists(self.profile):
                        break
                    time.sleep(0.1)
            if self._lock_fh is not None:
                try:
                    self._lock_fh.close()  # the lock goes with the handle
                except OSError:
                    pass
            self.proc = self.pipe = self.job = self.session = self._lock_fh = None
