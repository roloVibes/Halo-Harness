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
Halo's Job object on Windows), in the ledger as `browser` while it runs, and closed on every way out: `Browser.close`
(THE one way a browser ends: asked to close, up to END_WAIT_S for it to be gone, then every process that still carries
the profile ended BY PID (POSIX) or every process of the browser's own Job (Windows, browser_pipe_win.end_job)); then a
clean profile and its temp folder are removed. Every orderly way out of a session calls `end_browsers()` BEFORE any
other stop of its children (Controller.quit, the terminal app's force quit, the end of `halo -p`), and closing.on_close
runs it again for any other exit. A hard end of Halo closes the pipe, and the browser ends itself on its closed pipe
(and the reaper / the Job end what is left: a sign-in made in its last seconds may be lost).

NOTHING ELSE IS LEFT (batch 3): the browser's TMP, TEMP and TMPDIR are a temp folder of its own, `<halo home>/browser/
tmp/<pid>-<n>` (on Linux and macOS, a home too deep for the browser's socket gets `/tmp/halo-browser-<uid>/<pid>-<n>`
instead), removed when it ends (one a hard end left is swept by the next start: only when the pid in its name is no
longer alive; the sweep reads only these two folders, never the system's temp), and QUIET switches stop its own
background work (an updater, pings, reports). A download is staged in `<halo home>/browser/tmp/<pid>-<n>/downloads`
(always under Halo's home, so the move is one rename) and moved into `download_dir` only when the browser says it is
whole.

WHAT REAL PAGES DO (batch 2): an action that opens a new tab goes on IN it (NEW_TAB begins its answer; a current tab
that closes hands back to the one before it; there is always one current tab); a page's alert, confirm or prompt box
is answered at once on the pipe's reader thread (accepted; a prompt with its default text) and said (box_line); every
wait has a limit (LOAD_WAIT_S for a load, CONTROL_WAIT_S for a control to appear; STILL_LOADING when a load did not
end); a download lands in `download_dir` only (the session's attachments folder) and is said (downloaded_line).
THE WINDOW: `browser.window` hidden (the default) or shown, or `show=True` for one browser: a window a person can
watch (WINDOW_OPEN), or NO_DISPLAY and headless where there is no display.

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
import sys
import threading
import time
import weakref
from pathlib import Path
from typing import Optional

from halo_harness import subprocess_safe as subprocess  # a bare program name (`ps`) is never taken from the current folder

LOAD_WAIT_S = 15.0
CALL_WAIT_S = 30.0
START_WAIT_S = 60.0  # a cold start on a slow Windows CI runner; a healthy start answers in well under a second
CLOSE_WAIT_S = 5.0
END_WAIT_S = 3.0  # the longest any way out waits for the browser to close itself before it is stopped hard
# the browser's own background work, which nobody asked for and which writes temp files and goes to the network
QUIET = ("--disable-component-update", "--disable-background-networking", "--disable-domain-reliability", "--no-pings",
         "--disable-default-apps")
CONTROLS_MAX = 80
WIDTH, HEIGHT = 1280, 800
HEADLESS = ("--headless=new", "--disable-gpu", "--hide-scrollbars")
FLAGS = ("--no-first-run", "--no-default-browser-check", "--password-store=basic", "--use-mock-keychain",
         f"--window-size={WIDTH},{HEIGHT}")
PROFILES = ("kept", "clean")
IN_USE = "Another session is using Halo's browser profile; this one starts clean (not signed in)."
_SEQ = itertools.count(1)
_LIVE: "weakref.WeakSet" = weakref.WeakSet()  # every Browser this process started (end_browsers)


class BrowserError(RuntimeError):
    """A plain sentence a person (and the model) reads: what went wrong and what to do next."""


class NoBrowser(BrowserError):
    """No browser on this machine (browser_find.none_found())."""


class NoAnswer(BrowserError):
    """A call's wait ran out (its late answer is dropped)."""


NEW_TAB = "A new tab opened; now on it."
STILL_LOADING = "The page was still loading after 15 s; this is what it shows so far."
WINDOW_OPEN = "A browser window is open on your desktop."
NO_DISPLAY = "No display here: the browser runs without a window."
WINDOWS = ("hidden", "shown")
CONTROL_WAIT_S = 5.0


def box_line(message: str) -> str:
    """What an action's answer says for a page's alert, confirm or prompt box Halo answered at once."""
    return f"The page showed a box: '{' '.join(str(message or '').split())}' (accepted)."


def size_words(n: int) -> str:
    return f"{n} bytes" if n < 1024 else f"{n / 1024:.0f} KiB" if n < 1024 * 1024 else f"{n / 1048576:.1f} MiB"


def downloaded_line(path, size: int) -> str:
    return f"Downloaded: {path} ({size_words(size)})."


def window_setting() -> str:
    """`browser.window`: hidden (the default) or shown (every session's browser opens as a window on the desktop)."""
    try:
        from halo_harness.theme import get_config_value
        v = str(get_config_value("browser.window", default="hidden") or "hidden").strip().lower()
    except Exception:
        v = "hidden"
    return v if v in WINDOWS else "hidden"


def has_display() -> bool:
    """Windows and macOS always draw a window; Linux and the BSDs only with an X or Wayland display."""
    if os.name == "nt" or sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


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
        text = subprocess.run(["ps", "-axww", "-o", "pid=,command="], capture_output=True, text=True, timeout=10,
                              env=subprocess.Probe(dict(os.environ))).stdout  # Halo's own look: not a spawn (3.6.0.1)
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


SOCKET_MAX = 100  # a POSIX socket's address: 104 bytes on macOS, 108 on Linux (with its end)
SOCKET_TAIL = len("/.org.chromium.Chromium.XXXXXX/SingletonSocket")  # what the browser puts in its temp folder


SHORT_ROOT = "/tmp"  # POSIX, a home too deep for the socket: never TMPDIR (macOS's alone is about 48 characters)


def _fits(folder: Path) -> bool:
    return len(str(folder)) + SOCKET_TAIL <= SOCKET_MAX


def short_root() -> Optional[Path]:
    """POSIX: Halo's folder for the temp folders of a home too deep for the browser's socket, `/tmp/halo-browser-<uid>`
    (one per user: the sweep reads it alone, never the whole of /tmp); None on Windows."""
    return None if os.name == "nt" else Path(SHORT_ROOT) / f"halo-browser-{os.getuid()}"


def _own_short_root() -> bool:
    """The short root is made this user's own (0700) and is used only when it is: never a link, never another's."""
    d = short_root()
    try:
        d.mkdir(mode=0o700, exist_ok=True)
        st = os.lstat(d)
    except OSError:
        return False
    import stat
    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid() and not st.st_mode & 0o077


def temp_folders(root: Path) -> "tuple[Path, Optional[Path]]":
    """(own, tmp). `own` = `<root>/tmp/<pid>-<n>`: this browser's folder under Halo's home (its download staging).
    `tmp` = its TMP, TEMP and TMPDIR: `own`, except on Linux and macOS when `own` is too deep for the socket the browser
    keeps in it (a file, never a network port; its whole path must fit a socket's address): then
    `<short_root()>/<pid>-<n>`, and None when even that does not fit (the browser keeps the system's temp)."""
    name = f"{os.getpid()}-{next(_SEQ)}"
    own = Path(root) / "tmp" / name
    if os.name == "nt" or _fits(own):
        return own, own
    short = short_root() / name
    return own, (short if _fits(short) else None)


def sweep_temps(home=None) -> None:
    """A browser's temp folder whose session is gone (a hard end) is removed at the next start: only when the pid in its
    name is no longer alive (never by a name alone, never one in use). Reads Halo's two folders only (`<halo home>/
    browser/tmp` and, on POSIX, the short root), never the system's temp."""
    from halo_harness.children import pid_running
    found = []
    for root in (browser_home(home) / "tmp", short_root()):
        try:
            found += [(p, re.match(r"(\d+)-\d+$", p.name)) for p in root.iterdir() if p.is_dir()] if root else []
        except OSError:
            continue
    for p, m in found:
        if m and int(m.group(1)) != os.getpid() and not pid_running(int(m.group(1))):
            shutil.rmtree(p, ignore_errors=True)
    _drop_short_root()


def _make_short(folder: Path) -> bool:
    for _ in range(3):
        if not _own_short_root():
            return False
        try:
            folder.mkdir(exist_ok=True)
            return True
        except FileNotFoundError:
            continue  # another session dropped the empty root a moment before
        except OSError:
            return False
    return False


def _drop_short_root() -> None:
    """The short root goes when nothing is in it (another session's folder keeps it)."""
    d = short_root()
    if d is not None:
        try:
            d.rmdir()
        except OSError:
            pass


def _remove(folder) -> None:
    for _ in range(20):  # Windows lets go of a folder a moment after its processes end
        shutil.rmtree(folder, ignore_errors=True)
        if not os.path.exists(folder):
            return
        time.sleep(0.1)


def end_browsers(limit: Optional[float] = None) -> None:
    """THE orderly end of this process's browsers, which every orderly way out of a session calls BEFORE any other stop
    of its children: each one's Browser.close (asked to close, up to END_WAIT_S, then the hard stop by pid), all at
    once. Idempotent; never raises; never waits much past END_WAIT_S, nor past `limit` (a quit's share of its way-out
    deadline: a close still going then goes on beside the stops after it)."""
    live = [b for b in list(_LIVE) if b.proc is not None]
    threads = [threading.Thread(target=b.close, name="halo-browser-end", daemon=True) for b in live]
    for th in threads:
        th.start()
    wait = END_WAIT_S + 2.0  # the hard stop after the bound gets a moment
    end = time.monotonic() + (wait if limit is None else max(0.0, min(wait, limit)))
    for th in threads:
        th.join(max(0.0, end - time.monotonic()))


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
        self._drop: set = set()  # the ids of sends nobody waits for (and of calls whose wait ran out)
        self.on_event = None  # called on the reader thread with each event; it may send(), never call()
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
                    handler = None
                    with self.cv:
                        if "id" in msg:
                            if msg["id"] in self._drop:
                                self._drop.discard(msg["id"])
                            else:
                                self.answers[msg["id"]] = msg
                        else:
                            self.events = (self.events + [msg])[-200:]
                            handler = self.on_event
                        self.cv.notify_all()
                    if handler is not None:
                        try:
                            handler(msg)
                        except Exception:
                            pass
        except OSError:
            pass
        with self.cv:
            self.closed = True
            self.cv.notify_all()

    def _write(self, method: str, params: dict, session: Optional[str]) -> int:
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
        return mid

    def send(self, method: str, params: dict, session: Optional[str]) -> None:
        """A message nobody waits for (the reader thread answers a page's box this way: it cannot wait on itself)."""
        if self.closed:
            return
        mid = self._write(method, params, session)
        with self.cv:
            if self.answers.pop(mid, None) is None:
                self._drop.add(mid)

    def call(self, method: str, params: dict, session: Optional[str], timeout: float) -> dict:
        mid = self._write(method, params, session)
        end = time.monotonic() + timeout
        with self.cv:
            while mid not in self.answers:
                if self.closed:
                    raise BrowserError("The browser has closed. Call open to start it again.")
                left = end - time.monotonic()
                if left <= 0:
                    self._drop.add(mid)
                    raise NoAnswer(f"The browser did not answer {method} in {timeout:.0f} s.")
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


def _posix_spawn(argv: list, popen, env=None):
    """A tiny Python step puts the two pipe ends at descriptors 3 and 4 and execs the browser (its pid is the
    browser's); no code runs in the forked child before exec (no preexec_fn in a process with threads)."""
    import sys as _sys
    to_child_r, to_child_w = os.pipe()
    from_child_r, from_child_w = os.pipe()
    try:
        proc = popen([_sys.executable, "-I", "-S", "-c", _TRAMPOLINE, str(to_child_r), str(from_child_w), argv[0],
                      "--remote-debugging-pipe", *argv[1:]], pass_fds=(to_child_r, from_child_w),
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, env=env)  # a Ctrl+C at the terminal stops a turn, never the browser
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
                 show: Optional[bool] = None):
        self.want = profile if profile in PROFILES else profile_setting()
        self.want_show = (window_setting() == "shown") if show is None else bool(show)
        self.home, self.exe, self.show = home, exe, self.want_show
        self.popen = popen
        self.download_dir: Optional[Path] = None  # where a download lands (the tool: the session's attachments)
        self.loaded = True  # whether the last action's load ended within LOAD_WAIT_S
        self.tabs: "list[str]" = []  # the tabs, oldest first; the last is the current one
        self.sessions: dict = {}  # target id -> DevTools session id
        self._seen: set = set()  # every page target met so far
        self._downloads: dict = {}  # guid -> {"name", "state", "said"}
        self._auto: dict = {}  # target id -> the session its automatic attach made (a new tab, held at its start)
        self._first: dict = {}  # DevTools session id -> where in `notes` its first line is (NEW_TAB goes before it)
        self.tmp: Optional[Path] = None  # the browser's own temp folder (its TMP, TEMP, TMPDIR)
        self.stage: Optional[Path] = None  # its folder under Halo's home (downloads staged in `downloads`)
        self._nmu = threading.Lock()  # the notes: the reader thread adds a box's line
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
            sweep_temps(self.home)
            self._pick_profile(root)
            self._pick_window()
            self.tabs, self.sessions, self._seen, self._downloads, self._auto = [], {}, set(), {}, {}
            self.stage, self.tmp = temp_folders(root)
            (self.stage / "downloads").mkdir(parents=True, exist_ok=True)
            if self.tmp is not None and self.tmp != self.stage and not _make_short(self.tmp):
                self.tmp = None  # the short root is not this user's own: the browser keeps the system's temp
            try:
                self._spawn()
                self._attach()
            except BaseException:
                self.close()
                raise
            return self

    def _pick_window(self) -> None:
        """A window when one was asked for and this machine can draw it; the first answer says which."""
        self.show = self.want_show and has_display()
        if self.want_show:
            self.notes.insert(0, WINDOW_OPEN if self.show else NO_DISPLAY)

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
        return [self.exe, *(() if self.show else HEADLESS), *FLAGS, *QUIET, *extra, f"--user-data-dir={self.profile}",
                "about:blank"]

    def env(self) -> dict:
        """This process's environment with the temp folder the browser's own: what it writes as temporary is there."""
        if self.tmp is None:
            return dict(os.environ)
        t = str(self.tmp)
        return {**os.environ, "TMP": t, "TEMP": t, "TMPDIR": t}

    def _spawn(self) -> None:
        from halo_harness import subprocess_safe
        popen = self.popen or subprocess_safe.Popen
        if os.name == "nt":
            from halo_harness.browser_pipe_win import spawn
            self.proc, rfd, wfd, self.job = spawn(self.argv(), popen, show=self.show, env=self.env())
        else:
            self.proc, rfd, wfd, self.job = _posix_spawn(self.argv(), popen, env=self.env())
        _LIVE.add(self)
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
        self._seen = {t["targetId"] for t in pages}
        target = next((t["targetId"] for t in pages if t.get("url") == "about:blank"), None) or \
            (pages[0]["targetId"] if pages else None)
        self.pipe.on_event = self._on_event
        if target is None:
            target = self._new_blank()
        self._take_tab(target)
        # a new tab is taken over BEFORE its page runs: attached automatically and held at its start, its page events
        # switched on, then let go (_on_event), so a box in its first moment is answered like any other
        self.pipe.call("Target.setAutoAttach", {"autoAttach": True, "waitForDebuggerOnStart": True, "flatten": True},
                       None, CALL_WAIT_S)
        if self.download_dir is not None:
            Path(self.download_dir).mkdir(parents=True, exist_ok=True)
            self.pipe.call("Browser.setDownloadBehavior", {"behavior": "allowAndName", "eventsEnabled": True,
                                                           "downloadPath": str(self.stage / "downloads")}, None,
                           CALL_WAIT_S)  # staged in Halo's own folder; moved into download_dir only when whole

    def _new_blank(self) -> str:
        tid = self.pipe.call("Target.createTarget", {"url": "about:blank"}, None, CALL_WAIT_S)["targetId"]
        self._seen.add(tid)
        return tid

    def _take_tab(self, target: str) -> None:
        """Attach to `target` (the session its automatic attach made, when it has one), make it the current tab (the
        last of `tabs`)."""
        sid, end = self._auto.get(target), time.monotonic() + 0.5
        while sid is None and self.sessions and time.monotonic() < end:  # its attach event is on its way
            time.sleep(0.02)
            sid = self._auto.get(target)
        if sid is None:
            sid = self.pipe.call("Target.attachToTarget", {"targetId": target, "flatten": True}, None,
                                 CALL_WAIT_S)["sessionId"]
        self.sessions[target] = sid
        self.tabs = [t for t in self.tabs if t != target] + [target]
        self.session = sid
        self.call("Page.enable")

    # -- what the page and the browser say while an action runs (the reader thread) ------------------------------------
    def _note(self, line: str, sid: Optional[str] = None) -> None:
        with self._nmu:
            if sid:
                self._first.setdefault(sid, len(self.notes))
            self.notes.append(line)

    def _note_new_tab(self, sid: str) -> None:
        """NEW_TAB, said before anything the new tab itself said (a box in its first moment)."""
        with self._nmu:
            i = self._first.get(sid)
            if i is None:
                self.notes.append(NEW_TAB)
                return
            self.notes.insert(i, NEW_TAB)
            self._first = {k: v + 1 if v >= i else v for k, v in self._first.items()}

    def take_notes(self) -> "list[str]":
        """The lines the next answer begins with, in the order they happened; emptied."""
        with self._nmu:
            out, self.notes, self._first = list(self.notes), [], {}
        return out

    def _on_event(self, msg: dict) -> None:
        method, p = msg.get("method"), msg.get("params") or {}
        if method == "Target.attachedToTarget":
            info, sid = p.get("targetInfo") or {}, p.get("sessionId")
            tid = info.get("targetId")
            if sid and tid and info.get("type") == "page" and tid not in self.sessions:
                self._auto[tid] = sid
                self.pipe.send("Page.enable", {}, sid)  # its boxes are seen from its first moment
            if sid and p.get("waitingForDebugger"):
                self.pipe.send("Runtime.runIfWaitingForDebugger", {}, sid)  # and only then it runs
        elif method == "Page.javascriptDialogOpening":
            # answered AT ONCE so the page never freezes: alert and confirm accepted, prompt with its default text
            answer = {"accept": True}
            if p.get("type") == "prompt":
                answer["promptText"] = str(p.get("defaultPrompt") or "")
            self.pipe.send("Page.handleJavaScriptDialog", answer, msg.get("sessionId"))
            self._note(box_line(p.get("message")), msg.get("sessionId"))
        elif method == "Browser.downloadWillBegin" and p.get("guid"):
            with self._nmu:
                self._downloads[p["guid"]] = {"name": str(p.get("suggestedFilename") or ""), "state": "inProgress",
                                              "said": False}
        elif method == "Browser.downloadProgress" and p.get("guid"):
            with self._nmu:
                d = self._downloads.setdefault(p["guid"], {"name": "", "state": "inProgress", "said": False})
                d["state"] = str(p.get("state") or d["state"])

    # -- after an action: a new tab, a closed one, the load, a download -------------------------------------------------
    def _follow_tabs(self) -> None:
        """A tab the action opened becomes the current one (its answer begins NEW_TAB); a current tab that closed
        hands back to the one before it; there is always exactly one current tab."""
        infos = self.pipe.call("Target.getTargets", {}, None, CALL_WAIT_S).get("targetInfos") or []
        pages = [t for t in infos if t.get("type") == "page"]
        alive = {t["targetId"] for t in pages}
        self.tabs = [t for t in self.tabs if t in alive]
        new = [t["targetId"] for t in pages if t["targetId"] not in self._seen]
        self._seen |= alive
        for tid in new:
            try:
                self._take_tab(tid)
            except BrowserError:
                continue
            self._note_new_tab(self.sessions[tid])
            end = time.monotonic() + 2.0  # a new tab is about:blank until its own address commits
            while time.monotonic() < end:
                try:
                    if self.eval("location.href", timeout=2.0) != "about:blank":
                        break
                except BrowserError:
                    pass
                time.sleep(0.1)
        was = self.session
        if not self.tabs:
            self._take_tab(self._new_blank())
        elif self.sessions.get(self.tabs[-1]) != self.session:
            self.session = self.sessions[self.tabs[-1]]
        if new or was != self.session:  # the current tab is the one in front (its picture is the one taken)
            try:
                self.pipe.call("Target.activateTarget", {"targetId": self.tabs[-1]}, None, CALL_WAIT_S)
            except BrowserError:
                pass

    def _finish_downloads(self, until: float) -> None:
        """Each download that began: wait (up to `until`) for its end, give it its own name in the download folder
        and say where it is. One still going is said by a later answer, once it has ended."""
        if self.download_dir is None:
            return
        while True:
            with self._nmu:
                going = [g for g, d in self._downloads.items() if not d["said"] and d["state"] == "inProgress"]
                done = [(g, d) for g, d in self._downloads.items() if not d["said"] and d["state"] == "completed"]
                for _g, d in done:
                    d["said"] = True
            for g, d in done:
                path = self._name_download(g, d["name"])
                if path is not None:
                    self._note(downloaded_line(path, path.stat().st_size))
            if not going or time.monotonic() >= until:
                return
            time.sleep(0.1)

    def _name_download(self, guid: str, name: str) -> Optional[Path]:
        """A whole download moves from the staging folder into `download_dir` under its own name (a taken name gets
        " (2)" before its ending, never an overwrite)."""
        folder = Path(self.download_dir)
        got = (self.stage / "downloads" / guid) if self.stage else folder / guid
        end = time.monotonic() + 2.0  # the browser renames its part file a moment after it says "completed"
        while not got.is_file() and time.monotonic() < end:
            time.sleep(0.05)
        if not got.is_file():
            return None
        safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", os.path.basename(name or "")).strip(" .") or "download"
        stem, ext = os.path.splitext(safe)
        folder.mkdir(parents=True, exist_ok=True)
        path, n = folder / safe, 2
        while path.exists():
            path, n = folder / f"{stem} ({n}){ext}", n + 1
        for _ in range(20):  # one rename (staging is under Halo's home); Windows may hold a file it just wrote a moment
            try:
                shutil.move(str(got), str(path))
                return path
            except OSError:
                time.sleep(0.1)
        return None

    def _settle(self) -> bool:
        """After an action: a moment for a navigation or a new tab to begin, the tab followed, its load waited for (up
        to LOAD_WAIT_S), a download's end too. Sets and returns `loaded`."""
        until = time.monotonic() + LOAD_WAIT_S
        time.sleep(0.3)
        self._follow_tabs()
        self.loaded = self.wait_loaded(max(0.5, until - time.monotonic()))
        self._finish_downloads(until)
        return self.loaded

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
        until = time.monotonic() + wait_s
        try:
            r = self.call("Page.navigate", wait_s, url=url)
        except NoAnswer:  # the page's own address never answered: what is there is the answer
            self.loaded = False
            return False
        if r.get("errorText"):
            time.sleep(0.3)  # an address that is a download ends its navigation "aborted" as the download begins
            with self._nmu:
                began = any(not d["said"] for d in self._downloads.values())
            if not began:
                raise BrowserError(f"The page did not open: {r['errorText']} ({url}).")
        self.loaded = self.wait_loaded(max(0.5, until - time.monotonic()))
        self._finish_downloads(until)
        return self.loaded

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
        end = time.monotonic() + CONTROL_WAIT_S  # a control still to appear is waited for, up to 5 s
        got = self.eval(f"{_FIND_JS}({json.dumps(how)}, {json.dumps(what)})")
        while got == "none" and how != "n" and time.monotonic() < end:
            time.sleep(0.2)
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

    def press(self, target) -> bool:
        x, y = self._locate(target)
        for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
            self._mouse(kind, x, y)
        return self._settle()

    def type_into(self, target, text: str, enter: bool = False) -> bool:
        if target not in (None, ""):
            x, y = self._locate(target)
            for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
                self._mouse(kind, x, y)
            self.eval("(() => { const e = document.activeElement; if (!e) return 0;"
                      " if (e.select && 'value' in e) e.select(); else if (e.isContentEditable)"
                      " document.execCommand('selectAll'); return 1; })()")
        self.call("Input.insertText", text=str(text or ""))
        if enter:
            return self.key("Enter")
        time.sleep(0.05)
        self.loaded = True
        return True

    def key(self, name: str) -> bool:
        key, code, vk, text, mods = parse_key(name)
        down = {"type": "keyDown" if text else "rawKeyDown", "key": key, "code": code, "windowsVirtualKeyCode": vk,
                "modifiers": mods}
        if text:
            down["text"] = text
        self.call("Input.dispatchKeyEvent", **down)
        self.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=code, windowsVirtualKeyCode=vk, modifiers=mods)
        return self._settle()

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
        self.loaded = True

    def back(self) -> bool:
        h = self.call("Page.getNavigationHistory")
        i, entries = int(h.get("currentIndex") or 0), h.get("entries") or []
        if i <= 0 or i >= len(entries) + 1 or not entries:
            raise BrowserError("There is no page before this one.")
        self.call("Page.navigateToHistoryEntry", entryId=entries[i - 1]["id"])
        return self._settle()

    def js(self, expr: str) -> str:
        if not str(expr or "").strip():
            raise BrowserError("js needs `text`: the JavaScript to run in the page.")
        v = self.eval(str(expr))
        self._settle()  # a script may open a tab, go to another address or start a download
        return v if isinstance(v, str) else "undefined" if v is None else json.dumps(v, ensure_ascii=False)

    def collect(self) -> None:
        """A download that ended since the last action is said in this answer (no wait)."""
        if self.pipe is not None:
            self._finish_downloads(time.monotonic())

    def screenshot(self) -> bytes:
        return base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"])

    # -- close -----------------------------------------------------------------------------------------------------------
    def close(self) -> None:
        with self._mu:
            if self._closed:
                return
            self._closed = True
            proc, pipe = self.proc, self.pipe
            end = time.monotonic() + END_WAIT_S  # asked, up to END_WAIT_S to be gone, then the hard stop by pid
            if pipe is not None and not pipe.closed:
                try:
                    pipe.call("Browser.close", {}, None, END_WAIT_S)
                except Exception:
                    pass
            if proc is not None:
                try:
                    proc.wait(timeout=max(0.0, end - time.monotonic()))
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
                end_profile_pids(self.profile, wait_s=max(0.0, end - time.monotonic()))
            if proc is not None:
                try:
                    from halo_harness import children
                    children.unregister(proc.pid)
                except Exception:
                    pass
            if self.kind == "clean" and self.profile:
                _remove(self.profile)
            if self.stage is not None:
                _remove(self.stage)  # the download staging (and its temp files when they were there) go with it
            if self.tmp is not None and self.tmp != self.stage:
                _remove(self.tmp)
                _drop_short_root()
            if self._lock_fh is not None:
                try:
                    self._lock_fh.close()  # the lock goes with the handle
                except OSError:
                    pass
            self.proc = self.pipe = self.job = self.session = self._lock_fh = None
