"""tests.test_closing_real_halo -- the closing procedure of the REAL `halo` (3.6.0.0 R10), not a stand-in.

tests/test_closing.py ends owners that install the closing procedure themselves (tests/helpers/closing_owner.py, a
`python -c` that calls closing.install()): with `halo` itself no longer installing it (cli.main skipping
closing.install()) 23 of its 24 tests still passed. Here the real `halo init` (`python -m halo_harness init`, the way
the console script runs cli.main) starts in a terminal of its own (a pty / a pseudoconsole: scripts/realcheck's
Terminal) in a scratch home, prints its Studio's address, and is ended the ways a person ends it: Ctrl+C (Ctrl+Break
where a launcher switched Ctrl+C off, and said), its terminal closed, a hard kill of the top process. The Studio it
started (its pid and start time from studio.json) must be gone within BOUND_S, and nothing started under the scratch
home may be left. Nothing here talks to a network: the provider and the browser are scripts/realcheck's stand-ins."""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from realcheck import core, procs  # noqa: E402
from realcheck.steps_close import HOW, _end, _studio_pid  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BOUND_S = 10.0  # the Studio a launch started is gone this long after the launch ended


def _same(pid: int, started: float) -> bool:
    """`pid` still names the process that started at `started` (never another program the pid was given to)."""
    if not pid or not procs.alive(pid):
        return False
    now = procs.started_at(pid)
    return not started or not now or abs(now - started) <= 2


def _close_init(c: "core.Ctx", how: str) -> dict:
    h = c.home("init")
    env = c.env(h, HALO_NO_UPDATER="1", BRIDGE_TEST_NO_BACKGROUND_NET="1")
    t = c.terminal(h, "init", env=env)
    row: dict = {"how": how}
    try:
        url, at, _seen = core.wait_address(c, h, t, 60)
        row["address_s"] = round(at, 1)
        if not url:
            row["not_up"] = core.excerpt(t.plain(), 300) or f"exit {t.poll()}"
            return row
        pid = _studio_pid(h)
        started = procs.started_at(pid) if pid else 0.0
        row.update(studio=pid, studio_alive=_same(pid, started), init_alive=t.poll() is None)
        row["keys"] = _end(c, t, how, full_screen=False)
        end = time.monotonic() + BOUND_S
        while _same(pid, started) and time.monotonic() < end:
            time.sleep(0.2)
        row["studio_alive_after"] = _same(pid, started)
        row["left"] = [f"{p.short(110)} [{p.why}]" for p in c.left_after(h, 5.0)]
        return row
    finally:
        t.cleanup()
        c.end_leftovers(h)


def _check(ctx: Ctx, how: str) -> None:
    c = core.Ctx(REPO, Path(tempfile.mkdtemp(prefix="rc-close-init-")))
    try:
        row = _close_init(c, how)
    finally:
        c.close()
    ctx.check(f"`halo init` printed its Studio's address ({row.get('not_up', '')!r})", "not_up" not in row)
    ctx.check(f"before it was ended, `halo init` and the Studio it started both ran (not a vacuous check), got {row}",
              row["init_alive"] and row["studio"] and row["studio_alive"])
    ctx.check(f"{row['keys']}: its Studio (pid {row['studio']}) gone within {BOUND_S:.0f} s, got {row}",
              not row["studio_alive_after"])
    ctx.check(f"{row['keys']}: nothing started under the scratch home left 5 s later, got {row['left']}", not row["left"])


@test
def test_a_real_halo_init_ended_by_ctrl_c_takes_its_studio_with_it(ctx: Ctx):
    _check(ctx, HOW[0])


@test
def test_a_real_halo_init_whose_terminal_closes_takes_its_studio_with_it(ctx: Ctx):
    _check(ctx, HOW[1])


@test
def test_a_real_halo_init_killed_hard_takes_its_studio_with_it(ctx: Ctx):
    _check(ctx, HOW[2])


GONE_S = 5.0  # the ONE look for leftovers, this long after the Halo process has gone (never a poll that waits them away)
# 3.6.0.18 L: whether the Halo process ITSELF is gone is never read against a small wall-clock constant: a stand-in
# holds the worker for a long named time and the process must be gone before half of it (a way out that waited on the
# stand-in would be gone only after all of it), and where the close trace is on, its phases came in this order.
_PHASES = ("quit asked", "app exit asked", "app.run returned", "app.run's finally done", "close: start", "close: end",
           "hard exit armed")


