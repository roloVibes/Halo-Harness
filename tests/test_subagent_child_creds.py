"""tests.test_subagent_child_creds -- pass-B fix (review finding 1,
critical): a sub-agent CHILD now resolves its OWN credentials for its
model ref instead of always inheriting the PARENT's creds/openrouter_
base_url/extra_headers regardless of provider -- a local ol:/hf:local
child under an or:/oai: parent (or the reverse) used to send its whole
prompt to the PARENT's upstream with the PARENT's bearer key. Mirrors
tests/test_subagent_e2e.py's own real-Session construction pattern
(same `_new_session`-style helper, same scripted Task tool call).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_openai import MockUpstream, SCENARIOS, ScriptedTurns
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

# Test hygiene (same reasoning as test_subagent_e2e.py's own module-level
# comment): BRIDGE_TEST_HOME is process-wide, set unconditionally by
# `_new_parent_session` below for the lifetime of each test -- restored by
# `test_zzz_restore_env`, which must stay the LAST `@test` in this file.
_ORIGINAL_BRIDGE_TEST_HOME = os.environ.get("BRIDGE_TEST_HOME")


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


def _new_parent_session(*, mock, model="or:mock/parent-b1", agents=None):
    """Mirrors test_subagent_e2e.py's own `_new_session`, plus a
    DISTINCTIVE `extra_headers` (an `X-HF-Bill-To` value, the exact shape
    pass-B finding 1's own review verification used) -- carried by the
    PARENT so a mismatched-route CHILD not inheriting it is provable."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds

    cwd = Path(tempfile.mkdtemp(prefix="b1-creds-cwd-"))
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="b1-creds-home-")))
    session_ctx = SessionContext(cwd=cwd, model_label=model, bare=True)
    model_ref = parse_model_ref(model)
    session = Session(
        cwd=cwd, model_ref=model_ref, model_profile=ModelProfile(),
        creds=ProviderCreds(base_url=mock.base_url, api_key="or-parent-key"),
        state_dir=Path(tempfile.mkdtemp(prefix="b1-creds-state-")), model_label=model,
        session_context=session_ctx, openrouter_base_url=mock.base_url,
        extra_headers={"X-HF-Bill-To": "parent-org"}, max_turns=10,
        permission_engine=PermissionEngine(mode="auto", cwd=cwd),
        agents=(agents if agents is not None else {}), routes={},
    )
    session.interactive = False
    return session


def _general_purpose_spec(**overrides):
    from halo_harness.config.agents_md import AgentSpec
    kwargs = dict(name="general-purpose", description="general purpose sub-agent",
                  tools=None, disallowed_tools=["Agent", "Task"], body="You are a helpful sub-agent.")
    kwargs.update(overrides)
    return AgentSpec(**kwargs)


# ---- error case: no credentials for the child -> is_error, zero requests --

@test
def test_oai_child_with_no_key_errors_and_sends_nothing(ctx: Ctx):
    mock = MockUpstream().start()
    saved = {k: os.environ.pop(k, None) for k in ("OPENAI_API_KEY", "BRIDGE_OPENAI_BASE_URL", "HALO_OPENAI_BASE_URL")}
    try:
        SCENARIOS["b1-parent-oai-child"] = ScriptedTurns([
            _tool_call_step("Task", {"description": "delegate", "prompt": "hello",
                                      "subagent_type": "general-purpose", "model": "oai:gpt-6-sol"}),
            _text_step("the child could not run"),
        ])
        session = _new_parent_session(mock=mock, model="or:mock/b1-parent-oai-child",
                                       agents={"general-purpose": _general_purpose_spec()})
        events = list(session.turn("delegate to a sub-agent on oai:gpt-6-sol"))

        tool_results = [e.data for e in events if e.kind == "tool_result"]
        agent_result = next((r for r in tool_results if r.get("ok") is False), None)
        ctx.check(f"an error tool_result came back, got {tool_results}", agent_result is not None)
        content = (agent_result or {}).get("content") or ""
        ctx.check(f"it names the missing credential, got {content!r}",
                  "OPENAI_API_KEY" in content or "OpenAI API not configured" in content)

        # The parent's own scripted turn makes two requests (the tool-call
        # step, then its own follow-up once the error tool_result comes
        # back) -- both naming the PARENT's own model. A cross-provider
        # child that reused the parent's OpenRouter creds (the pre-fix
        # bug) would have made a THIRD request against this same mock,
        # with the OpenRouter key, naming the CHILD's oai: model instead.
        models_seen = [r["body"].get("model") for r in mock.requests]
        ctx.check(f"exactly two requests reached the mock, both the parent's own, got {models_seen}",
                  len(mock.requests) == 2 and all(m == "mock/b1-parent-oai-child" for m in models_seen))
        ctx.check(f"the child's own model id never reached the mock, got {models_seen}",
                  "gpt-6-sol" not in models_seen)
    finally:
        mock.stop()
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


