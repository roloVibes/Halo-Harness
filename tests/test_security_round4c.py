"""tests.test_security_round4c -- 2.0.10 round 4, security fix pass 2,
findings 24-25 of docs/harness/SECURITY-REVIEW-2.0.10.md.

24  the state tree (`~/.halo`, sessions, shadow snapshots, tool-result spills,
    bridge.log) is created 0700 / 0600 and an existing tree is tightened once
    (POSIX; a no-op on Windows -- the mode checks that need real mode bits
    skip there, the call-recording checks run everywhere)
25  provider- and CLI-supplied ids are checked before they become a file
    name: session ids are rejected with a clear error, tool_use_ids become a
    safe stem
"""
from __future__ import annotations

import contextlib
import io
import os
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="halo-sec4c-home-"))

from halo_harness import privateio, safe_id

_POSIX = os.name != "nt"


def _tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="halo-sec4c-")).resolve()


@contextlib.contextmanager
def _record_modes():
    """Pretend to be POSIX and record every chmod / os.open mode that
    privateio asks for (nothing is really chmod-ed), so the 0700/0600 intent
    is checked on every host."""
    chmods, opens = [], []
    real_chmod, real_open, real_flag = os.chmod, os.open, privateio.IS_POSIX

    def fake_chmod(path, mode, *a, **k):
        chmods.append((str(path).replace("\\", "/"), mode))

    def fake_open(path, flags, mode=0o777, *a, **k):
        opens.append((str(path).replace("\\", "/"), mode))
        return real_open(path, flags, mode, *a, **k)

    os.chmod, os.open, privateio.IS_POSIX = fake_chmod, fake_open, True
    try:
        yield chmods, opens
    finally:
        os.chmod, os.open, privateio.IS_POSIX = real_chmod, real_open, real_flag


@contextlib.contextmanager
def _state_dir(path: Path):
    saved = os.environ.get("BRIDGE_STATE_DIR")
    os.environ["BRIDGE_STATE_DIR"] = str(path)
    try:
        yield
    finally:
        if saved is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = saved


def _mode(path: Path) -> int:
    return stat.S_IMODE(os.stat(path).st_mode)


# ---- 24 -----------------------------------------------------------------------------------


@test
def test_f24_private_mkdir_makes_every_new_directory_0700(ctx: Ctx):
    base = _tmp()
    target = base / "a" / "b" / "c"
    with _record_modes() as (chmods, _opens):
        privateio.private_mkdir(target)
    pinned = {p: m for p, m in chmods}
    for d in (base / "a", base / "a" / "b", target):
        ctx.check(f"{d.name} pinned to 0700", pinned.get(str(d).replace("\\", "/")) == 0o700)
    ctx.check("the pre-existing parent is left alone", str(base).replace("\\", "/") not in pinned)
    if _POSIX:
        old = os.umask(0o022)
        try:
            fresh = base / "x" / "y"
            privateio.private_mkdir(fresh)
        finally:
            os.umask(old)
        ctx.check("real modes, umask 022: 0700", _mode(fresh) == 0o700 and _mode(fresh.parent) == 0o700)


@test
def test_f24_session_log_dirs_and_transcript_are_private(ctx: Ctx):
    home = _tmp() / ".halo"
    with _state_dir(home), _record_modes() as (chmods, opens):
        from halo_harness.agent.log import SessionLog
        log = SessionLog(_tmp())
        log.append_system("hello")
    pinned = {p: m for p, m in chmods}
    ctx.check("sessions/ and the project dir are pinned 0700",
              pinned.get(str(home / "sessions").replace("\\", "/")) == 0o700
              and pinned.get(str(log.dir).replace("\\", "/")) == 0o700)
    modes = {p: m for p, m in opens}
    ctx.check("the transcript is created 0600", modes.get(str(log.path).replace("\\", "/")) == 0o600)
    if _POSIX:
        ctx.check("real modes", _mode(log.dir) == 0o700 and _mode(log.path) == 0o600)


@test
def test_f24_shadow_store_and_spills_are_private(ctx: Ctx):
    home = _tmp() / ".halo"
    session_dir = home / "sessions" / "slug" / "sid"
    with _state_dir(home), _record_modes() as (chmods, opens):
        from halo_harness.shadow import ShadowStore
        ShadowStore(session_dir)
        from halo_harness.tools.truncate import spill_and_truncate
        spill_and_truncate("x" * 5000, cap=100, session_dir=session_dir, tool_use_id="toolu_1")
    pinned = {p: m for p, m in chmods}
    ctx.check("the shadow dir is pinned 0700", pinned.get(str(session_dir / "shadow").replace("\\", "/")) == 0o700)
    ctx.check("the tool-results dir is pinned 0700",
              pinned.get(str(session_dir / "tool-results").replace("\\", "/")) == 0o700)
    spill = str(session_dir / "tool-results" / "toolu_1.txt").replace("\\", "/")
    ctx.check("the spill file is created 0600", dict(opens).get(spill) == 0o600)


