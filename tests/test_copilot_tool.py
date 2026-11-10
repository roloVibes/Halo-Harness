"""tests.test_copilot_tool -- the `copilot_ask` tool (Halo 3.3.17.0 R2, tools/copilot_ask.py): registered once
Copilot is set up (and not before), in the `web` capability and the bio editor's tool names; not signed in, one
line; signed in, the answer with its citations as numbered lines, the session's conversation shared (the second call
carries the contextId), `web: false` and the files sent; the session's cost marked incomplete for `cp:work`; and in a
real session the model's call and Copilot's citations land in the transcript like any tool result. Mock servers only.

Run: python -m tests.test_copilot_tool
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.copilot_rig import CopilotRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Session:
    def __init__(self):
        from halo_harness.model import CostMeter
        self.cost_meter = CostMeter(price_in=1e-6, price_out=2e-6)


class _Runtime:
    def __init__(self):
        self.parent = _Session()


def _ctx():
    from halo_harness.tools.base import ToolContext
    return ToolContext(cwd=Path(tempfile.gettempdir()), agent_runtime=_Runtime())


@test
def test_registered_once_set_up(ctx: Ctx):
    from halo_harness.isolation.capabilities import capability_of
    from halo_harness.tools.registry import default_tools, known_tool_names
    with CopilotRig(configured=False):
        ctx.check("not set up: not in the session's tools", "copilot_ask" not in {t.name for t in default_tools()})
    with CopilotRig():
        ctx.check("set up: in the session's tools", "copilot_ask" in {t.name for t in default_tools()})
    ctx.check("always in the bio editor's tool names, in the web capability", "copilot_ask" in known_tool_names()
              and capability_of("copilot_ask") == "web")


@test
def test_not_signed_in_is_one_line(ctx: Ctx):
    from halo_harness.tools.copilot_ask import CopilotAskTool
    with CopilotRig():
        got = CopilotAskTool().run({"prompt": "who owns the budget"}, _ctx())
        ctx.check(f"one line with the next step, got {got.content!r}", got.is_error
                  and got.content == "Copilot: not signed in -- run `halo copilot signin`.")
        got = CopilotAskTool().run({}, _ctx())
        ctx.check("an empty prompt says so", got.is_error and "prompt" in got.content)


@test
def test_the_answer_its_citations_the_conversation_and_the_cost(ctx: Ctx):
    from halo_harness.tools.copilot_ask import CopilotAskTool
    from halo_harness.tools.registry import ToolRegistry
    with CopilotRig() as r:
        r.signin()
        tctx = _ctx()
        reg = ToolRegistry([CopilotAskTool()])
        got = reg.dispatch("copilot_ask", {"prompt": "what changed in the plan", "web": False,
                                           "files": ["https://pretend.sharepoint.com/plan.docx"]}, tctx)
        text = str(got.content)
        ctx.check(f"the answer, then the citations numbered, got {text!r}", not got.is_error
                  and text.startswith("Work IQ heard: what changed in the plan")
                  and "[1] Q3 plan.docx -- https://pretend.sharepoint.com/q3.docx" in text and "[2] Standup notes" in text)
        body = r.mock.calls("/a2a")[0][3]
        ctx.check("web off and the file sent", body["params"]["metadata"]["webSearch"] is False
                  and "plan.docx" in body["params"]["message"]["parts"][0]["text"])
        reg.dispatch("copilot_ask", {"prompt": "and the owner?"}, tctx)
        ctx.check("the session's one conversation: the second call carries the contextId",
                  r.mock.calls("/a2a")[1][3]["params"]["message"].get("contextId") == "ctx-1")
        f = tctx.agent_runtime.parent.cost_meter.cost_fields()
        ctx.check(f"the cost is incomplete for cp:work, no dollars added, got {f}", f["cost_complete"] is False
                  and f["cost_unknown"] == ["cp:work"] and f["cost_usd"] == 0.0)


@test
def test_in_a_session_the_call_and_its_citations_are_in_the_transcript(ctx: Ctx):
    from tests.helpers.fleet_rig import text_step, tool_step
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
    from halo_harness import headless

    def step(handler, body):
        msgs = (body or {}).get("messages") or []
        if msgs and isinstance(msgs[-1], dict) and msgs[-1].get("role") == "tool":
            return _finish(handler, text_step("Copilot says the plan changed [1]."))
        return _finish(handler, tool_step(("copilot_ask", {"prompt": "what changed in the plan"}, "call_cp_1")))

    SCENARIOS["copilotask"] = step
    mock = MockUpstream().start()
    saved = {k: os.environ.get(k) for k in ("OPENROUTER_API_KEY", "BRIDGE_OPENROUTER_BASE_URL")}
    try:
        with CopilotRig() as r, tempfile.TemporaryDirectory() as cwd:
            r.signin()
            os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
            os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
            build = headless.build_session(cwd=Path(cwd), model_ref_raw="or:mock/copilotask", bare=True,
                                           print_mode=True, max_turns=4, permission_mode="auto")
            s = build.session
            list(s.turn("ask copilot what changed"))
            nodes = s.log.nodes()
            uses = [b for n in nodes if n.get("type") == "assistant" for b in n.get("content") or []
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "copilot_ask"]
            results = [n for n in nodes if n.get("type") == "tool_result"]
            ctx.check(f"the call is in the transcript, got {len(uses)}", len(uses) == 1)
            got = str(results[0].get("content") if results else "")
            ctx.check(f"its answer and citations are the tool result, got {got[:160]!r}", "Work IQ heard" in got
                      and "[1] Q3 plan.docx" in got)
            f = s.cost_meter.cost_fields()
            ctx.check(f"the session's cost names cp:work, got {f}", f["cost_complete"] is False and "cp:work" in f["cost_unknown"])
    finally:
        mock.stop()
        SCENARIOS.pop("copilotask", None)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
