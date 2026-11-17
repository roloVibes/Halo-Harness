"""tests.test_prompt_one_terminal -- 3.6.0.2 package P5 batch 1 ("one prompt", the terminal side; the design
promptF-design.md F1a): what a session's terminal does with what Studio sends over the control socket.

P1  a socket prompt or steer adds no grey note (the `❯` row is the one copy); a held turn starts with no note;
    Studio's interrupt draws no `(remote) interrupt` (other clients keep it).
P2  a socket `user_message` / `steer_queued` brings the transcript to the bottom, as Enter does.
P4  an ask answered over the socket closes the terminal's card for it (and one waiting behind it); a card that
    borrows the box ends the borrow and leaves what he typed there, unsent (the HARD GATE).
P5  that close is ONE muted line, the card's marker: `Answered in Studio: <label>` / `Answered remotely: <label>`,
    the label from `events.ask_label`, the one table; the answer's via reaches the handle.
P6  one `ask_answered` event per answer, from either side, only when the claim won.
P73 two answers that cross: one wins, the other gets False; one decision, one line, one event.
P7  plain-text Enter on a card that no longer waits sends the text as an ordinary prompt, no toast.
P17 `/studio` in a private session says so and opens nothing.
Batch 2 (F1b): P3 no frame, log line, receipt or line names a user or host (`origin` is `{via}`); P8 a socket slash
runs the terminal's own table (taken within 1 s or not at all); P9 its answer holds its notes and toasts; P10 still
running after 3.5 s says so; P11 a screen, a box command or `/exit`; P12 the `❯ /<line>` row for both boxes; P16 the
row after `/clear` follows the old id and is written first; P70 the row's `first_words`.
The socket half runs over the remote rig (a real Controller + handle + socket over a scripted FakeSession); the
terminal half drives the real TUI (Textual run_test) over the FakeController. No model is called.
Run: python -m tests.test_prompt_one_terminal
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import queue
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from halo_harness import events as ev  # noqa: E402
from tests.helpers.remote_rig import Rig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
STUDIO = {"via": "studio"}


# ---- helpers ------------------------------------------------------------------------------------------------------
def _drain(rig) -> list:
    out = []
    while True:
        try:
            item = rig.controller.events.get_nowait()
        except queue.Empty:
            return out
        if item is not None:
            out.append(item)


def _wait(fn, timeout: float = 8.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.02)
    return None


def _turn(rig, c, text: str, n: int, waiters: str = "", key: str = "") -> bool:
    """Start turn `n` with `text`; when `waiters` is given, wait until it parks on that ask."""
    c.call("submit", text=text)
    if waiters:
        return bool(_wait(lambda: rig.session.busy and key in getattr(rig.session, waiters)))
    return bool(_wait(lambda: rig.session.turn_count == n and not rig.session.busy))


def _app():
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    fake = FakeController(turns=[])
    return fake, BridgeApp(fake, cwd=str(REPO_DIR))


class _Sink:
    """A controller `events` that records what the TUI puts on it and gives the app's drain nothing."""

    def __init__(self) -> None:
        self.put_events: list = []

    def put(self, item) -> None:
        self.put_events.append(item)

    def get_nowait(self):
        raise queue.Empty


def _perm(rid: str = "req-1"):
    return ev.Event("permission_request", {"id": rid, "name": "Bash", "input": {"command": "rm -rf build"},
                                           "reason": "not covered by a rule", "suggested_rule": "Bash(rm:*)"}, turn=1)


def _question(rid: str = "q-1"):
    return ev.Event("question", {"id": rid, "name": "AskUserQuestion",
                                 "input": {"question": "which one?", "options": ["red", "blue"]}}, turn=1)


def _plan(rid: str = "plan-1"):
    return ev.Event("plan_review", {"id": rid, "plan": "1. do the thing", "path": ""}, turn=1)


def _approval(rid: str = "appr-1"):
    return ev.Event("approval_request", {"id": rid, "position": "reviewer", "text": "looks fine?", "is_error": False},
                    turn=1)


def _answered_notes(app) -> list:
    from halo_harness.tui.widgets.transcript import SystemNote
    return [w.raw_text for w in app.transcript.query(SystemNote) if w.raw_text.startswith("Answered ")]


def _markers(app) -> dict:
    """request key -> the card's marker widget, while the cards wait."""
    from halo_harness.tui.app import _ask_key
    cards = ([app.pending_card] if app.pending_card is not None else []) + list(app._pending_queue)
    return {_ask_key(c): app._pending_markers.get(id(c)) for c in cards}


# ---- P1 -----------------------------------------------------------------------------------------------------------
@test
def test_socket_prompt_draws_one_row_no_grey_note(ctx: Ctx):
    with Rig() as rig:
        c = rig.client()
        c.call("submit", text="hello from the panel", origin=STUDIO)
        ctx.check("a Studio turn ran", _wait(lambda: rig.session.turn_count == 1 and not rig.session.busy))
        ctx.check("a phone turn ran", _turn(rig, c, "plain phone turn", 2))
        got = _drain(rig)
        notes = [e.data["text"] for e in got if e.kind == "system_note"]
        rows = [e.data["text"] for e in got if e.kind == "user_message"]
        ctx.check(f"no grey note for a socket prompt, got {notes}",
                  not [t for t in notes if "prompt:" in t or "hello from the panel" in t or "plain phone turn" in t])
        ctx.check(f"each prompt is one row, got {rows}",
                  rows.count("hello from the panel") == 1 and rows.count("plain phone turn") == 1)
        ctx.check("the parked turn", _turn(rig, c, "please ask first", 3, "_permission_waiters", "perm_1"))
        r = c.call("submit", text="steer it now", origin=STUDIO)
        ctx.check(f"a steer, got {r}", r["ok"] and r["result"]["steered"] is True)
        r = c.call("submit", text="queued from the panel", origin=STUDIO, when_busy="queue")
        ctx.check(f"held, got {r}", r["ok"] and r["result"]["queued"] is True)
        c.call("answer", kind="permission", request_id="perm_1", action="allow", origin=STUDIO)
        ctx.check("the held turn ran", _wait(lambda: rig.session.turn_count == 4 and not rig.session.busy))
        got = _drain(rig)
        notes = [e.data["text"] for e in got if e.kind == "system_note"]
        rows = [e.data["text"] for e in got if e.kind == "user_message"]
        ctx.check(f"no steer note, got {notes}", not [t for t in notes if "steer:" in t])
        ctx.check(f"`(from Studio) queued:` stays, got {notes}",
                  [t for t in notes if t.startswith("(from Studio) queued: queued from the panel")] != [])
        ctx.check(f"no `the queued turn starts` note, got {notes}", not [t for t in notes if "queued turn starts" in t])
        ctx.check(f"the held turn's row is there once, got {rows}", rows.count("queued from the panel") == 1)


@test
def test_studio_interrupt_draws_no_remote_note(ctx: Ctx):
    with Rig(start_controller=False) as rig:
        c = rig.client()
        for via in ("Studio", "studio"):
            r = c.call("interrupt", origin={"via": via})
            ctx.check(f"interrupt via {via} ok", r["ok"] and r["result"]["interrupted"] is True)
        notes = [e.data["text"] for e in _drain(rig) if e.kind == "system_note"]
        ctx.check(f"Studio's interrupt draws no (remote) note, got {notes}", not [t for t in notes if "interrupt" in t])
        c.call("interrupt")
        c.call("mode", mode="auto")
        notes = [e.data["text"] for e in _drain(rig) if e.kind == "system_note"]
        ctx.check(f"another client keeps `(remote) interrupt` and `(remote) mode`, got {notes}",
                  notes.count("(remote) interrupt") == 1 and "(remote) mode auto" in notes)


