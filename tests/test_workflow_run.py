"""tests.test_workflow_run -- a compiled workflow run by the Orchestra
pipeline (Halo 3.2.0.0 R5; workflows/runtime.py, gate.py, outputs.py): the
mock lead and stage workers carry the doc-review workflow to its typed
artifact and the report; an artifact off its schema goes back with the
problems, and at the stage's retries the run stops; a `when` on an upstream
output skips its stage at run time; a stage's budget stops the run before
another pass; a stage waits for its `after_event`; a stage's timeout_s is
the worker's time limit; `--as goal` queues the compiled run for the
supervisor, which resumes it from its checkpoint after a crash (skipped where
the build has no supervisor). No model call.

Run: python -m tests.test_workflow_run
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.workflow_rig import BAD_REPORT, GOOD_REPORT, StageWorker, WorkflowRig  # noqa: E402

test, TESTS = new_registry()


def _texts(run_dir, kind: str = "state") -> list:
    from halo_harness.orchestra import events
    return [e["text"] for e in events.read(run_dir) if e["kind"] == kind]


@test
def test_a_run_reaches_its_typed_artifact_and_the_report(ctx: Ctx):
    from halo_harness.orchestra import jsonl
    with WorkflowRig() as w:
        run = w.new_run(w.compile(docs="docs").goal)
        worker = StageWorker()
        report = w.run(run, worker=worker)
        ctx.check(f"finished, got {report['status']} {report.get('stop_reason')}", report["status"] == "finished")
        ctx.check("every stage ran once, in its layer", [c[1] for c in worker.calls] == ["read", "read", "judge", "write"]
                  or sorted(c[1] for c in worker.calls[:2]) == ["read", "read"])
        prompt = next(c[2] for c in worker.calls if c[1] == "write")
        ctx.check("the worker's prompt has its stage, the lead's brief and its schema", "Your stage of the workflow doc-review/review" in prompt
                  and "Brief: refined brief for job-4" in prompt and "checked against the review-report schema" in prompt
                  and "fix the dead link in docs/guide.md first" in prompt)
        art = report["artifacts"]
        ctx.check(f"the report lists the artifact with its schema and view, got {art}", len(art) == 1 and art[0]["name"] == "report"
                  and art[0]["schema"] == "review-report" and art[0]["view"] == "table" and art[0]["state"] == "saved" and art[0]["ok"])
        ctx.check("copied to <run>/artifacts/report/", jsonl.read_json(run / "artifacts" / "report" / "report.json", None) == GOOD_REPORT)
        ctx.check("the report's workflow block", report["workflow"]["ref"] == "doc-review/review"
                  and [s["id"] for s in report["workflow"]["stages"]] == ["read", "judge", "write"])
        rec = next(c for c in report["checks"] if c["id"] == "record_equals_disk")
        ctx.check(f"the evidence joined the record check, got {rec}", rec["ok"] and "2 workflow output(s) and evidence read" in rec["detail"])
        ctx.check("the plan was reviewed (gate: human)", any("plan approved by test" in t for t in _texts(run)))
        from halo_harness.orchestra.report import format_report
        text = format_report(report, run)
        ctx.check("the CLI report names the artifact and what is not enforced yet", "artifact report       ok" in text
                  and "not enforced yet: budget_usd 2.0" in text)


@test
def test_an_artifact_off_its_schema_goes_back_and_the_cap_stops(ctx: Ctx):
    from halo_harness.orchestra.lanes import load_lane
    with WorkflowRig() as w:
        run = w.new_run(w.compile(docs="docs").goal)
        worker = StageWorker(reports=[BAD_REPORT, GOOD_REPORT])
        report = w.run(run, worker=worker)
        writes = [c for c in worker.calls if c[1] == "write"]
        ctx.check(f"finished after one return, got {report['status']}", report["status"] == "finished" and len(writes) == 2
                  and load_lane(run, 4).pieces_returned == 1)
        ctx.check("the worker is told each problem", "findings[0].line is a whole number" in writes[1][3]
                  and "findings[1].file is required" in writes[1][3])
        ctx.check("a gate line says so", any("lane 4: 5 problem(s) with its outputs" in t for t in _texts(run, "gate")))
        run2 = w.new_run(w.compile(docs="docs").goal)
        report = w.run(run2, worker=StageWorker(reports=[BAD_REPORT]))
        ctx.check(f"always bad: stopped at the stage's retries (2), got {report.get('stop_reason')}", report["status"] == "stopped"
                  and "lane 4 (write) reached the return cap (2)" in report["stop_reason"] and load_lane(run2, 4).pieces_returned == 2)


@test
def test_a_when_on_an_upstream_output_skips_the_stage_at_run_time(ctx: Ctx):
    from halo_harness.orchestra import jsonl
    with WorkflowRig() as w:
        run = w.new_run(w.compile(docs="docs").goal)
        worker = StageWorker(verdict="")
        report = w.run(run, worker=worker)
        ctx.check(f"finished, got {report.get('stop_reason')}", report["status"] == "finished")
        ctx.check("the writer never ran", [c[1] for c in worker.calls].count("write") == 0)
        ctx.check("a state line says why", any("worker-4 skipped: stage write when output judge.verdict is not empty is false" in t
                                               for t in _texts(run)))
        graph = jsonl.read_json(run / "workflow.json", {})
        ctx.check("its step is skipped", next(s for s in graph["steps"] if s["id"] == "worker-4")["state"] == "skipped")
        ctx.check(f"the artifact row says skipped, got {report['artifacts']}", report["artifacts"][0]["state"] == "skipped")


@test
def test_a_stage_budget_stops_before_another_pass(ctx: Ctx):
    with WorkflowRig() as w:
        goal = w.compile(docs="docs").goal
        goal.workflow["stages"][2]["budget_usd"] = 0.05
        run = w.new_run(goal)
        report = w.run(run, worker=StageWorker(reports=[BAD_REPORT, GOOD_REPORT], cost=0.06))
        ctx.check(f"stopped on the stage's budget, got {report.get('stop_reason')}", report["status"] == "stopped"
                  and "budget: stage write spent $0.0600 of its $0.0500" in report["stop_reason"])


@test
def test_a_stage_waits_for_its_event(ctx: Ctx):
    from halo_harness.ext import publish_event
    with WorkflowRig() as w:
        goal = w.compile(docs="docs").goal
        goal.workflow["stages"][2]["after_event"] = "doc-review:review.done"
        run = w.new_run(goal)

        def later():
            deadline = time.time() + 30
            while time.time() < deadline and not any("waits for the event" in t for t in _texts(run)):
                time.sleep(0.05)
            publish_event("doc-review", "review.done", {"file": "docs/guide.md", "findings": 1})
        t = threading.Thread(target=later, daemon=True)
        t.start()
        report = w.run(run, worker=StageWorker())
        t.join(5)
        texts = _texts(run)
        ctx.check(f"finished after the event, got {report.get('stop_reason')}", report["status"] == "finished"
                  and any("lane 4 waits for the event doc-review:review.done" in x for x in texts)
                  and any("the event doc-review:review.done came" in x for x in texts))


@test
def test_a_stage_timeout_is_the_workers_time_limit(ctx: Ctx):
    from types import SimpleNamespace
    from halo_harness.orchestra.adapters import spawn_worker
    seen = []

    def runner(argv, **kw):
        seen.append(kw["timeout"])
        raise subprocess.TimeoutExpired(argv, kw["timeout"])
    with WorkflowRig() as w:
        spawn = spawn_worker(None, run_dir=w.repo, runner=runner, timeout_s=3600)
        lane = SimpleNamespace(n=1, prompt="p", worktree=w.repo, job=SimpleNamespace(model="", bio=""), timeout_s=900)
        got = spawn(lane)
        lane.timeout_s = 0
        spawn(lane)
        ctx.check(f"the stage's 900 s, else the run's, got {seen} {got}", seen == [900, 3600] and got["error"] == "the worker ran past 900s")


class _Killed(Exception):
    pass


@test
def test_as_goal_queues_the_compiled_run_and_the_supervisor_resumes_it(ctx: Ctx):
    """test_supervise_resume's crash shape: the first runner dies right after lane 2 merges; the
    supervisor (runner.ADAPTERS = the fakes) resumes the queued goal's run from its checkpoint."""
    from halo_harness.workflows import goal as WG
    if not WG.available():
        raise SkipTest("this build has no supervisor (halo_harness/supervise/, 3.1.8.0 R1): --as goal answers one line")
    from halo_harness.orchestra import events as E
    from halo_harness.orchestra import plan as P
    from halo_harness.orchestra.run import run
    from halo_harness.supervise import queue, runner
    from halo_harness.supervise.loop import Supervisor
    from tests.helpers.workflow_rig import FakeLead, fake_judge
    with WorkflowRig() as w:
        row = WG.add(w.compile(docs="docs"), w.repo, w.state)
        rd = Path(row["run_dir"])
        ctx.check("a queued orchestra goal whose run folder is the compiled run", row["kind"] == "orchestra"
                  and row["workflow"] == "doc-review/review" and runner.ensure_run(row) == rd)
        queue.set_state(w.state, row["id"], "running", "started", run_dir=str(rd))
        stop = threading.Event()

        def approver():
            while not stop.is_set() and not P.is_planned(rd):
                time.sleep(0.05)
            P.approve(rd, P.current_jobs(rd), by="test")
        threading.Thread(target=approver, daemon=True).start()

        def kill(entry):
            if entry["kind"] == "merge" and entry["text"].startswith("lane 2 merged"):
                raise _Killed()
        try:
            run(rd, model_calls=FakeLead(), spawn=StageWorker(), judge=fake_judge, on_event=kill, plan_poll_s=0.05)
            killed = False
        except _Killed:
            killed = True
        finally:
            stop.set()
        ctx.check("the first runner died after lane 2 merged", killed)
        count, worker = len(E.read(rd)), StageWorker()
        runner.ADAPTERS = lambda run_dir, goal, model: {"model_calls": FakeLead(), "spawn": worker, "judge": fake_judge}
        try:
            out = Supervisor(w.state).run_inline(queue.load(w.state, row["id"]))
        finally:
            runner.ADAPTERS = None
        new = [e["text"] for e in E.read(rd, since=count)]
        ctx.check(f"the supervisor finished it, got {out}", out["state"] == "done" and queue.load(w.state, row["id"])["state"] == "done")
        ctx.check("it picked up at the merge, no stage ran again", new[0] == "resume: picking up at merge" and worker.calls == [])
        ctx.check("the typed artifact is the run's", (rd / "artifacts" / "report" / "report.json").is_file())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
