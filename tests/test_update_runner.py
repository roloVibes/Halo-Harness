"""tests.test_update_runner -- Halo 3.6.0.0 R13: `halo update` can never leave a half install.

The owner's Windows `halo update`, run from a halo inside the tool environment it was replacing, died halfway and left
that environment without the package. Now the install runs in a standalone updater (halo_harness/update_runner.py)
that the running halo copies OUTSIDE the environment and starts with another Python (update_plan.py). These tests
run that very script, as a separate process, against a scratch "tool environment": a marker file that a fake `halo`
reads to answer `--version`, and fake installer commands that write it, break it halfway, or install the wrong
version. Nothing real is installed, no real `halo` runs, no real process is stopped.

1. A fake installer that fails halfway (it removes the package, then exits non-zero): the updater puts back what was
   there, the marker answers the OLD version again, and one line says what happened and how to try again.
2. An install that "succeeds" but answers the wrong version is a failure too: put back, said in one line.
3. The happy path: the new version answers; the result file says `updated`; the next `halo update` reports it once.
4. When putting back fails as well: one line naming the command to run by hand.
5. The updater waits for the old halo to be gone (a short-lived pid), and installs nothing when it does not go; on
   Windows a halo still holding the files (`--force`) stops the install before it starts.
6. The plan: Windows waits for this halo and its launcher and keeps its own window; POSIX hands over in the
   foreground (exec); the previous install's exact spec (the git commit) and a lock of this environment; a checkout
   is put back with `git reset --keep <commit>`; the expected version comes from the tag.
7. `launch` starts the copied runner with a Python that is not this environment's (exec on POSIX, its own console on
   Windows), and a test home never starts a real one.
Run: python -m tests.test_update_runner
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from halo_harness import update_plan as UP
from halo_harness import update_runner as R

test, TESTS = new_registry()
OLD = "halo 2.0.2 (aaaaaaa, master)"
NEW = "halo 2.0.3 (bbbbbbb, v2.0.3)"

FAKE_HALO = '''import sys
marker = sys.argv[1]
try:
    text = open(marker, encoding="utf-8").read().strip()
except OSError:
    print("ModuleNotFoundError: No module named 'halo_harness'", file=sys.stderr)
    sys.exit(1)
print("  _  _   _   _    ___")
print(text)
'''

FAKE_INSTALL = '''import os, sys
mode, marker = sys.argv[1], sys.argv[2]
if mode == "fail-halfway":
    os.remove(marker)
    print("Uninstalled 1 package: halo-harness")
    print("error: failed to remove file Scripts\\\\halo.exe: Access is denied. (os error 5)", file=sys.stderr)
    sys.exit(2)
if mode == "fail":
    sys.exit(3)
open(marker, "w", encoding="utf-8").write(sys.argv[3] + "\\n")
print("Installed 1 executable: halo")
'''


class _Env:
    """A scratch "tool environment" (a folder name with a space, as Windows homes often have) and its state dir."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix="r13 updater "))
        self.state = self.root / "state"
        self.tool = self.root / "tool env"
        self.tool.mkdir(parents=True)
        self.marker = self.tool / "installed.txt"
        self.marker.write_text(OLD + "\n", encoding="utf-8")
        (self.tool / "fake_halo.py").write_text(FAKE_HALO, encoding="utf-8")
        (self.tool / "fake_install.py").write_text(FAKE_INSTALL, encoding="utf-8")

    def cmd(self, mode: str, version: str = "") -> str:
        q = lambda s: f'"{s}"'  # noqa: E731 -- cmd.exe and sh both take a double-quoted path
        return " ".join([q(sys.executable), q(self.tool / "fake_install.py"), mode, q(self.marker)]
                        + ([q(version)] if version else []))

    def plan(self, install: str, *, restore: "str | None", expect: dict, **extra) -> dict:
        plan = UP.build_plan(cmd=install, cwd=str(self.tool), before={"version": "2.0.2", "commit": "aaaaaaa",
                                                                       "branch": "master"},
                             expect=expect, restore={"cmd": restore, "cwd": None} if restore else None,
                             state_dir=self.state, windows=False)
        plan["halo"] = [sys.executable, str(self.tool / "fake_halo.py"), str(self.marker)]
        plan.update(extra)
        return plan

    def run(self, plan: dict, timeout: float = 120) -> "tuple[int, str, dict]":
        """The updater as production starts it: the copied script, its own process, the plan file."""
        runner, path = UP.write_runner(self.state), UP.write_plan(plan, self.state)
        r = subprocess.run([sys.executable, "-I", str(runner), str(path)], capture_output=True, text=True,
                           timeout=timeout, cwd=str(self.root))
        result = json.loads(Path(plan["result"]).read_text(encoding="utf-8"))
        return r.returncode, r.stdout + r.stderr, result

    def answers(self) -> str:
        r = subprocess.run([sys.executable, str(self.tool / "fake_halo.py"), str(self.marker), "--version"],
                           capture_output=True, text=True, timeout=60)
        return R.last_line(r.stdout) if r.returncode == 0 else ""


