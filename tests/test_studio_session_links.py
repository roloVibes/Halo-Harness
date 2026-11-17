"""tests.test_studio_session_links -- the links into the Session dashboard in a
real browser (Halo 3.1.4.0 R2; headless Chrome through the driver base,
tests/helpers/studio_session.py `links` -> studio_session_links.py; skipped
without one), over this harness's real session mid-work:

a live Orchestra run led by this harness's session: its pages (the Map's line, Open) have Watch in Session, which
opens Session with that session chosen. 3.6.0.0 R5: Live's Watch in Session, its node menu's Open in Session and Roles'
Live tab went with those views.
Run: python -m tests.test_studio_session_links
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_studio_session import _driver, _ran  # noqa: E402  (one driver runner, its cache per module)

test, TESTS = new_registry()


@test
def test_orchestra_run_line_watches_its_session(ctx: Ctx):
    r, got = _driver("links")
    _ran(ctx, r, got)
    if (got.get("open_clicks") or 1) > 1 or got.get("settled") is False:  # said on a green run too (the driver's note)
        print(f"    (the Map's Open took {got.get('open_clicks')} click(s) before its drawer showed the run; "
              f"the Map had settled first: {got.get('settled')})")
    ctx.check(f"a live run's line has the button, got {got.get('watch_orchestra')!r}", got.get("watch_orchestra") == "Watch in Session")
    # P8 batch 3 (the coordinator's ruling; red on dc72c152, the drawing went 38 px down): the run's row is there from the
    # Map's first draw, one line high, empty and hidden from a screen reader; a goal run of 40 characters starting moves
    # nothing; one of 200 characters grows the row once, whole, and nothing moves after that
    s = got.get("starts") or {}
    none, short, long_, later = (s.get(k) or {} for k in ("no_run", "short", "long", "long_later"))
    row = s.get("empty_row") or [0, None, "?"]
    ctx.check(f"P8 batch 3: with no goal run the run's row is drawn, one line high, empty, aria-hidden, got {row}",
              row[0] >= 20 and row[1] == "true" and row[2] == "")
    ctx.check(f"P8 batch 3: a 40-character goal run starting moves nothing on the Map, got {none} -> {short} "
              f"(the row's parts [left, top, width, height]: {s.get('short_parts')})",
              bool(none.get("drawing")) and short == none)
    lw = s.get("long_whole") or {}
    ctx.check(f"P8 batch 3: a 200-character goal is whole on screen, got {lw}",
              "the shop staff" in str(lw.get("text")) and lw.get("fits") is True and lw.get("cut") is False)
    ctx.check(f"P8 batch 3: after the row grew once for it, nothing moves, got {long_} -> {later}",
              bool(long_.get("drawing")) and later == long_)
    # P4 batch 9 (the Map's top line draws its buttons in one parent): Open is pressed once, the same node before and after
    w = got.get("whole") or {}
    ctx.check(f"P8: the goal's 120 characters whole on the top line, wrapped, nothing cut, got {w}",
              str(w.get("text") or "").endswith("then make the tests pass") and w.get("fits") is True and w.get("cut") is False)
    ctx.check(f"P8: the goal run's Open is drawn inside the top line's box, got {w.get('open_inside')!r}", w.get("open_inside") is True)
    # P8 repair (the owner's rule: nothing moves after the first draw): with the answers held, the Map's drawing waits for
    # the goal runs' listing (on 79f00437 it was drawn first and the run's line pushed it 44 px down); its first draw
    # holds the run's line; after it, as every other answer lands, nothing on the Map moves
    h = got.get("held") or {}
    first = h.get("first") or {}
    ctx.check(f"P8 repair: nothing of the Map's drawing before the goal runs are listed, got {h.get('drawn_before_runs')}",
              not {"drawing", "top line", "zoom"} & set(h.get("drawn_before_runs") or ["?"]))
    ctx.check(f"P8 repair: the first draw holds the drawing, the top line, the zoom and the run's Open, got {sorted(first)}",
              {"drawing", "top line", "zoom", "run open"} <= set(first) and h.get("run_landed") == "landed")
    ctx.check(f"P8 repair: after the first draw nothing on the Map moves, got {h.get('moved')} "
              f"(released {h.get('released')})", h.get("moved") == [])
    ctx.check(f"Open pressed once, the same node before and after the Map settled, got {got.get('open_clicks')} {got.get('open_same_node')!r}",
              got.get("open_clicks") == 1 and got.get("open_same_node") is True)
    ctx.check(f"it opens Session with the run's session chosen, got {got.get('orchestra_tab')!r} {got.get('orchestra_session')}",
              str(got.get("orchestra_tab")).startswith("Session") and got.get("orchestra_session") == got.get("sid"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
