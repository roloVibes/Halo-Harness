"""tests.test_review_fix -- Halo 2.0.10 round 1: `--fix` (apply a minimal fix, re-verify), `--fix` with
`--no-verify`, and Esc aborting every reviewer. The rest of the engine is tests/test_review_run.py.
"""
from __future__ import annotations

import json
import os
import sys
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
def test_fix_applies_a_minimal_change_and_reverifies(ctx: Ctx):
    mock, repo, session = _setup()
    try:
        before_log = rm.git(repo, "log", "--oneline")
        items = [rm.finding_json(file="a.py", line=2, severity="high", category="logic-error", short="subtracts"),
                 rm.finding_json(file="util.py", line=2, severity="high", category="crash", short="empty list crash"),
                 rm.finding_json(file="util.py", line=1, severity="medium", category="already", short="handled elsewhere"),
                 rm.finding_json(file="a.py", line=1, severity="medium", category="claimed", short="claims a fix"),
                 rm.finding_json(file="util.py", line=1, severity="low", category="stubborn", short="still broken"),
                 rm.finding_json(file="a.py", line=1, severity="low", category="soft", short="only plausible")]
        rev = rm.Router(lambda p: rm.fenced(items) if _dim(p) == "correctness" else EMPTY)

        def judge(p):
            if "A fix was just applied" in p:                       # the re-verification
                return _verdict("CONFIRMED", "still there") if "still broken" in p else _verdict("DISMISSED", "gone now")
            if "only plausible" in p:
                return _verdict("PLAUSIBLE", "maybe")
            return _verdict("CONFIRMED", "real")

        def coder(p):
            if '"short_summary": "subtracts"' in p:
                (repo / "a.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
                return '```json\n{"outcome": "fixed", "note": "restored the plus"}\n```'
            if "empty list crash" in p:
                (repo / "util.py").write_text("def first(xs):\n    return xs[0] if xs else None\n", encoding="utf-8")
                return '```json\n{"outcome": "fixed", "note": "guarded the empty list"}\n```'
            if "handled elsewhere" in p:
                return '```json\n{"outcome": "no_change_needed", "note": "callers already check"}\n```'
            if "claims a fix" in p:
                return '```json\n{"outcome": "fixed", "note": "I fixed it"}\n```'      # but touches nothing
            if "still broken" in p:
                (repo / "util.py").write_text("def first(xs):\n    return xs[0] if xs else None  # tweak\n", encoding="utf-8")
                return '```json\n{"outcome": "fixed", "note": "tweaked"}\n```'
            return '```json\n{"outcome": "skipped", "note": "unexpected"}\n```'
        cod = rm.Router(coder)
        rm.register(reviewer=rev, judge=rm.Router(judge), coder=cod)
        result = _run(session, fix=True)
        out = {f.short_summary: (f.outcome, f.fix_note) for f in result.findings}
        ctx.check(f"only CONFIRMED findings reach the coder, got {len(cod.prompts)}", len(cod.prompts) == 5)
        ctx.check(f"fixed + re-verified, got {out['subtracts']}", out["subtracts"][0] == "fixed" and "gone now" in out["subtracts"][1])
        ctx.check(f"second fix, got {out['empty list crash']}", out["empty list crash"][0] == "fixed")
        ctx.check(f"no_change_needed passes through, got {out['handled elsewhere']}",
                  out["handled elsewhere"][0] == "no_change_needed")
        ctx.check(f"a claimed fix that changed nothing is skipped, got {out['claims a fix']}",
                  out["claims a fix"][0] == "skipped" and "did not change" in out["claims a fix"][1])
        ctx.check(f"re-verification that still finds the problem is skipped, got {out['still broken']}",
                  out["still broken"][0] == "skipped" and "still reports" in out["still broken"][1])
        ctx.check("a PLAUSIBLE finding gets no outcome", out["only plausible"][0] is None)
        ctx.check("the working tree holds the fixes", "a + b" in (repo / "a.py").read_text(encoding="utf-8"))
        ctx.check("nothing was committed", rm.git(repo, "log", "--oneline") == before_log)
        ctx.check("the fix is an uncommitted change", "a.py" in rm.git(repo, "status", "--porcelain"))
        outcomes = [f.to_dict()["outcome"] for f in result.findings]
        ctx.check("outcome values are in the allowed set", all(o in (None, "fixed", "skipped", "no_change_needed") for o in outcomes))
    finally:
        mock.stop()



@test
def test_esc_aborts_every_reviewer_and_stops_the_pipeline(ctx: Ctx):
    mock, repo, session = _setup(max_concurrent=1)
    try:
        seen = []

        def on_call(prompt):
            seen.append(prompt)
            if len(seen) == 2:                          # Esc while the second reviewer is mid-call
                session.abort.set()
        rev = rm.Router(lambda p: rm.fenced([rm.finding_json()]), delay=0.25, on_call=on_call)
        jud = rm.Router(lambda p: _verdict("CONFIRMED"))
        rm.register(reviewer=rev, judge=jud)
        result = _run(session, fix=True)
        ctx.check(f"reviewers that had not started never ran, got {len(rev.prompts)} calls", len(rev.prompts) < 5)
        ctx.check("result is marked interrupted", result.aborted is True)
        ctx.check("the judge never ran after Esc", jud.prompts == [])
        ctx.check("later reviewers report interrupted",
                  sum(1 for r in result.reviewers if r.get("error") == "interrupted") >= 3)
        ctx.check("a note says verification was skipped", any("interrupted" in n for n in result.notes))
    finally:
        mock.stop()



@test
def test_fix_with_no_verify_is_skipped_with_a_note(ctx: Ctx):
    mock, repo, session = _setup()
    try:
        from halo_harness.review.run import ReviewOptions, run_review
        rev = rm.Router(lambda p: rm.fenced([rm.finding_json()]) if _dim(p) == "correctness" else EMPTY)
        rm.register(reviewer=rev, judge=rm.Router(lambda p: _verdict("CONFIRMED")))
        result = run_review(session.agent_runtime, ReviewOptions(fix=True, verify=False))
        ctx.check("--fix with --no-verify is skipped with a note", any("--fix needs verification" in n for n in result.notes))
        ctx.check("findings still returned", len(result.findings) == 1)
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
