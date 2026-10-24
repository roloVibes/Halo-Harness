"""tests.test_supervise_replan -- Halo 3.1.8.0 R2: the supervisor replans a run
that drifts, end to end through the real Orchestra pipeline with fakes
(tests/helpers/replan_rig.py): the gate sends lane 5's piece back twice, the
spawn guard pauses the run before its third pass (returns drift), and the lead
is asked for the lanes left. The prompt carries the lanes left and what came
back; `auto` applies a model change + retry; `review` parks a goal_plan row
with the diff and a merged lane never changes; reject resumes the old lanes;
a plan that fails its check twice parks a goal_replan row; supervise.replan_max
leaves the drift to the gate's stop; the cooldown holds a second pause. No
model is called.

Run: python -m tests.test_supervise_replan
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _lead(*answers):
    from tests.helpers import orchestra_fixtures as F
    return F.FakeLead(F.split_answer([[f] for f in F.FUNCS]), *answers)


@test
def test_auto_applies_a_model_change_and_a_retry_with_the_contrast(ctx: Ctx):
    from halo_harness.orchestra import jsonl
    from halo_harness.supervise import queue
    from tests.helpers import replan_rig as R
    sd = R.state_dir({"replan": "auto"})
    g = R.goal(sd)
    lead, worker = _lead(R.retry_answer()), R.Worker(wrong_for={"total": 2})
    out = R.run_goal(sd, g["id"], R.adapters(lead, worker))
    rd = Path(g["run_dir"])
    ctx.check(f"the replanned run finished, got {out}", out["state"] == "done")
    ctx.check(f"lane 5 ran three times, the third after the replan, got {worker.passes}", worker.passes.get(5) == 3)
    ask = lead.prompts[1]
    ctx.check("the prompt names the drift and the lane left with its returns",
              "returns: lane 5 (job-5) was sent back 2 times" in ask and "job-5 (lane 5): write total" in ask
              and "sent back 2 times" in ask)
    ctx.check("the prompt pins the merged lanes", "job-1 (lane 1): write add_item  [merged" in ask)
    ctx.check("the prompt carries what came back (the gate's verdict as its worker read it)",
              "the gate's last verdict" in ask and "The tests fail on the finished branch" in ask)
    ctx.check(f"the third pass ran on the new model, got {worker.models[5]}", worker.models[5][-1] == "mock:better")
    ctx.check("its hand-off carries the contrast", "The supervisor replanned this lane (revision 1)" in worker.prompts[5][-1]
              and "The tests fail on the finished branch" in worker.prompts[5][-1])
    plan = jsonl.read_json(rd / "plan.json", {})
    rev = (plan.get("revisions") or [{}])[0]
    ctx.check(f"plan.json gains the revision, got {rev}", rev.get("by") == "auto" and rev.get("n") == 1
              and rev.get("why", [""])[0].startswith("returns:") and rev.get("to", [{}])[0].get("model") == "mock:better")
    ctx.check("events.jsonl: replan_asked then replan_applied", R.events(rd, "replan_asked") and R.events(rd, "replan_applied"))
    ctx.check("the lead's replan call is on the run's spend", len(jsonl.read_json(rd / "split.json", {})["lead_sessions"]) == 2)
    eps = queue.load(sd, g["id"])["replans"]
    ctx.check(f"the goal keeps one applied replan, got {eps}", len(eps) == 1 and eps[0]["state"] == "applied"
              and eps[0]["why"] == ["returns"])
    report = jsonl.read_json(rd / "report.json", {})
    ctx.check(f"the report says replanned 1 time, got {report.get('replans')}",
              (report.get("replans") or [{}])[0].get("n") == 1)


@test
def test_review_parks_the_diff_and_approve_applies_it(ctx: Ctx):
    from halo_harness.supervise import decisions, queue
    from halo_harness.supervise.loop import Supervisor
    from tests.helpers import replan_rig as R
    sd = R.state_dir({"replan": "review"})
    g = R.goal(sd)
    lead, worker = _lead(R.retry_answer()), R.Worker(wrong_for={"total": 2})
    make = R.adapters(lead, worker)
    out = R.run_goal(sd, g["id"], make)
    rd = Path(g["run_dir"])
    ctx.check(f"the goal parks for the review, got {out}", out["state"] == "parked" and out["why"] == "replan review")
    rows = [r for r in decisions.open_rows(sd) if r["goal"] == g["id"]]
    ctx.check(f"one goal_plan row naming the replan, got {[r['kind'] for r in rows]}",
              len(rows) == 1 and rows[0]["kind"] == "goal_plan" and rows[0]["target"].get("replan") == 1)
    ctx.check(f"its detail is the diff of the lanes, got {rows[0]['detail']!r}",
              "lane 5 (job-5): model the default -> mock:better" in rows[0]["detail"]
              and "lane 5 (job-5): retry with the contrast as context" in rows[0]["detail"])
    merged = R.lane_bytes(rd, (1, 2, 3, 4))
    decisions.answer(sd, rows[0]["id"], "a", by="owner")
    Supervisor(sd)._decisions()
    ctx.check("approve applied it and never touched a merged lane", R.lane_bytes(rd, (1, 2, 3, 4)) == merged)
    ctx.check("the goal is back in the queue", queue.load(sd, g["id"])["state"] == "queued")
    out = R.run_goal(sd, g["id"], make)
    ctx.check(f"the resumed goal finished on the new plan, got {out}", out["state"] == "done"
              and worker.models[5][-1] == "mock:better")
    ctx.check("the revision is by the owner", (json.loads((rd / "plan.json").read_text(encoding="utf-8"))
                                                ["revisions"][0]["by"]) == "owner")


@test
def test_reject_resumes_the_old_lanes_unchanged(ctx: Ctx):
    from halo_harness.supervise import decisions, queue
    from halo_harness.supervise.loop import Supervisor
    from tests.helpers import replan_rig as R
    sd = R.state_dir({"replan": "review"})
    g = R.goal(sd)
    worker = R.Worker(wrong_for={"total": 2})
    make = R.adapters(_lead(R.retry_answer()), worker)
    R.run_goal(sd, g["id"], make)
    rd = Path(g["run_dir"])
    row = [r for r in decisions.open_rows(sd) if r["goal"] == g["id"]][0]
    decisions.answer(sd, row["id"], "r", "the old plan is fine", by="owner")
    Supervisor(sd)._decisions()
    rejected = R.events(rd, "replan_rejected")
    ctx.check(f"the why is in events.jsonl, got {[e['text'] for e in rejected]}",
              rejected and "the old plan is fine" in rejected[0]["text"])
    out = R.run_goal(sd, g["id"], make)
    ctx.check(f"the old plan resumed and finished, got {out}", out["state"] == "done")
    ctx.check(f"lane 5 kept its model, got {worker.models[5]}", "mock:better" not in worker.models[5])
    ctx.check("no revision was written", not (json.loads((rd / "plan.json").read_text(encoding="utf-8")).get("revisions")
                                              if (rd / "plan.json").is_file() else None))
    ctx.check("the goal's replan reads rejected", queue.load(sd, g["id"])["replans"][0]["state"] == "rejected")


@test
def test_a_plan_that_fails_its_check_twice_parks_a_goal_replan_row(ctx: Ctx):
    from halo_harness.supervise import decisions, queue
    from halo_harness.supervise.loop import Supervisor
    from tests.helpers import replan_rig as R
    sd = R.state_dir({"replan": "auto"})
    g = R.goal(sd)
    bad = json.dumps({"jobs": [{"id": "job-1", "title": "write add_item", "claims": ["basket.py#add_item"]}]})
    lead, worker = _lead(bad, bad), R.Worker(wrong_for={"total": 2})
    out = R.run_goal(sd, g["id"], R.adapters(lead, worker))
    rd = Path(g["run_dir"])
    ctx.check(f"the goal parks, why replan, got {out}", out["state"] == "parked" and out["why"] == "replan")
    ctx.check("the lead was asked twice, the second time with the problems",
              len(lead.prompts) == 3 and "Your previous answer had these problems" in lead.prompts[2]
              and "job-1 is merged: it is pinned" in lead.prompts[2])
    row = [r for r in decisions.open_rows(sd) if r["goal"] == g["id"]][0]
    ctx.check(f"a goal_replan row with the problems as its detail, got {row['kind']}: {row['detail']!r}",
              row["kind"] == "goal_replan" and "job-5 is a lane left and the plan drops it" in row["detail"]
              and set(row["keys"]) == {"a", "r", "s", "o"})
    decisions.answer(sd, row["id"], "a", by="owner")
    Supervisor(sd)._decisions()
    again = decisions.read(sd, row["id"])
    ctx.check("apply with the failing proposal reopens the row with the problems",
              not again["answer"] and "does not pass the check" in again["detail"])
    (rd / "replan.plan.json").write_text(R.retry_answer(), encoding="utf-8")  # the owner's edit
    decisions.answer(sd, row["id"], "a", by="owner")
    Supervisor(sd)._decisions()
    ctx.check("the edited plan is applied and the goal re-queued", queue.load(sd, g["id"])["state"] == "queued"
              and queue.load(sd, g["id"])["replans"][0]["state"] == "applied")
    out = R.run_goal(sd, g["id"], R.adapters(lead, worker))
    ctx.check(f"it then finished, got {out}", out["state"] == "done" and worker.models[5][-1] == "mock:better")


@test
def test_past_replan_max_the_gate_stops_it_as_today(ctx: Ctx):
    from halo_harness.supervise import decisions
    from tests.helpers import replan_rig as R
    sd = R.state_dir({"replan": "auto", "replan_max": 0})
    g = R.goal(sd)
    lead = _lead(R.retry_answer())
    out = R.run_goal(sd, g["id"], R.adapters(lead, R.Worker(wrong_for={"total": 3})))
    ctx.check(f"no replan: the gate's return cap parks the goal, got {out}", out["state"] == "parked" and out["why"] == "gate")
    ctx.check("the lead was asked only for the split", len(lead.prompts) == 1)
    ctx.check("a goal_gate row waits", any(r["kind"] == "goal_gate" and r["goal"] == g["id"] for r in decisions.open_rows(sd)))


@test
def test_the_cooldown_holds_a_second_pause(ctx: Ctx):
    import shutil
    import time
    from halo_harness.supervise import queue, replan
    from halo_harness.supervise.settings import settings
    from tests.helpers import replan_rig as R
    sd = R.state_dir({"replan": "auto", "replan_cooldown_s": 300})
    g = queue.add(sd, "x", repo=str(sd), kind="job")
    rd = sd / "run"
    shutil.copytree(REPO / "tests" / "fixtures" / "supervise" / "drift-run", rd)
    now = time.time()
    queue.update(sd, g["id"], lambda goal: goal.update(replans=[{"n": 1, "at": now - 100, "state": "applied", "settled": now - 60}]))
    cfg = settings(sd)
    ctx.check("within the cooldown: no pause", replan.check_and_pause(sd, g["id"], rd, cfg, now) == []
              and not (rd / "replan.json").exists())
    got = replan.check_and_pause(sd, g["id"], rd, cfg, now + 400)
    ctx.check(f"past it the run pauses, got {[d.kind for d in got]}", got and replan.pausing(rd) and (rd / "stop.json").is_file())
    ctx.check("a second pause while one is in flight is refused", replan.check_and_pause(sd, g["id"], rd, cfg, now + 800) == [])
    ctx.check("the goal keeps the new replan as pausing", queue.load(sd, g["id"])["replans"][-1]["state"] == "pausing")


@test
def test_a_workflow_run_that_drifts_keeps_its_stage_set(ctx: Ctx):
    """3.2.1.0 R2: the drift-run fixture as a workflow run three ways (the goal row's `workflow`, goal.json's block,
    split.json's pin) is never paused; its row and `halo goal show` say so once; the same run as a plain goal pauses."""
    import contextlib
    import io
    import shutil
    import time
    from halo_harness.orchestra import jsonl
    from halo_harness.supervise import goal_cli, queue, replan
    from halo_harness.supervise.settings import settings
    from tests.helpers import replan_rig as R
    sd, now = R.state_dir({"replan": "auto"}), time.time()
    cfg, line = settings(sd), "a workflow run keeps its stage set (its plan is pinned by doc-review/review)"
    rows = {}
    for way in ("row", "block", "pin", "plain"):
        rd = sd / way
        shutil.copytree(REPO / "tests" / "fixtures" / "supervise" / "drift-run", rd)
        rows[way] = queue.add(sd, way, repo=str(sd), kind="job")
        queue.update(sd, rows[way]["id"], lambda g, rd=rd: g.update(run_dir=str(rd)))
    queue.update(sd, rows["row"]["id"], lambda g: g.update(workflow="doc-review/review"))
    for name, key, value in (("block", "goal.json", {"ref": "doc-review/review"}), ("pin", "split.json", {"pinned": True})):
        data = jsonl.read_json(sd / name / key, {})
        jsonl.write_json(sd / name / key, dict(data, workflow=value))
    for way in ("row", "block", "pin"):
        rd, gid = sd / way, rows[way]["id"]
        got = [replan.check_and_pause(sd, gid, rd, cfg, now), replan.spawn_hook(sd, gid, rd, cfg)(None)]
        ctx.check(f"{way}: never paused, got {got}", got == [[], ""] and not (rd / "replan.json").exists()
                  and not (rd / "stop.json").exists())
    goal = queue.load(sd, rows["row"]["id"])
    ctx.check(f"allowed answers first, got {replan.allowed(goal, cfg, now)!r}", replan.allowed(goal, cfg, now) == line)
    ctx.check(f"the goal row says it, got {goal.get('replan_off')!r}", goal.get("replan_off") == line)
    said = [e for e in R.events(sd / "row", "replan_off")]
    ctx.check(f"one state line in the run, got {[e['text'] for e in said]}", len(said) == 1 and said[0]["text"] == f"replan_off: {line}")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        goal_cli._show(sd, rows["row"]["id"], False)
    ctx.check(f"halo goal show says it once, got {out.getvalue()!r}", out.getvalue().count(f"  replan: off -- {line}\n") == 1)
    ctx.check("split.json's pin: the line names its workflow",
              queue.load(sd, rows["pin"]["id"]).get("replan_off") == "a workflow run keeps its stage set (its plan is pinned by its workflow)")
    plain = replan.check_and_pause(sd, rows["plain"]["id"], sd / "plain", cfg, now)
    ctx.check(f"the same run as a plain goal pauses, got {[d.kind for d in plain]}", plain and replan.pausing(sd / "plain"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
