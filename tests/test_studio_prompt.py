"""tests.test_studio_prompt -- Halo 3.3.11.0 R1, Session's Prompt panel in headless Chrome through
tests/helpers/studio_prompt.py (skipped without one), over a scripted fake session on its real control socket
behind the real Controller (tests/helpers/prompt_rig.py); no model call:
1. `?prompt=1` opens Session with the keyboard in the Prompt box;
2. a turn typed there runs once, shows "from Studio" and the reply, and its receipt's four marks reach replied;
3. `/eff` + Tab completes from the slash list; `/effort high` prints the session's lines and is no turn;
4. a permission ask shows the TUI card's buttons; Allow answers it through the socket and the turn ends;
5. a send while busy is refused with one line and keeps the text; Queue it holds it (no steer), and when the
   running turn ends it runs as the next turn, its marks reaching replied; every receipt ends replied, the
   refused one failed.
Run: python -m tests.test_studio_prompt
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
    return driver_got(ctx, "tests.helpers.studio_prompt", why="the Prompt panel needs headless Chrome", cache=_RUN,
                      args=("prompt",), timeout=300)


@test
def test_prompt_1_opens_the_panel_with_the_keyboard_in_it(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Session on the session, the box focused, got {got.get('opened')} {got.get('focused')}",
              got.get("opened") is True and got.get("focused") == "focused")


@test
def test_a_turn_from_studio_with_its_receipt(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the turn says from Studio, got {got.get('turn_via')} {got.get('turn_chip')}",
              got.get("turn_via") == "studio" and got.get("turn_chip") == "from Studio")
    ctx.check("the reply shows", got.get("reply") == "reply")
    ctx.check(f"the four marks reach replied, got {got.get('turn_marks')} {got.get('turn_lit')} {got.get('turn_title')!r}",
              got.get("turn_marks") == "replied" and got.get("turn_lit") == 4 and str(got.get("turn_title")).startswith("replied"))
    ctx.check(f"it ran once and the box cleared, got {got.get('users_after_turn')}",
              got.get("users_after_turn") == ["hello from the panel"] and got.get("cleared") is True)


@test
def test_the_slash_list_completes_and_a_slash_prints_its_lines(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"/eff lists effort, got {got.get('slash_list')}", "effort" in (got.get("slash_list") or []))
    ctx.check(f"Tab completes, got {got.get('completed')!r}", got.get("completed") == "/effort ")
    ctx.check(f"the output lines, got {got.get('slash_lines')!r}", "ran /effort high" in str(got.get("slash_lines")))
    ctx.check("a slash is no turn", got.get("slash_not_a_turn") is True)


@test
def test_an_ask_answered_from_the_panel(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the permission card's buttons, got {got.get('ask_buttons')}",
              got.get("ask_buttons") == ["Allow", "Allow for this session", "Deny"])
    ctx.check(f"answered: Allow, the session took allow, got {got.get('ask_done')} {got.get('ask_decision')}",
              got.get("ask_done") == "answered: Allow" and got.get("ask_decision") == "allow" and got.get("ask_turn_ended") is True)


@test
def test_busy_refused_then_queue_it_runs_after_the_turn(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"refused with one line, the text kept, got {got.get('busy_line')!r} {got.get('busy_kept_text')!r}",
              got.get("busy_session") is True and "queue this one" in str(got.get("busy_line"))
              and got.get("busy_kept_text") == "queued turn text")
    ctx.check("Queue it holds it, no steer", got.get("busy_gone") == "gone" and got.get("not_steered") is True and got.get("held") is True)
    ctx.check(f"it runs after the running turn, from Studio, replied, got {got.get('users')}",
              got.get("users") == ["hello from the panel", "please ask now", "please ask again", "queued turn text"]
              and got.get("queued_via") == "studio" and got.get("queued_marks") == "replied")
    states = [tuple(x) for x in got.get("receipt_states") or []]
    ctx.check(f"every receipt replied, the refused one failed, got {states}",
              states.count(("prompt", "failed")) == 1 and all(s == "replied" for k, s in states if (k, s) != ("prompt", "failed")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
