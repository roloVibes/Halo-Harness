"""tests.test_storage_failures -- session files and locks when the disk or
the filesystem says no (3.6.0.0 fix pass, package "sessions-storage"):

  * a filesystem whose flock() answers with an error that is not "someone
    else holds it" (ENOSYS, ENOLCK, EOPNOTSUPP: Lustre without the flock
    mount option, NFS with no lock service) has no locks at all: the state-
    file lock and the governor's lock give up at once instead of burning
    their whole timeout on every call (a one-word `halo -p` took 90 s);
    real contention (EWOULDBLOCK / EAGAIN) still waits as before
  * a session log that cannot be written (a full disk) is said once, in
    plain words, instead of silently; an empty (0-byte) log is never the
    session `--continue` / `--resume` picks or lists
  * the governor's own "cannot persist" line reads `halo: ...`, not a raw
    UserWarning with a source path

The POSIX lock paths are driven on every platform by handing the modules a
fake `fcntl` whose flock() answers a chosen errno.
"""
from __future__ import annotations

import contextlib
import errno
import io
import json
import os
import sys
import tempfile
import time
import types
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all
from tests.test_review2_round10 import scoped_home

test, TESTS = new_registry()

_NO_LOCKS = errno.ENOSYS
_HELD = getattr(errno, "EWOULDBLOCK", errno.EAGAIN)


def _fake_fcntl(lock_errno: int):
    """A stand-in `fcntl` whose LOCK_EX request fails with `lock_errno`;
    unlocking always works."""
    calls = []

    def flock(fd, op):
        calls.append(op)
        if op & 2:  # LOCK_EX
            raise OSError(lock_errno, os.strerror(lock_errno))
    return types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4, LOCK_UN=8, flock=flock, calls=calls)


@contextlib.contextmanager
def _filelock_with(fake):
    from halo_harness import filelock
    saved = filelock.__dict__.get("fcntl", None)
    had = "fcntl" in filelock.__dict__
    filelock.fcntl = fake
    try:
        yield filelock
    finally:
        if had:
            filelock.fcntl = saved
        else:
            del filelock.fcntl


@contextlib.contextmanager
def _governor_with(fake, timeout_s: float):
    from halo_harness.providers import governor_state as gs
    saved = (gs.fcntl, gs._HAVE_FLOCK, gs._HAVE_MSVCRT, gs.LOCK_TIMEOUT_S, os.environ.get("GOVERNOR_STATE_DIR"))
    gs.fcntl, gs._HAVE_FLOCK, gs._HAVE_MSVCRT, gs.LOCK_TIMEOUT_S = fake, True, False, timeout_s
    os.environ["GOVERNOR_STATE_DIR"] = tempfile.mkdtemp(prefix="gov-nolock-")
    gs.reset_degraded_for_tests()
    try:
        yield gs
    finally:
        gs.fcntl, gs._HAVE_FLOCK, gs._HAVE_MSVCRT, gs.LOCK_TIMEOUT_S = saved[:4]
        if saved[4] is None:
            os.environ.pop("GOVERNOR_STATE_DIR", None)
        else:
            os.environ["GOVERNOR_STATE_DIR"] = saved[4]
        gs.reset_degraded_for_tests()


# ---- a filesystem with no locks ---------------------------------------------

@test
def test_lock_errors_that_mean_no_locks_here_are_told_apart_from_a_holder(ctx: Ctx):
    from halo_harness.filelock import lock_unsupported
    for name in ("ENOSYS", "ENOLCK", "EOPNOTSUPP", "EINVAL"):
        code = getattr(errno, name, None)
        if code is not None:
            ctx.check(f"{name} means this filesystem has no locks", lock_unsupported(OSError(code, name)))
    for name in ("EWOULDBLOCK", "EAGAIN", "EACCES", "EINTR"):
        code = getattr(errno, name)
        ctx.check(f"{name} means someone holds it: wait", not lock_unsupported(OSError(code, name)))


@test
def test_file_lock_gives_up_at_once_on_a_filesystem_without_locks(ctx: Ctx):
    fake = _fake_fcntl(_NO_LOCKS)
    with scoped_home() as home, _filelock_with(fake) as filelock:
        t0 = time.monotonic()
        with filelock.file_lock(home / "state.json", timeout=3.0) as got:
            ran = True
        took = time.monotonic() - t0
    ctx.check("the body ran", ran)
    ctx.check(f"without the lock, got {got}", got is False)
    ctx.check(f"at once, not after the timeout: took {took:.2f}s", took < 1.0)
    ctx.check(f"the fake flock was asked, got {fake.calls}", bool(fake.calls))