# ---- P2 -----------------------------------------------------------------------------------------------------------
@test
def test_socket_turn_scrolls_to_bottom(ctx: Ctx):
    async def body():
        fake, app = _app()
        async with app.run_test(size=(80, 20)) as pilot:
            await pilot.pause(0.2)
            for i in range(60):
                await app.transcript.add_note(f"earlier line {i}")
            await pilot.pause(0.2)
            for kind, event in (("user_message", ev.Event("user_message", {"text": "sent from Studio", "images": [],
                                                                            "via": "studio"}, turn=2)),
                                ("steer_queued", ev.steer_queued("a steer from Studio", turn=2))):
                app.transcript.scroll_home(animate=False)
                await pilot.pause(0.2)
                ctx.check(f"{kind}: scrolled up first", app.transcript.scroll_y < app.transcript.max_scroll_y)
                from halo_harness.tui.dispatch import apply_event
                await apply_event(app, event)
                await pilot.pause(0.3)
                ctx.check(f"{kind}: the transcript is at the bottom, got {app.transcript.scroll_y} of "
                          f"{app.transcript.max_scroll_y}", app.transcript.scroll_y >= app.transcript.max_scroll_y)
    asyncio.run(body())


# ---- P4 -----------------------------------------------------------------------------------------------------------
@test
def test_socket_answer_closes_the_card_and_the_one_behind(ctx: Ctx):
    from halo_harness.tui.dispatch import apply_event

    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            await apply_event(app, _perm("req-1"))
            await apply_event(app, _perm("req-2"))
            await pilot.pause(0.2)
            marks = _markers(app)
            ctx.check("req-1 shows, req-2 waits", getattr(app.pending_card, "request_id", "") == "req-1"
                      and [q.request_id for q in app._pending_queue] == ["req-2"])
            await apply_event(app, ev.ask_answered("req-2", "permission", "Deny", "studio"))
            await pilot.pause(0.2)
            ctx.check("the one behind left the waiting list", app._pending_queue == []
                      and getattr(app.pending_card, "request_id", "") == "req-1")
            ctx.check(f"its marker is the line, got {marks['req-2'].raw_text!r}",
                      marks["req-2"].raw_text == "Answered in Studio: Deny")
            await apply_event(app, ev.ask_answered("req-1", "permission", "Allow", "studio"))
            await pilot.pause(0.3)
            ctx.check("the shown card closed", app.pending_card is None)
            ctx.check(f"its marker is the line, got {marks['req-1'].raw_text!r}",
                      marks["req-1"].raw_text == "Answered in Studio: Allow")
            ctx.check(f"the terminal answered nothing itself, got {fake.permission_replies}", fake.permission_replies == [])
            await apply_event(app, _plan("plan-x"))
            await pilot.pause(0.2)
            mark = _markers(app)["plan"]
            await apply_event(app, ev.ask_answered("toolu_other", "plan", "Approve the plan", "remote"))
            await pilot.pause(0.3)
            ctx.check("the open plan card closed", app.pending_card is None and fake.plan_replies == [])
            ctx.check(f"its line, got {mark.raw_text!r}", mark.raw_text == "Answered remotely: Approve the plan")
            ctx.check("no (remote) line anywhere", not [t for t in app.transcript.plain_log if "(remote)" in t])
    asyncio.run(body())


@test
def test_socket_answer_while_typing_a_deny_reason_keeps_the_text(ctx: Ctx):
    """THE GATE: every card that borrows the box (a deny reason, a question's Other, plan feedback, an approval
    edit): he starts typing, the ask is answered over the socket; the card is gone, the placeholder is back, the
    words are still in the box, nothing was sent, one `Answered in Studio` line."""
    from halo_harness.tui.dispatch import apply_event

    async def borrow_permission(app, pilot):
        await pilot.press("4")

    async def borrow_question(app, pilot):
        ol = app.pending_card._lists[0]
        ol.highlighted = len(app.pending_card.questions[0][1])  # the "Other" row
        ol.action_select()

    async def borrow_plan(app, pilot):
        await pilot.press("3")

    async def borrow_approval(app, pilot):
        await pilot.press("2")

    cases = (("deny reason", _perm("req-1"), borrow_permission, ("req-1", "permission", "Allow")),
             ("question Other", _question("q-1"), borrow_question, ("q-1", "question", "red")),
             ("plan feedback", _plan("plan-1"), borrow_plan, ("plan-1", "plan", "Approve the plan")),
             ("approval edit", _approval("appr-1"), borrow_approval, ("appr-1", "approval", "Accept")))

    async def body(name, event, borrow, answer):
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            await apply_event(app, event)
            await pilot.pause(0.3)
            await borrow(app, pilot)
            await pilot.pause(0.3)
            ctx.check(f"{name}: the card borrows the box", app._borrowing_card is not None)
            typed = "keep the old one, it still works"
            app.prompt_input.insert(typed)
            await pilot.pause(0.1)
            await apply_event(app, ev.ask_answered(answer[0], answer[1], answer[2], "studio"))
            await pilot.pause(0.3)
            ctx.check(f"{name}: the card is gone", app.pending_card is None and app._borrowing_card is None)
            ctx.check(f"{name}: the placeholder is back, got {app.prompt_input.placeholder!r}",
                      app.prompt_input.placeholder == app._current_placeholder_text())
            ctx.check(f"{name}: the words are still in the box, got {app.prompt_input.text!r}",
                      app.prompt_input.text == typed)
            ctx.check(f"{name}: no turn, no steer, no answer of its own, got {fake.submitted}",
                      fake.submitted == [] and not fake.permission_replies and not fake.question_replies
                      and not fake.plan_replies and not fake.approval_replies)
            lines = _answered_notes(app)
            ctx.check(f"{name}: one line, got {lines}", lines == [f"Answered in Studio: {answer[2]}"])
    for case in cases:
        asyncio.run(body(*case))


@test
def test_kept_text_never_answers_the_card_behind_or_goes_as_a_prompt(ctx: Ctx):
    """THE GATE, the Enter he was about to press: what he typed for a card that a Studio answer closed (or whose own
    Enter lost the claim) stays in the box and the next Enter sends it nowhere -- not as the answer to the card that
    waited behind it, not as a prompt or a steer. Once he changes the box, Enter is his again."""
    from halo_harness.tui.dispatch import apply_event

    async def borrow_permission(app, pilot):
        await pilot.press("4")

    async def borrow_question(app, pilot):
        ol = app.pending_card._lists[0]
        ol.highlighted = len(app.pending_card.questions[0][1])  # the "Other" row
        ol.action_select()

    async def enter(app, pilot):
        app.set_focus(app.prompt_input)
        await pilot.press("enter")
        await pilot.pause(0.3)

    def nothing_sent(fake) -> bool:
        return (fake.submitted == [] and not fake.permission_replies and not fake.question_replies
                and not fake.plan_replies and not fake.approval_replies)

    typed = "reason meant for the first ask"

    async def body(name, first, borrow, answer, behind, lost):
        fake, app = _app()
        if lost:
            fake.lost_request_ids = {answer[0]}
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            await apply_event(app, first)
            if behind is not None:
                await apply_event(app, behind)
            await pilot.pause(0.3)
            await borrow(app, pilot)
            await pilot.pause(0.3)
            app.prompt_input.insert(typed)
            await pilot.pause(0.1)
            if lost:
                await enter(app, pilot)  # his Enter lost the claim: the card closed, the words stay
            else:
                await apply_event(app, ev.ask_answered(answer[0], answer[1], answer[2], "studio"))
                await pilot.pause(0.3)
            ctx.check(f"{name}: the words are in the box, got {app.prompt_input.text!r}", app.prompt_input.text == typed)
            if behind is not None:
                ctx.check(f"{name}: the card behind shows", getattr(app.pending_card, "request_id", "") == "req-2")
            await enter(app, pilot)
            ctx.check(f"{name}: Enter sent nothing, got {fake.submitted} {fake.permission_replies}", nothing_sent(fake))
            ctx.check(f"{name}: the words are still in the box, got {app.prompt_input.text!r}",
                      app.prompt_input.text == typed)
            if behind is not None:
                ctx.check(f"{name}: the card behind still waits", getattr(app.pending_card, "request_id", "") == "req-2")
            app.prompt_input.insert(" now")
            await pilot.pause(0.2)
            await enter(app, pilot)
            if behind is not None:
                got = fake.permission_replies
                ctx.check(f"{name}: changed, Enter answers the card he sees, got {got}",
                          [(r, d.get("action"), d.get("message")) for r, d in got] == [("req-2", "deny", typed + " now")])
            else:
                ctx.check(f"{name}: changed, Enter is an ordinary prompt, got {fake.submitted}",
                          fake.submitted == [typed + " now"])

    cases = (("deny reason, one behind", _perm("req-1"), borrow_permission, ("req-1", "permission", "Allow"),
              _perm("req-2"), False),
             ("question Other, one behind", _question("q-1"), borrow_question, ("q-1", "question", "red"),
              _perm("req-2"), False),
             ("deny reason, nothing behind", _perm("req-1"), borrow_permission, ("req-1", "permission", "Allow"),
              None, False),
             ("his own Enter lost, one behind", _perm("req-1"), borrow_permission, ("req-1", "permission", "Allow"),
              _perm("req-2"), True))
    for case in cases:
        asyncio.run(body(*case))


