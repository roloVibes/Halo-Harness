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
    ctx.check(f"Windows: its own console, detached from this halo, got {got} {popens}",
              got == 0 and popens and popens[0][1]["creationflags"] & 0x10 and popens[0][0][0] == "C:/py/python.exe")
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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