@test
def test_an_installer_that_fails_halfway_leaves_the_old_halo_answering(ctx: Ctx):
    env = _Env()
    restore = env.cmd("install", OLD)
    code, out, result = env.run(env.plan(env.cmd("fail-halfway"), restore=restore,
                                         expect={"version": "2.0.3", "label": "2.0.3"}))
    ctx.check(f"the updater exits 1, got {code} {out[-600:]!r}", code == 1)
    ctx.check(f"the package really was gone halfway (the installer's own words), got {out[-600:]!r}",
              "Uninstalled 1 package" in out and "Access is denied" in out)
    ctx.check(f"the old version answers again, got {env.answers()!r}", env.answers() == OLD)
    ctx.check(f"the outcome is 'restored', got {result}", result.get("outcome") == "restored")
    line = result.get("line") or ""
    ctx.check(f"ONE line: what failed, that the old one is back, and the command to try by hand, got {line!r}",
              "\n" not in line and "the update to 2.0.3 failed (the installer exited with code 2)" in line
              and f"{OLD} was put back and answers again" in line and "fake_install.py\" fail-halfway" in line)
    log = (env.state / "update.log").read_text(encoding="utf-8")
    ctx.check("the log holds the same story, ending with the outcome",
              line in log and "putting back" in log and log.rstrip().endswith("=== restored"))


@test
def test_an_install_that_answers_the_wrong_version_is_put_back(ctx: Ctx):
    env = _Env()
    code, _out, result = env.run(env.plan(env.cmd("install", "halo 1.9.0 (0000000, v1.9.0)"),
                                          restore=env.cmd("install", OLD), expect={"version": "2.0.3", "label": "2.0.3"}))
    ctx.check(f"exit 1 and restored, got {code} {result}", code == 1 and result.get("outcome") == "restored")
    ctx.check(f"the line names what answered instead, got {result.get('line')!r}",
              "answered 'halo 1.9.0 (0000000, v1.9.0)', not 2.0.3" in (result.get("line") or ""))
    ctx.check("the old version answers", env.answers() == OLD)


@test
def test_the_new_version_answering_is_an_update_and_said_once_after(ctx: Ctx):
    env = _Env()
    code, out, result = env.run(env.plan(env.cmd("install", NEW), restore=env.cmd("install", OLD),
                                         expect={"version": "2.0.3", "label": "2.0.3"}))
    ctx.check(f"exit 0, updated, got {code} {result} {out[-400:]!r}", code == 0 and result.get("outcome") == "updated")
    ctx.check(f"before and after are printed, got {out!r}", f"before {OLD}" in out and f"after  {NEW}" in out)
    ctx.check("the new version answers", env.answers() == NEW)
    first = UP.take_unseen_line(env.state)
    ctx.check(f"the next `halo update` reads the outcome once, got {first!r}",
              first and "done" in first and UP.take_unseen_line(env.state) is None)


