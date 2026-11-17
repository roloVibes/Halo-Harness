"""3.6.0.2 P5 batch 4: "a card never takes a key meant for the box" (cardkeys-design.md, the decisions' last part).

A card that asks him something used to take the keyboard the moment it showed, so a letter of the sentence he was
typing answered it (an `a` gave "Allow for this session" with a rule). Each test here walks the keys one at a time
with the product's REAL times (`@real_card_timing`: a card shown within 1.5 s of a key into the box waits, a card
answers no key in its first 0.6 s); the card clock (`tui.keys.card_clock_fn`) is stepped by hand so the times never
depend on how fast this machine is. Each test is red on 865ab155 unless it says "guard".
"""

from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from halo_harness import events as ev  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, real_card_timing, run_all  # noqa: E402

test, TESTS = new_registry()

WAIT_PERMISSION = "⏸ Permission waits while you type · Tab goes to it · Enter sends your text"
WAIT_PERMISSION_SHORT = "⏸ Permission waits · Tab goes to it"
HELD_PLACEHOLDER = "Tab: go to the waiting card · Enter: send a message"
HELD_PLACEHOLDER_SHORT = "Tab: go to the waiting card"
PERMISSION_PLACEHOLDER = "1-4 answers the request above"
TAG_WAITING = "permission needed · Tab goes to it"
TAG_KEYS = "permission needed: 1 yes · 2 session · 3 always · 4 no"


# ---- helpers ------------------------------------------------------------------------------------------------------
class _Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def step(self, seconds: float) -> None:
        self.t += seconds


def _app():
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    fake = FakeController(turns=[])
    return fake, BridgeApp(fake, cwd=str(REPO_DIR))


def _run(walk, size=(80, 24)) -> None:
    """Run `walk(fake, app, pilot, clock)` in a pilot, with the card clock stepped by hand."""
    from halo_harness.tui import keys as tui_keys
    clock = _Clock()
    before = getattr(tui_keys, "card_clock_fn", None)
    tui_keys.card_clock_fn = clock

    async def body():
        fake, app = _app()
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.2)
            app.set_focus(app.prompt_input)
            clock.step(5.0)
            await walk(fake, app, pilot, clock)

    try:
        asyncio.run(body())
    finally:
        tui_keys.card_clock_fn = before


_KEYS = {" ": "space", "!": "exclamation_mark", "/": "slash"}


async def _type(pilot, clock, text: str, gap: float = 0.1) -> None:
    for ch in text:
        await pilot.press(_KEYS.get(ch, ch))
        clock.step(gap)


def _perm(rid: str = "req-1"):
    return ev.Event("permission_request", {"id": rid, "name": "Bash", "input": {"command": "rm -rf build"},
                                           "reason": "not covered by a rule", "suggested_rule": "Bash(rm:*)"}, turn=1)


def _two_questions(rid: str = "q-2"):
    return ev.Event("question", {"id": rid, "name": "AskUserQuestion", "input": {"questions": [
        {"question": "first?", "options": ["a1", "a2"]}, {"question": "second?", "options": ["b1", "b2"]}]}}, turn=1)


async def _ask(app, pilot, event) -> None:
    from halo_harness.tui.dispatch import apply_event
    await apply_event(app, event)
    await pilot.pause(0.05)


def _nothing_answered(fake) -> bool:
    return (not fake.permission_replies and not fake.question_replies and not fake.plan_replies
            and not fake.approval_replies and not fake.added_rules)


def _line(app) -> "str | None":
    found = app.query("#card-wait-line")
    if not found:
        return None
    w = found.first()
    return w.text if w.display else ""


def _held(app, card) -> bool:
    return card is not None and getattr(app, "_held_card", None) is card


def _in(card, widget) -> bool:
    return widget is not None and (widget is card or card in widget.ancestors)


def _status(app) -> str:
    content = getattr(app.status_bar, "content", "")
    return getattr(content, "plain", str(content))


def _answers(fake) -> list:
    """(request id, action, rule) per permission reply: rule None = once, the suggested rule = for this session."""
    return [(r, d.get("action"), d.get("rule")) for r, d in fake.permission_replies]


def _rid(card) -> str:
    return getattr(card, "request_id", "") if card is not None else ""


