"""tests.test_teams_runtime -- Halo 2.0.5 round 5 "team control": the
lineup sections ENFORCED (teams_runtime.TeamControl) -- routing, budget,
delegation caps, handoff shapes, pipeline gates, member context/hooks/
memory/permissions, org reports, the escalation decision, and the
spawn-level wiring in agent/subagent.run_agent_call (a real Session, a
mocked upstream, a fixture team -- the brief's own Tests section).
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
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()


class _Env:
    """Scratch BRIDGE_TEST_HOME/BRIDGE_STATE_DIR + a scratch project cwd --
    the real `~/.halo` is never touched."""

    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="teams-runtime-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.home = d
        self.state_dir = d / ".halo"
        self.cwd = d / "project"
        (self.cwd / ".halo").mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _fixture(e: _Env, *, max_budget_usd=0.0001, agents_may_exceed=False, escalation_ask=False):
    """The brief's fixture lineup: two bios, a routing/budget/pipeline
    team, and a TEAM.md the whole team reads. Returns the saved team name."""
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import save_team_template
    hook_file = e.cwd / "hook-out.txt"
    save_agent_bio("worker-bio", {
        "description": "implements things",
        "models": {"preference": "or:mock/team-worker"},
        "hooks": {"on_start": [{"command": f'echo "$HALO_AGENT" > "{hook_file}"'}],
                  "pre_tool": [{"command": "echo pre", "match": "Bash"}]},
    }, state_dir=e.state_dir)
    save_agent_bio("reviewer-bio", {
        "description": "reviews things",
        "models": {"preference": "or:mock/team-reviewer"},
        "hooks": {"post_tool": ["echo post"]},
    }, state_dir=e.state_dir)
    (e.cwd / "TEAM.md").write_text("Team file: ship it.\n", encoding="utf-8")
    ok, problems = save_team_template("fixture-team", {
        "description": "the round-5 fixture lineup",
        "agents": [
            {"agent": "worker-bio", "role": "main"},
            {"agent": "worker-bio", "role": "subagent", "as": "worker", "use_for": ["implement", "fix"],
             "hooks": {"post_tool": ["echo overridden"]}},
            {"agent": "reviewer-bio", "role": "reviewer", "as": "review", "use_for": ["review"]},
        ],
        "delegation": {"mode": "by-skill", "max_parallel": 2, "max_depth": 1, "handoff": "structured",
                       "forward_text": True},
        "routing": {"implement": "worker", "review": "review", "default": "worker"},
        "budget": {"max_budget_usd": max_budget_usd, "agents_may_exceed": agents_may_exceed},
        "escalation": {"triggers": ["budget_exhausted"], "to": "or:mock/team-bigger", "ask": escalation_ask},
        "context": {"files": ["TEAM.md"], "memory": {"namespace": "shared", "writers": ["worker"]}},
        "permissions": {"mode": "auto", "rules": {"deny": ["Bash(rm -rf:*)"]}, "offline": False},
        "pipeline": {"stages": [
            {"name": "implement", "role": "worker", "gate": "required",
             "acceptance": {"prompt": "say READY", "expect": "READY"}},
            {"name": "review", "role": "review", "gate": "optional"},
        ]},
    }, state_dir=e.state_dir)
    assert ok, problems
    return "fixture-team"


def _control(e: _Env, **kw):
    from halo_harness.teams_runtime import load_team_control
    _fixture(e, **kw)
    control = load_team_control("fixture-team", cwd=e.cwd, state_dir=e.state_dir)
    assert control is not None
    return control


# ---------------------------------------------------------------------------
# routing / budget / escalation decisions (pure TeamControl)
# ---------------------------------------------------------------------------

@test
def test_routing_sends_implement_to_worker_and_review_to_reviewer(ctx: Ctx):
    with _Env() as e:
        control = _control(e)
        kind, target = control.route_call({"prompt": "implement the login flow"}, "implement the login flow")
        ctx.check(f"implement routes to worker, got {kind}/{target}", (kind, target) == ("implement", "worker"))
        kind, target = control.route_call({"prompt": "review the diff"}, "review the diff")
        ctx.check(f"review routes to the reviewer alias, got {kind}/{target}", (kind, target) == ("review", "review"))
        kind, target = control.route_call({}, "something undecidable")
        ctx.check(f"the default applies, got {kind}/{target}", (kind, target) == ("default", "worker"))
        kind, target = control.route_call({"role": "judge"}, "implement but I chose a role")
        ctx.check(f"an explicit role= wins, got {kind}/{target}", (kind, target) == (None, None))


@test
def test_budget_exhaustion_stops_delegation_with_the_reason(ctx: Ctx):
    with _Env() as e:
        control = _control(e)
        ctx.check("under the cap: no refusal", control.budget_refusal() is None)
        control.record_spend(1.0)
        line = control.budget_refusal()
        ctx.check(f"the refusal names the cap and the spend, got {line!r}",
                  line is not None and "max_budget_usd=0.0001" in line and "delegation stopped" in line)
        ctx.check("budget_exhausted drives escalation", control.budget_exhausted)
    with _Env() as e:
        control = _control(e, agents_may_exceed=True)
        control.record_spend(1.0)
        line = control.budget_refusal()
        ctx.check(f"agents_may_exceed keeps members running, got {line!r}",
                  line is not None and "agents_may_exceed: true" in line)
    with _Env() as e:
        control = _control(e, max_budget_usd=10.0)
        control.record_turn(1)
        control.record_turn(1)
        ctx.check("turn budget counts root + child turns", control.turn_count == 2)


@test
def test_escalation_decision_names_trigger_target_and_ask(ctx: Ctx):
    with _Env() as e:
        control = _control(e, escalation_ask=True)
        ctx.check("no trigger before the budget is out",
                  control.escalation_decision(tool_failures=5, context_overflow=True) is None)
        control.record_spend(1.0)
        control.budget_refusal()
        decision = control.escalation_decision(tool_failures=0)
        ctx.check(f"budget_exhausted decides a switch, got {decision}",
                  decision == ("budget_exhausted", "or:mock/team-bigger", True))
        control.escalated = True
        ctx.check("already switched: no second switch this run",
                  control.escalation_decision(tool_failures=0) is None)


@test
def test_required_gate_blocks_next_stage_optional_records_and_continues(ctx: Ctx):
    with _Env() as e:
        control = _control(e)
        implement = control.stage_for("implement", "worker")
        review = control.stage_for("review", "review")
        ctx.check("the FIRST stage is never blocked by itself", control.gate_block(implement) is None)
        block = control.gate_block(review)
        ctx.check(f"review waits on implement's required gate, got {block!r}",
                  block is not None and "implement" in block and "required gate has not passed" in block)
        ok, note = control.evaluate_stage(implement, "READY to go", call_fn=lambda role, prompt: "READY")
        ctx.check(f"the acceptance passes on READY, got {ok}/{note}", ok)
        control.record_stage(implement, ok, note)
        ctx.check("with the gate passed, review runs", control.gate_block(review) is None)
        # a failed OPTIONAL gate records and continues (no block either way)
        ok2, note2 = control.evaluate_stage(review, "", call_fn=lambda role, prompt: "")
        ctx.check(f"an empty review fails its acceptance, got {ok2}", not ok2)
        control.record_stage(review, ok2, note2)
        ctx.check("a failed optional gate blocks nothing", control.gate_block(review) is None)


@test
def test_handoff_shapes_and_org_reports(ctx: Ctx):
    with _Env() as e:
        control = _control(e)
        control.template.setdefault("delegation", {}).pop("handoff", None)
        ctx.check("summary (the default) is the text itself",
                  control.handoff_text("worker", "plain") == "plain")
        control.template["delegation"]["handoff"] = "structured"
        structured = control.handoff_text("worker", "the result", cost_usd=0.5, child_log_path="/x/y.jsonl")
        ctx.check(f"structured carries role/status/cost/result, got {structured!r}",
                  "[handoff] role: worker" in structured and "[handoff] cost_usd: 0.5000" in structured
                  and "the result" in structured)
    with _Env() as e:
        from halo_harness.teams_yaml import save_team_template
        _fixture(e)
        save_team_template("org-team", {
            "description": "with an org",
            "agents": [{"agent": "worker-bio", "role": "main"},
                       {"agent": "worker-bio", "role": "subagent", "as": "worker"}],
            "org": {"positions": [{"title": "worker", "agent": "worker-bio", "reports_to": "main"}]},
        }, state_dir=e.state_dir)
        from halo_harness.teams_runtime import load_team_control
        control = load_team_control("org-team", cwd=e.cwd, state_dir=e.state_dir)
        line = control.record_report("worker", "worker finished ($0.0100)")
        ctx.check(f"the report is addressed to reports_to, got {line!r}",
                  line.startswith("[team org-team] worker -> main:"))


@test
def test_member_context_hooks_memory_and_permissions(ctx: Ctx):
    with _Env() as e:
        control = _control(e)
        addition = control.member_context_addition("worker", cwd=e.cwd, state_dir=e.state_dir)
        ctx.check(f"the team file loads for every member, got {addition!r}", "Team file: ship it." in addition)
        hooks = control.member_hooks("worker")
        ctx.check(f"the bio's on_start survives the override, got {hooks}",
                  any("hook-out.txt" in str(h.get("command")) for h in hooks.get("on_start", [])))
        ctx.check(f"the assignment's post_tool override wins, got {hooks}",
                  hooks.get("post_tool") == ["echo overridden"])
        memory_dir, may_write = control.member_memory("worker", e.state_dir)
        ctx.check("the writer alias may write the namespaced memory", may_write and memory_dir is not None
                  and "shared" in str(memory_dir))
        _dir, review_write = control.member_memory("review", e.state_dir)
        ctx.check("a non-writer alias may only read", not review_write)
        perms = control.member_permissions()
        ctx.check(f"team mode and rules reach the member, got {perms}",
                  perms["mode"] == "auto" and perms["deny"] == ["Bash(rm -rf:*)"] and perms["offline"] is False)


@test
def test_max_parallel_cap_holds_the_third_spawn(ctx: Ctx):
    from halo_harness.agent.subagent import SessionConcurrencyGate
    gate = SessionConcurrencyGate(8)
    gate.set_limit(2)
    entered = []
    release = threading.Event()

    def worker(n):
        with gate:
            entered.append(n)
            release.wait(3.0)  # every holder stays inside until released

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    time.sleep(0.5)
    ctx.check(f"only two run concurrently, got {sorted(entered)}", len(entered) == 2)
    release.set()
    for t in threads:
        t.join(4.0)
    ctx.check(f"the third entered after a slot freed, got {sorted(entered)}", len(entered) == 3)
    ctx.check("the limit is readable back", gate.limit == 2)


# ---------------------------------------------------------------------------
# spawn level: a real Session, a mocked upstream, run_agent_call under a team
# ---------------------------------------------------------------------------

def _make_team_session(e: _Env, mock, scenario: str, roles: dict):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.config.agents_md import discover_agents
    from halo_harness.hooks import HookRunner
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    session_ctx = SessionContext(cwd=e.cwd, model_label=f"mock/{scenario}")
    session = Session(
        cwd=e.cwd, model_ref=parse_model_ref(f"or:mock/{scenario}"), model_profile=ModelProfile(),
        creds=ProviderCreds(base_url=mock.base_url, api_key="k"),
        state_dir=e.state_dir, model_label=f"mock/{scenario}",
        session_context=session_ctx, openrouter_base_url=mock.base_url, max_turns=10,
        agents=discover_agents(e.cwd, settings=None), roles=roles,
        hook_runner=HookRunner({}, cwd=e.cwd, session_id=f"teamtest-{scenario}",
                               transcript_path=str(e.state_dir / f"{scenario}.jsonl")),
    )
    return session


def _dispatch(session, tool_id, subagent_type, prompt, extra=None):
    tu = {"type": "tool_use", "id": tool_id, "name": "Agent",
          "input": {"description": "task", "prompt": prompt, "subagent_type": subagent_type, **(extra or {})}}
    return list(session._dispatch_tools(1, [tu]))


@test
def test_spawn_level_routing_budget_depth_and_gate(ctx: Ctx):
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
    mock = MockUpstream().start()
    try:
        SCENARIOS["team-worker"] = lambda h, b: _finish(h, _text("WORKER DONE"))
        SCENARIOS["team-reviewer"] = lambda h, b: _finish(h, _text("REVIEW DONE"))
        SCENARIOS["team-main"] = lambda h, b: _finish(h, _text("MAIN"))
        with _Env() as e:
            control = _control(e)
            from halo_harness.teams_yaml import resolve_role_table
            team_roles, _notes = resolve_role_table(control.template, cwd=e.cwd, state_dir=e.state_dir)
            session = _make_team_session(e, mock, "team-main", team_roles)
            session.agent_runtime.team_control = control
            session.agent_runtime.role_table.update(team_roles)
            # routing: an `implement` description lands on the worker's model
            events = _dispatch(session, "c1", "general-purpose", "implement the login flow",
                               {"description": "implement the login flow"})
            result = next(ev for ev in events if ev.kind == "tool_result")
            ctx.check(f"routed to the worker bio's model, got {result.data.get('content', '')[:120]!r}",
                      "WORKER DONE" in result.data.get("content", ""))
            # the same team, budget now out: delegation stops with the reason
            control.record_spend(1.0)
            events = _dispatch(session, "c2", "general-purpose", "implement more",
                               {"description": "implement more"})
            result = next(ev for ev in events if ev.kind == "tool_result")
            ctx.check(f"the budget stop is a clean error with its reason, got "
                      f"{result.data.get('content', '')[:160]!r}",
                      result.data.get("ok") is False and "max_budget_usd" in result.data.get("content", ""))
            # a nested delegation under max_depth: 1 refuses with one line
            control.spend_usd = 0.0
            control.budget_stopped = None
            session.agent_runtime.depth = 1
            session.agent_runtime.max_depth = 1
            events = _dispatch(session, "c3", "general-purpose", "implement nested",
                               {"description": "implement nested"})
            result = next(ev for ev in events if ev.kind == "tool_result")
            ctx.check("the depth cap still refuses a nested delegation",
                      result.data.get("ok") is False and "depth limit" in result.data.get("content", ""))
            session.agent_runtime.depth = 0
            # a required gate that has not passed blocks the NEXT stage
            events = _dispatch(session, "c4", "general-purpose", "review the diff",
                               {"description": "review the diff"})
            result = next(ev for ev in events if ev.kind == "tool_result")
            ctx.check(f"review waits on implement's required gate, got {result.data.get('content', '')[:160]!r}",
                      result.data.get("ok") is False and "waits on stage 'implement'" in result.data.get("content", ""))
            # pass the implement gate (the c1 run above already produced
            # WORKER READY): record it, then review runs
            stage = control.stage_for("implement", "worker")
            control.record_stage(stage, True, "test")
            events = _dispatch(session, "c5", "general-purpose", "review the diff again",
                               {"description": "review the diff again"})
            result = next(ev for ev in events if ev.kind == "tool_result")
            ctx.check(f"with the gate passed review runs (and the structured handoff shows), got "
                      f"{result.data.get('content', '')[:160]!r}",
                      "REVIEW DONE" in result.data.get("content", "")
                      and "[handoff] role: review" in result.data.get("content", ""))
    finally:
        mock.stop()


@test
def test_member_hooks_run_with_HALO_AGENT_and_output_lands_in_the_transcript(ctx: Ctx):
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
    mock = MockUpstream().start()
    try:
        SCENARIOS["team-worker"] = lambda h, b: _finish(h, _text("WORKER READY"))
        SCENARIOS["team-main"] = lambda h, b: _finish(h, _text("MAIN"))
        with _Env() as e:
            control = _control(e)
            hook_file = e.cwd / "hook-out.txt"
            roles = {"worker": "or:mock/team-worker"}
            session = _make_team_session(e, mock, "team-main", roles)
            session.agent_runtime.team_control = control
            session.agent_runtime.role_table.update(roles)
            events = _dispatch(session, "c1", "general-purpose", "implement it",
                               {"description": "implement it"})
            result = next(ev for ev in events if ev.kind == "tool_result")
            ctx.check("the spawned member completed", result.data.get("ok") is True)
            deadline = time.time() + 3
            content = ""
            while time.time() < deadline and not content:
                try:
                    content = hook_file.read_text(encoding="utf-8").strip()
                except OSError:
                    time.sleep(0.05)
            ctx.check(f"the bio's on_start hook ran with HALO_AGENT set, got {content!r}",
                      content.endswith("general-purpose"))
    finally:
        mock.stop()


class _EscSession:
    """The minimal Session surface `_maybe_team_escalate` touches."""

    def __init__(self, control, interactive, state_dir):
        self.team_control = control
        self.interactive = interactive
        self.model_label = "or:mock/team-worker"
        self.model_ref = None
        self._escalation_decisions = []
        self._approval_waiters = {}
        self.settings = None
        self.state_dir = state_dir
        self._reply = {"action": "accept"}
        self.routes = {}

        class _RT:
            routes = {}

        self.agent_runtime = _RT()
        self.log = type("L", (), {"nodes": staticmethod(lambda: [])})()

    def _await_reply(self, waiters, request_id):
        return self._reply


def _text(text: str):
    return [
        {"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
        {"choices": [{"index": 0, "delta": {"content": text}}]},
        {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]


@test
def test_team_escalation_switches_and_ask_shows_the_card(ctx: Ctx):
    from halo_harness.agent.loop import Session
    with _Env() as e:
        control = _control(e, escalation_ask=False)
        control.record_spend(1.0)
        control.budget_refusal()
        stub = _EscSession(control, interactive=False, state_dir=e.state_dir)
        out = list(Session._maybe_team_escalate(stub, 1))
        ctx.check(f"ask:false switches and announces, got {[getattr(o, 'kind', o) for o in out]}",
                  any(getattr(o, "kind", "") == "system_note" and "escalation (budget_exhausted)" in o.data.get("text", "")
                      for o in out))
        ctx.check(f"the switch landed, got {stub.model_label}", stub.model_label == "or:mock/team-bigger")
    with _Env() as e:
        control = _control(e, escalation_ask=True)
        control.record_spend(1.0)
        control.budget_refusal()
        stub = _EscSession(control, interactive=True, state_dir=e.state_dir)
        stub._reply = {"action": "stop"}
        out = list(Session._maybe_team_escalate(stub, 1))
        ctx.check("ask:true shows the approval card first",
                  any(getattr(o, "kind", "") == "approval_request" for o in out))
        ctx.check(f"declined stays on the current model, got {stub.model_label}",
                  stub.model_label == "or:mock/team-worker")
        # 2.0.5 release-review finding 8: a DECLINE ends escalation for
        # the team (no second card on the next turn).
        out_again = list(Session._maybe_team_escalate(stub, 2))
        ctx.check(f"a declined escalation does not re-show the card next turn, got "
                  f"{[getattr(o, 'kind', '') for o in out_again]}",
                  not any(getattr(o, "kind", "") == "approval_request" for o in out_again))
        stub2 = _EscSession(control, interactive=True, state_dir=e.state_dir)
        stub2._reply = {"action": "accept"}
        control.escalated = False
        list(Session._maybe_team_escalate(stub2, 1))
        ctx.check(f"accepted switches, got {stub2.model_label}", stub2.model_label == "or:mock/team-bigger")


@test
def test_session_under_config_team_loads_control_and_caps(ctx: Ctx):
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
    mock = MockUpstream().start()
    try:
        SCENARIOS["team-main"] = lambda h, b: _finish(h, _text("MAIN"))
        SCENARIOS["team-worker"] = lambda h, b: _finish(h, _text("WORKER READY"))
        with _Env() as e:
            _fixture(e)
            from halo_harness.theme import set_config_value
            set_config_value("team", "fixture-team")
            set_config_value("roles", {"worker": "or:mock/team-worker", "reviewer": "or:mock/team-reviewer"})
            session = _make_team_session(e, mock, "team-main", None)
            ctx.check("the session picked the config team up",
                      getattr(session, "team_control", None) is not None
                      and session.team_control.name == "fixture-team")
            ctx.check("the control rides the runtime",
                      session.agent_runtime.team_control is session.team_control)
            ctx.check("delegation.max_parallel sized the in-flight cap",
                      session.agent_runtime.concurrency_semaphore.limit == 2)
            ctx.check("delegation.max_depth set the depth cap", session.agent_runtime.max_depth == 1)
            ctx.check("the team's own role table merged in",
                      session.agent_runtime.role_table.get("worker") == "or:mock/team-worker")
    finally:
        mock.stop()


if __name__ == "__main__":
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
