"""tests.test_orchestra_stale_lanes -- Halo 3.1.2.0 round R2: a stale
downstream lane is never merged stale (orchestra/stale.py, gate.py's loop
in run.py, merge.py), over a real temp git repo with the fixture's fakes
(tests/helpers/orchestra_fixtures.py; no model): five one-function lanes,
`total` (lane 5) after `subtotal` (lane 3), lane 3's first piece wrong.

1. The gate sends lane 3 back: lane 5 (it started from lane 3's head) is
   marked stale and waits with the reason; once lane 3 is written again it
   is re-based (lane 3's new head merged into its worktree, its tests run
   there) and merged; the run finishes.
2. The conflict path: lane 3's second piece also touches `total`, so the
   re-base conflicts: lane 5 goes back to its own worker with the retry
   text (a returned piece), its worker resolves it, the run finishes.
3. A run with no lane after another is unchanged: nothing is marked stale.
4. `merge_lanes` refuses a lane whose stale flag is still set.

Run: python -m tests.test_orchestra_stale_lanes
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers import orchestra_fixtures as F  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
WRONG = {"subtotal": ['    return Decimal("0")']}
TOTAL = "    return apply_discount(subtotal(basket), percent)"


def _answer(chain: bool = True) -> str:
    data = json.loads(F.split_answer([[f] for f in F.FUNCS]))
    if chain:
        data["jobs"][4]["after"] = ["job-3"]
    return json.dumps(data)


class TouchesTotal:
    """Lane 3's second pass also rewrites `total` (outside its claim), so lane 5's re-base conflicts."""

    def __init__(self, inner):
        self.inner, self.passes = inner, {}

    def __call__(self, lane):
        out = self.inner(lane)
        self.passes[lane.n] = self.passes.get(lane.n, 0) + 1
        if lane.n == 3 and self.passes[3] == 2:
            F.write_function(lane.worktree / "basket.py", "total", ["    return subtotal(basket)  # lane 3 was here"])
        return out


def _run(spawn, *, chain=True, judge=None):
    from halo_harness.orchestra.run import run
    repo = F.make_repo("orch-stale-")
    run_dir = F.make_run(repo)
    report = run(run_dir, model_calls=F.FakeLead(_answer(chain)), spawn=spawn, judge=judge or F.FakeJudge())
    return repo, run_dir, report


def _lane(run_dir, n: int) -> dict:
    return json.loads((run_dir / "lanes" / f"{n}.json").read_text(encoding="utf-8"))


def _events(run_dir) -> list:
    from halo_harness.orchestra.events import read
    return read(run_dir)


@test
def test_sent_back_marks_the_downstream_stale_then_it_is_rebased_and_merged(ctx: Ctx):
    worker = F.FakeWorker(wrong=WRONG)
    repo, run_dir, report = _run(worker)
    ctx.check(f"the run finished, got {report['status']} {report.get('stop_reason')}", report["status"] == "finished")
    texts = [e["text"] for e in _events(run_dir)]
    ctx.check(f"lane 5 was marked stale naming its upstream, got {[t for t in texts if 'stale' in t]}",
              "lane 5 is stale: upstream job-3 was sent back" in texts)
    five = _lane(run_dir, 5)
    waits = [h for h in five["history"] if h["state"] == "waiting" and "stale" in h["text"]]
    ctx.check(f"it waited with the reason, got {[h['text'] for h in waits]}", len(waits) == 1
              and waits[0]["text"].startswith("stale: upstream job-3 was sent back"))
    head3 = _lane(run_dir, 3)["head"]
    rebased = five.get("rebased") or {}
    ctx.check(f"then re-based onto lane 3's new head, got {rebased}", rebased.get("onto", [{}])[0].get("lane") == 3
              and rebased["onto"][0]["head"] == head3 and rebased.get("tests_ok") is True and not five.get("stale"))
    line = next((t for t in texts if t.startswith("lane 5 re-based onto lane 3's new head")), "")
    ctx.check(f"the re-base line is in the run log, got {line!r}", head3[:12] in line)
    ctx.check("lane 5's branch holds lane 3's new head, and both are merged",
              F.git(repo, "merge-base", "--is-ancestor", head3, five["branch"]) == ""
              and five["state"] == "merged" and _lane(run_dir, 3)["state"] == "merged")
    final = F.git(repo, "show", f"orchestra/{run_dir.name}:basket.py")
    ctx.check("the finished branch has the fixed subtotal and lane 5's total",
              F.SOLUTIONS["subtotal"][0] in final and TOTAL in final)
    from halo_harness.work.store import UnitStore
    ctx.check("the lane units carry it in extra", UnitStore(run_dir).unit("5").extra.get("rebased", {}).get("tests_ok") is True)


@test
def test_a_rebase_conflict_returns_the_piece_to_its_worker(ctx: Ctx):
    inner = F.FakeWorker(wrong=WRONG)
    spawn = TouchesTotal(inner)
    repo, run_dir, report = _run(spawn, judge=F.FakeJudge(TOTAL))
    ctx.check(f"the run finished, got {report['status']} {report.get('stop_reason')}", report["status"] == "finished")
    five = _lane(run_dir, 5)
    retry = [t for n, t in inner.calls if n == 5 and t]
    ctx.check(f"lane 5 went back to its own worker with the retry text, got {[t[:80] for t in retry]}",
              len(retry) == 1 and "conflict markers are in those files" in retry[0] and "basket.py" in retry[0]
              and five["pieces_returned"] == 1)
    ctx.check(f"the conflict is recorded, the flag cleared, got {five.get('rebased')}",
              five.get("rebased", {}).get("conflict") == ["basket.py"] and not five.get("stale") and five["state"] == "merged")
    texts = [e["text"] for e in _events(run_dir)]
    ctx.check("the run log says the piece went back", any(t.startswith("lane 5: re-base onto lane 3's new head: conflict in basket.py")
                                                           for t in texts))
    final = F.git(repo, "show", f"orchestra/{run_dir.name}:basket.py")
    ctx.check("the finished branch has lane 5's total and no marker", TOTAL in final and "<<<<<<<" not in final)


@test
def test_a_run_with_no_downstream_lanes_is_unchanged(ctx: Ctx):
    repo, run_dir, report = _run(F.FakeWorker(wrong=WRONG), chain=False)
    ctx.check(f"the run finished, got {report['status']} {report.get('stop_reason')}", report["status"] == "finished")
    lanes = [_lane(run_dir, n) for n in range(1, 6)]
    ctx.check("lane 3 went back once and nothing was marked stale or re-based",
              lanes[2]["pieces_returned"] >= 1 and not any(x.get("stale") or x.get("rebased") for x in lanes)
              and not any("stale" in e["text"] or "re-base" in e["text"] for e in _events(run_dir)))
    ctx.check("the lane files keep R1's keys (no stale / rebased key added)",
              all("stale" not in x and "rebased" not in x for x in lanes))


@test
def test_merge_refuses_a_lane_still_marked_stale(ctx: Ctx):
    from halo_harness.orchestra.goal import load_goal
    from halo_harness.orchestra.lanes import list_lanes
    from halo_harness.orchestra.merge import merge_lanes
    from halo_harness.orchestra.split import StopRun, load_split
    repo, run_dir, report = _run(F.FakeWorker(), chain=True)
    lanes = list_lanes(run_dir)
    lanes[4].update(stale={"upstreams": [3], "jobs": ["job-3"], "reason": "upstream job-3 was sent back"})
    try:
        merge_lanes(run_dir, load_goal(run_dir / "goal.json"), lanes, judge=F.FakeJudge(), base=load_split(run_dir)["base"])
        why = ""
    except StopRun as e:
        why = str(e)
    ctx.check(f"StopRun names the lane and the reason, got {why!r}",
              why == "lane 5 is stale (upstream job-3 was sent back): it is re-based before it merges")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="orchestra stale lane tests"))
