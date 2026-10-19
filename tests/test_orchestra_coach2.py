"""tests.test_orchestra_coach2 -- Halo 3.0.9.0 round R3: the coach's cache, its
three CLI verbs and the evidence the engine now records for it:

1. a real run (the R2 fixture, fake lead / workers / judge) whose lane 2
   worker's result names a model and a denied tool call: lanes/2.json keeps
   `model` and `denied`, events.jsonl a `note` line; a refused claim is a
   `claim` line with op `refused` (the lane from $HALO_ORCHESTRA_LANE); the
   coach reads that run; the worker adapter (`spawn_worker`) passes the
   result's `model` and `permission_denials` on;
2. a bio's `context.prompt_notes` reach its prompt (after `system_prompt`);
3. `coach.cached` keeps coach.json and computes again when a run file is newer;
4. `halo orchestra coach`, `halo fleet mission coach`,
   `halo team coach` print the card (and `--json`); an unknown run exits 1.
Run: python -m tests.test_orchestra_coach2
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_orchestra_coach import Home

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _cli(fn, argv):
    o, e = io.StringIO(), io.StringIO()
    with redirect_stdout(o), redirect_stderr(e):
        rc = fn(argv)
    return rc, o.getvalue(), e.getvalue()


@test
def test_the_engine_records_the_coach_s_evidence(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    from tests.helpers.orchestra_studio_rig import cleanup
    repo = F.make_repo("orch-coach-")
    run_dir = F.make_run(repo)
    worker = F.FakeWorker()

    def spawn(lane):
        res = worker(lane)
        if lane.n == 2:
            res.update(model="or:vendor/cheap", denied=[{"tool_name": "WebFetch", "tool_input": {"url": "x"},
                                                         "reason": "denied by rule 'WebFetch'"}])
        return res
    try:
        with Home() as h:
            report = run(run_dir, model_calls=F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), spawn=spawn, judge=F.FakeJudge())
            ctx.check(f"the run finished, got {report.get('stop_reason')}", report["status"] == "finished")
            two, one = _read(run_dir / "lanes" / "2.json"), _read(run_dir / "lanes" / "1.json")
            ctx.check(f"lane 2 keeps its model and the denied call, got {two.get('model')} {two.get('denied')}",
                      two["model"] == "or:vendor/cheap" and two["denied"] == [{"tool_name": "WebFetch", "reason": "denied by rule 'WebFetch'"}])
            ctx.check("lane 1: no bio, no model named, nothing denied", one["bio"] == "" and one["model"] == "" and one["denied"] == [])
            notes = [e for e in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines() if '"denied": true' in e]
            ctx.check(f"one note line for the denied call, got {notes}", len(notes) == 1 and '"lane": 2' in notes[0])
            log = ClaimLog(run_dir)
            ctx.check("a holds the unit", log.claim("a/main", "basket.py#total").ok)
            os.environ["HALO_ORCHESTRA_LANE"] = "3"
            try:
                ctx.check("b is refused", not log.claim("b/main", "basket.py#total").ok)
            finally:
                os.environ.pop("HALO_ORCHESTRA_LANE", None)
            last = json.loads((run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            ctx.check(f"the refusal is a claim line, got {last}", last["kind"] == "claim" and last["data"]["op"] == "refused"
                      and last["data"]["by"] == "a/main" and last["data"]["lane_n"] == 3 and last["data"]["key"] == "basket.py#total")
            res = h.coach(run_dir)
            ids = [s["id"] for s in res["suggestions"]]
            ctx.check(f"the coach reads the real run: the denied call and lane 3's refused claim, got {ids}",
                      "tools-2-WebFetch" in ids and "tools-3-claim-basket.py#total" in ids)
            ctx.check("five lanes in the evidence", len(res["evidence"]["lanes"]) == 5)
    finally:
        cleanup(repo)


@test
def test_the_worker_adapter_reads_the_model_and_the_denials(ctx: Ctx):
    import subprocess
    import tempfile
    from halo_harness.orchestra.adapters import spawn_worker
    from halo_harness.orchestra.lanes import Lane
    from halo_harness.orchestra.split import Job
    run_dir = Path(tempfile.mkdtemp(prefix="orch-coach-adapt-"))
    lane = Lane(run_dir, 1, Job("job-1", "t", ["basket.py#total"], 1, 1), "b", run_dir / "wt" / "worker-1")
    lane.prompt = "write total"

    def runner(argv, **kw):
        out = json.dumps({"type": "result", "is_error": False, "result": "done", "session_id": "s-1", "total_cost_usd": 0.001,
                          "model": "or:vendor/cheap", "permission_denials": [{"tool_name": "Bash", "tool_input": {}, "reason": "r"}]})
        return subprocess.CompletedProcess(argv, 0, out + "\n", "")
    res = spawn_worker(None, run_dir=run_dir, runner=runner)(lane)
    ctx.check(f"the model and the denials come back, got {res}", res["model"] == "or:vendor/cheap"
              and res["denied"] == [{"tool_name": "Bash", "tool_input": {}, "reason": "r"}])

@test
def test_prompt_notes_reach_the_bio_s_prompt(ctx: Ctx):
    from halo_harness.agents_yaml import save_agent_bio
    from halo_harness.teams_yaml import member_system_context_addition
    with Home() as h:
        ok, problems = save_agent_bio("noted", {"description": "x", "context": {"system_prompt": "You are terse.",
                                                                               "prompt_notes": "Run the tests first."}},
                                      state_dir=h.state)
        ctx.check(f"the bio saves, got {problems}", ok)
        text = member_system_context_addition("noted", team_name="", cwd=h.root, state_dir=h.state)
        ctx.check(f"the notes follow the prompt, got {text!r}", text.index("You are terse.") < text.index("Run the tests first."))


@test
def test_the_cache_and_its_refresh(ctx: Ctx):
    from halo_harness.orchestra.coach import cached
    from tests.helpers import coach_seed as S
    with Home() as h:
        run_dir = S.orchestra_run(h.root, [S.lane(1, written={}, state="merged")])
        first = cached(run_dir, catalog=S.CATALOG, state_dir=h.state)
        ctx.check(f"computed and kept, got {first.get('cached')}", first["cached"] is False and (run_dir / "coach.json").is_file()
                  and [s["id"] for s in first["suggestions"]] == ["structure-1-drop"])
        again = cached(run_dir, catalog=S.CATALOG, state_dir=h.state)
        ctx.check("read back from coach.json", again["cached"] is True and again["suggestions"] == first["suggestions"])
        S.write(run_dir / "lanes" / "1.json", S.lane(1))
        later = time.time() + 5
        os.utime(run_dir / "lanes" / "1.json", (later, later))
        fresh = cached(run_dir, catalog=S.CATALOG, state_dir=h.state)
        ctx.check(f"a newer run file computes again, got {fresh.get('cached')} {fresh['suggestions']}",
                  fresh["cached"] is False and fresh["suggestions"] == [])


@test
def test_the_three_cli_verbs_print_the_card(ctx: Ctx):
    from halo_harness.fleet.cli import cmd_fleet
    from halo_harness.orchestra_cli import cmd_orchestra
    from halo_harness.team.cli import cmd_team
    from tests.helpers import coach_seed as S
    with Home() as h:
        S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=[{"tool_name": "WebFetch", "reason": "denied by rule"}])])
        rc, out, err = _cli(cmd_orchestra, ["coach", "--repo", str(h.root)])
        ctx.check(f"orchestra: the card, got {rc} {out!r} {err!r}", rc == 0 and f"coach: orchestra run {S.RUN}: 1 suggestion" in out
                  and "[high] tools · 1 (bio coach-deny)" in out and "apply: bio coach-deny: tools.deny = Agent" in out
                  and "    - lane 1: WebFetch denied 1 time(s)" in out)
        rc, out, _ = _cli(cmd_orchestra, ["coach", S.RUN, "--json", "--repo", str(h.root)])
        ctx.check("orchestra --json", rc == 0 and json.loads(out)["suggestions"][0]["id"] == "tools-1-WebFetch")
        ctx.check("an unknown run exits 1", _cli(cmd_orchestra, ["coach", "nope", "--repo", str(h.root)])[0] == 1)
        mission = S.mission_folder(h.state)
        rc, out, _ = _cli(cmd_fleet, ["mission", "coach", mission.name])
        ctx.check(f"mission: the card, got {rc} {out[:200]!r}", rc == 0 and "coach: mission run m-20261017-c0a1: 5 suggestions" in out)
        ctx.check("an unknown mission exits 1", _cli(cmd_fleet, ["mission", "coach", "m-20261017-ffff"])[0] == 1)
        S.team_run(h.root)
        here = os.getcwd()
        os.chdir(h.root)
        try:
            rc, out, err = _cli(cmd_team, ["coach"])
            ctx.check(f"team: the card, got {rc} {out[:200]!r} {err!r}", rc == 0 and "coach: team run" in out and "looped 2 times" in out)
            ctx.check("team coach --help", _cli(cmd_team, ["coach", "--help"])[0] == 0)
        finally:
            os.chdir(here)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="orchestra coach cli tests"))
