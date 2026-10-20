"""tests.helpers.coach_probe_rig -- a reference Orchestra run for the coach's
probes (Halo 3.1.6.0 R2; orchestra/coach_probe.py) and the seams that run a
probe with no model:

* `Probe` scopes a home (BRIDGE_STATE_DIR for the block only), seeds the
  coach's bios (tests/helpers/coach_seed.py), builds the basket repo and runs
  the reference with the fake lead, workers and judge (two lanes: lane 1 as
  bio coach-cheap, lane 2 as coach-strong; `lineup=True` names a lineup
  `probe-line` in the goal), sets HALO_COACH_FAKE=1 and the seams, and puts
  everything back after;
* `fake_adapters(log, cost)` is probe_runs.ADAPTERS: the real spawn_worker
  path (the overlay written into the worktree, the argv built) with a runner
  that records the argv and the worktree's `.halo` files, then does the
  FakeWorker's edits and answers a JSON result with `cost[kind]` per lane.
No model is ever called.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

GROUPS = [["add_item", "remove_item"], ["subtotal", "apply_discount", "total"]]
COST = {"invariant": 0.001, "domain": 0.003}


def fake_adapters(log: list, cost: "dict | None" = None, hold=None):
    """probe_runs.ADAPTERS over the real worker argv; `hold` (an Event) makes every worker wait for it first."""
    from tests.helpers import orchestra_fixtures as F
    cost = dict(COST if cost is None else cost)

    def make(probe_dir, goal, cand, f, seen):
        from halo_harness.orchestra import probe_runs as PR
        from halo_harness.orchestra.lanes import load_lane
        worker = F.FakeWorker()

        def runner(argv, cwd=None, env=None, **kw):
            if hold is not None:
                hold.wait(30)
            lane = load_lane(env["HALO_ORCHESTRA_RUN"], int(env["HALO_ORCHESTRA_LANE"]))
            scope = Path(cwd) / ".halo"
            log.append({"cand": cand["id"], "kind": cand["kind"], "lane": lane.n, "argv": list(argv), "cwd": cwd,
                        "files": {p.relative_to(cwd).as_posix(): p.read_text(encoding="utf-8")
                                  for p in scope.rglob("*") if p.is_file()} if scope.is_dir() else {}})
            out = worker(lane)
            body = {"type": "result", "result": out["text"], "total_cost_usd": cost.get(cand["kind"], 0.002),
                    "session_id": out["session_id"]}
            return subprocess.CompletedProcess(argv, 0, json.dumps(body), "")
        return PR.real_adapters(probe_dir, goal, cand, f, seen, runner=runner)
    return make


def studio_probe(s, run_dir) -> dict:
    """POST orchestra/<run>/coach/probe on a Studio (tests/helpers/orchestra_studio_rig.Studio) with the fakes: the cost
    line, the start, a frame, a 409 while the workers are held, the end; what each answered."""
    import threading
    import time
    from halo_harness.orchestra import coach_probe, probe_runs
    from tests.helpers.orchestra_studio_rig import Reader
    rid, out, log, hold = run_dir.name, {}, [], threading.Event()
    saved = (probe_runs.ADAPTERS, os.environ.get("HALO_COACH_FAKE"))
    probe_runs.ADAPTERS, os.environ["HALO_COACH_FAKE"] = fake_adapters(log, hold=hold), "1"
    rd = Reader(f"{s.base}/api/events?t={s.srv.token}&sessions=all")
    try:
        out["cost"] = s.post(f"orchestra/{rid}/coach/probe", {})
        out["nothing_ran"] = not (run_dir / "probe.json").exists()
        out["start"] = s.post(f"orchestra/{rid}/coach/probe", {"confirm": True})
        out["frame"] = rd.wait(lambda k, f: k == "orchestra_state" and (f.get("data") or {}).get("probe_of") == rid, 10)
        out["again"] = s.post(f"orchestra/{rid}/coach/probe", {"confirm": True})
        out["live"] = (s.get(f"orchestra/{rid}/coach")[1].get("probe") or {}).get("live")
        hold.set()
        end = time.monotonic() + 90
        while coach_probe.live(run_dir) and time.monotonic() < end:
            time.sleep(0.1)
        out["done"] = rd.wait(lambda k, f: (f.get("data") or {}).get("probe_of") == rid and f["data"].get("step") == "done", 10)
        out["coach"], out["runs"] = s.get(f"orchestra/{rid}/coach")[1], s.get("orchestra/runs")[1]
    finally:
        hold.set()
        rd.close()
        probe_runs.ADAPTERS = saved[0]
        if saved[1] is None:
            os.environ.pop("HALO_COACH_FAKE", None)
        else:
            os.environ["HALO_COACH_FAKE"] = saved[1]
    return out


def ask(answer):
    """coach_probe.ASK answering `answer` (a dict is sent as JSON), recording each prompt."""
    prompts = []

    def call(prompt, model, cwd):
        prompts.append(prompt)
        return {"text": answer if isinstance(answer, str) else json.dumps(answer), "ok": True, "cost_usd": 0.0005}
    call.prompts = prompts
    return call


class Probe:
    def __init__(self, *, lineup: bool = False, bios: bool = True):
        self.lineup, self.bios, self.log = lineup, bios, []

    def __enter__(self):
        from halo_harness.orchestra import coach_compare, coach_probe, probe_runs
        from halo_harness.orchestra.lanes import load_lane
        from halo_harness.orchestra.run import run
        from tests.helpers import orchestra_fixtures as F
        from tests.helpers.coach_seed import seed_home
        self.saved = {k: os.environ.get(k) for k in ("BRIDGE_STATE_DIR", "HALO_COACH_FAKE")}
        self.seams = (probe_runs.ADAPTERS, coach_probe.ASK, coach_compare.JUDGE)
        self.root = Path(tempfile.mkdtemp(prefix="coach-probe-"))
        self.state = self.root / ".state"
        os.environ["BRIDGE_STATE_DIR"] = str(self.state)
        os.environ["HALO_COACH_FAKE"] = "1"
        seed_home(self.state)
        if self.lineup:
            from halo_harness.teams_yaml import save_team_template
            ok, problems = save_team_template("probe-line", {"description": "the probe's lineup", "agents": [
                {"agent": "coach-strong", "role": "main"}, {"agent": "coach-cheap", "role": "subagent"},
                {"agent": "coach-strong", "role": "subagent", "as": "helper"}]}, state_dir=self.state)
            assert ok, problems
        self.repo = F.make_repo("coach-probe-repo-")
        self.run_dir = F.make_run(self.repo, workers=2)
        if self.lineup:
            goal = json.loads((self.run_dir / "goal.json").read_text(encoding="utf-8"))
            (self.run_dir / "goal.json").write_text(json.dumps(dict(goal, lineup="probe-line")), encoding="utf-8")
        report = run(self.run_dir, model_calls=F.FakeLead(F.split_answer(GROUPS)), spawn=F.FakeWorker(), judge=F.FakeJudge())
        assert report["status"] == "finished", report.get("stop_reason")
        if self.bios:
            load_lane(self.run_dir, 1).update(bio="coach-cheap")
            load_lane(self.run_dir, 2).update(bio="coach-strong")
        probe_runs.ADAPTERS = fake_adapters(self.log)
        return self

    def __exit__(self, *a):
        from halo_harness.orchestra import coach_compare, coach_probe, probe_runs
        probe_runs.ADAPTERS, coach_probe.ASK, coach_compare.JUDGE = self.seams
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        from tests.helpers.orchestra_studio_rig import cleanup
        cleanup(self.repo)
        shutil.rmtree(self.root, ignore_errors=True)

    def git(self, *args) -> str:
        from tests.helpers import orchestra_fixtures as F
        return F.git(self.repo, *args)
