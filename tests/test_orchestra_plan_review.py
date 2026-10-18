"""tests.test_orchestra_plan_review -- Halo 3.0.9.0 round R2: the run pauses
after the plan (orchestra/plan.py, plan_check.py; `halo orchestra run
--review | plan | approve | reject`).

Over the R2 fixture (real git, the fake lead / workers / judge):
1. `plan: auto` runs as before: no plan.json, the split step never planned.
2. `plan: review` writes split.json, holds the split step `planned` with no
   lane, and waits; the edited plan (four jobs become five, job-5 after
   job-4, a bio and a model on one job) approved through the CLI runs:
   the workflow widens to five lanes, split.json takes the plan (the lead's
   is kept), the worker sees the job's bio and model, merge in layer order.
3. Reject stops the run with the reason; nothing ran.
4. Every validation problem; the bio/model preflight; a bad plan.json waits.
Run: python -m tests.test_orchestra_plan_review
"""
from __future__ import annotations

import io
import json
import sys
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()

KEYS = [f"basket.py#{f}" for f in ("add_item", "remove_item", "subtotal", "apply_discount", "total")]


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _review_run(workers: int = 5, groups=None):
    """`(repo, run_dir, thread, out, worker)`: a review run started on a thread, waiting for its plan."""
    from halo_harness.orchestra import goal as G
    from halo_harness.orchestra.plan import is_planned
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-plan-")
    run_dir = F.make_run(repo, workers=workers)
    goal = G.load_goal(run_dir / "goal.json")
    goal.plan = "review"
    G.save_goal(goal, run_dir / "goal.json")
    worker, out = F.FakeWorker(), {}
    seen = {}

    def spawn(lane):
        seen[lane.n] = (lane.job.bio, lane.job.model, lane.job.after)
        return worker(lane)
    lead = F.FakeLead(F.split_answer(groups or [[f] for f in F.FUNCS]))
    t = threading.Thread(target=lambda: out.update(report=run(run_dir, model_calls=lead, spawn=spawn,
                                                                judge=F.FakeJudge(), plan_poll_s=0.05)), daemon=True)
    t.start()
    end = time.monotonic() + 20
    while time.monotonic() < end and not is_planned(run_dir):
        time.sleep(0.05)
    return repo, run_dir, t, out, seen


def _cli(argv):
    from halo_harness.orchestra_cli import cmd_orchestra
    o, e = io.StringIO(), io.StringIO()
    with redirect_stdout(o), redirect_stderr(e):
        rc = cmd_orchestra(argv)
    return rc, o.getvalue(), e.getvalue()


@test
def test_auto_runs_the_split_as_before(ctx: Ctx):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    from tests.helpers.orchestra_studio_rig import cleanup
    repo = F.make_repo("orch-plan-auto-")
    run_dir = F.make_run(repo)
    try:
        report = run(run_dir, model_calls=F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), spawn=F.FakeWorker(),
                     judge=F.FakeJudge())
        ctx.check(f"finished, got {report.get('status')} {report.get('stop_reason')}", report["status"] == "finished")
        ctx.check("the goal says plan: auto", _read(run_dir / "goal.json")["plan"] == "auto")
        ctx.check("no plan.json, no draft, no lead copy", not any((run_dir / n).exists() for n in ("plan.json", "plan.draft.json", "split.lead.json")))
        ctx.check("the split step is done and was never planned", "split planned" not in (run_dir / "events.jsonl").read_text(encoding="utf-8")
                  and "plan" not in _read(run_dir / "split.json"))
    finally:
        cleanup(repo)


