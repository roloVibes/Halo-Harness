"""tests.test_studio_prompt -- Halo 3.3.11.0 R1, Session's Prompt panel in headless Chrome through
tests/helpers/studio_prompt.py (skipped without one), over a scripted fake session on its real control socket
behind the real Controller (tests/helpers/prompt_rig.py); no model call:
1. `?prompt=1` opens Session with the keyboard in the Prompt box;
2. a turn typed there runs once and shows the reply (3.6.0.2 P24: no "from Studio" word), and its receipt's four
   marks reach replied;
3. `/eff` + Tab completes from the slash list; `/effort high` prints the session's lines and is no turn;
   (fx jb4) opening the Prompt again while the box holds the keyboard leaves it there;
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
def test_opening_the_prompt_again_leaves_the_keyboard_in_the_box(ctx: Ctx):
    """fx jb4: openPrompt while the box holds the keyboard (the new session's late open, Alt+Enter) never moves it to
    the panel: what is typed right after lands in the box (a lost Enter left a Studio prompt unsent)."""
    got = _got(ctx)
    ctx.check(f"the box never lost the keyboard and kept the text, got {got.get('lost_focus')} {got.get('kept_text')!r} "
              f"{got.get('still_in_box')}", got.get("lost_focus") == 0 and got.get("kept_text") == "kept" and got.get("still_in_box") is True)
    ctx.check(f"the box emptied for the next step, got {got.get('emptied')}", got.get("emptied") == "empty")


@test
def test_the_box_empties_where_ctrl_a_is_no_select_all(ctx: Ctx):
    """fx jb9: the helper empties the box the same way on every system (macOS CI: Ctrl+A is no select-all there, the
    box kept its text and six tests failed); the keyboard stays in the box."""
    got = _got(ctx)
    ctx.check(f"the box emptied with the select-all chord doing nothing, got {got.get('any_keyboard_emptied')} "
              f"{got.get('any_keyboard_left')!r}", got.get("any_keyboard_emptied") == "empty")
    ctx.check(f"the keyboard stayed in the box, got {got.get('any_keyboard_in_box')}", got.get("any_keyboard_in_box") is True)


@test
def test_a_turn_from_studio_with_its_receipt(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the turn came from Studio (its via) and no word marks the box it was typed in (3.6.0.2 P24), got "
              f"{got.get('turn_via')} {got.get('turn_chip')!r}", got.get("turn_via") == "studio" and got.get("turn_chip") is None)
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
    ctx.check(f"Answered in Studio: Allow (3.6.0.2 P23), the session took allow, got {got.get('ask_done')} {got.get('ask_decision')}",
              got.get("ask_done") == "Answered in Studio: Allow" and got.get("ask_decision") == "allow" and got.get("ask_turn_ended") is True)
    ctx.check(f"one line, also once the session's own ask_answered arrived, got {got.get('ask_heard')} {got.get('ask_done_lines')}",
              got.get("ask_heard") == "heard" and got.get("ask_done_lines") == ["Answered in Studio: Allow"])


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


# -- 3.6.0.2 P6 ("one prompt"): tests/helpers/studio_prompt_one.py, the answer to a send held on the server ------------
def _one(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_prompt_one", why="the Prompt panel needs headless Chrome", cache=_RUN,
                      key="one", args=("one",), timeout=300)


@test
def test_answer_never_wipes_what_he_typed_after_enter(ctx: Ctx):
    """P72 (a gate): the box changes only when the answer to a send arrives, and then only by the text sent, while no
    edit touched it since Enter."""
    p = _one(ctx).get("p72") or {}
    ctx.check(f"a plain send with nothing typed after: the box is empty after the answer, got {p.get('plain_after')}",
              p.get("plain_after") == "empty")
    want = {"typed_after": ("first part and more", "and more"),  # a prompt, more typed while in flight
            "recall_up": ("repeat me", "repeat me"),  # (a) Up recalls the line just sent: left
            "replaced_longer": ("base text extended", "base text extended"),  # (b) a longer text beginning with it: left
            "backspace_edge": ("see more", "see more"),  # a Backspace took the sent text's last letter: left
            "slash_typed_after": ("/effort low next", "next"),  # a slash line, more typed while in flight
            "failed": ("/effort none more", "/effort none more"),  # a refused send: nothing changes
            "ran_false": ("/effort mid x", "/effort mid x")}  # a slash that ran nothing: nothing changes
    for name, (during, after) in want.items():
        got = p.get(name) or {}
        ctx.check(f"{name}: nothing taken out while in flight ({during!r}), then {after!r}, got {got}",
                  got.get("during") == during and got.get("after") == after)
    ctx.check(f"the slash ran and its 'nothing was run' line shows, got {p.get('slash_ran')} {p.get('ran_false_line')}",
              p.get("slash_ran") == "ran" and p.get("ran_false_line") == "shown")
    s = _one(ctx).get("steer") or {}
    ctx.check(f"Steer on the busy line, more typed while in flight: only that stays, got {s.get('during')!r} {s.get('after')!r}",
              s.get("during") == "steer this after" and s.get("after") == "after")
    ctx.check(f"a refused Steer leaves the box, got {s.get('refused_box')!r}", s.get("refused_box") == "steer two")
    ctx.check(f"a failed Enter recorded more than the busy line holds: Steer sends 'alpha' and the box keeps 'alpha beta', "
              f"got {s.get('drift_during')!r} {s.get('drift_steered')} {s.get('drift_after')!r}",
              s.get("drift_during") == "alpha beta" and s.get("drift_steered") == ["alpha"] and s.get("drift_after") == "alpha beta")


@test
def test_no_from_studio_word(ctx: Ctx):
    p = _one(ctx).get("p72") or {}
    ctx.check(f"no row of Studio's feed says 'from Studio' (P24), got {p.get('from_studio_word')}", p.get("from_studio_word") is False)


@test
def test_steer_row_once_at_once(ctx: Ctx):
    s = _one(ctx).get("steer") or {}
    ctx.check(f"the session took the steers, the refused one once it was sent again, got {s.get('steered')} {s.get('steered_end')}",
              s.get("steered") == ["steer this"] and s.get("steered_end") == ["steer this", "steer two"])
    ctx.check(f"one row with the muted steering line (the event and the answer both landed), got {s.get('rows')}",
              s.get("rows") == ["↳ steering the running turn…"])
    ctx.check(f"a refused steer draws none, got {s.get('refused_rows')}", s.get("refused_rows") == [])
    ctx.check(f"sent again, one row, got {s.get('again_rows')}", s.get("again_rows") == ["↳ steering the running turn…"])


@test
def test_bare_model_opens_studio_picker(ctx: Ctx):
    m = _one(ctx).get("model") or {}
    ctx.check(f"Enter on a bare /model opens Studio's model picker, `/model ` in the box, nothing sent, got {m}",
              m.get("picker") == "open" and m.get("box") == "/model " and m.get("new_outs") == 0 and m.get("slash_requests") == 0)


@test
def test_any_interrupted_turn_shows_interrupted(ctx: Ctx):
    i = _one(ctx).get("interrupted") or {}
    ctx.check(f"`Interrupted.` under each interrupted turn, whoever stopped it; none for a plain end, got {i}",
              i.get("first") == ["Interrupted."] and i.get("second") == ["Interrupted.", "Interrupted."] and i.get("after_end_turn") == 2)


@test
def test_ask_answered_in_terminal_closes_studio_card(ctx: Ctx):
    e = _one(ctx).get("elsewhere") or {}
    ctx.check(f"answered in the terminal: one line in place of the buttons, got {e.get('terminal')}",
              e.get("terminal") == {"lines": ["Answered in the terminal: Allow"], "buttons": 0})
    ctx.check(f"answered from a phone: 'Answered remotely', got {e.get('remote')}",
              e.get("remote") == {"lines": ["Answered remotely: Allow"], "buttons": 0})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