# ---- N1, N12 (K1-K5, K12, K16, K20) --------------------------------------------------------------------------------
@test
@real_card_timing
def test_n1_an_ask_that_lands_while_he_types_never_takes_a_letter(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        bells = []
        app.bell = lambda: bells.append(1)
        await _type(pilot, clock, "please")
        await _ask(app, pilot, _perm("req-1"))
        await _type(pilot, clock, " add a test")
        await _type(pilot, clock, "ao1n3")
        await pilot.pause(0.1)
        ctx.check(f"every letter in the box, got {app.prompt_input.text!r}",
                  app.prompt_input.text == "please add a testao1n3")
        ctx.check(f"no reply and no rule, got {fake.permission_replies} {fake.added_rules}", _nothing_answered(fake))
        ctx.check("the base screen on top (no pager)", len(app.screen_stack) == 1)
        ctx.check(f"the box has the focus, got {type(app.focused).__name__}", app.focused is app.prompt_input)
        ctx.check("the card is still shown and waits", _rid(app.pending_card) == "req-1" and _held(app, app.pending_card))
        ctx.check(f"the wait line at 80 columns, got {_line(app)!r}", _line(app) == WAIT_PERMISSION)
        ctx.check(f"the held placeholder, got {app.prompt_input.placeholder!r}",
                  app.prompt_input.placeholder == HELD_PLACEHOLDER)
        ctx.check(f"the bell rang, got {len(bells)}", len(bells) >= 1)
        ctx.check(f"needs you 1, got {app.status_bar.needs_you_count}", app.status_bar.needs_you_count == 1)
        ctx.check(f"the permission tag says it waits, got {_status(app)!r}", TAG_WAITING in _status(app))
        await pilot.resize_terminal(60, 24)
        await pilot.pause(0.2)
        ctx.check(f"the short wait line at 60 columns, got {_line(app)!r}", _line(app) == WAIT_PERMISSION_SHORT)
    _run(walk)


@test
@real_card_timing
def test_n20_the_box_placeholder_never_asks_for_words_and_follows_the_card(ctx: Ctx):
    """Repair of batch 4 (checker finding 1, F-C, K20): with a permission card in front the box once read '1-4 answers
    the request above, or type why not' -- the box path that sentence described is gone, and typing `why not` on the
    card answers it (`y` allows). The placeholder names only the card's keys; a tip refresh never paints over a card's
    placeholder; a waiting card's placeholder picks its form from the width again on a resize, as its line does."""
    async def walk(fake, app, pilot, clock):
        await _ask(app, pilot, _perm("req-1"))
        card = app.pending_card
        ctx.check(f"the card took the focus from the idle box, got {type(app.focused).__name__}", _in(card, app.focused))
        ctx.check(f"the placeholder names the keys only, got {app.prompt_input.placeholder!r}",
                  app.prompt_input.placeholder == PERMISSION_PLACEHOLDER)
        app._refresh_tip_placeholder()  # a Studio note or the idle tip rotation refreshes the placeholder
        ctx.check(f"a tip refresh keeps it, got {app.prompt_input.placeholder!r}",
                  app.prompt_input.placeholder == PERMISSION_PLACEHOLDER)
        clock.step(1.0)
        await pilot.press("tab")
        await pilot.pause(0.1)
        ctx.check("Tab went back to the box", app.focused is app.prompt_input)
        ctx.check(f"the held placeholder, got {app.prompt_input.placeholder!r}",
                  app.prompt_input.placeholder == HELD_PLACEHOLDER)
        app._refresh_tip_placeholder()
        ctx.check(f"a tip refresh keeps the held one, got {app.prompt_input.placeholder!r}",
                  app.prompt_input.placeholder == HELD_PLACEHOLDER)
        await pilot.resize_terminal(48, 24)
        await pilot.pause(0.2)
        ctx.check(f"narrower: the short form, got {app.prompt_input.placeholder!r}",
                  app.prompt_input.placeholder == HELD_PLACEHOLDER_SHORT)
        await pilot.resize_terminal(80, 24)
        await pilot.pause(0.2)
        ctx.check(f"wide again: the long form, got {app.prompt_input.placeholder!r}",
                  app.prompt_input.placeholder == HELD_PLACEHOLDER)
        await pilot.press("tab")
        clock.step(0.1)
        await pilot.press("1")
        await pilot.pause(0.2)
        ctx.check(f"Tab, 1 allowed once, got {_answers(fake)}", _answers(fake) == [("req-1", "allow", None)])
        ctx.check(f"no card: the placeholder is no card's, got {app.prompt_input.placeholder!r}",
                  app.prompt_input.placeholder not in (PERMISSION_PLACEHOLDER, HELD_PLACEHOLDER, HELD_PLACEHOLDER_SHORT))
    _run(walk)


@test
@real_card_timing
def test_n12_a_waiting_card_answered_in_studio_closes_on_his_send(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        from halo_harness.tui.dispatch import apply_event
        await _type(pilot, clock, "go")
        await _ask(app, pilot, _perm("req-1"))
        await _ask(app, pilot, _perm("req-2"))
        await _type(pilot, clock, " on")
        a = app.pending_card
        ctx.check("A waits", _rid(a) == "req-1" and _held(app, a))
        await apply_event(app, ev.ask_answered("req-1", "permission", "Allow", "studio"))
        await pilot.pause(0.1)
        ctx.check(f"with text in the box, got {_line(app)!r}",
                  _line(app) == "✓ Answered in Studio: Allow · closes when you send")
        await pilot.press("ctrl+u")
        await pilot.pause(0.1)
        ctx.check(f"with the box empty, got {_line(app)!r}", _line(app) == "✓ Answered in Studio: Allow · Enter closes it")
        await _type(pilot, clock, "go on")
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"`go on` went as text, got {fake.submitted}", fake.submitted == ["go on"])
        ctx.check(f"nothing answered, got {fake.permission_replies}", _nothing_answered(fake))
        ctx.check(f"A closed, B came forward and waits, got {_rid(app.pending_card)}",
                  _rid(app.pending_card) == "req-2" and _held(app, app.pending_card))
        ctx.check("the box keeps the focus", app.focused is app.prompt_input)
    _run(walk)


# ---- N2 (J1 M1, J2 M2) ---------------------------------------------------------------------------------------------
@test
@real_card_timing
def test_n2_a_card_answered_elsewhere_closes_on_his_first_key_and_the_next_waits(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        from halo_harness.tui.dispatch import apply_event
        await _ask(app, pilot, _perm("req-1"))
        await _ask(app, pilot, _perm("req-2"))
        a = app.pending_card
        ctx.check(f"A takes the focus from an idle empty box, got {type(app.focused).__name__}", _in(a, app.focused))
        await apply_event(app, ev.ask_answered("req-1", "permission", "Allow", "studio"))
        await pilot.pause(0.1)
        clock.step(1.0)
        await _type(pilot, clock, "please add a test")
        await pilot.pause(0.1)
        ctx.check(f"nothing sent for A or B, got {fake.permission_replies} {fake.added_rules}", _nothing_answered(fake))
        ctx.check(f"the whole sentence in the box, got {app.prompt_input.text!r}",
                  app.prompt_input.text == "please add a test")
        ctx.check(f"B shown and waits, got {_rid(app.pending_card)}",
                  _rid(app.pending_card) == "req-2" and _held(app, app.pending_card))
        ctx.check("the box has the focus", app.focused is app.prompt_input)
    _run(walk)

    async def walk_lost(fake, app, pilot, clock):
        await _ask(app, pilot, _perm("req-1"))
        await _ask(app, pilot, _perm("req-2"))
        fake.lost_request_ids = {"req-1"}  # his key loses the claim: Studio's answer is on its way
        clock.step(1.0)
        await pilot.press("a")
        await pilot.pause(0.1)
        await _type(pilot, clock, "nd more")
        await pilot.pause(0.1)
        ctx.check(f"lost claim: nothing answered, got {fake.permission_replies}", _nothing_answered(fake))
        ctx.check(f"lost claim: B waits, got {_rid(app.pending_card)}",
                  _rid(app.pending_card) == "req-2" and _held(app, app.pending_card))
        ctx.check(f"lost claim: the next letters in the box, got {app.prompt_input.text!r}",
                  app.prompt_input.text == "nd more")
    _run(walk_lost)

    async def walk_draft(fake, app, pilot, clock):
        await _type(pilot, clock, "draft")
        await _ask(app, pilot, _perm("req-1"))
        await _ask(app, pilot, _perm("req-2"))
        clock.step(1.0)
        await pilot.press("tab")
        await pilot.press("1")
        await pilot.pause(0.2)
        ctx.check(f"with a draft: Tab, 1 answers A once, got {fake.permission_replies}",
                  _answers(fake) == [("req-1", "allow", None)])
        ctx.check(f"with a draft: B waits, got {_rid(app.pending_card)}",
                  _rid(app.pending_card) == "req-2" and _held(app, app.pending_card))
        ctx.check(f"the draft untouched, got {app.prompt_input.text!r}", app.prompt_input.text == "draft")
    _run(walk_draft)


# ---- N3 (K6, F-C, F5) ----------------------------------------------------------------------------------------------
@test
@real_card_timing
def test_n3_words_typed_before_a_card_are_never_its_answer(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        await _type(pilot, clock, "go on")
        await _ask(app, pilot, _perm("req-1"))
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"Enter sent the words as text, got {fake.submitted}", fake.submitted == ["go on"])
        ctx.check(f"the card still shown, no reply, got {fake.permission_replies}",
                  _rid(app.pending_card) == "req-1" and _nothing_answered(fake))
        await pilot.press("3")
        ctx.check(f"`3` is text, got {app.prompt_input.text!r}", app.prompt_input.text == "3")
        clock.step(1.0)
        await pilot.press("tab")
        ctx.check("Tab turns to the card", _in(app.pending_card, app.focused))
        await pilot.press("tab")
        ctx.check("Tab comes back to the box", app.focused is app.prompt_input)
        await _type(pilot, clock, "no")
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"`3no` sent as text, got {fake.submitted}", fake.submitted == ["go on", "3no"])
        ctx.check(f"still no reply, the card shown, got {fake.permission_replies}",
                  _rid(app.pending_card) == "req-1" and _nothing_answered(fake))
    _run(walk)


# ---- N4 (K5, K7, K8), the offer, two questions, the status tag ------------------------------------------------------
@test
@real_card_timing
def test_n4_tab_turns_to_the_card_and_back(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        await _type(pilot, clock, "keep this")
        await _ask(app, pilot, _perm("req-1"))
        clock.step(1.0)
        ctx.check(f"the tag while it waits, got {_status(app)!r}", TAG_WAITING in _status(app))
        await pilot.press("tab")
        await pilot.pause(0.05)
        ctx.check("Tab focuses the card", _in(app.pending_card, app.focused))
        ctx.check(f"the line goes, got {_line(app)!r}", _line(app) == "")
        ctx.check(f"the key list is back on the tag, got {_status(app)!r}", TAG_KEYS in _status(app))
        await pilot.press("1")
        await pilot.pause(0.2)
        ctx.check(f"`1` allows once, got {fake.permission_replies}",
                  _answers(fake) == [("req-1", "allow", None)])
        ctx.check(f"the box unchanged, got {app.prompt_input.text!r}", app.prompt_input.text == "keep this")
    _run(walk)

    async def walk_click(fake, app, pilot, clock):
        await _type(pilot, clock, "x")
        await _ask(app, pilot, _perm("req-1"))
        await pilot.click("#card-wait-line")
        await pilot.pause(0.1)
        ctx.check(f"a click on the line focuses the card, got {type(app.focused).__name__}",
                  _in(app.pending_card, app.focused))
    _run(walk_click)

    async def walk_offer(fake, app, pilot, clock):
        from halo_harness.tui import lane_offer_flow
        await lane_offer_flow.show(app, {"line": "model check: it fits", "offer": {"orchestrator": "big", "lineup": "x"}})
        await pilot.pause(0.05)
        offer = app.pending_card
        ctx.check("the offer takes the focus from an idle box", _in(offer, app.focused))
        clock.step(1.0)
        await pilot.press("tab")
        await pilot.pause(0.05)
        ctx.check("offer: Tab goes back to the box", app.focused is app.prompt_input)
        ctx.check("offer: Tab answered nothing", app.pending_card is offer and not offer.done)
        ctx.check(f"offer: its line, got {_line(app)!r}",
                  _line(app) == "⏸ Offer waits while you type · Tab goes to it · Enter sends your text")
        await pilot.press("tab")
        ctx.check("offer: Tab turns to it again", _in(offer, app.focused))
        await pilot.press("tab")
        ctx.check("offer: and back, still unanswered", app.focused is app.prompt_input and not offer.done)
    _run(walk_offer)

    async def walk_questions(fake, app, pilot, clock):
        await _ask(app, pilot, _two_questions("q-2"))
        await pilot.pause(0.1)
        card = app.pending_card
        ctx.check(f"the card lands on q1, got {app.focused!r}", app.focused is card._lists[0])
        clock.step(1.0)
        await pilot.press("tab")
        ctx.check(f"Tab reaches q2, got {app.focused!r}", app.focused is card._lists[1])
        await pilot.press("tab")
        ctx.check(f"Tab from the last question reaches the box, got {app.focused!r}", app.focused is app.prompt_input)
        ctx.check("nothing answered", _nothing_answered(fake))
        card._lists[0].highlighted = 0
        card._lists[0].action_select()
        await pilot.pause(0.1)
        app.set_focus(app.prompt_input)
        await pilot.pause(0.05)
        await pilot.press("tab")
        ctx.check(f"with q1 answered, Tab from the box lands on q2, got {app.focused!r}", app.focused is card._lists[1])
    _run(walk_questions)

    async def walk_tab_not_counted(fake, app, pilot, clock):
        await _ask(app, pilot, _perm("req-1"))
        await _ask(app, pilot, _perm("req-2"))
        a = app.pending_card
        clock.step(0.1)
        await pilot.press("backspace")  # in A's first moments: into the (empty) box, A waits
        await pilot.pause(0.05)
        ctx.check("A waits after a key in its first moments", _held(app, a) and app.focused is app.prompt_input)
        clock.step(2.0)
        await pilot.press("tab")
        await pilot.press("1")
        await pilot.pause(0.2)
        b = app.pending_card
        ctx.check(f"A answered once, got {fake.permission_replies}", len(fake.permission_replies) == 1)
        ctx.check(f"the Tab was not counted: B takes the focus, got {type(app.focused).__name__}",
                  _rid(b) == "req-2" and _in(b, app.focused))
    _run(walk_tab_not_counted)


@test
@real_card_timing
def test_n18_an_offer_waits_and_a_later_ask_is_counted_and_reached(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        from halo_harness.tui import lane_offer_flow
        await _type(pilot, clock, "next")
        await lane_offer_flow.show(app, {"line": "model check: it fits", "offer": {"orchestrator": "big", "lineup": "x"}})
        await pilot.pause(0.05)
        offer = app.pending_card
        ctx.check("the offer waits (text in the box)", _held(app, offer))
        await pilot.press("enter")
        await pilot.pause(0.1)
        await _ask(app, pilot, _perm("req-1"))
        ctx.check(f"the line names the waiting offer, got {_line(app)!r}",
                  _line(app) == "⏸ Offer waits while you type · Tab goes to it · Enter sends your text")
        ctx.check(f"two need him, got {app.status_bar.needs_you_count}", app.status_bar.needs_you_count == 2)
        clock.step(2.0)
        await pilot.press("tab")
        await pilot.press("n")
        await pilot.pause(0.2)
        ctx.check(f"the permission shows, got {type(app.pending_card).__name__}", _rid(app.pending_card) == "req-1")
        ctx.check("the prompt went", fake.submitted == ["next"])
    _run(walk)


# ---- N7 (guard: K15, K3 own act) ------------------------------------------------------------------------------------
@test
@real_card_timing
def test_n7_guard_a_card_from_an_idle_box_or_his_own_command_takes_the_focus(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        await _ask(app, pilot, _perm("req-1"))
        ctx.check("idle empty box: the ask takes the focus", _in(app.pending_card, app.focused))
    _run(walk)

    async def walk_effort(fake, app, pilot, clock):
        app.prompt_input.text = "/effort"
        await pilot.pause(0.05)
        app.completion_popup.hide()
        app._completion_items = []
        app.prompt_input.set_completion_open(False)
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"/effort's card takes the focus, got {type(app.focused).__name__}",
                  type(app.pending_card).__name__ == "EffortCard" and _in(app.pending_card, app.focused))
    _run(walk_effort)

    async def walk_undo_chord(fake, app, pilot, clock):
        fake.shadow_step_list = [{"id": "s1", "ts": 0, "label": "an edit", "files": ["a.txt"]}]
        await pilot.press("ctrl+x")
        await pilot.press("ctrl+u")
        await pilot.pause(0.2)
        ctx.check(f"the undo chord's rewind card takes the focus, got {type(app.pending_card).__name__} "
                  f"{type(app.focused).__name__}",
                  type(app.pending_card).__name__ == "RewindCard" and _in(app.pending_card, app.focused))
    _run(walk_undo_chord)

    async def walk_bang(fake, app, pilot, clock):
        from halo_harness.permissions import Decision
        fake.decide_inline_shell = lambda command: Decision("ask", "asks first")
        app.prompt_input.text = "!rm x"
        await pilot.pause(0.05)
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"`!rm x`'s card takes the focus, got {type(app.focused).__name__}",
                  type(app.pending_card).__name__ == "PermissionCard" and _in(app.pending_card, app.focused))
    _run(walk_bang)


# ---- N9 (K2) ---------------------------------------------------------------------------------------------------------
@test
@real_card_timing
def test_n9_an_ask_under_a_dialog_waits(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        from halo_harness.tui.dialogs.session_picker import SessionPicker
        row = {"id": "s1", "cwd": str(REPO_DIR), "mtime": 0, "summary": "hello", "title": "one",
               "model": "", "cost_usd": 0.0, "turns": 1}
        app.push_screen(SessionPicker([row]))
        await pilot.pause(0.2)
        await _ask(app, pilot, _perm("req-1"))
        clock.step(3.0)
        await pilot.press("escape")
        await pilot.pause(0.2)
        ctx.check(f"the box has the focus, got {type(app.focused).__name__}", app.focused is app.prompt_input)
        ctx.check(f"the line shows, got {_line(app)!r}", _line(app) == WAIT_PERMISSION)
        await pilot.press("1")
        await pilot.pause(0.1)
        ctx.check(f"`1` is text, got {app.prompt_input.text!r} {fake.permission_replies}",
                  app.prompt_input.text == "1" and _nothing_answered(fake))
    _run(walk)


# ---- N10 (K13, J1 M2) -----------------------------------------------------------------------------------------------
@test
@real_card_timing
def test_n10_ctrl_l_and_the_heal_keep_a_waiting_card_waiting(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        await _type(pilot, clock, "d")
        await _ask(app, pilot, _perm("req-1"))
        clock.step(2.0)
        await pilot.press("ctrl+l")
        await pilot.pause(0.1)
        ctx.check(f"Ctrl+L: the box keeps the focus, got {type(app.focused).__name__}", app.focused is app.prompt_input)
        app.set_focus(None)
        await pilot.pause(0.05)
        await pilot.press("x")
        await pilot.press("a")
        await pilot.pause(0.1)
        ctx.check(f"with nothing focused the first key lands too, got {app.prompt_input.text!r}",
                  app.prompt_input.text == "dxa")
        ctx.check(f"no reply, got {fake.permission_replies}", _nothing_answered(fake))
    _run(walk)

    async def walk_taken(fake, app, pilot, clock):
        await _ask(app, pilot, _perm("req-1"))
        clock.step(1.0)
        app.set_focus(None)
        await pilot.pause(0.05)
        await pilot.press("a")
        await pilot.pause(0.2)
        ctx.check(f"guard: a taken card heals to the card and `a` allows, got {fake.permission_replies}",
                  _answers(fake) == [("req-1", "allow", "Bash(rm:*)")])
    _run(walk_taken)


# ---- N11, N13, N18 (F2, K19, J2 M1) ---------------------------------------------------------------------------------
@test
@real_card_timing
def test_n11_an_ask_just_after_his_enter_waits(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        await _type(pilot, clock, "go on")
        await pilot.press("enter")
        await pilot.pause(0.1)
        clock.step(0.2)
        await _ask(app, pilot, _perm("req-1"))
        await _type(pilot, clock, "and also add")
        await pilot.pause(0.1)
        ctx.check(f"all in the box, got {app.prompt_input.text!r}", app.prompt_input.text == "and also add")
        ctx.check(f"no reply, got {fake.permission_replies}", _nothing_answered(fake))
        ctx.check("the card waits", _held(app, app.pending_card))
    _run(walk)

    async def walk_size_check(fake, app, pilot, clock):
        await _type(pilot, clock, "big prompt")
        await pilot.press("enter")
        await pilot.pause(0.1)
        clock.step(0.2)
        await _ask(app, pilot, ev.Event("approval_request", {"id": "pre-1", "position": "preflight",
                                                             "text": "too big", "is_error": False}, turn=1))
        ctx.check(f"a size check 0.2 s after the sent prompt waits, got {type(app.pending_card).__name__}",
                  type(app.pending_card).__name__ == "PreflightCard" and _held(app, app.pending_card))
        ctx.check(f"its line, got {_line(app)!r}",
                  _line(app) == "⏸ Size check waits while you type · Tab goes to it · Enter sends your text")
    _run(walk_size_check)


@test
@real_card_timing
def test_n13_a_key_and_a_card_in_one_step(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        from textual import events
        from halo_harness.tui.widgets.cards import PermissionCard
        card = PermissionCard(request_id="req-9", summary="Bash(rm x)", reason="", suggested_rule=None,
                              on_decide=lambda d: fake.permission_replies.append(("req-9", d)))
        await app.pending_dock.show_card(card)
        app.post_message(events.Key("a", "a"))
        app.set_pending_card(card)
        await pilot.pause(0.2)
        ctx.check(f"`a` in the box, got {app.prompt_input.text!r}", app.prompt_input.text == "a")
        ctx.check(f"no reply, got {fake.permission_replies}", fake.permission_replies == [])
        ctx.check(f"the box has the focus, got {type(app.focused).__name__}", app.focused is app.prompt_input)
    _run(walk)


@test
@real_card_timing
def test_n18_an_enter_and_a_card_in_one_step(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        from halo_harness.tui.widgets.cards import PermissionCard
        from halo_harness.tui.widgets.input import PromptInput
        app.prompt_input.text = "go on"
        await pilot.pause(0.05)
        card = PermissionCard(request_id="req-9", summary="Bash(rm x)", reason="", suggested_rule=None,
                              on_decide=lambda d: fake.permission_replies.append(("req-9", d)))
        await app.pending_dock.show_card(card)
        app.prompt_input.post_message(PromptInput.Submitted("go on", {}))
        app.set_pending_card(card)
        await pilot.pause(0.2)
        ctx.check(f"no reply, got {fake.permission_replies}", fake.permission_replies == [])
        ctx.check(f"`go on` went as text, got {fake.submitted}", fake.submitted == ["go on"])
        ctx.check("the card waits", _held(app, card))
    _run(walk)


# ---- N14 (K17, F-A) ---------------------------------------------------------------------------------------------------
@test
@real_card_timing
def test_n14_a_card_answers_no_key_in_its_first_moments(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        await _ask(app, pilot, _perm("req-1"))
        await _ask(app, pilot, _perm("req-2"))
        clock.step(1.0)
        await pilot.press("1")
        await pilot.pause(0.05)
        clock.step(0.05)
        await pilot.press("1")
        await pilot.pause(0.2)
        ctx.check(f"a double tap answers ONE card, got {fake.permission_replies}", len(fake.permission_replies) == 1)
        ctx.check(f"B waits, got {_rid(app.pending_card)}", _rid(app.pending_card) == "req-2"
                  and _held(app, app.pending_card))
        ctx.check(f"the second `1` is in the box, got {app.prompt_input.text!r}", app.prompt_input.text == "1")
    _run(walk)

    async def walk_early(fake, app, pilot, clock):
        await _ask(app, pilot, _perm("req-1"))
        clock.step(0.1)
        await pilot.press("2")
        await pilot.pause(0.1)
        ctx.check(f"0.1 s after: no answer, got {fake.permission_replies}", _nothing_answered(fake))
        ctx.check(f"0.1 s after: the key in the box, the card waits, got {app.prompt_input.text!r}",
                  app.prompt_input.text == "2" and _held(app, app.pending_card) and app.focused is app.prompt_input)
    _run(walk_early)

    async def walk_late(fake, app, pilot, clock):
        await _ask(app, pilot, _perm("req-1"))
        clock.step(0.7)
        await pilot.press("1")
        await pilot.pause(0.2)
        ctx.check(f"0.7 s after: it answers as before, got {fake.permission_replies}",
                  _answers(fake) == [("req-1", "allow", None)])
    _run(walk_late)

    async def walk_early_tab(fake, app, pilot, clock):
        await _ask(app, pilot, _perm("req-1"))
        clock.step(0.1)
        await pilot.press("tab")
        await pilot.pause(0.1)
        ctx.check("Tab in its first moments goes back to the box and stops there",
                  app.focused is app.prompt_input and _held(app, app.pending_card) and _nothing_answered(fake))
    _run(walk_early_tab)


# ---- N16, N17 (K1) ---------------------------------------------------------------------------------------------------
@test
@real_card_timing
def test_n16_n17_text_or_a_chip_in_the_box_holds_a_card_wherever_the_focus_is(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        from halo_harness.tui.widgets.cards import ToolCard
        tool = ToolCard(tool_use_id="t-1", header="Bash(ls)")
        await app.transcript.mount_widget(tool)
        app.prompt_input.text = "a draft"
        app.set_focus(tool)
        await pilot.pause(0.05)
        clock.step(3.0)
        await _ask(app, pilot, _perm("req-1"))
        ctx.check(f"held, the ToolCard keeps the focus, got {type(app.focused).__name__}",
                  _held(app, app.pending_card) and app.focused is tool)
        await pilot.click("#prompt-input")
        await pilot.pause(0.05)
        await pilot.press("end")
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"Enter sends the draft as text, got {fake.submitted}", fake.submitted == ["a draft"])
        ctx.check(f"no reply, got {fake.permission_replies}", _nothing_answered(fake))
    _run(walk)

    async def walk_chip(fake, app, pilot, clock):
        import tempfile
        folder = Path(tempfile.mkdtemp(prefix="cardkeys-"))
        image = folder / "shot.png"
        image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 32)
        try:
            app.prompt_input.add_image_chip(path=image, width=10, height=10)
            await pilot.pause(0.05)
            clock.step(2.0)
            await _ask(app, pilot, _perm("req-1"))
            ctx.check(f"only a chip in the box: the ask waits, got {app.prompt_input.text!r}",
                      _held(app, app.pending_card) and app.focused is app.prompt_input)
        finally:
            import shutil
            shutil.rmtree(folder, ignore_errors=True)
    _run(walk_chip)


# ---- N19 (J2 M5) -----------------------------------------------------------------------------------------------------
@test
@real_card_timing
def test_n19_his_own_command_never_buries_a_waiting_card(ctx: Ctx):
    async def walk(fake, app, pilot, clock):
        await _type(pilot, clock, "x")
        await _ask(app, pilot, _perm("req-1"))
        perm = app.pending_card
        ctx.check("the permission waits", _held(app, perm))
        await pilot.press("ctrl+u")
        app.prompt_input.text = "/effort"
        await pilot.pause(0.05)
        app.completion_popup.hide()
        app._completion_items = []
        app.prompt_input.set_completion_open(False)
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"/effort shows its card, got {type(app.pending_card).__name__}",
                  type(app.pending_card).__name__ == "EffortCard")
        clock.step(1.0)
        await pilot.press("enter")  # the effort card (no level on this model) closes
        await pilot.pause(0.3)
        ctx.check(f"the permission is shown again, got {type(app.pending_card).__name__}", app.pending_card is perm)
        ctx.check("and waits", _held(app, perm) and app.focused is app.prompt_input)
        ctx.check(f"needs you 1, got {app.status_bar.needs_you_count}", app.status_bar.needs_you_count == 1)
        clock.step(1.0)
        await pilot.press("tab")
        await pilot.press("1")
        await pilot.pause(0.2)
        ctx.check(f"Tab then 1 allows, got {fake.permission_replies}",
                  _answers(fake) == [("req-1", "allow", None)])
    _run(walk)


# ---- batch 5: N5, N6, N8 (K9, K10, K11, J2 M3, J3 M3, J3 M4) -------------------------------------------------------
SET_ASIDE = "Your text is set aside; it comes back after this answer."
SET_ASIDE_SHORT = "Text set aside until this answer."
KEPT = "Kept, not sent: that ask was already answered. Edit the text to send it."
KEPT_SHORT = "Kept, not sent: the ask was answered."
DRAFT_PASTE = "draft line 1\ndraft line 2\ndraft line 3\ndraft line 4"
REASON_PASTE = "reason line 1\nreason line 2\nreason line 3\nreason line 4"


def _box_state(box) -> tuple:
    return box.text, dict(box.pasted), [dict(i) for i in box.images]


async def _paste(app, pilot, text: str) -> None:
    """A bracketed paste from the terminal: it reaches the app as one Paste event."""
    from textual import events
    app.post_message(events.Paste(text))
    await pilot.pause(0.05)


def _image(folder: Path) -> Path:
    image = folder / "shot.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 32)
    return image


@test
@real_card_timing
def test_n5_a_borrow_sets_his_draft_aside_and_gives_it_back(ctx: Ctx):
    """K9, J2 M3, J3 M4: every borrow sets the box's text, pastes and chips aside; the reason's paste is numbered after
    the draft's; the draft comes back exactly, as the LAST step of the borrow's Enter (or Esc). Red on 865ab155 and
    on batch 4's commit: the borrow emptied the box and the draft was lost."""
    import shutil
    import tempfile
    folder = Path(tempfile.mkdtemp(prefix="cardkeys-"))

    async def walk(fake, app, pilot, clock):
        box = app.prompt_input
        await _type(pilot, clock, "draft ")
        await _paste(app, pilot, DRAFT_PASTE)
        box.add_image_chip(path=_image(folder), width=10, height=10)
        await pilot.pause(0.05)
        before = _box_state(box)
        ctx.check(f"the draft holds a paste and a chip, got {box.text!r}",
                  "[Pasted text #1 +4 lines]" in box.text and "[Image #1 10x10]" in box.text)
        await _ask(app, pilot, _perm("req-1"))
        await _ask(app, pilot, _perm("req-2"))
        ctx.check("the ask waits", _held(app, app.pending_card))
        clock.step(1.0)
        await pilot.press("tab")
        await pilot.press("4")
        await pilot.pause(0.1)
        ctx.check(f"the box is empty for the reason, got {box.text!r}", box.text == "")
        ctx.check(f"the set-aside line above the box, got {_line(app)!r}", _line(app) == SET_ASIDE)
        ctx.check(f"not in the status bar, got {_status(app)!r}", "set aside" not in _status(app))
        await _type(pilot, clock, "no ")
        await _paste(app, pilot, REASON_PASTE)
        ctx.check(f"the reason's paste is numbered after the draft's, got {box.text!r}",
                  box.text == "no [Pasted text #2 +4 lines]")
        await pilot.press("enter")
        await pilot.pause(0.2)
        replies = fake.permission_replies
        ctx.check(f"one deny that carries the reason only, got {replies}",
                  len(replies) == 1 and replies[0][0] == "req-1" and replies[0][1].get("action") == "deny"
                  and replies[0][1].get("message") == "no " + REASON_PASTE)
        ctx.check(f"the draft is back exactly, got {_box_state(box)!r}", _box_state(box) == before)
        ctx.check(f"the ask behind comes forward and waits, got {_rid(app.pending_card)}",
                  _rid(app.pending_card) == "req-2" and _held(app, app.pending_card))
        ctx.check(f"the line is the wait line again, got {_line(app)!r}", _line(app) == WAIT_PERMISSION)
        ctx.check("nothing went as a prompt", fake.submitted == [])
    try:
        _run(walk)
    finally:
        shutil.rmtree(folder, ignore_errors=True)

    async def walk_taken_then_esc(fake, app, pilot, clock):
        box = app.prompt_input
        await _ask(app, pilot, _perm("req-1"))
        ctx.check("taken from the idle box", _in(app.pending_card, app.focused))
        clock.step(1.0)
        await pilot.press("tab")
        await _type(pilot, clock, "mine")
        await pilot.press("tab")
        await pilot.press("4")
        await pilot.pause(0.1)
        ctx.check(f"a taken card left and come back to: set aside too, got {box.text!r} {_line(app)!r}",
                  box.text == "" and _line(app) == SET_ASIDE)
        await pilot.resize_terminal(60, 24)
        await pilot.pause(0.2)
        ctx.check(f"the short set-aside line at 60 columns, got {_line(app)!r}", _line(app) == SET_ASIDE_SHORT)
        await pilot.press("escape")
        await pilot.pause(0.2)
        ctx.check(f"Esc: a deny with no reason, got {fake.permission_replies}",
                  _answers(fake) == [("req-1", "deny", None)])
        ctx.check(f"Esc: the draft is back, got {box.text!r}", box.text == "mine")
        ctx.check(f"the line is gone, got {_line(app)!r}", _line(app) == "")
    _run(walk_taken_then_esc)


@test
@real_card_timing
def test_n5_n8_answered_elsewhere_during_a_borrow_keeps_draft_and_words(ctx: Ctx):
    """K10, K11, F3, J1 M6: Studio answers the ask while he types a reason; his Enter sends nothing, the box holds the
    draft, a new line, then his words (each paste keeps its own number), and the kept guard holds ALL of it: Enter
    again sends nothing, rings the bell and shows the kept line above the box (whole at 80, short at 60). An edit
    makes it his again and both pastes go out right. Red on 865ab155 and on batch 4's commit (the draft was lost)."""
    async def walk(fake, app, pilot, clock):
        from halo_harness.tui.dispatch import apply_event
        box = app.prompt_input
        bells = []
        app.bell = lambda: bells.append(1)
        await _type(pilot, clock, "draft ")
        await _paste(app, pilot, DRAFT_PASTE)
        await _ask(app, pilot, _perm("req-1"))
        clock.step(1.0)
        await pilot.press("tab")
        await pilot.press("4")
        await pilot.pause(0.1)
        await _type(pilot, clock, "why ")
        await _paste(app, pilot, REASON_PASTE)
        await apply_event(app, ev.ask_answered("req-1", "permission", "Allow", "studio"))
        await pilot.pause(0.1)
        await pilot.press("enter")
        await pilot.pause(0.2)
        whole = "draft [Pasted text #1 +4 lines]\nwhy [Pasted text #2 +4 lines]"
        ctx.check(f"nothing sent, got {fake.permission_replies} {fake.submitted}",
                  _nothing_answered(fake) and fake.submitted == [])
        ctx.check(f"the box: draft, a new line, his words, got {box.text!r}", box.text == whole)
        ctx.check(f"the kept guard holds the whole text, got {app._kept_text!r}", app._kept_text == whole)
        ctx.check(f"the kept line above the box, got {_line(app)!r}", _line(app) == KEPT)
        ctx.check(f"not in the status bar, got {_status(app)!r}", "Kept" not in _status(app))
        rang = len(bells)
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"Enter again: nothing sent, got {fake.submitted}", fake.submitted == [] and _nothing_answered(fake))
        ctx.check(f"Enter again: the bell, got {len(bells) - rang}", len(bells) > rang)
        ctx.check(f"Enter again: the kept line, got {_line(app)!r}", _line(app) == KEPT)
        await pilot.resize_terminal(60, 24)
        await pilot.pause(0.2)
        ctx.check(f"the short kept line at 60 columns, got {_line(app)!r}", _line(app) == KEPT_SHORT)
        await pilot.press("end")
        await pilot.press("exclamation_mark")
        await pilot.press("enter")
        await pilot.pause(0.3)
        sent = fake.submitted[-1] if fake.submitted else ""
        ctx.check(f"edited, Enter sends both pastes right, got {sent!r}",
                  len(fake.submitted) == 1 and DRAFT_PASTE in sent and REASON_PASTE in sent)
        ctx.check(f"the kept line is gone, got {_line(app)!r}", _line(app) == "")
    _run(walk)


@test
@real_card_timing
def test_n5_k10_an_empty_reason_that_lost_its_claim_keeps_the_draft(ctx: Ctx):
    """K10 (one of the two when the other is empty), F3: a draft is set aside, Tab, `4`, Studio answers the ask, he
    presses Enter with NO reason: nothing is sent, the box holds the draft, and the kept guard holds it, so a second
    Enter (a double tap) sends nothing, rings the bell and shows the kept line. Red on 0804c304 (the guard tested his
    empty words, so the second Enter sent the unfinished draft to the model)."""
    async def walk(fake, app, pilot, clock):
        from halo_harness.tui.dispatch import apply_event
        box = app.prompt_input
        bells = []
        app.bell = lambda: bells.append(1)
        await _type(pilot, clock, "half a draft")
        await _ask(app, pilot, _perm("req-1"))
        clock.step(1.0)
        await pilot.press("tab")
        await pilot.press("4")
        await pilot.pause(0.1)
        ctx.check(f"the draft is set aside, got {box.text!r}", box.text == "" and _line(app) == SET_ASIDE)
        await apply_event(app, ev.ask_answered("req-1", "permission", "Allow", "studio"))
        await pilot.pause(0.1)
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"nothing sent, got {fake.permission_replies} {fake.submitted}",
                  _nothing_answered(fake) and fake.submitted == [])
        ctx.check(f"the box holds the draft, got {box.text!r}", box.text == "half a draft")
        ctx.check(f"the kept guard holds it, got {app._kept_text!r}", app._kept_text == "half a draft")
        ctx.check(f"the kept line above the box, got {_line(app)!r}", _line(app) == KEPT)
        rang = len(bells)
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"a second Enter sends nothing, got {fake.submitted}", fake.submitted == [] and _nothing_answered(fake))
        ctx.check(f"a second Enter rings the bell, got {len(bells) - rang}", len(bells) > rang)
    _run(walk)


@test
@real_card_timing
def test_n6_a_two_question_card_keeps_the_draft_aside_until_he_goes_back(ctx: Ctx):
    """K8, K9, J3 M3: a held two-question card and a draft: Tab, Other, `x`, Enter answers q1; the draft stays aside
    while q2 has the focus; Tab in the box during the borrow does nothing; Tab from q2 to the box brings it back; Enter
    sends it as text and picks no option. Red on 865ab155 and on batch 4's commit (the draft was lost)."""
    async def walk(fake, app, pilot, clock):
        box = app.prompt_input
        await _type(pilot, clock, "my draft")
        await _ask(app, pilot, _two_questions("q-2"))
        card = app.pending_card
        ctx.check("the question card waits", _held(app, card))
        clock.step(1.0)
        await pilot.press("tab")
        await pilot.pause(0.05)
        q1 = app.focused
        ctx.check(f"Tab lands on q1, got {getattr(q1, 'id', None)}", getattr(q1, "id", None) == "q-opt-0")
        q1.highlighted = 2  # "… Other (type your own answer)"
        await pilot.press("enter")
        await pilot.pause(0.1)
        ctx.check(f"Other borrows the box: empty, got {box.text!r}", box.text == "" and app.focused is box)
        ctx.check(f"the set-aside line, got {_line(app)!r}", _line(app) == SET_ASIDE)
        await pilot.press("tab")
        await pilot.pause(0.05)
        ctx.check("Tab in the box during the borrow does nothing",
                  app.focused is box and app._borrowing_card is card and box.text == "")
        await _type(pilot, clock, "x")
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"q2 has the focus, got {getattr(app.focused, 'id', None)}",
                  getattr(app.focused, "id", None) == "q-opt-1")
        ctx.check(f"the draft is still aside, got {box.text!r} {_line(app)!r}",
                  box.text == "" and _line(app) == SET_ASIDE)
        ctx.check(f"no answer sent yet, got {fake.question_replies}", fake.question_replies == [])
        await pilot.press("tab")
        await pilot.pause(0.1)
        ctx.check(f"Tab to the box: the draft is back, got {box.text!r}", app.focused is box and box.text == "my draft")
        ctx.check(f"the card waits, its line shows, got {_line(app)!r}",
                  _held(app, card) and _line(app) == "⏸ Question waits while you type · Tab goes to it · Enter sends your text")
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"Enter sends the draft as text, got {fake.submitted}", fake.submitted == ["my draft"])
        ctx.check(f"no option picked, got {fake.question_replies}", fake.question_replies == [])
    _run(walk)


@test
@real_card_timing
def test_n6_the_draft_comes_back_when_q2_closes_the_card(ctx: Ctx):
    """K9: a held two-question card and a draft: Tab, Other, `x`, Enter answers q1 (the draft stays aside); Enter on
    q2's own list answers it and closes the card: the draft is back in the box exactly, the set-aside line is gone,
    the draft is not sent. Shown red by taking out only the bring-back on close (see notes-batch05.md)."""
    async def walk(fake, app, pilot, clock):
        box = app.prompt_input
        await _type(pilot, clock, "my draft")
        await _ask(app, pilot, _two_questions("q-2"))
        card = app.pending_card
        clock.step(1.0)
        await pilot.press("tab")
        await pilot.pause(0.05)
        app.focused.highlighted = 2  # "… Other (type your own answer)"
        await pilot.press("enter")
        await pilot.pause(0.1)
        await _type(pilot, clock, "x")
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"q2 has the focus, the draft aside, got {getattr(app.focused, 'id', None)} {box.text!r}",
                  getattr(app.focused, "id", None) == "q-opt-1" and box.text == "" and _line(app) == SET_ASIDE)
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"q2's key closed the card, got {fake.question_replies}",
                  len(fake.question_replies) == 1 and app.pending_card is not card)
        ctx.check(f"the draft is back exactly, got {box.text!r}", box.text == "my draft")
        ctx.check(f"the set-aside line is gone, got {_line(app)!r}", _line(app) == "")
        ctx.check(f"the draft is not sent, got {fake.submitted}", fake.submitted == [])
    _run(walk)


