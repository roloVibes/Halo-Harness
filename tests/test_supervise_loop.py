"""tests.test_supervise_loop -- Halo 3.1.8.0 R1: the supervisor's tick end to
end, in-process (supervise/loop.py). A `--review` orchestra goal starts on its
own thread, its waiting plan parks a goal_plan decision, the owner's Approve
(written as Attention writes it) is applied on the next tick and the run
finishes; a `job` goal starts as a background run with `--max-budget-usd` and
settles from its status.json and result JSON; a goal over its cap at start
parks with a goal_budget row. No model is called; the job's process is a fake.

Run: python -m tests.test_supervise_loop
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
PY = f'"{sys.executable}"'


def _sd():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _until(fn, timeout: float = 30.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.1)
    return None


@test
def test_a_review_goal_parks_its_plan_and_runs_once_approved(ctx: Ctx):
    from halo_harness.supervise import decisions, queue, runner
    from halo_harness.supervise.loop import Supervisor
    from tests.helpers import orchestra_fixtures as F
    sd = _sd()
    repo = F.make_repo()

    def make(run_dir, goal, model):
        return {"model_calls": F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), "spawn": F.FakeWorker(),
                "judge": F.FakeJudge(), "plan_poll_s": 0.05}
    runner.ADAPTERS = make
    sup = Supervisor(sd)
    try:
        g = queue.add(sd, "write basket", repo=str(repo), kind="orchestra", files=["basket.py"],
                      test=f"{PY} -m unittest -q test_basket", workers=5, review=True)
        sup.tick()
        ctx.check("the goal started", queue.load(sd, g["id"])["state"] == "running")
        row = _until(lambda: (sup.tick(), [r for r in decisions.open_rows(sd) if r["kind"] == "goal_plan"])[1])
        ctx.check("its waiting plan parked a goal_plan row", bool(row))
        if row:
            saved, why = decisions.answer(sd, row[0]["id"], "a", by="test")
            ctx.check(f"the owner's approve is taken, got {why!r}", saved is not None)
        done = _until(lambda: (sup.tick(), queue.load(sd, g["id"])["state"] == "done")[1], 60)
        ctx.check(f"the approved run finished, got {queue.load(sd, g['id'])['state']}", bool(done))
        ctx.check("the decision is closed", not decisions.open_rows(sd) and not decisions.answered(sd))
    finally:
        runner.ADAPTERS = None
        sup.close()


class _FakePopen:
    seen: list = []

    def __init__(self, argv, **kw):
        _FakePopen.seen.append(list(argv))
        self.pid = os.getpid()  # alive: the job reads as running until its status.json lands


@test
def test_a_job_goal_starts_with_its_cap_and_settles_from_its_result(ctx: Ctx):
    from halo_harness.supervise import queue, runner
    from halo_harness.supervise.loop import Supervisor
    sd = _sd()
    repo = Path(sd).parent / "job-repo"
    repo.mkdir(exist_ok=True)
    _FakePopen.seen = []
    runner.POPEN = _FakePopen
    sup = Supervisor(sd)
    try:
        g = queue.add(sd, "summarise the issues", repo=str(repo), kind="job", budget_usd=0.5)
        sup.tick()
        goal = queue.load(sd, g["id"])
        ctx.check("the job goal is running with a bg id", goal["state"] == "running" and goal["bg_id"])
        argv = _FakePopen.seen[-1] if _FakePopen.seen else []
        ctx.check(f"the job runs -p with --max-budget-usd 0.5, got {argv}",
                  "-p" in argv and "--max-budget-usd" in argv and argv[argv.index("--max-budget-usd") + 1] == "0.5")
        sup.tick()
        ctx.check("still running while no status.json exists", queue.load(sd, g["id"])["state"] == "running")
        from halo_harness.bg_run import load_run
        meta = load_run(goal["bg_id"])
        Path(meta["log_path"]).write_text(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                                                      "result": "three issues", "total_cost_usd": 0.12}) + "\n",
                                          encoding="utf-8")
        Path(meta["run_dir"], "status.json").write_text(json.dumps({"exit_code": 0, "ended": time.time()}), encoding="utf-8")
        sup.tick()
        done = queue.load(sd, g["id"])
        ctx.check(f"the job goal is done with its cost, got {done['state']} {done['cost_usd']}",
                  done["state"] == "done" and abs(done["cost_usd"] - 0.12) < 1e-9)
    finally:
        runner.POPEN = None
        sup.close()


@test
def test_a_goal_over_its_cap_at_start_parks_with_a_budget_row(ctx: Ctx):
    from halo_harness.supervise import decisions, queue, runner
    from halo_harness.supervise.loop import Supervisor
    sd = _sd()
    repo = Path(sd).parent / "cap-repo"
    repo.mkdir(exist_ok=True)
    runner.POPEN = _FakePopen
    sup = Supervisor(sd)
    try:
        g = queue.add(sd, "nothing left", repo=str(repo), kind="job", budget_usd=0.0)
        sup.tick()
        goal = queue.load(sd, g["id"])
        ctx.check(f"it parked on the budget, got {goal['state']} {goal['why']}",
                  goal["state"] == "parked" and goal["why"].startswith("budget"))
        rows = [r for r in decisions.open_rows(sd) if r["kind"] == "goal_budget" and r["goal"] == g["id"]]
        ctx.check("a goal_budget row waits on the owner", len(rows) == 1)
        decisions.answer(sd, rows[0]["id"], "r", "1", by="test")
        sup.tick()
        after = queue.load(sd, g["id"])
        ctx.check(f"raise by $1 re-queues (and the next tick starts) it, got {after['state']} {after['budget_usd']}",
                  after["budget_usd"] == 1.0 and after["state"] in ("queued", "running"))
    finally:
        runner.POPEN = None
        sup.close()


@test
def test_a_job_past_max_minutes_parks_why_time_and_is_not_retried(ctx: Ctx):
    from halo_harness.supervise import queue, runner
    from halo_harness.supervise.loop import Supervisor
    sd = _sd()
    repo = Path(sd).parent / "time-repo"
    repo.mkdir(exist_ok=True)
    # max_running 10: an earlier test's fake job is still "running" in this module's home
    (Path(sd) / "config.json").write_text(json.dumps({"supervise": {"max_minutes": 0.001, "retries": 3, "max_running": 10}}),
                                          encoding="utf-8")
    runner.POPEN = _FakePopen
    sup = Supervisor(sd)
    try:
        g = queue.add(sd, "a slow job", repo=str(repo), kind="job")
        sup.tick()
        time.sleep(0.2)
        sup.tick()
        goal = queue.load(sd, g["id"])
        ctx.check(f"past its time it parks, why time, got {goal['state']} {goal['why']}",
                  goal["state"] == "parked" and goal["why"] == "time" and goal["failure"]["kind"] == "time")
        sup.tick()
        ctx.check("it is not retried as a crash", queue.load(sd, g["id"])["state"] == "parked"
                  and int(queue.load(sd, g["id"]).get("retries") or 0) == 0)
    finally:
        runner.POPEN = None
        (Path(sd) / "config.json").unlink()
        sup.close()


@test
def test_a_pause_made_while_the_run_ran_is_kept(ctx: Ctx):
    """`halo goal pause` re-queues a goal held while its run thread is still busy; the thread's outcome
    (a stopped run) must not overwrite that."""
    from halo_harness.supervise import apply, queue
    sd = _sd()
    repo = Path(sd).parent / "pause-repo"
    repo.mkdir(exist_ok=True)
    g = queue.add(sd, "x", repo=str(repo), kind="orchestra")
    queue.set_state(sd, g["id"], "running", "started", run_dir=str(repo))
    queue.set_state(sd, g["id"], "queued", "paused", held=True)  # what goal_cli pause writes

    class _Sup:
        state_dir, cfg, _threads = sd, {"retries": 1}, {g["id"]: None}
    apply.outcome(_Sup(), queue.load(sd, g["id"]),
                  {"state": "stopped", "why": "cancelled", "cost_usd": 0.3, "failure": {"kind": "cancelled"}})
    got = queue.load(sd, g["id"])
    ctx.check(f"the pause stands and the cost is kept, got {got['state']} {got['held']} {got['cost_usd']}",
              got["state"] == "queued" and got["held"] is True and abs(got["cost_usd"] - 0.3) < 1e-9)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
