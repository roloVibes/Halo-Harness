"""tests.test_review2_round8 -- pins for the vibes/review.md fix pass,
round 8, loop scheduling (findings 49-51):

  * f49  read-only calls queued BEFORE an Agent call in one assistant
        message ran after the sub-agent (observing its edits)
  * f50  the read-only pool cut every batched Bash command off at 30 s,
        ignoring the model's own `timeout`
  * f51  text typed during a manual /compact or /clear sat in the
        leftover list until some LATER turn ended

The rest of round 8 lives in tests/test_review2_round8b.py (52-55),
round8c (56-58, 60) and round8d (61, 62, 64).
"""
from __future__ import annotations

import os
import queue
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

_SAVED_HOME = os.environ.get("BRIDGE_TEST_HOME")


def _text_chunk(text: str) -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": text}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]


def _session(fh, mock, scenario="r8-unused", **kw):
    from tests.test_agent_tool import _make_session
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    return _make_session(fh, scenario=scenario, mock=mock, **kw)


def _restore_home() -> None:
    if _SAVED_HOME is None:
        os.environ.pop("BRIDGE_TEST_HOME", None)
    else:
        os.environ["BRIDGE_TEST_HOME"] = _SAVED_HOME


# ---- f49: reads listed before an Agent call run before it ---------------------

@test
def test_f49_read_only_calls_before_an_agent_call_finish_first(ctx: Ctx):
    fh = build_fake_home()
    target = fh["proj"] / "f49.txt"
    target.write_text("state before the sub-agent\n", encoding="utf-8")
    SCENARIOS["r8-f49-child"] = lambda h, b: _finish(h, _text_chunk("child done"))
    mock = MockUpstream().start()
    try:
        session = _session(fh, mock)
        read = {"type": "tool_use", "id": "call_read", "name": "Read", "input": {"file_path": str(target)}}
        agent = {"type": "tool_use", "id": "call_agent", "name": "Agent",
                 "input": {"description": "t", "prompt": "go", "subagent_type": "general-purpose",
                           "model": "or:mock/r8-f49-child"}}
        read2 = dict(read, id="call_read2")
        # the trailing read is what used to drag the FIRST one behind the sub-agent: it flushed the
        # agent batch first, then ran both reads together afterwards
        evs = list(session._dispatch_tools(1, [read, agent, read2]))
        kinds = [(e.kind, (e.data or {}).get("id")) for e in evs]
        read_idx = kinds.index(("tool_result", "call_read"))
        start_idx = next(i for i, e in enumerate(evs) if e.kind == "subagent_start")
        ctx.check(f"the Read result is logged BEFORE the sub-agent starts ({read_idx} < {start_idx})",
                  read_idx < start_idx)
        end_idx = next(i for i, e in enumerate(evs) if e.kind == "subagent_end")
        ctx.check(f"a read listed AFTER the sub-agent still follows it ({end_idx} < "
                  f"{kinds.index(('tool_result', 'call_read2'))})", end_idx < kinds.index(("tool_result", "call_read2")))
        ctx.check("every call still got exactly one result",
                  sorted(i for k, i in kinds if k == "tool_result") == ["call_agent", "call_read", "call_read2"])
    finally:
        mock.stop()
        _restore_home()
        SCENARIOS.pop("r8-f49-child", None)


# ---- f50: the pool honours the model's own Bash timeout -----------------------

@test
def test_f50_pool_wait_follows_the_bash_timeout(ctx: Ctx):
    from halo_harness.tools import registry as reg
    ctx.check("non-Bash calls keep the 30 s cap", reg.pool_wait_s("Read", {"timeout": 900000}) == 30.0)
    ctx.check("Bash with no timeout waits the tool default (120 s) plus grace",
              reg.pool_wait_s("Bash", {"command": "ls"}) == 120.0 + reg.READ_ONLY_BASH_GRACE_S)
    ctx.check("Bash with timeout=90000 waits 90 s plus grace",
              reg.pool_wait_s("Bash", {"timeout": 90000}) == 90.0 + reg.READ_ONLY_BASH_GRACE_S)
    ctx.check("a huge timeout is clamped to the tool's 600 s maximum",
              reg.pool_wait_s("Bash", {"timeout": 10 ** 9}) == 600.0 + reg.READ_ONLY_BASH_GRACE_S)
    ctx.check("a bool/negative timeout falls back to the default",
              reg.pool_wait_s("Bash", {"timeout": True}) == reg.pool_wait_s("Bash", {"timeout": -5}))


@test
def test_f50_a_slow_bash_call_is_not_cut_at_the_pool_cap(ctx: Ctx):
    from halo_harness.tools import registry as reg
    from halo_harness.tools.base import ToolResult

    class _SlowRegistry:
        def dispatch(self, name, tool_input, tctx):
            time.sleep(0.5)
            return ToolResult(f"{name} finished")

    saved = reg.READ_ONLY_CALL_TIMEOUT_S
    reg.READ_ONLY_CALL_TIMEOUT_S = 0.15
    try:
        out = reg.run_read_only_batch(
            _SlowRegistry(), [("Read", {"file_path": "x"}), ("Bash", {"command": "ls", "timeout": 3000})],
            SimpleNamespace(abort=None))
    finally:
        reg.READ_ONLY_CALL_TIMEOUT_S = saved
    ctx.check(f"Bash with its own 3 s timeout ran to completion, got {out[1].content!r}",
              not out[1].is_error and "finished" in out[1].content)
    ctx.check(f"a plain tool still hits the (shrunken) pool cap, got {out[0].content!r}",
              out[0].is_error and "timed out" in out[0].content)


# ---- f51: text typed during /compact or /clear is resubmitted ------------------

def _drive_run(session, commands_in, expected: int) -> list:
    commands = queue.Queue()
    for c in commands_in:
        commands.put(c)
    submitted: list = []

    def _fake_turn(text, images, out):
        submitted.append(text)
        if len(submitted) >= expected:
            commands.put(None)  # the sentinel arrives AFTER the resubmitted turns, as in the real app

    session._pump_turn = _fake_turn
    if expected == 0:
        commands.put(None)
    session.run(commands, lambda ev: None)
    return submitted


@test
def test_f51_steer_typed_during_clear_becomes_the_next_turn(ctx: Ctx):
    from halo_harness.events import Command
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        session = _session(fh, mock)
        session.clear = lambda: session.steer("typed while /clear ran")
        submitted = _drive_run(session, [Command("run_clear")], 1)
        ctx.check(f"the text typed during /clear was resubmitted, got {submitted}",
                  submitted == ["typed while /clear ran"])
        ctx.check("nothing is left stashed", session._leftover_steer_texts == [])
    finally:
        mock.stop()
        _restore_home()


@test
def test_f51_steer_typed_during_compact_is_resubmitted_in_order(ctx: Ctx):
    from halo_harness.events import Command
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        session = _session(fh, mock)

        def _fake_compaction(turn_no, trigger=None, custom_instructions=None):
            session.steer("first typed")
            session.steer("second typed")
            return True
            yield  # pragma: no cover -- makes this a generator

        session._run_compaction = _fake_compaction
        submitted = _drive_run(session, [Command("run_compact", {})], 2)
        ctx.check(f"both texts come back, in arrival order, got {submitted}",
                  submitted == ["first typed", "second typed"])
    finally:
        mock.stop()
        _restore_home()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
