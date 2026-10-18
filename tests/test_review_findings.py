"""tests.test_review_findings -- Halo 2.0.10 round 1: the pure parts of /review
(tolerant JSON parsing, dedup and ranking) and the `code-review` team template.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _verdict(v: str, reason: str = "checked") -> str:
    import json
    return "```json" + chr(10) + json.dumps({"verdict": v, "reason": reason}) + chr(10) + "```"


@test
def test_pure_parsing_is_tolerant(ctx: Ctx):
    from halo_harness.review.findings import extract_json, parse_findings, parse_verdict
    prose = 'Here you go:\n```json\n[{"file": "a.py", "line": "7", "severity": "Critical", "short_summary": "x"}]\n```\nDone.'
    got = parse_findings(prose, "security")
    ctx.check(f"a fenced block anywhere parses, got {got}", got and got[0].file == "a.py" and got[0].line == 7)
    ctx.check("severity aliases normalise (critical -> high)", got[0].severity == "high")
    ctx.check("dimension is recorded", got[0].dimensions == ["security"])
    bare = parse_findings('I found [{"file": "b.py", "summary": "y", "severity": "weird"}] only.')
    ctx.check(f"an unfenced array in prose parses, got {bare}", bare and bare[0].severity == "medium")
    ctx.check("an empty array is a valid, empty result", parse_findings("```json\n[]\n```") == [])
    ctx.check("prose with no JSON is None (triggers the repair)", parse_findings("looks fine to me") is None)
    ctx.check("junk items are skipped", len(parse_findings('[1, "x", {"file": "c.py"}, {"summary": "ok"}]')) == 1)
    ctx.check("{findings: [...]} object form parses", len(parse_findings('{"findings": [{"summary": "z"}]}')) == 1)
    ctx.check("extract_json finds an object in prose", extract_json('verdict: {"a": 1} ok') == {"a": 1})
    ctx.check("verdict parses", parse_verdict(_verdict("DISMISSED", "guarded")) == ("DISMISSED", "guarded"))
    ctx.check("a bare verdict word is accepted", parse_verdict("I say PLAUSIBLE.") == ("PLAUSIBLE", ""))
    ctx.check("garbage verdict is None", parse_verdict('{"verdict": "maybe"}') is None)



@test
def test_dedupe_and_rank_are_pure_and_severity_first(ctx: Ctx):
    from halo_harness.review.findings import Finding
    from halo_harness.review.verify import dedupe, rank
    a = Finding(file="a.py", line=2, category="logic-error", severity="medium", summary="first view",
                verdict="PLAUSIBLE", dimensions=["correctness"])
    b = Finding(file="a.py", line=2, category="logic-error", severity="high", summary="second view",
                verdict="CONFIRMED", dimensions=["tests"])
    c = Finding(file="b.py", line=1, category="x", severity="low", verdict="CONFIRMED")
    d = Finding(file="c.py", line=9, category="y", severity="high", verdict="PLAUSIBLE")
    e = Finding(file="a.py", line=3, category="logic-error", severity="medium", verdict="CONFIRMED")
    merged = dedupe([a, b, c, d, e])
    ctx.check(f"same file+line+category merges to one, got {len(merged)}", len(merged) == 4)
    top = next(f for f in merged if f.key() == ("a.py", 2, "logic-error"))
    ctx.check("the higher severity wins", top.severity == "high" and top.verdict == "CONFIRMED")
    ctx.check("summaries are merged", "first view" in top.summary and "second view" in top.summary)
    ctx.check("dimensions are merged", sorted(top.dimensions) == ["correctness", "tests"])
    order = [(f.file, f.severity, f.verdict) for f in rank(merged)]
    ctx.check(f"severity first, then verdict, got {order}", order == [
        ("a.py", "high", "CONFIRMED"), ("c.py", "high", "PLAUSIBLE"),
        ("a.py", "medium", "CONFIRMED"), ("b.py", "low", "CONFIRMED")])



@test
def test_code_review_team_template_maps_the_three_roles(ctx: Ctx):
    import tempfile
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="rv-team-home-")
    from halo_harness.teams_yaml import list_team_templates, resolve_team_template, validate_team_template
    from halo_harness.tui.dialogs.teams_list import team_rows
    template = resolve_team_template("code-review")
    ctx.check("the template ships", template is not None and "code-review" in list_team_templates())
    ctx.check(f"it validates, got {validate_team_template(template, name='code-review')}",
              validate_team_template(template, name="code-review") == [])
    roles = {a.get("role") for a in template.get("agents") or []}
    ctx.check(f"it maps reviewer, judge and coder, got {sorted(r for r in roles if r)}",
              {"reviewer", "judge", "coder"} <= roles)
    rows = team_rows()
    row = next((r for r in rows if r["name"] == "code-review"), None)
    ctx.check(f"the wizard's Team step row exists, got {row}", row is not None and "review" in row["description"].lower())




if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
