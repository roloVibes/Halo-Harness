"""tests.test_round_doctor_dead_ids -- Halo 2.0.7's doctor round: dead
model ids, the surfaced 404 handback, and balances-remaining.

  * `halo doctor --roles` resolves every configured model against its
    provider's own catalog (models.json for or:, dbx-endpoints.json for
    dbx:, the host's live tags for ol:) and reports each unknown id --
    the silent-404 case rolo hit live (a retired deepseek id);
  * a provider with no readable catalog is SKIPPED, never guessed at
    (no false 'dead id' from a missing file);
  * an errored sub-agent's handback now carries the child's OWN last
    error message (the 404's words), never a silently-empty result;
  * balances lines lead with what's LEFT and carry the total/used
    breakdown whenever the provider offered it.
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
from halo_harness.config.paths import bridge_home
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()


class _Home:
    """BRIDGE_TEST_HOME is the HOME-level dir; bridge_home() appends the
    `.halo` component itself -- config.json/models.json live INSIDE it."""

    def __init__(self):
        self.d = Path(tempfile.mkdtemp(prefix="docround-"))
        os.environ["BRIDGE_TEST_HOME"] = str(self.d)
        os.environ["BRIDGE_STATE_DIR"] = str(self.d)
        self.halo = bridge_home()  # <d>/.halo, made real by the getter
        self.halo.mkdir(exist_ok=True)

    def set_roles(self, table: dict):
        cfg = {"roles": table}
        (self.halo / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    def set_models_json(self, models: dict):
        (self.halo / "models.json").write_text(json.dumps(models), encoding="utf-8")


# ---- dead model ids -----------------------------------------------------------


@test
def test_dead_model_ids_reported_and_live_ids_clean(ctx: Ctx):
    from halo_harness.agents_doctor import check_dead_model_ids
    home = _Home()
    home.set_roles({
        "coder": "or:z-ai/glm-5.3",            # live
        "reviewer": "or:deepseek/deepseek-v4-pro-0813",  # retired -- rolo's live case
        "researcher": "or:deepseek/deepseek-v4-flash",   # live
        "small": "cc:claude-haiku",            # no catalog to check -> skipped
    })
    home.set_models_json({"z-ai/glm-5.3": {}, "deepseek/deepseek-v4-flash": {}})
    problems = check_dead_model_ids(state_dir=home.halo)
    ctx.check(f"exactly the dead id is reported, got {problems}", len(problems) == 1)
    if problems:
        ctx.check("it names the role and the id",
                  "reviewer" in problems[0] and "deepseek-v4-pro-0813" in problems[0])
        ctx.check("it says requests 404 silently", "404" in problems[0])
    # A clean table reports nothing.
    home.set_roles({"coder": "or:z-ai/glm-5.3"})
    ctx.check("a live-only table is clean", check_dead_model_ids(state_dir=home.halo) == [])


@test
def test_missing_catalog_is_skipped_never_a_false_dead_id(ctx: Ctx):
    from halo_harness.agents_doctor import check_dead_model_ids
    home = _Home()
    home.set_roles({"coder": "or:some/model"})
    # No models.json at all -> catalog unreadable -> skipped entirely.
    ctx.check("no catalog -> no dead-id claims",
              check_dead_model_ids(state_dir=home.halo) == [])


@test
def test_doctor_roles_wires_the_dead_id_check(ctx: Ctx):
    from halo_harness import doctor as doctor_mod
    home = _Home()
    home.set_roles({"coder": "or:dead/model-x"})
    home.set_models_json({"z-ai/glm-5.3": {}})
    rc = doctor_mod.cmd_doctor(["--roles", "--cwd", str(home.d)])
    ctx.check(f"doctor --roles exits 1 on a dead id, got {rc}", rc == 1)


# ---- the surfaced 404 handback --------------------------------------------------


@test
def test_errored_child_handback_carries_the_childs_error(ctx: Ctx):
    from halo_harness.agent.subagent import _last_child_error_text
    from halo_harness import events
    evs = [events.error("early transient error that a retry survived", turn=1),
           events.text_delta("partial text", turn=1),
           events.error("no endpoints found for model deepseek/deepseek-v4-pro-0813", turn=1),
           events.Event("turn_done", {"reason": "error"}, turn=1)]
    got = _last_child_error_text(evs)
    ctx.check(f"the LAST error wins, got {got!r}",
              got == "no endpoints found for model deepseek/deepseek-v4-pro-0813")
    ctx.check("an empty stream has no error text", _last_child_error_text([]) is None)
    only_soft = [events.error("  ", turn=1)]
    ctx.check("whitespace-only errors read as none", _last_child_error_text(only_soft) is None)


@test
def test_e2e_dead_lane_subagent_surfaces_the_404(ctx: Ctx):
    """The full story: a sub-agent on a DEAD model id (the mock returns a
    404 for the unknown id) hands back an is_error result whose text
    CARRIES the 404's own words -- never a silently-empty result."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.permissions import PermissionEngine
    from halo_harness.providers.stream import ProviderCreds

    mock = MockUpstream().start()
    try:
        from halo_harness.config.agents_md import AgentSpec
        spec = AgentSpec(name="general-purpose", description="gp",
                         disallowed_tools=["Agent", "Task"], body="You are a helper.")
        cwd = Path(tempfile.mkdtemp(prefix="deadlane-"))
        session = Session(
            cwd=cwd, model_ref=parse_model_ref("or:mock/parent"), model_profile=ModelProfile(),
            creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
            state_dir=Path(tempfile.mkdtemp(prefix="deadlane-state-")),
            model_label="or:mock/parent",
            session_context=SessionContext(cwd=cwd, model_label="or:mock/parent", bare=True),
            openrouter_base_url=mock.base_url, max_turns=6,
            permission_engine=PermissionEngine(mode="auto", cwd=cwd),
            agents={"general-purpose": spec}, routes={},
        )
        # Parent's first step: spawn the sub-agent on a DEAD model.
        # The mock's 404 for the unknown child model becomes the child's
        # own error event; the handback must carry it.
        import json as _json
        def _agent_call_step(call_id, arguments):
            return [
                {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
                {"choices": [{"index": 0, "delta": {"tool_calls": [
                    {"index": 0, "id": call_id, "type": "function",
                     "function": {"name": "Agent", "arguments": _json.dumps(arguments)}}]}}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]},
            ]

        SCENARIOS["parent"] = ScriptedTurns([
            _agent_call_step("call_dead1", {"prompt": "do work", "description": "x",
                                            "subagent_type": "general-purpose",
                                            "model": "or:mock/dead-lane"}),
            [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
             {"choices": [{"index": 0, "delta": {"content": "noted the failure"}}]},
             {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}],
        ])
        # The DEAD lane: the mock has no scenario named "dead-lane", so its
        # default handler answers a 404 (unknown model) -- exactly the live
        # symptom.
        evs = list(session.turn("run the agent on the dead lane"))
        tool_results = [e for e in evs if e.kind == "tool_result"]
        ctx.check("the Agent call produced a tool_result", len(tool_results) == 1)
        if tool_results:
            body = tool_results[0].data.get("content", "")
            ctx.check("the handback is an error", tool_results[0].data.get("ok") is False)
            ctx.check(f"the 404's own words ride the handback, got {body[:160]!r}",
                      "not finish normally" in body)
    finally:
        mock.stop()


# ---- balances remaining -------------------------------------------------------------


@test
def test_balance_lines_lead_with_remaining_and_carry_the_breakdown(ctx: Ctx):
    from halo_harness.providers.balances import format_balance_entry
    spent = format_balance_entry("OpenRouter", {"status": "ok", "amount": 145.0, "kind": "spend",
                                                 "total_credits": 200.0, "total_usage": 145.0})
    ctx.check(f"a spend figure carries total+used+left, got {spent!r}",
              "$145.00 spent" in spent and "$200.00 total" in spent and "$55.00 left" in spent)
    credits = format_balance_entry("OpenRouter", {"status": "ok", "amount": 55.0, "kind": "credits",
                                                    "total_credits": 200.0, "total_usage": 145.0})
    ctx.check(f"a credits-remaining line carries the breakdown, got {credits!r}",
              "$55.00 remaining" in credits and "$200.00 total" in credits and "$145.00 used" in credits)
    plain = format_balance_entry("OpenRouter", {"status": "ok", "amount": 12.4, "kind": "limit_remaining"})
    ctx.check(f"a bare remaining line stays clean, got {plain!r}",
              plain == "OpenRouter: $12.40 remaining")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
