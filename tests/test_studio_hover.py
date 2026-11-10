"""tests.test_studio_hover -- Halo 3.3.16.1, "hover says what a box is; a click says everything" (the owner, 2026-11-10:
"hovering over gives a solid summary, if we click one we get that other panel with all the detail about the selected
box"). Unit pins over the source and the catalog, then headless Chrome through tests/helpers/studio_hover.py (skipped
without one); no provider request, no model call:

1. the shared card: one host, `role="tooltip"`, the 350 ms rest, the 8 px margin, `data-kind` / `data-for`; the
   setting `studio.hover_cards` (Settings -> Studio, on by default);
2. nothing with `hover-card` after Cast, Live and Workflows load;
3. the real pointer resting on a Cast card, a Live agent (its NOW follows a seeded tool frame), a session and a machine,
   a square on the board and a library row shows one card of that kind with its rows; leaving removes it; a press
   removes it and the inspector opens as before; Tab to a node shows its card; Esc removes it;
4. a right-most and a bottom-most box in a narrow window: the card inside the window, off its box;
5. every card: one on the page, no button, at most eight rows, no row's text overflowing, the 12 px inset, rows >= 20 px,
   the labels in mono caps;
6. `studio.hover_cards` off: no card, the titles back, a square's hover shows the inspector as before.
Run: python -m tests.test_studio_hover
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
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
_RUN: dict = {}
CARDS = ("cast", "agent", "session", "machine", "edge_right", "edge_bottom", "square", "row")


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_hover", why="the hover cards are drawn in headless Chrome", cache=_RUN,
                      timeout=420, tail=800, what="the hover driver")


def _src(rel: str) -> str:
    return (UI / rel).read_text(encoding="utf-8")


def _rows(card: dict) -> dict:
    return {r[0]: r[2] for r in (card or {}).get("rows") or []}


@test
def test_the_shared_card_and_its_setting(ctx: Ctx):
    host, store, place = _src("lib/ui/HoverCard.tsx"), _src("lib/hover/store.ts"), _src("lib/hover/place.ts")
    ctx.check("one host, a tooltip naming its kind and its box", 'role="tooltip"' in host and 'data-testid="hover-card"' in host
              and "data-kind={shown.kind}" in host and "data-for={shown.key}" in host and "<HoverCardHost />" in _src("App.tsx"))
    ctx.check("the rest is 350 ms", "export const HOVER_DELAY = 350;" in store)
    ctx.check("an 8 px margin, right then left then below then above", "export const MARGIN = 8;" in place
              and place.index('side: "right"') < place.index('side: "left"') < place.index('side: "below"') < place.index('side: "above"'))
    from halo_harness.settings_catalog import GROUP_TITLES, row
    r = row("studio.hover_cards")
    ctx.check(f"studio.hover_cards is a bool on Settings -> Studio, on by default, got {r}",
              r is not None and r.kind == "bool" and r.default is True and r.group == "studio" and GROUP_TITLES.get("studio") == "Studio")


@test
def test_nothing_opens_on_load(ctx: Ctx):
    got = _got(ctx)
    for view in ("cast", "live", "workflows"):
        ctx.check(f"{view}: no hover card after it loads", got.get(f"quiet_{view}") is True)


@test
def test_each_kind_shows_its_card(ctx: Ctx):
    got = _got(ctx)
    cast = got.get("cast") or {}
    model = _rows(cast).get("model", "")
    ctx.check(f"a Cast card: kind cast, its model with where it comes from, got {model!r}",
              cast.get("kind") == "cast" and bool(model) and ("from " in model or "'s model" in model or "picked when" in model))
    ctx.check("the Cast card's title tooltip is off", got.get("cast_title_attr") is None)
    ctx.check("moving away removes it", got.get("cast_left") == "gone")
    agent = _rows(got.get("agent"))
    ctx.check(f"a Live agent: its state and its model, got {agent}", (got.get("agent") or {}).get("kind") == "agent"
              and agent.get("state", "").startswith("running") and "or:mock/qwen3-coder" in agent.get("model", ""))
    ctx.check(f"its NOW follows the seeded tool frame, got {got.get('agent_now')!r}", "Bash" in str(got.get("agent_now")) and "pytest" in str(got.get("agent_now")))
    sess, mach = got.get("session") or {}, got.get("machine") or {}
    ctx.check(f"a session: where it works, got {_rows(sess)}", sess.get("kind") == "session" and "feature/basket" in _rows(sess).get("where", ""))
    ctx.check(f"a machine: what it has, in full, got {_rows(mach)}", mach.get("kind") == "machine" and bool(_rows(mach).get("what-it-has"))
              and got.get("machine_title_attr") is None)
    sq, row = got.get("square") or {}, got.get("row") or {}
    ctx.check(f"a square on the board: its contract, got {_rows(sq)}", sq.get("kind") == "square" and sq.get("for") == "media"
              and {"takes", "gives", "runs-on", "costs", "limits", "from"} <= set(_rows(sq)))
    ctx.check("the square's hover no longer opens the inspector", got.get("square_no_inspector") is True)
    ctx.check(f"a click on it opens the inspector and hides the card, got {got.get('square_click')!r}", got.get("square_click") == "media")
    ctx.check(f"a library row: its own card, got {row.get('for')!r}", row.get("kind") == "square" and row.get("for") == "library:media")


@test
def test_a_press_and_the_keyboard(ctx: Ctx):
    got = _got(ctx)
    ctx.check("a press removes the card", got.get("press_gone") == "gone")
    ctx.check(f"and the inspector opens on the agent as before, got {got.get('press_inspector')!r}",
              str(got.get("press_inspector") or "").endswith("|t7e5s1t0"))
    ctx.check("the card stays gone while the pointer rests after the press", got.get("press_stays_gone") is True)
    ctx.check(f"Tab to a node shows its card, got {got.get('tab')}", (got.get("tab") or [None])[0] == "agent" and (got.get("tab") or [0, 0, 0])[2] == "roles-live-node")
    ctx.check("Esc removes it", got.get("esc_gone") == "gone")


@test
def test_the_card_stays_inside_the_window_and_off_its_box(ctx: Ctx):
    got = _got(ctx)
    for name in CARDS:
        c = got.get(name) or {}
        card, box, vw, vh = c.get("card"), c.get("box"), c.get("vw", 0), c.get("vh", 0)
        if not card or not box:
            ctx.check(f"{name}: a card beside an aria-describedby box, got {c.get('box_testid')!r}", False)
            continue
        ctx.check(f"{name}: inside the window with 8 px, got {card} in {vw}x{vh}", card[0] >= 8 and card[1] >= 8 and card[2] <= vw - 8 and card[3] <= vh - 8)
        ctx.check(f"{name}: never over its box, card {card} box {box}", card[2] <= box[0] or card[0] >= box[2] or card[3] <= box[1] or card[1] >= box[3])
        width = card[2] - card[0]
        ctx.check(f"{name}: right only when it fits there, got {c.get('side')}", c.get("side") != "right" or box[2] + 8 + width <= vw - 8)
    right = got.get("edge_right") or {}
    ctx.check(f"the right-most box's card flips left, got {right.get('side')}", right.get("side") == "left")


@test
def test_every_card_is_one_quiet_readable_thing(ctx: Ctx):
    got = _got(ctx)
    for name in CARDS:
        c = got.get(name) or {}
        ctx.check(f"{name}: one card, a tooltip, no button, got {c.get('count')} / {c.get('role')} / {c.get('buttons')}",
                  c.get("count") == 1 and c.get("role") == "tooltip" and c.get("buttons") == 0)
        ctx.check(f"{name}: a title, at most eight rows, a last line, got {len(c.get('rows') or [])}",
                  bool(c.get("title")) and 0 < len(c.get("rows") or []) <= 8 and bool(c.get("foot")))
        ctx.check(f"{name}: no row's text overflows, got {c.get('over')}", c.get("over") == [])
        ctx.check(f"{name}: no unknown fact printed, got {_rows(c)}", not any(v.strip() in ("?", "0", "$0.0000") for v in _rows(c).values()))
        ctx.check(f"{name}: the 12 px inset, got {c.get('pad')}", min(c.get("pad") or [0]) >= 12)
        ctx.check(f"{name}: rows >= 20 px, got {c.get('row_h')}", min(c.get("row_h") or [0]) >= 20)
        caps = c.get("caps") or ["", ""]
        ctx.check(f"{name}: labels in mono caps, got {caps}", caps[0] == "uppercase" and "mono" in caps[1].lower())


@test
def test_the_setting_off_is_the_page_before(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the titles are back, got {got.get('off_titles')!r}", bool(got.get("off_titles")))
    ctx.check("no card while the pointer rests", got.get("off_none") is True)
    ctx.check("a square's hover shows the inspector as before, and no card", got.get("off_square_inspector") == "hover" and got.get("off_square_none") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
