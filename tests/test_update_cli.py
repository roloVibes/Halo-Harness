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
             "commit_is_ancestor", "other_halo_pids", "other_halo_processes", "run", "halo_ancestors", "halo_openers")}
    orig["update_stop._stop"] = update_stop._stop
    # 3.6.0.0 R13: the install runs in the standalone updater; here it runs in this process over the fakes below
    from tests.helpers.update_inline import inline
    orig["update_cli.launch"] = update_cli.launch
    update_cli.launch = inline
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
    upd.halo_ancestors = lambda **kw: []  # 3.6.0.0 R13: the Windows updater waits for these; never a real process list
    upd.halo_openers = lambda **kw: []
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
    update_cli.launch = orig.pop("update_cli.launch", None)
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
def test_cmd_update_check_says_when_its_answer_is_the_cache(ctx: Ctx):
    """3.3.16.0 (rolo, 2026-11-10: a box behind a dead router read "3.3.14.0 is the latest" and `halo update` said
    up to date while v3.3.15.0 existed): an answer `latest_available` took from the cache prints the note -- from
    the cache, its age, the live failure -- on the available line and on "already up to date"."""
    import time
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="aaaaaaa")
    upd.latest_available = lambda *a, **kw: {"channel": "main", "commit": "aaaaaaa", "ref": "master", "reason": None,
                                             "source": "cache", "checked_at": time.time() - 6 * 3600,
                                             "live_reason": "network unavailable"}
    try:
        code, out, _err = _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"--check: the available line carries the cache note, got {code} {out!r}",
                  code == 0 and "available (main): aaaaaaa, master (from the cache, checked 6 h ago; the live check failed: "
                  "network unavailable -- run `halo update --check` again when you are online)" in out)
        code, out, _err = _capture(update_cli.cmd_update, [])
        ctx.check(f"apply: 'already up to date' carries it too, got {code} {out!r}",
                  code == 0 and "already up to date" in out and "(from the cache, checked 6 h ago" in out)
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
        # R12: getcwd() is the resolved spelling (macOS: the temp folder is under /private)
        ctx.check(f"this PROCESS's own cwd is untouched, got {os.getcwd()!r}",
                  Path(os.getcwd()).resolve() == other_project.resolve())
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
def test_apply_update_retries_once_on_the_system_store_after_a_certificate_failure(ctx: Ctx):
    """3.3.16.0 (the owner's Kali, 2026-11-10): uv stopped at "invalid peer certificate: UnknownIssuer"; the
    updater runs the uv command once more on the system's certificate store and says why; a second failure names
    what to check. The store is asked for through the environment (UV_SYSTEM_CERTS, and UV_NATIVE_TLS for a uv
    before 0.11), never the flag uv renamed."""
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb")
    ran = []

    def fake_run(cmd, **kwargs):
        if isinstance(cmd, list) and cmd[:1] == ["halo"]:
            return _Proc(stdout="halo 2.0.3 (bbbbbbb, master)\n")
        ran.append((cmd, kwargs.get("env") or {}))
        if (kwargs.get("env") or {}).get("UV_SYSTEM_CERTS") == "1":
            return _Proc(stdout="Installed 1 executable: halo", returncode=0)
        return _Proc(stdout="error: Error while accessing remote requirements file\n  Caused by: invalid peer "
                     "certificate: UnknownIssuer", returncode=1)
    upd.run = fake_run
    try:
        code, out, _err = _capture(lambda: update_cli.apply_update(cmd="uv tool install --reinstall git+https://x/y"))
        ctx.check(f"the same command twice, the second with the system store asked for, got {[c for c, _ in ran]}",
                  len(ran) == 2 and ran[0][0] == ran[1][0] and "--native-tls" not in ran[1][0] and not ran[0][1]
                  and ran[1][1].get("UV_NATIVE_TLS") == "1" and "PATH" in {k.upper() for k in ran[1][1]})
        ctx.check(f"the line to paste carries the variables, got {out!r}", "UV_SYSTEM_CERTS" in out)
        ctx.check(f"it says why and ends 0, got {code} {out!r}",
                  code == 0 and "did not trust a certificate" in out and "after  halo 2.0.3 (bbbbbbb, master)" in out)
    finally:
        _restore_all(orig)


