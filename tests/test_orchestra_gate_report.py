"""tests.test_orchestra_gate_report -- Halo 3.0.3.0 round R2: the gate's
test runner (timeout, tail, scrubbed env, unittest/pytest summaries), the
record-equals-disk check (true, false, judge-resolved), the gate's
narrowing of a failure to one lane, the conflict hunks (extract, parse,
apply), and report formatting. Real temp git repos; no model anywhere.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _goal(test: str, timeout: int = 60):
    from halo_harness.orchestra.goal import Goal
    return Goal(what="w", done_when="d", stop_when="s", test=test, test_timeout_s=timeout, files=["basket.py"])


def _script(tmp: Path, body: str) -> str:
    from tests.helpers.orchestra_fixtures import PY
    path = tmp / "t.py"
    path.write_text(body, encoding="utf-8")
    return f'{PY} "{path}"'


@test
def test_run_tests_timeout_kills_and_says_so(ctx: Ctx):
    import tempfile
    from halo_harness.orchestra.gate import run_tests
    tmp = Path(tempfile.mkdtemp(prefix="orch-gate-"))
    cmd = _script(tmp, "import time\nprint('started', flush=True)\ntime.sleep(60)\n")
    t0 = time.monotonic()
    result = run_tests(tmp, _goal(cmd, timeout=1), tmp)
    ctx.check(f"stopped well before the sleep ends ({time.monotonic() - t0:.1f}s)", time.monotonic() - t0 < 20)
    ctx.check("timed out, not ok, no exit code", result.timed_out and not result.ok and result.returncode is None)
    ctx.check(f"the tail keeps the output and the reason, got {result.tail!r}",
              "started" in result.tail and "ran past 1s" in result.tail)


@test
def test_run_tests_tail_and_scrubbed_env(ctx: Ctx):
    import tempfile
    from halo_harness.orchestra.gate import TAIL_LINES, run_tests
    tmp = Path(tempfile.mkdtemp(prefix="orch-gate-"))
    cmd = _script(tmp, "import os, sys\nfor i in range(100):\n    print('line', i)\n"
                       "print('RUN=' + os.environ.get('HALO_ORCHESTRA_RUN', '-'))\nsys.exit(3)\n")
    old = os.environ.get("HALO_ORCHESTRA_RUN")
    os.environ["HALO_ORCHESTRA_RUN"] = str(tmp)
    try:
        result = run_tests(tmp, _goal(cmd), tmp)
    finally:
        if old is None:
            os.environ.pop("HALO_ORCHESTRA_RUN", None)
        else:
            os.environ["HALO_ORCHESTRA_RUN"] = old
    lines = result.tail.splitlines()
    ctx.check(f"exit 3, not ok", result.returncode == 3 and not result.ok)
    ctx.check(f"only the last {TAIL_LINES} lines kept", len(lines) == TAIL_LINES and lines[0] == "line 61")
    ctx.check("the run variable never reaches the tests", lines[-1] == "RUN=-")
    empty = run_tests(tmp, _goal(""), tmp)
    ctx.check("no test command counts as passing", empty.ok and empty.command == "")


@test
def test_summary_parsers(ctx: Ctx):
    from halo_harness.orchestra.gate import TestResult, failing_tests, passed_count
    ut = ("ERROR: test_total (test_basket.BasketTest.test_total)\n----\nFAIL: test_subtotal (test_basket.BasketTest)\n"
          "Ran 5 tests in 0.01s\n\nFAILED (failures=1, errors=1)\n")
    ctx.check("unittest: passed = ran - failures - errors", passed_count(ut) == 3)
    ctx.check("unittest: failing names", failing_tests(ut) == ["test_subtotal (test_basket.BasketTest)",
                                                               "test_total (test_basket.BasketTest.test_total)"])
    ctx.check("unittest OK", passed_count("Ran 2 tests in 0.0s\n\nOK\n") == 2 and failing_tests("Ran 2 tests in 0s\n\nOK") == [])
    py = "FAILED test_b.py::test_total - assert 1 == 2\n==== 1 failed, 4 passed in 0.1s ===="
    ctx.check("pytest", passed_count(py) == 4 and failing_tests(py) == ["test_b.py::test_total"])
    ctx.check("no summary", passed_count("Traceback: SyntaxError") is None and failing_tests("boom") is None)
    before = TestResult(False, 1, "", "t", failing=["a", "b"])
    ctx.check("fewer failures is no worse", TestResult(False, 1, "", "t", failing=["a"]).no_worse_than(before))
    ctx.check("a new failure is worse", not TestResult(False, 1, "", "t", failing=["a", "c"]).no_worse_than(before))
    ctx.check("unreadable output is worse", not TestResult(False, 1, "", "t", failing=None).no_worse_than(before))


def _lanes_on_branch(final_text: str, snapshot: str, judged=False):
    from halo_harness.orchestra import jsonl
    from halo_harness.orchestra.lanes import Lane
    from halo_harness.orchestra.split import Job
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo("orch-record-")
    run_dir = F.make_run(repo)
    F.git(repo, "checkout", "-q", "-b", f"orchestra/{run_dir.name}")
    (repo / "basket.py").write_text(final_text, encoding="utf-8", newline="")
    F.git(repo, "commit", "-q", "-am", "finished")
    lane = Lane.create(run_dir, Job("job-1", "t", ["basket.py#subtotal"], 1, 1), branch="b", worktree=repo, started=0)
    lane.store_written("basket.py#subtotal", snapshot)
    if judged:
        jsonl.write_json(run_dir / "merge.json", {"conflicts": [{"lane": 1, "file": "basket.py", "tests_ok": True}]})
    return run_dir, [lane]


@test
def test_record_equals_disk_true_and_false(ctx: Ctx):
    from halo_harness.orchestra.gate import record_equals_disk
    from tests.helpers.orchestra_fixtures import SOLUTIONS, TEMPLATES, write_function
    import shutil
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="orch-rec-")) / "basket.py"
    shutil.copy(TEMPLATES / "basket.py", tmp)
    write_function(tmp, "subtotal", SOLUTIONS["subtotal"])
    text = tmp.read_text(encoding="utf-8")
    snap = "\n".join(text.split("\n")[text.split("\n").index("def subtotal(basket):"):][:3])
    run_dir, lanes = _lanes_on_branch(text, snap)
    ok, rows = record_equals_disk(run_dir, lanes)
    ctx.check(f"equal when the branch holds the snapshot, got {rows}", ok and rows[0]["equal"])
    run_dir, lanes = _lanes_on_branch(text, snap.replace('"0"', '"1"'))
    ok, rows = record_equals_disk(run_dir, lanes)
    ctx.check("differs when the text changed after it was written", not ok and not rows[0]["equal"])
    run_dir, lanes = _lanes_on_branch(text, snap.replace('"0"', '"1"'), judged=True)
    ok, rows = record_equals_disk(run_dir, lanes)
    ctx.check("a judge-resolved file is flagged and still counts", ok and rows[0]["judge"])


@test
def test_hunks_extract_parse_apply(ctx: Ctx):
    from halo_harness.orchestra.hunks import apply_resolution, extract_hunks, parse_resolution
    text = ("top\n<<<<<<< HEAD\na1\n||||||| base\na0\n=======\na2\n>>>>>>> w\nmid\n"
            "<<<<<<< HEAD\nb1\n=======\nb2\n>>>>>>> w\nend\n")
    hunks = extract_hunks(text)
    ctx.check("two hunks with their lines",
              [(h["ours"], h["base"], h["theirs"], h["start_line"], h["end_line"]) for h in hunks]
              == [("a1", "a0", "a2", 2, 8), ("b1", "", "b2", 10, 14)])
    ctx.check("one hunk wants a bare answer, fences stripped", parse_resolution("```python\nx\n```", 1) == ["x"])
    two = parse_resolution("=== hunk 1 ===\nA\n=== hunk 2 ===\nB1\nB2\n", 2)
    ctx.check(f"blocks per hunk, got {two}", two == ["A", "B1\nB2"])
    ctx.check("a missing block is no answer", parse_resolution("=== hunk 1 ===\nA\n", 2) is None)
    ctx.check("markers in the answer are no answer", parse_resolution("<<<<<<< HEAD\nx", 1) is None)
    ctx.check("applied by code", apply_resolution(text, two) == "top\nA\nmid\nB1\nB2\nend\n")


@test
def test_gate_narrows_to_the_lane_others_depend_on(ctx: Ctx):
    from halo_harness.orchestra.gate import _narrow
    from halo_harness.orchestra.lanes import Lane
    from halo_harness.orchestra.split import Job
    import tempfile
    run_dir = Path(tempfile.mkdtemp(prefix="orch-narrow-"))
    sub = Lane.create(run_dir, Job("job-3", "s", ["basket.py#subtotal"], 3, 3), branch="b", worktree=run_dir, started=0)
    sub.store_written("basket.py#subtotal", "def subtotal(basket):\n    return 1")
    tot = Lane.create(run_dir, Job("job-5", "t", ["basket.py#total"], 5, 5), branch="b", worktree=run_dir, started=0)
    tot.store_written("basket.py#total", "def total(basket, percent=0):\n    return apply_discount(subtotal(basket), percent)")
    ctx.check("total calls subtotal: only subtotal goes back", [l.n for l in _narrow([sub, tot])] == [3])
    ctx.check("a lone lane stays", [l.n for l in _narrow([tot])] == [5])


@test
def test_format_report(ctx: Ctx):
    from halo_harness.orchestra.report import CHECK_IDS, format_report
    report = {"run_id": "r1", "status": "stopped", "stop_reason": "lane 2 reached the cap", "branch": "orchestra/r1",
              "finished": None, "tests_ok": False, "cost_usd": 0.01234, "elapsed_s": 12.5,
              "lanes": [{"lane": 1, "title": "write total", "state": "merged", "pieces_returned": 0, "cost_usd": 0.002}],
              "checks": [{"id": cid, "ok": (None if cid == "goal_done_when" else cid != "all_branches_merged"),
                          "detail": "x"} for cid in CHECK_IDS]}
    text = format_report(report)
    ctx.check("the status and reason lead", text.splitlines()[0] == "run r1: stopped -- lane 2 reached the cap")
    ctx.check("cost and time", "$0.0123" in text and "12.5s" in text)
    ctx.check("a lane line", "lane 1   merged" in text and "write total" in text)
    ctx.check("PASS/FAIL per check, the done-when echo unmarked",
              "FAIL  all_branches_merged" in text and "PASS  reviewer_fresh" in text
              and "      goal_done_when" in text)
    ctx.check("json-serialisable", json.loads(json.dumps(report)) == report)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
