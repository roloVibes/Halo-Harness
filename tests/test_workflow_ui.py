"""tests.test_workflow_ui -- a workflow's typed artifact in Studio (Halo
3.2.0.0 R5). Headless Chrome through the driver base
(tests/helpers/studio_workflow.py; skipped without one), over a fresh home
with doc-review (bash granted, a model that calls tools) and a repo where the
review workflow ran to its report (fakes, no model call):

1. the pack's Docs review section: the "Last review report" artifact panel
   draws the newest run's review-report as a table (its schema's view hint),
   the summary above, a row per finding, the run in its meta line;
2. Session's Reviews panel: a review.done's data under its line (the kind's
   schema has a view hint), an off-schema one's problems under it;
3. Orchestra's Report panel: an "Artifacts (1)" tab lists the report
   artifact (saved, ok) and draws the same rows.

Run: python -m tests.test_workflow_ui
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}
ROW = ["docs/guide.md", "3", "a dead link", "high"]


def _got(ctx: Ctx) -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Studio artifact-viewer checks need headless Chrome)")
    if "r" not in _RUN:
        r = subprocess.run([sys.executable, "-m", "tests.helpers.studio_workflow"], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=400, env=driver_env(REPO), cwd=str(REPO), stdin=subprocess.DEVNULL)
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN["r"] = (r, info)
    r, info = _RUN["r"]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in info)
    return info


@test
def test_the_packs_artifact_panel_draws_the_newest_report_as_a_table(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Alt+7 opens Docs review, got {got.get('section')!r}", str(got.get("section") or "").startswith("Docs review"))
    ctx.check(f"the table view, of the run that wrote it, got {got.get('view')} {got.get('run')}", got.get("view") == "table"
              and got.get("run") == got.get("run_id"))
    ctx.check(f"its meta line names the schema, view and workflow, got {got.get('meta')!r}",
              got.get("meta") == f"review-report · table · run {got.get('run_id')} · doc-review/review")
    ctx.check(f"the schema's columns, got {got.get('head')}", got.get("head") == ["file", "line", "finding", "severity"])
    ctx.check(f"one row per finding, got {got.get('rows')} {got.get('cells')}", got.get("rows") == 1 and got.get("cells") == ROW)
    ctx.check(f"the summary above the rows, got {got.get('summary')!r}", got.get("summary") == "One dead link.")


@test
def test_an_events_data_and_its_problems_show_under_its_line(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the data under the line (keyvalue), got {got.get('event_kv')}", got.get("event_kv") == ["file=docs/guide.md", "findings=1"])
    ctx.check(f"an off-schema event is shown with its problems, got {got.get('event_problems')} {got.get('event_line')!r}",
              got.get("event_problems") == ["findings is required"] and got.get("event_line") == "docs/intro.md: ? findings")


@test
def test_the_run_views_report_has_an_artifacts_tab(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the tab counts the artifacts, got {got.get('tab')!r}", got.get("tab") == "Artifacts (1)")
    ctx.check(f"the report artifact: saved and ok, got {got.get('artifact')}", got.get("artifact") == ["report", "saved", "true"])
    ctx.check(f"its head names the schema and view, got {got.get('artifact_head')!r}",
              "review-report · table · saved · lane 4" in str(got.get("artifact_head")))
    ctx.check(f"the same rows, got {got.get('artifact_cells')}", got.get("artifact_rows") == 1 and got.get("artifact_cells") == ROW)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
