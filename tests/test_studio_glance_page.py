"""tests.test_studio_glance_page -- the glance and the alert in headless Chrome (Halo 3.4.1.0 R4 "Time"), through
tests/helpers/studio_glance.py (skipped without Chrome), every pack off; no model call:

1. Session's "..." -> Open the glance says where the glance is: this machine's address, and for a phone the SSH door's
   steps or, with no SSH server here, plainly that the page is this-machine-only; DOES / COSTS / WRITES before Open;
2. Settings -> Studio -> Alerts: None by default, nothing asked or shown on load; a click on the browser's asks this
   browser ONCE and saves `studio.alerts: browser`;
3. a card that starts waiting is ONE notification naming what waits and the session -- the ask's frames again and the
   queue read twice more do not make a second -- and a click on it opens Session's Attention on that row;
4. the glance at 390 px: no rail, no horizontal scroll, the sentence, the ask with its three answers as large buttons
   saying what each does, the spend honestly ("unknown", "no cap set"), the elapsed time, the last three events; Allow
   once answers the card (the owner-proof path) and then nothing waits;
5. Studio stops: the page says it is stale; Studio comes back: the page is live again by itself; 3.4.1.1 (63): Studio
   restarted for real (a new token): the page says so and where to open it again, and stops asking.
Run: python -m tests.test_studio_glance_page
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
    return driver_got(ctx, "tests.helpers.studio_glance", why="the glance needs headless Chrome", cache=_RUN, timeout=420)


@test
def test_open_the_glance_says_where_it_is(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"this machine's address: {got.get('door_here')!r}", str(got.get("door_here", "")).startswith("http://127.0.0.1:")
              and str(got.get("door_here")).endswith("/?mode=glance"))
    line = str(got.get("door_line", ""))
    ctx.check(f"a phone: the SSH door's line, or this-machine-only said plainly: {got.get('door_ssh')} {line!r}",
              (got.get("door_ssh") == "off" and "this-machine-only" in line) or (got.get("door_ssh") == "on" and "SSH server" in line))
    ctx.check(f"what Open does, costs and writes: {got.get('door_cost')}", (got.get("door_cost") or [""])[-1] == "nothing")


@test
def test_the_alert_setting_asks_once_on_a_click(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"nothing asked, nothing shown on load: {got.get('asked_on_load')} {got.get('notes_on_load')}",
              got.get("asked_on_load") == 0 and got.get("notes_on_load") == 0)
    ctx.check(f"None, then each channel: {got.get('choices')}", got.get("choices") == ["none", "browser"])
    ctx.check(f"the click asks once and saves the choice: {got.get('asked_after_click')} {got.get('saved')}",
              got.get("asked_after_click") == 1 and got.get("saved") == "browser")
    ctx.check(f"it says what this browser will do: {got.get('state_line')!r}", "allows it" in str(got.get("state_line")))
    ctx.check(f"3.4.1.1 (64): one control of studio.alerts, its line there before a choice: {got.get('state_on_load')!r} "
              f"{got.get('alerts_rows')!r}", got.get("state_on_load") == "ask" and got.get("alerts_rows") == 0)


@test
def test_one_notification_per_new_ask_and_its_click_opens_it(ctx: Ctx):
    got = _got(ctx)
    note = got.get("note") or {}
    ctx.check(f"what waits and on which session: {note}", note.get("title") == "Waiting on you: Permission: Bash"
              and "you@studio" in str(note.get("body")) and str(note.get("tag", "")).endswith(":perm_1"))
    ctx.check(f"the frames again and two more reads: still one, got {got.get('notes_after')}",
              got.get("notes_after") == 1 and got.get("reads_grew") is True)
    ctx.check(f"a click opens Session's Attention on that row: {got.get('opened')}", got.get("opened") == "permission"
              and got.get("note_closed") is True)


@test
def test_the_glance_at_phone_width_answers_an_ask(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"no rail, no panels: {got.get('rail')}", got.get("rail") is False)
    w = got.get("scroll") or [1, 0, 1, 0]
    ctx.check(f"390 px, no horizontal scroll: {w}", w[0] == w[1] == 390 and w[2] <= w[3])
    ctx.check(f"the sentence says what waits: {got.get('narration')!r}", "waiting on you" in str(got.get("narration")))
    keys = got.get("keys") or []
    ctx.check(f"three answers, each saying what it does: {keys}", [k[0] for k in keys] == ["a", "r", "s"]
              and keys[0][1] == "allow once" and keys[0][2] == "runs this one call")
    ctx.check(f"large buttons: {got.get('key_h')}", (got.get("key_h") or 0) >= 48)
    spend = str(got.get("spend"))  # the fake session's row reports no price (unknown) or, once its status lands, $0.000
    ctx.check(f"the spend, honestly, against no cap: {spend!r}", spend in ("unknown · no cap set", "$0.000 · no cap set"))
    ctx.check(f"the elapsed time: {got.get('elapsed')!r}", got.get("elapsed") in ("under a minute", "1 min", "2 min"))
    ctx.check(f"the last three events, newest first: {got.get('events')}", got.get("events") ==
              ["tool: ran Bash", "text: The discount applies before tax.", "tool: ran Read"])
    ctx.check(f"Allow once answered the card: {got.get('decision')!r}", got.get("decision") == "allow")
    ctx.check(f"then nothing waits: {got.get('after')!r}", got.get("after") == "Nothing waits on you.")


@test
def test_the_glance_says_when_it_is_stale_and_comes_back(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Studio stopped: stale, said: {got.get('stale')!r}", str(got.get("stale", "")).startswith("stale: last heard"))
    ctx.check(f"Studio back: live by itself: {got.get('back')!r}", str(got.get("back", "")).startswith("live"))
    # 3.4.1.1 (63): a REAL restart (a new per-launch token): said, and the page stops asking (no key is kept or reused)
    ctx.check(f"restarted with a new key: said, with where to open it again: {got.get('rekeyed')!r}",
              got.get("rekeyed") == "Studio was restarted and has a new key: open the glance again from Studio "
                                    "(Session's ... menu -> Open the glance)")
    ctx.check(f"and it stops asking: the feed off, no request in two probe periods: {got.get('feed_after')!r} "
              f"{got.get('asked_after')!r}", got.get("feed_after") == "off" and got.get("asked_after") == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio glance page"))