# ---- batch 5: N15 (K18, F4, J3 M5) -----------------------------------------------------------------------------------
@test
@real_card_timing
def test_n15_a_paste_on_a_card_goes_into_the_box(ctx: Ctx):
    """K18, F4: a bracketed paste that reaches a card that has the focus never answers it: the text goes into the box
    and the card waits. Red on 865ab155 and on batch 4's commit (the paste was dropped on the card)."""
    async def walk(fake, app, pilot, clock):
        await _ask(app, pilot, _perm("req-1"))
        ctx.check("taken from the idle box", _in(app.pending_card, app.focused))
        clock.step(1.0)
        await _paste(app, pilot, "yes and also this")
        await pilot.pause(0.1)
        ctx.check(f"the paste is in the box, got {app.prompt_input.text!r}", app.prompt_input.text == "yes and also this")
        ctx.check(f"no reply, got {fake.permission_replies}", _nothing_answered(fake))
        ctx.check("the card waits, the box has the focus", _held(app, app.pending_card) and app.focused is app.prompt_input)
        ctx.check(f"its line, got {_line(app)!r}", _line(app) == WAIT_PERMISSION)
    _run(walk)

    async def walk_fresh(fake, app, pilot, clock):
        await _ask(app, pilot, _perm("req-1"))
        clock.step(0.1)
        await _paste(app, pilot, "early")
        ctx.check(f"in its first moments too, got {app.prompt_input.text!r}",
                  app.prompt_input.text == "early" and _nothing_answered(fake) and _held(app, app.pending_card))
    _run(walk_fresh)


