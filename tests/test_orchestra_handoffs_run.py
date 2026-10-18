"""tests.test_orchestra_handoffs_run -- Halo 3.0.9.0 round R1: lanes with
two upstreams and goal.json's pre-declared hand-offs, over the R2 fixture
(basket.py, real git; the lead, workers and judge are fakes).

1. Lane 3 takes `all` from lanes 1 and 2: it starts from the merge of their
   heads (a scratch branch, both heads its parents) and its prompt carries
   both summaries and both lanes' written keys.
2. The two heads conflict (both change line 2's import): lane 3 stays
   `waiting` with the reason, never runs, and the run stops naming it.
3. goal.json's `handoffs: {job-2: {after: [job-1]}}` over a lead that
   declares nothing: lane 2 starts from lane 1's head, and with no `needs`
   its prompt has no Hand-offs section.

Run: python -m tests.test_orchestra_handoffs_run
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

KEYS = {f: f"basket.py#{f}" for f in ("add_item", "remove_item", "subtotal", "apply_discount", "total")}


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _answer(jobs: list) -> str:
    return json.dumps({"jobs": jobs})


@test
def test_two_upstreams_start_from_the_merge_of_their_heads(ctx: Ctx):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo, workers=3)
    answer = _answer([{"title": "write add_item", "claims": [KEYS["add_item"]]},
                      {"title": "write remove_item", "claims": [KEYS["remove_item"]]},
                      {"title": "write the totals", "claims": [KEYS["subtotal"], KEYS["apply_discount"], KEYS["total"]],
                       "handoff": {"needs": [{"from": "job-1", "take": "all"}, {"from": "job-2", "take": "all"}]}}])
    worker = F.Recorder(F.FakeWorker(), texts={1: "ONE: add_item done", 2: "TWO: remove_item done"})
    report = run(run_dir, model_calls=F.FakeLead(answer), spawn=worker, judge=F.FakeJudge())
    ctx.check(f"finished, got {report['status']} {report.get('stop_reason')}", report["status"] == "finished")
    l1, l2, l3 = (_read(run_dir / "lanes" / f"{n}.json") for n in (1, 2, 3))
    parents = F.git(repo, "rev-list", "--parents", "-n", "1", l3["base"]).split()[1:]
    ctx.check(f"lane 3's base is a merge of both heads, got {parents}", sorted(parents) == sorted([l1["head"], l2["head"]])
              and worker.seen[3]["head"] == l3["base"])
    ctx.check("the scratch branch keeps the merge", F.git(repo, "rev-parse", f"orchestra/{run_dir.name}-base-3").strip() == l3["base"])
    p3 = worker.seen[3]["prompt"]
    ctx.check("both summaries and both lanes' keys are in lane 3's prompt",
              "ONE: add_item done" in p3 and "TWO: remove_item done" in p3 and f"`{KEYS['add_item']}`" in p3
              and f"`{KEYS['remove_item']}`" in p3)
    ctx.check("lanes 1 and 2 see nothing of each other", "Hand-offs" not in worker.seen[1]["prompt"] + worker.seen[2]["prompt"])
    ctx.check(f"lane 3 sits in layer 1, got {_read(run_dir / 'workflow.json')['layers']}",
              _read(run_dir / "workflow.json")["layers"] == [[1, 2], [3]])
    final = F.git(repo, "show", f"orchestra/{run_dir.name}:basket.py")
    ctx.check("the finished branch has every function", "NotImplementedError" not in final)


@test
def test_heads_that_conflict_leave_the_lane_waiting_and_stop_the_run(ctx: Ctx):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo, workers=3)
    answer = _answer([{"title": "write apply_discount", "claims": [KEYS["apply_discount"]]},
                      {"title": "write total", "claims": [KEYS["total"]]},
                      {"title": "write the rest", "claims": [KEYS["add_item"], KEYS["remove_item"], KEYS["subtotal"]],
                       "after": ["job-1", "job-2"]}])
    worker = F.Recorder(F.FakeWorker(F.CONFLICT_SOLUTIONS, F.CONFLICT_IMPORTS))
    report = run(run_dir, model_calls=F.FakeLead(answer), spawn=worker, judge=F.FakeJudge())
    l3 = _read(run_dir / "lanes" / "3.json")
    ctx.check(f"stopped on lane 3, got {report['status']} {report.get('stop_reason')}",
              report["status"] == "stopped" and "lane 3 waits" in report["stop_reason"]
              and "do not merge" in report["stop_reason"] and "basket.py" in report["stop_reason"])
    ctx.check(f"lane 3 is waiting with the reason and never ran, got {l3['state']} / {sorted(worker.seen)}",
              l3["state"] == "waiting" and "do not merge" in l3["history"][-1]["text"] and 3 not in worker.seen
              and l3["base"] == "")
    graph = _read(run_dir / "workflow.json")
    states = {s["id"]: s["state"] for s in graph["steps"]}
    ctx.check(f"workers 1 and 2 done, worker 3 never started, got {states}",
              states["worker-1"] == states["worker-2"] == "done" and states["worker-3"] == "pending")
    ctx.check("no merge was started", not (run_dir / "merge.json").exists())


@test
def test_goal_json_predeclares_an_after_only_lane(ctx: Ctx):
    from halo_harness.orchestra.goal import Goal, new_run
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    goal = Goal(what="Write the five functions of basket.py", done_when="the tests pass", stop_when="two returns",
                workers=2, test=f"{F.PY} -m unittest -q test_basket", files=["basket.py"], test_timeout_s=60,
                handoffs={"job-2": {"after": ["job-1"]}})
    run_dir = new_run(repo, goal)
    ctx.check("goal.json keeps the hand-offs", _read(run_dir / "goal.json")["handoffs"] == {"job-2": {"after": ["job-1"]}})
    worker = F.Recorder(F.FakeWorker())
    report = run(run_dir, model_calls=F.FakeLead(F.split_answer([["add_item", "remove_item"], ["subtotal", "apply_discount", "total"]])),
                 spawn=worker, judge=F.FakeJudge())
    ctx.check(f"finished, got {report.get('stop_reason')}", report["status"] == "finished")
    split = _read(run_dir / "split.json")
    ctx.check(f"split.json carries the goal's declaration, got {split['jobs'][1]}",
              split["jobs"][1]["after"] == ["job-1"] and "handoff" not in split["jobs"][1] and "after" not in split["jobs"][0])
    l1, l2 = _read(run_dir / "lanes" / "1.json"), _read(run_dir / "lanes" / "2.json")
    ctx.check("lane 2 starts from lane 1's head", l2["base"] == l1["head"] == worker.seen[2]["head"])
    ctx.check("with no needs, lane 2 sees nothing from lane 1", "Hand-offs" not in worker.seen[2]["prompt"]
              and worker.seen[2]["files"] == [])
    edges = [(e["from"], e["to"], e.get("label")) for e in _read(run_dir / "workflow.json")["edges"] if e["kind"] == "after"]
    ctx.check(f"the edge is labelled after, got {edges}", edges == [("worker-1", "worker-2", "after")])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
