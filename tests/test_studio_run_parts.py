"""tests.test_studio_run_parts -- Halo 3.6.0.2, P4 batch 13 (the coordinator's ruling: nothing a person could see of a run in
3.6.0.1 is lost): what the 3.6.0.0 lit Map showed of a run is back on BOTH run drawings, Session's Live drawer and
Agents -> 4 · Live, from one set of parts (routes/crew/map/runParts.tsx), in headless Chrome (driver
tests/helpers/studio_run_parts.py; skipped without Chrome; the Linux VM and CI only).

1. the tool clock: a helper in a tool call says the tool and its seconds, which grow while no box moves;
2. the talk pulse: main talking to the implementer lights the line main -> code, and no other;
3. "+{n} under it": main's box draws three rows and counts the rest; a press opens 4 · Live's Feed on main's `under:` page;
4. J / K step the selection from box to box in drawing order; J typed into the card's Steer field selects nothing;
5. no interval the drawing started is left once it is hidden (Session: another section; Live: 3 · Map).
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
        ctx.check(f"{w}: its seconds grow between two reads 1.2 s apart, got {secs}", secs[0] >= 0 and secs[1] > secs[0])
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
        # clock's (other parts of the page started while it was shown, e.g. the Attention chip's 5 s, are not the drawing's)
        ctx.check(f"{w}: hidden, no one-second interval it started is left, got {x.get('left')}", 1000 not in (x.get("left") or []))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