@test
@real_card_timing
def test_n15_text_that_lands_through_ctrl_v_counts_as_a_key_into_the_box(ctx: Ctx):
    """J3 M5 (a): a Ctrl+V's text lands later (the clipboard is read off the UI thread); it counts as a key into the box
    WHEN it lands. A card his own command showed waits when a dragged image lands after it (only the chips his command
    kept do not count). Red on 865ab155 and on batch 4's commit (the landing was not counted)."""
    import shutil
    import tempfile
    folder = Path(tempfile.mkdtemp(prefix="cardkeys-"))

    async def walk(fake, app, pilot, clock):
        box = app.prompt_input
        clock.step(0.3)
        box.paste_text("from the clipboard")
        ctx.check(f"the landing is stamped, got {box.last_key_at} vs {clock.t}", box.last_key_at == clock.t)
        clock.step(0.2)
        await _ask(app, pilot, _perm("req-1"))
        ctx.check("an ask 0.2 s after it waits", _held(app, app.pending_card))

    async def walk_own_act(fake, app, pilot, clock):
        from halo_harness.tui.widgets.cards import PermissionCard
        card = PermissionCard(request_id="req-9", summary="Bash(rm x)", reason="", suggested_rule=None,
                              on_decide=lambda d: fake.permission_replies.append(("req-9", d)))
        await app.pending_dock.show_card(card)
        app.set_pending_card(card, own_act=True)
        clock.step(0.05)
        app.prompt_input.paste_text(str(_image(folder)))  # a dragged image path, through Ctrl+V
        await pilot.pause(0.2)
        ctx.check(f"a chip landed after his command: the card waits, got {app.prompt_input.text!r}",
                  "[Image #1" in app.prompt_input.text and _held(app, card) and app.focused is app.prompt_input)
    try:
        _run(walk)
        _run(walk_own_act)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


