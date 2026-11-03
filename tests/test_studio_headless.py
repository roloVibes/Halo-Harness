"""tests.test_studio_headless -- Halo 3.3.11.0 R2, a session with no terminal from Studio, in headless Chrome through
tests/helpers/studio_headless.py (skipped without one), over an in-process Studio whose launcher spawns a real
`halo --headless --session-for studio` child on the fake upstream (tests/helpers/headless_rig.py); no model call:
1. Session's Start view has New session (the default model first, Studio's folder); Start -> Session opens on the
   new session with the keyboard in the Prompt box, the header says "no terminal", the registry row is headless;
2. a turn typed in the Prompt gets the reply;
3. its ask (a Write) shows the card's buttons in the panel, Allow answers it and the tool runs;
4. End session (asks first) ends the child: its registry row goes and no child survives.
Run: python -m tests.test_studio_headless
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
    return driver_got(ctx, "tests.helpers.studio_headless", why="New session from Studio needs headless Chrome", cache=_RUN,
                      args=("headless",), timeout=400)


@test
def test_new_session_opens_on_it_with_the_prompt(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the default model first, Studio's folder, got {got.get('default_option')!r} {got.get('cwd_placeholder')!r}",
              "or:mock/headless" in str(got.get("default_option")) and bool(got.get("cwd_placeholder")))
    ctx.check(f"Session on the new session, got {got.get('sid')!r}", len(str(got.get("sid") or "")) == 32)
    ctx.check(f"the Prompt has the keyboard, got {got.get('focused')}", got.get("focused") == "focused")
    ctx.check(f"the header says no terminal, got {got.get('noterm')!r}", "no terminal" in str(got.get("noterm")))
    ctx.check(f"the registry row is headless, got {got.get('registered')}", got.get("registered") == "headless")


@test
def test_a_turn_and_an_ask_from_the_prompt(ctx: Ctx):
    got = _got(ctx)
    ctx.check("the reply shows", got.get("reply") == "reply")
    ctx.check(f"the ask's buttons, got {got.get('ask_buttons')}", got.get("ask_buttons") == ["Allow", "Allow for this session", "Deny"])
    ctx.check(f"answered: Allow, the tool ran, got {got.get('ask_done')} {got.get('made')} {got.get('file')}",
              got.get("ask_done") == "answered: Allow" and got.get("made") == "made" and got.get("file") is True)


@test
def test_end_session_ends_the_child(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"its registry row is gone, got {got.get('ended')}", got.get("ended") == "gone")
    ctx.check(f"no child survives, got {got.get('survivors')}", got.get("survivors") == [])
    ctx.check(f"no step failed, got {got.get('failed')}", not got.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
