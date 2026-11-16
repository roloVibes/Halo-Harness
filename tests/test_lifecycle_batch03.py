"""tests.test_lifecycle_batch03 -- kept spawns without a window, nohup, `halo --tmux`'s environment, and what
subprocess_safe.run starts (Halo 3.6.0.0, fix package "lifecycle" batch 3).

1. Windows: a kept spawn (`halo --bg`, `halo host serve`, `halo supervise --daemon`, the home watch of a
   `halo local serve`, the updater) starts with CREATE_NO_WINDOW, never DETACHED_PROCESS: a venv's python.exe is a
   launcher, and the interpreter it starts from a console-less launcher got a new, visible terminal window.
2. POSIX: `nohup halo ...` keeps an ignored SIGHUP ignored (Halo installed its own handler over it and exited 129).
3. `halo --tmux` hands the new session this shell's environment (a running tmux server gave it its own old one).
4. POSIX: what subprocess_safe.run starts is inside the closing procedure: it ends when its starter gets SIGTERM or
   is killed hard; an `isolation: user` worker carries the owner variables through sudo.
Every process a test starts is its own and is ended by pid and start time; nothing is killed by name.
Run: python -m tests.test_lifecycle_batch03
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
WIN = os.name == "nt"
SCRUB = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "BRIDGE_", "HALO_", "ROLO_CLAUDE_", "TYPESAFE_", "OPENAI_",
         "GEMINI_", "GOOGLE_", "OLLAMA_")
DETACHED, NO_WINDOW, NEW_CONSOLE, GROUP = 0x00000008, 0x08000000, 0x00000010, 0x00000200


def _env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB)}
    env.update(BRIDGE_TEST_HOME=str(home), BRIDGE_STATE_DIR=str(home / ".halo"), PYTHONPATH=str(REPO),
               PYTHONIOENCODING="utf-8", HALO_NO_UPDATER="1", OLLAMA_HOST="http://127.0.0.1:9",
               BRIDGE_TEST_NO_BACKGROUND_NET="1")
    return env


class _Home:
    """A scratch state folder for this process (BRIDGE_TEST_HOME / BRIDGE_STATE_DIR) and back."""

    def __enter__(self):
        self._snap = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        self.root = Path(tempfile.mkdtemp(prefix="lc-b3-"))
        self.state = self.root / ".halo"
        self.state.mkdir(parents=True)
        os.environ["BRIDGE_TEST_HOME"] = str(self.root)
        os.environ["BRIDGE_STATE_DIR"] = str(self.state)
        return self

    def __exit__(self, *exc):
        for k, v in self._snap.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.root, ignore_errors=True)


# ---- 1. Windows: a kept spawn has no window ------------------------------------------------------------------------

@test
def test_windows_kept_kwargs_ask_for_no_window_never_a_detached_process(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows: creation flags")
    from halo_harness import closing
    for given in (0, GROUP, GROUP | DETACHED, GROUP | DETACHED | closing._BREAKAWAY):
        flags = closing.kept_kwargs({"creationflags": given})["creationflags"]
        ctx.check(f"from {given:#x}: CREATE_NO_WINDOW, got {flags:#x}", bool(flags & NO_WINDOW))
        ctx.check(f"from {given:#x}: no DETACHED_PROCESS (it cancels CREATE_NO_WINDOW), got {flags:#x}",
                  not flags & DETACHED)
        ctx.check(f"from {given:#x}: out of the Job and its own group, got {flags:#x}",
                  flags & closing._BREAKAWAY and flags & GROUP)
    flags = closing.kept_kwargs({"creationflags": NEW_CONSOLE})["creationflags"]
    ctx.check(f"a window asked for (CREATE_NEW_CONSOLE) keeps it and gets no CREATE_NO_WINDOW, got {flags:#x}",
              flags & NEW_CONSOLE and not flags & (NO_WINDOW | DETACHED))


class _Stop(Exception):
    pass


@test
def test_windows_a_bg_run_starts_with_no_window(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows: creation flags")
    from halo_harness.bg_run import start_background_run
    got: dict = {}

    def popen(argv, **kw):
        got.update(kw)
        raise _Stop()
    with _Home():
        try:
            start_background_run(["--version"], popen=popen)
        except _Stop:
            pass
    flags = int(got.get("creationflags") or 0)
    ctx.check(f"the bg run asks for CREATE_NO_WINDOW and no DETACHED_PROCESS, got {flags:#x}",
              flags & NO_WINDOW and not flags & DETACHED)
    ctx.check(f"the bg run leaves the Job, got {flags:#x}", bool(flags & 0x01000000))
    ctx.check("the bg run carries a kept marker", str((got.get("env") or {}).get("HALO_OWNER", "")).startswith("kept-"))


CONSOLE_PROBE = r'''
import ctypes, json, sys
k32, u32 = ctypes.windll.kernel32, ctypes.windll.user32
k32.GetConsoleWindow.restype = ctypes.c_void_p
hwnd = k32.GetConsoleWindow() or 0
visible = bool(hwnd) and bool(u32.IsWindowVisible(ctypes.c_void_p(hwnd)))
open(sys.argv[1], "w").write(json.dumps({"hwnd": hwnd, "visible": visible, "exe": sys.executable}))
'''


@test
def test_windows_a_kept_venv_python_opens_no_terminal_window(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows: only there is a venv's python.exe a launcher that starts the interpreter")
    from halo_harness import closing
    from halo_harness import subprocess_safe as sp
    tmp = Path(tempfile.mkdtemp(prefix="lc-b3-win-"))
    proc = None
    try:
        subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", "--without-pip", str(tmp / "venv")],
                       check=True, capture_output=True, timeout=180)
        py = tmp / "venv" / "Scripts" / "python.exe"
        (tmp / "probe.py").write_text(CONSOLE_PROBE, encoding="utf-8")
        out = tmp / "out.json"
        proc = sp.Popen([str(py), str(tmp / "probe.py"), str(out)],
                        **closing.kept_kwargs({"stdin": sp.DEVNULL, "stdout": sp.DEVNULL, "stderr": sp.DEVNULL}))
        deadline = time.time() + 60
        while time.time() < deadline and not (out.exists() and out.stat().st_size):
            time.sleep(0.2)
        got = json.loads(out.read_text()) if out.exists() and out.stat().st_size else {}
        ctx.check(f"the probe ran, got {got}", "visible" in got)
        ctx.check(f"the interpreter a kept venv launcher starts has no visible console window, got {got}",
                  got.get("visible") is False)
    finally:
        if proc is not None:
            try:
                proc.wait(timeout=30)
            except Exception:
                pass
        shutil.rmtree(tmp, ignore_errors=True)


# ---- 2. POSIX: nohup ---------------------------------------------------------------------------------------------

HUP_PROBE = r'''
import contextlib, io, signal, sys
if sys.argv[1] == "ignored":
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
from halo_harness import cli
with contextlib.redirect_stdout(io.StringIO()):
    try:
        cli._main(["--version"])
    except SystemExit:
        pass
h = signal.getsignal(signal.SIGHUP)
print("IGNORED" if h is signal.SIG_IGN else "HANDLED" if callable(h) else "DEFAULT")
'''


@test
def test_posix_an_ignored_sighup_stays_ignored(ctx: Ctx):
    if WIN:
        raise SkipTest("POSIX: Windows has no SIGHUP")
    tmp = Path(tempfile.mkdtemp(prefix="lc-b3-hup-"))
    try:
        (tmp / "probe.py").write_text(HUP_PROBE, encoding="utf-8")
        env = _env(tmp / "home")
        for given, want in (("ignored", "IGNORED"), ("default", "HANDLED")):
            r = subprocess.run([sys.executable, str(tmp / "probe.py"), given], capture_output=True, text=True,
                               env=env, cwd=str(tmp), timeout=120)
            last = (r.stdout.strip().splitlines() or [""])[-1]
            ctx.check(f"SIGHUP {given} at start -> {want}, got {last!r} ({r.stderr[-300:]})", last == want)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---- 3. halo --tmux: this shell's environment ----------------------------------------------------------------------

@test
def test_tmux_session_is_handed_this_shells_environment(ctx: Ctx):
    from halo_harness import bg_run
    seen: dict = {}

    def call(command, env=None):
        seen["command"] = list(command)
        arg = next((a for a in command if str(a).startswith("HALO_TMUX_ENV=")), None)
        seen["path"] = arg.split("=", 1)[1] if arg else None
        if seen["path"] and os.path.exists(seen["path"]):
            seen["data"] = json.loads(Path(seen["path"]).read_text(encoding="utf-8"))
            seen["mode"] = os.stat(seen["path"]).st_mode & 0o777
        return 0
    snap = {k: os.environ.get(k) for k in ("LC_B3_EXPORTED", "HALO_OWNER", "TERM")}
    os.environ.update(LC_B3_EXPORTED="from-this-shell", HALO_OWNER="some-owner", TERM="xterm-256color")
    try:
        code = bg_run.run_in_tmux(["-c"], which=lambda name: "/usr/bin/tmux", call=call)
    finally:
        for k, v in snap.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    ctx.check(f"returns the session's code, got {code}", code == 0)
    ctx.check(f"the session command names an environment file, got {seen.get('command')}", bool(seen.get("path")))
    data = seen.get("data") or {}
    ctx.check("the file holds this shell's exported variable", data.get("LC_B3_EXPORTED") == "from-this-shell")
    ctx.check("the file holds no owner variable", "HALO_OWNER" not in data)
    ctx.check("the file leaves the pane's own TERM to tmux", "TERM" not in data)
    if not WIN:
        ctx.check(f"the file is private (0600), got {oct(seen.get('mode') or 0)}", seen.get("mode") == 0o600)
    ctx.check("the file is gone once the session returned", not (seen.get("path") and os.path.exists(seen["path"])))


@test
def test_a_tmux_session_takes_the_environment_file(ctx: Ctx):
    from halo_harness import bg_run
    snap = dict(os.environ)
    fd, path = tempfile.mkstemp(prefix="halo-tmux-env-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"LC_B3_KEY": "the-shells", "PATH": os.environ.get("PATH", "")}, fh)
    try:
        os.environ.update(TMUX="/tmp/tmux-1/default,1,0", TMUX_PANE="%1", TERM="tmux-256color",
                          LC_B3_KEY="the-servers-old-one", LC_B3_SERVER_ONLY="1", HALO_TMUX_ENV=path)
        took = bg_run.take_tmux_env()
        got = dict(os.environ)
    finally:
        os.environ.clear()
        os.environ.update(snap)
        if os.path.exists(path):
            os.unlink(path)
    ctx.check(f"it took the file, got {took}", took is True)
    ctx.check("this shell's value wins", got.get("LC_B3_KEY") == "the-shells")
    ctx.check("a variable only the tmux server had is gone", "LC_B3_SERVER_ONLY" not in got)
    ctx.check("the pane's own TMUX / TMUX_PANE / TERM stay",
              (got.get("TMUX"), got.get("TMUX_PANE"), got.get("TERM")) == ("/tmp/tmux-1/default,1,0", "%1",
                                                                           "tmux-256color"))
    ctx.check("the pointer itself is not handed on", "HALO_TMUX_ENV" not in got)
    ctx.check("the file was deleted as it was read", not os.path.exists(path))


TMUX_PROBE = r'''
import json, os, sys
from halo_harness import bg_run
getattr(bg_run, "take_tmux_env", lambda: None)()
open(sys.argv[1], "w").write(json.dumps(dict(os.environ)))
'''


@test
def test_posix_real_tmux_with_a_server_running_gets_this_shells_environment(ctx: Ctx):
    tmux = shutil.which("tmux")
    if WIN or not tmux:
        raise SkipTest("POSIX with tmux on PATH")
    from halo_harness import bg_run
    from halo_harness.selfexec import python_argv
    tmp = Path(tempfile.mkdtemp(prefix="lc-b3-tmux-"))
    (tmp / "probe.py").write_text(TMUX_PROBE, encoding="utf-8")
    out = tmp / "env.json"
    base = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB) and not k.startswith("TMUX")}
    base.update(TMUX_TMPDIR=str(tmp), PYTHONPATH=str(REPO), OPENROUTER_API_KEY="the-servers-old-one")
    sock = ["-L", "lcb3"]
    try:
        subprocess.run([tmux, *sock, "new-session", "-d", "-s", "first", "sleep", "60"], env=base, check=True,
                       capture_output=True, timeout=30)
        shell = dict(base, OPENROUTER_API_KEY="exported-in-this-shell", LC_B3_EXPORTED="1")
        seen: dict = {}

        def call(command, env=None):  # the real tmux, detached (no terminal here), on this test's own server
            n = len(python_argv())
            head = list(command[:-(n + 1)])
            real = [head[0], *sock, "new-session", "-d", *head[2:], sys.executable, str(tmp / "probe.py"), str(out)]
            seen["argv"] = real
            r = subprocess.run(real, env=env, capture_output=True, text=True, timeout=30)
            deadline = time.time() + 30
            while time.time() < deadline and not (out.exists() and out.stat().st_size):
                time.sleep(0.2)
            return r.returncode
        snap = dict(os.environ)
        os.environ.clear()
        os.environ.update(shell)
        try:
            bg_run.run_in_tmux(["-c"], call=call)
        finally:
            os.environ.clear()
            os.environ.update(snap)
        got = json.loads(out.read_text()) if out.exists() and out.stat().st_size else {}
        ctx.check(f"the session ran, argv {seen.get('argv')}", bool(got))
        ctx.check(f"the session sees the key exported in this shell (set: {'OPENROUTER_API_KEY' in got}, "
                  f"the exported value: {got.get('OPENROUTER_API_KEY') == 'exported-in-this-shell'})",
                  got.get("OPENROUTER_API_KEY") == "exported-in-this-shell")
        ctx.check("the session sees a variable exported only in this shell", got.get("LC_B3_EXPORTED") == "1")
        ctx.check("the session is inside tmux", bool(got.get("TMUX")))
    finally:
        subprocess.run([tmux, *sock, "kill-server"], env=base, capture_output=True, timeout=30)
        shutil.rmtree(tmp, ignore_errors=True)


# ---- 4. POSIX: what subprocess_safe.run starts ends with its starter -----------------------------------------------

RUN_STARTER = r'''
import os, signal, sys, threading, time
from halo_harness import closing, subprocess_safe
closing.install(sweep_at_start=False)
signal.signal(signal.SIGTERM, closing.signal_exit(143))
pidfile = sys.argv[1]
def go():
    try:
        subprocess_safe.run(["sh", "-c", "echo $$ > " + pidfile + "; exec sleep 671"], timeout=600)
    except Exception:
        pass
threading.Thread(target=go, daemon=True).start()
deadline = time.time() + 30
while time.time() < deadline and not (os.path.exists(pidfile) and open(pidfile).read().strip()):
    time.sleep(0.05)
time.sleep(1.0)
print("READY", flush=True)
time.sleep(600)
'''


@test
def test_posix_what_run_starts_ends_with_its_starter(ctx: Ctx):
    if WIN:
        raise SkipTest("POSIX: on Windows the Job object is the mechanism")
    from halo_harness.children import pid_running, start_time
    tmp = Path(tempfile.mkdtemp(prefix="lc-b3-run-"))
    try:
        (tmp / "starter.py").write_text(RUN_STARTER, encoding="utf-8")
        for sig, name in ((signal.SIGTERM, "SIGTERM"), (signal.SIGKILL, "SIGKILL")):
            pidfile = tmp / f"child-{name}.pid"
            env = _env(tmp / f"home-{name}")
            (tmp / f"home-{name}" / ".halo").mkdir(parents=True)
            starter = subprocess.Popen([sys.executable, str(tmp / "starter.py"), str(pidfile)], env=env,
                                       cwd=str(tmp), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            child, cstart = None, None
            try:
                line = starter.stdout.readline().strip()
                ctx.check(f"[{name}] the starter is up, got {line!r}", line == "READY")
                child = int(pidfile.read_text().strip())
                cstart = start_time(child)
                starter.send_signal(sig)
                starter.wait(timeout=20)
                deadline = time.time() + 6
                while time.time() < deadline and pid_running(child):
                    time.sleep(0.1)
                ctx.check(f"[{name}] 6 s after the starter got {name} its run() child (pid {child}) has ended",
                          not pid_running(child))
            finally:
                if starter.poll() is None:
                    starter.kill()
                    starter.wait(timeout=10)
                if child and cstart and pid_running(child) and start_time(child) == cstart:
                    os.kill(child, signal.SIGKILL)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---- 4b. Windows (3.6.0.1): what subprocess_safe.run starts is in the starter's Job ------------------------------------

WIN_RUN_STARTER = r'''
import os, sys, threading, time
from halo_harness import closing, subprocess_safe
closing.install(sweep_at_start=False)
pidfile = sys.argv[1]
code = "import os, time; open(%r, 'w').write(str(os.getpid())); time.sleep(60)" % pidfile
def go():
    try:
        subprocess_safe.run([sys.executable, "-c", code], capture_output=True, timeout=600)
    except Exception:
        pass
threading.Thread(target=go, daemon=True).start()
deadline = time.time() + 60
while time.time() < deadline and not (os.path.exists(pidfile) and open(pidfile).read().strip()):
    time.sleep(0.05)
print("READY", flush=True)
time.sleep(600)
'''


@test
def test_windows_a_run_child_ends_with_a_hard_killed_starter(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows: POSIX has the marker scan and the reaper (test above)")
    from halo_harness.children import pid_running, start_time
    tmp = Path(tempfile.mkdtemp(prefix="lc-b3-winrun-"))
    child, cstart = None, None
    try:
        (tmp / "starter.py").write_text(WIN_RUN_STARTER, encoding="utf-8")
        (tmp / "home" / ".halo").mkdir(parents=True)
        pidfile = tmp / "child.pid"
        starter = subprocess.Popen([sys.executable, str(tmp / "starter.py"), str(pidfile)], env=_env(tmp / "home"),
                                   cwd=str(tmp), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                   creationflags=0x00004000)  # BELOW_NORMAL_PRIORITY_CLASS
        try:
            line = starter.stdout.readline().strip()
            ctx.check(f"the starter is up, got {line!r}", line == "READY")
            child = int(pidfile.read_text().strip())
            cstart = start_time(child)
            starter.kill()  # TerminateProcess: no Python code of the starter runs
            starter.wait(timeout=20)
            deadline = time.time() + 30
            while time.time() < deadline and pid_running(child):
                time.sleep(0.1)
            ctx.check(f"the run() child (pid {child}) ended with its hard-killed starter", not pid_running(child))
        finally:
            if starter.poll() is None:
                starter.kill()
                starter.wait(timeout=10)
            if starter.stdout:
                starter.stdout.close()
    finally:
        if child and cstart and pid_running(child) and start_time(child) == cstart:
            os.kill(child, signal.SIGTERM)  # Windows: TerminateProcess of the one child this test made
        shutil.rmtree(tmp, ignore_errors=True)


@test
def test_windows_run_joins_the_job_like_popen_but_never_an_editor_or_a_kept_env(ctx: Ctx):
    if not WIN:
        raise SkipTest("Windows: the Job object")
    from halo_harness import closing, subprocess_safe
    calls: list = []
    saved = closing.adopt
    closing.adopt = lambda proc: calls.append(proc.pid) or True
    try:
        quick = [sys.executable, "-c", "pass"]
        subprocess_safe.run(quick, env=closing.scrubbed_env(), timeout=60)
        ctx.check(f"the person's editor (a scrubbed env) is never adopted, got {calls}", calls == [])
        kept = dict(os.environ, **{closing.MARKER: closing.KEPT_PREFIX + "1-x"})
        subprocess_safe.run(quick, env=kept, timeout=60)
        ctx.check(f"a kept env is never adopted, got {calls}", calls == [])
        proc = subprocess_safe.run(quick, env=dict(os.environ), capture_output=True, text=True, timeout=60)
        ctx.check(f"an ordinary run() child is adopted once, got {calls}", len(calls) == 1)
        ctx.check(f"and run() answers as before, got {proc!r}",
                  isinstance(proc, subprocess.CompletedProcess) and proc.returncode == 0 and proc.stdout == "")
        out = subprocess_safe.check_output([sys.executable, "-c", "print(41 + 1)"], text=True, timeout=60)
        ctx.check(f"check_output too, got {out!r} / {calls}", out.strip() == "42" and len(calls) == 2)
        code = subprocess_safe.call([sys.executable, "-c", "import sys; sys.exit(3)"], timeout=60)
        ctx.check(f"call answers the exit code, got {code}", code == 3 and len(calls) == 3)
        try:
            subprocess_safe.check_call([sys.executable, "-c", "import sys; sys.exit(4)"], timeout=60)
            ctx.check("check_call raises on a failure", False)
        except subprocess.CalledProcessError as exc:
            ctx.check(f"check_call raises on a failure, got {exc.returncode}", exc.returncode == 4)
        try:
            subprocess_safe.run([sys.executable, "-c", "import time; time.sleep(30)"], capture_output=True,
                                timeout=2)
            ctx.check("a timeout raises TimeoutExpired", False)
        except subprocess.TimeoutExpired:
            ctx.check("a timeout raises TimeoutExpired (the child is killed)", True)
        done = subprocess_safe.run([sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"],
                                   input="abc", capture_output=True, text=True, timeout=60)
        ctx.check(f"input reaches the child, got {done.stdout!r}", done.stdout.strip() == "ABC")
    finally:
        closing.adopt = saved


@test
def test_a_scoped_user_worker_carries_the_owner_variables(ctx: Ctx):
    from halo_harness import closing
    from halo_harness.isolation import scoped_user
    tmp = Path(tempfile.mkdtemp(prefix="lc-b3-su-"))
    snap = {k: os.environ.get(k) for k in (closing.MARKER, closing.WATCH)}
    os.environ.update({closing.MARKER: "lead-marker", closing.WATCH: "123:start"})
    try:
        for given in ({"PATH": "/usr/bin"}, {"PATH": "/usr/bin", closing.MARKER: "lead-marker",
                                              closing.WATCH: "123:start"}):
            argv, env = scoped_user.wrap(["python", "-m", "halo_harness", "-p", "x"], tmp, dict(given),
                                         {"user": "worker"}, run_dir=tmp, lane_n=1, which=lambda n: "/usr/bin/sudo",
                                         platform="linux", sharer=lambda paths, spec: None)
            keep = next((a for a in argv if a.startswith("--preserve-env=")), "").split("=", 1)[-1].split(",")
            ctx.check(f"sudo keeps {closing.MARKER} and {closing.WATCH} (env {sorted(given)}), got {keep}",
                      closing.MARKER in keep and closing.WATCH in keep)
            ctx.check(f"the worker's environment has them, got {sorted(env)}",
                      env.get(closing.MARKER) == "lead-marker" and env.get(closing.WATCH) == "123:start")
    finally:
        for k, v in snap.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
