"""tests.test_orchestra_cli_run -- Halo 3.0.3.0 round R2: `halo orchestra run
[--dry-run] | lanes | report | stop` (orchestra_cli_run.py) over a prepared
run folder, the real adapters with their process/session seams faked
(adapters.py: the worker's argv, cwd and environment; the judge/lead
wiring), the worker joining its lane at session start (guard.py), the
OrchestraRelease snapshot, the headless `/orchestra` text and the TUI
panel. No model is called and no `halo` child is started.
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _cli(argv):
    from halo_harness.orchestra_cli import cmd_orchestra
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = cmd_orchestra(argv)
    return rc, out.getvalue(), err.getvalue()


def _fakes(F):
    return {"model_calls": F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), "spawn": F.FakeWorker(),
            "judge": F.FakeJudge()}


@contextlib.contextmanager
def _patched(module, **attrs):
    old = {k: getattr(module, k) for k in attrs}
    for k, v in attrs.items():
        setattr(module, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(module, k, v)


@test
def test_run_lanes_report_stop_over_a_run_folder(ctx: Ctx):
    from halo_harness.orchestra import adapters
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-cli-run-")
    run_dir = F.make_run(repo)
    rc, out, _ = _cli(["report", "--repo", str(repo)])
    ctx.check("no report before the run", rc == 1 and "no report yet" in out)
    rc, out, _ = _cli(["lanes", "--repo", str(repo)])
    ctx.check("no lanes before the run", rc == 0 and "no lanes yet" in out)
    with _patched(adapters, real_adapters=lambda run_dir, goal, model=None: _fakes(F)):
        rc, out, err = _cli(["run", run_dir.name, "--repo", str(repo)])
    ctx.check(f"run finishes with rc 0, got {rc} {err!r}", rc == 0)
    lines = out.splitlines()
    ctx.check("one line per step as it happens", any("split done" in l for l in lines)
              and any("lane 3 merged into" in l for l in lines) and any("gate done" in l for l in lines))
    ctx.check("then the report", "checks:" in out and "PASS  tests_pass_finished_branch" in out)
    rc, out, _ = _cli(["lanes", "--repo", str(repo)])
    ctx.check("lanes lists five merged lanes", rc == 0 and out.count(" merged ") == 5 and "basket.py#total" in out)
    rc, out, _ = _cli(["report", run_dir.name[:15], "--repo", str(repo)])
    ctx.check("report by id prefix", rc == 0 and out.startswith(f"run {run_dir.name}: finished"))
    rc, out, _ = _cli(["stop", "--reason", "owner stop", "--repo", str(repo)])
    ctx.check("stop writes stop.json", rc == 0 and json.loads((run_dir / "stop.json").read_text())["reason"] == "owner stop")
    rc, _, err = _cli(["lanes", "nope", "--repo", str(repo)])
    ctx.check("an unknown run is rc 1", rc == 1 and "no run named 'nope'" in err)


@test
def test_dry_run_prints_the_split_and_claims_nothing(ctx: Ctx):
    from halo_harness.orchestra import adapters
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-cli-dry-")
    run_dir = F.make_run(repo)
    seen = []
    lead = F.FakeLead(F.split_answer([["add_item", "remove_item"], ["subtotal", "apply_discount", "total"]]))
    with _patched(adapters, model_call=lambda model, role, cwd=None: (seen.append((model, role)) or lead)):
        rc, out, err = _cli(["run", "--dry-run", "--model", "or:some/model", "--repo", str(repo)])
    ctx.check(f"rc 0, got {rc} {err!r}", rc == 0)
    ctx.check("the lead's role and the --model ref reach the adapter", seen == [("or:some/model", "main")])
    ctx.check("two jobs printed with their claims", "2 job(s)" in out and "job-2  worker 2  write subtotal" in out
              and "basket.py#apply_discount" in out)
    ctx.check("nothing claimed, nothing split, no worktree", not (run_dir / "claims.jsonl").exists()
              and not (run_dir / "split.json").exists() and not (run_dir / "wt").exists())
    with _patched(adapters, model_call=lambda model, role, cwd=None: F.FakeLead('{"jobs": [{"title": "x", "claims": ["nope"]}]}')):
        rc, out, _ = _cli(["run", "--dry-run", "--repo", str(repo)])
    ctx.check("a bad split is shown with its problems, rc 1", rc == 1 and "'nope' is not a key" in out)


@test
def test_spawn_worker_argv_cwd_env_and_result(ctx: Ctx):
    from halo_harness.orchestra.adapters import spawn_worker
    from halo_harness.orchestra.lanes import Lane
    from halo_harness.orchestra.split import Job
    import tempfile
    run_dir = Path(tempfile.mkdtemp(prefix="orch-adapt-"))
    lane = Lane(run_dir, 3, Job("job-3", "t", ["basket.py#subtotal"], 3, 3), "b", run_dir / "wt" / "worker-3")
    lane.prompt = "write subtotal"
    got = {}

    def runner(argv, **kw):
        got.update(argv=argv, **kw)
        out = json.dumps({"type": "result", "is_error": False, "result": "done", "session_id": "s-3",
                          "total_cost_usd": 0.0042})
        return subprocess.CompletedProcess(argv, 0, "noise\n" + out + "\n", "")
    result = spawn_worker("or:cheap/model", run_dir=run_dir, runner=runner)(lane)
    argv = got["argv"]
    ctx.check("a fresh `halo -p` child", argv[1:3] == ["-m", "halo_harness"] and argv[3:5] == ["-p", "write subtotal"])
    ctx.check("json output, auto mode, the model", "--output-format" in argv and "json" in argv and "auto" in argv
              and argv[-2:] == ["--model", "or:cheap/model"])
    ctx.check("cwd is the lane's worktree", got["cwd"] == str(lane.worktree))
    ctx.check("the run and the lane are in its environment",
              got["env"]["HALO_ORCHESTRA_RUN"] == str(run_dir.resolve()) and got["env"]["HALO_ORCHESTRA_LANE"] == "3")
    ctx.check(f"the result is read back, got {result}", result == {"ok": True, "text": "done", "cost_usd": 0.0042,
                                                                    "session_id": "s-3", "error": ""})
    bad = spawn_worker(None, run_dir=run_dir, runner=lambda argv, **kw: subprocess.CompletedProcess(argv, 2, "", "boom"))(lane)
    ctx.check("no result is a failed worker with the reason", bad["ok"] is False and "boom" in bad["error"])


@test
def test_judge_and_lead_adapters_use_a_brand_new_session(ctx: Ctx):
    from halo_harness.orchestra import adapters
    from halo_harness.orchestra.goal import Goal
    calls = []

    def fake_one_shot(prompt, *, model, cwd):
        calls.append((prompt, model))
        return {"text": "merged line", "session_id": f"s{len(calls)}", "messages_before": 0, "cost_usd": 0.01}
    with _patched(adapters, one_shot=fake_one_shot):
        judge = adapters.fresh_judge("or:judge/model")
        hunks = [{"index": 1, "start_line": 2, "end_line": 8, "ours": "A", "base": "O", "theirs": "B"}]
        answer = judge(hunks, Goal(what="WANT", done_when="DONE", stop_when="S"), "basket.py")
        lead = adapters.model_call("or:lead/model")("split please")
    ctx.check("the judge's whole prompt is the goal and the hunk", calls[0][0].startswith("Two workers changed")
              and "GOAL: WANT" in calls[0][0] and "[incoming]\nB" in calls[0][0] and calls[0][1] == "or:judge/model")
    ctx.check("one session per call", answer["session_id"] == "s1" and lead["session_id"] == "s2")
    ctx.check("the role table is used when no --model", adapters.role_model("main", "or:x") == "or:x")


@test
def test_worker_session_joins_its_lane_and_release_snapshots(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    from halo_harness.orchestra.goal import load_goal, set_lead_holder
    from halo_harness.orchestra.guard import install_from_env
    from halo_harness.orchestra.run import goal_units
    from halo_harness.orchestra.split import split_goal
    from halo_harness.orchestra.workers import prepare_lane
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.orchestra_claims import OrchestraClaimTool, OrchestraReleaseTool
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-join-")
    run_dir = F.make_run(repo)
    set_lead_holder(run_dir, "orchestra/lead")
    goal = load_goal(run_dir / "goal.json")
    jobs = split_goal(run_dir, goal, goal_units(repo, goal), call_model=F.FakeLead(F.split_answer([["subtotal"]])),
                      base=F.git(repo, "rev-parse", "HEAD").strip())
    lane = prepare_lane(run_dir, jobs[0], F.git(repo, "rev-parse", "HEAD").strip())

    class Engine:
        guards: list = []
    sdir = Path(run_dir) / "fake-sessions" / "sess-w1"
    env = {"HALO_ORCHESTRA_RUN": str(run_dir), "HALO_ORCHESTRA_LANE": "1"}
    guard = install_from_env(Engine(), sdir, env=env)
    ctx.check("the guard is installed for the worker", guard is not None and guard.holder == "sess-w1/main")
    ctx.check("the worker took over lane 1's placeholder", ClaimLog(run_dir).active()["basket.py#subtotal"].holder
              == "sess-w1/main" and lane.holder == "sess-w1/main")
    tctx = ToolContext(cwd=lane.worktree, session_dir=sdir, env=env)
    ctx.check("its own claim renews", not OrchestraClaimTool().run({"key": "basket.py#subtotal"}, tctx).is_error)
    F.write_function(lane.worktree / "basket.py", "subtotal", F.SOLUTIONS["subtotal"])
    ClaimLog(run_dir).mark_writing("sess-w1/main", "basket.py#subtotal")
    res = OrchestraReleaseTool().run({"key": "basket.py#subtotal"}, tctx)
    ctx.check(f"released, got {res.content if hasattr(res, 'content') else res}", not res.is_error)
    snap = lane.written.get("basket.py#subtotal", "")
    ctx.check(f"the release stored the written snapshot, got {snap!r}",
              snap.startswith("def subtotal(basket):") and 'Decimal("0")' in snap)
    # a worker that edited and then died; the next session takes over and finds the unit written
    log = ClaimLog(run_dir)
    log.claim("sess-w1/main", "basket.py#subtotal")
    log.mark_writing("sess-w1/main", "basket.py#subtotal")
    sdir2 = sdir.parent / "sess-w2"
    install_from_env(Engine(), sdir2, env=env)
    tctx2 = ToolContext(cwd=lane.worktree, session_dir=sdir2, env=env)
    OrchestraClaimTool().run({"key": "basket.py#subtotal"}, tctx2)
    ctx.check("the takeover release still records the edit as written",
              not OrchestraReleaseTool().run({"key": "basket.py#subtotal"}, tctx2).is_error
              and [e["op"] for e in log.entries()][-2:] == ["written", "release"])


@test
def test_orchestra_slash_text_and_panel(ctx: Ctx):
    from halo_harness.commands.builtins import _BUILTIN_SPECS
    from halo_harness.orchestra.run import run
    from halo_harness.orchestra.view import panel_text, run_finder
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-panel-")
    ctx.check("no run yet", "No Orchestra run" in panel_text(run_finder(repo)()))
    run_dir = F.make_run(repo)
    run(run_dir, **_fakes(F))
    text = panel_text(run_finder(repo)())
    ctx.check("the text names the run, the steps and five lanes",
              text.startswith(f"run {run_dir.name}: finished") and "merge:done" in text and text.count("merged") >= 5)
    ctx.check("/orchestra is a registered built-in", "orchestra" in _BUILTIN_SPECS)
    from textual.app import App
    from halo_harness.tui.dialogs.orchestra import OrchestraPanel

    class _Host(App):
        def on_mount(self):
            self.push_screen(OrchestraPanel(lambda: run_dir))

    async def drive():
        app = _Host()
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            body = str(app.screen.query_one("#orchestra-body").render())
            await pilot.press("escape")
            await pilot.pause()
            return body, type(app.screen).__name__
    body, after = asyncio.run(drive())
    ctx.check("the panel shows the lanes", "lane 5" in body and "write total" in body)
    ctx.check("Esc closes it", after != "OrchestraPanel")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
