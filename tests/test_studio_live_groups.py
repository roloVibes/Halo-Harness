"""tests.test_studio_live_groups -- Live in groups (Halo 3.3.16.3, the owner: "for the auto, there should be groups of:
here's this one task and here's the sub-agents in there, and it points to that group"), in headless Chrome through
tests/helpers/studio_live_groups.py (skipped without one), over the Studio fleet rig's real session plus an Auto main's
agents with their spawn steps; no model call:

1. nothing opens on load: no hover card, no pick in the inspector, every group open;
2. one reply's three readers are one task group titled from main's own line, its counts line and Auto's pick in plain
   words; main's edge goes into the group, none into each reader; a lone scribe is not boxed and keeps its edge;
3. ten checkers are one group, a grid (three rows of up to four) inside its box with no two boxes overlapping;
4. a square's agent is a square group (its DOES line under the title), its two helpers a task group inside it;
5. no bar's text spills or is cut other than by CSS ellipsis; the group's hover card says what it is for and who is in it;
6. the chevron folds the ten to the bar; a member that waits on you lights the folded bar; the chevron opens it again;
7. Session's timeline "by group" puts a title row over each group's lanes.
Run: python -m tests.test_studio_live_groups
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
    return driver_got(ctx, "tests.helpers.studio_live_groups", why="Live in groups needs headless Chrome", cache=_RUN,
                      args=("groups",), timeout=420)


def _group(got: dict, tail: str) -> dict:
    return next((g for g in got.get("groups") or [] if str(g.get("id", "")).endswith(tail)), {})


@test
def test_nothing_opens_on_load(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"no hover card, no pick, every group open, got {got.get('quiet')} {got.get('inspector_on_load')!r} {got.get('all_open')}",
              got.get("quiet") is True and got.get("inspector_on_load") in ("", "none") and got.get("all_open") is True)


@test
def test_a_task_group_its_bar_and_its_edge(ctx: Ctx):
    got = _got(ctx)
    g = _group(got, "main#3")
    ctx.check(f"titled from main's own line, got {g.get('title')!r}", g.get("title") == "Read the three PDFs side by side")
    ctx.check(f"the counts line, got {g.get('counts')!r}", str(g.get("counts", "")).startswith("3 agents · 3 working · $0.0036"))
    ctx.check(f"Auto's pick in plain words, got {g.get('why')!r}", g.get("why") == "3 readers on kimi-k3 for a pdf in the task")
    box = got.get("readers_box") or {}
    ctx.check(f"the three inside the box under its bar, got {box}", box.get("n") == 3 and box.get("inside") is True and box.get("overlap") == 0)
    ctx.check(f"main's edge goes into the group, none into each reader, got {got.get('edge_to_group')} / {got.get('edges_to_readers')}",
              got.get("edge_to_group") == ["main"] and got.get("edges_to_readers") == 0)
    ctx.check(f"a lone agent is not boxed and keeps its edge, got {got.get('scribe_boxed')} {got.get('scribe_edge')}",
              got.get("scribe_boxed") is False and got.get("scribe_edge") == ["main"])


@test
def test_ten_agents_are_a_tidy_grid(ctx: Ctx):
    got = _got(ctx)
    g, box = _group(got, "main#4"), got.get("ten_box") or {}
    ctx.check(f"one group of ten, got {g.get('count')} {g.get('title')!r}", g.get("count") == 10 and g.get("title") == "Check the links in doc")
    ctx.check(f"three rows inside the box, no overlap, got {box}", box.get("n") == 10 and box.get("inside") is True
              and box.get("overlap") == 0 and box.get("tops") == 3)


@test
def test_a_square_group_with_a_task_inside(ctx: Ctx):
    got = _got(ctx)
    q, inner = _group(got, "|sqm1"), _group(got, "sqm1#1")
    ctx.check(f"the square's group, its DOES line, got {q.get('kind')} {q.get('title')!r} {q.get('why')!r}",
              q.get("kind") == "square" and q.get("title") == "square media" and str(q.get("why", "")).startswith("Reads and makes images"))
    ctx.check(f"its helpers a task group inside it, got {inner.get('outer')!r} for {q.get('id')!r}",
              bool(inner) and inner.get("outer") == q.get("id") and inner.get("title") == "Splitting the clip between two helpers")
    box = got.get("square_box") or {}
    ctx.check(f"all three inside the square's box, got {box}", box.get("n") == 3 and box.get("inside") is True and box.get("overlap") == 0)


@test
def test_no_bar_spills_and_the_hover_card(ctx: Ctx):
    got = _got(ctx)
    bad = [g.get("id") for g in got.get("groups") or [] if g.get("spill") or g.get("cut")]
    ctx.check(f"no bar spills or is cut but by an ellipsis, got {bad}", not bad and len(got.get("groups") or []) >= 5)
    hv = got.get("hover") or {}
    rows = {r[1]: r[2] for r in hv.get("rows") or []}
    ctx.check(f"the group's card: what it is for, who, now, got {hv}", hv.get("title") == "Read the three PDFs side by side"
              and rows.get("Who") == "3 × reader on kimi-k3" and str(rows.get("Now", "")).startswith("3 agents") and not hv.get("over"))


@test
def test_fold_and_the_ask_lights_it(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"folded: ten fewer agent boxes, got {got.get('folded')}", isinstance(got.get("folded"), list) and got["folded"][0] == 10)
    ctx.check(f"a waiting member lights the folded bar, got {got.get('asks')!r}", "1 waiting" in str(got.get("asks") or ""))
    ctx.check(f"opened again, got {got.get('reopened')}", got.get("reopened") == 20)


@test
def test_the_timeline_by_group(ctx: Ctx):
    got = _got(ctx)
    heads = got.get("timeline_groups") or []
    ctx.check(f"a title row per group, got {heads}", got.get("by_group_pressed") == "true"
              and any("Read the three PDFs side by side · 3" in h for h in heads) and any("Check the links in doc · 10" in h for h in heads))
    ctx.check(f"no step failed, got {got.get('failed')}", not got.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
