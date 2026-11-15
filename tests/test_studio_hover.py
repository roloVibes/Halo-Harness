"""tests.test_studio_hover -- Halo 3.3.16.1, "hover says what a box is; a click says everything" (the owner, 2026-11-10:
"hovering over gives a solid summary, if we click one we get that other panel with all the detail about the selected
box"). The shared card: one host, `role="tooltip"`, the 350 ms rest, the 8 px margin, `data-kind` / `data-for`; the
setting `studio.hover_cards` (Settings -> Studio, on by default). 3.6.0.0 R5: the Chrome checks over Cast's cards, Live's
agents and the board's squares (tests/helpers/studio_hover.py) went with those views; the Map's boxes show the same
card (tests/helpers/studio_map_takeover_more.py reads it).
Run: python -m tests.test_studio_hover
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
def _src(rel: str) -> str:
    return (UI / rel).read_text(encoding="utf-8")


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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
