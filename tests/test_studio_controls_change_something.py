"""tests.test_studio_controls_change_something -- Halo 3.6.0.2 R42 (owner's point 5: "No dead controls in the two views this
round touches"): every control in Session's Live drawer and in Agents' four views changes the page the moment it is
pressed (a MutationObserver counts more than nothing, awaited after a fetch), or it is taken out. Driven in headless
Chrome by tests/helpers/studio_controls.py (its docstring says how a press is made and counted; skipped without
Chrome; browser-driven: the Linux VM and CI only).

Groups: `session` (Session's Live drawer: the zoom row and Fit, the pair, [New session], "↓ n more below", [Open in
Agents -> Live], a box / step row / line click, each button of the step-in card), `map` (3 · Map: the picker, + New map,
the switch, Run a goal, Lock, Undo, Dismiss, `map-fresh`, [Open it], [Watch it in Live], Replay / Back to now, the tabs,
Attention), `live` (4 · Live: the picker, a box and its card, the Feed and its controls), `agents` and `workflows`
(every visible control of 1 · Agents and 2 · Workflows at rest, enumerated). A failure lists `name: not found` or
`name: nothing changed`.
Run: python -m tests.test_studio_controls_change_something
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.studio_controls import failures  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
# the controls each group must find and see change the page (R42 names them; a group's list is checked in full)
SESSION = ["the pair: Running", "the pair: Just built", "Zoom out", "the zoom (100%)", "Zoom in", "Fit", "[New session]",
           "the New session form's x", "↓ n more below", "a step row", "the card: Pause", "the card: Resume",
           "the card: steer field (Enter sends)", "the card: Stop", "Stop's confirm: Cancel", "the card: x", "a box",
           "the card: Open in Agents -> Live", "a line", "an off-map line's card: Open the map at main", "[Open in Agents -> Live]"]
MAP = ["[Watch it in Live]", "the map picker", "+ New map", "Make (a name it refuses)", "the error's Dismiss", "the new map's Cancel", "New sessions run on this",
       "Undo (the switch)", "Run a goal", "Lock", "Lock (off again)", "n new, not connected yet", "Undo (the box)", "[Open it]", "Replay",
       "Back to now (History)", "Back to now (the replay line)", "Zoom out", "the zoom (100%)", "Zoom in", "Fit", "the tab 1 · Agents",
       "the tab 2 · Workflows", "the tab 4 · Live", "the tab 3 · Map", "Attention", "Attention's x"]
LIVE = ["Which session", "a box", "the card: Pause", "the card: x", "Feed", "the Feed's filter", "the Feed's Steer", "the Feed's Stop",
        "Stop's No", "the box head's Pause"]
# what 1 · Agents and 2 · Workflows may leave unpressed, and why (anything else not pressed is a failure)
SKIP_WHY = {"disabled at rest (nothing to press)", "writes or starts a run without a confirm", "opens a new tab", "a select with one choice",
            "the tab shown now (pressing it keeps the page as it is)"}


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_controls", why="every control is pressed in headless Chrome", cache=_RUN, timeout=1500)


def _group(ctx: Ctx, got: dict, name: str, want: "list | None") -> None:
    recs = got.get(name) or []
    names = [r.get("name") for r in recs]
    if want is not None:
        ctx.check(f"{name}: every control R42 names was pressed, missing {[w for w in want if w not in names]}", all(w in names for w in want))
    else:
        ctx.check(f"{name}: the tab's controls were enumerated, got {got.get(name + '_rest')}", len(recs) >= 3)
    bad = failures(recs)
    ctx.check(f"{name}: every control found and the page changed when pressed, failed: {bad}", not bad)


@test
def test_every_control_changes_something(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the driver ran every group, got {got.get('failed')!r}", not got.get("failed"))
    _group(ctx, got, "session", SESSION)
    fb, fa = got.get("fit_before"), got.get("fit_after") or [None, None]
    ctx.check(f"Session's Fit, once fitted: hidden with its slot kept (the same box), got {fb} -> {fa}",
              fa[0] == "hidden" and bool(fb) and all(abs(x - y) <= 0.5 for x, y in zip(fb, fa[1] or [])))
    _group(ctx, got, "map", MAP)
    ctx.check(f"3 · Map: the run overlay's old controls are gone (R55), got {got.get('gone')}", got.get("gone") == 0)
    _group(ctx, got, "live", LIVE)
    ctx.check(f"4 · Live: no editing handle (R34: no dot, no When label to press), got {got.get('handles')}", got.get("handles") == [0, 0])
    for g in ("agents", "workflows"):
        _group(ctx, got, g, None)
        why = {w for _, w in got.get(g + "_skipped") or []}
        ctx.check(f"{g}: only writers, disabled controls and new-tab links are left unpressed, got {got.get(g + '_skipped')}", why <= SKIP_WHY)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
