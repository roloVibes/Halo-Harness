"""tests.test_round_0c_steer_through -- Halo 2.0.7 round 0c: steers reach
running work instead of queueing behind it.

Pre-0c, a steer only applied at safe points BETWEEN tool calls: one typed
during a long Bash or a foreground sub-agent waited the whole call out
(rolo's live report: 60s+ of "thinking" with the steer invisible to the
work). This module pins the 0c contract:

  * run_streamed: a `steer_cut` Event + `on_steer_handoff` hands the
    still-live process to the caller (adopted, NOT killed); without a
    callback the signal is ignored (the pre-0c behavior); a real `abort`
    always wins the race and kills;
  * Bash: a steer queued while a foreground command runs ends that wait
    early with the command MOVED TO THE BACKGROUND (a live job, not an
    error), and the steer itself still applies at the parent's next safe
    point;
  * a foreground sub-agent batch: the parent's queued steer is FORWARDED
    into the live children (consumed by the child, never re-applied by
    the parent), falls back to the parent queue when no child can take
    it, and an unapplied forwarded steer is handed back to the parent
    when the child finishes (never silently lost);
  * run_agent_call's on_child hook (the handle the forwarding relies on).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_openai import MockUpstream, SCENARIOS, ScriptedTurns
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()


def _wait_until(fn, timeout=15.0, interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if fn():
            return True
        time.sleep(interval)
    return False


def _text_step(text: str) -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": text}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]


def _tool_call_step(name: str, arguments: dict, call_id: str = "call_1") -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"tool_calls": [
            {"index": 0, "id": call_id, "type": "function",
             "function": {"name": name, "arguments": json.dumps(arguments)}},
        ]}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
    ]


def _new_session(*, mock, model, agents=None):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds

    cwd = Path(tempfile.mkdtemp(prefix="r0c-e2e-"))
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="r0c-home-")))
    session_ctx = SessionContext(cwd=cwd, model_label=model, bare=True)
    return Session(
        cwd=cwd, model_ref=parse_model_ref(model), model_profile=ModelProfile(),
        creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
        state_dir=Path(tempfile.mkdtemp(prefix="r0c-state-")), model_label=model,
        session_context=session_ctx, openrouter_base_url=mock.base_url, max_turns=10,
        permission_engine=PermissionEngine(mode="auto", cwd=cwd),
        agents=(agents if agents is not None else {}), routes={},
    )


def _general_purpose_spec(**overrides):
    from halo_harness.config.agents_md import AgentSpec
    kwargs = dict(name="general-purpose", description="general purpose sub-agent",
                  tools=None, disallowed_tools=["Agent", "Task"], body="You are a helpful sub-agent.")
    kwargs.update(overrides)
    return AgentSpec(**kwargs)


# ---- run_streamed: the steer-cut handoff -------------------------------------


@test
def test_run_streamed_steer_cut_hands_off_without_killing(ctx: Ctx):
    from halo_harness.tools._proc import run_streamed

    steer_cut = threading.Event()
    handed = []
    t = threading.Timer(0.5, steer_cut.set)
    t.start()
    try:
        out, code, timed_out, aborted = run_streamed(
            ["bash", "-lc", "sleep 3"], cwd=".", env=dict(os.environ), timeout_s=30,
            steer_cut=steer_cut, on_steer_handoff=lambda proc, q, col: handed.append(proc),
        )
    finally:
        t.cancel()
    ctx.check(f"returned fast (aborted={aborted} code={code})", aborted and code is None and not timed_out)
    ctx.check("the process was handed off, not killed", len(handed) == 1 and handed[0].poll() is None)
    ctx.check("output so far is empty (sleep prints nothing)", out == "")
    handed[0].kill()
    handed[0].wait(timeout=5)


@test
def test_run_streamed_without_callback_steer_cut_is_ignored(ctx: Ctx):
    from halo_harness.tools._proc import run_streamed

    steer_cut = threading.Event()
    t = threading.Timer(0.3, steer_cut.set)
    t.start()
    try:
        t0 = time.monotonic()
        out, code, timed_out, aborted = run_streamed(
            ["bash", "-lc", "sleep 1"], cwd=".", env=dict(os.environ), timeout_s=30,
            steer_cut=steer_cut,
        )
        elapsed = time.monotonic() - t0
    finally:
        t.cancel()
    ctx.check("no callback -> the command ran to completion", not aborted and not timed_out and code == 0)
    ctx.check(f"it really waited the full sleep (elapsed {elapsed:.1f}s)", elapsed >= 0.95)


@test
def test_run_streamed_real_abort_wins_over_steer_cut(ctx: Ctx):
    from halo_harness.tools._proc import run_streamed

    abort = threading.Event()
    steer_cut = threading.Event()
    handed = []
    abort.set()
    steer_cut.set()
    out, code, timed_out, aborted = run_streamed(
        ["bash", "-lc", "sleep 3"], cwd=".", env=dict(os.environ), timeout_s=30,
        abort=abort, steer_cut=steer_cut,
        on_steer_handoff=lambda proc, q, col: handed.append(proc),
    )
    ctx.check("abort wins: killed, not handed off", aborted and not handed)
    ctx.check("the process is dead", code is not None or not handed)


# ---- Bash: a steer cuts the wait, adopts the command -------------------------


@test
def test_bash_cut_by_steer_moves_to_background(ctx: Ctx):
    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r0c-bash")
        session._busy.set()  # steer() only accepts while a turn runs
        try:
            tu = {"type": "tool_use", "id": "call_r0c_bash", "name": "Bash",
                  "input": {"command": "sleep 2 && echo r0c-late-output", "timeout": 30000}}
            threading.Timer(0.6, session.steer, args=("stop the sleep, use mock data",)).start()
            t0 = time.monotonic()
            evs = list(session._dispatch_tools(1, [tu]))
            elapsed = time.monotonic() - t0
        finally:
            session._busy.clear()
            session._steer_cut_event.clear()
        results = [e for e in evs if e.kind == "tool_result"]
        body = results[0].data.get("content", "") if results else ""
        ctx.check(f"the dispatch ended early ({elapsed:.1f}s < 1.8s)", elapsed < 1.8)
        ctx.check("the result says the command moved to the background", "moved to the background" in body)
        ctx.check("the result names the new shell_id", "shell_id" in body)
        ctx.check("the result is NOT an error (the command still runs)",
                  not results[0].data.get("is_error", False))
        ctx.check("the steer is still queued for the parent's safe point", session._pending_steer())
        ok = _wait_until(lambda: bool(session._pending_job_notices), timeout=8.0)
        ctx.check("the adopted job finishes and queues a notice", ok)
        if ok:
            ctx.check("the notice carries the command's real output", "r0c-late-output" in session._pending_job_notices[0])
        applied = list(session._apply_pending_steers_events(2))
        ctx.check("the steer applies at the safe point right after",
                  any(e.kind == "user_message" and "mock data" in e.data.get("text", "") for e in applied))
        ctx.check("any user node for it is kind=steer",
                  any(n.get("kind") == "steer" and "mock data" in (n.get("content") or [{}])[0].get("text", "")
                      for n in session.log.nodes() if n.get("type") == "user"))
        session.job_registry.kill_all()
    finally:
        mock.stop()


# ---- forwarding into foreground children --------------------------------------


class _StubChild:
    def __init__(self, accept=True):
        self.accept = accept
        self.received = []

    def steer(self, text):
        if self.accept:
            self.received.append(text)
            return True
        return False


@test
def test_forward_pending_steers_delivers_consumes_and_falls_back(ctx: Ctx):
    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r0c-fwd")
        session._busy.set()
        try:
            runtime = session.agent_runtime
            child_a = _StubChild(accept=True)
            child_b = _StubChild(accept=False)  # e.g. its turn already ended
            runtime.live_children["a1"] = child_a
            runtime.live_children["b1"] = child_b
            ctx.check("steer queued", session.steer("use the mock data"))

            n = session._forward_pending_steers_to_children(set())
            ctx.check(f"one text forwarded into the accepting child, got {n}", n == 1)
            ctx.check("the accepting child received the text", child_a.received == ["use the mock data"])
            ctx.check("the refusing child did not", child_b.received == [])
            ctx.check("the parent consumed it (queue empty)", not session._pending_steer())

            # A pre-existing child (background task from an earlier turn) is
            # never a target: the steer comes back to the parent queue.
            ctx.check("steer requeued", session.steer("and hurry"))
            n2 = session._forward_pending_steers_to_children({"a1"})
            ctx.check(f"no forward when the only child is pre-existing, got {n2}", n2 == 0)
            ctx.check("the refusing child was not consulted either", child_a.received == ["use the mock data"])
            ctx.check("the text fell back to the parent queue", session._pending_steer())
            session._pop_all_steers()

            # Every child refusing -> falls back too.
            ctx.check("steer queued again", session.steer("third"))
            runtime.live_children.clear()
            runtime.live_children["c1"] = _StubChild(accept=False)
            n3 = session._forward_pending_steers_to_children(set())
            ctx.check(f"refused everywhere falls back, got {n3}", n3 == 0 and session._pending_steer())
            session._pop_all_steers()
        finally:
            session._busy.clear()
    finally:
        mock.stop()


@test
def test_run_agent_call_on_child_hook_fires(ctx: Ctx):
    from halo_harness.agent.subagent import run_agent_call

    SCENARIOS["r0c-hook-child"] = ScriptedTurns([_text_step("child done")])
    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r0c-hook-child",
                               agents={"general-purpose": _general_purpose_spec()})
        captured = []

        def _grab(child):
            captured.append(child)

        _, tr = run_agent_call(runtime=session.agent_runtime, tool_id="call_r0c_hook",
                               tool_input={"prompt": "say done"}, tool_name="Agent",
                               on_event=None, on_child=_grab)
        ctx.check("the hook fired exactly once with the child Session", len(captured) == 1)
        ctx.check("the child actually ran its turn and reported back",
                  "child done" in tr.content and not tr.is_error)
        ctx.check("the child's own log carries its answer",
                  any(n.get("type") == "assistant" and "child done" in
                      "".join(b.get("text", "") for b in (n.get("content") or []) if isinstance(b, dict))
                      for n in captured[0].log.nodes()))
        ctx.check("the child is no longer registered as live",
                  not any(c is captured[0] for c in session.agent_runtime.live_children.values()))
    finally:
        mock.stop()


@test
def test_e2e_steer_reaches_foreground_child_running_bash(ctx: Ctx):
    """The full 0c story: parent dispatches a foreground sub-agent whose
    first call is a long Bash; the human steers mid-run; the steer is
    FORWARDED into the child (never left queueing behind the whole batch),
    the child applies it at its own safe point, and the parent never
    re-applies the same text."""
    SCENARIOS["r0c-parent"] = ScriptedTurns([
        _tool_call_step("Agent", {"prompt": "do the thing", "description": "run the thing",
                                  "subagent_type": "general-purpose", "model": "or:mock/r0c-child"}),
        _text_step("parent done"),
    ])
    SCENARIOS["r0c-child"] = ScriptedTurns([
        _tool_call_step("Bash", {"command": "sleep 2 && echo child-bash-done", "timeout": 30000}),
        _text_step("child finished"),
    ])
    mock = MockUpstream().start()
    try:
        session = _new_session(mock=mock, model="or:mock/r0c-parent",
                               agents={"general-purpose": _general_purpose_spec()})
        threading.Timer(0.8, session.steer, args=("actually use the mock data",)).start()
        evs = list(session.turn("run the sub-agent"))
        kinds = [(e.kind, e.data.get("text", "")) for e in evs]
        ctx.check("the parent's turn completed normally",
                  any(k == "turn_done" for k, _ in kinds))
        ctx.check("the parent saw the forward note",
                  any(k == "system_note" and "steer forwarded" in t for k, t in kinds))
        ctx.check("the steer was consumed by the child (parent queue empty)",
                  not session._pending_steer())
        parent_texts = [(n.get("kind"), (n.get("content") or [{}])[0].get("text", ""))
                        for n in session.log.nodes() if n.get("type") == "user"]
        ctx.check("the parent never logged the steer as its own user node",
                  not any("mock data" in t for _, t in parent_texts))

        # The child's session file on disk carries the applied steer.
        child_sids = [e.get("child_session_id") for e in session.agent_runtime.tasks.values()
                      if e.get("child_session_id")]
        ctx.check("a child task was registered", bool(child_sids))
        if child_sids:
            # `<parent session dir>/subagents/<child_session_id>.jsonl`
            # (agent/subagent.py's `_child_log_paths`).
            child_log = session.log.dir / session.log.session_id / "subagents" / f"{child_sids[0]}.jsonl"
            ctx.check(f"the child session file exists ({child_log.name})", child_log.exists())
            steer_nodes = []
            if child_log.exists():
                for line in child_log.read_text(encoding="utf-8").splitlines():
                    try:
                        node = json.loads(line)
                    except Exception:
                        continue
                    if node.get("type") == "user" and node.get("kind") == "steer":
                        steer_nodes.append(node)
            ctx.check("the child applied the forwarded steer at its own safe point",
                      any("mock data" in (n.get("content") or [{}])[0].get("text", "") for n in steer_nodes))
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
