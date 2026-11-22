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
3.6.0.2 P6 (tests/helpers/studio_prompt_one.py, tests/helpers/studio_prompt_pick.py): the answer to a send never
wipes what was typed after Enter, a steer's one row, `Interrupted.`, an ask answered elsewhere; the header names the
session in words on two lines, `Change session`, `Now typing into ...`, the pick following /clear, an ended session's
text kept read-only with Copy.
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
    ctx.check(f"3.6.0.11: a long prompt, Up: the text stays and the caret is at 0, got {p.get('up_once')}",
              p.get("up_once") == [79, 0, 0])
    ctx.check(f"3.6.0.11: Up again: the older prompt, got {p.get('up_twice')!r}", p.get("up_twice") == "plain send")
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


@test
def test_a_bang_line_runs_in_the_session_with_no_turn(ctx: Ctx):
    """3.6.0.12 BS (the owner: "can I run commands in the terminal like Claude code using the "!" ? If not that is a must
    have"): Studio's box sent `!echo ...` to the model as a prompt. Now it runs in the session as in the terminal."""
    b = _one(ctx).get("bang") or {}
    ctx.check(f"the answer line: `ran`, then the output, got {b.get('lines')}",
              (b.get("lines") or [None])[0] == "ran" and "BANG-ONE" in (b.get("lines") or [])[1:])
    ctx.check(f"your line once, got {b.get('line_rows')}", b.get("line_rows") == 1)
    ctx.check(f"one tool row on the session's stream (Bash), got {b.get('tool_rows')} {b.get('rows_once')} {b.get('tool_text')!r}",
              b.get("tool_rows") == 1 and b.get("rows_once") == 1 and "Bash" in str(b.get("tool_text")))
    ctx.check(f"the Feed shows it once, got {b.get('feed_rows')}", b.get("feed_rows") == 1)
    ctx.check(f"no model turn, the box emptied, got {b.get('turns')} {b.get('box')!r}", b.get("turns") == 0 and b.get("box") == "")
    ctx.check(f"an asking ! says so, word for word, got {b.get('asked')!r}", b.get("asked") == "asks first: answer below")
    ctx.check(f"the panel's own ask card; its Allow runs the command, got {b.get('ask_buttons')} {b.get('ask_ran')} "
              f"{b.get('ask_done')!r} {b.get('ask_turns')}", "Allow" in (b.get("ask_buttons") or []) and b.get("ask_ran") is True
              and b.get("ask_done") == "Answered in Studio: Allow" and b.get("ask_turns") == 0)


# -- 3.6.0.2 P6 P27-P29, P31, P32: tests/helpers/studio_prompt_pick.py, which session the box types into -------------
def _pick(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_prompt_pick", why="the Prompt panel needs headless Chrome", cache=_RUN,
                      key="pick", args=("pick",), timeout=300)


def _held(ctx: Ctx, what: str, a: dict, b: dict) -> None:
    ctx.check(f"{what}: the header's height and the box's top unchanged, got {a and (a.get('head'), a.get('top'))} -> "
              f"{b and (b.get('head'), b.get('top'))}", bool(a) and bool(b) and a.get("head") == b.get("head") and a.get("top") == b.get("top"))


@test
def test_header_names_the_session_in_two_lines(ctx: Ctx):
    """P27: `<folder> · <title> · started <HH:MM> · in a terminal`, never an id; a one-line and a two-line title give
    the header the same height and are never clipped."""
    got = _pick(ctx)
    ctx.check(f"the driver ran to its end, failed: {got.get('failed')!r}", not got.get("failed"))
    h = got.get("header") or {}
    first, one, two = h.get("first") or {}, h.get("one") or {}, h.get("two") or {}
    ctx.check(f"the folder, then the words, never the id, got {first.get('text')!r}",
              str(first.get("text", "")).startswith(f"{h.get('folder')} · ") and " · started " in first.get("text", "")
              and first.get("text", "").endswith(" · in a terminal") and h.get("sid", "")[:8] not in first.get("text", ""))
    ctx.check(f"a title: the words name it, got {one.get('text')!r}", " · Fix the parser · started " in str(one.get("text")))
    ctx.check(f"the long title takes two lines, got {h.get('two_lines')}", h.get("two_lines") == 2)
    for name, g in (("one line", one), ("two lines", two)):
        ctx.check(f"{name}: not clipped (scrollWidth {g.get('sw')} == clientWidth {g.get('cw')}, scrollHeight {g.get('sh')} "
                  f"<= clientHeight {g.get('ch')})", g.get("sw") == g.get("cw") and (g.get("sh") or 0) <= (g.get("ch") or 0))
    _held(ctx, "one line -> two lines", one, two)
    _held(ctx, "no title -> one line", first, one)


