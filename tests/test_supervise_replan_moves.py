"""tests.test_supervise_replan_moves -- Halo 3.1.8.0 R2: the lead's plan for the
lanes left, checked against the run (supervise/replan_plan.py) and written
into it (supervise/replan_apply.py): the problems a bad answer gets, and a
split plus a second specialist applied to a stopped run that then resumes to
its finished branch -- new lanes on the next numbers, the split lane replaced
with its claims released, placeholders for the parts, the specialist refused
its claim and handed to the lane it assists, which runs after it. No model is
called.

Run: python -m tests.test_supervise_replan_moves
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
GROUPS = [["add_item"], ["remove_item"], ["subtotal", "apply_discount"], ["total"]]


def _job(jid, title, *names, **extra):
    return dict({"id": jid, "title": title, "claims": [f"basket.py#{n}" for n in names]}, **extra)


KEEP = [_job("job-1", "write add_item", "add_item"), _job("job-2", "write remove_item", "remove_item"),
        _job("job-4", "write total", "total")]
SPLIT = [_job("job-3a", "write subtotal", "subtotal", **{"from": "job-3"}),
         _job("job-3b", "write apply_discount", "apply_discount", **{"from": "job-3"})]
ASSIST = [_job("job-9", "look at total before its worker does", "total", assist="job-4")]


def _stopped_run():
    """A run whose lane 3 (subtotal + apply_discount) stopped on its first pass: lanes 1, 2, 4 written."""
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    from tests.helpers import replan_rig as R
    rd = F.make_run(F.make_repo("replan-moves-"))
    worker, lead = R.Worker(stop_first={3}), F.FakeLead(F.split_answer(GROUPS))
    report = run(rd, model_calls=lead, spawn=worker, judge=F.FakeJudge())
    assert report["status"] == "stopped" and "lane 3" in report["stop_reason"], report
    return rd, worker, lead


@test
def test_the_problems_a_bad_answer_gets(ctx: Ctx):
    from halo_harness.supervise.replan_plan import check
    rd, _w, _l = _stopped_run()

    def problems(jobs):
        return " | ".join(check(rd, {"jobs": jobs}).problems)
    ctx.check("no jobs: the shape", "answer with {\"jobs\"" in " ".join(check(rd, {"why": "x"}).problems))
    ctx.check("a lane left dropped", "job-4 is a lane left and the plan drops it" in problems(KEEP[:2] + SPLIT))
    ctx.check("a kept lane changing its claims",
              "job-4 keeps its id but changes its claims" in problems(KEEP[:2] + [_job("job-4", "t", "total", "add_item")] + SPLIT))
    ctx.check("a one-part split", "job-3 is split into one part" in problems(KEEP + [_job("job-3a", "s", "subtotal", "apply_discount",
                                                                                           **{"from": "job-3"})]))
    got = problems(KEEP + [_job("job-3a", "s", "subtotal", **{"from": "job-3"}), _job("job-3b", "t", "total", **{"from": "job-3"})])
    ctx.check(f"a part outside its lane and a unit left unclaimed, got {got}",
              "job-3b is a part of job-3 but claims basket.py#total" in got and "leaves basket.py#apply_discount unclaimed" in got)
    ctx.check("a specialist for a lane that is not left", "assists 'job-8', which is not a lane left"
              in problems(KEEP + SPLIT + [_job("job-9", "x", "total", assist="job-8")]))
    ctx.check("a new job that is no move", "job-7 is not a lane left" in problems(KEEP + SPLIT + [_job("job-7", "x", "total")]))
    ctx.check("a retry on a part", "job-3a retries" in problems(KEEP + [dict(SPLIT[0], retry=True), SPLIT[1]]))
    ctx.check("plan_check's preflight runs on the whole plan", "bio `no-such-bio` does not exist"
              in problems(KEEP[:2] + [dict(KEEP[2], bio="no-such-bio")] + SPLIT))
    ok = check(rd, {"jobs": KEEP + SPLIT + ASSIST})
    ctx.check(f"the good answer passes, got {ok.problems}", not ok.problems)


@test
def test_a_split_and_a_specialist_applied_then_the_run_finishes(ctx: Ctx):
    from halo_harness.orchestra import jsonl
    from halo_harness.orchestra.claims import ClaimLog
    from halo_harness.orchestra.run import run
    from halo_harness.supervise import replan
    from halo_harness.supervise.replan_moves import diff_lines
    from halo_harness.supervise.replan_plan import check
    from tests.helpers import orchestra_fixtures as F
    from tests.helpers import replan_rig as R
    rd, worker, lead = _stopped_run()
    jsonl.write_json(rd / "replan.json", {"n": 1, "state": "asking", "at": time.time(), "why": [
        {"kind": "blocked", "lane": 3, "value": 700, "limit": 600, "text": "lane 3 (job-3) waited 700s on a claim"}]})
    checked = check(rd, {"jobs": KEEP + SPLIT + ASSIST})
    ctx.check(f"new lanes take the next numbers, got {checked.added}", checked.added == [5, 6, 7] and checked.retired == [3]
              and checked.requeue == [4] and checked.assists == {7: "job-4"})
    lines = diff_lines(checked.moves)
    ctx.check(f"the diff names the split and the specialist, got {lines}",
              "lane 3 (job-3) split -> job-3a (lane 5: 1 unit), job-3b (lane 6: 1 unit)" in lines
              and "+ lane 7 (job-9) assists lane 4 (job-4)" in lines)
    replan.apply_checked(R.state_dir({}), "g-test", rd, checked, "auto")
    split = jsonl.read_json(rd / "split.json", {})
    ctx.check(f"split.json takes the plan, got {[(j['id'], j['worker']) for j in split['jobs']]}",
              [(j["id"], j["worker"]) for j in split["jobs"]] == [("job-1", 1), ("job-2", 2), ("job-4", 4), ("job-3a", 5),
                                                                  ("job-3b", 6), ("job-9", 7)])
    four = next(j for j in split["jobs"] if j["id"] == "job-4")
    ctx.check("the lane assisted runs after the specialist and takes its summary",
              four["after"] == ["job-9"] and four["handoff"]["needs"] == [{"from": "job-9", "take": "summary"}])
    ctx.check("split.lead.json keeps the lead's split", len(jsonl.read_json(rd / "split.lead.json", {})["jobs"]) == 4)
    ctx.check("lane 3 is replaced (its history kept)", jsonl.read_json(rd / "lanes" / "3.json", {})["replaced"]["by"] == ["job-3a", "job-3b"])
    held = {c.key: c.holder for c in ClaimLog(rd).active().values()}
    ctx.check(f"placeholders: the parts and the lane assisted, none for the specialist, got {held}",
              held.get("basket.py#subtotal") == "lane:5" and held.get("basket.py#apply_discount") == "lane:6"
              and held.get("basket.py#total") == "lane:4" and "lane:7" not in held.values() and "lane:3" not in held.values())
    ctx.check("the specialist's lane file says assist", jsonl.read_json(rd / "lanes" / "7.json", {}).get("assist") == "job-4")
    steps = {s["id"]: s["state"] for s in jsonl.read_json(rd / "workflow.json", {})["steps"]}
    ctx.check(f"workflow: lane 3 skipped, the new lanes pending, got {steps}",
              steps["worker-3"] == "skipped" and all(steps[f"worker-{n}"] == "pending" for n in (4, 5, 6, 7)))
    report = run(rd, model_calls=lead, spawn=worker, judge=F.FakeJudge())
    ctx.check(f"the resumed run finished, got {report.get('stop_reason')}", report["status"] == "finished")
    ctx.check(f"the specialist ran before the lane it assists, got {worker.order}",
              worker.order.index(7) < len(worker.order) - 1 - worker.order[::-1].index(4))
    ctx.check("the specialist was refused its claim (it reads, it never edits)", worker.refused == [True])
    last4 = worker.prompts[4][-1]
    ctx.check("lane 4's hand-off carries the specialist's summary and the replan note",
              R.NOTES in last4 and "a specialist (job-9, lane 7)" in last4)
    ctx.check("lane 3's worker never ran again", worker.passes[3] == 1)
    bad = [c["id"] for c in report["checks"] if c["ok"] is False]
    ctx.check(f"every check passes, got {bad}", not bad)
    spent = sum(float(jsonl.read_json(p, {}).get("cost_usd") or 0) for p in (rd / "lanes").glob("*.json"))
    ctx.check(f"the report's cost counts the replaced lane too, got {report['cost_usd']} vs lanes {spent}",
              report["cost_usd"] >= round(spent, 6))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
