"""tests.test_packs_fleet_ui -- the packs' fleet capabilities in Studio (Halo
3.2.0.0 R4). Headless Chrome through the driver base
(tests/helpers/studio_packs_fleet.py; skipped without one), over a fresh home
with doc-review (bash granted, a model that calls tools) and fleet-needs-gpu:

1. Fleet's Capabilities card has a "packs" line: docs.review available (the
   model and the grant), gpu.render not available (no GPU here); the chips
   count the available one;
2. the Mission panel's plan names the part's pack need with the harness that
   has it, the head shows the mission's metadata (it was started with the
   pack's lineup), and the selected part shows the pack's inspector line,
   read through the pack's file route;
3. (3.2.1.0 R1) the Mission form's Lineup select, the active lineup first; the
   pack's lineup picked there rides in the new mission;
4. (3.2.1.0 R3) a member's pack inspector line shows the text its catalog
   carries.

Run: python -m tests.test_packs_fleet_ui
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.helpers import fleet_pack as _fleet_pack  # noqa: E402  (the fleet pack on: these drive its Studio doors)
_fleet_pack.on()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_packs_fleet",
                      why="the Studio fleet-capabilities checks need headless Chrome", cache=_RUN, timeout=400, tail=600)
    return info


@test
def test_the_capabilities_card_lists_the_packs_capabilities(ctx: Ctx):
    got = _got(ctx)
    rows = got.get("caps_packs") or []
    ctx.check(f"a packs line on the card, got {got.get('caps_label')}", got.get("caps_label") == ["packs"])
    ctx.check(f"docs.review: available, the model and the grant, got {rows}", bool(rows) and rows[0] ==
              ["docs.review", "yes", "available: tools: or:anthropic/claude-sonnet-4.6; bash granted"])
    ctx.check("gpu.render: not available, no GPU here", len(rows) > 1 and rows[1] == ["gpu.render", "no", "not available: no GPU here"])
    ctx.check(f"the chips count the available one, got {got.get('caps_chips')}", "+1 pack cap" in (got.get("caps_chips") or []))


@test
def test_the_mission_plan_shows_the_pack_need_metadata_and_inspector(ctx: Ctx):
    got = _got(ctx)
    on = got.get("planned_on") or "?"
    ctx.check(f"the part's need names its pack and harness, got {got.get('need_chip')!r}",
              got.get("need_chip") == f"docs.review · pack doc-review on {on}" and got.get("need_pack") == "doc-review")
    ctx.check(f"the head: the pack's mission metadata, got {got.get('metadata')!r}", got.get("metadata") == "pack doc-review · review=docs · style=short")
    ctx.check("no inspector before a part is selected", got.get("inspector_before") is False)
    ctx.check(f"selected: the pack's inspector line, got {got.get('inspector_label')!r}", got.get("inspector_label") == "Review checklist")
    ctx.check(f"its file read through the pack's route, got {str(got.get('inspector_text'))[:80]!r}",
              "Every link in a changed document resolves." in str(got.get("inspector_text")))


@test
def test_the_mission_form_sends_the_lineup(ctx: Ctx):
    """3.2.1.0 R1: the Lineup select lists the lineups `halo teams` lists, the active one (halo-dev-cycle) first;
    the pack's lineup picked there reaches the mission: its head says it, with the pack's metadata."""
    got = _got(ctx)
    opts = got.get("form_options") or []
    ctx.check(f"the active lineup first, the pack's among them, got {opts} {got.get('form_first')!r}",
              opts[:1] == ["halo-dev-cycle"] and "doc-review--review" in opts and got.get("form_first") == "halo-dev-cycle (active)")
    ctx.check(f"the seeded mission (started with the pack's lineup) says it, got {got.get('mission_lineup')!r}",
              got.get("mission_lineup") == "doc-review--review")
    ctx.check(f"planned from the form: the lineup and the pack's metadata, got {got.get('form_lineup')!r} {got.get('form_metadata')!r}",
              got.get("form_lineup") == "doc-review--review" and got.get("form_metadata") == "pack doc-review · review=docs · style=short")


@test
def test_a_members_inspector_line_shows_its_text(ctx: Ctx):
    """3.2.1.0 R3: a part on a member whose pack runs only there: the line renders the text the member's catalog
    carries (markdown), names where it runs, and no longer says "its Studio reads this file"."""
    got = _got(ctx)
    ctx.check(f"not this harness's pack, got {got.get('member_local')!r}", got.get("member_local") == "no")
    ctx.check(f"the member's text, rendered, got {got.get('member_text')!r}", "Scan rules" in str(got.get("member_text"))
              and "Only the lab subnet, never the office." in str(got.get("member_text")))
    ctx.check(f"the head names the pack, the file and where it runs, got {got.get('member_head')!r}",
              got.get("member_head") == "Scan rules pack net-scan · fleet/rules.md · on kali@lab")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
