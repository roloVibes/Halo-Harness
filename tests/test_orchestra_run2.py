"""tests.test_orchestra_run2 -- Halo 3.0.3.0 round R2: the run's loops and
stops (orchestra/run.py, merge.py, gate.py), over a real temp git repo with
fake lead, workers and judge.

3. A judge answer that fails the tests sends the piece back once
   (`pieces_returned` 1) and the second answer passes; with `return_cap: 1`
   and a judge that is always wrong the run stops with the reason.
4. Resume: the runner dies right after lane 2's merge; a re-run picks up at
   the merge and merges lanes 3..5 without running any worker again.
5. The gate: a wrong function fails the tests on the finished branch, the
   gate sends that lane back, the worker fixes it, the run finishes.
6. Stops: a worker's `STOP:` line, a worker that fails (and a re-run that
   finishes), and `halo orchestra stop` between steps.
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

CONFLICT_TEST = ("{py} -m unittest -q test_basket.BasketTest.test_apply_discount test_basket.BasketTest.test_total "
                 "test_basket.BasketTest.test_subtotal")
BAD_IMPORT = "from decimal import Decimal"


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _conflict_run(cap: int, judge):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo, workers=2, return_cap=cap, test=CONFLICT_TEST.format(py=F.PY))
    worker = F.FakeWorker(F.CONFLICT_SOLUTIONS, F.CONFLICT_IMPORTS)
    report = run(run_dir, model_calls=F.FakeLead(F.split_answer([["apply_discount"], ["subtotal", "total"]])),
                 spawn=worker, judge=judge)
    return repo, run_dir, worker, report


@test
def test_a_failing_judge_answer_returns_the_piece_once(ctx: Ctx):
    from tests.helpers import orchestra_fixtures as F
    judge = F.FakeJudge(BAD_IMPORT, F.COMBINED_IMPORT)
    repo, run_dir, worker, report = _conflict_run(2, judge)
    ctx.check(f"finished, got {report.get('stop_reason')}", report["status"] == "finished")
    lane = _read(run_dir / "lanes" / "2.json")
    ctx.check("pieces_returned 1", lane["pieces_returned"] == 1)
    ctx.check("the lane waited, then wrote again",
              [h["state"] for h in lane["history"]] == ["joined", "writing", "written", "in_review", "waiting",
                                                       "writing", "written", "in_review", "merged"])
    retries = [text for n, text in worker.calls if n == 2 and text]
    ctx.check("the worker was re-spawned with the failure text", len(retries) == 1 and "failed the tests" in retries[0])
    rows = _read(run_dir / "merge.json")["conflicts"]
    ctx.check("two judge rows: failed then passed",
              [(r["attempt"], r["tests_ok"]) for r in rows] == [(1, False), (2, True)])
    ctx.check("two fresh judge sessions", [r["judge_session"] for r in rows] == ["judge-session-1", "judge-session-2"])
    checks = {c["id"]: c["ok"] for c in report["checks"]}
    ctx.check(f"all checks true, got {checks}", all(v is True for k, v in checks.items() if k != "goal_done_when"))
    events = [e["text"] for e in __import__("halo_harness.orchestra.events", fromlist=["read"]).read(run_dir)]
    ctx.check("the loop back is logged", any("lane 2 sent back to its worker" in t for t in events))


@test
def test_return_cap_one_stops_the_run_with_the_reason(ctx: Ctx):
    from tests.helpers import orchestra_fixtures as F
    judge = F.FakeJudge(BAD_IMPORT)
    repo, run_dir, worker, report = _conflict_run(1, judge)
    ctx.check("stopped", report["status"] == "stopped")
    ctx.check(f"the reason names the lane and the cap, got {report['stop_reason']}",
              "lane 2" in report["stop_reason"] and "return cap (1)" in report["stop_reason"])
    ctx.check("returned once, judged twice", _read(run_dir / "lanes" / "2.json")["pieces_returned"] == 1
              and len(judge.calls) == 2)
    checks = {c["id"]: c["ok"] for c in report["checks"]}
    ctx.check("no piece over the cap", checks["no_piece_over_cap"] is True)
    ctx.check("not merged, tests not run", checks["all_branches_merged"] is False
              and checks["tests_pass_finished_branch"] is False and report["finished"] is None)
    graph = _read(run_dir / "workflow.json")
    ctx.check("the merge step is marked failed", any(s["id"] == "merge" and s["state"] == "failed" for s in graph["steps"]))


class _Killed(Exception):
    pass


@test
def test_resume_after_a_crash_picks_up_at_lane_3(ctx: Ctx):
    from halo_harness.orchestra import events as E
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo)
    lead = F.FakeLead(F.split_answer([[f] for f in F.FUNCS]))

    def kill(entry):
        if entry["kind"] == "merge" and entry["text"].startswith("lane 2 merged"):
            raise _Killed()
    try:
        run(run_dir, model_calls=lead, spawn=F.FakeWorker(), judge=F.FakeJudge(), on_event=kill)
        ctx.check("the fake kill fired", False)
    except _Killed:
        pass
    ctx.check("merge.json: lanes 1 and 2 merged", _read(run_dir / "merge.json")["merged"] == [1, 2])
    count = len(E.read(run_dir))
    worker = F.FakeWorker()
    report = run(run_dir, model_calls=F.FakeLead("unused"), spawn=worker, judge=F.FakeJudge())
    ctx.check(f"finished, got {report.get('stop_reason')}", report["status"] == "finished")
    ctx.check("no worker ran again", worker.calls == [])
    new = E.read(run_dir, since=count)
    ctx.check("the re-run says where it picks up", new[0]["text"] == "resume: picking up at merge")
    merged = [e["lane"] for e in new if e["kind"] == "merge" and e["text"].startswith(f"lane {e['lane']} merged")]
    ctx.check(f"only lanes 3..5 merged on the re-run, got {merged}", merged == [3, 4, 5])
    base = _read(run_dir / "split.json")["base"]
    ctx.check("five merges on the finished branch",
              len(F.git(repo, "log", "--merges", "--oneline", f"{base}..orchestra/{run_dir.name}").splitlines()) == 5)
    elapsed = [e["elapsed_s"] for e in E.read(run_dir)]
    ctx.check("elapsed_s monotonic across both runs", elapsed == sorted(elapsed))


@test
def test_the_gate_sends_a_wrong_piece_back(ctx: Ctx):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo)
    worker = F.FakeWorker(wrong={"subtotal": ['    return Decimal("1")']})
    report = run(run_dir, model_calls=F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), spawn=worker,
                 judge=F.FakeJudge())
    ctx.check(f"finished, got {report.get('stop_reason')}", report["status"] == "finished")
    lanes = {n: _read(run_dir / "lanes" / f"{n}.json")["pieces_returned"] for n in range(1, 6)}
    ctx.check(f"only the subtotal lane went back, got {lanes}", lanes == {1: 0, 2: 0, 3: 1, 4: 0, 5: 0})
    retry = [text for n, text in worker.calls if n == 3 and text]
    ctx.check("its worker got the failing output", len(retry) == 1 and "test_subtotal" in retry[0])
    ctx.check("the record matches the second pass", _read(run_dir / "lanes" / "3.json")["written"]
              ["basket.py#subtotal"].endswith('basket.values()), Decimal("0"))'))
    ctx.check("six merges (lane 3 twice)",
              len(F.git(repo, "log", "--merges", "--oneline", f"orchestra/{run_dir.name}").splitlines()) == 6)


@test
def test_a_worker_stop_line_stops_the_run(ctx: Ctx):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo)
    report = run(run_dir, model_calls=F.FakeLead(F.split_answer([[f] for f in F.FUNCS])),
                 spawn=F.FakeWorker(stop_lanes={4: "apply_discount needs total's rounding"}), judge=F.FakeJudge())
    ctx.check(f"stopped with the worker's reason, got {report['stop_reason']}",
              report["status"] == "stopped" and "STOP: apply_discount needs total's rounding" in report["stop_reason"])
    ctx.check("lane 4 failed", _read(run_dir / "lanes" / "4.json")["state"] == "failed")


@test
def test_a_failed_worker_stops_and_a_rerun_finishes(ctx: Ctx):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo)
    lead = F.FakeLead(F.split_answer([[f] for f in F.FUNCS]))
    failing = F.FakeWorker(fail_lanes={2})
    report = run(run_dir, model_calls=lead, spawn=failing, judge=F.FakeJudge())
    ctx.check(f"stopped, got {report['stop_reason']}", report["status"] == "stopped"
              and "lane 2: RuntimeError: the fake worker fell over" in report["stop_reason"])
    second = [text for n, text in failing.calls if n == 2]
    ctx.check("a worker's own error gets one more run, told what happened",
              len(second) == 2 and "ended with an error: RuntimeError" in second[1])
    worker = F.FakeWorker()
    report = run(run_dir, model_calls=lead, spawn=worker, judge=F.FakeJudge())
    ctx.check("the re-run finishes", report["status"] == "finished")
    ctx.check("only lane 2's worker ran again", [n for n, _ in worker.calls] == [2])


@test
def test_a_stop_request_ends_the_run_between_steps(ctx: Ctx):
    from halo_harness.orchestra.run import request_stop, run, stop_path
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo)
    worker = F.FakeWorker()

    def on_event(entry):
        if entry["kind"] == "state" and entry["text"].startswith("split done") and not stop_path(run_dir).exists():
            request_stop(run_dir, "the owner said stop")
    report = run(run_dir, model_calls=F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), spawn=worker,
                 judge=F.FakeJudge(), on_event=on_event)
    ctx.check(f"stopped with the reason, got {report['stop_reason']}",
              report["status"] == "stopped" and report["stop_reason"] == "the owner said stop")
    ctx.check("no worker ran", worker.calls == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
