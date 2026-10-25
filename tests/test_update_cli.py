"""tests.test_update_cli -- Halo 2.0.2 round 6: `halo update` (cmd_update,
apply_update). Every piece of halo_harness.update that would shell out,
fetch, list processes, or exec is monkeypatched to a canned fake -- this
file never runs a real install, never lists real processes for a real
refusal, and never execs anything.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from halo_harness import update as upd
from halo_harness import update_cli
from halo_harness import update_stop

test, TESTS = new_registry()


class _Proc:
    def __init__(self, stdout: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def _patch_all(*, installed_commit="aaaaaaa", available_commit="bbbbbbb", other_pids=None,
                run_returncode=0, after_version="halo 2.0.3 (bbbbbbb, master)", ordering=None):
    """One shared fake rig for the whole report-building + apply chain --
    every test below tweaks just the bits it cares about via the kwargs.
    `ordering` (round C): `commit_is_ancestor`'s own three-way answer --
    None (the default, "no checkout to ask") keeps every existing test's
    "available" wording exactly as before this knob existed; a test that
    wants the new "differs from" wording passes `ordering=False`."""
    orig = {name: getattr(upd, name) for name in
            ("installed_build", "latest_available", "install_kind", "commits_between",
             "commit_is_ancestor", "other_halo_pids", "other_halo_processes", "run")}
    orig["update_stop._stop"] = update_stop._stop
    upd.installed_build = lambda **kw: {"version": "2.0.2", "commit": installed_commit,
                                         "requested_revision": None, "checkout": None,
                                         "branch": "master", "editable": False}
    upd.latest_available = lambda *a, **kw: {"channel": "main", "commit": available_commit,
                                              "ref": "master", "reason": None, "source": "cache"}
    upd.install_kind = lambda **kw: {"kind": "uv_tool", "spec": "git+https://github.com/roloVibes/Halo-Harness",
                                      "reinstall_cmd": "uv tool install --reinstall "
                                                        "git+https://github.com/roloVibes/Halo-Harness"}
    upd.commits_between = lambda *a, **kw: (["bbbbbbb fix: a thing"], 1)
    upd.commit_is_ancestor = lambda *a, **kw: ordering
    upd.other_halo_pids = lambda **kw: list(other_pids or [])
    # 3.2.2.0 R3: the scan's details and the stop itself are fakes too -- a
    # test never lists or ends a real process.
    upd.other_halo_processes = lambda **kw: [{"pid": p, "ppid": 1, "what": "halo", "cmd": "halo --continue"}
                                             for p in (other_pids or [])]
    stopped = orig.setdefault("stopped", [])
    update_stop._stop = lambda entry, **kw: stopped.append(entry) or {"what": entry["what"], "pid": entry["pid"],
                                                                      "ok": True, "cmd": []}

    def _fake_run(cmd, **kwargs):
        if isinstance(cmd, list) and cmd[:1] == ["halo"]:
            return _Proc(stdout=after_version + "\n")
        return _Proc(returncode=run_returncode)
    upd.run = _fake_run
    return orig


def _restore_all(orig: dict) -> None:
    update_stop._stop = orig.pop("update_stop._stop")
    orig.pop("stopped", None)
    for name, value in orig.items():
        setattr(upd, name, value)


def _capture(fn, *args) -> "tuple[int, str, str]":
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fn(*args)
    return code, out.getvalue(), err.getvalue()


@test
def test_cmd_update_check_exit_0_when_up_to_date(ctx: Ctx):
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="aaaaaaa")
    try:
        code, out, _err = _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"exit 0, got {code}", code == 0)
        ctx.check(f"reports installed and available, got {out!r}", "installed:" in out and "available" in out)
    finally:
        _restore_all(orig)


@test
def test_cmd_update_check_exit_10_when_update_available(ctx: Ctx):
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb")
    try:
        code, out, _err = _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"exit 10, got {code}", code == 10)
        ctx.check(f"lists the commit(s) between, got {out!r}", "bbbbbbb fix: a thing" in out)
        ctx.check(f"names the exact reinstall command, got {out!r}",
                  "uv tool install --reinstall git+https://github.com/roloVibes/Halo-Harness" in out)
        ctx.check(f"says 'available' (ordering unknown/no checkout keeps the old wording), got {out!r}",
                  "available (main): bbbbbbb" in out)
    finally:
        _restore_all(orig)


@test
def test_cmd_update_check_exit_1_when_unknown(ctx: Ctx):
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb")
    upd.latest_available = lambda *a, **kw: {"channel": "main", "commit": None, "ref": None,
                                              "reason": "network unavailable", "source": "disabled"}
    try:
        code, out, _err = _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"exit 1, got {code}", code == 1)
        ctx.check(f"names the reason, got {out!r}", "network unavailable" in out)
    finally:
        _restore_all(orig)


@test
def test_cmd_update_check_never_applies_anything(ctx: Ctx):
    """--check must never call the reinstall command (upd.run) at all --
    proven by a run_fn that explodes on anything but `halo --version`."""
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb")
    def boom(cmd, **kw):
        raise AssertionError(f"--check must never run anything, got {cmd!r}")
    upd.run = boom
    try:
        code, _out, _err = _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"still reports exit 10, got {code}", code == 10)
    finally:
        _restore_all(orig)


@test
def test_cmd_update_without_check_always_queries_live_not_just_with_refresh(ctx: Ctx):
    """Halo 2.0.2 round C: "an explicit --check or /update always
    queries ... with the cache only as the fallback" -- a bare `halo
    update` (no --check, no --refresh) must reach `latest_available`
    with `refresh=True` regardless; the old code only did that when
    `--refresh` was ALSO passed, so a within-TTL cache answer could sit
    stale under an explicit check."""
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="aaaaaaa")
    seen = {}
    real_latest_available = upd.latest_available

    def spy(*a, **kw):
        seen["refresh"] = kw.get("refresh")
        return real_latest_available(*a, **kw)
    upd.latest_available = spy
    try:
        _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"--check passes refresh=True, got {seen}", seen.get("refresh") is True)
        _capture(update_cli.cmd_update, [])
        ctx.check(f"a bare 'halo update' ALSO passes refresh=True (no --refresh given), got {seen}",
                  seen.get("refresh") is True)
    finally:
        _restore_all(orig)


@test
def test_cmd_update_reports_differs_from_when_a_checkout_confirms_not_an_ancestor(ctx: Ctx):
    """Halo 2.0.2 round C: "'differs from <channel>' when the ordering
    is unknown and git merge-base --is-ancestor when a checkout exists"
    -- a real local checkout that confirms the installed commit is NOT
    an ancestor of the available one (diverged, or pinned to a different
    ref) must say "differs from", never the "available" wording that
    implies a clean, ordinary upgrade path."""
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb", ordering=False)
    try:
        code, out, _err = _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"exit code is unchanged (still 10 -- commits differ either way), got {code}", code == 10)
        ctx.check(f"says 'differs from', not 'available', got {out!r}", "differs from (main): bbbbbbb" in out)
        ctx.check("the word 'available' never appears as the label itself",
                  "available (main):" not in out)
    finally:
        _restore_all(orig)


@test
def test_apply_update_source_dir_names_the_real_fix_instead_of_could_not_determine(ctx: Ctx):
    """Halo 2.0.2 round 6/C: a plain source directory (no .git, no dist
    metadata -- the tar copy the test suite itself runs from is the
    known real case) used to fall into the generic "could not determine
    how halo was installed -- nothing to run"; now says plainly that
    replacing the directory is the fix, naming its real path."""
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb")
    upd.install_kind = lambda **kw: {"kind": "source_dir", "spec": "/opt/halo-source-copy", "reinstall_cmd": None}
    try:
        code, _out, err = _capture(update_cli.apply_update)
        ctx.check(f"exit 1 (nothing to run), got {code}", code == 1)
        ctx.check(f"names the real path and 'replace the directory', got {err!r}",
                  "/opt/halo-source-copy" in err and "replace the directory" in err)
        ctx.check("never the old generic 'could not determine' wording", "could not determine" not in err)
    finally:
        _restore_all(orig)


@test
def test_apply_update_stops_another_halo_process_and_says_so(ctx: Ctx):
    """3.2.2.0 R3: the default stops what still runs (the scan's halo here,
    a fake stop) before the install, one line each."""
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb", other_pids=[4242])
    stopped = orig["stopped"]
    try:
        code, out, _err = _capture(update_cli.apply_update)
        ctx.check(f"installs, exit 0, got {code}", code == 0 and "uv tool install --reinstall" in out)
        ctx.check(f"pid 4242 went to the stop, got {stopped}", [e["pid"] for e in stopped] == [4242])
        ctx.check(f"and a line says so, got {out!r}", "halo update: stopped: halo (pid 4242)" in out)
    finally:
        _restore_all(orig)


@test
def test_apply_update_keep_running_refuses_and_names_each_process(ctx: Ctx):
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb", other_pids=[4242])
    stopped = orig["stopped"]
    try:
        code, out, err = _capture(lambda: update_cli.apply_update(keep_running=True))
        ctx.check(f"refuses, exit 1, got {code}", code == 1)
        ctx.check(f"names the pid, what it is and how to stop it, got {err!r}",
                  "halo (pid 4242): halo --continue" in err and "stop it with: /quit in that session" in err)
        ctx.check(f"stops nothing and installs nothing, got {stopped} {out!r}",
                  not stopped and "uv tool install" not in out)
    finally:
        _restore_all(orig)


@test
def test_apply_update_force_stops_nothing_and_installs(ctx: Ctx):
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb", other_pids=[4242])
    stopped = orig["stopped"]
    try:
        code, out, _err = _capture(lambda: update_cli.apply_update(force=True))
        ctx.check(f"--force proceeds anyway, got {code}", code == 0)
        ctx.check(f"runs the reinstall command live, got {out!r}",
                  "uv tool install --reinstall" in out)
        ctx.check(f"and stops nothing, got {stopped}", stopped == [] and "stopped:" not in out)
    finally:
        _restore_all(orig)


def _sleeping_child():
    import subprocess
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@test
def test_halo_update_stops_a_lingering_registered_process_for_real(ctx: Ctx):
    """A children.json entry (scoped home) pointing at a sleeping child of
    this test: the default `halo update` really ends it and says so; the
    scan stays a fake (it never lists this host's processes)."""
    from halo_harness import children
    from halo_harness import children_stop
    child = _sleeping_child()
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb", other_pids=[])
    update_stop._stop = children_stop.stop_entry  # the real stop, for this child only
    try:
        children.register(child.pid, "bg", [sys.executable, "-m", "halo_harness", "-p", "x"], bg_id="ab12cd34")
        code, out, _err = _capture(update_cli.apply_update)
        ctx.check(f"installs, exit 0, got {code}", code == 0)
        ctx.check(f"says what it stopped, got {out!r}", f"halo update: stopped: background run (pid {child.pid})" in out)
        try:
            child.wait(timeout=10)
        except Exception:
            pass
        ctx.check("the lingering process ended", child.poll() is not None)
        ctx.check("and left children.json", all(e["pid"] != child.pid for e in children.load()))
    finally:
        children.unregister(child.pid)
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)
        _restore_all(orig)


@test
def test_keep_running_names_the_registered_process_and_its_stop_command(ctx: Ctx):
    from halo_harness import children
    child = _sleeping_child()
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb", other_pids=[])
    try:
        children.register(child.pid, "bg", [sys.executable, "-m", "halo_harness", "-p", "x"], bg_id="ab12cd34")
        code, out, err = _capture(update_cli.cmd_update, ["--keep-running"])
        ctx.check(f"refuses, exit 1, got {code}", code == 1)
        ctx.check(f"names it and the command that stops it, got {err!r}",
                  f"background run (pid {child.pid})" in err and "stop it with: halo bg stop ab12cd34" in err)
        ctx.check("the process keeps running and nothing installs", child.poll() is None and "uv tool install" not in out)
    finally:
        children.unregister(child.pid)
        child.kill()
        child.wait(timeout=10)
        _restore_all(orig)


@test
def test_apply_update_runs_in_the_checkout_cwd_never_the_process_cwd(ctx: Ctx):
    """Finding 3 (critical): for an editable/bare/local-dir checkout kind,
    the reinstall command must run WITH `cwd` set to the real checkout --
    never in whatever directory `halo update`/`/update` happened to be
    invoked from (usually an unrelated project repo) -- and must leave
    THIS process's own cwd completely untouched either way."""
    checkout = Path(tempfile.mkdtemp(prefix="halo-update-checkout-"))
    other_project = Path(tempfile.mkdtemp(prefix="halo-update-unrelated-project-"))
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb")
    upd.install_kind = lambda **kw: {"kind": "editable_checkout", "spec": str(checkout),
                                      "reinstall_cmd": f"git -C {checkout} pull --ff-only && echo reinstalled"}
    seen_cwd = []

    def fake_run(cmd, **kwargs):
        if isinstance(cmd, list) and cmd[:1] == ["halo"]:
            return _Proc(stdout="halo 2.0.3 (bbbbbbb, master)\n")
        seen_cwd.append(kwargs.get("cwd"))
        return _Proc(returncode=0)
    upd.run = fake_run
    old_cwd = os.getcwd()
    os.chdir(str(other_project))
    try:
        code, _out, _err = _capture(update_cli.apply_update)
        ctx.check(f"exit 0, got {code}", code == 0)
        ctx.check(f"the reinstall ran with cwd == the checkout, got {seen_cwd}", seen_cwd == [str(checkout)])
        ctx.check(f"this PROCESS's own cwd is untouched, got {os.getcwd()!r}", os.getcwd() == str(other_project))
    finally:
        os.chdir(old_cwd)
        _restore_all(orig)


@test
def test_apply_update_reports_before_and_after_from_a_fresh_halo_dash_dash_version(ctx: Ctx):
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb",
                       after_version="halo 2.0.3 (bbbbbbb, master)")
    try:
        code, out, _err = _capture(update_cli.apply_update)
        ctx.check(f"exit 0, got {code}", code == 0)
        ctx.check(f"before line names the OLD commit, got {out!r}", "before halo 2.0.2 (aaaaaaa, master)" in out)
        ctx.check(f"after line comes from a FRESH `halo --version`, got {out!r}",
                  "after  halo 2.0.3 (bbbbbbb, master)" in out)
    finally:
        _restore_all(orig)


@test
def test_apply_update_nonzero_reinstall_returncode_is_a_failure(ctx: Ctx):
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb", run_returncode=1)
    try:
        code, _out, _err = _capture(update_cli.apply_update)
        ctx.check(f"the reinstall command's own failure propagates, got {code}", code == 1)
    finally:
        _restore_all(orig)


@test
def test_slash_update_hands_off_to_the_detached_updater(ctx: Ctx):
    """3.2.2.0 R3: `/update` never installs inside the halo process (its
    `halo.exe` parent holds the venv on Windows) and never relaunches it:
    `cli._apply_update_and_relaunch` hands over to update_detached with the
    `halo --continue` hint. The hand-off itself is a fake here."""
    from halo_harness import cli as cli_mod
    from halo_harness import update_detached
    calls, applied, relaunched = [], [], []
    saved = (update_detached.run_after_exit, update_cli.apply_update, upd.relaunch_halo)
    update_detached.run_after_exit = lambda **kw: calls.append(kw) or 0
    update_cli.apply_update = lambda **kw: applied.append(kw) or 0
    upd.relaunch_halo = lambda args, **kw: relaunched.append(args) or 0
    try:
        code = cli_mod._apply_update_and_relaunch(["--continue", "--model", "or:a/b"])
        ctx.check(f"exit 0, the updater was handed the work once, got {code} {calls}", code == 0 and len(calls) == 1)
        ctx.check(f"the hint resumes the session with the same flags, got {calls}",
                  calls[0].get("resume_hint") == "halo --continue --model or:a/b")
        ctx.check(f"no in-process install and no relaunch, got {applied} {relaunched}", not applied and not relaunched)
    finally:
        update_detached.run_after_exit, update_cli.apply_update, upd.relaunch_halo = saved


@test
def test_cmd_update_to_retargets_the_spec_in_the_printed_command(ctx: Ctx):
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="aaaaaaa")  # up to date -> --check only prints
    try:
        code, out, _err = _capture(update_cli.cmd_update, ["--check", "--to", "v9.9.9"])
        ctx.check(f"exit 0 (up to date, --to is cosmetic here), got {code}", code == 0)
        ctx.check(f"the printed command targets v9.9.9, got {out!r}",
                  "git+https://github.com/roloVibes/Halo-Harness@v9.9.9" in out)
    finally:
        _restore_all(orig)


@test
def test_up_to_date_prints_no_reinstall_command(ctx: Ctx):
    """3.0.2.0: the reinstall command read as something to type (and its
    `&&` is not PowerShell 5.1); an up-to-date install prints none of it."""
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="aaaaaaa")
    try:
        code, out, _err = _capture(update_cli.cmd_update, [])
        ctx.check(f"plain `halo update` says up to date with the commit and channel, got {out!r}",
                  code == 0 and "already up to date -- aaaaaaa is the newest on main" in out)
        ctx.check("and prints no command at all", "uv tool install" not in out and "to apply" not in out)
        code, out, _err = _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"--check on an up-to-date install prints no command either, got {out!r}", "uv tool install" not in out)
    finally:
        _restore_all(orig)
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb")
    try:
        code, out, _err = _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"--check with an update pending names halo update as the thing to run, got {out!r}",
                  code == 10 and "to apply: halo update  (it runs: " in out and "update command:" not in out)
    finally:
        _restore_all(orig)


@test
def test_cmd_update_channel_flag_is_remembered_in_config(ctx: Ctx):
    state_dir = Path(tempfile.mkdtemp(prefix="halo-update-channel-"))
    old_state_dir_env = os.environ.get("BRIDGE_STATE_DIR")
    os.environ["BRIDGE_STATE_DIR"] = str(state_dir)
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="aaaaaaa")
    try:
        ctx.check("no remembered channel yet", upd.default_channel({}) == "main")
        _capture(update_cli.cmd_update, ["--check", "--channel", "stable"])
        ctx.check("--channel stable is now remembered by default_channel()",
                  upd.default_channel({}) == "stable")
    finally:
        _restore_all(orig)
        if old_state_dir_env is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = old_state_dir_env


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