@test
def test_apply_update_fetches_the_lock_itself_and_fails_closed_when_it_cannot(ctx: Ctx):
    """3.3.16.0: the lock is fetched by halo into a local file; 3.4.1.2 (PACKS-10): a failed fetch installs nothing."""
    from halo_harness import update_install as UI
    url = "https://raw.githubusercontent.com/roloVibes/Halo-Harness/master/requirements.lock"
    cmd = f"uv tool install --reinstall --constraints {url} git+https://github.com/roloVibes/Halo-Harness"
    local, note = UI.pin_locally(cmd, fetch=lambda u: b"textual==0.80.0\nrich==13.0.0\n")
    ctx.check(f"fetched: the command points at a local copy and nothing is said, got {local!r} {note!r}",
              url not in local and "--constraints " in local and local.endswith("requirements.lock\" git+https://github.com/roloVibes/Halo-Harness")
              and note == "")
    def boom(u):
        raise OSError("certificate verify failed: unable to get local issuer certificate")
    dropped, note = UI.pin_locally(cmd, fetch=boom)
    ctx.check(f"PACKS-10: not fetched: nothing to run, the line says how to go on, got {dropped!r} {note!r}", dropped is None
              and "nothing was installed" in note and note.endswith("on purpose: uv tool install --reinstall git+https://github.com/roloVibes/Halo-Harness"))
    ctx.check("a command without a pin is untouched", UI.pin_locally("pip install -U x", fetch=boom) == ("pip install -U x", ""))
    ctx.check("the version is the banner's last line",
              UI.last_line("  _  _   _   _    ___  \n |_||_| |_| |_|  | | | \n\nhalo 3.3.14.0 (28d0b24)\n") == "halo 3.3.14.0 (28d0b24)")


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
def test_an_older_release_is_called_older_and_never_installed_by_accident(ctx: Ctx):
    """3.6.0.0 R13 (a laptop: `halo update --check` on a main-line build said the stable release was "3 commit(s)
    ahead" when applying it would move the machine BACK): versions are compared; --check says OLDER in plain words;
    a plain `halo update` asks for --to or --channel main; `--to <tag>` still moves back on purpose, its checksums
    checked, and a release without them is refused in one line."""
    from tests.helpers.update_inline import PLANS
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="ccccccc",
                      after_version="halo 3.5.0.1 (ccccccc, v3.5.0.1)")
    saved = (upd.default_channel, upd.tag_checksums)
    upd.installed_build = lambda **kw: {"version": "3.6.0.0", "commit": "aaaaaaa", "requested_revision": None,
                                         "checkout": None, "branch": "master", "editable": False}
    upd.latest_available = lambda *a, **kw: {"channel": "stable", "commit": "ccccccc", "ref": "v3.5.0.1",
                                              "reason": None, "source": "live"}
    upd.default_channel = lambda build=None: "stable"
    upd.commits_between = lambda *a, **kw: ([], 3)
    upd.tag_checksums = lambda tag, **kw: [{"name": "checksums.txt"}]
    try:
        code, out, _err = _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"--check: nothing newer (exit 0), said in plain words, no commit count, got {code} {out!r}",
                  code == 0 and "the newest release, 3.5.0.1, is OLDER than this build (3.6.0.0, aaaaaaa); "
                  "`halo update` would move you back" in out and "commit(s)" not in out)
        before = len(PLANS)
        code, out, err = _capture(update_cli.cmd_update, [])
        ctx.check(f"a plain `halo update` does not move back; it names --to and --channel main, got {code} {err!r}",
                  code == 1 and "not moving back" in err and "--to v3.5.0.1" in err and "--channel main" in err
                  and len(PLANS) == before and "uv tool install" not in out)
        code, out, err = _capture(update_cli.cmd_update, ["--to", "v3.5.0.1"])
        ctx.check(f"--to v3.5.0.1 moves back on purpose and checks that version answers, got {code} {out[-300:]!r}",
                  code == 0 and PLANS[-1]["expect"].get("version") == "3.5.0.1" and "@v3.5.0.1" in out)
        upd.tag_checksums = lambda tag, **kw: [{"name": "source.tar.gz"}]
        code, out, err = _capture(update_cli.cmd_update, ["--to", "v3.5.0.1"])
        ctx.check(f"a release without checksums: refused in one line (--no-verify is the way round), got {err!r}",
                  code == 1 and err.strip().count("\n") == 0 and "no checksums.txt" in err and "--no-verify" in err)
        upd.latest_available = lambda *a, **kw: {"channel": "stable", "commit": "ccccccc", "ref": "v3.6.1.0",
                                                  "reason": None, "source": "live"}
        upd.tag_checksums = lambda tag, **kw: [{"name": "checksums.txt"}]
        code, out, _err = _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"a NEWER release is still an update (exit 10), got {code} {out!r}", code == 10 and "OLDER" not in out)
    finally:
        upd.default_channel, upd.tag_checksums = saved
        _restore_all(orig)


