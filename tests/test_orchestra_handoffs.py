"""tests.test_orchestra_handoffs -- Halo 3.0.9.0 round R1: Orchestra lanes
declare hand-offs (orchestra/handoff_spec.py) and get per-lane context
(orchestra/handoff.py, handoff_run.py).

1. Parse and validate: the lead's `handoff` / `after`, goal.json's
   `handoffs:`, every problem named (a job that is not there, a job that
   waits for itself, a cycle, a take nothing gives, a bad shape); a job that
   declares nothing keeps today's split.json shape.
2. Layering: designed_graph's `after` edges, `layer` and `layers`, `ready`
   honouring them; the undeclared graph is unchanged.
3. A two-lane chain over the R2 fixture (basket.py, real git, fake lead /
   workers / judge): lane 2 starts from lane 1's head and its prompt carries
   lane 1's summary and artifact (copied into its worktree, never
   committed); lane 3, with no needs, gets neither and starts from the split
   base; gave, base, after and handoff in lanes/<n>.json; merge in layer order.

Run: python -m tests.test_orchestra_handoffs
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

KEYS = [f"basket.py#{f}" for f in ("add_item", "remove_item", "subtotal", "apply_discount", "total")]
SUMMARY = "LANE-ONE-SUMMARY: add_item keeps one [price, qty] entry per name"


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@test
def test_parse_and_validate_the_declarations(ctx: Ctx):
    from halo_harness.orchestra.goal import validate_goal
    from halo_harness.orchestra.split import Job, job_handoffs, validate_jobs
    gives = {"gives": [{"name": "notes", "kind": "artifact", "paths": ["notes.txt"]}]}
    ok = {"jobs": [{"title": "a", "claims": [KEYS[0]], "handoff": gives},
                   {"title": "b", "claims": [KEYS[1]], "handoff": {"needs": [{"from": "job-1", "take": "notes"}]}},
                   {"title": "c", "claims": [KEYS[2]], "after": ["2"]}]}
    ctx.check(f"a valid chain passes, got {validate_jobs(ok, KEYS, 3)}", validate_jobs(ok, KEYS, 3) == [])
    resolved, _ = job_handoffs(ok["jobs"])
    ctx.check(f"refs become job ids, got {resolved}", resolved[1] == ({"needs": [{"from": "job-1", "take": "notes"}]}, [])
              and resolved[2] == ({}, ["job-2"]) and resolved[0][0] == gives)
    own = {"jobs": [{"id": "write", "title": "a", "claims": [KEYS[0]]},
                    {"title": "b", "claims": [KEYS[1]], "handoff": {"needs": [{"from": "write", "take": "summary"}]}}]}
    ctx.check("the lead's own id names a job", job_handoffs(own["jobs"])[0][1][0]["needs"][0]["from"] == "job-1")

    def problems(jobs, pre=None):
        return " | ".join(validate_jobs({"jobs": jobs}, KEYS, 5, pre))
    a = {"title": "a", "claims": [KEYS[0]]}
    got = problems([a, {"title": "b", "claims": [KEYS[1]], "after": ["job-9"]}])
    ctx.check(f"after names a real job, got {got}", "'job-9', which is not one of the jobs" in got)
    got = problems([a, {"title": "b", "claims": [KEYS[1]], "handoff": {"needs": [{"from": "job-2", "take": "all"}]}}])
    ctx.check(f"a job does not need itself, got {got}", "needs its own hand-off" in got)
    got = problems([dict(a, after=["job-2"]), {"title": "b", "claims": [KEYS[1]], "after": ["job-1"]}])
    ctx.check(f"a cycle is named, got {got}", "job-1 waits for itself" in got and "job-2 waits for itself" in got)
    got = problems([a, {"title": "b", "claims": [KEYS[1]], "handoff": {"needs": [{"from": "job-1", "take": "chart"}]}}])
    ctx.check(f"take names something the upstream gives, got {got}", "takes 'chart' from job-1" in got)
    got = problems([dict(a, handoff={"gives": [{"name": "x", "kind": "picture"}], "needs": [{"take": "all"}]})])
    ctx.check(f"bad shapes are named, got {got}", "kind 'picture'" in got and "must say which job it is from" in got)
    pre = {"job-2": {"needs": [{"from": "job-1", "take": "summary"}]}, "job-4": {"after": ["job-1"]}}
    got = problems([a, {"title": "b", "claims": [KEYS[1]]}], pre)
    ctx.check(f"goal.json's pre-declaration for a job the split lacks, got {got}", "'job-4', which this split does not have" in got)
    resolved, _ = job_handoffs([a, {"title": "b", "claims": [KEYS[1]], "after": ["job-1"]}], {"2": {"needs": [{"from": "1", "take": "all"}]}})
    ctx.check(f"the goal's declaration joins the lead's, got {resolved[1]}",
              resolved[1] == ({"needs": [{"from": "job-1", "take": "all"}]}, ["job-1"]))
    ctx.check("goal.json: handoffs must be a map", any("handoffs" in p for p in validate_goal(
        {"what": "w", "done_when": "d", "stop_when": "s", "handoffs": ["job-1"]})))
    ctx.check("goal.json: a bad entry is named", any("handoffs[job-2]" in p for p in validate_goal(
        {"what": "w", "done_when": "d", "stop_when": "s", "handoffs": {"job-2": {"needs": "job-1"}}})))
    plain = Job(id="job-1", title="t", claims=[KEYS[0]], worker=1, order=1)
    ctx.check(f"an undeclared job keeps today's shape, got {plain.to_dict()}",
              plain.to_dict() == {"id": "job-1", "title": "t", "claims": [KEYS[0]], "worker": 1, "order": 1}
              and Job.from_dict(plain.to_dict()) == plain and plain.upstreams == [])
    chained = Job(id="job-2", title="t", claims=[], worker=2, order=2, handoff={"needs": [{"from": "job-1", "take": "all"}]}, after=["job-3"])
    ctx.check("a declared job round-trips and lists its upstreams",
              Job.from_dict(chained.to_dict()) == chained and chained.upstreams == ["job-3", "job-1"])


@test
def test_layers_in_the_designed_graph(ctx: Ctx):
    from halo_harness.orchestra import workflow as W
    plain = W.designed_graph(3)
    ctx.check("undeclared: no layer, no layers, no after edge, split fans out to every worker",
              "layers" not in plain and all("layer" not in s for s in plain["steps"])
              and sum(1 for e in plain["edges"] if e["from"] == "split") == 3 and W.designed_graph(3, {}) == plain)
    g = W.designed_graph(3, {2: [1], 3: [1, 2]}, {(1, 2): "summary", (1, 3): "all"})
    after = [(e["from"], e["to"], e.get("label")) for e in g["edges"] if e["kind"] == "after"]
    ctx.check(f"after edges with their labels, got {after}",
              after == [("worker-1", "worker-2", "summary"), ("worker-1", "worker-3", "all"), ("worker-2", "worker-3", "after")])
    ctx.check(f"only lane 1 hangs off the split, got {g['layers']}",
              [e["to"] for e in g["edges"] if e["from"] == "split"] == ["worker-1"] and g["layers"] == [[1], [2], [3]]
              and [s.get("layer") for s in W.steps_of_kind(g, "worker")] == [0, 1, 2])
    ctx.check("the graph validates", W.validate_graph(g) == [])
    g = W.advance(W.advance(W.advance(g, "goal", "done"), "lead", "done"), "split", "done")
    ctx.check(f"ready: lane 1 first, got {W.ready(g)}", W.ready(g) == ["worker-1"])
    g = W.advance(g, "worker-1", "done")
    ctx.check(f"then lane 2 (lane 3 still waits for it), got {W.ready(g)}", W.ready(g) == ["worker-2"])
    g = W.advance(g, "worker-2", "done")
    ctx.check(f"then lane 3, got {W.ready(g)}", W.ready(g) == ["worker-3"])
    kept = W.with_layers(W.advance(W.designed_graph(2), "goal", "done"), {2: [1]})
    ctx.check("with_layers keeps the states", W.step(kept, "goal")["state"] == "done" and kept["layers"] == [[1], [2]])


@test
def test_a_two_lane_chain_hands_on_its_summary_and_artifact(ctx: Ctx):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo, workers=3)
    base = F.git(repo, "rev-parse", "HEAD").strip()
    answer = json.dumps({"jobs": [
        {"title": "write add_item", "claims": [KEYS[0]],
         "handoff": {"gives": [{"name": "notes", "kind": "artifact", "paths": ["notes.txt"]}, {"name": "summary", "kind": "summary"}]}},
        {"title": "write remove_item", "claims": [KEYS[1]],
         "handoff": {"needs": [{"from": "job-1", "take": "summary"}, {"from": "job-1", "take": "notes"}]}},
        {"title": "write the totals", "claims": KEYS[2:]}]})
    worker = F.Recorder(F.FakeWorker(), texts={1: SUMMARY}, artifacts={1: {"notes.txt": "entries are [Decimal, int]\n"}})
    report = run(run_dir, model_calls=F.FakeLead(answer), spawn=worker, judge=F.FakeJudge())
    ctx.check(f"finished, got {report['status']} {report.get('stop_reason')}", report["status"] == "finished")
    l1, l2, l3 = (_read(run_dir / "lanes" / f"{n}.json") for n in (1, 2, 3))
    ctx.check(f"lane 2 started from lane 1's head, got {worker.seen[2]['head'][:12]} vs {l1['head'][:12]}",
              l1["head"] and worker.seen[2]["head"] == l1["head"] == l2["base"])
    ctx.check("lanes 1 and 3 started from the split base", l1["base"] == base == l3["base"] == worker.seen[3]["head"])
    p2, p3 = worker.seen[2]["prompt"], worker.seen[3]["prompt"]
    ctx.check("lane 2's prompt has the Hand-offs section with lane 1's summary and artifact",
              "Hand-offs" in p2 and SUMMARY in p2 and ".halo/handoff/job-1/notes.txt" in p2)
    ctx.check(f"the artifact was in lane 2's worktree when it started, got {worker.seen[2]['files']}",
              worker.seen[2]["files"] == [".halo/handoff/job-1/notes.txt"])
    ctx.check("lane 3 (no needs) sees neither", "Hand-offs" not in p3 and SUMMARY not in p3 and "notes" not in p3
              and worker.seen[3]["files"] == [])
    ctx.check("lane 1 is asked to hand on its artifact", "Hand on" in worker.seen[1]["prompt"] and "notes.txt" in worker.seen[1]["prompt"])
    gave = {(g["name"], g["kind"]): g for g in l1["gave"]}
    ctx.check(f"lane 1 gave its artifact and its summary, got {l1['gave']}",
              set(gave) == {("notes", "artifact"), ("summary", "summary")} and gave[("notes", "artifact")]["path"] == "lanes/1/artifacts/notes.txt"
              and gave[("summary", "summary")]["bytes"] == len(SUMMARY))
    ctx.check(f"an undeclared lane gives its summary and its units, got {l3['gave']}",
              [g["kind"] for g in l3["gave"]] == ["summary", "files", "files", "files"] and l3["handoff"] == {} and l3["after"] == [])
    ctx.check(f"lane 2's record: after and the handoff as declared, got {l2['after']} {l2['handoff']}",
              l2["after"] == ["job-1"] and l2["handoff"]["needs"][1] == {"from": "job-1", "take": "notes"})
    ctx.check(f"lane 2 waited, then joined, got {[h['state'] for h in l2['history']][:3]}",
              [h["state"] for h in l2["history"]][:3] == ["waiting", "joined", "writing"])
    graph = _read(run_dir / "workflow.json")
    edges = [(e["from"], e["to"], e.get("label")) for e in graph["edges"] if e["kind"] == "after"]
    ctx.check(f"the workflow hangs lane 2 off lane 1, got {edges} {graph.get('layers')}",
              edges == [("worker-1", "worker-2", "summary + notes")] and graph["layers"] == [[1, 3], [2]]
              and {s["state"] for s in graph["steps"]} == {"done"})
    ctx.check(f"merge in layer order, got {_read(run_dir / 'merge.json')['order']}", _read(run_dir / "merge.json")["order"] == [1, 3, 2])
    branch = f"orchestra/{run_dir.name}"
    ctx.check("the hand-off copy was never committed",
              ".halo/handoff" not in F.git(repo, "ls-tree", "-r", "--name-only", branch))
    checks = {c["id"]: c["ok"] for c in report["checks"]}
    ctx.check(f"every check true, got {checks}", all(checks[k] is True for k in checks if k != "goal_done_when"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
