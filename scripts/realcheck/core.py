"""scripts/realcheck/core.py -- what every step stands on: a scratch home per launch, the environment a person's
terminal gives `halo` (with the home moved into scratch), the ways to start `halo`, and the scan of what is still
running under a home.

The environment: everything of this shell except Halo's, the providers' and Claude Code's own variables; HOME,
USERPROFILE, APPDATA, LOCALAPPDATA, XDG_*, TMP / TEMP / TMPDIR inside the scratch home (BRIDGE_TEST_HOME too: the
same folder, and Halo's switch that keeps a scratch launch off the machine's firewall); the fake provider through
BRIDGE_OPENROUTER_BASE_URL with a made-up key; OLLAMA_HOST at a dead loopback port unless a step gives its fake one;
a truecolor terminal (TERM, COLORTERM); and a browser (BROWSER) that writes down the URL it is asked to open."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from realcheck import fakes, procs

SCRUB = ("HALO_", "BRIDGE_", "OPENROUTER_", "ANTHROPIC_", "DATABRICKS_", "OPENAI_", "HF_", "HUGGING", "CLAUDE_",
         "ROLO_", "OLLAMA_", "SSH_", "TMUX", "TERM_PROGRAM", "WT_SESSION", "PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")
DEAD_OLLAMA = "http://127.0.0.1:9"


class Fail(Exception):
    def __init__(self, detail: str, evidence: "dict | None" = None, expected_until: str = "") -> None:
        super().__init__(detail)
        self.detail, self.evidence, self.expected_until = detail, evidence or {}, expected_until


class Skip(Exception):
    pass


@dataclass
class Home:
    name: str
    dir: Path      # root/<name>: everything of this launch
    home: Path     # the home directory Halo sees
    proj: Path     # the project folder it runs in
    tmp: Path
    browser: str
    opened: Path   # the URLs the "browser" was asked to open
    pids: dict = field(default_factory=dict)  # {pid: start time} of what this script started for this launch

    @property
    def state(self) -> Path:
        return self.home / ".halo"

    def needles(self) -> list:
        return procs.needles_for(self.dir)


@dataclass
class Ran:
    code: "int | None"
    out: str
    err: str
    seconds: float


class Ctx:
    def __init__(self, repo: Path, root: Path, *, installed: bool = False, real_local: str = "") -> None:
        self.repo, self.root, self.installed, self.real_local = Path(repo), Path(root), installed, real_local
        self.homes: list = []
        self.started: dict = {}     # {pid: start time} of every process this script started itself
        self.terms: list = []
        self.popens: list = []
        self._provider = None
        self.notes: dict = {}
        self.chrome, self.chrome_from = "", "--browser"  # 3.6.0.1: the browser the steps may use (see browser())

    # -- the fakes -------------------------------------------------------------------------------------------------
    @property
    def provider(self) -> "fakes.Provider":
        if self._provider is None:
            self._provider = fakes.Provider().start()
        return self._provider

    # -- homes and environments ------------------------------------------------------------------------------------
    def home(self, name: str) -> Home:
        d = self.root / f"{name}-{len(self.homes)}"
        home, proj, tmp = d / "home", d / "proj", d / "tmp"
        for p in (home, proj, tmp):
            p.mkdir(parents=True, exist_ok=True)
        browser, opened = fakes.browser_command(d)
        h = Home(name, d, home, proj, tmp, browser, opened)
        self.homes.append(h)
        return h

    def env(self, h: Home, **extra) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(SCRUB)}
        env.update(HOME=str(h.home), USERPROFILE=str(h.home), BRIDGE_TEST_HOME=str(h.home),
                   TMP=str(h.tmp), TEMP=str(h.tmp), TMPDIR=str(h.tmp), OLLAMA_HOST=DEAD_OLLAMA,
                   OPENROUTER_API_KEY="sk-or-realcheck-not-a-key", BRIDGE_OPENROUTER_BASE_URL=self.provider.base_url,
                   TERM="xterm-256color", COLORTERM="truecolor", BROWSER=h.browser, REALCHECK_HOME=str(h.dir))
        if sys.platform == "win32":
            env.update(APPDATA=str(h.home / "AppData" / "Roaming"), LOCALAPPDATA=str(h.home / "AppData" / "Local"))
        else:
            env.update(XDG_CONFIG_HOME=str(h.home / ".config"), XDG_DATA_HOME=str(h.home / ".local" / "share"),
                       XDG_CACHE_HOME=str(h.home / ".cache"), XDG_STATE_HOME=str(h.home / ".local" / "state"))
            if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
                env["WAYLAND_DISPLAY"] = "realcheck-desktop"  # a desktop session: Halo may open a browser
        if not self.installed:
            env["PYTHONPATH"] = str(self.repo)
        env.update({k: str(v) for k, v in extra.items() if v is not None})
        for k in [k for k, v in extra.items() if v is None]:
            env.pop(k, None)
        return env

    def argv(self, *args: str) -> list:
        if self.installed:
            exe = shutil.which("halo")
            if not exe:
                raise Skip("--installed: no `halo` on PATH")
            return [exe, *args]
        return [sys.executable, "-m", "halo_harness", *args]

    # -- starting halo -----------------------------------------------------------------------------------------------
    def run(self, h: Home, *args: str, timeout: float = 60, env: "dict | None" = None, stdin: str = "") -> Ran:
        """`halo <args>` to the end, its output captured (no terminal: a script's or a pipe's launch)."""
        t = time.monotonic()
        p = subprocess.Popen(self.argv(*args), cwd=str(h.proj), env=env or self.env(h), stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._mark(h, p.pid)
        try:
            out, err = p.communicate(stdin.encode("utf-8"), timeout=timeout)
            code = p.returncode
        except subprocess.TimeoutExpired:
            p.kill()
            out, err = p.communicate()
            code = None
        dec = lambda b: (b or b"").decode("utf-8", "replace").replace("\r\n", "\n")  # noqa: E731
        return Ran(code, dec(out), dec(err), time.monotonic() - t)

    def terminal(self, h: Home, *args: str, env: "dict | None" = None, cols: int = 120, rows: int = 40):
        """`halo <args>` in a terminal of its own (a pty / a pseudoconsole), as typed into a terminal window."""
        from realcheck.term import Terminal
        t = Terminal(self.argv(*args), env=env or self.env(h), cwd=str(h.proj), cols=cols, rows=rows)
        self._mark(h, t.pid)
        self.terms.append(t)
        return t

    # -- what is still running -----------------------------------------------------------------------------------------
    def ours(self, h: "Home | None" = None) -> dict:
        """{pid: Proc} still running under `h` (or under the whole scratch root)."""
        for t in self.terms:  # reap what has ended (POSIX: an unreaped child is a zombie, listed but gone)
            t.poll()
        needles = h.needles() if h is not None else procs.needles_for(self.root)
        return procs.belonging(procs.snapshot(), needles, roots=h.pids if h is not None else self.started)

    def _mark(self, h: Home, pid: int) -> None:
        self.started[pid] = h.pids[pid] = procs.started_at(pid)

    def left_after(self, h: Home, seconds: float = 5.0) -> list:
        """The processes of `h` still alive `seconds` from now (polled; returns early once none is left)."""
        end = time.monotonic() + seconds
        while True:
            left = list(self.ours(h).values())
            if not left or time.monotonic() >= end:
                return left
            time.sleep(0.25)

    def end_leftovers(self, h: "Home | None" = None) -> list:
        """End what is still running under `h` (each one verified as ours by the scan) and say what it was."""
        said = []
        for _ in range(3):
            left = list(self.ours(h).values())
            if not left:
                break
            for p in left:
                if procs.kill(p):
                    said.append(f"{p.short(120)} [{p.why}]")
            time.sleep(0.5)
        return said

    def ctrl_c(self) -> dict:
        """Whether a typed Ctrl+C reaches a program in a terminal on this host (term.ctrl_c_probe), read once."""
        if "ctrl_c" not in self.notes:
            from realcheck.term import ctrl_c_probe
            self.notes["ctrl_c"] = ctrl_c_probe(self.root)
        return self.notes["ctrl_c"]

    def close(self) -> None:
        for t in self.terms:
            try:
                t.hard_kill()
                t.cleanup()
            except Exception:
                pass
        self.end_leftovers(None)
        if self._provider is not None:
            self._provider.stop()


URL = r"http://127\.0\.0\.1:\d+/[^\s'\"]*"


def browser(ctx) -> "str | None":
    """The browser a step that opens one uses: its FIRST act, before any `halo` starts (3.6.0.1). `--browser none`
    (or REALCHECK_BROWSER=none): Skip naming the switch. A browser named there (a path, or a command name on PATH):
    that one, or a Fail saying it names nothing. Not set: tests/helpers/chrome_driver.find_chrome (HALO_CHROME, else
    an installed Chrome; None when there is none). Whichever: headless, with a throw-away profile (tests/helpers/cdp.py),
    never the person's own Chrome profile and never a window on the desktop."""
    from halo_harness.browser_find import named_browser
    from tests.helpers.chrome_driver import ChromeNotFound, find_chrome
    sep = "=" if ctx.chrome_from.startswith("REALCHECK") else " "
    if ctx.chrome == "none":
        raise Skip(f"no browser may be used here ({ctx.chrome_from}{sep}none)")
    if ctx.chrome:
        found = named_browser(ctx.chrome)
        if not found:
            raise Fail(f"the browser named by {ctx.chrome_from} does not exist: {ctx.chrome}")
        return found
    try:
        return find_chrome()
    except ChromeNotFound as e:
        raise Fail(str(e)) from None