@test
def test_file_lock_still_waits_while_another_process_holds_it(ctx: Ctx):
    fake = _fake_fcntl(_HELD)
    with scoped_home() as home, _filelock_with(fake) as filelock:
        t0 = time.monotonic()
        with filelock.file_lock(home / "state.json", timeout=0.4) as got:
            pass
        took = time.monotonic() - t0
    ctx.check(f"not taken, got {got}", got is False)
    ctx.check(f"it kept trying until the timeout: took {took:.2f}s", took >= 0.35)
    ctx.check(f"more than one try, got {len(fake.calls)}", len(fake.calls) > 1)


@test
def test_governor_lock_gives_up_at_once_on_a_filesystem_without_locks(ctx: Ctx):
    fake = _fake_fcntl(_NO_LOCKS)
    with _governor_with(fake, 3.0) as gs, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        t0 = time.monotonic()
        failed = None
        try:
            with gs._Lock("host:gpu-box"):
                pass
            with gs._Lock("host:gpu-box"):
                pass
        except gs.LockFailed as e:
            failed = e
        took = time.monotonic() - t0
        reason = gs.is_degraded()
    ctx.check(f"no LockFailed, got {failed!r}", failed is None)
    ctx.check(f"two entries at once, not after the 3 s timeout: took {took:.2f}s", took < 1.0)
    ctx.check(f"the degraded flag says why, got {reason!r}", bool(reason) and "lock" in reason)
    said = [str(w.message) for w in caught if "lock" in str(w.message)]
    ctx.check(f"said once, got {said}", len(said) == 1)


@test
def test_governor_lock_still_waits_while_another_process_holds_it(ctx: Ctx):
    fake = _fake_fcntl(_HELD)
    with _governor_with(fake, 0.4) as gs:
        t0 = time.monotonic()
        failed = None
        try:
            with gs._Lock("host:gpu-box"):
                pass
        except gs.LockFailed as e:
            failed = e
        took = time.monotonic() - t0
    ctx.check(f"contention past the timeout is LockFailed, got {failed!r}", failed is not None)
    ctx.check(f"after waiting the timeout: took {took:.2f}s", took >= 0.35)


@test
def test_real_flock_on_posix_answering_enosys_does_not_wait(ctx: Ctx):
    """The same fault through the real `fcntl` module (POSIX only): its
    flock() is replaced by one that answers ENOSYS, as Lustre does without
    the flock mount option."""
    if os.name == "nt":
        raise SkipTest("POSIX flock only")
    import fcntl as real_fcntl
    from halo_harness import filelock
    from halo_harness.providers import governor_state as gs
    real_flock = real_fcntl.flock

    def no_locks(fd, op):
        if op & real_fcntl.LOCK_EX:
            raise OSError(errno.ENOSYS, "Function not implemented")
        return real_flock(fd, op)
    real_fcntl.flock = no_locks
    saved_dir = os.environ.get("GOVERNOR_STATE_DIR")
    os.environ["GOVERNOR_STATE_DIR"] = tempfile.mkdtemp(prefix="gov-enosys-")
    saved_timeout = gs.LOCK_TIMEOUT_S
    gs.LOCK_TIMEOUT_S = 3.0
    gs.reset_degraded_for_tests()
    try:
        with scoped_home() as home, warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t0 = time.monotonic()
            with filelock.file_lock(home / "state.json", timeout=3.0) as got:
                pass
            with gs._Lock("host:gpu-box"):
                pass
            took = time.monotonic() - t0
    finally:
        real_fcntl.flock = real_flock
        gs.LOCK_TIMEOUT_S = saved_timeout
        gs.reset_degraded_for_tests()
        if saved_dir is None:
            os.environ.pop("GOVERNOR_STATE_DIR", None)
        else:
            os.environ["GOVERNOR_STATE_DIR"] = saved_dir
    ctx.check(f"file_lock ran unlocked, got {got}", got is False)
    ctx.check(f"both locks gave up at once: took {took:.2f}s", took < 1.0)


# ---- a session log that cannot be written -----------------------------------

