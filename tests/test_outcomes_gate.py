"""tests.test_outcomes_gate -- the Orchestra gate reads the evidence (Halo
3.1.8.0 R3, outcomes/lane.py, orchestra/gate.py), in the mock rig (a real
temp repo, real git and tests; the workers are fakes that leave a transcript):

1. a code lane whose work ran no test (the goal has one) goes back ONCE with
   "no test run in this lane's work: run <test>", shown as a `gate` line; its
   second pass ran the tests and the run finishes; a lane that ran them is
   never sent back; the gate's verdict carries each lane's evidence lines;
2. once only: a lane that still runs no test after its send-back is not sent
   back again; a lane without a transcript is never sent back;
3. a research lane with no source goes back once with "no source fetched or
   read"; a lane at its return cap is not sent back for evidence;
4. the judge prompt gains an EVIDENCE block -- the lanes' tests, sources and
   reproductions, never their summary -- in a real conflict;
5. the run report lists each lane's evidence lines, `format_report` prints
   them, and the supervisor's failure keeps them.
No model call. Run: python -m tests.test_outcomes_gate
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import outcomes_rig as R  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
GROUPS = [["add_item", "remove_item", "subtotal"], ["apply_discount", "total"]]


def _run(plan: dict, *, groups=None, cap: int = 2):
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    repo = F.make_repo()
    run_dir = F.make_run(repo, workers=len(groups or GROUPS), return_cap=cap)
    worker = R.TranscriptWorker(F.FakeWorker(), plan)
    report = run(run_dir, model_calls=F.FakeLead(F.split_answer(groups or GROUPS)), spawn=worker, judge=F.FakeJudge())
    return run_dir, worker, report


def _lane(run_dir, n) -> dict:
    from halo_harness.orchestra.lanes import load_lane
    return load_lane(run_dir, n).data()


@test
def test_a_code_lane_without_a_test_run_goes_back_once(ctx: Ctx):
    from halo_harness.orchestra import events as E
    from halo_harness.orchestra.goal import load_goal
    with R.home():
        run_dir, worker, report = _run({1: ["code-no-tests", "code-lane"], 2: ["code-lane"]})
        test = load_goal(run_dir / "goal.json").test
        line = f"no test run in this lane's work: run {test}"
        ctx.check(f"the run finishes, got {report['status']} {report.get('stop_reason')}", report["status"] == "finished")
        ctx.check(f"lane 1 went back once, lane 2 never, got {worker.passes}",
                  worker.passes == {1: 2, 2: 1} and _lane(run_dir, 1)["pieces_returned"] == 1
                  and _lane(run_dir, 2)["pieces_returned"] == 0)
        ctx.check("its second prompt carries the line", line in worker.prompts[1][1] and line not in worker.prompts[1][0])
        gate_lines = [e.get("text") for e in E.read(run_dir) if e.get("kind") == "gate"]
        ctx.check(f"the send-back is one gate line, got {gate_lines}", f"lane 1 sent back for its evidence: {line}" in gate_lines)
        ctx.check("the lane file keeps the rule it went back for", _lane(run_dir, 1).get("evidence_returned") == line)
        from halo_harness.orchestra.gate import quality_gate
        from halo_harness.orchestra.lanes import list_lanes
        gate = quality_gate(run_dir, load_goal(run_dir / "goal.json"), list_lanes(run_dir), run_dir / "wt" / "merge")
        ctx.check(f"the verdict carries each lane's evidence lines, got {gate.evidence}",
                  gate.ok and sorted(gate.evidence) == [1, 2] and gate.evidence[1][0].startswith("tests: `python -m pytest"))


@test
def test_once_only_and_no_transcript_no_send_back(ctx: Ctx):
    with R.home():
        run_dir, worker, report = _run({1: ["code-no-tests"]})
        ctx.check(f"still no test run after its send-back: not sent back again, got {worker.passes} {report['status']}",
                  report["status"] == "finished" and worker.passes == {1: 2, 2: 1}
                  and _lane(run_dir, 1)["pieces_returned"] == 1)
        ctx.check("lane 2 left no transcript: never sent back", _lane(run_dir, 2)["pieces_returned"] == 0)


class _Lane:
    def __init__(self, run_dir, n, returned=0):
        self.run_dir, self.n, self._d = run_dir, n, {"pieces_returned": returned}

    def data(self):
        return dict(self._d)

    def update(self, **fields):
        self._d.update(fields)

    @property
    def pieces_returned(self):
        return self._d["pieces_returned"]


@test
def test_a_research_lane_without_sources_and_the_cap(ctx: Ctx):
    from halo_harness.orchestra.goal import Goal
    from halo_harness.outcomes import evidence as EV
    from halo_harness.outcomes.lane import evidence_back, evidence_path
    run_dir = Path(tempfile.mkdtemp(prefix="gate-research-"))
    for n, kind, sources in ((1, "research", []), (2, "research", [{"kind": "fetch", "target": "https://x.test", "when": 1}]),
                             (3, "code", []), (4, "research", [])):
        EV.write(evidence_path(run_dir, n), EV.Evidence(kind=kind, transcript=True, sources=sources))
    goal = Goal(what="w", done_when="d", stop_when="s", test="", return_cap=2)
    lanes = [_Lane(run_dir, 1), _Lane(run_dir, 2), _Lane(run_dir, 3), _Lane(run_dir, 4, returned=2)]
    tests = type("T", (), {"ok": True, "tail": ""})()
    back = evidence_back(run_dir, goal, lanes, tests)
    ctx.check(f"only the research lane with no source goes back, got {back}",
              list(back) == [1] and "no source fetched or read" in back[1])
    ctx.check("a code lane is not held to a test when the goal has none; a lane at its cap is not sent back", 3 not in back and 4 not in back)
    ctx.check("once: the second gate sends nothing back", evidence_back(run_dir, goal, lanes, tests) == {})


@test
def test_the_judge_prompt_gains_an_evidence_block(ctx: Ctx):
    from halo_harness.orchestra.hunks import judge_prompt
    from halo_harness.orchestra.run import run
    from tests.helpers import orchestra_fixtures as F
    seen = []

    class _Judge(F.FakeJudge):
        def __call__(self, hunks, goal, file):
            seen.append(judge_prompt(hunks, goal, file))
            return super().__call__(hunks, goal, file)

    with R.home():
        repo = F.make_repo()
        test = (f"{F.PY} -m unittest -q test_basket.BasketTest.test_apply_discount test_basket.BasketTest.test_total "
                "test_basket.BasketTest.test_subtotal")
        run_dir = F.make_run(repo, workers=2, return_cap=2, test=test)
        worker = R.TranscriptWorker(F.FakeWorker(F.CONFLICT_SOLUTIONS, F.CONFLICT_IMPORTS), {1: ["code-lane"], 2: ["research"]})
        report = run(run_dir, model_calls=F.FakeLead(F.split_answer([["apply_discount"], ["subtotal", "total"]])),
                     spawn=worker, judge=_Judge())
    prompt = seen[0] if seen else ""
    ctx.check(f"a conflict was judged and the run finished, got {report['status']} {len(seen)}", seen and report["status"] == "finished")
    ctx.check("the prompt has the EVIDENCE block", "EVIDENCE (what each lane's worker ran and read" in prompt)
    ctx.check("with the incoming lane's own lines", "- lane 2 (code, incoming): tests: none run" in prompt
              and "- lane 2 (code, incoming): sources: 4 -- search python decimal" in prompt)
    ctx.check("and the merged lane that wrote the file", "- lane 1 (code, merged): tests: `python -m pytest -q test_basket.py` exit 1" in prompt)
    ctx.check("never a summary", "Wrote add_item; the five tests pass." not in prompt and "The basket needs ROUND_HALF_UP" not in prompt)
    plain = judge_prompt([{"index": 1, "start_line": 1, "end_line": 3, "ours": "a", "base": "", "theirs": "b"}],
                         {"what": "w", "done_when": "d"}, "f.py")
    ctx.check("a goal with no evidence: the prompt as before", "EVIDENCE" not in plain)


@test
def test_the_report_and_the_supervisor_keep_the_lines(ctx: Ctx):
    from halo_harness.orchestra.report import format_report
    from halo_harness.supervise.runner import report_outcome
    with R.home():
        run_dir, _worker, report = _run({1: ["code-lane"], 2: ["code-lane"]})
    rows = report["lanes"]
    ctx.check(f"each report lane carries its evidence lines, got {[r.get('evidence') for r in rows]}",
              all(r.get("evidence") and r["evidence"][0].startswith("tests: `python -m pytest") for r in rows))
    text = format_report(report)
    ctx.check("format_report prints them under their lane",
              "\n      tests: `python -m pytest -q test_basket.py` exit 1, 4 passed" in text)
    stopped = dict(report, status="stopped", stop_reason="lane 1 reached the return cap (2) and the tests still fail "
                                                         "on the finished branch")
    out = report_outcome(run_dir, stopped)
    ev = ((out.get("failure") or {}).get("report") or {}).get("evidence") or {}
    ctx.check(f"the supervisor's failure keeps them per lane, got {sorted(ev)}",
              out["state"] == "parked" and sorted(ev) == ["1", "2"] and ev["1"] == rows[0]["evidence"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
