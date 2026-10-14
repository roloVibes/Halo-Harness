"""tests.test_orchestra_workflow_goal -- Halo 3.0.3.0 round R1: the Orchestra's
designed graph (N worker lanes, the gate's loop edges, advance/loop_back/
ready), goal validation lines, the run folder `new_run` lays out, and
list_runs/latest_run/resolve_run. Every path is a fresh temp dir.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _raises(fn, exc=Exception) -> bool:
    try:
        fn()
    except exc:
        return True
    return False


def _goal(**over):
    from halo_harness.orchestra.goal import Goal
    base = dict(what="write basket.py", done_when="tests pass", stop_when="two returns", files=["basket.py"],
                test="python -m unittest")
    base.update(over)
    return Goal(**base)


@test
def test_designed_graph_has_one_lane_per_worker_and_loop_edges(ctx: Ctx):
    from halo_harness.orchestra.workflow import designed_graph, validate_graph
    g = designed_graph(3)
    ids = [s["id"] for s in g["steps"]]
    ctx.check(f"steps in order, got {ids}", ids == ["goal", "lead", "split", "worker-1", "worker-2", "worker-3",
                                                    "merge", "test", "gate", "done"])
    lanes = [s["lane"] for s in g["steps"] if s["kind"] == "worker"]
    ctx.check("worker lanes are 1..3", lanes == [1, 2, 3])
    ctx.check("every step starts pending", all(s["state"] == "pending" for s in g["steps"]))
    loops = [(e["from"], e["to"]) for e in g["edges"] if e["kind"] == "loop"]
    ctx.check(f"the gate loops back to each worker, got {loops}",
              loops == [("gate", "worker-1"), ("gate", "worker-2"), ("gate", "worker-3")])
    flows = {(e["from"], e["to"]) for e in g["edges"] if e["kind"] == "flow"}
    ctx.check("split fans out and workers merge",
              ("split", "worker-2") in flows and ("worker-2", "merge") in flows and ("gate", "done") in flows)
    ctx.check("JSON round trip is identical", json.loads(json.dumps(g)) == g)
    ctx.check("the graph validates clean", validate_graph(g) == [])
    ctx.check("50 workers is the top", len(designed_graph(50)["steps"]) == 57)
    ctx.check("0 and 51 workers raise", _raises(lambda: designed_graph(0), ValueError)
              and _raises(lambda: designed_graph(51), ValueError) and _raises(lambda: designed_graph(True), ValueError))


@test
def test_advance_ready_and_loop_back_are_pure(ctx: Ctx):
    from halo_harness.orchestra import workflow as W
    g = W.designed_graph(2)
    ctx.check("only the goal is ready at first", W.ready(g) == ["goal"])
    g2 = W.advance(g, "goal", "done")
    ctx.check("advance returns a new graph and leaves the old one", W.step(g, "goal")["state"] == "pending"
              and W.step(g2, "goal")["state"] == "done")
    ctx.check("lead is ready after the goal", W.ready(g2) == ["lead"])
    for sid in ("lead", "split"):
        g2 = W.advance(g2, sid, "done")
    ctx.check("both workers are ready after the split", W.ready(g2) == ["worker-1", "worker-2"])
    for sid in ("worker-1", "worker-2", "merge", "test"):
        g2 = W.advance(g2, sid, "done")
    g2 = W.advance(g2, "gate", "failed")
    back = W.loop_back(g2, 2)
    ctx.check("loop_back re-opens that worker and the steps behind it",
              W.step(back, "worker-2")["state"] == "pending" and W.step(back, "worker-1")["state"] == "done"
              and W.step(back, "gate")["state"] == "pending" and W.step(back, "merge")["state"] == "pending")
    ctx.check("the re-opened worker is ready again", W.ready(back) == ["worker-2"])
    ctx.check("summary counts states", W.summary(back) == {"done": 4, "pending": 5})
    ctx.check("unknown step / state raise", _raises(lambda: W.advance(g, "nope", "done"), KeyError)
              and _raises(lambda: W.advance(g, "goal", "finished"), ValueError))


@test
def test_validate_goal_lines_name_each_problem(ctx: Ctx):
    from halo_harness.orchestra.goal import validate_goal
    ctx.check("a full goal is clean", validate_goal(_goal()) == [])
    lines = validate_goal({"workers": 0, "return_cap": -1, "files": ["/abs/x.py", "../up.py", ""], "test": 5,
                           "colour": "red"})
    text = "\n".join(lines)
    for needle in ('"what" (WHAT YOU WANT) is required', '"done_when" (DONE WHEN) is required',
                   '"stop_when" (STOP WHEN) is required', '"workers" must be a whole number from 1 to 50',
                   '"return_cap" must be a whole number 0 or more', 'files[0]', 'files[1]', 'files[2]',
                   '"test" must be a string', 'unknown field(s): colour'):
        ctx.check(f"a line says {needle!r}", needle in text)
    ctx.check("defaults: 5 workers, return cap 2, lead main, worker subagent",
              (_goal().workers, _goal().return_cap, _goal().lead, _goal().worker) == (5, 2, "main", "subagent"))
    ctx.check("a non-object is one line", validate_goal([1]) == ["goal must be a JSON object"])


@test
def test_new_run_lays_out_the_folder(ctx: Ctx):
    from halo_harness.orchestra import goal as G
    repo = Path(tempfile.mkdtemp(prefix="orch-repo-"))
    run = G.new_run(repo, _goal(workers=3, files=["./src\\basket.py"]))
    ctx.check(f"under .halo/orchestra, got {run}", run.parent == repo / ".halo" / "orchestra")
    import re
    ctx.check(f"run id shape, got {run.name}", re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{4}", run.name) is not None)
    names = sorted(p.name for p in run.iterdir())
    ctx.check(f"the four files, got {names}", names == ["events.jsonl", "goal.json", "run.json", "workflow.json"])
    ctx.check("events.jsonl starts empty", (run / "events.jsonl").read_text(encoding="utf-8") == "")
    g = G.load_goal(run / "goal.json")
    ctx.check(f"files normalised, got {g.files}", g.files == ["src/basket.py"])
    wf = json.loads((run / "workflow.json").read_text(encoding="utf-8"))
    ctx.check("workflow.json is the designed graph for 3", wf["workers"] == 3 and len(wf["steps"]) == 10)
    meta = G.run_meta(run)
    ctx.check("run.json names the run and repo", meta["run_id"] == run.name
              and Path(meta["repo_root"]) == repo.resolve() and meta["lead_holder"] is None)
    ctx.check("the runs folder is git-ignored", "*" in (run.parent / ".gitignore").read_text(encoding="utf-8"))
    ctx.check("repo_root_of reads run.json", G.repo_root_of(run) == repo.resolve())
    G.set_lead_holder(run, "s1/main")
    ctx.check("set_lead_holder writes run.json", G.run_meta(run)["lead_holder"] == "s1/main")
    ctx.check("an invalid goal raises", _raises(lambda: G.new_run(repo, _goal(what="")), ValueError))


@test
def test_list_latest_and_resolve_runs(ctx: Ctx):
    from halo_harness.orchestra import goal as G
    repo = Path(tempfile.mkdtemp(prefix="orch-runs-"))
    ctx.check("no runs yet", G.list_runs(repo) == [] and G.latest_run(repo) is None)
    root = G.runs_root(repo)
    made = []
    for rid in ("20260101-000000-aaaa", "20260102-000000-bbbb", "20260103-000000-cccc"):
        d = root / rid
        d.mkdir(parents=True)
        G.save_goal(_goal(), d / "goal.json")
        made.append(d)
    (root / "stray").mkdir()
    ctx.check("oldest first, a folder without goal.json ignored", G.list_runs(repo) == made)
    ctx.check("latest is the newest", G.latest_run(repo) == made[-1])
    ctx.check("resolve by id, prefix, path, and empty", G.resolve_run(repo, made[0].name) == made[0]
              and G.resolve_run(repo, "20260102") == made[1] and G.resolve_run(repo, str(made[2])) == made[2]
              and G.resolve_run(repo, None) == made[-1])
    ctx.check("an ambiguous or unknown name is None", G.resolve_run(repo, "2026") is None
              and G.resolve_run(repo, "nope") is None)
    bad = Path(tempfile.mkdtemp(prefix="orch-bad-")) / "goal.json"
    bad.write_text('{"what": ""}', encoding="utf-8")
    ctx.check("load_goal names the problem", _raises(lambda: G.load_goal(bad), ValueError))


@test
def test_events_log_read_and_emit_to_the_session_feed(ctx: Ctx):
    from halo_harness import events as feed
    from halo_harness.orchestra import events as E
    from halo_harness.orchestra import goal as G
    run = G.new_run(Path(tempfile.mkdtemp(prefix="orch-ev-")), _goal())
    for kind in ("state", "claim", "merge", "gate", "report"):
        ctx.check(f"orchestra_{kind} is a registered feed kind", f"orchestra_{kind}" in feed.EVENT_KINDS)
    first = E.log(run, "state", "worker-1 running", lane=1, step="worker-1")
    ctx.check("a line has the schema", set(first) == {"ts", "elapsed_s", "lane", "kind", "text", "data"}
              and first["data"] == {"step": "worker-1"} and first["elapsed_s"] >= 0)
    ctx.check("an unknown kind raises", _raises(lambda: E.log(run, "chat", "x"), ValueError))
    got = []

    class _Session:
        _event_sink = staticmethod(got.append)

    E.emit(_Session(), "gate", {"text": "lane 2 failed", "lane": 2, "verdict": "fail"}, run_dir=run)
    E.emit(None, "note", {"text": "file only"}, run_dir=run)
    E.emit(got.append, "merge", {"text": "merged lane 1"}, run_dir=run)
    ctx.check("the session sink got orchestra_gate and orchestra_merge, not the note",
              [e.kind for e in got] == ["orchestra_gate", "orchestra_merge"])
    ctx.check("the feed event carries the log entry and the run", got[0].data["lane"] == 2
              and got[0].data["data"] == {"verdict": "fail"} and got[0].data["run"] == run.name)
    ctx.check("read returns all four, since skips", len(E.read(run)) == 4 and [e["kind"] for e in E.read(run, 2)]
              == ["note", "merge"])
    ctx.check("format_line shows time, lane, kind, text", "lane 2" in E.format_line(E.read(run)[1])
              and E.format_line(E.read(run)[1]).startswith("+"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
