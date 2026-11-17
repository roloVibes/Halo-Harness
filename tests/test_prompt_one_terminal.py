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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
