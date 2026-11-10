"""tests.test_studio_blocks -- blocks on one canvas (Halo 3.3.16.3, the owner: "different blocks that you can almost like
drag and drop in the agents tab ... here is the media workflow ... here's my thinking block"), in headless Chrome
through tests/helpers/studio_blocks.py (skipped without one), over a scratch home on the auto lineup with the shipped
`media` square and `my-media` (a copy in yours with three agents) enabled; no model call:

1. Cast draws the lineup's tiers, each with its purpose line, AND the two squares as blocks, main's line into each;
   nothing opens on load;
2. my-media, open, shows its three agents (role, model) and a footer with its limits and cost band; no block overlaps a
   tier box or another block, no text spills but by CSS ellipsis;
3. the chevron folds it to its lines and a reload keeps it folded; the chevron opens it again;
4. a click on the block opens its summary in the inspector: Purpose, Agents, Enable, Budget, Limits, YAML, each its own
   page; the Agents page lists who is inside; the Purpose page saves into yours and the block's line says it; a click
   on the canvas clears it.
Run: python -m tests.test_studio_blocks
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_blocks", why="the blocks need headless Chrome", cache=_RUN, args=("blocks",), timeout=420)


@test
def test_one_board_tiers_and_squares(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"nothing opens on load, got {got.get('quiet')} {got.get('insp_block')!r}", got.get("quiet") is True and got.get("insp_block") == "")
    ctx.check(f"the tiers with their purpose lines, got {got.get('tiers')}",
              got.get("tiers") == [["main", "the one you talk to"], ["pool", "the workers, picked per task"]])
    ctx.check(f"both squares as open blocks, main's line into each, got {got.get('blocks')} {got.get('edges')}",
              got.get("blocks") == [["media", True, 1], ["my-media", True, 3]] and got.get("edges") == ["media", "my-media"])


@test
def test_a_block_shows_what_is_inside(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"its three agents, lead first, each on its model, got {got.get('agents')}",
              [a[0] for a in got.get("agents") or []] == ["auto-media", "auto-researcher", "auto-reviewer"]
              and all(a[1] == "auto: picked per task" for a in got.get("agents") or []))
    ctx.check(f"its purpose and its footer, got {got.get('purpose')!r} {got.get('foot')!r}",
              str(got.get("purpose", "")).startswith("Reads and makes images") and "depth 1" in str(got.get("foot")) and "band low" in str(got.get("foot")))
    ctx.check(f"no overlap, no spill, the agents inside, got {got.get('overlap')} {got.get('spill')} {got.get('inside')}",
              got.get("overlap") == 0 and got.get("spill") == 0 and got.get("inside") is True)


@test
def test_fold_is_kept(ctx: Ctx):
    got = _got(ctx)
    f = got.get("folded") or [0, 0]
    ctx.check(f"folded to its three lines, got {f}", f[1] == 3)
    ctx.check(f"a reload keeps it folded, got {got.get('kept')!r}; opened again, got {got.get('reopened')}",
              got.get("kept") == "folded" and got.get("reopened") == 3)


@test
def test_the_block_in_the_inspector(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"summary first, one row per page, got {got.get('summary')}",
              got.get("summary") == ["purpose", "agents", "enable", "budget", "limits", "yaml"])
    ctx.check(f"the Agents page, got {got.get('agents_page')}", got.get("agents_page") == ["auto-media", "auto-researcher", "auto-reviewer"])
    ctx.check(f"the Purpose page saves and the block says it, got {got.get('saved_line')!r}", got.get("saved_line") == "saved")
    ctx.check(f"a click on the canvas clears it, got {got.get('cleared')!r}", got.get("cleared") == "clear")
    ctx.check(f"no step failed, got {got.get('failed')}", not got.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
