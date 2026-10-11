"""tests.test_review_run -- Halo 2.0.10 round 1: the review engine through a real agent.loop.Session against
the mock upstream with scripted reviewer and judge replies (tests/helpers/review_mock.py): dimensions run in
parallel under the gate, tolerant parse + one repair, level caps, verification, dedup, --no-verify, /tasks rows.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.mock_openai import MockUpstream
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials
from tests.helpers import review_mock as rm

ensure_default_provider_credentials()
test, TESTS = new_registry()
_ORIGINAL_HOME = os.environ.get("BRIDGE_TEST_HOME")

EMPTY = "```json\n[]\n```"


def _verdict(v: str, reason: str = "checked") -> str:
    return "```json\n" + json.dumps({"verdict": v, "reason": reason}) + "\n```"


def _dim(prompt: str) -> str:
    for line in prompt.splitlines():
        if line.startswith("Dimension: "):
            return line.split()[1]
    return ""


def _run(session, **opts):
    from halo_harness.review.run import ReviewOptions, run_review
    return run_review(session.agent_runtime, ReviewOptions(**opts))


def _setup(max_concurrent=None):
    mock = MockUpstream().start()
    repo = rm.make_repo()
    return mock, repo, rm.new_session(mock, repo, max_concurrent=max_concurrent)


@test
def test_dimensions_run_in_parallel_under_the_gate(ctx: Ctx):
    mock, repo, session = _setup(max_concurrent=2)
    try:
        rev = rm.Router(lambda p: EMPTY, delay=0.35)
        rm.register(reviewer=rev, judge=rm.Router(lambda p: _verdict("CONFIRMED")))
        t0 = time.monotonic()
        result = _run(session)
        took = time.monotonic() - t0
        ctx.check(f"five reviewers ran, got {len(result.reviewers)}", len(result.reviewers) == 5)
        ctx.check(f"each dimension got its own prompt, got {sorted(_dim(p) for p in rev.prompts)}",
                  sorted(_dim(p) for p in rev.prompts) == sorted(
                      ["correctness", "security", "performance", "tests", "docs-consistency"]))
        ctx.check(f"the gate held at 2 while reviewers overlapped, peak={rev.peak}", rev.peak == 2)
        ctx.check(f"parallel, not serial (5 x 0.35 s serial = 1.75 s), took {took:.2f}", took < 1.6)
        ctx.check("no findings, no judge calls", result.findings == [] and not result.dismissed)
        ctx.check("each reviewer prompt carries the diff", all("-    return a + b" in p for p in rev.prompts))
        from halo_harness.agent.subagent import list_agent_task_rows
        rows = list_agent_task_rows(session)
        titles = sorted(r["title"] for r in rows)
        ctx.check(f"/tasks rows exist for every reviewer, got {titles}", titles == sorted(
            ["review-correctness", "review-security", "review-performance", "review-tests", "review-docs-consistency"]))
        ctx.check("all rows finished", all(r["status"] == "completed" for r in rows))
    finally:
        mock.stop()


@test
def test_dimensions_flag_restricts_reviewers(ctx: Ctx):
    mock, repo, session = _setup()
    try:
        rev = rm.Router(lambda p: EMPTY)
        rm.register(reviewer=rev)
        result = _run(session, dimensions=["security", "tests"])
        ctx.check(f"two reviewers, got {[r['dimension'] for r in result.reviewers]}",
                  [r["dimension"] for r in result.reviewers] == ["security", "tests"])
        ctx.check("only those prompts went out", sorted(_dim(p) for p in rev.prompts) == ["security", "tests"])
    finally:
        mock.stop()


@test
def test_tolerant_parse_and_one_repair(ctx: Ctx):
    mock, repo, session = _setup()
    try:
        calls = {"first": 0}

        def reviewer(p):
            d = _dim(p)
            if "could not be parsed" in p:           # the repair re-ask (for `tests`, and again for `security`)
                calls["first"] += 1
                return ("No JSON here either." if calls["first"] == 1 else
                        rm.fenced([rm.finding_json(file="util.py", line=2, category="missing-test",
                                                   short="first() has no test")]))
            if d == "tests":
                return "I reviewed the change and it looks mostly fine, nothing to list."
            if d == "security":
                return "No JSON here, and the repair does not help either."
            if d == "correctness":
                return "Some words first.\n" + rm.fenced([rm.finding_json()]) + "\nTrailing remarks."
            return EMPTY

        rev = rm.Router(reviewer)
        rm.register(reviewer=rev, judge=rm.Router(lambda p: _verdict("CONFIRMED")))
        result = _run(session)
        by_dim = {r["dimension"]: r for r in result.reviewers}
        ctx.check("a fenced block in prose parses (correctness)", by_dim["correctness"]["findings"] == 1)
        repairs = sum("could not be parsed" in p for p in rev.prompts)
        ctx.check(f"exactly one repair per unparsable reviewer (2), got {repairs}", repairs == 2)
        ctx.check(f"5 first calls + 2 repairs, got {len(rev.prompts)}", len(rev.prompts) == 7)
        ok_fixed = [r for r in result.reviewers if r["ok"] and r["findings"] == 1 and r["dimension"] != "correctness"]
        failed = [r for r in result.reviewers if not r["ok"]]
        ctx.check(f"one reviewer was repaired into a finding, got {ok_fixed}", len(ok_fixed) == 1)
        ctx.check(f"one stayed unparsable after its single repair, got {failed}",
                  len(failed) == 1 and "parsable" in failed[0]["error"])
        ctx.check(f"the review still completed with both findings, got {[f.file for f in result.findings]}",
                  sorted(f.file for f in result.findings) == ["a.py", "util.py"])
        ctx.check("the repair prompt asks for only the JSON array",
                  any("Output only the JSON array" in p for p in rev.prompts))
    finally:
        mock.stop()


@test
def test_level_caps_findings_and_shapes_the_prompt(ctx: Ctx):
    mock, repo, session = _setup()
    try:
        many = [rm.finding_json(line=i + 1, short=f"issue {i}", category=f"c{i}") for i in range(25)]
        rev = rm.Router(lambda p: rm.fenced(many) if _dim(p) == "correctness" else EMPTY)
        rm.register(reviewer=rev, judge=rm.Router(lambda p: _verdict("PLAUSIBLE")))
        counts = {}
        for level, cap in (("low", 3), ("medium", 8), ("high", 20)):
            rev.prompts.clear()
            result = _run(session, level=level, dimensions=["correctness"], verify=False)
            counts[level] = len(result.findings)
            ctx.check(f"{level}: prompt says at most {cap}", any(f"at most {cap} findings" in p for p in rev.prompts))
        ctx.check(f"caps are 3/8/20, got {counts}", counts == {"low": 3, "medium": 8, "high": 20})
        rev.prompts.clear()
        _run(session, level="low", dimensions=["correctness"], verify=False)
        low_prompt = rev.prompts[0]
        rev.prompts.clear()
        _run(session, level="high", dimensions=["correctness"], verify=False)
        ctx.check("low asks for a concrete failing scenario, high allows speculation",
                  "concrete failing scenario" in low_prompt and "plausible risks" in rev.prompts[0])
    finally:
        mock.stop()


@test
def test_verification_dismisses_ranks_and_keeps_dismissed(ctx: Ctx):
    mock, repo, session = _setup()
    try:
        items = [rm.finding_json(line=2, severity="low", category="style", short="nit one"),
                 rm.finding_json(file="util.py", line=2, severity="high", category="crash", short="first() on empty list"),
                 rm.finding_json(file="util.py", line=1, severity="medium", category="api", short="bad name"),
                 rm.finding_json(file="a.py", line=1, severity="high", category="phantom", short="not real")]
        rev = rm.Router(lambda p: rm.fenced(items) if _dim(p) == "correctness" else EMPTY)

        def judge(p):
            if "not real" in p:
                return _verdict("DISMISSED", "the guard on line 1 prevents it")
            if "first() on empty list" in p:
                return _verdict("CONFIRMED", "xs[0] raises IndexError")
            return _verdict("PLAUSIBLE", "depends on callers")
        jud = rm.Router(judge)
        rm.register(reviewer=rev, judge=jud)
        result = _run(session)
        ctx.check(f"every finding went to the judge, got {len(jud.prompts)}", len(jud.prompts) == 4)
        ctx.check("the judge saw the finding and the diff excerpt for its file",
                  any("first() on empty list" in p and "def first(xs)" in p for p in jud.prompts))
        ctx.check(f"dismissed dropped from findings, got {[f.short_summary for f in result.findings]}",
                  [f.short_summary for f in result.findings] == ["first() on empty list", "bad name", "nit one"])
        ctx.check("dismissed kept with its reason",
                  [(f.short_summary, f.verdict, f.reason) for f in result.dismissed]
                  == [("not real", "DISMISSED", "the guard on line 1 prevents it")])
        ctx.check("verdicts attached", [f.verdict for f in result.findings] == ["CONFIRMED", "PLAUSIBLE", "PLAUSIBLE"])
        ctx.check("ranked severity-first (high, medium, low)", [f.severity for f in result.findings] == ["high", "medium", "low"])
    finally:
        mock.stop()


@test
def test_same_finding_from_two_dimensions_is_merged(ctx: Ctx):
    mock, repo, session = _setup()
    try:
        rev = rm.Router(lambda p: {
            "correctness": rm.fenced([rm.finding_json(severity="medium", summary="correctness view")]),
            "tests": rm.fenced([rm.finding_json(severity="high", summary="tests view")])}.get(_dim(p), EMPTY))
        rm.register(reviewer=rev, judge=rm.Router(lambda p: _verdict("CONFIRMED")))
        result = _run(session)
        ctx.check(f"one merged finding, got {len(result.findings)}", len(result.findings) == 1)
        f = result.findings[0]
        ctx.check("higher severity kept", f.severity == "high")
        ctx.check("summaries merged", "correctness view" in f.summary and "tests view" in f.summary)
        ctx.check("both dimensions recorded", sorted(f.dimensions) == ["correctness", "tests"])
    finally:
        mock.stop()


@test
def test_no_verify_skips_the_judge(ctx: Ctx):
    mock, repo, session = _setup()
    try:
        rev = rm.Router(lambda p: rm.fenced([rm.finding_json()]) if _dim(p) == "correctness" else EMPTY)
        jud = rm.Router(lambda p: _verdict("DISMISSED"))
        rm.register(reviewer=rev, judge=jud)
        result = _run(session, verify=False)
        ctx.check("no judge call", jud.prompts == [])
        ctx.check("findings stay PLAUSIBLE", [f.verdict for f in result.findings] == ["PLAUSIBLE"])
        ctx.check("nothing dismissed", result.dismissed == [])
    finally:
        mock.stop()


@test
def test_a_judge_that_cannot_be_parsed_leaves_the_finding_plausible(ctx: Ctx):
    mock, repo, session = _setup()
    try:
        rev = rm.Router(lambda p: rm.fenced([rm.finding_json()]) if _dim(p) == "correctness" else EMPTY)
        jud = rm.Router(lambda p: "I cannot decide")
        rm.register(reviewer=rev, judge=jud)
        result = _run(session)
        ctx.check(f"judge asked twice (one repair), got {len(jud.prompts)}", len(jud.prompts) == 2)
        ctx.check("finding kept as PLAUSIBLE with the reason",
                  result.findings and result.findings[0].verdict == "PLAUSIBLE"
                  and "could not be parsed" in result.findings[0].reason)
    finally:
        mock.stop()

@test
def test_zzz_restore_env(ctx: Ctx):
    if _ORIGINAL_HOME is None:
        os.environ.pop("BRIDGE_TEST_HOME", None)
    else:
        os.environ["BRIDGE_TEST_HOME"] = _ORIGINAL_HOME
    ctx.check("env restored", True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