@contextlib.contextmanager
def _log_writes_fail():
    """The session log's appends fail the way a full disk fails them: the
    file is created (0 bytes) and the write raises ENOSPC."""
    from halo_harness.agent import log as log_mod
    real_open = open

    def full_disk_open(path, mode="r", *a, **kw):
        if "a" in mode and str(path).endswith(".jsonl"):
            real_open(path, "a", encoding="utf-8").close()
            raise OSError(errno.ENOSPC, "No space left on device")
        return real_open(path, mode, *a, **kw)
    log_mod.open = full_disk_open
    try:
        yield
    finally:
        del log_mod.open


@test
def test_a_failed_log_append_is_remembered_and_said_once(ctx: Ctx):
    from halo_harness.agent.log import SessionLog
    with scoped_home() as home, _log_writes_fail():
        log = SessionLog(home / "proj")
        log.append_user([{"type": "text", "text": "first"}])
        log.append_user([{"type": "text", "text": "second"}])
        first = log.take_write_error_note()
        again = log.take_write_error_note()
    ctx.check(f"the session goes on in memory, got {len(log.nodes())} nodes", len(log.nodes()) == 2)
    ctx.check(f"the error is kept, got {log.write_error!r}", "No space left" in (log.write_error or ""))
    ctx.check(f"one plain line, got {first!r}",
              (first or "").startswith("halo: this session's log could not be written")
              and "cannot be resumed" in first and "No space left" in first)
    ctx.check(f"said once, got {again!r}", again is None)


@test
def test_a_log_that_writes_fine_has_nothing_to_say(ctx: Ctx):
    from halo_harness.agent.log import SessionLog
    with scoped_home() as home:
        log = SessionLog(home / "proj")
        log.append_user([{"type": "text", "text": "hello"}])
        ctx.check("no error", log.write_error is None and log.take_write_error_note() is None)


def _write_log(cwd, sid: str, text: str, mtime: float):
    from halo_harness.agent import sessions as agent_sessions
    d = agent_sessions.sessions_dir(cwd)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{sid}.jsonl"
    p.write_text(text, encoding="utf-8")
    os.utime(p, (mtime, mtime))
    return p


@test
def test_continue_and_resume_skip_an_empty_log(ctx: Ctx):
    from halo_harness.agent import sessions as agent_sessions
    from halo_harness.agent.log import SessionLog
    from halo_harness.controller import Controller
    from halo_harness.config.paths import bridge_home
    with scoped_home() as home:
        cwd = home / "proj"
        cwd.mkdir()
        real, empty = "a" * 32, "b" * 32
        now = time.time()
        line = json.dumps({"type": "user", "content": [{"type": "text", "text": "the real question"}], "seq": 0})
        _write_log(cwd, real, line + "\n", now - 100)
        _write_log(cwd, empty, "", now)
        ctx.check("-c picks the last session with content",
                  agent_sessions.resolve_continue(cwd) == real)
        ctx.check("--resume with no value too", agent_sessions.resolve_resume(cwd, None) == (real, None))
        latest = SessionLog.latest_for_cwd(cwd)
        ctx.check(f"latest_for_cwd too, got {latest and latest.session_id}",
                  latest is not None and latest.session_id == real)
        listed = [r["id"] for r in agent_sessions.list_sessions(cwd)]
        ctx.check(f"the print-mode list leaves the empty one out, got {listed}", listed == [real])
        found = [r["id"] for r in agent_sessions.find_resume_matches(cwd, "")]
        ctx.check(f"the --resume matcher too, got {found}", found == [real])
        fake_self = types.SimpleNamespace(cwd=cwd, state_dir=Path(bridge_home()))
        picker = [r["id"] for r in Controller.list_sessions(fake_self)]
        ctx.check(f"the TUI picker too, got {picker}", picker == [real])
    with scoped_home() as home:
        cwd = home / "proj"
        cwd.mkdir()
        _write_log(cwd, "c" * 32, "", time.time())
        ctx.check("only an empty log: nothing to continue", agent_sessions.resolve_continue(cwd) is None)


