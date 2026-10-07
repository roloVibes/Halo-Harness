"""tests.test_acceptance_round -- Halo 2.0.6 round 3: acceptance-gated
sub-agent returns.

The v2.0.4 model review's item 2, the part 2.0.5 round 5 left open: when
a sub-agent returns, the result is checked against the bio's own
`acceptance` criteria; a failure gets ONE retry (the critique as a second
user turn on the SAME child -- it keeps its context); a second failure
escalates with the failure MARKED: the hand-back carries the note, the
cost rollup's `ok` counts it failed (round 2's cost-per-accepted), and
the task meta records the verdict. A run that errored never retries on
acceptance; a bio with no acceptance block is the byte-for-byte old path.

Driven end-to-end against the mock upstream exactly like the sub-agent
e2e suite: a scripted parent calls Task, a custom child scenario answers
by inspecting its own last user message (so the retry turn can be told
apart from the first).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.mock_openai import MockUpstream, SCENARIOS, ScriptedTurns, _finish
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_subagent_e2e import _drain as _e2e_drain
from tests.test_subagent_e2e import (_general_purpose_spec, _new_session,
                                     _text_step, _tool_call_step)

test, TESTS = new_registry()

_LAST_NODES: list = [[]]


def _drain(session, prompt):
    """The e2e drain, plus a capture of the parent session's own log nodes
    (the rollup's `ok`/`bio` land there -- the round's core assertion)."""
    events = _e2e_drain(session, prompt)
    try:
        _LAST_NODES[0] = list(session.log.nodes())
    except Exception:
        _LAST_NODES[0] = []
    return events


def _write_acceptance_bio(cwd: Path, name: str, expect: str, critique=None) -> None:
    # project_agents_dir(cwd) is <cwd>/.halo/agents -- the bio search path's
    # nearest-wins project scope
    d = cwd / ".halo" / "agents"
    d.mkdir(parents=True, exist_ok=True)
    body = {"name": name, "description": f"bio for {name}",
            "acceptance": {"expect": expect}}
    if critique:
        body["acceptance"]["critique"] = critique
    (d / f"{name}.yaml").write_text(json.dumps(body), encoding="utf-8")


def _child_scenario(first_text: str, retry_text: "str | None"):
    """Answers `first_text`; when the last user message is the critique
    (any message mentioning 'rejected'), answers `retry_text` instead."""
    def _scn(h, body):
        messages = (body or {}).get("messages") or []
        last_user = next((m.get("content", "") for m in reversed(messages)
                          if isinstance(m, dict) and m.get("role") == "user"), "")
        last_user = last_user if isinstance(last_user, str) else json.dumps(last_user)
        if retry_text is not None and "rejected" in last_user.lower():
            _finish(h, [
                {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
                {"choices": [{"index": 0, "delta": {"content": retry_text}}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
            ])
            return
        _finish(h, [
            {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"content": first_text}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ])
    return _scn


def _run_one(mock, parent_scn, child_scn, *, cwd):
    SCENARIOS["acc-parent"] = parent_scn
    SCENARIOS["acc-child"] = child_scn
    session = _new_session(mock=mock, model="or:mock/acc-parent", cwd=cwd,
                           agents={"general-purpose": _general_purpose_spec()})
    return _drain(session, "delegate it")


def _rollup_nodes():
    return [n for n in _LAST_NODES[0] if n.get("type") == "usage" and n.get("agent_id")]


@test
def test_a_failed_acceptance_retries_once_then_passes(ctx: Ctx):
    mock = MockUpstream().start()
    cwd = Path(tempfile.mkdtemp(prefix="acc-pass-"))
    _write_acceptance_bio(cwd, "general-purpose", "FINAL TOKEN")
    try:
        parent = ScriptedTurns([
            _tool_call_step("Task", {"description": "work", "prompt": "do the work",
                                     "subagent_type": "general-purpose", "model": "or:mock/acc-child"}),
            _text_step("parent saw the accepted result"),
        ])
        child = _child_scenario("not the right answer", "here is the corrected FINAL TOKEN result")
        events = _run_one(mock, parent, child, cwd=cwd)

        tool_results = [e.data for e in events if e.kind == "tool_result"]
        agent_result = next(r for r in tool_results if "task_id" in (r.get("content") or ""))
        content = agent_result["content"]
        ctx.check(f"the RETRY's answer is what comes back, got {content!r}", "FINAL TOKEN" in content)
        ctx.check(f"no failure mark on a passing retry, got {content!r}",
                  "[acceptance gate:" not in content)
        nodes = _rollup_nodes()
        ctx.check(f"one rollup node, got {len(nodes)}", len(nodes) == 1)
        if nodes:
            ctx.check(f"the rollup is ok=True (accepted), got {nodes[0].get('ok')}",
                      nodes[0].get("ok") is True)
            ctx.check(f"the rollup carries the bio, got {nodes[0].get('bio')!r}",
                      nodes[0].get("bio") == "general-purpose")
    finally:
        mock.stop()
        SCENARIOS.pop("acc-parent", None)
        SCENARIOS.pop("acc-child", None)


@test
def test_a_double_failure_is_returned_marked(ctx: Ctx):
    mock = MockUpstream().start()
    cwd = Path(tempfile.mkdtemp(prefix="acc-fail-"))
    _write_acceptance_bio(cwd, "general-purpose", "FINAL TOKEN",
                          critique="REJECTED: your answer must contain FINAL TOKEN.")
    try:
        parent = ScriptedTurns([
            _tool_call_step("Task", {"description": "work", "prompt": "do the work",
                                     "subagent_type": "general-purpose", "model": "or:mock/acc-child"}),
            _text_step("parent saw the marked result"),
        ])
        child = _child_scenario("still wrong", None)  # never satisfies
        events = _run_one(mock, parent, child, cwd=cwd)

        tool_results = [e.data for e in events if e.kind == "tool_result"]
        agent_result = next(r for r in tool_results if "task_id" in (r.get("content") or ""))
        content = agent_result["content"]
        ctx.check(f"the double failure is MARKED in the hand-back, got {content[:120]!r}",
                  "[acceptance gate:" in content and "2 attempts" in content)
        nodes = _rollup_nodes()
        ctx.check(f"one rollup node, got {len(nodes)}", len(nodes) == 1)
        if nodes:
            ctx.check(f"the rollup counts the task FAILED (ok=False), got {nodes[0].get('ok')}",
                      nodes[0].get("ok") is False)
        # exactly one retry happened: the child answered twice
        # the wire body carries the BARE model name (no "or:" route prefix)
        child_posts = [r for r in mock.requests
                       if (r.get("body") or {}).get("model") == "mock/acc-child"]
        ctx.check(f"first attempt + exactly one retry = 2 child turns, got {len(child_posts)}",
                  len(child_posts) == 2)
    finally:
        mock.stop()
        SCENARIOS.pop("acc-parent", None)
        SCENARIOS.pop("acc-child", None)


@test
def test_no_acceptance_block_is_the_old_path(ctx: Ctx):
    mock = MockUpstream().start()
    cwd = Path(tempfile.mkdtemp(prefix="acc-none-"))
    # NO bio file at all: no gate, no retry, byte-for-byte the old flow
    try:
        parent = ScriptedTurns([
            _tool_call_step("Task", {"description": "work", "prompt": "do the work",
                                     "subagent_type": "general-purpose", "model": "or:mock/acc-child"}),
            _text_step("parent saw the result"),
        ])
        child = _child_scenario("a plain answer", "SHOULD NEVER BE SENT")
        events = _run_one(mock, parent, child, cwd=cwd)

        # the wire body carries the BARE model name (no "or:" route prefix)
        child_posts = [r for r in mock.requests
                       if (r.get("body") or {}).get("model") == "mock/acc-child"]
        ctx.check(f"no criteria -> exactly one child turn, got {len(child_posts)}",
                  len(child_posts) == 1)
        tool_results = [e.data for e in events if e.kind == "tool_result"]
        agent_result = next(r for r in tool_results if "task_id" in (r.get("content") or ""))
        ctx.check(f"the plain answer passes through unmarked, got {agent_result['content'][:80]!r}",
                  "a plain answer" in agent_result["content"]
                  and "[acceptance gate:" not in agent_result["content"])
        nodes = _rollup_nodes()
        if nodes:
            ctx.check("no criteria -> accepted (ok=True), same as the old path",
                      nodes[0].get("ok") is True)
    finally:
        mock.stop()
        SCENARIOS.pop("acc-parent", None)
        SCENARIOS.pop("acc-child", None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
