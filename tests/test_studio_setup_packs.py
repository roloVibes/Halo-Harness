"""tests.test_studio_setup_packs -- a pack's own Setup blocks in Studio (Halo 3.3.11.0 R3, routes/setup/PackBlocks.tsx,
packSetup.ts, pages.ts, SetupRail.tsx, Check.tsx, Summary.tsx). Headless Chrome through tests/helpers/
studio_setup_packs.py (skipped without one), over a seeded scratch home with the fixture pack setup-blocks; no
provider request, no model call:

1. the pack disabled: the rail is the core one (the same steps as a home with no pack);
2. enabled: the three blocks in the rail -- the form behind Default model with the pack's name on it, the check and
   the note after the core steps under the pack's name, before the Summary; `halo pack enable` named all three;
3. the form saves to the pack's settings and the rail says done; 4. the note dismisses;
5. the Check page's "From packs" row is unticked, says what / cost / time / writes, and runs green through the job;
6. the Summary lists the three with their state; `?block=pack:<id>:<block>` lands on it.
Run: python -m tests.test_studio_setup_packs
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}
P = "pack:setup-blocks:"
CORE = ["providers", "local", "model", "permissions", "theme", "team", "check", "summary"]


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_setup_packs", why="the pack Setup block checks need headless Chrome",
                      cache=_RUN, timeout=300, tail=600)


def _steps(rows) -> list:
    """The rail's step ids without Linux fixes (a step only on a box that needs them)."""
    return [r[0] for r in (rows or []) if r[0] != "linux"]


@test
def test_a_disabled_pack_leaves_the_rail_as_it_is(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the core steps only, the count of today's rail, got {got.get('off_rail')}", _steps(got.get("off_rail")) == CORE
              and len(got.get("off_rail") or []) in (len(CORE), len(CORE) + 1) and got.get("off_groups") == 0)
    ctx.check(f"halo pack enable named the three blocks waiting, got {got.get('enable_lines')}", got.get("enable_lines") == [
        "setup: setup-blocks -- Review preferences (halo setup setup-blocks)",
        "setup: setup-blocks -- Reach the review service (halo setup setup-blocks)",
        "setup: setup-blocks -- Before you start (halo setup setup-blocks)"])


@test
def test_the_blocks_join_the_rail(ctx: Ctx):
    got = _got(ctx)
    want = ["providers", "local", "model", P + "prefs", "permissions", "theme", "team", "check", P + "reach", P + "about", "summary"]
    ctx.check(f"behind Default model, then after the core steps, before the Summary, got {got.get('on_rail')}", _steps(got.get("on_rail")) == want)
    titles = [t for t in got.get("on_titles") or [] if t != "Linux fixes"]
    ctx.check(f"the pack's name on the placed one, the block titles, got {titles}", titles[3] == "Setup blocks: Review preferences"
              and titles[8:10] == ["Reach the review service", "Before you start"])
    ctx.check(f"one group label before the trailing two, got {got.get('on_groups')}", got.get("on_groups") == ["Setup blocks:"])
    states = dict((r[0], r[1]) for r in got.get("on_rail") or [])
    ctx.check("each block waiting (todo)", all(states.get(P + b) == "todo" for b in ("prefs", "reach", "about")))


@test
def test_the_form_saves_and_the_note_dismisses(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the form page: the block's title, its two fields, got {got.get('form_title')!r} {got.get('form_keys')}",
              got.get("form_title") == "Review preferences" and got.get("form_keys") == ["style", "depth"])
    ctx.check(f"saved: done on the page and in the rail, got {got.get('form_word')!r} {got.get('form_rail')!r}",
              got.get("form_word") == "done" and got.get("form_rail") == "done")
    ctx.check(f"written to the pack's settings, got {got.get('form_saved')}", got.get("form_saved") == {"setup-blocks": {"style": "long", "depth": 3}})
    ctx.check(f"the note: its markdown, then read, got {got.get('note_head')!r} {got.get('note_word')!r}",
              got.get("note_head") == "Before you start" and got.get("note_word") == "done")


@test
def test_the_pack_check_rides_the_check_page(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"under From packs, unticked, with its four lines, got {got.get('from_packs')!r} {got.get('check_ticked')} {got.get('check_detail')!r}",
              got.get("from_packs") == "From packs" and got.get("check_ticked") is False
              and got.get("check_detail") == "asks the pack's script whether the review service answers. Cost: free. Time: seconds. Writes: nothing.")
    ctx.check(f"ticked and run: green with its two lines, got {got.get('check_state')!r} {got.get('check_log')!r}",
              got.get("check_state") == "done" and got.get("check_log") == "review service: asked\nreview service: answered")
    ctx.check(f"the rail says done, got {got.get('check_rail')!r}", got.get("check_rail") == "done")


@test
def test_the_summary_and_the_door(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the Summary lists the three with their state, got {got.get('summary_packs')}", got.get("summary_packs") == [
        [P + "prefs", "done", "Setup blocks: done"], [P + "reach", "done", "Setup blocks: done"], [P + "about", "done", "Setup blocks: done"]])
    ctx.check(f"?block= lands on the block, got {got.get('door_page')!r} {got.get('door_title')!r}",
              got.get("door_page") == P + "reach" and got.get("door_title") == "Reach the review service")


@test
def test_the_source_keeps_the_shape(ctx: Ctx):
    """No Chrome needed: the round's files exist, each under the cap."""
    ui = REPO / "halo_harness" / "studio" / "ui" / "src" / "routes"
    for name in ("setup/PackBlocks.tsx", "setup/packSetup.ts", "setup/pages.ts", "setup/SetupRail.tsx", "setup/Check.tsx", "packs/PackForm.tsx"):
        p = ui / name
        ctx.check(f"{name} exists and is under 250 lines", p.is_file() and len(p.read_text(encoding="utf-8").splitlines()) < 250)
    blocks = (ui / "setup" / "PackBlocks.tsx").read_text(encoding="utf-8")
    ctx.check("the form block is the pack's own settings form", "<PackForm" in blocks and "setup/packs/" in blocks)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