@test
def test_f24_existing_tree_is_tightened_once_with_one_notice(ctx: Ctx):
    home = _tmp() / ".halo-state"
    (home / "sessions" / "slug").mkdir(parents=True)
    log = home / "sessions" / "slug" / "s.jsonl"
    log.write_text("{}\n", encoding="utf-8")
    hist = home / "history.jsonl"
    hist.write_text("x\n", encoding="utf-8")
    with _record_modes() as (chmods, _opens):
        changed = privateio.tighten_state_tree(home)
        first = {p: m for p, m in chmods}
        ctx.check("the home, the dirs and the files are tightened",
                  first.get(str(home).replace("\\", "/")) == 0o700
                  and first.get(str(log).replace("\\", "/")) == 0o600
                  and first.get(str(home / "sessions").replace("\\", "/")) == 0o700 and changed >= 4)
        ctx.check("a marker records it", (home / ".modes-v1").exists())
        chmods.clear()
        privateio.tighten_state_tree(home)
        ctx.check("the second launch does not walk the tree again",
                  str(log).replace("\\", "/") not in {p for p, _m in chmods})
    fresh = _tmp() / ".halo-state2"
    fresh.mkdir()
    (fresh / "a.jsonl").write_text("{}\n", encoding="utf-8")
    err = io.StringIO()
    with _record_modes(), contextlib.redirect_stderr(err):
        privateio.tighten_state_tree_notice(fresh)
    ctx.check("one notice line the first time", err.getvalue().count("\n") == 1 and "owner-only" in err.getvalue())
    ctx.check("Windows: a no-op", privateio.tighten_state_tree(_tmp() / ".halo-none") == 0)
    if _POSIX:
        d = _tmp() / ".halo-real"
        (d / "sub").mkdir(parents=True)
        f, x = d / "sub" / "f.jsonl", d / "run.sh"
        f.write_text("{}\n", encoding="utf-8")
        x.write_text("#!/bin/sh\n", encoding="utf-8")
        os.chmod(f, 0o644)
        os.chmod(x, 0o755)
        os.chmod(d / "sub", 0o755)
        privateio.tighten_state_tree(d)
        err2 = io.StringIO()
        with contextlib.redirect_stderr(err2):
            privateio.tighten_state_tree_notice(d)
        ctx.check("no notice once the tree is already private", err2.getvalue() == "")
        ctx.check("real modes: 0600 file, 0700 dirs, owner exec kept",
                  _mode(f) == 0o600 and _mode(d / "sub") == 0o700 and _mode(d) == 0o700 and _mode(x) == 0o700)


# ---- 25 -----------------------------------------------------------------------------------


@test
def test_f25_session_ids_are_validated(ctx: Ctx):
    for bad in ("../../x", "a/b", "a\\b", "", ".hidden", "x" * 129, "C:evil", "a b", "id\x00", "-flag"):
        try:
            safe_id.validate_session_id(bad)
            ok = False
        except ValueError as exc:
            ok = "invalid session id" in str(exc)
        ctx.check(f"rejected with a clear error: {bad!r}", ok)
    for good in ("0123456789abcdef0123456789abcdef", "123e4567-e89b-12d3-a456-426614174000", "agent-ab_1.2"):
        ctx.check(f"accepted: {good}", safe_id.validate_session_id(good) == good)
    home = _tmp() / ".halo"
    with _state_dir(home):
        from halo_harness.agent.log import SessionLog
        try:
            SessionLog(_tmp(), session_id="../../escape")
            raised = False
        except ValueError:
            raised = True
        ctx.check("SessionLog refuses an id with separators", raised)
        ctx.check("a normal id still works", SessionLog(_tmp(), session_id="abc-123").path.name == "abc-123.jsonl")
        from halo_harness.agent import sessions
        cwd = _tmp()
        sdir = sessions.sessions_dir(cwd)
        sdir.mkdir(parents=True)
        (sdir.parent / "outside.jsonl").write_text("{}\n", encoding="utf-8")
        got, err = sessions.resolve_resume(cwd, "../outside")
        ctx.check("--resume ../outside is not treated as an exact id", got is None and err)


@test
def test_f25_tool_use_ids_cannot_leave_the_results_dir(ctx: Ctx):
    from halo_harness.tools.mcp_tool import cap_and_spill
    from halo_harness.tools.truncate import spill_and_truncate
    for hostile in ("../../escape", "..\\..\\escape", "/abs/escape", "a/../../b", "..", "functions.Read:0"):
        root = _tmp()
        session_dir = root / "sess"
        spill_and_truncate("x" * 5000, cap=100, session_dir=session_dir, tool_use_id=hostile)
        cap_and_spill([{"type": "text", "text": "y" * 400000}], session_dir=session_dir, tool_use_id=hostile)
        files = [p for p in root.rglob("*") if p.is_file()]
        inside = (session_dir / "tool-results").resolve()
        ctx.check(f"{hostile!r}: every file stays inside tool-results/",
                  files and all(p.resolve().parent == inside for p in files))
    ctx.check("provider-style ids keep a readable stem", safe_id.safe_file_stem("functions.Read:0") == "functions.Read_0")
    ctx.check("no separator or leading dot survives",
              all("/" not in safe_id.safe_file_stem(s) and "\\" not in safe_id.safe_file_stem(s)
                  and not safe_id.safe_file_stem(s).startswith(".") for s in ("../x", "..", ".env", "a/b", "")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
