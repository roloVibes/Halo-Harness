"""tests.test_studio_run_parts -- Halo 3.6.0.2, P4 batch 13 (the coordinator's ruling: nothing a person could see of a run in
3.6.0.1 is lost): what the 3.6.0.0 lit Map showed of a run is back on BOTH run drawings, Session's Live drawer and
Agents -> 4 · Live, from one set of parts (routes/crew/map/runParts.tsx), in headless Chrome (driver
tests/helpers/studio_run_parts.py; skipped without Chrome; the Linux VM and CI only).

1. the tool clock: a helper in a tool call says the tool and its seconds, which grow while no box moves;
2. the talk pulse: main talking to the implementer lights the line main -> code, and no other;
3. "+{n} under it": main's box draws three rows and counts the rest; a press opens 4 · Live's Feed on main's `under:` page;
4. J / K step the selection from box to box in drawing order; J typed into the card's Steer field selects nothing;
5. no interval the drawing started is left once it is hidden (Session: another section; Live: 3 · Map);
6. (batch 13's repair) the box the session waits on (the end of the waiting path: here a helper in a Bash call that main
   handed work to) carries the 3.6.0.0 outline, and the drawing's wait link names it and picks it; (P8) a long tool line's
   link is whole on its own reserved row, which keeps its height;
7. a waiting row says what it waits for and for how long, ticking while nothing moves;
8. (P7) in Session's bottom slot the wait link never squeezes or wraps "↓ n more below", and sits inside the slot whole
   (P8: on its own reserved lines; the slot keeps its height); (P9 batch 4) a link one line longer than the room kept
   grows the slot once, in the frame it shows in, and "more below" stays where it was.
Run: python -m tests.test_studio_run_parts
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
BOTH = ("session", "live")


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_run_parts", why="the run drawings are driven in headless Chrome", cache=_RUN, timeout=600)


def _of(d: dict, where: str, step: str) -> dict:
    return {k.split(".", 2)[2]: v for k, v in d.items() if k.startswith(f"{where}.{step}.")}


@test
def test_tool_clock_ticks_and_nothing_moves(ctx: Ctx):
    d = _got(ctx)
    for w in BOTH:
        x = _of(d, w, "clock")
        reads = x.get("reads") or ["", ""]
        secs = [int(m.group(1)) if (m := re.search(r"· (\d+) s$", str(r))) else -1 for r in reads]
        ctx.check(f"{w}: the helper's row says the tool it is in, got {x.get('tool')!r} {reads} ({x.get('error')})",
                  x.get("tool") == "Bash" and all(str(r).startswith("Bash · ") for r in reads))
        ctx.check(f"{w}: its seconds grow (the second read waits for it, up to 15 s), got {secs}", secs[0] >= 0 and secs[1] > secs[0])
        ctx.check(f"{w}: no box of the drawing moved while it ticked, got {x.get('moved')}", x.get("moved") == [])


@test
def test_talk_pulses_its_line_and_no_other(ctx: Ctx):
    d = _got(ctx)
    for w in BOTH:
        x = _of(d, w, "talk")
        ctx.check(f"{w}: nothing pulses before the talk, got {x.get('before')} ({x.get('error')})", x.get("before") == [])
        ctx.check(f"{w}: main talking to the implementer pulses main -> code alone, got {x.get('lit')}", x.get("lit") == [["main", "code"]])


@test
def test_under_it_opens_the_feed_under_page(ctx: Ctx):
    d = _got(ctx)
    for w in BOTH:
        x = _of(d, w, "under")
        n = x.get("hidden") or 0
        ctx.check(f"{w}: main's box draws three rows and says '+{{n}} under it' for the rest (a button), got {x.get('text')!r} "
                  f"{x.get('tag')!r} hidden {n} ({x.get('error')})", n >= 2 and x.get("text") == f"+{n} under it" and x.get("tag") == "BUTTON")
        ctx.check(f"{w}: a press opens 4 · Live's Feed on main's under: page, got {x.get('feed')}", x.get("feed") == ["live", "main", "under:main"])


@test
def test_j_and_k_step_the_selection_never_from_a_text_box(ctx: Ctx):
    d = _got(ctx)
    for w in BOTH:
        x = _of(d, w, "jk")
        o = x.get("order") or ["?", "?"]
        ctx.check(f"{w}: J picks the first box in drawing order, J the next, K back, got {x.get('got')} (order {o}) ({x.get('error')})",
                  x.get("got") == [o[0], o[1], o[0]])
        ctx.check(f"{w}: J typed into the card's Steer field selects nothing, got {x.get('field')} {x.get('after_field')!r} {x.get('typed')!r}",
                  x.get("field") is True and x.get("after_field") == o[0] and "j" in str(x.get("typed")))


@test
def test_no_clock_interval_outlives_the_drawing(ctx: Ctx):
    d = _got(ctx)
    for w in BOTH:
        x = _of(d, w, "timers")
        ctx.check(f"{w}: showing the drawing started its clock, got {x.get('shown')} ({x.get('error')})", 1000 in (x.get("shown") or []))
        # the clock ticks once a second: a one-second interval started while it was shown and left once it is hidden is the
        # clock's (other parts of the page started while it was shown are not the drawing's)
        ctx.check(f"{w}: hidden, no one-second interval it started is left, got {x.get('left')}", 1000 not in (x.get("left") or []))


@test
def test_the_box_waited_on_is_outlined_and_the_wait_link_picks_it(ctx: Ctx):
    d = _got(ctx)
    for w in BOTH:
        x = _of(d, w, "wait")
        ctx.check(f"{w}: main waiting on the implementer, which is in a Bash call, outlines the implementer's box (code) alone, "
                  f"got {x.get('outlined')} ({x.get('error')})", x.get("outlined") == ["code"])
        ctx.check(f"{w}: the drawing's wait link says 3.6.0.0's words and names the implementer, got {x.get('link')!r} "
                  f"leaf {x.get('leaf')!r}", str(x.get("link")).startswith("waiting on: ") and "Bash pytest -q" in str(x.get("link"))
                  and x.get("leaf") == x.get("helper"))
        ctx.check(f"{w}: P8: a long tool line's link is whole on its own reserved row (no ellipsis, no clamp), and that row "
                  f"keeps its height when the link comes, got whole {x.get('whole')} row {x.get('row_before')} -> {x.get('row_after')}",
                  x.get("whole") is True and (x.get("row_before") or 0) > 0 and x.get("row_before") == x.get("row_after"))
        ctx.check(f"{w}: a press picks that box as a click does (selected, its card open), got {x.get('picked')}", x.get("picked") == ["code", True])


@test
def test_a_wait_on_a_tool_of_wide_words_is_whole_and_its_row_holds_after_its_first_draw(ctx: Ctx):
    """P8 batch 3 (red on dc72c152: narrate.ts cut a tool's words at 36 characters with '…'): a helper waits on a tool
    whose words are 90 wide letters; the link shows every word, and its row's height at the link's first draw equals its
    height five frames later (its room is the real words', taken when the wait appears)."""
    from tests.helpers.studio_run_parts import WIDE
    d = _got(ctx)
    for w in BOTH:
        x = _of(d, w, "wide")
        link, rows = str(x.get("link")), x.get("rows") or [None, None]
        ctx.check(f"{w}: the link says the tool's 90 wide letters whole, no '…', got {link!r} ({x.get('error')})",
                  WIDE in link and "…" not in link and x.get("whole") is True)
        ctx.check(f"{w}: the row's height at the link's first draw is its height five frames later, got {rows}",
                  bool(rows[0]) and rows[0] == rows[1])


@test
def test_a_waiting_row_says_how_long_it_has_waited(ctx: Ctx):
    d = _got(ctx)
    for w in BOTH:
        x = _of(d, w, "waited")
        reads = x.get("reads") or ["", ""]
        secs = [int(m.group(1)) if (m := re.search(r"· (\d+) s$", str(r))) else -1 for r in reads]
        ctx.check(f"{w}: an asking helper's row says it waits for him, got {reads} {x.get('kind')!r} ({x.get('error')})",
                  x.get("kind") == "you" and all(str(r).startswith("waiting for you · ") for r in reads))
        ctx.check(f"{w}: its seconds grow (the second read waits for it, up to 15 s), got {secs}", secs[0] >= 0 and secs[1] > secs[0])
        ctx.check(f"{w}: no box of the drawing moved while it ticked, got {x.get('moved')}", x.get("moved") == [])


@test
def test_the_wait_link_never_squeezes_more_below(ctx: Ctx):
    """P7: in Session's bottom slot the wait link never squeezes "↓ n more below"; that control keeps its rect and its one
    line when the link appears (a control never moves after the first draw). P8 (rewritten to the truth, the owner's rule
    a text is never cut): the link has its own reserved lines beside the control (the twins of the longest link this run
    can show), so the slot is at least 32 px tall from the first draw and keeps that height when the link comes; the
    link's words are whole. P9 batch 4 (rewritten to the truth, the coordinator's ruling of P8 batch 3: the room kept is
    a number of lines, and on macOS CI's long link took one more): the link's words are found BY MEASURING at the page's
    own font, the longest whose link fits the room kept from the first draw."""
    x = _of(_got(ctx), "session", "below")
    b = x.get("before") or {}
    f = x.get("fit") or {}
    a, fr = f.get("settled") or {}, (f.get("frames") or {})
    ctx.check(f"the drawer at its least width (360 px), got {x.get('drawer')} ({x.get('error')})", x.get("drawer") == 360)
    ctx.check(f"at 1280 x 800 '↓ n more below' is shown, its own width, one line, got {b} ({x.get('error')})",
              bool(b.get("more")) and b.get("lines") == 1 and b.get("natural") is True)
    sb, sa = (b.get("slot") or [0, 0])[1], (a.get("slot") or [0, 0])[1]
    ctx.check(f"a wait link whose words fit the room kept shows inside the slot, its words whole, the slot's height kept (at least "
              f"32 px) at its first frame and after, got {b.get('slot')} -> {fr} -> {a} (measured {x.get('measure')}, link {x.get('fit_link')!r})",
              a.get("wait") is True and a.get("inside") is True and a.get("whole") is True and sb >= 32 and sa == sb
              and (fr.get("first") or {}).get("slot") == sb and (fr.get("later") or {}).get("slot") == sb)
    ctx.check(f"'↓ n more below' keeps its rect, its own width and its one line beside it, got {b.get('more')} -> {a.get('more')} "
              f"lines {a.get('lines')} natural {a.get('natural')}",
              bool(b.get("more")) and a.get("more") == b.get("more") and a.get("lines") == 1 and a.get("natural") is True)


@test
def test_a_wait_link_longer_than_its_room_grows_the_slot_once_and_moves_nothing(ctx: Ctx):
    """P9 batch 4 (red on 12878d78, macOS CI: the slot 42 -> 56 px and '↓ n more below' 14 px up with it): a link of words
    one line longer than the room kept (measured at the page's font) grows the slot ONCE, in the frame the link first shows
    in, to exactly the link's own lines, the same five frames later; '↓ n more below' keeps its rect, its own width and its
    one line (the slot stands on the drawer's bottom: the control stands on the slot's bottom); the link lies inside the slot,
    its words whole."""
    x = _of(_got(ctx), "session", "below")
    b, m = x.get("before") or {}, x.get("measure") or {}
    g = x.get("grow") or {}
    a, fr = g.get("settled") or {}, (g.get("frames") or {})
    first, later = fr.get("first") or {}, fr.get("later") or {}
    room, need = m.get("room") or 0, (m.get("grow") or [None, 0])[1]
    ctx.check(f"the driver measured a link one line longer than the room kept, got {m} ({x.get('error')})",
              room > 0 and need > room)
    ctx.check(f"in the frame the link first shows in the slot is the link's own lines (at least 32 px), and so five frames later "
              f"and once settled, got {first} -> {later} -> {a.get('slot')} (link {x.get('grow_link')!r})",
              bool(first.get("link")) and first.get("link") == need and first.get("slot") == max(32, need)
              and later.get("slot") == first.get("slot") and (a.get("slot") or [0, 0])[1] == first.get("slot"))
    ctx.check(f"'↓ n more below' keeps its rect (at the link's first frame and after), its own width and its one line, got "
              f"{b.get('more')} -> {first.get('more')} -> {a.get('more')} lines {a.get('lines')} natural {a.get('natural')}",
              bool(b.get("more")) and first.get("more") == b.get("more") and a.get("more") == b.get("more")
              and a.get("lines") == 1 and a.get("natural") is True)
    ctx.check(f"the link lies inside the slot, its words whole, got {a}",
              a.get("wait") is True and a.get("inside") is True and a.get("whole") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
