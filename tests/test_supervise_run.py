"""tests.test_supervise_run -- Halo 3.1.8.0 R1: the supervisor running a goal.
An orchestra goal through the real pipeline with fakes (supervise/runner.py,
loop.py), the budget guard as a stop (supervise/budget.py), the job outcome
reader, the failure classifier, the retry rule, and the runner heartbeat
(supervise/heartbeat.py). No model is called.

Run: python -m tests.test_supervise_run
"""
from __future__ import annotations

import sys
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


@test
def test_an_orchestra_goal_runs_to_done_with_the_heartbeat(ctx: Ctx):
    from halo_harness.supervise import heartbeat, queue, runner
    from halo_harness.supervise.loop import Supervisor
    from tests.helpers import orchestra_fixtures as F
    sd = _sd()
    repo = F.make_repo()
    beats = {"seen": False}

    def make(run_dir, goal, model):
        inner = F.FakeWorker()

        def spawn(lane):  # the worker runs inside run(), inside the Beat context: runner.json is live
            beats["seen"] = beats["seen"] or (heartbeat.read(run_dir) is not None)
            return inner(lane)
        return {"model_calls": F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), "spawn": spawn, "judge": F.FakeJudge()}
    runner.ADAPTERS = make
    try:
        g = queue.add(sd, "write basket", repo=str(repo), kind="orchestra", files=["basket.py"],
                      test=f"{PY} -m unittest -q test_basket", workers=5)
        queue.set_state(sd, g["id"], "running", "started", run_dir=str(runner.ensure_run(queue.load(sd, g["id"]))))
        out = Supervisor(sd).run_inline(queue.load(sd, g["id"]))
        ctx.check(f"the orchestra goal finished, got {out}", out["state"] == "done" and out["why"] == "finished")
        ctx.check("the goal file is done with its cost", queue.load(sd, g["id"])["state"] == "done" and out["cost_usd"] > 0)
        ctx.check("the runner wrote runner.json while it ran", beats["seen"])
        ctx.check("runner.json is cleared after the run (no live runner)",
                  heartbeat.live(Path(g["run_dir"]) if g.get("run_dir") else runner.ensure_run(queue.load(sd, g["id"]))) is None)
    finally:
        runner.ADAPTERS = None


@test
def test_the_budget_guard_stops_a_lane_over_the_cap(ctx: Ctx):
    """supervise/budget.Guard against a real run dir: once a lane file carries cost over the cap, the next
    lane does not start and the run gets a budget stop."""
    from halo_harness.orchestra import jsonl
    from halo_harness.supervise import budget, queue, runner
    from tests.helpers import orchestra_fixtures as F
    sd = _sd()
    repo = F.make_repo()
    g = queue.add(sd, "x", repo=str(repo), kind="orchestra", budget_usd=0.5, files=["basket.py"], workers=5)
    rd = runner.ensure_run(queue.load(sd, g["id"]))
    (rd / "lanes").mkdir(exist_ok=True)
    jsonl.write_json(rd / "lanes" / "1.json", {"lane": 1, "cost_usd": 0.8})  # lane 1 already spent over the cap
    guard = budget.Guard(sd, queue.load(sd, g["id"]), rd, None)

    class _Lane:
        n = 2
    out = guard.wrap(lambda lane: {"ok": True, "text": "ran"})(_Lane())
    ctx.check(f"lane 2 does not start, a STOP result, got {out}", out.get("text", "").startswith("STOP: budget:"))
    ctx.check("the guard recorded the hit and wrote the run's stop file", guard.hit and (rd / "stop.json").is_file())


@test
def test_budget_over_at_start_and_job_cap(ctx: Ctx):
    from halo_harness.supervise import budget, queue
    from tests.helpers import orchestra_fixtures as F
    sd = _sd()
    repo = F.make_repo()
    g = queue.add(sd, "x", repo=str(repo), kind="job", budget_usd=1.0)
    queue.update(sd, g["id"], lambda goal: goal.update(cost_usd=1.0))
    goal = queue.load(sd, g["id"])
    ctx.check("a goal that already spent its cap is over at start", budget.over_at_start(sd, goal, None))
    g2 = queue.add(sd, "y", repo=str(repo), kind="job", budget_usd=2.0)
    cap = budget.job_cap(sd, queue.load(sd, g2["id"]), 5.0)
    ctx.check(f"the job cap is the lower of its own and the queue's rest, got {cap}", abs(cap - 2.0) < 1e-6)


@test
def test_job_argv_carries_the_flags(ctx: Ctx):
    from halo_harness.supervise import runner
    argv = runner.job_argv({"what": "do it", "lineup": "", "repo": "."}, 1.25)
    ctx.check(f"argv is -p, json, auto, with the budget, got {argv}",
              argv[:2] == ["-p", "do it"] and "--output-format" in argv and "--permission-mode" in argv
              and "--max-budget-usd" in argv and argv[argv.index("--max-budget-usd") + 1] == "1.25")


@test
def test_classify_and_report_outcome(ctx: Ctx):
    from halo_harness.supervise import runner
    cases = {
        "budget: lane 2 not started": ("parked", "budget", "budget"),
        "lane 3 reached the return cap (2) and the tests still fail on the finished branch": ("parked", "gate", "gate"),
        "lane 1: the worker fell over": ("failed", "worker", "worker"),
        "the plan was rejected: no": ("stopped", "plan rejected", "cancelled"),
        "something unexpected": ("failed", "crash", "crash"),
    }
    for reason, want in cases.items():
        ctx.check(f"{reason!r} -> {want}", runner.classify(reason) == want)
    rep = {"status": "stopped", "stop_reason": "budget: over", "cost_usd": 0.4}
    out = runner.report_outcome(Path("."), rep)
    ctx.check("report_outcome maps a budget stop to parked/budget",
              out["state"] == "parked" and out["why"] == "budget" and out["failure"]["kind"] == "budget")


@test
def test_a_crash_is_retried_then_parks(ctx: Ctx):
    """A retryable failure (crash/worker) is re-queued up to supervise.retries, then parks why retries."""
    from halo_harness.supervise import apply, queue
    from tests.helpers import orchestra_fixtures as F

    class _Sup:
        def __init__(self, sd):
            self.state_dir = sd
            self.cfg = {"retries": 1}
            self._threads = {}
    sd = _sd()
    repo = F.make_repo()
    g = queue.add(sd, "x", repo=str(repo), kind="orchestra")
    queue.set_state(sd, g["id"], "running", "started", run_dir=str(repo))
    sup = _Sup(sd)
    crash = {"state": "failed", "why": "crash", "cost_usd": 0.1, "failure": {"kind": "crash", "step": "lead", "last_event": "boom"}}
    apply.outcome(sup, queue.load(sd, g["id"]), crash)
    g1 = queue.load(sd, g["id"])
    ctx.check("first crash re-queues it (retry 1)", g1["state"] == "queued" and g1["retries"] == 1)
    queue.set_state(sd, g["id"], "running", "started")
    apply.outcome(sup, queue.load(sd, g["id"]), crash)
    g2 = queue.load(sd, g["id"])
    ctx.check("the second crash parks it, why retries", g2["state"] == "parked" and g2["why"] == "retries"
              and g2["failure"]["kind"] == "crash")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