def split_url(url: str) -> "tuple[str, str]":
    """(the page's base `http://127.0.0.1:<port>`, the token from its `#t=` fragment)."""
    import re
    m = re.match(r"(http://127\.0\.0\.1:\d+)", url)
    t = re.search(r"#t=([A-Za-z0-9_\-]+)", url)
    return (m.group(1) if m else ""), (t.group(1) if t else "")


def http_get(url: str, token: str = "", timeout: float = 10.0) -> "tuple[int, bytes, float]":
    """(status, body, seconds) of one GET on loopback (no proxy); status 0 when nothing answered."""
    import urllib.error
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token} if token else {})
    t = time.monotonic()
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read(), time.monotonic() - t
    except urllib.error.HTTPError as e:
        return e.code, e.read() or b"", time.monotonic() - t
    except (OSError, ValueError):
        return 0, b"", time.monotonic() - t


def wait_until(fn, timeout: float, step: float = 0.05):
    end = time.monotonic() + timeout
    while True:
        try:
            got = fn()
        except Exception:
            got = None
        if got or time.monotonic() >= end:
            return got
        time.sleep(step)


def wait_address(ctx, h, t, limit: float = 60.0) -> "tuple[str, float, list]":
    """(the Studio address the terminal printed or '', seconds after launch, what ran meanwhile). A slow start is
    measured to `limit` rather than cut at a step's budget, and the processes seen under the home every 2 s while
    waiting are kept (the evidence of what it waited on)."""
    import re
    seen: list = []
    next_sample = 0.0
    while True:
        m = re.search(URL, t.plain())
        el = time.monotonic() - t.started_at
        if m:
            return m.group(0), el, seen
        if el >= limit or t.poll() is not None:
            return "", el, seen
        if el >= next_sample:
            next_sample = el + 2.0
            for p in ctx.ours(h).values():
                line = f"{el:.0f}s {p.name}: {' '.join(p.cmdline.split())[:110]}"
                if p.pid not in h.pids and not any(line.split(" ", 1)[1] == s.split(" ", 1)[1] for s in seen):
                    seen.append(line)
        time.sleep(0.1)


def excerpt(text: str, n: int = 300) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else "..." + text[-n:]