@test
@real_card_timing
def test_p7_the_kept_line_and_a_waiting_cards_line_both_show(ctx: Ctx):
    """cardkeys-decisions.md "After the build": the slot above the box shows the kept line AND a waiting card's line
    (two lines, the kept line above), so a waiting card is never unsaid, not even for the kept line's 10 s: whole at 80
    columns, short at 60; when the kept line's time ends only the wait line stays; the box keeps its place and size.
    Red on 4a150bf9 (the kept line took the slot alone)."""
    async def walk(fake, app, pilot, clock):
        from halo_harness.tui.dispatch import apply_event
        box = app.prompt_input
        await _type(pilot, clock, "draft ")
        await _ask(app, pilot, _perm("req-1"))
        clock.step(1.0)
        await pilot.press("tab")
        await pilot.press("4")
        await pilot.pause(0.1)
        await _type(pilot, clock, "why")
        await apply_event(app, ev.ask_answered("req-1", "permission", "Allow", "studio"))
        await pilot.pause(0.1)
        await pilot.press("enter")
        await pilot.pause(0.2)
        ctx.check(f"the kept line alone first, got {_line(app)!r}", _line(app) == KEPT)
        at = (box.region.y, box.region.height)
        line = app.card_wait_line
        gap = box.region.y - line.region.bottom  # the box's own top edge (its border) under the slot
        clock.step(5.0)
        await _ask(app, pilot, _perm("req-2"))
        await pilot.pause(0.2)
        ctx.check(f"a card waits while the kept line shows: both lines, the kept line above, got {_line(app)!r}",
                  _line(app) == f"{KEPT}\n{WAIT_PERMISSION}")
        ctx.check(f"two rows, right above the box, got {line.region} box {box.region}",
                  line.region.height == 2 and box.region.y - line.region.bottom == gap <= 1)
        ctx.check(f"the box keeps its size and place, got {at} -> {(box.region.y, box.region.height)}",
                  (box.region.y, box.region.height) == at)
        await pilot.resize_terminal(60, 24)
        await pilot.pause(0.2)
        ctx.check(f"at 60 columns both short forms, got {_line(app)!r}", _line(app) == f"{KEPT_SHORT}\n{WAIT_PERMISSION_SHORT}")
        await pilot.resize_terminal(80, 24)
        await pilot.pause(0.2)
        at = (box.region.y, box.region.height)
        line.clear_kept()  # what the kept line's 10 s timer calls
        await pilot.pause(0.2)
        ctx.check(f"the kept line's time ended: the wait line alone, got {_line(app)!r}", _line(app) == WAIT_PERMISSION)
        ctx.check(f"one row, right above the box, which has not moved, got {line.region} box {box.region} (was {at})",
                  line.region.height == 1 and box.region.y - line.region.bottom == gap and (box.region.y, box.region.height) == at)
    _run(walk)


