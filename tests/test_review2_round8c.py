"""tests.test_review2_round8c -- pins for the vibes/review.md fix pass,
round 8, resume / team / role table (findings 56-58, 60):

  * f56  a task_id resume dropped the original role=, model=, effort
  * f57  a team's delegation.max_parallel was reset by every Agent batch
  * f58  the live role table was never recomputed (/roles off, /model
        provider switch) and the cost-aware default beat an explicit
        CLAUDE_CODE_SUBAGENT_MODEL
  * f60  team-defined role names were rejected as "Unknown role"
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.fake_home import build_fake_home
from tests.helpers.mock_openai import SCENARIOS, MockUpstream, _finish
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.test_review2_round8 import _restore_home, _session, _text_chunk

ensure_default_provider_credentials()

test, TESTS = new_registry()


# ---- f56: resume keeps the spawn-time role / model / effort -------------------

@test
def test_f56_resume_keeps_role_model_and_effort(ctx: Ctx):
    from halo_harness.agent import subagent as S
    fh = build_fake_home()
    SCENARIOS["r8-f56-child"] = lambda h, b: _finish(h, _text_chunk("child reply"))
    mock = MockUpstream().start()
    seen: list = []
    real_build = S._build_child_session
    try:
        session = _session(fh, mock)
        rt = session.agent_runtime
        S._build_child_session = lambda **kw: (seen.append(kw), real_build(**kw))[1]
        tu = {"type": "tool_use", "id": "c1", "name": "Agent",
              "input": {"description": "t", "prompt": "go", "subagent_type": "general-purpose",
                        "model": "or:mock/r8-f56-child", "role": "coder", "effort": "low"}}
        evs = list(session._dispatch_tools(1, [tu]))
        content = next(e.data["content"] for e in evs if e.kind == "tool_result")
        task_id = re.search(r'task_id="([^"]+)"', content).group(1)
        rec = rt.tasks[task_id]
        ctx.check(f"the record remembers the overrides, got {rec}",
                  (rec.get("role_override"), rec.get("model_override"), rec.get("effort_override"))
                  == ("coder", "or:mock/r8-f56-child", "low"))
        resume = {"type": "tool_use", "id": "c2", "name": "Agent",
                  "input": {"task_id": task_id, "prompt": "again", "description": "resume"}}
        n_before = len(seen)
        list(session._dispatch_tools(2, [resume]))
        ctx.check("the resume really rebuilt a child", len(seen) == n_before + 1)
        kw = seen[-1]
        ctx.check(f"the resume rebuilt the child with the same overrides, got "
                  f"{(kw['role_override'], kw['model_override'], kw['effort_override'])}",
                  (kw["role_override"], kw["model_override"], kw["effort_override"])
                  == ("coder", "or:mock/r8-f56-child", "low"))
        # after a restart the overrides come back from meta.json
        rt.tasks.clear()
        rt.tasks_hydrated = False
        S._hydrate_tasks_from_disk(rt)
        rec2 = rt.tasks.get(task_id) or {}
        ctx.check(f"hydration restores them, got {rec2}",
                  (rec2.get("role_override"), rec2.get("model_override"), rec2.get("effort_override"))
                  == ("coder", "or:mock/r8-f56-child", "low"))
        n_before = len(seen)
        list(session._dispatch_tools(3, [dict(resume, id="c3")]))
        ctx.check("a resume after hydration keeps them too",
                  len(seen) == n_before + 1 and seen[-1]["role_override"] == "coder")
        # an explicit value on the resume call still wins
        n_before = len(seen)
        list(session._dispatch_tools(4, [dict(resume, id="c4", input={**resume["input"], "role": "reviewer"})]))
        ctx.check("an explicit role= on the resume wins",
                  len(seen) == n_before + 1 and seen[-1]["role_override"] == "reviewer")
    finally:
        S._build_child_session = real_build
        mock.stop()
        _restore_home()
        SCENARIOS.pop("r8-f56-child", None)


# ---- f57 / f60: team delegation and team role names ---------------------------

def test_f57_team_max_parallel_survives_an_agent_batch_and_f60_team_roles_validate(ctx: Ctx):
    from halo_harness.agent.subagent import _invalid_role_error, effective_max_concurrent
    from tests.test_teams_runtime import _Env, _fixture, _make_team_session
    from halo_harness.theme import set_config_value
    mock = MockUpstream().start()
    try:
        SCENARIOS["team-main"] = lambda h, b: _finish(h, _text_chunk("MAIN"))
        with _Env() as e:
            _fixture(e)
            set_config_value("team", "fixture-team")
            session = _make_team_session(e, mock, "team-main", None)
            rt = session.agent_runtime
            ctx.check(f"the runtime's own cap is the team's max_parallel, got {effective_max_concurrent(rt)}",
                      effective_max_concurrent(rt) == 2)
            with rt.concurrency_semaphore.pool(max_workers=1, limit=effective_max_concurrent(rt)):
                pass
            ctx.check(f"an Agent batch no longer resets the gate to agents.max_concurrent, got "
                      f"{rt.concurrency_semaphore.limit}", rt.concurrency_semaphore.limit == 2)
            ctx.check("a team alias is a valid Agent(role=...)", _invalid_role_error("review", rt) is None)
            ctx.check("without the runtime the same name is still unknown (the old behaviour)",
                      _invalid_role_error("review") is not None)
            ctx.check("a made-up name is still rejected under the team", _invalid_role_error("zzz_nope", rt) is not None)
    finally:
        mock.stop()


# ---- f58: the live role table follows /roles off and provider switches --------

if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