@test
def test_review_waits_then_the_approved_plan_runs(ctx: Ctx):
    from halo_harness.orchestra import plan as P
    from tests.helpers import orchestra_fixtures as F
    from tests.helpers.orchestra_studio_rig import cleanup
    repo, run_dir, t, out, seen = _review_run(workers=4, groups=[["add_item"], ["remove_item"], ["subtotal"],
                                                                  ["apply_discount", "total"]])
    try:
        ctx.check("the split step is planned", P.is_planned(run_dir))
        ctx.check("split.json has the lead's four jobs, no lane, no report", len(_read(run_dir / "split.json")["jobs"]) == 4
                  and not (run_dir / "lanes").exists() and not (run_dir / "report.json").exists() and t.is_alive())
        rc, text, _ = _cli(["plan", "--repo", str(repo)])
        ctx.check(f"`plan` prints the table, got {rc} {text!r}", rc == 0 and "waits for review" in text and "job-4" in text
                  and "basket.py#apply_discount, basket.py#total" in text and "no problems" in text)
        jobs = P.current_jobs(run_dir)
        jobs[3] = dict(jobs[3], claims=["basket.py#apply_discount"], bio="coder", model="or:vendor/cheap")
        jobs.append({"id": "new-1", "title": "write total", "claims": ["basket.py#total"], "after": [jobs[3]["id"]],
                     "handoff": {"needs": [{"from": jobs[3]["id"], "take": "summary"}]}})
        plan_file = run_dir.parent / "edited.json"
        plan_file.write_text(json.dumps({"jobs": jobs}), encoding="utf-8")
        rc, text, err = _cli(["approve", "--file", str(plan_file), "--repo", str(repo)])
        ctx.check(f"approve writes plan.json, got {rc} {text!r} {err!r}", rc == 0 and "plan approved (5 job(s))" in text)
        t.join(90)
        report = out.get("report") or {}
        ctx.check(f"the run finished, got {report.get('status')} {report.get('stop_reason')}", report.get("status") == "finished")
        decision = _read(run_dir / "plan.json")
        ctx.check(f"plan.json: approved, renumbered, refs rewritten, got {decision['jobs'][4]}",
                  decision["approved"] is True and [j["id"] for j in decision["jobs"]] == [f"job-{i}" for i in range(1, 6)]
                  and decision["jobs"][4]["after"] == ["job-4"] and decision["jobs"][4]["handoff"]["needs"][0]["from"] == "job-4")
        split = _read(run_dir / "split.json")
        ctx.check("split.json takes the plan, the lead's split is kept", split["plan"] == "approved" and len(split["jobs"]) == 5
                  and len(_read(run_dir / "split.lead.json")["jobs"]) == 4)
        graph = _read(run_dir / "workflow.json")
        ctx.check(f"the workflow widened to five lanes, lane 5 after lane 4, got {graph.get('layers')}",
                  graph["workers"] == 5 and graph.get("layers") == [[1, 2, 3, 4], [5]]
                  and all(s["state"] == "done" for s in graph["steps"] if s["kind"] == "worker"))
        ctx.check(f"the worker saw job-4's bio and model and job-5's after, got {seen}",
                  seen.get(4) == ("coder", "or:vendor/cheap", []) and seen.get(5) == ("", "", ["job-4"]))
        ctx.check("five lanes merged in layer order", _read(run_dir / "merge.json")["order"] == [1, 2, 3, 4, 5]
                  and [l["state"] for l in (_read(run_dir / "lanes" / f"{n}.json") for n in range(1, 6))] == ["merged"] * 5)
        rc, _, err = _cli(["approve", "--repo", str(repo)])
        ctx.check(f"a decided plan is not decided again, got {rc} {err!r}", rc == 1 and "already approved" in err)
        argv = __import__("halo_harness.orchestra.adapters", fromlist=["worker_argv"]).worker_argv("p", "or:m", "coder")
        ctx.check("the real worker gets --agent and --model", argv[-4:] == ["--agent", "coder", "--model", "or:m"])
    finally:
        cleanup(repo)


@test
def test_reject_stops_the_run_with_the_reason(ctx: Ctx):
    from tests.helpers.orchestra_studio_rig import cleanup
    repo, run_dir, t, out, seen = _review_run()
    try:
        rc, _, err = _cli(["reject", "--repo", str(repo), "--reason", ""])
        ctx.check(f"an empty reason is refused, got {rc} {err!r}", rc == 2)
        rc, text, _ = _cli(["reject", "--repo", str(repo), "--reason", "too broad: one lane per file"])
        ctx.check(f"reject writes plan.json, got {rc} {text!r}", rc == 0 and _read(run_dir / "plan.json")["approved"] is False)
        t.join(30)
        report = out.get("report") or {}
        ctx.check(f"stopped with the reason, got {report.get('status')} {report.get('stop_reason')!r}",
                  report.get("status") == "stopped" and report.get("stop_reason") == "the plan was rejected: too broad: one lane per file")
        split = next(s for s in _read(run_dir / "workflow.json")["steps"] if s["id"] == "split")
        ctx.check(f"no lane ran, the split step failed, got {split['state']}", not seen and split["state"] == "failed"
                  and not (run_dir / "lanes").exists())
    finally:
        cleanup(repo)


def _ok_plan():
    return [{"id": f"job-{i}", "title": f"write {k.split('#')[1]}", "claims": [k]} for i, k in enumerate(KEYS, 1)]