@test
def test_a_lost_plan_marker_never_takes_the_next_plan(ctx: Ctx):
    """P4/P73: a plan card whose key lost because the plan stopped waiting (no winner's event ever comes) leaves no
    marker behind that a LATER plan's Studio answer would land on: the later plan's card closes and its own marker
    gets the line."""
    from halo_harness.tui.dispatch import apply_event

    async def body():
        fake, app = _app()
        fake.lost_request_ids = {"plan"}
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            await apply_event(app, _plan("plan-1"))
            await pilot.pause(0.3)
            old = _markers(app)["plan"]
            old_text = old.raw_text
            await pilot.press("1")
            await pilot.pause(0.3)
            ctx.check("the stopped plan's card closed", app.pending_card is None)
            fake.lost_request_ids = set()
            await apply_event(app, _plan("plan-2"))
            await pilot.pause(0.3)
            new = _markers(app)["plan"]
            await apply_event(app, ev.ask_answered("plan-2", "plan", "Approve the plan", "studio"))
            await pilot.pause(0.3)
            ctx.check(f"the later plan's card closed, got {type(app.pending_card).__name__}", app.pending_card is None)
            ctx.check(f"its own marker has the line, got {new.raw_text!r}",
                      new.raw_text == "Answered in Studio: Approve the plan")
            ctx.check(f"the old marker is left as it was, got {old.raw_text!r}", old.raw_text == old_text)
            ctx.check(f"one line, got {_answered_notes(app)}", _answered_notes(app) == ["Answered in Studio: Approve the plan"])
    asyncio.run(body())


@test
def test_a_mode_change_that_answers_an_ask_emits_its_event(ctx: Ctx):
    """P6: every answered ask emits one `ask_answered`, also when a mode change (Shift+Tab) decides it -- the shown
    card and one waiting behind it -- so Studio's copy of the ask can close too."""
    from halo_harness.tui.dispatch import apply_event

    async def body():
        fake, app = _app()
        fake.events = sink = _Sink()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            await apply_event(app, _perm("req-1"))
            await apply_event(app, _perm("req-2"))
            await pilot.pause(0.3)
            fake.permission_mode = "auto"
            app._reevaluate_pending_permission_for_mode("auto")
            await pilot.pause(0.3)
            got = [(e.data["request_id"], e.data["kind"], e.data["label"], e.data["where"])
                   for e in sink.put_events if getattr(e, "kind", "") == "ask_answered"]
            ctx.check(f"one event per decided ask, got {got}",
                      got == [("req-1", "permission", "Allow", "terminal"), ("req-2", "permission", "Allow", "terminal")])
            ctx.check("both cards are gone", app.pending_card is None and app._pending_queue == [])
    asyncio.run(body())


# ---- P5 -----------------------------------------------------------------------------------------------------------
@test
def test_answered_line_names_label_and_where(ctx: Ctx):
    from halo_harness.tui.dispatch import apply_event
    table = [
        (("permission", {"action": "allow", "scope": "once"}), "Allow"),
        (("permission", {"action": "allow", "scope": "session"}), "Allow for this session"),
        (("permission", {"action": "allow", "scope": "always"}), "Allow always"),
        (("permission", {"action": "deny", "scope": None, "message": ""}), "Deny"),
        (("permission", {"action": "deny", "message": "not that file"}), "Deny: not that file"),
        (("question", {"answer": "red"}), "red"),
        (("question", {"answer": ["red", "blue"]}), "red; blue"),
        (("question", {"answer": {"which?": "red", "size?": "big"}}), "red; big"),
        (("plan", {"approved": True}), "Approve the plan"),
        (("plan", {"approved": False, "feedback": ""}), "Keep planning"),
        (("plan", {"approved": False, "feedback": "smaller steps"}), "Keep planning: smaller steps"),
        (("approval", {"action": "accept"}), "Accept"),
        (("approval", {"action": "edit", "instruction": None}), "Edit, re-run"),
        (("approval", {"action": "edit", "instruction": "shorter"}), "Edit, re-run: shorter"),
        (("approval", {"action": "stop"}), "Stop"),
    ]
    for (kind, fields), want in table:
        got = ev.ask_label(kind, fields)
        ctx.check(f"{kind} {fields} -> {want!r}, got {got!r}", got == want)
    ctx.check("Studio's words", ev.answered_line("studio", "Allow") == "Answered in Studio: Allow")
    ctx.check("another client's words", ev.answered_line("remote", "Allow") == "Answered remotely: Allow")
    ctx.check("via Studio in any case is studio", ev.where_of("Studio") == "studio" and ev.where_of("") == "remote")
    longest = max(len(ev.answered_line(w, want)) for w in ("studio", "remote") for _, want in table)
    ctx.check(f"every line without typed words fits 80 columns, longest {longest}", longest <= 80)
    reason = ("the build folder holds the only copy of the signed installer " * 4)[:199] + "!"

    async def body():
        fake, app = _app()
        async with app.run_test(size=(80, 30)) as pilot:
            await pilot.pause(0.2)
            await apply_event(app, _perm("req-9"))
            await pilot.pause(0.2)
            mark = _markers(app)["req-9"]
            await apply_event(app, ev.answered(None, "req-9", "permission", {"action": "deny", "message": reason},
                                               "remote"))
            await pilot.pause(0.3)
            want = "Answered remotely: Deny: " + reason
            ctx.check(f"the 200-character reason whole in the line, got {mark.raw_text!r}", mark.raw_text == want)
            ctx.check(f"wrapped on screen, never cut, got height {mark.size.height}", mark.size.height >= 3)
            ctx.check(f"one line, got {_answered_notes(app)}", _answered_notes(app) == [want])
    asyncio.run(body())