@test
def test_when_putting_back_fails_too_the_line_names_the_command(ctx: Ctx):
    env = _Env()
    restore = env.cmd("fail")
    code, _out, result = env.run(env.plan(env.cmd("fail-halfway"), restore=restore,
                                          expect={"version": "2.0.3", "label": "2.0.3"}))
    line = result.get("line") or ""
    ctx.check(f"exit 1, broken, one line with the command to run by hand, got {code} {line!r}",
              code == 1 and result.get("outcome") == "broken" and "\n" not in line
              and "halo does not answer now (putting it back failed too)" in line and line.endswith(restore))


@test
def test_the_updater_waits_for_the_old_halo_and_installs_nothing_while_it_stays(ctx: Ctx):
    env = _Env()
    short = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.5)"])
    stays = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    import threading  # reaped as it ends: the old halo is never the updater's child, so never a zombie to it
    threading.Thread(target=short.wait, daemon=True).start()
    try:
        t0 = time.monotonic()
        code, out, result = env.run(env.plan(env.cmd("install", NEW), restore=None, expect={"version": "2.0.3"},
                                             wait_pids=[short.pid]))
        ctx.check(f"it waited for the short-lived pid, then installed, got {code} {result}",
                  code == 0 and result.get("outcome") == "updated" and time.monotonic() - t0 >= 1.0)
        env2 = _Env()
        code, out, result = env2.run(env2.plan(env2.cmd("install", NEW), restore=None, expect={"version": "2.0.3"},
                                               wait_pids=[stays.pid], wait_s=1.5))
        ctx.check(f"a halo that does not go: nothing installed, the old one answers, got {code} {result}",
                  code == 1 and result.get("outcome") == "not_started" and env2.answers() == OLD
                  and "running:" not in out and str(stays.pid) in (result.get("line") or ""))
        env3 = _Env()
        code, out, result = env3.run(env3.plan(env3.cmd("install", NEW), restore=None, expect={"version": "2.0.3"},
                                               held=[{"pid": stays.pid, "what": "Studio"}], held_wait_s=1.5))
        ctx.check(f"Windows' held files: a halo that still runs is named and nothing installs, got {result}",
                  result.get("outcome") == "not_started" and f"Studio (pid {stays.pid})" in (result.get("line") or "")
                  and "without --force" in (result.get("line") or "") and env3.answers() == OLD)
    finally:
        for p in (short, stays):
            if p.poll() is None:
                p.kill()
            p.wait(timeout=10)


@test
def test_the_plan_differs_per_platform_and_keeps_the_previous_install(ctx: Ctx):
    before = {"version": "3.5.0.1", "commit": "abc1234", "branch": None, "requested_revision": "v3.5.0.1"}
    win = UP.build_plan(cmd="uv tool install --reinstall git+https://x/y@v3.6.0.0", cwd=None, before=before,
                        expect=UP.expectation("v3.6.0.0", "stable", {}, before), restore=None,
                        wait_pids=[11, 12], windows=True)
    nix = UP.build_plan(cmd="uv tool install --reinstall git+https://x/y@v3.6.0.0", cwd=None, before=before,
                        expect={}, restore=None, windows=False)
    ctx.check(f"Windows: waits for this halo and its launcher, keeps its window a moment, got {win}",
              win["wait_pids"] == [11, 12] and win["pause_s"] > 0 and nix["pause_s"] == 0)
    ctx.check(f"the tag's version is what must answer, got {win['expect']}", win["expect"]["version"] == "3.6.0.0")
    ctx.check("the certificate retry rides along for uv", win["cert_env"].get("UV_SYSTEM_CERTS") == "1"
              and "UV_SYSTEM_CERTS" in (win["cert_by_hand"] or ""))
    lock = str(Path(tempfile.mkdtemp()) / "prev.lock")
    kind = {"kind": "uv_tool", "spec": "git+https://github.com/o/r@master"}
    cur = ("uv tool install --reinstall --constraints https://raw.githubusercontent.com/o/r/master/requirements.lock "
           "git+https://github.com/o/r@master")
    got = UP.previous_install(kind, before, cur, lock, direct_url={"vcs_info": {"vcs": "git", "commit_id": "f" * 40}})
    ctx.check(f"a git install is put back at its exact commit with the lock of this environment, got {got}",
              got and got["cmd"].endswith("git+https://github.com/o/r@" + "f" * 40)
              and f"--constraints {lock}" in got["cmd"] and "raw.githubusercontent" not in got["cmd"])
    ck = {"kind": "dir_checkout", "spec": "/src/halo"}
    got = UP.previous_install(ck, {"commit": "abc1234", "branch": "master"},
                              "git -C /src/halo pull --ff-only && uv tool install --reinstall --constraints "
                              "/src/halo/requirements.lock /src/halo", lock)
    ctx.check(f"a checkout goes back with reset --keep (local changes kept), then the installer, got {got}",
              got and got["cmd"].startswith("git -C /src/halo reset --keep abc1234 && uv tool install --reinstall")
              and f"--constraints {lock}" in got["cmd"] and got["cwd"] == "/src/halo")
    path = UP.freeze_lock(Path(tempfile.mkdtemp()) / "prev.lock")
    text = path.read_text(encoding="utf-8") if path else ""
    ctx.check("the lock pins this environment's packages, never halo-harness itself",
              "==" in text and "halo-harness==" not in text.lower())
    ctx.check("main: anything but the commit installed now must answer (the branch may move meanwhile)",
              UP.expectation(None, "main", {"commit": "def5678", "ref": "master"}, before)["not_commit"] == "abc1234")