@test
def test_every_validation_problem_is_named(ctx: Ctx):
    from halo_harness.orchestra.workflow import plan_problems, validate_plan

    def got(jobs, **kw):
        return " | ".join(validate_plan(jobs, unit_keys=KEYS, preflight=False, **kw))
    ctx.check("a clean plan passes", got(_ok_plan()) == "")
    ctx.check("no jobs", "no jobs" in got([]))
    p = _ok_plan()
    p[1]["id"] = "job-1"
    ctx.check(f"a duplicate id, got {got(p)}", "two jobs are called job-1" in got(p))
    p = _ok_plan()
    p[0]["title"] = " "
    ctx.check("a job with no title", "job-1 has no title" in got(p))
    p = _ok_plan()
    p[0]["claims"] = []
    p[1]["claims"] = ["basket.py#nope"]
    ctx.check(f"no claims and an unknown key, got {got(p)}", "job-1 claims nothing" in got(p) and "'basket.py#nope' is not a unit" in got(p))
    p = _ok_plan()
    p[1]["after"] = ["job-9"]
    p[2]["handoff"] = {"needs": [{"from": "ghost", "take": "all"}]}
    ctx.check(f"after / needs.from that name no job, got {got(p)}", "job-2 runs after 'job-9', which is not one of the jobs" in got(p)
              and "job-3 needs 'ghost', which is not one of the jobs" in got(p))
    p = _ok_plan()
    p[0]["after"], p[1]["after"] = ["job-2"], ["job-1"]
    ctx.check(f"a cycle, got {got(p)}", "job-1 waits for itself" in got(p) and "job-2 waits for itself" in got(p))
    p = _ok_plan()
    p[0]["handoff"] = {"gives": [{"name": "notes", "kind": "artifact"}]}
    p[1]["handoff"] = {"needs": [{"from": "job-1", "take": "drawings"}]}
    ctx.check(f"a take the upstream does not give, got {got(p)}", "job-2 takes 'drawings' from job-1, which gives notes" in got(p))
    p[1]["handoff"]["needs"][0]["take"] = "notes"
    ctx.check("a take it gives passes", got(p) == "")
    p = _ok_plan()
    p[4]["claims"] = ["basket.py#subtotal"]
    rows = plan_problems(p, unit_keys=KEYS, preflight=False)
    ctx.check(f"two jobs on one key without an after, got {rows}", len(rows) == 1 and rows[0]["jobs"] == ["job-5", "job-3"]
              and "job-3 and job-5 both claim basket.py#subtotal and would run at once" in rows[0]["text"])
    p[4]["after"] = ["job-3"]
    ctx.check("with an after between them it passes", got(p) == "")
    p[4]["after"], p[4]["claims"] = [], ["basket.py"]
    whole = " | ".join(validate_plan(p, unit_keys=["basket.py"] + KEYS, preflight=False))
    ctx.check(f"a whole-file key overlaps every unit, got {whole}", whole.count("which overlap") == 4)


@test
def test_the_preflight_and_a_bad_plan_json_keep_the_run_waiting(ctx: Ctx):
    from halo_harness.orchestra import plan as P
    from halo_harness.orchestra.plan_check import validate_plan
    from tests.helpers.orchestra_studio_rig import cleanup
    from tests.helpers.preflight_seed import Home
    with Home() as home:
        p = _ok_plan()
        p[0]["bio"], p[1]["bio"], p[2]["bio"], p[3]["model"], p[4]["bio"] = "live-bio", "ghost-bio", "notools-bio", "or:vendor/gone", "dead-bio"
        text = " | ".join(validate_plan(p, unit_keys=KEYS, cwd=home.cwd, state_dir=home.state_dir))
        ctx.check(f"the bio/model preflight, got {text}", "job-1" not in text and "job-2's bio `ghost-bio` does not exist" in text
                  and "job-3's bio `notools-bio` has `tools.allow: []`" in text
                  and "job-4's model `or:vendor/gone` is not in the or catalog" in text
                  and "job-5's bio `dead-bio`'s model `or:vendor/gone`" in text)
    repo, run_dir, t, out, seen = _review_run()
    try:
        bad = P.current_jobs(run_dir)
        bad[1]["claims"] = list(bad[0]["claims"])
        ctx.check("approve with problems writes nothing", P.approve(run_dir, bad) and not (run_dir / "plan.json").exists())
        (run_dir / "plan.json").write_text(json.dumps({"approved": True, "jobs": bad}), encoding="utf-8")
        end = time.monotonic() + 10
        while time.monotonic() < end and not (run_dir / "plan.bad.json").exists():
            time.sleep(0.05)
        ctx.check("a hand-written bad plan.json moves to plan.bad.json with its problems",
                  _read(run_dir / "plan.bad.json")["problems"] and not (run_dir / "plan.json").exists())
        ctx.check("and the run still waits", t.is_alive() and P.is_planned(run_dir))
        ctx.check("a good plan then runs", P.approve(run_dir, P.split_jobs(run_dir)) == [] and (t.join(90) or True)
                  and (out.get("report") or {}).get("status") == "finished")
    finally:
        if t.is_alive():
            P.reject(run_dir, "test teardown")
            t.join(30)
        cleanup(repo)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="orchestra plan review tests"))