_CHILD_TIMES = "from halo_harness.tui.keys import card_times; print(card_times())"


def _child_times(env: dict) -> str:
    import subprocess
    r = subprocess.run([sys.executable, "-c", _CHILD_TIMES], cwd=str(REPO_DIR), env=env, capture_output=True,
                       text=True, timeout=120)
    return (r.stdout or r.stderr).strip()


@test
def test_p7_a_halo_a_test_starts_runs_with_the_real_card_times(ctx: Ctx):
    """cardkeys-decisions.md "After the build": the runner's switch for the two card times reaches this process only; a
    halo process an unmarked test starts runs with the REAL times unless the test asks for the switch. Red on 4a150bf9
    (the switch was an environment variable every child inherited)."""
    import os
    from halo_harness.tui.keys import CARD_FRESH_S, CARD_WAIT_S, card_times
    ctx.check(f"this (unmarked) test's own process has the times off, got {card_times()}", card_times() == (0.0, 0.0))
    env = {**os.environ, "PYTHONPATH": str(REPO_DIR)}
    real = _child_times(env)
    ctx.check(f"a child started with the test's environment has the real times, got {real!r}",
              real == str((CARD_WAIT_S, CARD_FRESH_S)))
    asked = _child_times({**env, "HALO_TEST_CARD_TIMES_OFF": "1"})
    ctx.check(f"a child whose test asks for the switch has them off, got {asked!r}", asked == "(0.0, 0.0)")