@test
def test_a_failed_install_hands_back_the_previous_install(ctx: Ctx):
    """3.6.0.0 R13: the plan carries what puts the install back -- the git commit installed now and a lock of
    this environment -- and a failed install runs it (here inline, over the fakes; tests/test_update_runner.py runs
    the real updater against a scratch tool environment)."""
    from tests.helpers.update_inline import PLANS
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb", run_returncode=1,
                      after_version="halo 2.0.2 (aaaaaaa, master)")
    ran = []

    def fake_run(cmd, **kwargs):
        if isinstance(cmd, list) and cmd[:1] == ["halo"]:
            return _Proc(stdout="halo 2.0.2 (aaaaaaa, master)\n")
        ran.append(cmd)
        return _Proc(returncode=1 if len(ran) == 1 else 0)
    upd.run = fake_run
    saved_du, upd._direct_url = upd._direct_url, lambda: None  # this test environment's own metadata stays out
    try:
        code, out, _err = _capture(update_cli.cmd_update, [])
        plan = PLANS[-1]
        ctx.check(f"the plan names the previous spec at its commit and a lock file, got {plan.get('restore')}",
                  (plan.get("restore") or {}).get("cmd", "").endswith("git+https://github.com/roloVibes/Halo-Harness@aaaaaaa"))
        ctx.check(f"the install ran, failed, and the restore ran, got {ran}", len(ran) == 2 and ran[1].endswith("@aaaaaaa"))
        ctx.check(f"one line says the old one is back, exit 1, got {code} {out[-400:]!r}",
                  code == 1 and "halo 2.0.2 (aaaaaaa, master) was put back and answers again" in out)
    finally:
        upd._direct_url = saved_du
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
        ctx.check("3.6.0.0 R13: `--check --channel stable` reports only and writes nothing",
                  upd.default_channel({}) == "main" and not (state_dir / "config.json").exists())
        _capture(update_cli.cmd_update, ["--channel", "stable"])
        ctx.check("--channel stable (no --check) is now remembered by default_channel()",
                  upd.default_channel({}) == "stable")
    finally:
        _restore_all(orig)
        if old_state_dir_env is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = old_state_dir_env


