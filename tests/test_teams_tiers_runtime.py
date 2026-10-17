"""tests.test_teams_tiers_runtime -- Halo 3.0.7.0 round R1: tier enforcement
(`TeamControl.tier_of/tier_gate/spawn_refusal/tier_claim/tier_release`) and
its wiring in agent/subagent.run_agent_call right after routing: allowed one
tier down, refused two down, refused up, refused sideways, the last tier,
the max_parallel refusal and its release, and no-tiers passthrough. The
spawn-level half uses the same real Session + mocked upstream
tests/test_teams_runtime.py uses. No model is called.

Run: python -m tests.test_teams_tiers_runtime
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402

ensure_default_provider_credentials()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

TIERS = [{"name": "top", "members": ["main"]},
         {"name": "leads", "members": ["planner", "reviewer"], "max_parallel": 1},
         {"name": "workers", "members": ["worker"]}]


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="tiers-runtime-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.state_dir = d / ".halo"
        self.cwd = d / "project"
        (self.cwd / ".halo").mkdir(parents=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _control(e: _Env, tiers=TIERS, name="tier-team"):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_runtime import load_team_control
    from halo_harness.teams_yaml import save_team_template
    for bio, model in (("main-bio", "or:mock/tier-main"), ("lead-bio", "or:mock/tier-lead"),
                       ("worker-bio", "or:mock/tier-worker")):
        save_agent_bio(bio, {"description": bio, "models": {"preference": model}}, state_dir=e.state_dir)
    data = {"agents": [{"agent": "main-bio", "role": "main"},
                       {"agent": "lead-bio", "role": "planner"},
                       {"agent": "lead-bio", "role": "reviewer"},
                       {"agent": "worker-bio", "role": "subagent", "as": "worker"}],
            "delegation": {"max_depth": 3}}
    if tiers is not None:
        data["tiers"] = tiers
    ok, problems = save_team_template(name, data, state_dir=e.state_dir)
    assert ok, problems
    control = load_team_control(name, cwd=e.cwd, state_dir=e.state_dir, trusted=True)
    assert control is not None
    return control


@test
def test_tier_of_and_the_gate_lines(ctx: Ctx):
    with _Env() as e:
        c = _control(e)
        ctx.check("tier_of places each alias", [c.tier_of(a) for a in ("main", "planner", "reviewer", "worker", "ghost")]
                  == [0, 1, 1, 2, None])
        ctx.check("main -> planner (one down) is allowed", c.tier_gate("main", "planner") is None)
        ctx.check("planner -> worker (one down) is allowed", c.tier_gate("planner", "worker") is None)
        two = c.tier_gate("main", "worker")
        ctx.check(f"main -> worker (two down) states the rule, got {two!r}", two ==
                  "`main` (tier 0 `top`) may spawn only into the next tier down (tier 1 `leads`); `worker` is in tier 2")
        up = c.tier_gate("planner", "main")
        ctx.check(f"planner -> main (up) states the rule, got {up!r}", up ==
                  "`planner` (tier 1 `leads`) may spawn only into the next tier down (tier 2 `workers`); `main` is in tier 0")
        side = c.tier_gate("planner", "reviewer")
        ctx.check(f"planner -> reviewer (sideways) states the rule, got {side!r}", side ==
                  "`planner` (tier 1 `leads`) may spawn only into the next tier down (tier 2 `workers`); "
                  "`reviewer` is in tier 1")
        last = c.tier_gate("worker", "planner")
        ctx.check(f"the last tier spawns no member, got {last!r}", last ==
                  "`worker` (tier 2 `workers`) is in the last tier: it does its work itself and spawns no lineup "
                  "member; `planner` is in tier 1")
        ctx.check("a caller or target outside the lineup is not placed and passes",
                  c.tier_gate(None, "worker") is None and c.tier_gate("main", "general") is None)
        ctx.check("no refusal line says 'not allowed'", all("not allowed" not in (x or "") for x in (two, up, side, last)))


@test
def test_max_parallel_refuses_and_releases(ctx: Ctx):
    with _Env() as e:
        c = _control(e)
        ctx.check("the first lead spawn passes", c.spawn_refusal("main", "planner") is None)
        c.tier_claim("a1", "planner")
        full = c.spawn_refusal("main", "reviewer")
        ctx.check(f"a second lead while one runs hits max_parallel, got {full!r}",
                  full == "tier `leads` already runs 1 of 1: wait or raise max_parallel")
        ctx.check("the gate line still wins over the count", c.spawn_refusal("main", "worker").startswith("`main`"))
        c.tier_release("a1")
        ctx.check("released, the next lead passes", c.spawn_refusal("main", "reviewer") is None)
        c.tier_release("a1")  # idempotent
        c.tier_claim("w1", "worker")
        c.tier_claim("w2", "worker")
        ctx.check("a tier without max_parallel never counts", c.spawn_refusal("planner", "worker") is None)
        c.tier_claim("x1", "general")
        ctx.check("a non-member claims nothing", "x1" not in c.tier_live)


@test
def test_no_tiers_is_a_passthrough(ctx: Ctx):
    with _Env() as e:
        c = _control(e, tiers=None, name="flat-team")
        ctx.check("no tiers declared", c.tiers_declared is False and [t["name"] for t in c.tiers] == ["all"])
        ctx.check("every spawn passes the gate", all(c.tier_gate(a, b) is None for a in ("main", "worker")
                                                      for b in ("main", "planner", "worker")))
        c.tier_claim("a1", "planner")
        ctx.check("claims are not counted, spawn_refusal never refuses",
                  c.tier_live == {} and c.spawn_refusal("main", "worker") is None)


# ---- spawn level: a real Session, a mocked upstream -------------------------------

def _text(text: str):
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"content": text}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}]


def _session(e: _Env, mock, roles: dict):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.config.agents_md import discover_agents
    from halo_harness.hooks import HookRunner
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.providers.stream import ProviderCreds
    return Session(
        cwd=e.cwd, model_ref=parse_model_ref("or:mock/tier-main"), model_profile=ModelProfile(),
        creds=ProviderCreds(base_url=mock.base_url, api_key="k"), state_dir=e.state_dir, model_label="mock/tier-main",
        session_context=SessionContext(cwd=e.cwd, model_label="mock/tier-main"), openrouter_base_url=mock.base_url,
        max_turns=10, agents=discover_agents(e.cwd, settings=None), roles=roles,
        hook_runner=HookRunner({}, cwd=e.cwd, session_id="tiertest", transcript_path=str(e.state_dir / "t.jsonl")))


def _call(session, tool_id: str, role: str) -> dict:
    tu = {"type": "tool_use", "id": tool_id, "name": "Agent",
          "input": {"description": "task", "prompt": "do the task", "subagent_type": "general-purpose", "role": role}}
    events = list(session._dispatch_tools(1, [tu]))
    return next(ev for ev in events if ev.kind == "tool_result").data


@test
def test_spawn_level_refusal_sits_after_routing(ctx: Ctx):
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
    mock = MockUpstream().start()
    try:
        SCENARIOS["tier-lead"] = lambda h, b: _finish(h, _text("LEAD DONE"))
        SCENARIOS["tier-worker"] = lambda h, b: _finish(h, _text("WORKER DONE"))
        SCENARIOS["tier-main"] = lambda h, b: _finish(h, _text("MAIN"))
        with _Env() as e:
            control = _control(e)
            from halo_harness.teams_yaml import resolve_role_table
            roles, _notes = resolve_role_table(control.template, cwd=e.cwd, state_dir=e.state_dir)
            session = _session(e, mock, roles)
            session.agent_runtime.team_control = control
            session.agent_runtime.role_table.update(roles)
            r = _call(session, "c1", "planner")
            ctx.check(f"main -> planner runs, got {r.get('content', '')[:120]!r}", "LEAD DONE" in r.get("content", ""))
            ctx.check(f"its tier slot is released when it finishes, got {control.tier_live}", control.tier_live == {})
            r = _call(session, "c2", "worker")
            ctx.check(f"main -> worker is a clean error naming the rule, got {r.get('content', '')[:200]!r}",
                      r.get("ok") is False and "may spawn only into the next tier down" in r.get("content", ""))
            control.tier_claim("busy", "reviewer")
            r = _call(session, "c3", "planner")
            ctx.check(f"a full tier refuses with its count, got {r.get('content', '')[:200]!r}",
                      r.get("ok") is False and "already runs 1 of 1" in r.get("content", ""))
            control.tier_release("busy")
            # the same session as a lead (a child one level down): planner -> worker runs, -> reviewer does not
            session.agent_runtime.depth, session.role_name = 1, "planner"
            session.agent_runtime.max_depth = 3  # delegation.max_depth, which a team session applies at start
            r = _call(session, "c4", "worker")
            ctx.check(f"planner -> worker runs, got {r.get('content', '')[:120]!r}", "WORKER DONE" in r.get("content", ""))
            r = _call(session, "c5", "reviewer")
            ctx.check(f"planner -> reviewer (sideways) is refused, got {r.get('content', '')[:200]!r}",
                      r.get("ok") is False and "`reviewer` is in tier 1" in r.get("content", ""))
    finally:
        mock.stop()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="teams tiers runtime tests"))
