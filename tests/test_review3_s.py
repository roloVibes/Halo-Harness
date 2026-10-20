"""tests.test_review3_s -- pins for the 3.0.1.0 review fix pass, round
S-subagents-teams (part 1): review items 50, 51 (item 49 pinned the
removed cc: route and went with it in 3.1.5.0).

  * 50  --resume <transcript.jsonl> with a file name that is not a valid
        session id imports under a stable valid id
  * 51  cron day-of-week ranges that end in 7 (Sunday) fire

Part 2 (items 54, 123, 124, 125) is tests/test_review3_s2.py; part 3
(items 52, 53) is tests/test_review3_s3.py.
"""
from __future__ import annotations

import contextlib
import datetime
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


@contextlib.contextmanager
def scoped_home():
    """A fresh BRIDGE_TEST_HOME for one test; the old values come back."""
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    home = Path(tempfile.mkdtemp(prefix="r3s-home-"))
    os.environ["BRIDGE_TEST_HOME"] = str(home)
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        yield home
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@contextlib.contextmanager
def patched(module, **attrs):
    """Shared with test_review3_s2/_s3: set module attributes for a block."""
    saved = {k: getattr(module, k) for k in attrs}
    for k, v in attrs.items():
        setattr(module, k, v)
    try:
        yield
    finally:
        for k, v in saved.items():
            setattr(module, k, v)


# ---- 50: --resume with a transcript whose name is not a valid id --------------


@test
def test_50_resume_of_an_oddly_named_transcript_imports_under_a_valid_id(ctx: Ctx):
    from halo_harness.agent import sessions
    from halo_harness.agent.log import SessionLog
    from halo_harness.safe_id import is_safe_session_id
    with scoped_home():
        cwd = Path(tempfile.mkdtemp(prefix="r3s-proj-"))
        outside = Path(tempfile.mkdtemp(prefix="r3s-tx-"))
        src = outside / "My Session.jsonl"
        src.write_text('{"type": "user", "content": [{"type": "text", "text": "hello"}]}\n', encoding="utf-8")
        sid, err = sessions.resolve_resume(cwd, str(src))
        ctx.check(f"a valid id comes back with no error, got {(sid, err)}", err is None and is_safe_session_id(sid))
        ctx.check("the history was imported under that id",
                  (sessions.sessions_dir(cwd) / f"{sid}.jsonl").read_bytes() == src.read_bytes())
        ctx.check("nothing lands under the unsafe name",
                  not (sessions.sessions_dir(cwd) / "My Session.jsonl").exists())
        sid2, _ = sessions.resolve_resume(cwd, str(src))
        ctx.check(f"a second resolve gives the same id, got {sid2}", sid2 == sid)
        ctx.check("only one copy exists", len(list(sessions.sessions_dir(cwd).glob("*.jsonl"))) == 1)
        try:
            SessionLog(cwd, session_id=sid)
            built = True
        except ValueError:
            built = False
        ctx.check("SessionLog accepts the id", built)
        safe = outside / "plain-id.jsonl"
        safe.write_text("", encoding="utf-8")
        ctx.check("a transcript with a valid name keeps its own id",
                  sessions.resolve_resume(cwd, str(safe)) == ("plain-id", None))
        (sessions.sessions_dir(cwd) / ".hidden.jsonl").write_text("", encoding="utf-8")
        latest = sessions.resolve_continue(cwd)
        ctx.check(f"--continue never picks a file whose name is not a valid id, got {latest}",
                  latest is not None and is_safe_session_id(latest))


# ---- 51: cron dow ranges ending in 7 ------------------------------------------


@test
def test_51_cron_dow_ranges_ending_in_seven_fire(ctx: Ctx):
    from halo_harness.agents_schedule import cron_next
    now = datetime.datetime(2026, 10, 13, 10, 0)   # a Tuesday
    cases = {
        "0 9 * * 5-7": (2026, 10, 16),   # Friday
        "0 9 * * 1-7": (2026, 10, 14),   # Wednesday (every day)
        "0 9 * * 6-7": (2026, 10, 17),   # Saturday
        "0 9 * * 7": (2026, 10, 18),     # Sunday
        "0 9 * * 0": (2026, 10, 18),     # Sunday
        "0 9 * * */2": (2026, 10, 15),   # Sun/Tue/Thu/Sat -> Thursday
        "0 9 * * 5,6,7": (2026, 10, 16),
    }
    for expr, ymd in cases.items():
        t0 = time.monotonic()
        got = cron_next(expr, now)
        took = time.monotonic() - t0
        ctx.check(f"{expr!r} -> {ymd}, got {got} in {took:.3f}s",
                  got == datetime.datetime(*ymd, 9, 0) and took < 0.3)
    sunday_hits = cron_next("30 8 * * 5-7", datetime.datetime(2026, 10, 17, 9, 0))
    ctx.check(f"5-7 also fires on the Sunday, got {sunday_hits}",
              sunday_hits == datetime.datetime(2026, 10, 18, 8, 30))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
