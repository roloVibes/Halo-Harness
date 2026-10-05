"""2.0.3 release fix (rolo, 2026-10-05, "what is this harness limit?"): a
session with no `--max-turns` has NO cap on model calls per turn. Before
this fix the flag defaulted to 50 and the TUI applied it to interactive
sessions, so a long task stopped mid-stream with the MAXIMUM STEPS REACHED
handoff. Claude Code only caps print mode and only when asked.

Pins: (1) with max_turns=None a tool loop of 56 model calls runs to its
natural end_turn; (2) an explicit max_turns=3 still caps with reason
max_turns; (3) a non-positive value means no cap. Each tool call differs
(a different Read offset) so the identical-call breaker, a separate guard,
never fires here.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_openai import MockUpstream, SCENARIOS, _finish
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

TOOL_ROUNDS = 55  # model calls = TOOL_ROUNDS tool-call replies + 1 final "done" = 56 > the old default of 50


def _scenario(target: Path):
    def _scn(h, body):
        messages = (body or {}).get("messages") or []
        done = sum(1 for m in messages if m.get("role") == "tool")
        if done >= TOOL_ROUNDS:
            _finish(h, [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
                        {"choices": [{"index": 0, "delta": {"content": "done"}}]},
                        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}])
            return
        _finish(h, [
            {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": [
                {"index": 0, "id": f"call_{done}", "type": "function",
                 "function": {"name": "Read", "arguments": json.dumps({"file_path": str(target), "offset": done + 1})}},
            ]}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
        ])
    return _scn


def _run(ctx: Ctx, *, max_turns):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds

    fh = build_fake_home()
    target = fh["proj"] / "lines.txt"
    target.write_text("".join(f"line {i}\n" for i in range(1, 200)), encoding="utf-8")
    mock = MockUpstream().start()
    name = "max-turns-probe"
    SCENARIOS[name] = _scenario(target)
    try:
        os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
        os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
        model = f"or:mock/{name}"
        session_ctx = SessionContext(cwd=fh["proj"], model_label=model)
        session = Session(
            cwd=fh["proj"], model_ref=parse_model_ref(model), model_profile=ModelProfile(),
            creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
            state_dir=Path(tempfile.mkdtemp(prefix="max-turns-")), model_label=model, session_context=session_ctx,
            openrouter_base_url=mock.base_url, max_turns=max_turns,
            permission_engine=PermissionEngine(mode="auto", cwd=fh["proj"]),
        )
        events_ = list(session.turn("read the file many times"))
        done = [e for e in events_ if e.kind == "turn_done"]
        reason = done[-1].data.get("reason") if done else None
        tool_results = sum(1 for n in session.log.nodes() if n.get("type") == "tool_result")
        return reason, tool_results, session.max_turns
    finally:
        SCENARIOS.pop(name, None)
        mock.stop()


@test
def test_no_max_turns_means_no_cap(ctx: Ctx):
    reason, tool_results, cap = _run(ctx, max_turns=None)
    ctx.check(f"Session.max_turns is None (no cap), got {cap!r}", cap is None)
    ctx.check(f"the loop ran all {TOOL_ROUNDS} tool rounds, got {tool_results}", tool_results == TOOL_ROUNDS)
    ctx.check(f"the turn ended naturally, not with max_turns, got {reason!r}", reason == "end_turn")


@test
def test_explicit_max_turns_still_caps(ctx: Ctx):
    reason, tool_results, cap = _run(ctx, max_turns=3)
    ctx.check(f"Session.max_turns kept at 3, got {cap!r}", cap == 3)
    ctx.check(f"the turn ended with reason max_turns, got {reason!r}", reason == "max_turns")
    ctx.check(f"well under the {TOOL_ROUNDS} rounds, got {tool_results}", tool_results < 10)


@test
def test_non_positive_max_turns_means_no_cap(ctx: Ctx):
    reason, tool_results, cap = _run(ctx, max_turns=0)
    ctx.check(f"0 means no cap, got {cap!r}", cap is None)
    ctx.check(f"ran to the natural end, got {reason!r} after {tool_results} rounds",
              reason == "end_turn" and tool_results == TOOL_ROUNDS)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
