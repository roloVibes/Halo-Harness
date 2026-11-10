"""tests.test_studio_workflows -- Agents -> Workflows, the board of squares (Halo 3.3.16.0 R3; the owner: "have that
whole entire workflow in like a square ... make it clean and clear"), in headless Chrome through
tests/helpers/studio_workflows.py (skipped without one), over a scratch home with no square enabled; no model call.
The board's rules (ROADMAP "Clean and clear"), each pinned:

1. nothing opens on load; the empty board is one sentence and a Library button;
2. the library's three groups (yours, packs, shipped), one row per square; `/` focuses its search;
3. a drag raises one confirm card (WHAT / COST / TIME / WRITES); Enable puts the square on the board, 240 x 140 on
   the 12 px grid, the name then the four mono lines and the limits chip, nothing else, never overlapping, with its
   one line; the edges are still at rest;
4. select shows the summary inspector (a dl, then Edit rows); Enable and Budget are pages of their own (a shipped
   square's Budget says how to copy it); Back;
5. keys: Escape clears, an arrow moves the selection, Enter opens the inspector, Delete asks in the inspector (no
   pop-up); the card's `x` takes it off with its line;
6. a session row whose square agent runs: exactly one square glows and one edge moves, its cost beside main;
7. no bar under 36 px, no row under 40 px.
Plus (no Chrome) the board's sources: the files under the 250-line cap, tokens only in workflows.css.
Run: python -m tests.test_studio_workflows
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
UI = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src"


def _got(ctx: Ctx) -> dict:
    got = driver_got(ctx, "tests.helpers.studio_workflows", why="the Workflows board needs headless Chrome", cache=_RUN,
                     args=("board",), timeout=420)
    ctx.check(f"the driver ran every step, failed: {got.get('failed')}", not got.get("failed"))
    return got


@test
def test_nothing_opens_on_load_and_the_empty_board_is_one_sentence(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the sentence, got {got.get('empty')!r}",
              str(got.get("empty") or "").startswith("No workflows enabled: drag one from the library, or halo workflows enable media"))
    ctx.check(f"nothing open, the Library button there, got {got.get('quiet')}", got.get("quiet") == {
        "library": False, "inspector": False, "confirm": False, "dialogs": 0, "view": "workflows", "button": True})


@test
def test_the_library_has_three_groups_and_slash_searches(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"yours, packs, shipped, got {got.get('groups')}", got.get("groups") == ["yours:0", "packs:0", "shipped:5"])
    ctx.check(f"the shipped rows, got {got.get('shipped_rows')}", got.get("shipped_rows") == ["code", "media", "plan", "research", "review"])
    ctx.check("/ focuses the search", got.get("slash") == "search")


@test
def test_a_drop_asks_once_then_the_card_is_on_the_board(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the confirm card's four lines, got {got.get('confirm')}", got.get("confirm") == ["WHAT", "COST", "TIME", "WRITES"])
    text = str(got.get("confirm_text") or "")
    ctx.check(f"it states the cost and what it writes, got {text!r}", "band low · cap $1.00" in text
              and "~/.halo/config.json, the key workflows.enabled" in text and got.get("cards_before_ok") == 0)
    ctx.check(f"the one line, got {got.get('note_on')!r}",
              str(got.get("note_on") or "").startswith("media enabled for the auto lineup (wrote config workflows.enabled)"))
    card = got.get("card") or {}
    ctx.check(f"240 x 140 on the grid, got {card}", card.get("w") == 240 and card.get("h") == 140
              and card.get("left", 1) % 12 == 0 and card.get("top", 1) % 12 == 0)
    ctx.check(f"the name, four lines, the chip, nothing else, got {card}", card.get("labels") == ["DOES", "TAKES", "GIVES", "COSTS"]
              and card.get("chip") == "depth 1 · 30 turns · 900 s" and card.get("kids") == 3)
    two = got.get("two") or []
    boxes = [(x, y, x + w, y + h) for _r, x, y, w, h in two]
    overlap = any(a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3] for i, a in enumerate(boxes) for b in boxes[i + 1:])
    ctx.check(f"two squares never overlap, on the grid, got {two}", len(two) == 2 and not overlap
              and all(v % 12 == 0 for _r, x, y, _w, _h in two for v in (x, y)))
    ctx.check(f"main's lines, still at rest, got {got.get('edges')} / {got.get('moving_at_rest')}", got.get("edges") == 2 and got.get("moving_at_rest") == 0)


@test
def test_select_shows_the_summary_and_its_pages(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the summary dl, got {got.get('summary')}", got.get("summary") == ["does", "takes", "gives", "covers", "lead", "engine", "costs", "limits", "from"])
    ctx.check(f"the Edit rows, got {got.get('edit_rows')}", got.get("edit_rows") == ["wf-block-purpose", "wf-block-when", "wf-block-agents", "wf-block-enable", "wf-block-budget", "wf-block-limits", "wf-block-yaml"])  # 3.3.16.3
    ctx.check(f"Enable is a page, got {got.get('enable_page')!r}", "media is on for the auto lineup: main may hand it work." in str(got.get("enable_page")))
    ctx.check(f"Budget is a page; a shipped square says how to copy it, got {got.get('budget_page')!r}",
              "halo workflows new my-media --from media" in str(got.get("budget_page")) and got.get("budget_disabled") is True)


@test
def test_the_keys_and_the_x(ctx: Ctx):
    got = _got(ctx)
    ctx.check("Escape clears the inspector", got.get("esc") == "closed")
    ctx.check(f"an arrow moves, Enter opens, got {got.get('arrow')} {got.get('enter')}", got.get("arrow") == got.get("enter") == "plan")
    ctx.check(f"Delete asks in the inspector, no pop-up, got {got.get('delete')} {got.get('delete_dialogs')}",
              got.get("delete") == "remove" and got.get("delete_dialogs") == 0)
    ctx.check(f"the x takes it off with its line, got {got.get('note_off')!r}",
              str(got.get("note_off") or "").startswith("plan disabled for the auto lineup (wrote config workflows.enabled)"))


@test
def test_one_glowing_square_while_its_agent_works(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"media glows, alone, got {got.get('glow')}", got.get("glow") == ["media"])
    ctx.check(f"one moving edge, toward it, got {got.get('live_edges')}", got.get("live_edges") == ["media"])
    ctx.check(f"its cost beside main, got {got.get('working_cost')!r}", got.get("working_cost") == "media $0.0123")
    live = got.get("live_square") or []
    ctx.check(f"Live: the square's node, its engine, the session's cost beside its own, got {live}",
              len(live) == 3 and live[0] == "media" and live[1] == "session" and "of session" in str(live[2]))


@test
def test_no_bar_under_36_no_row_under_40(ctx: Ctx):
    got = _got(ctx)
    bad = [f"bar {t} {h}" for t, h in got.get("bars") or [] if h < 36] + [f"row {t} {h}" for t, h in got.get("rows") or [] if h < 40]
    ctx.check(f"measured, got {len(got.get('bars') or [])} bars {len(got.get('rows') or [])} rows", got.get("bars") and got.get("rows"))
    ctx.check(f"offenders: {bad}", not bad)


@test
def test_the_sources_stay_small_and_use_tokens(ctx: Ctx):
    files = [UI / "routes" / "agents" / "workflows" / n for n in ("Board.tsx", "Card.tsx", "Library.tsx", "Edges.tsx", "WorkflowSummary.tsx",
                                                                  "YamlPage.tsx", "store.ts")] + [UI / "styles" / "workflows.css"]
    for f in files:
        n = len(f.read_text(encoding="utf-8").splitlines())
        ctx.check(f"{f.name}: {n} lines, under 250", n <= 250)
    css = (UI / "styles" / "workflows.css").read_text(encoding="utf-8")
    ctx.check("no literal colour in workflows.css", not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", css))
    edges = (UI / "routes" / "agents" / "workflows" / "Edges.tsx").read_text(encoding="utf-8")
    ctx.check("the card is 240 x 140 on the 12 px grid", "CARD_W = 240" in edges and "CARD_H = 140" in edges and "GRID = 12" in edges)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