# ---- the judge's pass (3.6.0.0 R13) ----
@test
def test_an_updater_that_cannot_start_stops_nothing_first(ctx: Ctx):
    """Judge should-fix 1 and 2: the reasons the updater cannot start are checked BEFORE any process is stopped;
    BRIDGE_STATE_DIR (a user's own setting) never blocks an update, only HALO_NO_UPDATER and a test home do."""
    from halo_harness import update_plan as UP
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb", other_pids=[4242])
    stopped = orig["stopped"]
    update_cli.launch = None  # the real launch path, whose guard refuses here (HALO_NO_UPDATER / a test home)
    saved_env = {k: os.environ.get(k) for k in ("HALO_NO_UPDATER", "BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    try:
        os.environ["HALO_NO_UPDATER"] = "1"
        code, out, err = _capture(update_cli.apply_update)
        ctx.check(f"refused in one line, and nothing stopped, got {code} {stopped} {err!r}",
                  code == 1 and stopped == [] and "switched off here" in err and err.strip().count("\n") == 0)
        os.environ.pop("HALO_NO_UPDATER")
        os.environ.pop("BRIDGE_TEST_HOME", None)
        os.environ["BRIDGE_STATE_DIR"] = str(Path(tempfile.mkdtemp(prefix="r13-statedir-")))
        ctx.check("BRIDGE_STATE_DIR alone does not switch the updater off",
                  UP.launch_refusal(python=["/opt/py/python3", "-I"]) is None)
        ctx.check("no outside Python is a reason too (said before anything stops)",
                  "no Python outside" in (UP.launch_refusal(python=[]) or ""))
    finally:
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        _restore_all(orig)


@test
def test_a_studio_that_opened_this_halo_is_left_to_the_updater(ctx: Ctx):
    """Judge must-fix 3: a Studio above this halo is named up front, never stopped from inside its own tree (that
    would end this halo too) and never waited on: the updater stops it once this halo has exited."""
    from tests.helpers.update_inline import PLANS
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb", other_pids=[4242, 400])
    stopped = orig["stopped"]
    upd.halo_openers = lambda **kw: [{"pid": 400, "what": "studio", "cmd": "halo studio"}]
    try:
        code, out, _err = _capture(update_cli.apply_update)
        ctx.check(f"named up front, got {out!r}", "Studio (pid 400) opened this halo; the updater stops it" in out)
        ctx.check(f"the other halo stopped here, the opener not, got {[e['pid'] for e in stopped]}",
                  [e["pid"] for e in stopped] == [4242])
        ctx.check(f"the opener is in the updater's stop list, got {PLANS[-1].get('stop_pids')}",
                  code == 0 and PLANS[-1].get("stop_pids") == [400] and 400 not in PLANS[-1].get("wait_pids", []))
    finally:
        _restore_all(orig)


@test
def test_an_opener_whose_pid_is_gone_on_a_second_look_is_not_in_the_plan(ctx: Ctx):
    """3.6.0.1: the opener's start time is read after the process list; one more look keeps it only while its pid
    still runs the same command, so a pid reused in between never lends another program's start time to the plan."""
    from tests.helpers.update_inline import PLANS
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb", other_pids=[4242])
    from halo_harness import children
    looks = []
    upd.halo_openers = lambda **kw: looks.append(1) or ([{"pid": 400, "what": "studio", "cmd": "halo studio"}]
                                                         if len(looks) == 1 else [])
    saved = children.pid_running
    children.pid_running = lambda pid: pid != 400  # the opener's pid no longer runs
    try:
        code, out, _err = _capture(update_cli.apply_update)
        ctx.check(f"not named, not in the plan, got {code} {out!r} {PLANS[-1].get('stop_pids')}",
                  code == 0 and "pid 400" not in out and 400 not in (PLANS[-1].get("stop_pids") or [])
                  and len(looks) == 2)
    finally:
        children.pid_running = saved
        _restore_all(orig)


@test
def test_an_opener_still_running_when_the_second_look_reads_nothing_is_never_stopped_from_inside(ctx: Ctx):
    """Checker (batch 1): a second look that cannot be read dropped the opener, so `skip` lost it and this halo
    could stop the Studio that opened it from inside its own tree. Kept, with no start time (never ended by
    number): named, left to the updater, which holds the install while it may still run."""
    from tests.helpers.update_inline import PLANS
    from halo_harness import children
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb", other_pids=[4242, 400])
    stopped = orig["stopped"]
    looks = []
    upd.halo_openers = lambda **kw: looks.append(1) or ([{"pid": 400, "what": "studio", "cmd": "halo studio"}]
                                                         if len(looks) == 1 else [])
    saved = children.pid_running
    children.pid_running = lambda pid: True
    try:
        code, out, _err = _capture(update_cli.apply_update)
        ctx.check(f"named up front, got {out!r}", "Studio (pid 400) opened this halo" in out)
        ctx.check(f"never stopped from inside, got {[e['pid'] for e in stopped]}",
                  [e["pid"] for e in stopped] == [4242])
        ctx.check(f"left to the updater with no start time, got {PLANS[-1:]}",
                  PLANS and PLANS[-1].get("stop_pids") == [400]
                  and all((PLANS[-1].get("stop_starts") or {}).get(k) is None for k in (400, "400")))
    finally:
        children.pid_running = saved
        _restore_all(orig)


@test
def test_an_archive_install_of_the_current_tag_is_not_called_older(ctx: Ctx):
    """Judge should-fix: a build whose commit is unknown is "unknown", never "older"."""
    got = update_cli.older_release({"version": "3.5.0.1", "commit": None, "requested_revision": None},
                                   {"commit": "aaaaaaa", "ref": "v3.5.0.1"}, "stable")
    ctx.check(f"commit unknown -> None, got {got!r}", got is None)
    got = update_cli.older_release({"version": "3.6.0.0", "commit": "c0ffee1"}, {"commit": "aaaaaaa", "ref": "v3.5.0.1"},
                                   "stable")
    ctx.check("a known main-line build ahead of the tag still is told", got and "OLDER" in got)


@test
def test_a_build_ahead_of_the_main_line_is_told_and_nothing_is_offered(ctx: Ctx):
    """3.6.0.0 fix (realcheck on every release candidate): a checkout whose HEAD is AHEAD of the branch head on
    offer (release.py's version commit on rc/<version>, a local commit) was told "differs from (main) ... to apply:
    halo update" with exit 10, and `halo update` would have moved it back. The checkout's git says the offer is an
    ancestor of this build: said in plain words, exit 0, no install line, and a plain `halo update` installs nothing.
    With no checkout to ask, or a real divergence, the old answer stands."""
    from tests.helpers.update_inline import PLANS
    orig = _patch_all(installed_commit="aaaaaaa", available_commit="bbbbbbb")
    upd.commit_is_ancestor = lambda old, new, **kw: (old, new) == ("bbbbbbb", "aaaaaaa")  # the offer is behind
    try:
        code, out, _err = _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"--check: exit 0, says this build is ahead and the offer older, no install line, got {code} {out!r}",
                  code == 0 and "ahead of master (bbbbbbb)" in out and "older" in out and "to apply:" not in out)
        before = len(PLANS)
        code, out, err = _capture(update_cli.cmd_update, [])
        ctx.check(f"a plain `halo update` installs nothing and says why, got {code} {out!r} {err!r}",
                  code == 0 and len(PLANS) == before and "nothing to install" in out and "ahead of master" in out)
        upd.commit_is_ancestor = lambda old, new, **kw: False  # diverged: neither leads to the other
        code, out, _err = _capture(update_cli.cmd_update, ["--check"])
        ctx.check(f"a real divergence keeps 'differs from' and exit 10, got {code} {out!r}",
                  code == 10 and "differs from (main): bbbbbbb" in out and "ahead of" not in out)
    finally:
        _restore_all(orig)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