@test
def test_answer_via_reaches_the_handle(ctx: Ctx):
    with Rig() as rig:
        c = rig.client()
        ctx.check("turn 1 parks", _turn(rig, c, "please ask first", 1, "_permission_waiters", "perm_1"))
        r = c.call("answer", kind="permission", request_id="perm_1", action="allow", origin={"via": "Studio"})
        ctx.check(f"answered, got {r}", r["ok"])
        ctx.check("turn 2 parks", _wait(lambda: not rig.session.busy) and
                  _turn(rig, c, "please ask again", 2, "_permission_waiters", "perm_1"))
        c.call("answer", kind="permission", request_id="perm_1", action="allow", scope="session")
        _wait(lambda: not rig.session.busy)
        ctx.check("turn 3 parks on a question", _turn(rig, c, "ask-question now", 3, "_question_waiters", "q_1"))
        c.call("answer", kind="question", request_id="q_1", answer="red", origin=STUDIO)
        _wait(lambda: not rig.session.busy)
        ctx.check("turn 4 parks on a plan", _turn(rig, c, "ask-plan now", 4, "_plan_waiters", "plan_1"))
        c.call("answer", kind="plan", approved=False, feedback="smaller steps", origin=STUDIO)
        _wait(lambda: not rig.session.busy)
        ctx.check("turn 5 parks on an approval", _turn(rig, c, "ask-approval now", 5, "_approval_waiters", "appr_1"))
        c.call("answer", kind="approval", request_id="appr_1", action="edit", instruction="shorter")
        _wait(lambda: not rig.session.busy)
        got = _drain(rig)
        answers = [(e.data["kind"], e.data["label"], e.data["where"]) for e in got if e.kind == "ask_answered"]
        ctx.check(f"one event per answer, the via reached the handle, got {answers}", answers == [
            ("permission", "Allow", "studio"), ("permission", "Allow for this session", "remote"),
            ("question", "red", "studio"), ("plan", "Keep planning: smaller steps", "studio"),
            ("approval", "Edit, re-run: shorter", "remote")])
        notes = [e.data["text"] for e in got if e.kind == "system_note"]
        ctx.check(f"no (remote) permission|question|plan|approval note, got {notes}",
                  not [t for t in notes if t.startswith(("(remote) permission", "(remote) question", "(remote) plan",
                                                         "(remote) approval"))])


# ---- P6 -----------------------------------------------------------------------------------------------------------
@test
def test_ask_answered_event_from_both_sides(ctx: Ctx):
    from halo_harness.tui.dispatch import apply_event
    ctx.check("ask_answered is an event kind", "ask_answered" in ev.EVENT_KINDS)

    async def body():
        fake, app = _app()
        fake.events = sink = _Sink()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            for event, keys, want in ((_perm("req-1"), ("1",), ("req-1", "permission", "Allow")),
                                      (_approval("appr-1"), ("3",), ("appr-1", "approval", "Stop")),
                                      (_plan("plan-1"), ("1",), ("plan-1", "plan", "Approve the plan"))):
                sink.put_events.clear()
                await apply_event(app, event)
                await pilot.pause(0.3)
                mark = list(_markers(app).values())[0]
                for key in keys:
                    await pilot.press(key)
                await pilot.pause(0.3)
                got = [(e.data["request_id"], e.data["kind"], e.data["label"], e.data["where"])
                       for e in sink.put_events if e.kind == "ask_answered"]
                ctx.check(f"the terminal's own answer: one event, got {got}", got == [(*want, "terminal")])
                ctx.check(f"the card keeps its own words on the marker, got {mark.raw_text!r}",
                          not mark.raw_text.startswith("Answered "))
    asyncio.run(body())
    with Rig() as rig:
        c = rig.client()
        ctx.check("the turn parks", _turn(rig, c, "please ask first", 1, "_permission_waiters", "perm_1"))
        c.call("answer", kind="permission", request_id="perm_1", action="deny", message="no", origin=STUDIO)
        _wait(lambda: not rig.session.busy)
        got = [e.data for e in _drain(rig) if e.kind == "ask_answered"]
        ctx.check(f"the socket's answer: one event, got {got}",
                  got == [{"request_id": "perm_1", "kind": "permission", "label": "Deny: no", "where": "studio"}])


# ---- P73 ----------------------------------------------------------------------------------------------------------
class _Engine:
    mode = "auto"

    def decide(self, tool_name, tool_input, tool):
        from halo_harness.permissions import Decision
        return Decision(action="allow", reason="", rule=None, message="")


def _slots():
    from halo_harness.agent.loop import Session

    class _Slots:
        resolve_permission = Session.resolve_permission
        resolve_question = Session.resolve_question
        resolve_plan = Session.resolve_plan
        resolve_approval = Session.resolve_approval
        reevaluate_pending_permission = Session.reevaluate_pending_permission

        def __init__(self) -> None:
            self._permission_waiters, self._question_waiters = {}, {}
            self._plan_waiters, self._approval_waiters = {}, {}
            self._pending_plan_id = None
            self.permission_engine = _Engine()
    return _Slots()


def _handle(session, out: list):
    from halo_harness.remote.base import _BaseHandle

    class _H(_BaseHandle):
        def _emit(self, e) -> None:
            out.append(e)

        def _add_rule(self, rule, scope):
            return None
    return _H(session, REPO_DIR)