def _phases(trace: Path) -> list:
    """The way out's phases (_PHASES) in the order the process's close trace wrote them, each the first time."""
    try:
        lines = trace.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    seen: list = []
    for line in lines:
        what = line.split("] ", 1)[-1]
        for phase in _PHASES:
            if what.startswith(phase) and phase not in seen:
                seen.append(phase)
    return seen


def _gone_by(t, seconds: float) -> bool:
    """True once the process `t` has gone, waiting at most `seconds` (half a stand-in's hold) for it."""
    end = time.monotonic() + seconds
    while t.poll() is None and time.monotonic() < end:
        time.sleep(0.1)
    return t.poll() is not None


def _session_while_the_check_hangs(c: "core.Ctx") -> dict:
    """A real terminal session (bare `halo`) in a scratch home with no update cache: its update check at the start
    runs the stand-in `git` (tests/helpers/hanging_git.py: a hanging network), which is still waiting when the session
    is ended with Ctrl+C (its "Quit Halo?" answered with Enter, as a person does)."""
    import os
    from realcheck import screen
    from realcheck.steps_close import _noter
    from tests.helpers import hanging_git
    h = c.home("session")
    folder = hanging_git.make(h.dir / "git-standin")
    trace = h.dir / "close-trace.txt"
    # Never the real network: git is a stand-in, and every HTTP(S) request (the check's fallback to the API, and
    # anything else the session asks) goes to a proxy on a dead loopback port and fails at once.
    dead = "http://127.0.0.1:9"
    proxies = {k: dead for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")}
    env = c.env(h, PATH=f"{folder}{os.pathsep}{os.environ.get('PATH', '')}", HALO_NO_UPDATER="1",
                BRIDGE_TEST_NO_BACKGROUND_NET=None, HALO_OFFLINE=None, HALO_CLOSE_TRACE=str(trace),
                NO_PROXY=None, no_proxy=None, **proxies)
    t = c.terminal(h, env=env)
    row: dict = {}
    rows: list = []
    first = None
    try:
        end = time.monotonic() + 90
        while time.monotonic() < end and t.poll() is None:
            rows = hanging_git.seen(folder)
            if rows and first is None:
                first = time.monotonic()
            if rows and screen.READY.search(t.plain()):
                break
            time.sleep(0.2)
        row["standins"] = rows
        row["standins_alive"] = hanging_git.alive(rows)
        if not (rows and screen.READY.search(t.plain())):
            row["not_up"] = core.excerpt(t.plain(), 300) or f"exit {t.poll()}"
            return row
        time.sleep(1.0)  # keys typed the moment the status line shows may not be taken (the realcheck re-presses then)
        # the close must land DURING the hang: git and its helper still alive as the keys go (else nothing is proved)
        row["standins_alive_at_close"] = hanging_git.alive(rows)
        row["hung_s_at_close"] = round(time.monotonic() - (first or time.monotonic()), 1)
        row["keys"] = _end(c, t, HOW[0], full_screen=True, note=_noter(trace))
        row["halo_alive_after"] = not _gone_by(t, hanging_git.HOLD_S / 2)  # the stand-in git holds HOLD_S
        row["phases"] = _phases(trace)
        if not row["halo_alive_after"]:
            time.sleep(GONE_S)  # the one look, GONE_S after the process has gone
        row["standins_alive_after"] = hanging_git.alive(rows)
        row["left"] = [f"{p.short(110)} [{p.why}]" for p in c.left_after(h, 0.5)]
        return row
    finally:
        hanging_git.end(rows or hanging_git.seen(folder))
        t.cleanup()
        c.end_leftovers(h)


@test
def test_z1_a_session_closed_while_its_update_check_hangs_is_gone_with_its_git(ctx: Ctx):
    """3.6.0.17 Z1 (a): the closing rule while the network hangs: the Halo process gone after the Ctrl+C before half
    the stand-in git's hold, its way out's phases in order, and neither git nor its helper alive GONE_S after it had
    gone (by pid and start time). 3.6.0.18 L: the close must still land within the update check's own budget
    (update.CHECK_TIMEOUT_S) of git's start; the product has no door that makes it longer, so a slow start can still
    make the not-vacuous guard below red (said, never loosened)."""
    c = core.Ctx(REPO, Path(tempfile.mkdtemp(prefix="rc-close-z1-")))
    try:
        row = _session_while_the_check_hangs(c)
    finally:
        c.close()
    ctx.check(f"the session came up and its update check's git and helper ran (not a vacuous check), got {row}",
              "not_up" not in row and len(row["standins_alive"]) == 2)
    ctx.check(f"the close landed while the check's git and helper still hung (not a vacuous check), got {row}",
              len(row.get("standins_alive_at_close") or []) == 2)
    from tests.helpers import hanging_git
    ctx.check(f"{row.get('keys')}: the Halo process gone before half the stand-in's {hanging_git.HOLD_S} s hold, "
              f"got {row}", not row["halo_alive_after"])
    ctx.check(f"{row.get('keys')}: its way out's phases in order, got {row.get('phases')}",
              tuple(row.get("phases") or ()) == _PHASES)
    ctx.check(f"{row.get('keys')}: no stand-in git left {GONE_S:.0f} s after Halo had gone, got {row}",
              not row["standins_alive_after"])
    ctx.check(f"{row.get('keys')}: nothing started under the scratch home left, got {row['left']}", not row["left"])


class _Silent:
    """3.6.0.17 Z2: a listener of this test's own on a loopback port that accepts and never answers -- a network read
    that hangs (a dead port is not enough: it refuses at once). `conns` are the connections it holds; close() ends
    them all (a test's `finally`)."""

    def __init__(self) -> None:
        import socket
        import threading
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.conns: list = []
        self.first: "float | None" = None
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._accept, name="z2-silent", daemon=True)
        self._th.start()

    def _accept(self) -> None:
        import socket
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.first = self.first or time.monotonic()
            self.conns.append(conn)

    def close(self) -> None:
        self._stop.set()
        self._th.join(2)
        for s in self.conns + [self.sock]:
            try:
                s.close()
            except OSError:
                pass