@test
def test_launch_uses_an_outside_python_and_never_runs_in_a_test_home(ctx: Ctx):
    state = Path(tempfile.mkdtemp(prefix="r13-launch-"))
    plan = {"install": {"cmd": "echo x"}, "log": str(state / "update.log")}
    execs, popens = [], []
    got = UP.launch(plan, state_dir=state, windows=False, python=["/opt/py/bin/python3", "-I"],
                    execv=lambda exe, argv: execs.append(argv))
    ctx.check(f"POSIX: exec of the outside python on the copied runner and the plan, got {got} {execs}",
              got == 0 and execs and execs[0][:2] == ["/opt/py/bin/python3", "-I"]
              and execs[0][2] == str(state / "run" / "update_runner.py") and execs[0][3].endswith("update-plan.json"))
    ctx.check("the copied runner is the module's own text, outside any environment",
              (state / "run" / "update_runner.py").read_text(encoding="utf-8")
              == Path(R.__file__).read_text(encoding="utf-8"))

    class _P:
        pid = 4321
    got = UP.launch(plan, state_dir=state, windows=True, python=["C:/py/python.exe", "-I"],
                    popen=lambda argv, **kw: popens.append((argv, kw)) or _P())
    run_flags = popens[0][1]["creationflags"] if popens else 0
    ctx.check(f"Windows: the updater runs with NO console (a closed window or Ctrl+C never stops it), detached from "
              f"this halo, got {got} {popens}", got == 0 and len(popens) == 2 and run_flags & 0x08
              and not run_flags & 0x10 and popens[0][0][0] == "C:/py/python.exe" and "--watch" not in popens[0][0])
    ctx.check("its window is the viewer (`--watch` with the updater's pid), a console of its own",
              len(popens) == 2 and popens[1][0][-3:-1] == ["--watch", popens[0][0][-1]] and popens[1][0][-1] == "4321"
              and popens[1][1]["creationflags"] & 0x10)
    import contextlib
    import io
    err = io.StringIO()
    with contextlib.redirect_stderr(err):  # a python that does not exist: even a broken guard could start nothing
        got = UP.launch(plan, state_dir=state, python=[str(state / "no-such-python")])
    ctx.check(f"a test home never starts a real updater, got {got} {err.getvalue()!r}",
              got is None and "switched off here" in err.getvalue())
    py = UP.outside_python()
    in_venv = sys.prefix != sys.base_prefix
    ctx.check(f"the outside python is not under this environment, got {py}",
              py is None or not in_venv or not os.path.abspath(py[0]).lower().startswith(os.path.abspath(sys.prefix).lower() + os.sep))