@test
def test_crossed_answers_one_wins_one_event(ctx: Ctx):
    rounds = 40
    for kind in ("permission", "question", "plan", "approval"):
        bad = []
        for i in range(rounds):
            s, out = _slots(), []
            h = _handle(s, out)
            rid = f"{kind}-{i}"
            table = {"permission": s._permission_waiters, "question": s._question_waiters,
                     "plan": s._plan_waiters, "approval": s._approval_waiters}[kind]
            table[rid] = {"event": threading.Event(), "decision": None, "answer": None}
            if kind == "plan":
                s._pending_plan_id = rid
            gate, won = threading.Barrier(2), {}

            def terminal():
                gate.wait()
                if kind == "permission":
                    ok = s.resolve_permission(rid, {"action": "deny", "message": ""})
                    fields = {"action": "deny"}
                elif kind == "question":
                    ok, fields = s.resolve_question(rid, "blue"), {"answer": "blue"}
                elif kind == "plan":
                    ok, fields = s.resolve_plan({"approved": False, "feedback": ""}), {"approved": False}
                else:
                    ok, fields = s.resolve_approval(rid, {"action": "stop"}), {"action": "stop"}
                if ok:
                    ev.answered(out.append, rid, kind, fields, "terminal")
                won["terminal"] = ok

            def socket_side():
                gate.wait()
                if kind == "permission":
                    won["socket"] = h.answer_permission(rid, "allow", via="studio")
                elif kind == "question":
                    won["socket"] = h.answer_question(rid, "red", via="studio")
                elif kind == "plan":
                    won["socket"] = h.answer_plan(True, via="studio")
                else:
                    won["socket"] = h.answer_approval(rid, "accept", via="studio")
            threads = [threading.Thread(target=terminal), threading.Thread(target=socket_side)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(5)
            events_out = [e for e in out if e.kind == "ask_answered"]
            slot = table[rid]
            stored = slot.get("answer") if kind == "question" else slot.get("decision")
            winner = "socket" if won.get("socket") else "terminal"
            want_where = "studio" if winner == "socket" else "terminal"
            want_stored = {"permission": {"socket": "allow", "terminal": "deny"},
                           "question": {"socket": "red", "terminal": "blue"},
                           "plan": {"socket": True, "terminal": False},
                           "approval": {"socket": "accept", "terminal": "stop"}}[kind][winner]
            got_stored = (getattr(stored, "action", None) or (stored or {}).get("action") if kind == "permission"
                          else stored if kind == "question" else (stored or {}).get("approved") if kind == "plan"
                          else (stored or {}).get("action"))
            if not (sorted(won.values()) == [False, True] and len(events_out) == 1
                    and events_out[0].data["where"] == want_where and got_stored == want_stored):
                bad.append((i, won, [e.data for e in events_out], got_stored))
        ctx.check(f"{kind}: in {rounds} crossings one answer won, one got False, one event that names the winner, "
                  f"the winner's decision stored; bad: {bad[:2]}", bad == [])
    s, out = _slots(), []
    s._permission_waiters["r1"] = {"event": threading.Event(), "decision": None, "tool_name": "Bash",
                                   "tool_input": {"command": "ls"}, "tool": None}
    ctx.check("a socket answer claims it", _handle(s, out).answer_permission("r1", "deny", via="studio") is True)
    ctx.check("a later mode change re-decides nothing", s.reevaluate_pending_permission("r1") is None)
    ctx.check("a later key gets False", s.resolve_permission("r1", {"action": "allow"}) is False)
    s._permission_waiters["r2"] = {"event": threading.Event(), "decision": None, "tool_name": "Bash",
                                   "tool_input": {"command": "ls"}, "tool": None}
    ctx.check("a mode change that decides claims it", s.reevaluate_pending_permission("r2") == "allow")
    ctx.check("then a socket answer gets False", _handle(s, out).answer_permission("r2", "deny") is False)


@test
def test_a_card_key_that_lost_closes_and_does_nothing_else(ctx: Ctx):
    """P73 in the terminal: the card's key lost the claim -- the card closes, no toast, no rule, no event of its own,
    no decision of its own on the marker; the winner's event writes the one line."""
    from halo_harness.tui.dispatch import apply_event

    async def body():
        fake, app = _app()
        fake.events = sink = _Sink()
        fake.lost_request_ids = {"req-1"}
        toasts = []
        async with app.run_test(size=(100, 30)) as pilot:
            app.notify = lambda *a, **k: toasts.append(a)
            await pilot.pause(0.2)
            await apply_event(app, _perm("req-1"))
            await pilot.pause(0.3)
            mark = _markers(app)["req-1"]
            before = mark.raw_text
            await pilot.press("3")  # allow always: would write a rule if it had won
            await pilot.pause(0.3)
            ctx.check("the card closed", app.pending_card is None)
            ctx.check(f"no toast, no rule, no event, got {toasts} {fake.added_rules} {sink.put_events}",
                      toasts == [] and fake.added_rules == [] and sink.put_events == [])
            ctx.check(f"no decision of its own on the marker, got {mark.raw_text!r}", mark.raw_text == before)
            await apply_event(app, ev.ask_answered("req-1", "permission", "Deny", "studio"))
            await pilot.pause(0.2)
            ctx.check(f"the winner's line, got {mark.raw_text!r}", mark.raw_text == "Answered in Studio: Deny")
            ctx.check(f"one line, got {_answered_notes(app)}", _answered_notes(app) == ["Answered in Studio: Deny"])
    asyncio.run(body())


# ---- P7 -----------------------------------------------------------------------------------------------------------
@test
def test_text_after_a_stale_card_starts_a_turn_and_joins_history(ctx: Ctx):
    from halo_harness.tui.dispatch import apply_event

    async def body(event, rid):
        fake, app = _app()
        fake.turns = [[ev.user_message("do this instead", turn=2)]]  # the turn's row, as a real Controller emits it
        fake.lost_request_ids = {rid}
        toasts, history = [], []
        async with app.run_test(size=(100, 30)) as pilot:
            app.notify = lambda *a, **k: toasts.append(a)
            app._record_submitted_history = lambda text, pasted: history.append(text)
            await pilot.pause(0.2)
            await apply_event(app, event)
            await pilot.pause(0.3)
            app.set_focus(app.prompt_input)
            app.prompt_input.insert("do this instead")
            await pilot.pause(0.1)
            await pilot.press("enter")
            await pilot.pause(0.4)
            ctx.check(f"{rid}: the card closed", app.pending_card is None)
            ctx.check(f"{rid}: sent as an ordinary prompt, got {fake.submitted}", fake.submitted == ["do this instead"])
            ctx.check(f"{rid}: a row, got {app.transcript.plain_log[-3:]}",
                      any("do this instead" in t for t in app.transcript.plain_log))
            ctx.check(f"{rid}: a history entry, got {history}", history == ["do this instead"])
            ctx.check(f"{rid}: no toast, got {toasts}", toasts == [])
            ctx.check(f"{rid}: the box is empty", app.prompt_input.text == "")
    asyncio.run(body(_perm("req-1"), "req-1"))
    asyncio.run(body(_approval("appr-1"), "appr-1"))


# ---- P17 ----------------------------------------------------------------------------------------------------------
@test
def test_private_studio_line(ctx: Ctx):
    from halo_harness.remote import runtime
    from halo_harness.tui import studio_open
    old_flag, old_opener = runtime._private_flag, studio_open.OPENER
    opened, lines = [], []
    studio_open.OPENER = lambda *a, **k: opened.append(a)
    runtime._private_flag = True
    try:
        host = SimpleNamespace(controller=None, notify=lambda *a, **k: None)
        for word in ("", "session"):
            lines.clear()
            r = studio_open.open_section(host, word, on_line=lines.append)
            ctx.check(f"/studio {word}: says so and opens nothing, got {r} {lines} {opened}",
                      r is False and lines == ["This session is private: Studio cannot see it or type into it."]
                      and opened == [])
    finally:
        runtime._private_flag, studio_open.OPENER = old_flag, old_opener


# ==== batch 2 (the design's F1b): P3, P8-P12, P16, P70 ===============================================================
NAME = "someone@gpu-box"  # a user and host name a client might send: it must reach nothing


def _dump(x) -> str:
    import json
    return json.dumps(x, default=str, ensure_ascii=False)


# ---- P3 -----------------------------------------------------------------------------------------------------------
@test
def test_no_user_or_host_in_meta_frames_or_log(ctx: Ctx):
    origin = {"via": "studio", "by": NAME}
    with Rig() as rig:
        c = rig.client()
        c.call("submit", text="hello from the panel", origin=origin, receipt="r_name1")
        ctx.check("a Studio turn ran", _wait(lambda: rig.session.turn_count == 1 and not rig.session.busy))
        ctx.check("turn 2 parks", _turn(rig, c, "please ask first", 2, "_permission_waiters", "perm_1"))
        r = c.call("submit", text="steer it now", origin=origin)
        ctx.check(f"a steer, got {r}", r["ok"] and r["result"]["steered"] is True)
        c.call("answer", kind="permission", request_id="perm_1", action="allow", origin=origin)
        ctx.check("turn 2 ends", _wait(lambda: not rig.session.busy))
        r = c.call("agent_steer", agent_id="main", text="look again", by=NAME)
        ctx.check(f"a steer of the main agent, got {r}", r["ok"])
        ctx.check("its turn ran", _wait(lambda: rig.session.turn_count == 3 and not rig.session.busy))
        r = c.call("agent_stop", agent_id="main", reason="enough for now", by=NAME)
        ctx.check(f"an agent stop, got {r}", r["ok"])
        r = c.call("note", name="fleet.message", text="hi there", by=NAME)
        ctx.check(f"a fleet.message names the via, got {r}", r["ok"] and r["result"] == {"delivered": True, "via": "Studio"})
        frames = [{"kind": e.kind, **e.data} for e in _drain(rig)]
        nodes = rig.session.log.nodes()
        from halo_harness.remote.receipt_seams import rows
        receipts = rows(rig.session, rig.cwd)
        for what, blob in (("frames", frames), ("the session log", nodes), ("the receipts", receipts)):
            ctx.check(f"no user or host name in {what}", NAME not in _dump(blob) and "gpu-box" not in _dump(blob))
        users = [f for f in frames if f["kind"] == "user_message" and f.get("text") == "hello from the panel"]
        ctx.check(f"the turn's user_message carries via and no by, got {users}",
                  len(users) == 1 and users[0].get("via") == "studio" and "by" not in users[0])
        meta = [n["control"] for n in nodes if n.get("type") == "meta" and n.get("control")]
        ctx.check(f"the control records carry via only, got {meta}",
                  meta and all("by" not in m and m["via"] == "Studio" for m in meta))
        notes = [f["text"] for f in frames if f["kind"] == "system_note"]
        ctx.check(f"the message line names Studio, got {notes}", "(remote) message from Studio: hi there" in notes)


class _CtlHandle:
    """What agent_control needs of a handle: a TUI-backed one (`controller`), its notes, submits and shutdown."""

    def __init__(self, session) -> None:
        self.session, self.session_id, self.controller = session, session.log.session_id, object()
        self.notes: list = []
        self.submitted: list = []
        self.shut: list = []

    def _note(self, line: str) -> None:
        self.notes.append(line)

    def submit(self, text: str, **kw) -> dict:
        self.submitted.append(text)
        return {"steered": False}

    def interrupt(self, **kw) -> dict:
        return {"interrupted": True}

    def control_shutdown(self, text: str) -> None:
        self.shut.append(text)


@test
def test_agent_control_lines_name_no_one(ctx: Ctx):
    from halo_harness.agent import agent_inbox, agent_registry
    from halo_harness.remote import agent_control, protocol
    from tests.helpers.fake_remote_session import FakeSession
    main, child = FakeSession(), FakeSession("childsession000000000000000000001")
    child.agent_id = "a1"
    h = _CtlHandle(main)
    tree = agent_registry.tree_for(main)
    child._agent_tree = tree
    tree.add("a1", session=child, parent=tree.root_id, name="reader", state="running")
    tree.add("job:7", parent=tree.root_id, name="bash", state="running")
    main.job_registry = SimpleNamespace(kill=lambda jid: (True, f"killed {jid}"))

    def call(cmd: str, **fields) -> dict:
        return agent_control.run(h, {"cmd": cmd, "by": NAME, **fields})

    call("agent_steer", agent_id="a1", text="look at the index")
    ctx.check(f"the steer note reads `[steer from Studio] `, got {tree.controls.inbox.get('a1')}",
              tree.controls.drain("a1") == ["[steer from Studio] look at the index"])
    call("agent_steer", agent_id="main", text="do the other thing", handoff=True)
    ctx.check(f"the hand-off note reads `[hand-off from Studio] `, got {h.submitted}",
              h.submitted and h.submitted[-1].startswith("[hand-off from Studio] "))
    call("agent_steer", agent_id="a1", text="start over", handoff=True)
    tree.controls.drain("a1")
    ctx.check("a redirect's cut reads `not run: redirected from Studio`",
              agent_inbox.before_tool(child) == ("not run: redirected from Studio", False))
    call("pause", agent_id="a1")
    call("resume", agent_id="a1")
    call("pause", reason="cap")
    call("resume")
    call("agent_stop", agent_id="job:7", reason="too long")
    call("agent_stop", agent_id="a1", reason="enough for now")
    ctx.check("a stopped agent's next tool reads `not run: stopped from Studio`",
              agent_inbox.before_tool(child) == ("not run: stopped from Studio", True))
    ctx.check("its parent reads `stopped from Studio: <reason>`",
              agent_inbox.handback(child, "").startswith("stopped from Studio: enough for now"))
    call("shutdown", reason="done for today")
    protocol._message(h, {"text": "hi there", "by": NAME})
    want = ["reader (a1) steered from Studio: look at the index",
            "the main agent taken over from Studio: do the other thing",
            "reader (a1) taken over from Studio: start over",
            "reader (a1) paused from Studio", "reader (a1) resumed from Studio",
            "the session paused from Studio: cap (each agent holds at its next tool boundary)",
            "the session resumed from Studio", "background job 7 stopped from Studio: too long",
            "reader (a1) stopped from Studio: enough for now", "message from Studio: hi there"]
    ctx.check(f"every agent line of section 3, no name, got {h.notes}", h.notes == want)
    ctx.check(f"the shutdown line, got {h.shut}", h.shut == ["shut down from Studio: done for today"])
    call("agent_steer", agent_id="a1", text="nudge", via="halo remote")
    ctx.check("another client's own via stands in its place",
              tree.controls.drain("a1") == ["[steer from halo remote] nudge"])
    logged = main.log.nodes() + child.log.nodes()
    ctx.check("no name in any line, record or note", NAME not in _dump([h.notes, h.shut, h.submitted, logged,
                                                                         tree.controls.stops, tree.controls.pauses]))


# ---- P8-P12: a slash line over the socket runs the terminal's own table ------------------------------------------
def _rows(app) -> list:
    from halo_harness.tui.widgets.transcript import UserMessage
    return [w.raw_text for w in app.transcript.query(UserMessage)]


def _notes(app) -> list:
    from halo_harness.tui.widgets.transcript import SystemNote
    return [w.raw_text for w in app.transcript.query(SystemNote)]


def _order(app) -> list:
    from halo_harness.tui.widgets.transcript import SystemNote, UserMessage
    return [("row" if isinstance(w, UserMessage) else "note", w.raw_text) for w in app.transcript.children
            if isinstance(w, (SystemNote, UserMessage))]


async def _hook(fake, name: str, args: str = "") -> tuple:
    """The socket's thread calling the TUI's hook (what ControllerHandle.run_slash does): (answer, seconds)."""
    t0 = time.monotonic()
    r = await asyncio.to_thread(fake.slash_hook, name, args)
    return r, time.monotonic() - t0


def _patched(name: str, fn):
    """Swap one handler of tui/slash.py's table for the test's own (handle_slash reads the table at call time)."""
    from halo_harness.tui import slash as S
    attr = f"_handle_{name}"
    old = getattr(S, attr)
    setattr(S, attr, fn)
    return lambda: setattr(S, attr, old)


@test
def test_socket_slash_runs_terminal_table_model_switches(ctx: Ctx):
    with Rig() as rig:
        c = rig.client()
        seen = []
        rig.controller.slash_hook = lambda name, args: seen.append((name, args)) or {"output": "done", "ran": True}
        r = c.call("slash", line="/model other-model")
        ctx.check(f"a session with the hook runs it, never run_slash, got {r} {seen}",
                  r["ok"] and r["result"] == {"output": "done", "ran": True} and seen == [("model", "other-model")])
        rig.controller.slash_hook = None
        r = c.call("slash", line="/help me")
        ctx.check(f"no hook: run_slash as today, a plain string ran, got {r}",
                  r["ok"] and r["result"] == {"output": "ran /help me", "ran": True})
        notes = [e.data["text"] for e in _drain(rig) if e.kind == "system_note"]
        ctx.check(f"no `(remote) /<name>` note, got {notes}", not [t for t in notes if t.startswith("(remote) /")])

    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            ctx.check("the TUI set the controller's slash hook at mount", callable(getattr(fake, "slash_hook", None)))
            r, _ = await _hook(fake, "model", "other-model")
            await pilot.pause(0.2)
            ctx.check(f"/model <ref> from Studio switches the model, got {fake.model} {r}",
                      fake.model == "other-model" and r["ran"] is True and "Model set to other-model" in r["output"])
            ctx.check("Controller.run_slash never ran", fake.slash_calls == [])
    asyncio.run(body())


@test
def test_untaken_socket_slash_never_runs_late(ctx: Ctx):
    from halo_harness.tui.slash_capture import BUSY

    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            before, box = fake.model, {}

            def call():
                t0 = time.monotonic()
                box["r"] = fake.slash_hook("model", "late-model")
                box["t"] = time.monotonic() - t0
            th = threading.Thread(target=call, daemon=True)
            th.start()
            time.sleep(1.5)  # the UI thread is held
            th.join(5)
            await pilot.pause(0.5)
            ctx.check(f"the busy words and ran false within 1.2 s, got {box}",
                      box.get("r") == {"output": BUSY, "ran": False} and box.get("t", 9) < 1.2)
            ctx.check(f"nothing ran after the UI freed, got {fake.model} {_rows(app)}",
                      fake.model == before and "/model late-model" not in _rows(app))
    asyncio.run(body())


@test
def test_slash_answer_holds_notes_and_toasts(ctx: Ctx):
    async def handler(app, args):
        await app.transcript.add_note("first note", kind="command")
        app.notify("a toast", title="/intro")
        await app.transcript.add_note("last note", kind="command")
    restore = _patched("intro", handler)

    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            r, _ = await _hook(fake, "intro", "x")
            await pilot.pause(0.2)
            ctx.check(f"notes and toasts in order, got {r}", r == {"output": "first note\na toast\nlast note", "ran": True})
            ctx.check(f"the terminal draws them as for a typed line, got {_order(app)[-3:]}",
                      _order(app)[-3:] == [("row", "/intro x"), ("note", "first note"), ("note", "last note")])
    try:
        asyncio.run(body())
    finally:
        restore()


@test
def test_worker_slash_status_output_reaches_the_answer(ctx: Ctx):
    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            for name in ("status", "help"):
                r, _ = await _hook(fake, name)
                ctx.check(f"/{name} works in a worker thread; its output is in the answer, got {r}",
                          r == {"output": f"(fake) ran /{name}", "ran": True})
            await pilot.pause(0.2)
            ctx.check(f"and in the terminal, got {_notes(app)}", "(fake) ran /status" in _notes(app))
    asyncio.run(body())


@test
def test_unrelated_toast_not_in_slash_output(ctx: Ctx):
    async def handler(app, args):
        app.notify("its own toast", title="/intro")
        await asyncio.sleep(0.4)
    restore = _patched("intro", handler)

    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            task = asyncio.ensure_future(_hook(fake, "intro"))
            await asyncio.sleep(0.15)
            app.notify("a canary toast")  # made by something else while the line runs
            await app.transcript.add_note("a title changed")
            r, _ = await task
            ctx.check(f"only the line's own toast is in it, got {r}", r == {"output": "its own toast", "ran": True})
    try:
        asyncio.run(body())
    finally:
        restore()


@test
def test_slash_note_keeps_its_line_breaks(ctx: Ctx):
    text = "Line one\n  indented two\n\nafter a blank"

    async def handler(app, args):
        await app.transcript.add_note(text, kind="command")
    restore = _patched("intro", handler)

    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            r, _ = await _hook(fake, "intro")
            ctx.check(f"the note whole, its line breaks kept, got {r!r}", r == {"output": text, "ran": True})
    try:
        asyncio.run(body())
    finally:
        restore()


@test
def test_slash_over_3500ms_answers_still_running(ctx: Ctx):
    from halo_harness.tui.slash_capture import STILL

    async def body():
        fake, app = _app()
        plain = fake.run_slash

        def slow(name, args=""):
            if name == "slowcmd":
                time.sleep(4.2)
                return "the late output"
            return plain(name, args)
        fake.run_slash = slow
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            r, took = await _hook(fake, "slowcmd")
            ctx.check(f"the output so far and the still-running line within 4.6 s, ran true, got {r} in {took:.2f}s",
                      r == {"output": STILL, "ran": True} and took < 4.6)
            for _ in range(60):
                if "the late output" in _notes(app):
                    break
                await pilot.pause(0.1)
            ctx.check(f"the rest shows in the terminal, got {_notes(app)}", "the late output" in _notes(app))
    asyncio.run(body())


@test
def test_needs_screen_opens_nothing_and_says_so(ctx: Ctx):
    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            screens = len(app.screen_stack)
            for name, args in (("model", ""), ("resume", ""), ("rewind", ""), ("update", ""), ("ollama", "hosts"),
                               ("mcp", ""), ("permissions", ""), ("keys", ""), ("explain", "x"), ("effort", "")):
                r, _ = await _hook(fake, name, args)
                await pilot.pause(0.1)
                line = f"/{name} opens a window in the terminal: type it there."
                ctx.check(f"/{name} {args}: the line and ran false, got {r}", r == {"output": line, "ran": False})
                ctx.check(f"/{name}: the row then the line in the terminal, got {_order(app)[-2:]}",
                          _order(app)[-2:] == [("row", f"/{name} {args}".strip()), ("note", line)])
                ctx.check(f"/{name}: no screen and no card opened", len(app.screen_stack) == screens
                          and app.pending_card is None)
            ctx.check("nothing ran", fake.slash_calls == [])
    asyncio.run(body())


@test
def test_every_handler_that_pushes_a_screen_is_caught(ctx: Ctx):
    """Every handler of tui/slash.py's table that reaches a push site (a `push_screen`, a `set_pending_card`, the
    tasks panel, the editor) is in `needs_screen`; then a push the table missed is caught as it happens."""
    import ast
    import inspect
    from halo_harness.tui import slash as S
    from halo_harness.tui.slash_capture import needs_screen
    tree = ast.parse(inspect.getsource(S))
    funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    pushes = ("push_screen", "set_pending_card", "action_toggle_tasks", "action_open_editor")

    def reaches(name: str, seen: set) -> bool:
        if name in seen or name not in funcs:
            return False
        seen.add(name)
        names = {getattr(n, "attr", None) or getattr(n, "id", None) for n in ast.walk(funcs[name])}
        return bool(names & set(pushes)) or any(reaches(n, seen) for n in names if n in funcs)
    table = next(n for n in ast.walk(funcs["handle_slash"]) if isinstance(n, ast.Dict))
    handlers = {k.value: v.id for k, v in zip(table.keys, table.values) if isinstance(v, ast.Name)}
    pushing = sorted(name for name, fn in handlers.items() if reaches(fn, set()))
    missed = [n for n in pushing if not (needs_screen(n, "") or needs_screen(n, "hosts"))]
    ctx.check(f"the push sites found, got {pushing}", len(pushing) >= 12)
    ctx.check(f"every handler that pushes is in needs_screen, missed {missed}", missed == [])

    from textual.screen import ModalScreen

    async def handler(app, args):
        app.push_screen(ModalScreen())
    restore = _patched("intro", handler)

    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            screens = len(app.screen_stack)
            r, _ = await _hook(fake, "intro")
            await pilot.pause(0.2)
            line = "/intro opens a window in the terminal: type it there."
            ctx.check(f"a push the table missed is caught, got {r}", r == {"output": line, "ran": False})
            ctx.check("not pushed, the line in the terminal", len(app.screen_stack) == screens and line in _notes(app))
            app.push_screen(ModalScreen())  # outside a capture a push is a push
            await pilot.pause(0.2)
            ctx.check("a push outside a capture still opens", len(app.screen_stack) == screens + 1)
    try:
        asyncio.run(body())
    finally:
        restore()


@test
def test_screen_pushed_from_a_worker_is_caught(ctx: Ctx):
    from textual.screen import ModalScreen

    def work(app):
        time.sleep(0.2)
        app.call_from_thread(app.push_screen, ModalScreen())

    async def handler(app, args):
        app.run_worker(lambda: work(app), thread=True, name="pushes", group="pushes")
    restore = _patched("intro", handler)

    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            screens = len(app.screen_stack)
            r, _ = await _hook(fake, "intro")
            await pilot.pause(0.3)
            line = "/intro opens a window in the terminal: type it there."
            ctx.check(f"a worker's push is caught, got {r}", r == {"output": line, "ran": False})
            ctx.check("not pushed", len(app.screen_stack) == screens)
    try:
        asyncio.run(body())
    finally:
        restore()


@test
def test_box_commands_from_studio_leave_the_terminal_box(ctx: Ctx):
    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            pi = app.prompt_input
            pi.insert("half a thought")
            pi.images.append({"path": "chip.png"})
            text, chips = pi.text, list(pi.images)
            for name, args in (("paste", ""), ("paste", "shot.png"), ("images", "clear"), ("screenshot", "")):
                r, _ = await _hook(fake, name, args)
                await pilot.pause(0.1)
                line = f"/{name} works on the terminal's own box: type it there."
                ctx.check(f"/{name} {args}: the line, ran false, got {r}", r == {"output": line, "ran": False})
                ctx.check(f"/{name}: the row and the line in the terminal, got {_order(app)[-2:]}",
                          _order(app)[-2:] == [("row", f"/{name} {args}".strip()), ("note", line)])
                ctx.check(f"/{name}: the box and its chips unchanged", pi.text == text and list(pi.images) == chips)
            pi.images.clear()
    asyncio.run(body())


@test
def test_exit_from_studio_ends_the_terminal(ctx: Ctx):
    from halo_harness.remote import protocol

    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            r, _ = await _hook(fake, "exit")
            ctx.check(f"the answer comes first: output empty, ran true, the terminal still up, got {r}",
                      r.get("output") == "" and r.get("ran") is True and callable(r.get("then"))
                      and not app._quitting)
            conn = SimpleNamespace()
            ans = protocol._slash_answer(r, conn)
            ctx.check(f"the wire answer, the end held for after the send, got {ans}",
                      ans == {"output": "", "ran": True} and callable(getattr(conn, "then", None)) and not app._quitting)
            await asyncio.to_thread(conn.then)
            for _ in range(50):
                if getattr(fake, "quit_called", False):
                    break
                await pilot.pause(0.1)
            ctx.check("then the terminal's Halo ends as typed there", app._quitting and getattr(fake, "quit_called", False))
    asyncio.run(body())


@test
def test_slash_row_drawn_for_both_boxes(ctx: Ctx):
    async def handler(app, args):
        await app.transcript.add_note(f"intro {args}", kind="command")
    restore = _patched("intro", handler)

    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            app.prompt_input.insert("/intro typed")
            await pilot.press("enter")
            await pilot.pause(0.3)
            ctx.check(f"a typed line: its row then its output, got {_order(app)[-2:]}",
                      _order(app)[-2:] == [("row", "/intro typed"), ("note", "intro typed")])
            r, _ = await _hook(fake, "intro", "from studio")
            await pilot.pause(0.2)
            ctx.check(f"a Studio line: its row then its output, got {_order(app)[-2:]}",
                      _order(app)[-2:] == [("row", "/intro from studio"), ("note", "intro from studio")])
            ctx.check("no `(remote) /` line", not [t for t in _notes(app) if t.startswith("(remote) /")])
    try:
        asyncio.run(body())
    finally:
        restore()


# ---- P16, P70: the registry row follows the terminal and carries its first words -----------------------------------
def _registry_rows() -> dict:
    from halo_harness.remote import registry
    return {r["session_id"]: r for r in registry._load(registry.registry_path())}


@test
def test_new_row_follows_old_id(ctx: Ctx):
    from halo_harness.remote import registry, runtime
    from tests.helpers.fake_remote_session import FakeLog
    with Rig(serve=False, start_controller=False) as rig:
        act = runtime._open(rig.handle, rig.controller)
        try:
            old = act.session_id
            ctx.check("registered", old in _registry_rows())
            seen, real_reg, real_unreg = [], registry.register, registry.unregister

            def reg(entry):
                real_reg(entry)
                seen.append(("register", sorted(_registry_rows())))

            def unreg(sid):
                real_unreg(sid)
                seen.append(("unregister", sorted(_registry_rows())))
            registry.register, registry.unregister = reg, unreg
            try:
                new = "clearedsession00000000000000000002"
                rig.session.log = FakeLog(new)  # /clear: a fresh log under a new id
                rig.handle.hub.publish(ev.Event("status", {"session_id": new, "permission_mode": "default"}))
                ctx.check("re-registered", _wait(lambda: len(seen) >= 2, 5))
            finally:
                registry.register, registry.unregister = real_reg, real_unreg
            ctx.check(f"the new row is written before the old leaves, got {seen}",
                      seen == [("register", sorted([old, new])), ("unregister", [new])])
            row = _registry_rows().get(new) or {}
            ctx.check(f"the new row follows the old id, got {row}", row.get("follows") == old)
            pub = registry.public_entry(row)
            ctx.check(f"`follows` and `first_words` are public, got {pub}",
                      pub.get("follows") == old and pub.get("first_words") == "" and "token" not in pub)
        finally:
            runtime.stop_one(act)


@test
def test_first_words_in_the_registry_row(ctx: Ctx):
    from halo_harness.headless_session import HeadlessHandle
    from halo_harness.remote import registry, runtime
    from halo_harness.remote.print_handle import PrintModeHandle
    from tests.helpers.fake_remote_session import FakeLog, FakeSession
    ctx.check("six words, single spaces, at most 60 characters",
              registry.first_words("  fix   the\nflaky login test on windows please ") == "fix the flaky login test on"
              and len(registry.first_words("x" * 200)) == 60 and registry.first_words("") == "")
    text = "please fix the flaky login test on windows today"
    with Rig(serve=False, start_controller=False) as rig:
        acts = []
        try:
            resumed = FakeSession("resumedsession0000000000000000003")
            resumed.log.add("user", "carry on with the   index work from yesterday")
            kinds = (("terminal", lambda: runtime._open(rig.handle, rig.controller)),
                     ("Studio-started", lambda: runtime._open(HeadlessHandle(rig.controller, threading.Event()),
                                                              rig.controller)),
                     ("print", lambda: runtime._open(PrintModeHandle(FakeSession("printsession00000000000000000004"),
                                                                     rig.cwd), kind="print")),
                     ("resumed", lambda: runtime._open(PrintModeHandle(resumed, rig.cwd), kind="print")))
            for label, opener in kinds:
                if label == "Studio-started":
                    runtime.stop_one(acts[0])  # one handle per session: the terminal's first
                act = opener()
                acts.append(act)
                ctx.check(f"{label}: opened", act is not None)
                if label == "resumed":
                    ctx.check(f"resumed: read from the log at register, got {_registry_rows()[act.session_id]}",
                              _registry_rows()[act.session_id].get("first_words") == "carry on with the index work")
                    continue
                ctx.check(f"{label}: none until the first message",
                          _registry_rows()[act.session_id].get("first_words") == "")
                act.handle.hub.publish(ev.Event("user_message", {"text": "a sub-agent's task text"}, turn=1,
                                                agent_id="sub1"))
                act.handle.hub.publish(ev.Event("user_message", {"text": text}, turn=1))
                act.handle.hub.publish(ev.Event("user_message", {"text": "a second message later"}, turn=2))
                got = _wait(lambda: _registry_rows()[act.session_id].get("first_words"), 5)
                ctx.check(f"{label}: the first main message's words, got {got!r}", got == "please fix the flaky login test")
                time.sleep(0.2)
                ctx.check(f"{label}: a later message changes nothing",
                          _registry_rows()[act.session_id].get("first_words") == "please fix the flaky login test")
            act = acts[1]
            new = "clearedsession00000000000000000005"
            rig.session.log = FakeLog(new)
            act.handle.hub.publish(ev.Event("status", {"session_id": new, "permission_mode": "default"}))
            ctx.check("after /clear the new row", _wait(lambda: new in _registry_rows(), 5))
            ctx.check(f"a row made by /clear starts with none, got {_registry_rows().get(new)}",
                      _registry_rows()[new].get("first_words") == "")
        finally:
            for act in acts:
                runtime.stop_one(act)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
