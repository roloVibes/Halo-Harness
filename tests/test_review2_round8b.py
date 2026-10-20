"""tests.test_review2_round8b -- pins for the vibes/review.md fix pass,
round 8, continued (findings 52-54; f55 pinned the cc: route removed in
3.1.5.0):

  * f52  the forced tool_choice=required retry fed the overflow sentinel
        to `_account_usage` (AttributeError) instead of compacting
  * f53  Esc started the queued read-only batch / queued sub-agents, and
        a parked permission slot outlived the interrupt
  * f54  the concurrent-resume guard was check-then-set without a lock
"""
from __future__ import annotations

import dataclasses
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_openai import MockUpstream
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.test_review2_round8 import _restore_home, _session

ensure_default_provider_credentials()

test, TESTS = new_registry()


# ---- f52: the forced-retry overflow compacts instead of raising ---------------

@test
def test_f52_required_retry_overflow_compacts_instead_of_raising(ctx: Ctx):
    from halo_harness.agent import loop as L
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        session = _session(fh, mock)
        session.provider_profile = dataclasses.replace(
            session.provider_profile, tool_choice_required_supported=True, tool_leak_patterns=())
        body = {"tools": [{"type": "function"}], "messages": []}

        def _result(text):
            return L._StepResult(assistant_blocks=[{"type": "text", "text": text}], stop_reason="end_turn",
                                 usage={}, reasoning=None, body=body)

        calls: list = []

        def _fake_step(turn_no, tool_choice=None, overflow_handled=False, no_tools=False):
            calls.append((tool_choice, overflow_handled))
            if tool_choice == "required" and not overflow_handled:
                return L._OVERFLOW_NEEDS_COMPACTION
            return _result('<tool_call>{"name": "Read", "argum' if tool_choice is None else "settled answer")
            yield  # pragma: no cover -- makes this a generator

        compactions: list = []

        def _fake_compaction(turn_no, trigger=None, custom_instructions=None):
            compactions.append(trigger)
            return True
            yield  # pragma: no cover

        session._step = _fake_step
        session._run_compaction = _fake_compaction
        errors = [e for e in session.turn("go") if e.kind == "error"]
        ctx.check(f"the turn finished without raising or erroring, got {errors}", errors == [])
        ctx.check(f"it compacted once, then retried the forced call once more, got {calls} / {compactions}",
                  compactions == ["overflow"]
                  and calls == [(None, False), ("required", False), ("required", True)])
    finally:
        mock.stop()
        _restore_home()


# ---- f53: Esc starts nothing that was only queued -----------------------------

def _tu(call_id, name, tool_input):
    return {"type": "tool_use", "id": call_id, "name": name, "input": tool_input}


@test
def test_f53_esc_does_not_run_the_queued_read_only_batch(ctx: Ctx):
    fh = build_fake_home()
    target = fh["proj"] / "f53.txt"
    target.write_text("must not be read\n", encoding="utf-8")
    mock = MockUpstream().start()
    try:
        session = _session(fh, mock)
        dispatched: list = []
        real_dispatch = session.tool_registry.dispatch
        session.tool_registry.dispatch = lambda name, inp, c: (dispatched.append(name), real_dispatch(name, inp, c))[1]
        real_resolve = session._resolve_tool_call

        def _resolve(tu, outcome, flags):
            item = real_resolve(tu, outcome, flags)
            if item["tool_id"] == "call_2":
                session.abort.set()  # Esc lands while the second call is being resolved
            return item

        session._resolve_tool_call = _resolve
        evs = list(session._dispatch_tools(1, [_tu("call_1", "Read", {"file_path": str(target)}),
                                               _tu("call_2", "Read", {"file_path": str(target)})]))
        results = {e.data["id"]: e.data for e in evs if e.kind == "tool_result"}
        ctx.check(f"both calls got exactly one result, got {sorted(results)}", sorted(results) == ["call_1", "call_2"])
        ctx.check(f"the queued Read never ran, dispatched={dispatched}", dispatched == [])
        ctx.check("both results say interrupted",
                  all(not r["ok"] and "interrupted" in r["summary"].lower() for r in results.values()))
    finally:
        mock.stop()
        _restore_home()


@test
def test_f53_esc_does_not_start_a_queued_sub_agent_and_frees_the_permission_slot(ctx: Ctx):
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        session = _session(fh, mock)
        session.interactive = True
        session.permission_engine.mode = "default"  # a Write now asks (auto mode would just allow it)
        real_resolve = session._resolve_tool_call

        def _resolve(tu, outcome, flags):
            item = real_resolve(tu, outcome, flags)
            if item.get("pending_ask"):
                session.abort.set()  # Esc between "slot parked" and "wait for the answer"
            return item

        session._resolve_tool_call = _resolve
        agent = _tu("call_agent", "Agent", {"description": "t", "prompt": "go", "subagent_type": "general-purpose"})
        write = _tu("call_write", "Write", {"file_path": str(fh["proj"] / "w.txt"), "content": "x"})
        evs = list(session._dispatch_tools(1, [agent, write]))
        ctx.check("no sub-agent was started", not any(e.kind == "subagent_start" for e in evs))
        ctx.check(f"the parked permission slot was released, got {list(session._permission_waiters)}",
                  session._permission_waiters == {})
        done = sorted(e.data["id"] for e in evs if e.kind == "tool_result")
        ctx.check(f"every call still got its result, got {done}", done == ["call_agent", "call_write"])
    finally:
        mock.stop()
        _restore_home()


# ---- f54: two resumes of one task_id cannot both run --------------------------

@test
def test_f54_concurrent_resume_of_one_task_runs_once(ctx: Ctx):
    from halo_harness.agent import subagent as S
    from halo_harness.tools.base import ToolResult
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        session = _session(fh, mock)
        rt = session.agent_runtime
        rt.tasks["t1"] = {"child_session_id": "agent-x", "spec_name": "general-purpose", "cwd": str(fh["proj"]),
                          "running_in_process": False}
        entered: list = []
        gate = threading.Event()

        def _slow_inner(runtime, task_id, tool_input, tool_id, on_event=None):
            entered.append(tool_id)
            gate.wait(2.0)
            return [], ToolResult("resumed ok")

        real_inner = S._resume_task_claimed
        S._resume_task_claimed = _slow_inner
        outs: list = []
        try:
            threads = [threading.Thread(target=lambda i=i: outs.append(S._resume_task(rt, "t1", {}, f"c{i}")))
                       for i in range(2)]
            for t in threads:
                t.start()
            time.sleep(0.4)
            ctx.check(f"only one resume got in, got {entered}", len(entered) == 1)
            gate.set()
            for t in threads:
                t.join(3.0)
        finally:
            S._resume_task_claimed = real_inner
        errs = [o[1] for o in outs if o[1].is_error]
        ctx.check(f"the other got the 'still running' error, got {[e.content[:60] for e in errs]}",
                  len(errs) == 1 and "still running" in errs[0].content)
        ctx.check("the guard is released afterwards", rt.tasks["t1"]["running_in_process"] is False)
        # an early-return inside the real body (agent type gone) must release it too
        rt.tasks["t2"] = {"child_session_id": "agent-y", "spec_name": "no-such-type", "cwd": "",
                          "running_in_process": False}
        _, res = S._resume_task(rt, "t2", {}, "c9")
        ctx.check("an early error return leaves the guard False", res.is_error and rt.tasks["t2"]["running_in_process"] is False)
    finally:
        mock.stop()
        _restore_home()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
