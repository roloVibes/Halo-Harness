"""tests.test_orchestra_split -- Halo 3.0.3.0 round R2: the lead's split
(orchestra/split.py). A valid answer (bare or fenced) is accepted; an unknown
key, a key in two jobs, an overlapping key and too many jobs are retried
once with the validator's lines, then stop the run with the reason; the
lead's own `{"stop": ...}` stops it; split.json's shape and the `lane:<n>`
placeholder claims; ClaimLog.reassign (lead only) and join_lane. Every repo
is a real temp git repo; the lead is a fake.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _setup(workers=5):
    from halo_harness.orchestra.goal import load_goal
    from halo_harness.orchestra.run import goal_units
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-split-")
    run_dir = F.make_run(repo, workers=workers)
    goal = load_goal(run_dir / "goal.json")
    return F, repo, run_dir, goal, goal_units(repo, goal)


def _split(run_dir, goal, units, lead):
    from halo_harness.orchestra.split import split_goal
    return split_goal(run_dir, goal, units, call_model=lead, base="abc123", lead_holder="orchestra/lead")


@test
def test_valid_answer_is_accepted_and_written(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    F, repo, run_dir, goal, units = _setup()
    answer = "Here is the split:\n```json\n" + F.split_answer([["add_item", "remove_item"], ["subtotal"],
                                                                ["apply_discount", "total"]]) + "\n```"
    lead = F.FakeLead(answer)
    jobs = _split(run_dir, goal, units, lead)
    ctx.check("one model call", len(lead.prompts) == 1)
    ctx.check("the prompt carries the goal, STOP WHEN and the keys",
              "WHAT YOU WANT" in lead.prompts[0] and "STOP WHEN: two returns" in lead.prompts[0]
              and "basket.py#apply_discount" in lead.prompts[0])
    ctx.check("three jobs (fewer than five workers is fine)", [j.worker for j in jobs] == [1, 2, 3])
    data = json.loads((run_dir / "split.json").read_text(encoding="utf-8"))
    ctx.check(f"split.json keys, got {sorted(data)}", sorted(data) == ["base", "jobs", "lead_cost_usd", "lead_sessions"])
    ctx.check("base and cost recorded", data["base"] == "abc123" and data["lead_cost_usd"] == 0.001)
    ctx.check("lead session recorded", data["lead_sessions"] == ["lead-1"])
    ctx.check("job shape", data["jobs"][0] == {"id": "job-1", "title": "write add_item and remove_item",
                                                "claims": ["basket.py#add_item", "basket.py#remove_item"],
                                                "worker": 1, "order": 1})
    active = ClaimLog(run_dir).active()
    ctx.check("every key is held by its lane's placeholder",
              {k: c.holder for k, c in active.items()} == {
                  "basket.py#add_item": "lane:1", "basket.py#remove_item": "lane:1", "basket.py#subtotal": "lane:2",
                  "basket.py#apply_discount": "lane:3", "basket.py#total": "lane:3"})


def _expect_retry_then_stop(ctx: Ctx, bad: str, needle: str):
    from halo_harness.orchestra.split import StopRun
    F, repo, run_dir, goal, units = _setup()
    lead = F.FakeLead(bad)
    try:
        _split(run_dir, goal, units, lead)
        ctx.check("the run stops", False)
    except StopRun as e:
        ctx.check(f"the reason names the problem ({needle}), got {e}", needle in str(e) and "twice" in str(e))
    ctx.check("exactly one retry", len(lead.prompts) == 2)
    ctx.check(f"the retry lists the validator's lines ({needle})",
              "previous answer had these problems" in lead.prompts[1] and needle in lead.prompts[1])
    ctx.check("nothing written", not (run_dir / "split.json").exists())


@test
def test_unknown_key_retries_then_stops(ctx: Ctx):
    from tests.helpers import orchestra_fixtures as F
    _expect_retry_then_stop(ctx, F.split_answer([["add_item"], ["checkout"]]), "'basket.py#checkout' is not a key")


@test
def test_duplicate_key_retries_then_stops(ctx: Ctx):
    from tests.helpers import orchestra_fixtures as F
    _expect_retry_then_stop(ctx, F.split_answer([["add_item", "total"], ["total"]]), "already in job 1")


@test
def test_overlapping_whole_file_key_retries_then_stops(ctx: Ctx):
    bad = json.dumps({"jobs": [{"title": "a", "claims": ["basket.py#total"]}, {"title": "b", "claims": ["basket.py"]}]})
    _expect_retry_then_stop(ctx, bad, "overlaps 'basket.py#total'")


@test
def test_too_many_jobs_retries_then_stops(ctx: Ctx):
    from halo_harness.orchestra.split import StopRun
    F, repo, run_dir, goal, units = _setup(workers=2)
    lead = F.FakeLead(F.split_answer([["add_item"], ["subtotal"], ["total"]]))
    try:
        _split(run_dir, goal, units, lead)
        ctx.check("stops", False)
    except StopRun as e:
        ctx.check(f"names the cap, got {e}", "3 jobs, but only 2 worker(s)" in str(e))
    ctx.check("retried once", len(lead.prompts) == 2)


@test
def test_a_good_second_answer_is_taken(ctx: Ctx):
    F, repo, run_dir, goal, units = _setup()
    lead = F.FakeLead("not json at all", F.split_answer([["add_item"], ["total"]]))
    jobs = _split(run_dir, goal, units, lead)
    ctx.check("two prompts, two jobs", len(lead.prompts) == 2 and len(jobs) == 2)
    ctx.check("the first rejection is in the run log",
              any("split answer 1 rejected" in e["text"] for e in __import__(
                  "halo_harness.orchestra.events", fromlist=["read"]).read(run_dir)))


@test
def test_lead_stop_answer_stops_the_run(ctx: Ctx):
    from halo_harness.orchestra.split import StopRun
    F, repo, run_dir, goal, units = _setup()
    try:
        _split(run_dir, goal, units, F.FakeLead('{"stop": "the basket is already written"}'))
        ctx.check("stops", False)
    except StopRun as e:
        ctx.check(f"the lead's reason, got {e}", "the lead stopped the run: the basket is already written" in str(e))


@test
def test_validate_jobs_shapes(ctx: Ctx):
    from halo_harness.orchestra.split import parse_answer, validate_jobs
    keys = ["a.py", "a.py#f", "a.py#g"]
    ctx.check("not an object", validate_jobs(None, keys, 2) != [])
    ctx.check("empty jobs", validate_jobs({"jobs": []}, keys, 2) == ['"jobs" must be a non-empty list'])
    ctx.check("a job with no claims", "claims nothing" in " ".join(validate_jobs({"jobs": [{"title": "x", "claims": []}]}, keys, 2)))
    ctx.check("a job with no title", "has no title" in " ".join(validate_jobs({"jobs": [{"claims": ["a.py#f"]}]}, keys, 2)))
    ok = {"jobs": [{"title": "f", "claims": ["a.py#f"]}, {"title": "g", "claims": ["a.py#g"]}]}
    ctx.check("disjoint units pass", validate_jobs(ok, keys, 2) == [])
    ctx.check("parse a bare object with prose around it", parse_answer('ok: {"jobs": []} done') == {"jobs": []})
    ctx.check("garbage parses to None", parse_answer("no braces here") is None)


@test
def test_reassign_is_lead_only_and_join_moves_placeholders(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    from halo_harness.orchestra.goal import set_lead_holder
    from halo_harness.orchestra.split import Job
    from halo_harness.orchestra.workers import join_lane, prepare_lane
    from tests.helpers.orchestra_fixtures import git
    F, repo, run_dir, goal, units = _setup()
    set_lead_holder(run_dir, "orchestra/lead")
    lead = F.FakeLead(F.split_answer([["add_item"], ["total"]]))
    jobs = _split(run_dir, goal, units, lead)
    log = ClaimLog(run_dir)
    refused = log.reassign("basket.py#total", "s9/main", "s9/main")
    ctx.check(f"a non-lead cannot reassign, got {refused}", not refused.ok and "only the lead" in refused.text)
    lane = prepare_lane(run_dir, jobs[0], git(repo, "rev-parse", "HEAD").strip())
    ctx.check("the lane starts joined", lane.state == "joined" and (lane.worktree / "basket.py").is_file())
    moved = join_lane(run_dir, 1, "s1/main")
    ctx.check(f"lane 1's key moved, got {moved}", moved == ["basket.py#add_item"])
    active = log.active()
    ctx.check("the worker holds it now; lane 2's placeholder untouched",
              active["basket.py#add_item"].holder == "s1/main" and active["basket.py#total"].holder == "lane:2")
    ctx.check("the lane records its holder", lane.holder == "s1/main")
    ctx.check("the worker can now mark it written", log.mark_written("s1/main", "basket.py#add_item").ok)
    again = join_lane(run_dir, 1, "s2/main")
    ctx.check("a worker run again takes over its predecessor's live claim",
              again == ["basket.py#add_item"] and log.active()["basket.py#add_item"].holder == "s2/main"
              and lane.holder == "s2/main")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
