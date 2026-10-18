"""tests.test_studio_orchestra_plan -- Halo 3.0.9.0 round R2: the reviewed
plan's Studio routes (studio/orchestra_plan_api.py) over a real temp git repo
and the R2 fakes through `orchestra_api.RUNNER` (no model call):

1. `POST orchestra/run {review: true}` -> the run goes `planned`; `GET
   <run>/plan` has the five jobs, no problem, the units, the mode; `PUT` an
   overlap -> `{ok: false, problems}` naming both jobs, kept as the draft;
   approve answers 422 with it; `PUT` the fix (an after) -> ok; approve ->
   the run finishes with the edited plan; a second approve is a 409.
2. Reject needs a reason (422), then stops the run with it.
3. A planned run with no runner waiting (Studio restarted): approve starts
   one and the run finishes; the auto run's plan routes answer 409.

Run: python -m tests.test_studio_orchestra_plan
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import orchestra_studio_rig as R  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
GOAL = {"what": "Write the five functions of basket.py", "done_when": "the tests pass", "stop_when": "two returns",
        "workers": 5, "files": ["basket.py"]}


def _until(s, rid: str, state: str, timeout: float = 30) -> str:
    end, got = time.monotonic() + timeout, ""
    while time.monotonic() < end:
        got = s.get(f"orchestra/{rid}")[1].get("run", {}).get("state", "")
        if got == state:
            return got
        time.sleep(0.1)
    return got


class _Runner:
    def __enter__(self):
        from halo_harness.studio import orchestra_api
        self.saved, orchestra_api.RUNNER = orchestra_api.RUNNER, R.fake_runner()
        return self

    def __exit__(self, *a):
        from halo_harness.studio import orchestra_api, orchestra_live
        orchestra_live.wait(60)
        orchestra_api.RUNNER = self.saved


@test
def test_review_run_plan_put_approve(ctx: Ctx):
    from halo_harness.studio import orchestra_live
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-studio-plan-")
    try:
        with _Runner(), R.Studio(repo) as s:
            st, ok = s.post("orchestra/run", dict(GOAL, review=True, test=f"{F.PY} -m unittest -q test_basket"))
            rid = ok.get("run_id", "")
            ctx.check(f"201 with the run id, got {st} {ok}", st == 201 and rid)
            ctx.check("the run turns planned", _until(s, rid, "planned") == "planned")
            st, plan = s.get(f"orchestra/{rid}/plan")
            ctx.check(f"GET plan: five jobs, no problem, the units, review mode, got {st} {sorted(plan)}",
                      st == 200 and len(plan["jobs"]) == 5 and plan["problems"] == [] and plan["planned"] is True
                      and plan["mode"] == "review" and plan["source"] == "split" and "basket.py#total" in plan["units"]
                      and plan["decision"] is None and plan["state"] == "planned" and plan["preflight"] == [])
            jobs = plan["jobs"]
            jobs[4]["claims"] = ["basket.py#subtotal", "basket.py#total"]
            st, put = s.call("PUT", f"orchestra/{rid}/plan", {"jobs": jobs})
            row = (put.get("problems") or [{}])[0]
            ctx.check(f"PUT an overlap: ok false, the problem names both jobs, got {st} {put.get('problems')}",
                      st == 200 and put["ok"] is False and row.get("jobs") == ["job-5", "job-3"] and row.get("field") == "claims")
            ctx.check("the draft is kept and GET plan opens it", s.get(f"orchestra/{rid}/plan")[1]["source"] == "draft"
                      and any(p.parent.name == rid for p in repo.joinpath(".halo", "orchestra").glob("*/plan.draft.json")))
            st, err = s.post(f"orchestra/{rid}/approve")
            ctx.check(f"approve with a problem is a 422, got {st} {err.get('error')}", st == 422 and "would run at once" in err["error"])
            ctx.check("a body without jobs is a 422", s.call("PUT", f"orchestra/{rid}/plan", {"jobs": "x"})[0] == 422)
            jobs[4]["after"] = ["job-3"]
            st, put = s.call("PUT", f"orchestra/{rid}/plan", {"jobs": jobs})
            ctx.check(f"PUT the fix: ok, got {st} {put.get('problems')}", st == 200 and put["ok"] is True)
            st, ok = s.post(f"orchestra/{rid}/approve")
            ctx.check(f"approve: 200, the runner was live already, got {st} {ok}", st == 200 and ok["ok"] and ok["resumed"] is False
                      and ok["jobs"][4]["after"] == ["job-3"])
            ctx.check("the run ends", orchestra_live.wait(90))
            data = s.get(f"orchestra/{rid}")[1]
            ctx.check(f"finished with the edited plan, got {data['run']['state']} {(data.get('report') or {}).get('stop_reason')}",
                      data["run"]["state"] == "finished" and data["split"]["plan"] == "approved"
                      and data["workflow"]["layers"] == [[1, 2, 3, 4], [5]])
            st, again = s.post(f"orchestra/{rid}/approve")
            ctx.check(f"a decided plan is a 409, got {st} {again}", st == 409 and "already approved" in again["error"])
            ctx.check("so is a PUT", s.call("PUT", f"orchestra/{rid}/plan", {"jobs": jobs})[0] == 409)
    finally:
        R.cleanup(repo)


@test
def test_reject_needs_a_reason_then_stops_the_run(ctx: Ctx):
    from halo_harness.studio import orchestra_live
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-studio-reject-")
    try:
        with _Runner(), R.Studio(repo) as s:
            rid = s.post("orchestra/run", dict(GOAL, review=True))[1].get("run_id", "")
            ctx.check("planned", _until(s, rid, "planned") == "planned")
            st, err = s.post(f"orchestra/{rid}/reject", {"reason": "  "})
            ctx.check(f"no reason is a 422, got {st} {err}", st == 422 and "say why" in err["error"])
            st, ok = s.post(f"orchestra/{rid}/reject", {"reason": "split by file instead"})
            ctx.check(f"reject: 200, got {st} {ok}", st == 200 and ok["reason"] == "split by file instead")
            ctx.check("the run ends", orchestra_live.wait(30))
            rep = s.get(f"orchestra/{rid}")[1]
            ctx.check(f"stopped with the reason, nothing ran, got {rep['run']['state']} {rep.get('report', {}).get('stop_reason')!r}",
                      rep["run"]["state"] == "stopped" and rep["report"]["stop_reason"] == "the plan was rejected: split by file instead"
                      and rep["lanes"] == [])
    finally:
        R.cleanup(repo)


@test
def test_approve_starts_a_runner_when_none_waits(ctx: Ctx):
    from halo_harness.orchestra import goal as G
    from halo_harness.orchestra import jsonl, workflow as wf
    from halo_harness.orchestra.run import goal_units
    from halo_harness.orchestra.split import split_goal
    from halo_harness.studio import orchestra_live
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-studio-resume-")
    try:
        run_dir = F.make_run(repo)
        goal = G.load_goal(run_dir / "goal.json")
        goal.plan = "review"
        G.save_goal(goal, run_dir / "goal.json")
        split_goal(run_dir, goal, goal_units(repo, goal), call_model=F.FakeLead(F.split_answer([[f] for f in F.FUNCS])),
                   base=F.git(repo, "rev-parse", "HEAD").strip())
        graph = jsonl.read_json(run_dir / "workflow.json", {})
        for sid, state in (("goal", "done"), ("lead", "done"), ("split", "planned")):
            graph = wf.advance(graph, sid, state)
        jsonl.write_json(run_dir / "workflow.json", graph)
        auto = F.make_run(repo)
        with _Runner(), R.Studio(repo) as s:
            ctx.check("the planned run reads planned with no runner", s.get(f"orchestra/{run_dir.name}")[1]["run"]["state"] == "planned")
            st, err = s.post(f"orchestra/{auto.name}/approve")
            ctx.check(f"an auto run's plan is not approved, got {st} {err}", st == 409 and "plan: auto" in err["error"])
            st, ok = s.post(f"orchestra/{run_dir.name}/approve")
            ctx.check(f"approve starts a runner, got {st} {ok}", st == 200 and ok["resumed"] is True)
            ctx.check("the run ends", orchestra_live.wait(90))
            data = s.get(f"orchestra/{run_dir.name}")[1]
            ctx.check(f"finished, got {data['run']['state']} {(data.get('report') or {}).get('stop_reason')}",
                      data["run"]["state"] == "finished" and [l["state"] for l in data["lanes"]] == ["merged"] * 5)
    finally:
        R.cleanup(repo)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio orchestra plan tests"))
