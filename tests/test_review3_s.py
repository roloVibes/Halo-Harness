"""tests.test_review3_s -- pins for the 3.0.1.0 review fix pass, round
S-subagents-teams (part 1): review items 49, 50, 51.

  * 49  a cc: turn under a Stop hook that keeps blocking drains every
        continuation it sends, and no stdout reader outlives turn_done
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
import queue
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

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
    saved = {k: getattr(module, k) for k in attrs}
    for k, v in attrs.items():
        setattr(module, k, v)
    try:
        yield
    finally:
        for k, v in saved.items():
            setattr(module, k, v)


# ---- 49: Stop-hook continuation cap on the cc: route --------------------------


class _FakeClaude:
    """Stands in for ClaudeCodeProcess: every line sent is echoed (as
    `--replay-user-messages` does) and answered by one `result`, after a
    short delay so a reader left running past turn_done would show."""

    def __init__(self, delay: float = 0.05):
        self.q: "queue.Queue" = queue.Queue()
        self.delay = delay
        self.sent: list = []
        self.results_read = 0

    def _answer(self, text: str) -> None:
        def go():
            time.sleep(self.delay)
            self.q.put({"type": "user", "isReplay": True,
                        "message": {"content": [{"type": "text", "text": text}]}})
            self.q.put({"type": "result", "subtype": "success"})
        threading.Thread(target=go, daemon=True).start()

    def send_user_line(self, text):
        self.sent.append(text)
        self._answer(text)

    def send_user_blocks(self, blocks):
        self.sent.append("<turn>")
        self._answer("turn")

    def read_event(self):
        obj = self.q.get(timeout=10)
        if obj.get("type") == "result":
            self.results_read += 1
        return obj

    def interrupt(self):
        pass

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass

    def stderr_tail(self):
        return ""


class _Log:
    def __init__(self):
        self._nodes: list = []

    def nodes(self):
        return list(self._nodes)

    def append_user(self, content, kind=None):
        self._nodes.append({"type": "user", "content": content, "kind": kind})

    def append_tool_result(self, **_kw):
        pass


@test
def test_49_stop_hook_cap_never_sends_a_continuation_it_does_not_drain(ctx: Ctx):
    from halo_harness.agent import cc_runtime
    proc = _FakeClaude()
    state = cc_runtime.CcState(process=proc, bridge=None, cc_session_id="s")
    calls = []

    def run_hook_stop(event, **_kw):
        calls.append(event)
        return SimpleNamespace(blocked=True, block_reason="keep going", system_messages=[])

    hooks = SimpleNamespace(has_hooks=lambda ev: ev == "Stop", stop_block_count=9)
    session = SimpleNamespace(abort=threading.Event(), log=_Log(), hook_runner=hooks,
                              _run_hook_stop=run_hook_stop,
                              _apply_pending_job_notices=lambda t: iter(()),
                              _apply_pending_agent_notices=lambda t: iter(()))
    with patched(cc_runtime, ensure_cc_state=lambda s: state, _events_for_stdout_obj=lambda *a: [],
                 _confirm_session_id=lambda *a: None):
        evs = list(cc_runtime.turn_body_cc(session, 7, "hi"))
        at_done = proc.results_read
        alive = [t.name for t in threading.enumerate() if t.name.startswith("cc-reader-7") and t.is_alive()]
        time.sleep(proc.delay * 6)
    cap = cc_runtime._MAX_STOP_CONTINUATIONS
    continuations = [s for s in proc.sent if s == "keep going"]
    ctx.check(f"the turn ends with turn_done, got {evs[-1].kind}", evs[-1].kind == "turn_done")
    ctx.check(f"exactly the cap's continuations go out, got {len(continuations)}", len(continuations) == cap)
    ctx.check(f"every sent line's result was read inside the turn ({at_done} of {len(proc.sent)})",
              at_done == len(proc.sent))
    ctx.check(f"nothing is read after turn_done, got {proc.results_read} vs {at_done}", proc.results_read == at_done)
    ctx.check(f"no reader thread outlives the turn, got {alive}", not alive)
    ctx.check("the cap is said in a notification",
              any(e.kind == "notification" and "consecutive" in str(e.data) for e in evs))
    ctx.check("the hook runner's own block count is reset", hooks.stop_block_count == 0)
    ctx.check(f"the Stop hook ran once per reply, got {len(calls)}", len(calls) == cap + 1)


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
