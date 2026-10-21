"""tests.test_supervise_resume -- Halo 3.1.8.0 R1: the cross-process runner
heartbeat (supervise/heartbeat.py) and the supervisor resuming a run from its
checkpoint after a crash, with test_orchestra_run2's crash shape. A run with a
live runner reads `running`, not `interrupted` (studio/orchestra_model.py). No
model is called.

Run: python -m tests.test_supervise_resume
"""
from __future__ import annotations

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


class _Killed(Exception):
    pass


@test
def test_heartbeat_live_other_live_and_pid_reuse(ctx: Ctx):
    from halo_harness.orchestra import jsonl
    from halo_harness.supervise import heartbeat
    import os
    run_dir = Path(_sd()) / "hb"
    run_dir.mkdir(parents=True, exist_ok=True)
    heartbeat.write(run_dir, by="cli")
    ctx.check("a fresh beat is live", heartbeat.live(run_dir) is not None)
    ctx.check("this process is not 'other'", heartbeat.other_live(run_dir) is None)
    # a stale beat (older than 2*BEAT_S) is not live
    row = heartbeat.read(run_dir)
    row["beat"] = time.time() - 3 * heartbeat.BEAT_S
    jsonl.write_json(heartbeat.path(run_dir), row)
    ctx.check("a stale beat is not live", heartbeat.live(run_dir) is None)
    # a fresh beat from a dead/foreign pid is not live (pid reuse guard)
    jsonl.write_json(heartbeat.path(run_dir), {"pid": 2, "pstart": "x", "beat": time.time(), "by": "ghost"})
    ctx.check("a foreign pid's beat is not live", heartbeat.live(run_dir) is None)
    heartbeat.clear(run_dir)


@test
def test_studio_run_state_running_vs_interrupted(ctx: Ctx):
    from halo_harness.supervise import heartbeat
    from halo_harness.studio import orchestra_model as OM
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo)
    # make the run look started (advance a step past pending)
    from halo_harness.orchestra import jsonl
    graph = jsonl.read_json(run_dir / "workflow.json", {})
    for s in graph.get("steps") or []:
        if s.get("id") == "lead":
            s["state"] = "running"
    jsonl.write_json(run_dir / "workflow.json", graph)
    ctx.check("with no live runner the run is interrupted", OM.run_state(run_dir, live=False) == "interrupted")
    heartbeat.write(run_dir, by="supervise")
    ctx.check("with a live runner it is running", OM.run_state(run_dir, live=False) == "running")
    heartbeat.clear(run_dir)


@test
def test_supervisor_resumes_a_crashed_run_from_its_checkpoint(ctx: Ctx):
    """test_orchestra_run2's crash shape, through the supervisor: the runner dies right after lane 2's
    merge; the supervisor's resume picks up at the merge and merges lanes 3..5 without re-running a worker."""
    from halo_harness.orchestra import events as E
    from halo_harness.supervise import queue, runner
    from halo_harness.supervise.loop import Supervisor
    from tests.helpers import orchestra_fixtures as F
    sd = _sd()
    repo = F.make_repo()
    g = queue.add(sd, "write basket", repo=str(repo), kind="orchestra", files=["basket.py"],
                  test=f"{PY} -m unittest -q test_basket", workers=5)
    rd = runner.ensure_run(queue.load(sd, g["id"]))
    queue.set_state(sd, g["id"], "running", "started", run_dir=str(rd))

    # first pass: crash right after lane 2 merges (no ADAPTERS seam -- call run() directly with the kill hook)
    from halo_harness.orchestra.run import run

    def kill(entry):
        if entry["kind"] == "merge" and entry["text"].startswith("lane 2 merged"):
            raise _Killed()
    try:
        run(rd, model_calls=F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), spawn=F.FakeWorker(),
            judge=F.FakeJudge(), on_event=kill)
        ctx.check("the kill fired", False)
    except _Killed:
        pass
    ctx.check("lanes 1 and 2 merged before the crash", _read(rd / "merge.json")["merged"] == [1, 2])
    count = len(E.read(rd))

    # the supervisor resumes: a worker that must NOT run again
    worker = F.FakeWorker()

    def make(run_dir, goal, model):
        return {"model_calls": F.FakeLead("unused"), "spawn": worker, "judge": F.FakeJudge()}
    runner.ADAPTERS = make
    try:
        out = Supervisor(sd).run_inline(queue.load(sd, g["id"]))
    finally:
        runner.ADAPTERS = None
    ctx.check(f"the resumed run finished, got {out}", out["state"] == "done")
    ctx.check("no worker ran again on the resume", worker.calls == [])
    new = E.read(rd, since=count)
    ctx.check("the resume says where it picks up", new and new[0]["text"] == "resume: picking up at merge")
    merged = [e["lane"] for e in new if e["kind"] == "merge" and e["text"].startswith(f"lane {e['lane']} merged")]
    ctx.check(f"only lanes 3..5 merged on the resume, got {merged}", merged == [3, 4, 5])
    ctx.check("the goal is done", queue.load(sd, g["id"])["state"] == "done")


def _read(path):
    import json
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
