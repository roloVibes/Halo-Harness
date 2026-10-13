"""tests.test_review3_l -- pins for the 3.0.2.0 review fix pass, round L
(agent loop), part 1:

  * item 8    a schedule/trigger job fired from a live session ran with an
              environment holding only the fire marker
  * item 45   EnterPlanMode's own result was overwritten by a second run
              through the read-only pool
  * item 119  -p ExitPlanMode never auto-approved after a model-initiated
              EnterPlanMode under bypassPermissions/acceptEdits
  * item 47   a headless team escalation with ask: true re-notified at
              every safe point
  * item 48   the continuous canary counted inline base64 image data

Items 46, 120, 121 and 122 live in tests/test_review3_l2.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

_SAVED = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_OPENROUTER_BASE_URL")}


def _restore_env() -> None:
    for k, v in _SAVED.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _text_chunks(text: str) -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": text}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]


def _tool_chunks(tool_id: str, name: str, tool_input: dict) -> list:
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"tool_calls": [
            {"index": 0, "id": tool_id, "type": "function",
             "function": {"name": name, "arguments": json.dumps(tool_input)}}]}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
    ]


def _session(fh, mock, model: str, *, mode: str = "auto"):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds
    import tempfile
    os.environ["BRIDGE_TEST_HOME"] = str(fh["home"])
    os.environ["BRIDGE_OPENROUTER_BASE_URL"] = mock.base_url
    return Session(
        cwd=fh["proj"], model_ref=parse_model_ref(model),
        model_profile=ModelProfile(context_tokens=200_000, max_output_tokens=8192),
        creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
        state_dir=Path(tempfile.mkdtemp(prefix="r3l-")), model_label=model,
        session_context=SessionContext(cwd=fh["proj"], model_label=model),
        openrouter_base_url=mock.base_url, max_turns=10,
        permission_engine=PermissionEngine(mode=mode, cwd=fh["proj"]),
    )


def _result_text(node) -> str:
    content = node.get("content")
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content or [] if isinstance(b, dict))


# ---- item 8 -------------------------------------------------------------------

@test
def test_item8_a_fired_job_inherits_the_session_environment(ctx: Ctx):
    from halo_harness import agents_schedule
    seen = {}

    class _Record:
        job_id = "j1"

    class _Registry:
        def start_background(self, command, **kw):
            seen.update(kw)
            return _Record(), None

    os.environ["R3L_PARENT_ONLY"] = "parent-value"
    try:
        session = type("S", (), {"job_registry": _Registry(), "cwd": ".",
                                 "tool_env": {"R3L_FROM_SETTINGS": "settings-value"}})()
        agents_schedule._default_fire(session, {"name": "n", "prompt": "p", "team": "t"})
        env = seen.get("env") or {}
        ctx.check("the fire marker is still there", env.get("HALO_SCHEDULED_FIRE") == "1")
        ctx.check("PATH reaches the fired job", env.get("PATH") == os.environ.get("PATH") and env.get("PATH"))
        home_key = "HOME" if "HOME" in os.environ else "USERPROFILE"
        ctx.check(f"{home_key} reaches the fired job", env.get(home_key) == os.environ.get(home_key))
        ctx.check("a variable exported in the parent reaches it", env.get("R3L_PARENT_ONLY") == "parent-value")
        ctx.check("the provider key the fired harness needs reaches it",
                  env.get("OPENROUTER_API_KEY") == os.environ.get("OPENROUTER_API_KEY"))
        ctx.check("the session's settings env overlay reaches it", env.get("R3L_FROM_SETTINGS") == "settings-value")

        captured = {}
        real_popen = subprocess.Popen
        subprocess.Popen = lambda argv, **kw: captured.update(kw)
        try:
            bare = type("S", (), {"cwd": ".", "tool_env": {"R3L_FROM_SETTINGS": "settings-value"}})()
            agents_schedule._default_fire(bare, {"name": "n", "prompt": "p"})
        finally:
            subprocess.Popen = real_popen
        denv = captured.get("env") or {}
        ctx.check("the detached path builds the same environment",
                  denv.get("R3L_PARENT_ONLY") == "parent-value" and denv.get("R3L_FROM_SETTINGS") == "settings-value"
                  and denv.get("HALO_SCHEDULED_FIRE") == "1")
    finally:
        os.environ.pop("R3L_PARENT_ONLY", None)


# ---- items 45 + 119 -----------------------------------------------------------

def _scn_plan(h, body):
    _scn_plan.calls += 1
    if _scn_plan.calls == 1:
        _finish(h, _tool_chunks("t_enter", "EnterPlanMode", {}))
    elif _scn_plan.calls == 2:
        _finish(h, _tool_chunks("t_exit", "ExitPlanMode", {"plan": "# Plan\n1. change X"}))
    else:
        _finish(h, _text_chunks("IMPLEMENTED"))


_scn_plan.calls = 0
SCENARIOS["r3l-plan"] = _scn_plan


@test
def test_item45_item119_plan_mode_round_trip_in_print_mode(ctx: Ctx):
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        _scn_plan.calls = 0
        session = _session(fh, mock, "or:mock/r3l-plan", mode="bypassPermissions")
        list(session.turn("refactor X"))
        results = {n.get("tool_use_id"): n for n in session.log.nodes() if n.get("type") == "tool_result"}
        enter = _result_text(results.get("t_enter") or {})
        ctx.check(f"EnterPlanMode keeps the loop's own result, got {enter[:80]!r}",
                  enter.startswith("Entered plan mode. Plan file:"))
        exit_text = _result_text(results.get("t_exit") or {})
        ctx.check(f"ExitPlanMode approves under the pre-plan bypassPermissions, got {exit_text[:80]!r}",
                  exit_text == "User approved the plan; implement it.")
        ctx.check(f"the mode in force before plan mode is back, got {session.permission_engine.mode!r}",
                  session.permission_engine.mode == "bypassPermissions")
        ctx.check(f"the model went on to implement (3 calls), got {_scn_plan.calls}", _scn_plan.calls == 3)

        _scn_plan.calls = 0
        plain = _session(fh, mock, "or:mock/r3l-plan", mode="default")
        list(plain.turn("refactor X"))
        results = {n.get("tool_use_id"): n for n in plain.log.nodes() if n.get("type") == "tool_result"}
        ctx.check("without an approving mode the plan is still the answer and the turn ends",
                  _result_text(results.get("t_exit") or {}).startswith("# Plan") and _scn_plan.calls == 2)
        ctx.check("and the session stays in plan mode", plain.permission_engine.mode == "plan")
    finally:
        mock.stop()
        _restore_env()


# ---- item 47 ------------------------------------------------------------------

class _AskTeam:
    name = "ask-team"

    def __init__(self) -> None:
        self.escalated = False

    def escalation_decision(self, *, tool_failures: bool = False, context_overflow: bool = False):
        return None if self.escalated else ("budget_exhausted", "or:mock/bigger", True)


@test
def test_item47_headless_ask_escalation_notifies_once(ctx: Ctx):
    from halo_harness.agent.loop import Session
    from tests.test_review2_round7 import _EscStub
    stub = _EscStub(_AskTeam())
    first = list(Session._maybe_team_escalate(stub, 1))
    second = list(Session._maybe_team_escalate(stub, 1))
    third = list(Session._maybe_team_escalate(stub, 2))
    notes = [e for e in first + second + third if e.kind == "notification"]
    ctx.check(f"exactly one notification across three safe points, got {len(notes)}", len(notes) == 1)
    ctx.check("it names the /model switch", "/model or:mock/bigger" in notes[0].data.get("text", "")
              if notes else False)
    ctx.check("nothing switched the model on its own", stub.set_model_calls == [])


# ---- item 48 ------------------------------------------------------------------

def _canary_notes(session, body, seen_tokens: int) -> list:
    events = list(session._maybe_continuous_canary(1, {"input_tokens": seen_tokens, "output_tokens": 5}, body))
    return [e for e in events if e.kind == "notification" and "truncation" in e.data.get("text", "")]


@test
def test_item48_canary_ignores_inline_image_data(ctx: Ctx):
    fh = build_fake_home()
    mock = MockUpstream().start()
    try:
        b64 = "QUJD" * 200_000  # ~800k characters of base64
        anthropic_shape = {"messages": [{"role": "user", "content": [
            {"type": "text", "text": "what is in this screenshot?"},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}}]}]}
        openai_shape = {"messages": [{"role": "user", "content": [
            {"type": "text", "text": "what is in this screenshot?"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}]}]}
        session = _session(fh, mock, "or:mock/r3l-canary")
        ctx.check("an Anthropic-shaped image turn raises no truncation warning",
                  _canary_notes(session, anthropic_shape, 2400) == [])
        ctx.check("an OpenAI-shaped image turn raises none either", _canary_notes(session, openai_shape, 2400) == [])
        ctx.check("the one-shot warning is still unspent", not session._canary_truncation_noted)
        text_heavy = {"messages": [{"role": "user", "content": [{"type": "text", "text": "word " * 160_000}]}]}
        ctx.check("a real under-echo of a text body still warns", len(_canary_notes(session, text_heavy, 2400)) == 1)
    finally:
        mock.stop()
        _restore_env()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