BUILDER_USE_ROW = ("New sessions run on review-flow. This session keeps running on starter (the default), as it started. "
                   "Start a new session to run on review-flow. In the terminal: quit, then run halo; /clear keeps "
                   "starter (the default).")


def _builder_card_event():
    """The Builder card of the real-use check's step session-map (scripts/realcheck/steps_map.py): its first row and
    seven rows, the use row last (crew/session_tool.card)."""
    from halo_harness.crew.session_tool import card
    said = ["Make the workflow review: 1 coder, 2 reviewer", "review, step 1: code (coder) · always",
            "review, step 2: review (reviewer) · always", "Make a new map review-flow (main, then the boxes below)",
            "Add box review (workflow review)", "Add line main -> review (When: always)", BUILDER_USE_ROW]
    rows = [{"summary": s, "widen": False, "ticked": True} for s in said]
    first = ("Your review workflow: the workflow review (coder, then reviewer), run from a box on the new map "
             "review-flow.")
    return ev.Event("question", {"id": "q-builder", "name": "Builder", "input": card(rows, first)}, turn=1)


@test
def test_a_builder_card_of_seven_rows_is_whole_in_a_tall_terminal(ctx: Ctx):
    """P8 batch 2 repair (the real-use check's session-map step, red on bf2ed077): the dock was capped at 12 lines
    whatever the terminal's height, so at 200x50 the Builder card's row 7 (the use row, with S13 and the terminal's
    line) was scrolled out of sight under row 6. The dock now takes up to half the screen (never under 12 lines): the
    whole card shows at 200x50, and an 80x24 terminal keeps its 12-line dock with the box below it."""
    for size, whole in (((200, 50), True), ((80, 24), False)):
        async def walk(fake, app, pilot, clock, size=size, whole=whole):
            await _ask(app, pilot, _builder_card_event())
            await pilot.pause(0.2)
            dock = app.pending_dock
            ctx.check(f"{size}: the Builder card is in the dock, got {type(dock.card).__name__}",
                      type(dock.card).__name__ == "QuestionCard")
            if whole:
                ctx.check(f"{size}: nothing of the card is scrolled out of the dock (max_scroll_y "
                          f"{dock.max_scroll_y}, dock {dock.outer_size.height} lines)", dock.max_scroll_y == 0)
            ctx.check(f"{size}: the dock leaves the box and the status line on screen ({dock.outer_size.height} of "
                      f"{size[1]} lines)", dock.outer_size.height <= max(12, size[1] // 2))
            box = app.prompt_input.region
            ctx.check(f"{size}: the box is on screen below the dock, got {box}",
                      box.height > 0 and box.y + box.height <= size[1] and box.y >= dock.region.y + dock.region.height)
        _run(walk, size=size)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
