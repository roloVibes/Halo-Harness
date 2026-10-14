"""tests.test_orchestra_run -- Halo 3.0.3.0 round R2: the run pipeline end to
end (orchestra/run.py), over a real temp git repo holding the reel's
basket.py (five functions raising NotImplementedError) and test_basket.py.
The lead, the workers and the judge are fakes; git and the tests are real.

1. Five lanes: five worktrees, five `--no-ff` merges in the decided order,
   tests pass, every report check true, lanes/merge/workflow/report shapes,
   events in order with `elapsed_s` never going back.
2. Two lanes both change line 2's `from decimal import ...`: a conflict, a
   fake fresh judge returns the combined import, applied by code, tests
   pass; merge.json records it and `reviewer_fresh` is true.
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

CONFLICT_TEST = ("{py} -m unittest -q test_basket.BasketTest.test_apply_discount test_basket.BasketTest.test_total "
                 "test_basket.BasketTest.test_subtotal")


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@test
def test_five_lanes_end_to_end(ctx: Ctx):
    from halo_harness.orchestra import events as E
    from halo_harness.orchestra.gitops import merges_on
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo)
    base = F.git(repo, "rev-parse", "HEAD").strip()
    worker = F.FakeWorker()
    seen = []
    report = run(run_dir, model_calls=F.FakeLead(F.split_answer([[f] for f in F.FUNCS])), spawn=worker,
                 judge=F.FakeJudge(), on_event=seen.append)
    ctx.check(f"finished, got {report['status']} {report.get('stop_reason')}", report["status"] == "finished")
    ctx.check("every worker ran once", sorted(n for n, _ in worker.calls) == [1, 2, 3, 4, 5])
    trees = F.git(repo, "worktree", "list")
    ctx.check("five worker worktrees plus the merge tree",
              all(f"worker-{n}" in trees for n in range(1, 6)) and "merge" in trees)
    branch = f"orchestra/{run_dir.name}"
    merges = merges_on(repo, branch, base)
    ctx.check(f"five merges on {branch}, got {len(merges)}", len(merges) == 5)
    ctx.check("merged in the decided order (split order)",
              [m[1] for m in merges] == [f"orchestra: merge worker {n} (write {f})" for n, f in enumerate(F.FUNCS, 1)])
    ctx.check("--no-ff: each merge commit has two parents",
              all(len(F.git(repo, "rev-list", "--parents", "-n", "1", sha).split()) == 3 for sha, _ in merges))
    checks = {c["id"]: c["ok"] for c in report["checks"]}
    ctx.check(f"every check true, got {checks}",
              all(checks[k] is True for k in checks if k != "goal_done_when") and checks["goal_done_when"] is None)
    ctx.check("the report names the finished sha and branch",
              report["finished"] == F.git(repo, "rev-parse", branch).strip() and report["branch"] == branch)
    ctx.check("cost: lead 0.001 + five workers 0.002", abs(report["cost_usd"] - 0.011) < 1e-9)
    ctx.check("the finished file has all five functions written",
              "NotImplementedError" not in F.git(repo, "show", f"{branch}:basket.py"))
    lane = _read(run_dir / "lanes" / "3.json")
    for key in ("state", "holder", "cost_usd", "started", "ended", "pieces_returned", "written", "history", "branch"):
        ctx.check(f"lanes/3.json has {key}", key in lane)
    ctx.check(f"lane 3 merged, held by its worker's session, got {lane['holder']}",
              lane["state"] == "merged" and lane["holder"].startswith("worker3-") and lane["holder"].endswith("/main"))
    ctx.check("lane history walks the states",
              [h["state"] for h in lane["history"]] == ["joined", "writing", "written", "in_review", "merged"])
    ctx.check("lane snapshot of its unit", lane["written"]["basket.py#subtotal"].startswith("def subtotal(basket):"))
    merge = _read(run_dir / "merge.json")
    ctx.check("merge.json shape", merge["order"] == [1, 2, 3, 4, 5] and merge["merged"] == [1, 2, 3, 4, 5]
              and merge["conflicts"] == [] and merge["finished"] == report["finished"] and merge["base"] == base)
    graph = _read(run_dir / "workflow.json")
    ctx.check("every workflow step done", {s["state"] for s in graph["steps"]} == {"done"})
    entries = E.read(run_dir)
    elapsed = [e["elapsed_s"] for e in entries]
    ctx.check("elapsed_s never goes back", elapsed == sorted(elapsed))
    ctx.check("on_event saw every line", len(seen) == len(entries))
    texts = [e["text"] for e in entries if e["kind"] == "state" and e["data"].get("step") in
             ("goal", "lead", "split", "merge", "test", "gate", "done") and "state" in e["data"]]
    order = [t.split()[0] for t in texts]
    firsts = [s for i, s in enumerate(order) if s not in order[:i]]
    ctx.check(f"steps in pipeline order, got {firsts}", firsts == ["goal", "lead", "split", "merge", "test", "gate", "done"])
    ctx.check("the last line is the report", entries[-1]["kind"] == "report" and "run finished" in entries[-1]["text"])
    ctx.check("report.json written", _read(run_dir / "report.json")["status"] == "finished")
    again = run(run_dir, model_calls=None, spawn=None, judge=None)
    ctx.check("a finished run returns its report without running again", again["finished"] == report["finished"])


@test
def test_import_conflict_goes_to_a_fresh_judge(ctx: Ctx):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo, workers=2, test=CONFLICT_TEST.format(py=F.PY))
    judge = F.FakeJudge(F.COMBINED_IMPORT)
    report = run(run_dir, model_calls=F.FakeLead(F.split_answer([["apply_discount"], ["subtotal", "total"]])),
                 spawn=F.FakeWorker(F.CONFLICT_SOLUTIONS, F.CONFLICT_IMPORTS), judge=judge)
    ctx.check(f"finished, got {report.get('stop_reason')}", report["status"] == "finished")
    ctx.check("one judge call, for basket.py", len(judge.calls) == 1 and judge.calls[0]["file"] == "basket.py")
    hunk = judge.calls[0]["hunks"][0]
    ctx.check(f"the hunk carries both versions and the base, got {hunk}",
              hunk["ours"] == F.CONFLICT_IMPORTS["apply_discount"] and hunk["theirs"] == F.CONFLICT_IMPORTS["total"]
              and hunk["base"] == "from decimal import Decimal" and hunk["start_line"] == 2)
    branch = f"orchestra/{run_dir.name}"
    final = F.git(repo, "show", f"{branch}:basket.py").split("\n")
    ctx.check(f"line 2 is the judge's combined import, got {final[1]!r}", final[1] == F.COMBINED_IMPORT)
    ctx.check("no conflict markers left", not any(l.startswith(("<<<<<<<", ">>>>>>>")) for l in final))
    merge = _read(run_dir / "merge.json")
    row = merge["conflicts"][0]
    ctx.check("merge.json records the conflict",
              len(merge["conflicts"]) == 1 and row["lane"] == 2 and row["file"] == "basket.py"
              and row["judge_session"] == "judge-session-1" and row["resolution"] == F.COMBINED_IMPORT
              and row["applied_by"] == "code" and row["tests_ok"] is True and row["fresh"] is True)
    checks = {c["id"]: c for c in report["checks"]}
    ctx.check("reviewer_fresh true", checks["reviewer_fresh"]["ok"] is True)
    ctx.check("reviewer_applied_by_code_tests_pass true", checks["reviewer_applied_by_code_tests_pass"]["ok"] is True)
    ctx.check("record equals disk", checks["record_equals_disk"]["ok"] is True)
    ctx.check("judge cost counted", abs(report["cost_usd"] - (0.001 + 0.004 + 0.0005)) < 1e-9)


@test
def test_the_judge_prompt_is_the_goal_and_the_hunks_only(ctx: Ctx):
    from halo_harness.orchestra.goal import Goal
    from halo_harness.orchestra.hunks import extract_hunks, judge_prompt
    text = "a\n<<<<<<< HEAD\nx1\n||||||| base\nx0\n=======\nx2\n>>>>>>> w2\nb\n"
    prompt = judge_prompt(extract_hunks(text), Goal(what="WANT", done_when="DONE", stop_when="S"), "f.py")
    ctx.check("goal, file and the three versions are there",
              all(s in prompt for s in ("GOAL: WANT", "DONE WHEN: DONE", "FILE: f.py", "x1", "x0", "x2")))
    ctx.check("nothing outside the hunk is sent", "\na\n" not in prompt and "\nb\n" not in prompt)


@test
def test_reviewer_fresh_is_false_for_a_judge_with_history(ctx: Ctx):
    from halo_harness.orchestra.report import _reviewer_checks
    rows = [{"lane": 2, "file": "f", "judge_session": "j1", "fresh": False, "messages_before": 4,
             "applied_by": "code", "applied": True, "tests_ok": True}]
    fresh, applied = _reviewer_checks(rows, [], set())
    ctx.check("a judge that saw earlier messages is not fresh", fresh["ok"] is False and "with_history=1" in fresh["detail"])
    ctx.check("applied by code still true", applied["ok"] is True)
    reused = [dict(rows[0], fresh=True, messages_before=0), dict(rows[0], fresh=True, messages_before=0, file="g")]
    ctx.check("one session judging twice is not fresh", _reviewer_checks(reused, [], set())[0]["ok"] is False)
    lead = [dict(rows[0], fresh=True, messages_before=0)]
    ctx.check("the lead's own session is not fresh", _reviewer_checks(lead, [], {"j1"})[0]["ok"] is False)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