_LAST_LINES = 6


def _last_lines(text: str) -> list:
    """The last non-empty lines a terminal shows (what a person reads once the session is gone)."""
    return [ln.rstrip() for ln in text.splitlines() if ln.strip()][-_LAST_LINES:]


def _z2_env(c: "core.Ctx", h, folder: Path, listener: "_Silent", trace: Path, stuck: bool = True) -> dict:
    """A scratch home's session whose OpenRouter catalog and balance refreshes at launch read from `listener` (they
    hang; with `stuck` false they go to the dead port and fail at once, the same rig with nothing stuck), whose git
    answers at once (tests/helpers/hanging_git.py, hang=False) and whose every other HTTP(S) request goes to a proxy
    on a dead loopback port and fails at once: never the real network."""
    import os
    dead = "http://127.0.0.1:9"
    proxies = {k: dead for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")}
    base = f"http://127.0.0.1:{listener.port}/api/v1" if stuck else f"{dead}/api/v1"
    return c.env(h, PATH=f"{folder}{os.pathsep}{os.environ.get('PATH', '')}", HALO_NO_UPDATER="1",
                 BRIDGE_TEST_NO_BACKGROUND_NET=None, HALO_OFFLINE=None, HALO_CLOSE_TRACE=str(trace),
                 NO_PROXY=None, no_proxy=None, OPENROUTER_BASE_URL=base, BRIDGE_OPENROUTER_BASE_URL=base, **proxies)


def _quit_while_a_read_hangs(c: "core.Ctx", how: str, stuck: bool = True, claude: bool = False) -> dict:
    """A real terminal session (bare `halo`) in a scratch home, ONE of its launch workers (the OpenRouter catalog
    refresh: a 30 s read) stuck on `_Silent` (`stuck` false: the same rig, nothing stuck); the session is quit the
    way a person does (`how`: Ctrl+C then Enter on "Quit Halo?", or /quit). The Halo process must be gone before
    half the hold (3.6.0.18 L: the stuck read's own timeout, or the stand-in claude's), with the normal quit's code. `claude` (3.6.0.17 Z4-1): a stand-in `claude` (_CLAUDE) answers the launch's
    `claude auth status` only once the way out has begun, so its child is in flight at the quit, every time."""
    from realcheck import screen
    from realcheck.steps_close import _noter
    from tests.helpers import hanging_git
    h = c.home("z2" if stuck else "z2-free")
    folder = hanging_git.make(h.dir / "git-standin", hang=False)
    trace = h.dir / "close-trace.txt"
    listener = _Silent()
    row: dict = {"how": how, "stuck": stuck}
    t = None
    try:
        env = _z2_env(c, h, folder, listener, trace, stuck)
        if claude:
            env["HALO_CLAUDE_EXE"] = _claude_standin(h.dir / "claude-standin", trace)
            row["claude_dir"] = h.dir / "claude-standin"
        t = c.terminal(h, env=env)
        end = time.monotonic() + 90
        while time.monotonic() < end and t.poll() is None:
            if (listener.conns or not stuck) and screen.READY.search(t.plain()):
                break
            time.sleep(0.2)
        row["held"] = len(listener.conns)
        if not ((listener.conns or not stuck) and screen.READY.search(t.plain())):
            row["not_up"] = core.excerpt(t.plain(), 300) or f"exit {t.poll()}"
            return row
        time.sleep(1.0)  # keys typed the moment the status line shows may not be taken
        row["held_s_at_quit"] = round(time.monotonic() - (listener.first or time.monotonic()), 1)
        if how == "/quit":
            t.type("/quit")
            time.sleep(0.3)
            t.write(b"\r")
            row["keys"] = "/quit Enter"
        else:
            row["keys"] = screen.quit_with_ctrl_c(t, wait=0.5, note=_noter(trace))
        # the hold: the stuck read's own timeout (the listener never answers), or the stand-in claude's
        from halo_harness.providers import databricks
        row["hold_s"] = _CLAUDE_HOLD_S if claude else float(databricks._CATALOG_READ_TIMEOUT_S)
        asked = time.monotonic()
        row["halo_alive_after"] = not _gone_by(t, row["hold_s"] / 2)
        row["gone_s"] = round(time.monotonic() - asked, 1)  # from the quit's last key to the process gone
        row["phases"] = _phases(trace)
        row["code"] = t.poll()
        text = _settled(t)
        row["last_lines"] = _last_lines(text)
        row["way_out"] = _way_out(_after_the_app(t))
        row["left"] = [f"{p.short(110)} [{p.why}]" for p in c.left_after(h, 0.5)]
        if claude:
            row["claude"] = sorted(f.name.split("-")[0] for f in row["claude_dir"].iterdir() if "-" in f.name)
        return row
    finally:
        if t is not None:
            t.cleanup()
        listener.close()
        c.end_leftovers(h)


# 3.6.0.17 Z4-1: a stand-in `claude` (never the real one): `auth status` writes started-<pid>, waits until the halo's
# close trace says its app has returned (the quit is under way: the child is in flight then on every machine, however
# slow), then 0.5 s more, and answers "signed out" (mcp/claude_auth.py: loggedIn false), writing ended-<pid>. A SIGTERM
# (the closing procedure's marker scan on POSIX) writes term-<pid> instead. It gives up after _CLAUDE_HOLD_S on its own.
_CLAUDE_HOLD_S = 60.0
_CLAUDE = r'''
import os, signal, sys, time
folder, trace = sys.argv[1], sys.argv[2]
mark = lambda what: open(os.path.join(folder, "%s-%d" % (what, os.getpid())), "w").close()
mark("started")


def term(*_a):
    mark("term")
    os._exit(143)


if hasattr(signal, "SIGTERM"):
    signal.signal(signal.SIGTERM, term)


def returned():
    try:
        with open(trace, encoding="utf-8", errors="replace") as f:
            return "app.run returned" in f.read()
    except OSError:
        return False


end = time.monotonic() + float(sys.argv[3])
while time.monotonic() < end and not returned():
    time.sleep(0.05)
time.sleep(0.5)
print('{"loggedIn": false}', flush=True)
mark("ended")
'''


def _claude_standin(folder: Path, trace: Path) -> str:
    """HALO_CLAUDE_EXE for _CLAUDE (mcp/claude_process.py: shlex-split, every path double-quoted)."""
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "claude_standin.py"
    script.write_text(_CLAUDE, encoding="utf-8")
    return " ".join(f'"{x}"' for x in (sys.executable, script, folder, trace, _CLAUDE_HOLD_S))


_WAY_OUT = ("halo:", "stopped:", "stand-in:")
_ALT_OFF = "[?1049l"  # the terminal leaves the app's own screen


def _after_the_app(t) -> str:
    """What the process wrote once it had left the app's own screen for the last time, as plain text: the terminal's
    text from its last "alternate screen off" on (the whole text where a terminal reports no such switch). Read as
    one flat text, the screen's last row and the first line after it are ONE line, and a way-out line that follows a
    row ending in a letter ("...-0/proj" + "halo: left running on purpose: ...") was not found: CI's Linux runner,
    2026-11-24, and the Linux VM with a longer folder name. The line was printed; only this reading lost it."""
    from realcheck.term import strip_ansi
    raw = t.text()
    cut = raw.rfind(_ALT_OFF)
    return strip_ansi(raw[cut:] if cut >= 0 else raw)


def _settled(t) -> str:
    """The terminal's text once its reader has drained what the process wrote just before it left: unchanged for
    0.5 s, at most 5 s after the process is gone (a line printed right before the exit is otherwise read too soon)."""
    end = time.monotonic() + 5
    seen, still = len(t.raw()), time.monotonic()
    while time.monotonic() < end and time.monotonic() - still < 0.5:
        time.sleep(0.1)
        if len(t.raw()) != seen:
            seen, still = len(t.raw()), time.monotonic()
    return t.plain()


def _way_out(text: str) -> list:
    """The lines a way out prints once the app's own screen is gone (the closing procedure's `halo: ...`, the quit's
    `stopped: ...`, the rig's stand-in updater), never the app's screen or its replay (a terminal may keep or repaint
    them, with a tip picked at random), with what differs between two runs by nature (a pid) read the same."""
    import re
    found = (re.search(r"(?<![\w-])(?:%s).*" % "|".join(map(re.escape, _WAY_OUT)), ln) for ln in text.splitlines())
    return [re.sub(r"\bpid \d+", "pid N", m.group(0).strip()) for m in found if m]  # a row may hold screen remnants first


def _check_z2(ctx: Ctx, how: str) -> None:
    c = core.Ctx(REPO, Path(tempfile.mkdtemp(prefix="rc-close-z2-")))
    try:
        free = _quit_while_a_read_hangs(c, how, stuck=False)
        row = _quit_while_a_read_hangs(c, how)
    finally:
        c.close()
    ctx.check(f"the session came up and a launch worker's read hung on the test's listener (not a vacuous check), "
              f"got {row}", "not_up" not in row and row["held"] >= 1)
    ctx.check(f"the same session with nothing stuck came up and quit, got {free}",
              "not_up" not in free and not free["halo_alive_after"] and free.get("code") == 0)
    ctx.check(f"{row.get('keys')}: the Halo process gone before half the stuck read's {row.get('hold_s')} s, got {row}",
              not row["halo_alive_after"])
    # 3.6.0.19: the product's own bound, held against a healthy quit on THIS machine (half a stand-in's hold let a
    # quit that regressed to 10 s pass): a stuck quit may take the healthy quit's time, once more for a slow
    # machine, the whole way out's budget and the exit's grace, and three seconds for a slow runner's own jitter.
    from halo_harness import closing
    bound = closing.QUIT_BUDGET_S + closing.EXIT_GRACE_S
    allowed = 2 * float(free.get("gone_s") or 0.0) + bound + 3.0
    ctx.check(f"{row.get('keys')}: the stuck quit is gone within the product's bound of a healthy quit here: healthy "
              f"{free.get('gone_s')} s, stuck {row.get('gone_s')} s, allowed {allowed:.1f} s (twice the healthy quit + "
              f"{bound:.0f} s + 3 s)", "gone_s" in free and "gone_s" in row and row["gone_s"] <= allowed)
    for name, r in (("nothing stuck", free), ("a read stuck", row)):
        ctx.check(f"{row.get('keys')}, {name}: its way out's phases in order, got {r.get('phases')}",
                  tuple(r.get("phases") or ()) == _PHASES)
    ctx.check(f"{row.get('keys')}: it left with the normal quit's code 0, got {row.get('code')}", row.get("code") == 0)
    ctx.check(f"{row.get('keys')}: the terminal shows no traceback on the way out, got {row.get('last_lines')}",
              not any("Traceback" in ln for ln in row.get("last_lines") or []))
    ctx.check(f"{row.get('keys')}: 3.6.0.17 Z3-1: the stuck quit's last lines are those of the quit with nothing "
              f"stuck, got {row.get('way_out')} vs {free.get('way_out')}", row.get("way_out") == free.get("way_out"))
    ctx.check(f"{row.get('keys')}: nothing started under the scratch home left, got {row['left']} / {free['left']}",
              not row["left"] and not free["left"])


@test
def test_z2_a_session_quit_with_ctrl_c_while_a_launch_read_hangs_is_gone_within_the_bound(ctx: Ctx):
    """3.6.0.17 Z2-1: the terminal app's normal quit has the bound the other ways out have (closing.hard_exit): a
    pool thread in a hanging network read no longer keeps the quit Halo alive."""
    _check_z2(ctx, "Ctrl+C")


@test
def test_z2_a_session_quit_with_slash_quit_while_a_launch_read_hangs_is_gone_within_the_bound(ctx: Ctx):
    _check_z2(ctx, "/quit")


@test
def test_z4_a_quit_with_nothing_stuck_ends_no_child_of_halos_own_checks(ctx: Ctx):
    """3.6.0.17 Z4-1: a healthy quit while a launch worker's short child is still in flight (the stand-in `claude`'s
    `auth status`, _CLAUDE): the pool the app had is joined first (within one bound), so that child ends by itself
    before the closing procedure looks: no "halo: ended" line, the child never signalled, the normal quit's code 0,
    the process gone before half the stand-in's hold (3.6.0.18 L). On Windows there is no marker scan: green there before and after."""
    c = core.Ctx(REPO, Path(tempfile.mkdtemp(prefix="rc-close-z4-")))
    try:
        row = _quit_while_a_read_hangs(c, "Ctrl+C", stuck=False, claude=True)
    finally:
        c.close()
    seen = row.get("claude") or []
    ctx.check(f"the session came up and its `claude auth status` stand-in ran (not a vacuous check), got {row}",
              "not_up" not in row and "started" in seen)
    ctx.check(f"{row.get('keys')}: the Halo process gone before half the stand-in's {row.get('hold_s')} s, with the "
              f"normal quit's code 0, got {row}", not row["halo_alive_after"] and row.get("code") == 0)
    ctx.check(f"{row.get('keys')}: its way out's phases in order, got {row.get('phases')}",
              tuple(row.get("phases") or ()) == _PHASES)
    ctx.check(f"{row.get('keys')}: no 'halo: ended' line on a healthy quit, got {row.get('way_out')}",
              not any(ln.startswith("halo: ended") for ln in row.get("way_out") or []))
    ctx.check(f"{row.get('keys')}: the stand-in was never signalled and ended by itself, got {seen}",
              "term" not in seen and "ended" in seen)
    ctx.check(f"{row.get('keys')}: nothing started under the scratch home left, got {row['left']}", not row["left"])


# The restart exit (/update's Enter) needs an update on offer and then hands over to the updater, so a real session
# cannot be driven to it here. This drives the same terminal app the way cli.main does (`cli._run_full_screen`: the
# app, then for the restart exit the hand-off), the demo controller, in a terminal of its own, with the real closing
# procedure installed as cli.main installs it. A thread worker of the app (`stuck`) holds a read on the test's
# listener; it then asks the way out: the very function /update's dialog calls with Enter
# (slash._on_update_dialog_result), or the quit /quit asks (`_begin_quit`). The updater's start is a stand-in that
# takes HAND_OFF_S (longer than any grace: a slow machine's hand-off) and prints one line: never a real updater.
# `kept`: the app first starts a thing a person asked to keep (closing.start_kept), whose line the way out prints.
_RIG = r'''
import json, os, socket, sys, time
from halo_harness import closing
closing.install()  # what cli.main does first in the real process
from halo_harness import cli, update_detached
from halo_harness.tui import app as A, slash
port, way, stuck, kept, out = int(sys.argv[1]), sys.argv[2], sys.argv[3] == "stuck", sys.argv[4] == "kept", sys.argv[5]
HAND_OFF_S, HOLD_S = float(sys.argv[6]), float(sys.argv[7])


def hand_off(**_kw):  # the updater's start, stood in
    time.sleep(HAND_OFF_S)
    print("stand-in: the updater is on its way", flush=True)
    return 0


update_detached.run_after_exit = hand_off
_mount = A.BridgeApp.on_mount


async def on_mount(self):
    await _mount(self)
    if kept:
        p = closing.start_kept([sys.executable, "-c", "import time; time.sleep(120)", out], what="host")
        with open(os.path.join(out, "kept.json"), "w", encoding="utf-8") as f:
            json.dump({"pid": p.pid}, f)

    def act():
        s = None
        if stuck:  # a launch worker in a network read that never answers
            s = socket.create_connection(("127.0.0.1", port), timeout=5)
            s.settimeout(HOLD_S)
        with open(os.path.join(out, "asked.json"), "w", encoding="utf-8") as f:
            json.dump({"at": time.time()}, f)
        if way == "restart":
            self.call_from_thread(slash._on_update_dialog_result, self, "update")
        else:
            self.call_from_thread(self._begin_quit)
        if s is not None:
            try:
                s.recv(1)
            except OSError:
                pass
    self.run_worker(act, thread=True, name="z3-act", group="z3-act")


A.BridgeApp.on_mount = on_mount
sys.exit(cli._run_full_screen(cli._build_parser().parse_intermixed_args(["--demo"]), ["--demo"]))
'''
HAND_OFF_S = 8.0  # longer than Z2's bound for the restart exit (EXIT_GRACE_S + QUIT_BUDGET_S): it was cut there
RIG_HOLD_S = 120.0  # 3.6.0.18 L: the stuck worker's read holds this long; the process must be gone before half of it


def _end_kept(pid, started) -> None:
    """End the rig's kept thing, by its pid and its start time (never another program that pid was given to)."""
    import os
    import signal
    if pid and _same(pid, started or 0):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        end = time.monotonic() + 5
        while _same(pid, started or 0) and time.monotonic() < end:
            time.sleep(0.1)


def _rig(c: "core.Ctx", way: str, stuck: bool, kept: bool) -> dict:
    """One run of _RIG in a scratch home: the process's code, how long after the way out was asked it was gone, its
    last lines, what of it was left (the kept thing apart), and the kept thing's pid; that one is ended here, by pid
    and start time."""
    import json
    from realcheck.term import Terminal
    listener = _Silent()
    row: dict = {"way": way, "stuck": stuck}
    t = None
    kept_pid = kept_start = None
    h = c.home(f"z3-{way}-{'stuck' if stuck else 'free'}")
    out = h.dir / "rig-out"
    out.mkdir(parents=True, exist_ok=True)
    try:
        script = h.dir / "z3_rig.py"
        script.write_text(_RIG, encoding="utf-8")
        env = c.env(h, HALO_NO_UPDATER="1", BRIDGE_TEST_NO_BACKGROUND_NET="1")
        argv = [sys.executable, str(script), str(listener.port), way, "stuck" if stuck else "free",
                "kept" if kept else "-", str(out), str(HAND_OFF_S), str(RIG_HOLD_S)]
        t = Terminal(argv, env=env, cwd=str(h.proj))
        c._mark(h, t.pid)
        c.terms.append(t)
        end = time.monotonic() + 90 + RIG_HOLD_S / 2
        gone_at = None
        while True:
            if kept and kept_pid is None and (out / "kept.json").exists():
                try:
                    kept_pid = json.loads((out / "kept.json").read_text(encoding="utf-8"))["pid"]
                    kept_start = procs.started_at(kept_pid)
                except (OSError, ValueError, KeyError):
                    pass
            if gone_at is not None or time.monotonic() >= end:
                break
            if t.poll() is not None:
                gone_at = time.time()  # one more turn reads the kept thing's pid when it was written last
                continue
            time.sleep(0.1)
        row["held"] = len(listener.conns)
        try:
            asked = json.loads((out / "asked.json").read_text(encoding="utf-8"))["at"]
        except (OSError, ValueError, KeyError):
            asked = None
        row["gone_s"] = round(gone_at - asked, 1) if gone_at and asked else None
        row["code"] = t.poll()
        text = _settled(t)
        row["last_lines"] = _last_lines(text)
        row["way_out"] = _way_out(_after_the_app(t))
        row["kept_pid"] = kept_pid
        _end_kept(kept_pid, kept_start)  # it holds the terminal (Windows: its conhost) while it runs
        row["left"] = [f"{p.short(110)} [{p.why}]" for p in c.left_after(h, 2.0) if p.pid != kept_pid]
    finally:
        _end_kept(kept_pid, kept_start)
        if t is not None:
            t.cleanup()
        listener.close()
        c.end_leftovers(h)
    return row


def _check_rig(ctx: Ctx, way: str, kept: bool, code: int, bound: float) -> dict:
    c = core.Ctx(REPO, Path(tempfile.mkdtemp(prefix=f"rc-close-z3{way[0]}-")))
    try:
        free = _rig(c, way, False, kept)
        row = _rig(c, way, True, kept)
    finally:
        c.close()
    for name, r in (("nothing stuck", free), ("a worker stuck", row)):
        ctx.check(f"{way}, {name}: gone within {bound:.0f} s of the way out, with code {code}, got {r}",
                  r["gone_s"] is not None and r["gone_s"] <= bound and r["code"] == code)
        ctx.check(f"{way}, {name}: nothing started under the scratch home left, got {r['left']}", not r["left"])
    ctx.check(f"{way}: the worker's read hung on the test's listener (not a vacuous check), got {row}", row["held"] >= 1)
    ctx.check(f"{way}: the stuck way out's last lines are those of the one with nothing stuck, got "
              f"{row['way_out']} vs {free['way_out']}", row["way_out"] == free["way_out"])
    return row


@test
def test_z3_the_restart_exits_hand_off_is_never_cut_and_leaves_with_its_code(ctx: Ctx):
    """3.6.0.17 Z3-1 (rewrites Z2's `test_z2_the_restart_exit_keeps_its_code_through_the_bound`): /update's restart exit
    runs controller.quit and then the hand-off to the updater (cli.py) to its end, also when it takes longer than any
    grace (a slow machine) and also when a thread worker is stuck; the process then leaves within the bound with the
    hand-off's code, and the lines are those of a restart with nothing stuck."""
    # 3.6.0.17 Z4-1: measured on the PC and the Linux VM: 8.3 s with nothing stuck, 10.6 to 10.7 s with a worker stuck
    # (the hand-off, the pool's join at its 2 s bound, the short grace). 3.6.0.18 L: read against the stuck read's hold
    # (gone before half of it), never a small constant a slow runner passes.
    row = _check_rig(ctx, "restart", False, 0, RIG_HOLD_S / 2)
    ctx.check(f"the hand-off ran to its end (its line shows), got {row['way_out']}",
              "stand-in: the updater is on its way" in row["way_out"])


@test
def test_z3_a_quit_while_a_worker_is_stuck_names_what_it_leaves_running(ctx: Ctx):
    """3.6.0.17 Z3-1 (c): the closing procedure runs on the main path before the bound, as a normal exit runs it, so a
    quit whose thread worker is stuck in a network read prints the same last lines as one with nothing stuck:
    "halo: left running on purpose: ..." for the thing a person asked to keep (the owner's rule: Halo names what it
    leaves running). Before, the interpreter's join of the stuck thread held the exit until the bound's silent
    close() ran and the line was lost."""
    # 3.6.0.17 Z4-1: measured on the PC and the Linux VM: 0.2 to 0.4 s with nothing stuck, 2.7 s with a worker stuck
    # (the pool's join at its 2 s bound, then the short grace). 3.6.0.18 L: gone before half the stuck read's hold.
    row = _check_rig(ctx, "quit", True, 0, RIG_HOLD_S / 2)
    ctx.check(f"the kept thing is named on the way out, got {row['last_lines']}",
              any("left running on purpose" in ln and f"pid {row['kept_pid']}" in ln for ln in row["last_lines"]))
    ctx.check(f"and only once, got {row['way_out']}", sum("left running on purpose" in ln for ln in row["way_out"]) == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
