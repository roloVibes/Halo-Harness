"""tests.test_lifecycle_batch04 -- Ctrl+Break and the terminal, `halo ps` and the sessions, the macOS `ps` reads,
and launchd's login folder (Halo 3.6.0.0, fix package "lifecycle" batch 4).

1. Windows: a Ctrl+Break in a full-screen session ends it with the terminal left as the session found it (the
   alternate screen, mouse reporting and bracketed paste switched off, the cursor shown, the input mode put back).
2. `halo ps` lists the sessions running on the home (it said "no process of Halo is running" while they ran); a
   session is never a `halo stop` target.
3. macOS (no /proc): one `ps` look answers for a pid for a moment (the watchers ran 5-8 `ps` a second), and the proof
   before a signal is always a fresh read.
4. macOS: a start time read under another time zone still names the same process (and a 3.5 record, written in the
   reader's own zone, still matches).
5. macOS: the launchd line of `halo host install` / `halo supervise --service` puts the plist where launchd loads it
   at every login.
Every process a test starts is its own and is ended by its own handle; nothing is killed by name.
Run: python -m tests.test_lifecycle_batch04
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
WIN = os.name == "nt"
RESETS = ("\x1b[?1049l", "\x1b[?1000l", "\x1b[?1003l", "\x1b[?2004l", "\x1b[?25h")


# -- 1. Ctrl+Break ----------------------------------------------------------------------------------------------------

class _K32:
    def __init__(self, mode: int):
        self.mode, self.handlers, self.set_calls = mode, [], []

    def GetStdHandle(self, which):
        return 7

    def GetConsoleMode(self, handle, ptr):
        ptr.contents.value = self.mode
        return 1

    def SetConsoleMode(self, handle, mode):
        self.set_calls.append(mode)
        self.mode = mode
        return 1

    def SetConsoleCtrlHandler(self, fn, add):
        (self.handlers.append if add else self.handlers.remove)(fn)
        return 1


class _Sig:
    SIGINT, SIG_IGN = 2, "ignore"

    def __init__(self):
        self.current = "original"

    def getsignal(self, sig):
        return self.current

    def signal(self, sig, handler):
        self.current = handler


@test
def test_ctrl_break_writes_the_terminal_back_and_still_ends_the_session(ctx: Ctx):
    from halo_harness.tui import console_mode
    k32, written = _K32(0x0001 | 0x0200), []
    try:
        guard = console_mode.install(kernel32=k32, platform="win32", signal_module=_Sig(), write=written.append)
    except TypeError as e:
        ctx.check(f"install takes the terminal's writer, got {e}", False)
        return
    handler = k32.handlers[0]
    k32.mode = 0x0200  # what the full-screen session left on the input handle
    ended = not handler(1)
    text = "".join(written)
    ctx.check("Ctrl+Break still ends the process (the handler leaves it to the default)", ended)
    ctx.check(f"the off-sequences are written first, got {text!r}", all(s in text for s in RESETS))
    ctx.check("the alternate screen is left last (the prompt comes back on the main screen)",
              text.endswith("\x1b[?1049l"))
    ctx.check(f"the saved input mode is put back, got {k32.set_calls}", k32.set_calls[-1:] == [0x0001 | 0x0200])
    ctx.check("Ctrl+C is still swallowed and writes nothing more", handler(0) and "".join(written) == text)
    guard.restore()


CHILD = r"""
import ctypes, os, sys, time
sys.path.insert(0, sys.argv[1])
from halo_harness.tui import console_mode
guard = console_mode.install()
os.write(1, b"ON\n")
ctypes.windll.kernel32.GenerateConsoleCtrlEvent(1, 0)
time.sleep(8)
os.write(1, b"STILL\n")
"""


@test
def test_windows_a_real_ctrl_break_leaves_the_terminal_reset(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows only")
    # A console of its own with no window: the Ctrl+Break reaches this child alone, never the console of the tests.
    proc = subprocess.Popen([sys.executable, "-I", "-c", CHILD, str(REPO)], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000)
    try:
        out, err = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(10)
    text = out.decode("ascii", "replace")
    ctx.check(f"the child ended on the break (0xC000013A), got {proc.returncode:#x} {err[-300:]!r}",
              proc.returncode == 0xC000013A and "STILL" not in text)
    ctx.check(f"the terminal was written back before it ended, got {text!r}", all(s in text for s in RESETS))


# -- 2. halo ps and the sessions --------------------------------------------------------------------------------------

@test
def test_halo_ps_lists_a_running_session_and_never_stops_it(ctx: Ctx):
    from halo_harness import ps_cli
    root = Path(tempfile.mkdtemp(prefix="lc-b4-"))
    state = root / ".halo"
    (state / "run").mkdir(parents=True)
    lsock = socket.socket()
    lsock.bind(("127.0.0.1", 0))
    lsock.listen(4)
    sess = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdin=subprocess.DEVNULL)
    snap = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    try:
        os.environ["BRIDGE_TEST_HOME"], os.environ["BRIDGE_STATE_DIR"] = str(root), str(state)
        row = {"session_id": "s-1", "cwd": str(root), "pid": sess.pid, "kind": "tui", "started": 1.0,
               "endpoint": f"tcp:127.0.0.1:{lsock.getsockname()[1]}", "token_env": None, "title": "", "mode": ""}
        (state / "run" / "sessions.json").write_text(json.dumps({"version": 1, "sessions": [row]}), encoding="utf-8")
        table = ps_cli.rows(state)
        got = [r for r in table if r["pid"] == sess.pid]
        ctx.check(f"the session is listed as kind session, got {table}", len(got) == 1 and got[0]["kind"] == "session")
        every, _u = ps_cli.pick(table, [], every=True)
        orphans, _u = ps_cli.pick(table, [], orphans=True)
        by_pid, unknown = ps_cli.pick(table, [str(sess.pid)])
        ctx.check("a session is never a stop target (--all, --orphans, its pid)",
                  sess.pid not in {r["pid"] for r in every + orphans + by_pid})
        sess.kill()
        sess.wait(10)
        ctx.check("a session that ended is not listed", all(r["pid"] != sess.pid for r in ps_cli.rows(state)))
    finally:
        for k, v in snap.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        if sess.poll() is None:
            sess.kill()
            sess.wait(10)
        lsock.close()
        shutil.rmtree(root, ignore_errors=True)


# -- 3 and 4. macOS ps reads --------------------------------------------------------------------------------------------

class _Clock:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def __getattr__(self, name):
        import time
        return getattr(time, name)


class _Ps:
    """A macOS `ps` for one live pid: its lstart in the zone the caller's environment names (none: the system's)."""
    ZONES = {"UTC0": "Sun Nov 15 10:00:00 2026", "UTC": "Sun Nov 15 10:00:00 2026",
             "JST-9": "Sun Nov 15 19:00:00 2026", "PST8PDT": "Sun Nov 15 02:00:00 2026"}

    def __init__(self, pid: int, system_zone: str = "JST-9"):
        self.pid, self.system_zone, self.runs = pid, system_zone, 0

    def __call__(self, argv, **kw):
        self.runs += 1
        env = kw.get("env") or os.environ
        when = self.ZONES[env.get("TZ") or self.system_zone]
        cols = [a for a in argv if a.endswith("=")]
        out = " ".join(("S" if c == "stat=" else when) for c in cols if c in ("stat=", "lstart="))
        ok = str(self.pid) in argv
        return subprocess.CompletedProcess(argv, 0 if ok else 1, (out + "\n") if ok else "", "")


def _mac(ps: _Ps, clock: _Clock):
    """bg_run on a system without /proc: liveness is kill(pid, 0) (here: it runs) and then `ps` for a zombie."""
    from halo_harness import bg_run
    return [mock.patch.object(bg_run.subprocess, "run", ps), mock.patch.object(bg_run, "time", clock),
            mock.patch.object(bg_run, "pid_alive", lambda pid: not bg_run._ps_zombie(pid)),
            mock.patch.object(bg_run, "process_start_time", bg_run._ps_process_start_time)]


class _Patched:
    def __init__(self, patches):
        self.patches = patches

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()


@test
def test_macos_a_watcher_runs_far_fewer_ps_and_a_signal_proof_reads_afresh(ctx: Ctx):
    from halo_harness import bg_run
    from halo_harness import children as C
    pid = 4242
    ps, clock = _Ps(pid), _Clock()
    getattr(bg_run, "_PS_SEEN", {}).clear()
    with _Patched(_mac(ps, clock)):
        rec = C.start_time(pid)
        ps.runs = 0
        for tick in range(1, 9):  # the owner watch: every 0.25 s a liveness look, every 8th a start-time check
            clock.t += 0.25
            C.pid_running(pid)
            if tick % 8 == 0:
                C.same_process(pid, rec)
        watch = ps.runs
        ps.runs = 0
        proof = C.provably_same(pid, rec)
        fresh = ps.runs
    ctx.check(f"the owner watch's 2 s run at most 3 `ps` (was 10), got {watch}", watch <= 3)
    ctx.check(f"the proof before a signal holds and reads `ps` afresh, got {proof} after {fresh}",
              proof and fresh >= 1)


@test
def test_macos_a_start_time_read_in_another_zone_names_the_same_process(ctx: Ctx):
    from halo_harness import bg_run
    from halo_harness import children as C
    from halo_harness.remote import proc_ident
    pid = 4343
    ps, clock = _Ps(pid, system_zone="JST-9"), _Clock()
    getattr(bg_run, "_PS_SEEN", {}).clear()
    with _Patched(_mac(ps, clock)):
        rec = C.start_time(pid)
        token = proc_ident._ps_token(pid)
        ps.system_zone = "PST8PDT"  # the laptop travelled (or this shell has TZ set)
        getattr(bg_run, "_PS_SEEN", {}).clear()
        clock.t += 10
        same, proven = C.same_process(pid, rec), C.provably_same(pid, rec)
        token2 = proc_ident._ps_token(pid)
        ps.system_zone = "JST-9"
        old = "ps:" + _Ps.ZONES["JST-9"]  # what a 3.5 Halo recorded: its own zone
        clock.t += 10
        legacy = C.provably_same(pid, old)
        other = C.provably_same(pid, "ps:Mon Nov  9 08:00:00 2026")
    ctx.check(f"the ledger's start time still matches in the other zone ({rec!r}): {same}, {proven}", same and proven)
    ctx.check(f"a supervisor pulse's token is the same in both zones: {token!r} {token2!r}", token == token2 and token)
    ctx.check("a 3.5 record in this zone's text still matches; another process's does not", legacy and not other)


@test
def test_posix_one_ps_look_reads_state_and_utc_start(ctx: Ctx):
    """A real `ps` (Linux procps and macOS): the one look gives the state and a start time that does not move with TZ."""
    if WIN or not shutil.which("ps"):
        raise SkipTest("POSIX with ps only")
    from halo_harness import bg_run
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], stdin=subprocess.DEVNULL)
    snap = os.environ.get("TZ")
    try:
        os.environ["TZ"] = "Asia/Tokyo"
        bg_run.ps_forget(child.pid)
        stat, a = bg_run._ps_look(child.pid)
        os.environ["TZ"] = "America/New_York"
        bg_run.ps_forget(child.pid)
        b = bg_run._ps_process_start_time(child.pid)
        local = bg_run._ps_process_start_time(child.pid, local=True)
        ctx.check(f"state and start from one look, got {stat!r} {a!r}", bool(stat) and bool(a))
        ctx.check(f"the start does not move with TZ: {a!r} / {b!r} (local {local!r})", b == f"ps:{a}" and local != b)
        if sys.platform == "darwin":
            from halo_harness import closing
            ctx.check("a 3.5 marker (its owner's start in its own zone) still reads as a living owner",
                      closing.marker_owner_alive(closing.ident(child.pid, local)) is True)
    finally:
        os.environ.pop("TZ", None) if snap is None else os.environ.__setitem__("TZ", snap)
        child.kill()
        child.wait(10)


# -- 5. launchd ---------------------------------------------------------------------------------------------------------

@test
def test_macos_the_launchd_line_puts_the_plist_where_login_loads_it(ctx: Ctx):
    from halo_harness import host_install, logon_units
    path = Path("/Users/someone/my halo/.halo/host/com.halo.host.plist")
    line = logon_units.enable_command("macos", path)
    agent = "~/Library/LaunchAgents/com.halo.host.plist"
    ctx.check(f"the plist is copied into ~/Library/LaunchAgents and bootstrapped from there, got {line!r}",
              f"cp '{path}' {agent}" in line and line.endswith(f"launchctl bootstrap gui/$(id -u) {agent}")
              and line.startswith("mkdir -p ~/Library/LaunchAgents && "))
    off = host_install.disable_command("macos", path)
    ctx.check(f"uninstall's line boots it out and removes the copy, got {off!r}",
              off.startswith("launchctl bootout gui/$(id -u)/com.halo.host") and off.endswith(f"rm -f {agent}"))
    out = Path(tempfile.mkdtemp(prefix="lc-b4-u-"))
    try:
        _p, sup = logon_units.write_unit("macos", ["halo", "supervise"], env={}, out_dir=out)
        ctx.check(f"the supervisor's line does the same, got {sup!r}",
                  sup.endswith("launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/dev.halo.supervise.plist"))
        lin = logon_units.enable_command("linux", Path("/home/someone/.halo/host/halo-host.service"))
        ctx.check(f"the systemd line is unchanged, got {lin!r}", lin.startswith("systemctl --user link "))
    finally:
        shutil.rmtree(out, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
