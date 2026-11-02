"""tests.test_studio_model_select -- the one model select outside Roles (Halo
3.1.4.0 R4). Headless Chrome through the driver base (tests/helpers/
studio_model_select.py, two runs one after the other; skipped without one):

1. Orchestra's goal form shows the select without opening "who plays the
   parts" (the disclosure keeps the lead / worker roles), its first option
   "the lineup's (<the lead's model>)" from the role table, and a pick lands;
2. Design's Projects panel shows the open project's model (first option "the
   default (<model>)"); a pick saves the project (`GET design/projects`); New
   project's dialog creates the project on the picked model;
3. Team: a stage has no model field of its own (team/spec.py), so the `draft`
   stage says what it runs on -- its lead member's card in the `standard`
   lineup, the model `GET models/resolve` names -- and its link opens that
   card in Roles with the MODEL strip's select focused.
Run: python -m tests.test_studio_model_select
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUNS: dict = {}


def _got(ctx: Ctx, kind: str) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_model_select", why="the model select checks need headless Chrome",
                      cache=_RUNS, key=kind, args=(kind,), timeout=400, tail=400, stdin=False, what=f"the {kind} driver")
    return info


@test
def test_orchestra_shows_the_model_without_the_disclosure(ctx: Ctx):
    got = _got(ctx, "forms")
    ctx.check(f"its first option is the lineup's lead model, got {got.get('orch_first')!r}", got.get("orch_first") == "the lineup's (fakeco/beta-2)")
    ctx.check("it sits outside the closed disclosure", got.get("orch_outside_disclosure") is True)
    ctx.check(f"the catalog is in it and a pick lands, got {got.get('orch_options')} {got.get('orch_value')!r}",
              got.get("orch_options") == ["or:fakeco/alpha-1", "or:fakeco/beta-2"] and got.get("orch_value") == "or:fakeco/alpha-1")
    ctx.check(f"the disclosure keeps the roles only, got {got.get('orch_summary')!r}", got.get("orch_summary") == "who plays the parts (main leads, subagent works)")


@test
def test_design_projects_and_new_project_use_the_select(ctx: Ctx):
    got = _got(ctx, "forms")
    ctx.check(f"the open project's model, the default first, got {got.get('design_value')!r} {got.get('design_first')!r}",
              got.get("design_value") == "default" and got.get("design_first") == "the default (fakeco/alpha-1)")
    ctx.check(f"a pick saves the project, got {got.get('design_saved')!r}", got.get("design_saved") == "or:fakeco/beta-2")
    ctx.check(f"New project makes it on the picked model, got {got.get('new_first')!r} {got.get('new_saved')!r}",
              got.get("new_first") == "the default (fakeco/alpha-1)" and got.get("new_saved") == "or:fakeco/alpha-1")


@test
def test_team_stage_says_what_it_runs_on_and_links_to_the_card(ctx: Ctx):
    got = _got(ctx, "team")
    want = got.get("want") or {}
    ctx.check(f"runs on its lead's lineup card, got {got.get('source')!r} {got.get('ref')!r} want {want}",
              got.get("source") == "lineup" and got.get("ref") == want.get("ref") and "writer's card (main) in standard" in str(got.get("text")))
    ctx.check(f"the link opens that card in Roles, its select focused, got {got.get('roles_card')!r} {got.get('roles_lineup')!r}",
              got.get("roles_card") == want.get("card") and got.get("roles_lineup") == "standard")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