@test
def test_the_runner_imports_nothing_from_halo(ctx: Ctx):
    import ast
    tree = ast.parse(Path(R.__file__).read_text(encoding="utf-8"))
    names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    ctx.check(f"standard library only (it runs outside halo's environment), got {names}",
              not any(n.startswith("halo_harness") for n in names))


# ---- the judge's pass (3.6.0.0 R13): its probes, as tests ----
class _P:
    def __init__(self, rc=0, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, ""


OLD_LINE = "halo 3.5.0.1 (aaaaaaa, v3.5.0.1)"


def _judge_plan(**extra) -> dict:
    p = {"before": {"line": OLD_LINE, "version": "3.5.0.1", "commit": "aaaaaaa"},
         "expect": {"version": "3.6.0.0", "label": "3.6.0.0"},
         "install": {"cmd": "INSTALL"}, "restore": {"cmd": "RESTORE"}, "halo": ["halo"]}
    p.update(extra)
    return p


def _go(run_fn, **kw):
    return R.run_plan(_judge_plan(**kw.pop("plan", {})), run_fn=run_fn, alive_fn=kw.pop("alive_fn", lambda p: False),
                      kill_fn=kw.pop("kill_fn", lambda p: None), sleep_fn=kw.pop("sleep_fn", lambda s: None),
                      out=lambda s: None, **kw)


@test
def test_a_ctrl_c_during_the_install_still_puts_the_old_one_back(ctx: Ctx):
    import signal
    calls, ignored = [], []

    def ctrl_c(cmd, **kw):
        calls.append(cmd)
        if cmd == "INSTALL":
            ignored.append(signal.getsignal(signal.SIGINT) is signal.SIG_IGN)
            raise KeyboardInterrupt
        return _P(0, OLD_LINE)
    code, res = _go(ctrl_c, protect=True)
    ctx.check(f"the putting back ran after the Ctrl+C, got {calls}", "RESTORE" in calls and code == 1)
    ctx.check(f"restored, saying it was interrupted, got {res}", res["outcome"] == "restored"
              and "interrupted (Ctrl+C)" in res["line"])
    ctx.check("while it installs, a Ctrl+C is ignored by the updater (protect=True)", ignored == [True])
    ctx.check("and the handler is back afterwards", signal.getsignal(signal.SIGINT) is not signal.SIG_IGN)
    kw = R._own_group_kw()
    ctx.check(f"the installer runs in its own process group / session, got {kw}",
              kw.get("start_new_session") is True if os.name != "nt" else bool(kw.get("creationflags", 0) & 0x200))


@test
def test_nothing_put_back_and_nothing_changed_is_said_as_such(ctx: Ctx):
    def net_down(cmd, **kw):
        return _P(1, "error: failed to fetch") if cmd in ("INSTALL", "RESTORE") else _P(0, OLD_LINE)
    code, res = _go(net_down)
    ctx.check(f"the restore failed and the old halo answers: 'nothing changed', not 'restored', got {res}",
              code == 1 and res["outcome"] == "unchanged" and "nothing changed" in res["line"])


@test
def test_main_always_writes_the_outcome_whatever_the_way_out(ctx: Ctx):
    d = Path(tempfile.mkdtemp(prefix="r13-main-"))
    plan = _judge_plan(result=str(d / "res.json"), log=str(d / "u.log"), run_id="abc")
    (d / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    saved = R.run_plan

    def boom(plan, **kw):
        raise KeyboardInterrupt
    R.run_plan = boom
    try:
        code = R.main([str(d / "plan.json")])
    except BaseException as e:  # noqa: BLE001
        code = f"escaped {type(e).__name__}"
    finally:
        R.run_plan = saved
    res = json.loads((d / "res.json").read_text(encoding="utf-8")) if (d / "res.json").exists() else {}
    log = (d / "u.log").read_text(encoding="utf-8") if (d / "u.log").exists() else ""
    ctx.check(f"a Ctrl+C that escapes the plan: exit 1, the result file and the log's last line, got {code} {res}",
              code == 1 and res.get("outcome") == "broken" and res.get("run_id") == "abc"
              and log.rstrip().endswith("=== broken"))


@test
def test_a_studio_that_opened_this_halo_is_stopped_not_waited_on(ctx: Ctx):
    from halo_harness import update as upd
    me = os.getpid()
    rows = [{"ProcessId": 300, "ParentProcessId": 1, "CommandLine": "C:\\Users\\u\\.local\\bin\\halo.exe studio"},
            {"ProcessId": 400, "ParentProcessId": 300,
             "CommandLine": "C:\\uv\\tools\\halo-harness\\Scripts\\python.exe C:\\Users\\u\\.local\\bin\\halo studio"},
            {"ProcessId": 500, "ParentProcessId": 400, "CommandLine": "C:\\Users\\u\\.local\\bin\\halo.exe"},
            {"ProcessId": me, "ParentProcessId": 500,
             "CommandLine": "C:\\uv\\tools\\halo-harness\\Scripts\\python.exe C:\\Users\\u\\.local\\bin\\halo"}]
    ps = (lambda cmd, **kw: _P(0, json.dumps(rows))) if os.name == "nt" else (
        lambda cmd, **kw: _P(0, "PID PPID ARGS\n" + "\n".join(f"{r['ProcessId']} {r['ParentProcessId']} "
                                                            f"{r['CommandLine']}" for r in rows)))
    chain, openers = upd.launch_lineage(run_fn=ps)
    ctx.check(f"the launcher chain stops at Studio, got {chain} {[o['pid'] for o in openers]}",
              chain == [500] and [o["pid"] for o in openers] == [400, 300] and openers[0]["what"] == "studio")
    clock, killed = [0.0], []
    code, res = _go(lambda c, **k: _P(0, "halo 3.6.0.0"), plan={"wait_pids": [me, *chain], "stop_pids": [400],
                                                                 "wait_s": 300},
                    alive_fn=lambda p: p in (300, 400) and p not in killed, kill_fn=killed.append,
                    sleep_fn=lambda s: clock.__setitem__(0, clock[0] + s), clock=lambda: clock[0])
    ctx.check(f"installed at once, Studio stopped, no 300 s wait, got {code} {res['outcome']} {clock} {killed}",
              code == 0 and res["outcome"] == "updated" and clock[0] < 10 and killed == [400])
    clock[0], killed[:] = 0.0, []
    code, res = _go(lambda c, **k: _P(0, "halo 3.6.0.0"), plan={"wait_pids": [400], "stop_pids": [400], "wait_s": 300},
                    alive_fn=lambda p: p == 400 and p not in killed, kill_fn=killed.append,
                    sleep_fn=lambda s: clock.__setitem__(0, clock[0] + s), clock=lambda: clock[0])
    ctx.check(f"a pid both to stop and to wait for is stopped first, got {code} {clock} {killed}",
              code == 0 and killed == [400] and clock[0] < 10)


@test
def test_a_reused_pid_is_neither_waited_on_nor_ended(ctx: Ctx):
    killed, clock, looks = [], [0.0], {}

    def start_later(pid):  # each pid's first look sees "t1"; every later look sees another program on that pid
        looks[pid] = looks.get(pid, 0) + 1
        return "t1" if looks[pid] == 1 else "t2"
    code, res = _go(lambda c, **k: _P(0, "halo 3.6.0.0"), plan={"wait_pids": [700], "stop_pids": [400]},
                    alive_fn=lambda p: p in (400, 700), kill_fn=killed.append, start_fn=start_later,
                    sleep_fn=lambda s: clock.__setitem__(0, clock[0] + s), clock=lambda: clock[0])
    ctx.check(f"pid 700 now runs another program: not waited on (no 300 s), got {clock}", clock[0] < 10)
    ctx.check(f"pid 400 now runs another program: not ended, got {killed} {res['outcome']}",
              killed == [] and res["outcome"] == "updated")
    ctx.check("the real start time of this very process is known and stable", R._start_time(os.getpid()) is not None
              and R._start_time(os.getpid()) == R._start_time(os.getpid()))

if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