# ---- success case: a mismatched-route child resolves its OWN creds -------

@test
def test_ollama_child_under_openrouter_parent_resolves_its_own_creds(ctx: Ctx):
    mock = MockUpstream().start()
    saved = {k: os.environ.pop(k, None) for k in ("OLLAMA_HOST", "OLLAMA_API_KEY")}
    try:
        parent = _new_parent_session(mock=mock, agents={"general-purpose": _general_purpose_spec()})
        from halo_harness.agent.subagent import AgentRuntime, _build_child_session
        runtime = AgentRuntime(parent=parent)
        child, _meta_path = _build_child_session(
            runtime=runtime, spec=_general_purpose_spec(), agent_id="b1-child-1",
            model_override="ol:qwen3:8b", parent_tool_use_id="tool-1",
        )
        ctx.check(f"child creds point at Ollama's own default host, got {child.creds!r}",
                  child.creds is not None and child.creds.base_url == "http://127.0.0.1:11434")
        ctx.check(f"child never carries the parent's OpenRouter key, got {child.creds.api_key!r}",
                  child.creds.api_key != "or-parent-key")
        ctx.check(f"child never carries the parent's X-HF-Bill-To header, got {child.extra_headers!r}",
                  "X-HF-Bill-To" not in (child.extra_headers or {}))
        ctx.check(f"child never carries the parent's openrouter_base_url, got {child.openrouter_base_url!r}",
                  child.openrouter_base_url != mock.base_url)
    finally:
        mock.stop()
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


@test
def test_same_route_child_reuses_the_parents_creds_unchanged(ctx: Ctx):
    """The OTHER half of finding 1's own fix: when the child's route
    really IS the parent's route (same provider/host), the child still
    shares the parent's creds/openrouter_base_url/extra_headers exactly
    as before -- never re-resolved, never dropped."""
    mock = MockUpstream().start()
    try:
        parent = _new_parent_session(mock=mock, agents={"general-purpose": _general_purpose_spec()})
        from halo_harness.agent.subagent import AgentRuntime, _build_child_session
        runtime = AgentRuntime(parent=parent)
        child, _meta_path = _build_child_session(
            runtime=runtime, spec=_general_purpose_spec(), agent_id="b1-child-2",
            model_override="or:mock/other-model", parent_tool_use_id="tool-2",
        )
        ctx.check("same-route child reuses the parent's own creds object", child.creds is parent.creds)
        ctx.check("same-route child reuses the parent's openrouter_base_url",
                  child.openrouter_base_url == parent.openrouter_base_url)
        ctx.check("same-route child still carries the parent's X-HF-Bill-To header",
                  child.extra_headers.get("X-HF-Bill-To") == "parent-org")
    finally:
        mock.stop()


@test
def test_zzz_restore_env(ctx: Ctx):
    """Not a real test -- see the module-level comment by
    `_ORIGINAL_BRIDGE_TEST_HOME`. Must stay the LAST `@test` in this file."""
    if _ORIGINAL_BRIDGE_TEST_HOME is None:
        os.environ.pop("BRIDGE_TEST_HOME", None)
    else:
        os.environ["BRIDGE_TEST_HOME"] = _ORIGINAL_BRIDGE_TEST_HOME
    ctx.check("restored", True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
