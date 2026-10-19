"""tests.test_review3_l2 -- pins for the 3.0.2.0 review fix pass, round L
(agent loop), part 2:

  * item 46   read-only MCP tools (and Grep) were cut at a flat 30 s in the
              read-only pool, ignoring their own timeout
  * item 121  the compactionModel override billed at the main model's price
  * item 122  the --max-turns wrap-up vanished when it overflowed
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish, send_json_response
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.test_review3_l import _restore_env, _session, _text_chunks, _tool_chunks

ensure_default_provider_credentials()

test, TESTS = new_registry()


# ---- item 46 ------------------------------------------------------------------

class _SlowManager:
    def __init__(self, timeout_ms) -> None:
        self.handles = {"db": SimpleNamespace(config=SimpleNamespace(timeout_ms=timeout_ms))}

    def call(self, server, tool, arguments, abort=None):
        time.sleep(0.5)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="rows")], structured_content=None,
                               is_error=False)


def _mcp_tool(manager):
    from halo_harness.tools.mcp_tool import McpTool
    sdk = SimpleNamespace(name="query", description="run a query", input_schema={"type": "object", "properties": {}},
                          annotations=SimpleNamespace(read_only_hint=True, destructive_hint=False), meta=None)
    return McpTool("db", sdk, manager)


@test
def test_item46_a_read_only_mcp_call_waits_out_its_own_timeout(ctx: Ctx):
    from halo_harness.tools import registry as reg
    from halo_harness.tools.base import Tool, ToolResult

    class _SlowPlain(Tool):
        name = "SlowPlain"
        is_read_only = True

        def run(self, input, tctx):
            time.sleep(0.5)
            return ToolResult("plain finished")

    tool = _mcp_tool(_SlowManager(3000))
    registry = reg.ToolRegistry(tools=[tool, _SlowPlain()])
    saved = reg.READ_ONLY_CALL_TIMEOUT_S
    reg.READ_ONLY_CALL_TIMEOUT_S = 0.15
    try:
        out = reg.run_read_only_batch(registry, [("SlowPlain", {}), (tool.name, {})], SimpleNamespace(abort=None))
    finally:
        reg.READ_ONLY_CALL_TIMEOUT_S = saved
    ctx.check(f"the MCP call with its own 3 s timeout ran to completion, got {out[1].content!r}",
              not out[1].is_error and "rows" in str(out[1].content))
    ctx.check(f"a tool with no limit of its own still hits the (shrunken) cap, got {out[0].content!r}",
              out[0].is_error and "timed out" in out[0].content)

    saved_env = os.environ.get("MCP_TOOL_TIMEOUT")
    os.environ["MCP_TOOL_TIMEOUT"] = "45000"
    try:
        wait = reg.pool_wait_s(tool.name, {}, _mcp_tool(_SlowManager(None)))
    finally:
        if saved_env is None:
            os.environ.pop("MCP_TOOL_TIMEOUT", None)
        else:
            os.environ["MCP_TOOL_TIMEOUT"] = saved_env
    ctx.check(f"MCP_TOOL_TIMEOUT=45000 lets a pooled call run past 30 s, got {wait}",
              wait == 45.0 + reg.READ_ONLY_BASH_GRACE_S)
    ctx.check("Grep waits out ripgrep's own limit",
              reg.pool_wait_s("Grep", {}, reg.ToolRegistry().get("Grep")) > reg.READ_ONLY_CALL_TIMEOUT_S)
    ctx.check("Read keeps the 30 s floor", reg.pool_wait_s("Read", {}, reg.ToolRegistry().get("Read")) == 30.0)


# ---- item 121 -----------------------------------------------------------------

@test
def test_item121_the_summary_call_is_billed_at_the_compaction_models_rates(ctx: Ctx):
    from halo_harness.agent import loop as loop_mod
    from halo_harness.agent.compact import CompactionKnobs
    from halo_harness.model import ModelProfile
    fh = build_fake_home()
    mock = MockUpstream().start()
    real_resolve = loop_mod.resolve_model_profile
    try:
        session = _session(fh, mock, "or:mock/r3l-main")
        meter = session.cost_meter
        meter.price_in, meter.price_out = 15e-6, 75e-6
        session._compaction_knobs = CompactionKnobs(compaction_model="or:mock/r3l-cheap")
        loop_mod.resolve_model_profile = lambda ref, *a, **kw: ModelProfile(price_in=3e-7, price_out=1e-6)
        saved = session._compaction_model_override()
        ctx.check("the override took effect", saved is not None and session.model_ref.raw == "or:mock/r3l-cheap")
        before = meter.total_usd
        meter.add_usage("openrouter", {"input_tokens": 100_000, "output_tokens": 1_000})
        billed = meter.total_usd - before
        ctx.check(f"billed at the compaction model's rates (~$0.031), got ${billed:.4f}", abs(billed - 0.031) < 1e-9)
        session._restore_compaction_model(saved)
        ctx.check(f"the main model's rates are back, got {meter.price_in}/{meter.price_out}",
                  meter.price_in == 15e-6 and meter.price_out == 75e-6)
        ctx.check("and the main model itself", session.model_ref.raw == "or:mock/r3l-main")
    finally:
        loop_mod.resolve_model_profile = real_resolve
        mock.stop()
        _restore_env()


# ---- item 122 -----------------------------------------------------------------

def _scn_wrap(h, body):
    from tests.test_compaction_integration import _GOOD_SUMMARY, _OVERFLOW_400
    if (body or {}).get("tool_choice") == "none":
        _scn_wrap.wrap_bodies.append(body)
        if len(_scn_wrap.wrap_bodies) == 1:
            send_json_response(h, 400, _OVERFLOW_400)
        else:
            _finish(h, _text_chunks("WRAPPED UP"))
        return
    _scn_wrap.other += 1
    if _scn_wrap.other == 1:
        _finish(h, _tool_chunks("t_glob", "Glob", {"pattern": "*.nothing-matches"}))
    elif _scn_wrap.summary_fails:
        send_json_response(h, 400, _OVERFLOW_400)
    else:
        _finish(h, _text_chunks(_GOOD_SUMMARY))


SCENARIOS["r3l-wrap"] = _scn_wrap


def _run_wrap(fh, mock, *, summary_fails: bool, history: int) -> list:
    _scn_wrap.wrap_bodies, _scn_wrap.other, _scn_wrap.summary_fails = [], 0, summary_fails
    session = _session(fh, mock, "or:mock/r3l-wrap")
    session.max_turns = 1
    filler = "y" * 800
    for i in range(history):
        session.log.append_user([{"type": "text", "text": f"older question {i} {filler}"}])
        session.log.append_assistant(content=[{"type": "text", "text": f"older answer {i} {filler}"}],
                                     stop_reason="end_turn")
    return list(session.turn("keep going"))


@test
def test_item122_an_overflowing_wrap_up_compacts_and_retries(ctx: Ctx):
    from halo_harness.providers.errors import CONTEXT_WINDOW_EXCEEDED
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        evs = _run_wrap(fh, mock, summary_fails=False, history=150)
        kinds = [e.kind for e in evs]
        ctx.check("a compaction ran", any(e.kind == "compaction" and e.data.get("phase") == "done" for e in evs))
        text = "".join(e.data.get("text", "") for e in evs if e.kind == "text_delta")
        ctx.check(f"the retried wrap-up reply arrived, got {text[-40:]!r}", "WRAPPED UP" in text)
        retry = str(_scn_wrap.wrap_bodies[-1]) if len(_scn_wrap.wrap_bodies) == 2 else ""
        ctx.check("the retry still carries the wrap-up instruction", "MAXIMUM STEPS REACHED" in retry)
        done = [e for e in evs if e.kind == "turn_done"]
        ctx.check(f"the turn ends as max_turns, got {[d.data for d in done]}",
                  done and done[-1].data.get("reason") == "max_turns" and kinds[-1] == "turn_done")

        evs = _run_wrap(fh, mock, summary_fails=True, history=2)
        errors = [e for e in evs if e.kind == "error"]
        ctx.check(f"a failed compaction reports a context-window error, got {[e.data for e in errors]}",
                  any(e.data.get("category") == CONTEXT_WINDOW_EXCEEDED for e in errors))
        done = [e for e in evs if e.kind == "turn_done"]
        ctx.check(f"and the turn ends as an error, got {[d.data for d in done]}",
                  done and done[-1].data.get("reason") == "error")
        idx_err = max(i for i, e in enumerate(evs) if e.kind == "error") if errors else -1
        ctx.check("the error comes before turn_done", 0 <= idx_err < len(evs) - 1)
    finally:
        mock.stop()
        _restore_env()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