def _scn_answer(h, body):
    from tests.helpers.mock_openai import _finish
    _finish(h, [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": "RC-ANSWER-42"}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ])


@test
def test_print_mode_on_a_full_disk_says_the_session_is_not_saved(ctx: Ctx):
    from tests.helpers.fake_home import build_fake_home
    from tests.helpers.mock_openai import MockUpstream, SCENARIOS
    from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
    from halo_harness import headless
    ensure_default_provider_credentials()
    fh = build_fake_home()
    saved_home = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    mock = MockUpstream().start()
    SCENARIOS["storage-full"] = _scn_answer
    from halo_harness.agent.loop import Session
    seen_kinds: list = []
    real_turn = Session.turn

    def recording_turn(self, *a, **kw):
        for ev in real_turn(self, *a, **kw):
            seen_kinds.append((ev.kind, (ev.data or {}).get("text", "")))
            yield ev
    Session.turn = recording_turn
    out, err = io.StringIO(), io.StringIO()
    try:
        os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
        with _log_writes_fail(), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = headless.run_print_mode(prompt="hi", cwd=fh["proj"], model_ref_raw="or:mock/storage-full",
                                           max_turns=2)
    finally:
        Session.turn = real_turn
        mock.stop()
        os.environ.pop("BRIDGE_OPENROUTER_BASE_URL", None)
        if saved_home is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = saved_home
    text = err.getvalue()
    ctx.check(f"exit 0 and the answer printed, got {code} / {out.getvalue()!r}",
              code == 0 and "RC-ANSWER-42" in out.getvalue())
    hits = [ln for ln in text.splitlines() if ln.startswith("halo: this session's log could not be written")]
    ctx.check(f"one plain line on stderr, got {text!r}", len(hits) == 1 and "cannot be resumed" in hits[0])
    notes = [t for k, t in seen_kinds if k == "system_note" and "could not be written" in t]
    ctx.check(f"the turn carries it as a system line for the TUI, got {notes}", len(notes) == 1)


# ---- the governor's own line -------------------------------------------------

@test
def test_governor_warning_reads_as_a_halo_line_not_a_raw_userwarning(ctx: Ctx):
    from halo_harness.providers import governor_state as gs
    gs.reset_degraded_for_tests()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            gs.warn_once("governor: cannot persist state (No space left on device)")
    finally:
        gs.reset_degraded_for_tests()
    ctx.check(f"one warning, got {len(caught)}", len(caught) == 1)
    w = caught[0]
    ctx.check("still a UserWarning for code that filters on it", issubclass(w.category, UserWarning))
    shown = warnings.formatwarning(w.message, w.category, w.filename, w.lineno)
    ctx.check(f"shown as one halo: line, got {shown!r}",
              shown == "halo: governor: cannot persist state (No space left on device)\n")
    other = warnings.formatwarning(UserWarning("x"), UserWarning, "f.py", 1)
    ctx.check(f"other warnings keep their usual shape, got {other!r}", "UserWarning" in other)


# ---- a home Halo cannot use (fix pass 2) ---------------------------------------

def _run_halo(home: Path, *args: str, stdin: str = "") -> "tuple[int, str]":
    """The real `python -m halo_harness <args>` in a scratch home (no network, no updater)."""
    import subprocess
    env = dict(os.environ, BRIDGE_TEST_HOME=str(home), HOME=str(home), USERPROFILE=str(home),
               OLLAMA_HOST="http://127.0.0.1:9", HALO_NO_UPDATER="1", PYTHONIOENCODING="utf-8",
               OPENROUTER_API_KEY="sk-test-dummy",
               PYTHONPATH=str(Path(__file__).resolve().parent.parent))
    env.pop("BRIDGE_STATE_DIR", None)
    proj = home / "proj"
    proj.mkdir(exist_ok=True)
    p = subprocess.run([sys.executable, "-m", "halo_harness", *args], cwd=str(proj), env=env, input=stdin,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _home_with_halo_as_a_file() -> Path:
    home = Path(tempfile.mkdtemp(prefix="halo-file-home-"))
    (home / ".halo").write_text("x", encoding="utf-8")
    return home


@test
def test_a_state_folder_that_is_a_file_stops_halo_with_one_plain_line(ctx: Ctx):
    """`halo -p` and `halo init` in a home whose ~/.halo is a file ended with a traceback (FileNotFoundError /
    FileExistsError deep in the first mkdir). Now: one `halo: cannot use ...` line, exit 2."""
    home = _home_with_halo_as_a_file()
    for args, stdin in ((("-p", "hello"), ""), (("init", "--no-live", "--provider", "openrouter"), "\n")):
        rc, out = _run_halo(home, *args, stdin=stdin)
        ctx.check(f"`halo {' '.join(args)}`: exit 2, got {rc}", rc == 2)
        ctx.check(f"`halo {' '.join(args)}`: one plain line, no traceback, got {out[-600:]!r}",
                  "Traceback" not in out and f"halo: cannot use {home / '.halo'}" in out)


@test
def test_the_state_folder_check_cases(ctx: Ctx):
    from halo_harness.state_home import problem
    root = Path(tempfile.mkdtemp(prefix="halo-state-check-"))
    ctx.check("an existing folder that can be written: nothing to say", problem(root) is None)
    ctx.check("a folder that can be created: nothing to say", problem(root / "new" / ".halo") is None)
    ctx.check("nothing was created by looking", not (root / "new").exists())
    (root / "file").write_text("x", encoding="utf-8")
    said = problem(root / "file") or ""
    ctx.check(f"a file in its place: the plain line, got {said!r}", said.startswith(f"halo: cannot use {root / 'file'}"))
    said = problem(root / "file" / ".halo") or ""
    ctx.check(f"a file where a parent folder should be: the plain line, got {said!r}",
              said.startswith("halo: cannot use"))
    if os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        return  # the mode bits below mean nothing on Windows or to root
    ro = root / "readonly-home"
    ro.mkdir()
    os.chmod(ro, 0o555)
    try:
        said = problem(ro / ".halo") or ""
        ctx.check(f"a home that cannot be written: the plain line naming sudo chown, got {said!r}",
                  said.startswith(f"halo: cannot use {ro / '.halo'}") and f"sudo chown -R $USER {ro})" in said)
        ro2 = root / "locked"
        ro2.mkdir()
        os.chmod(ro2, 0o000)
        try:
            said = problem(ro2) or ""
            ctx.check(f"a ~/.halo that cannot be read (root-owned after sudo): the plain line, got {said!r}",
                      said.startswith(f"halo: cannot use {ro2}"))
        finally:
            os.chmod(ro2, 0o700)
    finally:
        os.chmod(ro, 0o755)


@test
def test_an_os_error_inside_halos_folder_is_the_plain_line_not_a_traceback(ctx: Ctx):
    from halo_harness import cli
    from halo_harness.state_home import line_for_error
    with scoped_home() as home:
        own = PermissionError(errno.EACCES, "Permission denied", str(home / ".halo" / "config.json"))
        said = line_for_error(own) or ""
        ctx.check(f"a file in ~/.halo: the plain line, got {said!r}",
                  said.startswith(f"halo: cannot use {home / '.halo' / 'config.json'} (Permission denied)"))
        other = PermissionError(errno.EACCES, "Permission denied", str(home / "proj" / "notes.txt"))
        ctx.check("a file elsewhere stays a real error", line_for_error(other) is None)
        real_main = cli._main

        def failing(argv=None):
            raise own
        cli._main = failing
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                rc = cli.main(["-p", "x"])
        finally:
            cli._main = real_main
        ctx.check(f"halo ends with exit 2 and the line, got {rc} / {err.getvalue()!r}",
                  rc == 2 and err.getvalue().startswith("halo: cannot use"))


@test
def test_doctor_names_the_state_folder_first_and_a_failing_check_is_one_row(ctx: Ctx):
    """`halo doctor` said nothing about a ~/.halo it could not use, and one check that could not read its file
    (PermissionError on .halo/models-dev.json) ended the whole run with a traceback."""
    from halo_harness import doctor
    with scoped_home() as home:
        (home / ".halo").write_text("x", encoding="utf-8")
        checks, ok = doctor.run_checks_structured()
        ctx.check(f"the first row names the folder, got {checks[0] if checks else None}",
                  checks and checks[0]["id"] == "state_home" and checks[0]["status"] == "missing"
                  and "cannot use" in checks[0]["message"])
        ctx.check("doctor is not ok", ok is False)
    with scoped_home() as home:
        real = doctor._check_catalog_ages

        def unreadable():
            raise PermissionError(errno.EACCES, "Permission denied", str(home / ".halo" / "models-dev.json"))
        doctor._check_catalog_ages = unreadable
        try:
            checks, ok = doctor.run_checks_structured()
        finally:
            doctor._check_catalog_ages = real
        ids = [c["id"] for c in checks]
        row = next((c for c in checks if c["id"] == "catalogs"), None)
        ctx.check(f"the failing check is one missing row naming the file, got {row}",
                  row is not None and row["status"] == "missing" and "models-dev.json" in row["message"])
        ctx.check(f"the checks after it still ran, got {ids[-5:]}", "install" in ids and "permission_mode" in ids)
        ctx.check("the folder row is ok in a usable home", checks[0]["id"] == "state_home" and checks[0]["status"] == "ok")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
