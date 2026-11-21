"""tests.test_studio_owner_tab -- a Studio tab that can only look says so in one plain line and has a button, "Make this
tab yours", that makes it able to change things with one press (Halo 3.6.0.6 P, the owner's point 31: "harness level
guard 'owners page' is blocking!"), in headless Chrome through tests/helpers/studio_owner_tab.py (skipped without
Chrome), with the pack that ships with Halo (doc-review) enabled. The rule of who gets the proof does not change
(tests/test_studio_owner_proof.py, test_studio_owner_routes.py, test_studio_owner_probe.py):

1. a tab reached by a link: the notice row, its button and its hover from the first draw (nothing moves), VIEW ONLY in
   the status bar with the sentence as its hover; Try it on the pack's workflow is 403 and the ONE toast of a refused
   write carries the same sentence and button (a view's own toast of it folds into it);
2. the button pressed for real: the tab reloads as his own page, and Try it answers 200 with its result;
3. a scripted click() on the button does nothing (the handler takes only a trusted press);
4. the toast's own button, pressed: the same, Try it answers 200;
5. (3.6.0.6 PF) Studio started again under his open tab and its new address entered over it: the row says so at once
   ("... because Studio was started again since it was opened."), the press makes it his; no page error on the way.
Run: python -m tests.test_studio_owner_tab
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
LINE = "This tab can look but not change things, because a link or a script opened it."
BUTTON = "Make this tab yours"
HOVER = "Reloads this tab; after that it can change things."


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_owner_tab", why="the tab is driven in headless Chrome", cache=_RUN, timeout=600)


@test
def test_a_tab_a_link_opened_says_so_and_offers_the_button(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the launcher's page is his own (no row, no VIEW ONLY), got {got.get('own_page')}", got.get("own_page") is True)
    n = got.get("link") or {}
    ctx.check(f"the row says it word for word, got {n.get('row')!r}", n.get("row") == LINE)
    ctx.check(f"its button and hover, got {n.get('button')!r} {n.get('hover')!r}", n.get("button") == BUTTON and n.get("hover") == HOVER)
    ctx.check(f"the status bar reads VIEW ONLY, its hover the sentence, got {n.get('cell')!r} {n.get('cell_hover')!r}",
              (n.get("cell") or "").strip() == "VIEW ONLY" and n.get("cell_hover") == LINE)
    first, now = n.get("first") or {}, n.get("now") or {}
    ctx.check(f"the row is there from the first draw and nothing moved, got first {first} now {now}",
              first.get("row", -1) > 0 and first == now)


@test
def test_a_refused_write_shows_the_one_toast_with_the_button(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Try it in that tab: 403, got {got.get('link_try')}", any(w.startswith("POST crew/try 403") for w in got.get("link_try") or []))
    t = got.get("link_toast") or {}
    ctx.check(f"one toast with the sentence and the button, and no second toast of it, got {t}",
              t.get("count") == 1 and t.get("line") == LINE and t.get("button") == BUTTON
              and not any("look but not change" in o for o in t.get("others") or []))


@test
def test_the_press_makes_the_tab_his_and_try_it_runs(ctx: Ctx):
    got = _got(ctx)
    p = got.get("pressed") or {}
    ctx.check(f"after the press: no row, no VIEW ONLY, got {p}", p.get("row") is None and p.get("cell") is None)
    ctx.check(f"Try it answers 200, got {got.get('pressed_try')}", any(w.startswith("POST crew/try 200") for w in got.get("pressed_try") or []))
    ctx.check(f"with its result, got {got.get('pressed_state')!r}", got.get("pressed_state") in ("done", "failed"))


@test
def test_a_scripted_click_does_nothing(ctx: Ctx):
    s = _got(ctx).get("scripted") or {}
    ctx.check(f"no reload and the row stays, got {s}", s.get("reloaded") is False and s.get("row") is True)


@test
def test_the_toasts_button_makes_the_tab_his(ctx: Ctx):
    got = _got(ctx)
    b = got.get("toast_before") or {}
    ctx.check(f"the refused write's toast carries the button, got {b}", b.get("button") == BUTTON and b.get("count") == 1)
    a = got.get("toast_after") or {}
    ctx.check(f"after its press: no row, no VIEW ONLY, got {a}", a.get("row") is None and a.get("cell") is None)
    ctx.check(f"Try it answers 200, got {got.get('toast_try')}", any(w.startswith("POST crew/try 200") for w in got.get("toast_try") or []))


AGAIN = "This tab can look but not change things, because Studio was started again since it was opened."


@test
def test_a_tab_open_across_a_restart_says_so_and_the_press_makes_it_his(ctx: Ctx):
    """3.6.0.6 PF: his own tab; Studio started again on the same port; its new address entered over the tab (only the
    `#t=` differs: no reload). The page takes the new key, but its proof was made for the old one: the row says so at
    once, with the button; one real press makes the tab work."""
    got = _got(ctx)
    ctx.check(f"entering the new address did not reload the tab, got {got.get('again_reloaded')}", got.get("again_reloaded") is False)
    a = got.get("again") or {}
    ctx.check(f"the row says Studio was started again, with the button, got {a}", a.get("row") == AGAIN and a.get("button") == BUTTON
              and a.get("hover") == HOVER)
    ctx.check(f"VIEW ONLY with the same sentence as its hover, got {a.get('cell')!r} {a.get('cell_hover')!r}",
              (a.get("cell") or "").strip() == "VIEW ONLY" and a.get("cell_hover") == AGAIN)
    p = got.get("again_pressed") or {}
    ctx.check(f"after the press: no row, no VIEW ONLY, got {p}", p.get("row") is None and p.get("cell") is None)
    ctx.check(f"Try it answers 200, got {got.get('again_try')}", any(w.startswith("POST crew/try 200") for w in got.get("again_try") or []))
    ctx.check(f"no page error on the way, got {got.get('page_errors')}", got.get("page_errors") == [])
    ctx.check(f"the driver ran to the end, got {got.get('failed')}", "failed" not in got)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