@test
def test_change_session_list_and_moved_line(ctx: Ctx):
    """P28, P29: the list in the header's words, newest first, the current marked; choosing shows no line; `/studio`
    shows `Now typing into ...` in the header's place for 6 s and nothing moves; a long title gives the short line."""
    got = _pick(ctx)
    ch = got.get("change") or {}
    listed = ch.get("listed") or []
    ctx.check(f"two sessions, newest first, the current one marked, got {listed}",
              [x.get("sid") for x in listed] == [ch.get("sid2"), (got.get("header") or {}).get("sid")]
              and [x.get("on") for x in listed] == [False, True])
    ctx.check(f"each in the header's words, got {[x.get('words') for x in listed]}",
              len(listed) == 2 and listed[1].get("words") == ch.get("head_words")
              and str(listed[0].get("words")).startswith(f"{ch.get('other')} · Second session · started "))
    ctx.check(f"choosing one sets the pick, shows no line and closes the list, got {ch.get('chosen')} "
              f"{ch.get('line_after_list')!r} {ch.get('list_closed')}",
              ch.get("chosen") is True and not ch.get("line_after_list") and ch.get("list_closed") is True)
    folder = (got.get("header") or {}).get("folder")
    ctx.check(f"`/studio` moved the pick with the line, got {ch.get('focus_status')} {ch.get('moved')!r}",
              ch.get("focus_status") == 200 and ch.get("moved") == f"Now typing into {folder} · Fix the parser."
              and ch.get("pick_after_focus") == (got.get("header") or {}).get("sid"))
    ctx.check(f"the line shows about 6 s, got {ch.get('shown_s')} s", ch.get("gone") == "gone" and 4.5 <= (ch.get("shown_s") or 0) <= 8.0)
    _held(ctx, "before -> during the line", ch.get("before") or {}, ch.get("during") or {})
    _held(ctx, "during -> after the line", ch.get("during") or {}, ch.get("after") or {})
    lg = ch.get("long") or {}
    ctx.check(f"a title past two lines: the short line, got {lg.get('line')!r}", lg.get("line") == f"Now typing into {folder}.")
    # both sessions carry the same header words here (the same long title, a folder of the same name, the same start;
    # 3.6.0.3 S), so before (the other one's header) has the same height too in any font; a title past two lines makes
    # the header taller than two lines (never cut, the decisions' J1 M3), the same for both
    _held(ctx, "long title: before -> during", lg.get("before") or {}, lg.get("during") or {})
    _held(ctx, "long title: during -> after", lg.get("during") or {}, lg.get("after") or {})


@test
def test_clear_in_the_terminal_never_shows_ended(ctx: Ctx):
    """P16, P31: /clear in the terminal moves the pick to the row that follows the old one; the header names it, the
    `Same terminal, new conversation` line shows, the box keeps its text and stays editable; never the ended line."""
    got = _pick(ctx)
    p = got.get("pick") or {}
    other = (got.get("change") or {}).get("other")
    ctx.check(f"the pick followed to the new row, got {p.get('followed')}", p.get("followed") is True)
    ctx.check(f"the line, got {p.get('line')!r}", p.get("line") == f"Same terminal, new conversation: {other}.")
    ctx.check(f"then the header names the new row, got {p.get('head_after')!r}",
              str(p.get("head_after") or "").startswith(f"{other} · no messages yet · started "))
    ctx.check(f"the box's text the same and editable, got {p.get('box_before')!r} -> {p.get('box_after')!r} {p.get('editable')}",
              p.get("box_before") == "a draft he keeps" == p.get("box_after") and p.get("editable") is True)
    ctx.check(f"the ended line never showed, got {p.get('ended_seen')}", p.get("ended_seen") == 0)
    f = p.get("from_ended") or {}
    ctx.check(f"from the ended state a later follower takes the pick, editable, the same text, got {f}",
              f.get("followed") is True and f.get("line") == f"Same terminal, new conversation: {other}."
              and f.get("box") == "a draft he keeps" and f.get("editable") is True and f.get("ended_gone") is True)


@test
def test_one_refused_connect_keeps_the_box_editable(ctx: Ctx):
    """3.6.0.4 S4: one refused connect to the picked session (a full accept queue on a loaded machine) pruned its row
    for good: the box went read-only, "ended", while the terminal went on. Now the row stays and the box with it."""
    r = _pick(ctx).get("refused") or {}
    ctx.check(f"the refused connects were used by Studio's read, got {r}", r.get("picked") is True and r.get("refusals_used") is True)
    ctx.check(f"the session's row is still in the registry, got {r.get('listed')}", r.get("listed") is True)
    ctx.check(f"the ended line never showed, got {r.get('ended_seen')} {r.get('ended_gone')}",
              r.get("ended_seen") == 0 and r.get("ended_gone") is True)
    ctx.check(f"the box keeps its text and stays editable, got {r.get('box_before')!r} -> {r.get('box')!r} {r.get('editable')}",
              r.get("box") == r.get("box_before") == "a draft he keeps" and r.get("editable") is True)


@test
def test_ended_session_keeps_text_read_only(ctx: Ctx):
    """P32: the picked session ends, nothing follows: read-only with its text, the line, Copy -> `Copied.` for 2 s with
    the text on the clipboard; picking another session makes the box editable with the same text."""
    got = _pick(ctx)
    p = got.get("pick") or {}
    e = p.get("ended") or {}
    ctx.check(f"the line, got {e.get('shown')!r}", e.get("shown") == "This session has ended. What you typed is still here.")
    ctx.check(f"the box read-only with its text, Send off, got {e.get('box')!r} {e.get('read_only')} {e.get('send_off')}",
              e.get("box") == "a draft he keeps" and e.get("read_only") is True and e.get("send_off") is True)
    ctx.check(f"the header still names the ended session, got {e.get('head')!r}", " · started " in str(e.get("head") or ""))
    ctx.check(f"Copy -> Copied. with the text on the clipboard, back to Copy, got {e.get('copy_word')!r} "
              f"{e.get('copied_word')!r} {e.get('clipboard')!r} {e.get('back_to_copy')!r} {e.get('copied_s')}",
              e.get("copy_word") == "Copy" and e.get("copied_word") == "Copied." and e.get("clipboard") == "a draft he keeps"
              and e.get("back_to_copy") == "Copy" and 1.0 <= (e.get("copied_s") or 0) <= 4.0)
    o = p.get("other_pick") or {}
    ctx.check(f"another session picked: editable with the same text, got {o}",
              o.get("picked") is True and o.get("box") == "a draft he keeps" and o.get("editable") is True and o.get("ended_gone") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
