"""tests.helpers.replan_rig -- the rig the replan tests share (Halo 3.1.8.0 R2):
a fresh state dir with a `supervise` config, a supervised Orchestra goal on the
reel's basket.py (orchestra_fixtures.make_repo), and a fake worker that writes
a WRONG body for a function on its first N passes, keeps every lane's prompts
and models, and plays a replan's specialist (an `assist` lane: it tries one
claim, is refused, and only replies). No model is ever called."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from tests.helpers import orchestra_fixtures as F

PY = f'"{sys.executable}"'
WRONG = {name: ['    raise ValueError("not yet")'] for name in F.FUNCS}
NOTES = "the specialist's notes: total is apply_discount(subtotal(basket), percent)"


def state_dir(supervise: dict) -> Path:
    sd = Path(tempfile.mkdtemp(prefix="replan-sd-")) / ".halo"
    sd.mkdir(parents=True)
    (sd / "config.json").write_text(json.dumps({"supervise": supervise}), encoding="utf-8")
    return sd


class Worker:
    """Per lane pass: claim, write (the wrong body while `wrong_for[name]` passes last), record, release."""

    def __init__(self, wrong_for=None, stop_first=()):
        self.wrong_for, self.stop_first = dict(wrong_for or {}), set(stop_first)
        self.passes, self.prompts, self.models, self.order, self.refused = {}, {}, {}, [], []

    def __call__(self, lane):
        from halo_harness.orchestra.claims import ClaimLog
        from halo_harness.orchestra.workers import join_lane, record_written
        k = self.passes[lane.n] = self.passes.get(lane.n, 0) + 1
        self.prompts.setdefault(lane.n, []).append(lane.prompt)
        self.models.setdefault(lane.n, []).append(getattr(lane.job, "model", ""))
        self.order.append(lane.n)
        log = ClaimLog(lane.run_dir)
        if lane.data().get("assist"):  # a replan's specialist: it reads, it may not edit
            self.refused.append(not log.claim(f"spec{lane.n}/main", lane.job.claims[0]).ok)
            return {"text": NOTES, "cost_usd": 0.001}
        if lane.n in self.stop_first and k == 1:
            return {"text": "I looked at it.\nSTOP: stuck on this one", "cost_usd": 0.001}
        holder = f"worker{lane.n}-{k}/main"
        join_lane(lane.run_dir, lane.n, holder)
        path = lane.worktree / "basket.py"
        for key in lane.job.claims:
            name = key.split("#", 1)[1]
            assert log.claim(holder, key).ok, f"claim {key}"
            log.mark_writing(holder, key)
            F.write_function(path, name, WRONG[name] if k <= self.wrong_for.get(name, 0) else F.SOLUTIONS[name])
            log.mark_written(holder, key)
            record_written(lane.run_dir, holder, key, lane.worktree)
            log.release(holder, key)
        return {"text": f"wrote {lane.job.claims}", "cost_usd": 0.002, "session_id": holder.split("/")[0]}


def adapters(lead, worker):
    """runner.ADAPTERS for a goal: one shared lead, worker and judge across the run's resumes."""
    judge = F.FakeJudge()
    return lambda run_dir, goal, model: {"model_calls": lead, "spawn": worker, "judge": judge}


def goal(sd: Path, *, groups=None, budget=None, review=False, replan=""):
    """A queued orchestra goal on a fresh basket repo, set running with its run folder (as the tick does)."""
    from halo_harness.supervise import queue, runner
    repo = F.make_repo("replan-run-")
    g = queue.add(sd, "write basket", repo=str(repo), kind="orchestra", files=["basket.py"], budget_usd=budget,
                  test=f"{PY} -m unittest -q test_basket", workers=5, review=review, replan=replan)
    queue.set_state(sd, g["id"], "running", "started", run_dir=str(runner.ensure_run(queue.load(sd, g["id"]))))
    return queue.load(sd, g["id"])


def run_goal(sd: Path, gid: str, make) -> dict:
    """The supervisor runs the goal to its outcome in this thread (Supervisor.run_inline)."""
    from halo_harness.supervise import queue, runner
    from halo_harness.supervise.loop import Supervisor
    runner.ADAPTERS = make
    try:
        g = queue.load(sd, gid)
        if g["state"] != "running":
            g = queue.set_state(sd, gid, "running", "resumed")
        return Supervisor(sd).run_inline(g)
    finally:
        runner.ADAPTERS = None


def retry_answer(model: str = "mock:better") -> str:
    return json.dumps({"jobs": [{"id": "job-5", "title": "write total", "claims": ["basket.py#total"], "retry": True,
                                 "model": model}], "why": "a stronger model, told what came back"})


def lane_bytes(run_dir, lanes) -> dict:
    return {n: (Path(run_dir) / "lanes" / f"{n}.json").read_bytes() for n in lanes}


def events(run_dir, name: str) -> list:
    from halo_harness.orchestra import events as E
    return [e for e in E.read(run_dir) if e["kind"] == "state" and e["text"].startswith(name + ":")]
