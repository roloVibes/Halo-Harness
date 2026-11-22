"""tests.helpers.studio_prompt_one -- 3.6.0.2 P6 ("one prompt", the design's F2) on Session's Prompt panel through
real keys and clicks in headless Chrome, over tests/helpers/prompt_rig.py (the scripted fake session behind the real
Controller and its real control socket, an in-process Studio). tests/test_studio_prompt.py runs it as a subprocess:

    python -m tests.helpers.studio_prompt_one one

The answer to a send is held on Studio's server (`sessions_prompt_api.after`, after the session already took it) while
keys are typed, then let go: P72 (the answer never wipes what was typed after Enter), P24 (no "from Studio" word), P22
(a steer's one row), P69 (a bare `/model`), P20 (`Interrupted.`), P23 (an ask answered in the terminal or remotely),
3.6.0.12 BS (a one-line `!command` runs in the session: its answer line, one tool row, no turn, its ask's Allow).
The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_prompt import ASKS, INPUT, TURNS, empty_box, enter, opened, press, turn_of, typed  # noqa: E402

SEND = "document.querySelector('[data-testid=\"prompt-send\"]')"
FEED = "document.querySelector('[data-testid=\"prompt-feed\"]')"
OUTS = "[...document.querySelectorAll('[data-testid=\"prompt-slash-out\"]')]"


class Gate:
    """Holds the answer of each send on Studio's server until `release()`; `answer` puts another socket answer in
    place of the session's once (a refusal, a slash that ran nothing); `refuse_next()` makes the next socket call
    fail before it reaches the session."""

    def __init__(self) -> None:
        from halo_harness.studio import sessions_api as S
        from halo_harness.studio import sessions_prompt_api as P
        self.S, self.P, self.real, self.client = S, P, P.after, S._client
        self.open = threading.Event()
        self.open.set()
        self.held = 0
        self.answer = None
        self.slashes = 0
        P.after = self._after
        real_fields = P.fields_for

        def fields_for(cmd, body):
            self.slashes += cmd == "slash"
            return real_fields(cmd, body)
        P.fields_for, self.real_fields = fields_for, real_fields

    def _after(self, p, resp):
        self.held += 1
        self.open.wait(20)
        if self.answer is not None:
            resp, self.answer = self.answer, None
        return self.real(p, resp)

    def hold(self) -> int:
        self.open.clear()
        return self.held

    def release(self) -> None:
        self.open.set()

    def refuse_next(self) -> None:
        def refused(entry, timeout):
            self.S._client = self.client
            raise ConnectionRefusedError("the session's socket refused")
        self.S._client = refused

    def close(self) -> None:
        self.open.set()
        self.P.after, self.P.fields_for, self.S._client = self.real, self.real_fields, self.client


def wait_for(fn, timeout: float = 10.0):
    from tests.helpers.session_rig import wait_for as w
    return w(fn, timeout)


def type_end(c, text: str) -> None:
    """The caret to the end of the box, then `text` typed (never a click in the middle of the text)."""
    c.js(f"(() => {{ const b = {INPUT}; b.focus(); b.setSelectionRange(b.value.length, b.value.length); return 1; }})()")
    c.type_text(text)


def settled(c) -> str:
    """The box once the held answer has been handled: Send is enabled again (the box holds text) or the box is empty."""
    time.sleep(0.3)
    c.wait(f"(!{SEND}.disabled || {INPUT}.value === '') && 'done'", 10)
    time.sleep(0.4)
    return c.js(f"{INPUT}.value")


def in_flight(c, rig, gate, text: str, then) -> dict:
    """`text` + Enter with the answer held; `then(c)` while it is in flight; the box in flight and after the answer."""
    n = gate.hold()
    try:
        typed(c, text) if not c.js(f"{INPUT}.value") else type_end(c, text)
        enter(c)
        wait_for(lambda: gate.held > n, 10)
        then(c)
        during = c.js(f"{INPUT}.value")
    finally:
        gate.release()
    return {"during": during, "after": settled(c)}


def p72(c, rig, gate) -> dict:
    out: dict = {}
    typed(c, "plain send")
    enter(c)
    c.wait(f"!!{turn_of('plain send')} && 'row'", 15)
    out["plain_after"] = c.wait(f"{INPUT}.value === '' && 'empty'", 10)
    out["from_studio_word"] = c.js(f"{FEED}.textContent.includes('from Studio') || !!document.querySelector('[data-testid=\"prompt-via\"]')")
    # 3.6.0.11 (the owner: "The up button should bring you to the start of your prompt"): a long prompt, Up: the text
    # stays and the caret is at 0; Up again: the older prompt ("plain send", just sent: a send starts the walk afresh)
    long = "a long prompt he would rather not scoot through with the left key, word by word"
    typed(c, long)
    c.wait(f"{INPUT}.value.length === {len(long)} && 'typed'", 10)
    press(c, "ArrowUp", "ArrowUp", 38)
    out["up_once"] = c.js(f"[{INPUT}.value.length, {INPUT}.selectionStart, {INPUT}.selectionEnd]")
    press(c, "ArrowUp", "ArrowUp", 38)
    try:
        out["up_twice"] = c.wait(f"{INPUT}.value.length !== {len(long)} && {INPUT}.value", 10)
    except TimeoutError:
        out["up_twice"] = c.js(f"{INPUT}.value")
    empty_box(c)
    out["typed_after"] = in_flight(c, rig, gate, "first part", lambda c: type_end(c, " and more"))
    empty_box(c)
    typed(c, "repeat me")
    enter(c)
    c.wait(f"{INPUT}.value === '' && 'empty'", 10)
    # 3.6.0.11: Up first takes the caret to the prompt's start, the second Up recalls (rewritten to the truth: one Up)
    out["recall_up"] = in_flight(c, rig, gate, "repeat me", lambda c: (press(c, "ArrowUp", "ArrowUp", 38),
                                                                       press(c, "ArrowUp", "ArrowUp", 38)))
    empty_box(c)

    def replace(c):
        c.js(f"{INPUT}.select(); 1")
        c.type_text("base text extended")
    out["replaced_longer"] = in_flight(c, rig, gate, "base text", replace)
    empty_box(c)

    def backspace_at_edge(c):  # the checker's walk: the caret right after the sent text, then Backspace
        type_end(c, "e more")
        c.js(f"(() => {{ const b = {INPUT}; b.focus(); b.setSelectionRange(3, 3); return 1; }})()")
        press(c, "Backspace", "Backspace", 8, commands=["deleteBackward"])
    out["backspace_edge"] = in_flight(c, rig, gate, "see", backspace_at_edge)
    empty_box(c)
    out["slash_typed_after"] = in_flight(c, rig, gate, "/effort low", lambda c: type_end(c, " next"))
    out["slash_ran"] = c.wait(f"{OUTS}.some((o) => o.textContent.includes('ran /effort low')) && 'ran'", 10)
    empty_box(c)
    gate.answer = {"ok": False, "error": "the session refused the command"}
    out["failed"] = in_flight(c, rig, gate, "/effort none", lambda c: type_end(c, " more"))
    empty_box(c)
    gate.answer = {"ok": True, "result": {"output": "The terminal is busy: nothing was run. Press Enter to try again.", "ran": False}}
    out["ran_false"] = in_flight(c, rig, gate, "/effort mid", lambda c: type_end(c, " x"))
    out["ran_false_line"] = c.wait(f"{OUTS}.some((o) => o.textContent.includes('nothing was run')) && 'shown'", 10)
    empty_box(c)
    c.wait(f"{INPUT}.value === '' && 'empty'", 5)
    return {"p72": out}


def steer_rows(c, text: str) -> list:
    return c.js(f"{TURNS}.filter((t) => t.dataset.steer && t.textContent.includes({text!r}))"
                ".map((t) => t.querySelector('[data-testid=\"prompt-steering\"]')?.textContent || '')")


def _steer_drawn(c, text: str) -> None:
    """P8: wait until the row of `text` shows its steering line (the event the old 1.5 s sleeps stood for)."""
    try:
        c.wait(f"{TURNS}.some((t) => t.dataset.steer && t.textContent.includes({text!r}) "
               "&& t.querySelector('[data-testid=\"prompt-steering\"]'))", 10)
    except TimeoutError:
        pass  # the check that follows says what is drawn


def steer(c, rig, gate) -> dict:
    out: dict = {}
    typed(c, "please ask steer")
    enter(c)
    card = f"{ASKS}.filter((a) => !a.dataset.answered).pop()"
    c.wait(f"!!{card} && 'card'", 15)
    wait_for(lambda: rig.session.busy, 5)
    typed(c, "steer this")
    enter(c)
    c.wait("!!document.querySelector('[data-testid=\"prompt-busy\"]') && 'busy'", 10)
    n = gate.hold()
    try:
        c.click_on("document.querySelector('[data-testid=\"prompt-steer\"]')")
        wait_for(lambda: gate.held > n, 10)
        type_end(c, " after")
        out["during"] = c.js(f"{INPUT}.value")
    finally:
        gate.release()
    out["after"] = settled(c)
    # P8: waited on the events, not 1.5 s -- the steer reached the session, and its row with the steering line is drawn
    wait_for(lambda: any("steer this" in str(x) for x in rig.session.steered), 10)
    _steer_drawn(c, "steer this")
    out["rows"] = steer_rows(c, "steer this")
    out["steered"] = list(rig.session.steered)
    empty_box(c)
    typed(c, "steer two")
    enter(c)
    c.wait("!!document.querySelector('[data-testid=\"prompt-busy\"]') && 'busy'", 10)
    gate.refuse_next()
    c.click_on("document.querySelector('[data-testid=\"prompt-steer\"]')")
    # P8: the refusal happened (the gate put the socket back) and the page has its answer (the box settled)
    wait_for(lambda: gate.S._client is gate.client, 10)
    settled(c)
    out["refused_rows"] = steer_rows(c, "steer two")
    out["refused_box"] = c.js(f"{INPUT}.value")
    c.click_on("document.querySelector('[data-testid=\"prompt-steer\"]')")
    c.wait(f"{INPUT}.value === '' && 'empty'", 10)
    wait_for(lambda: any("steer two" in str(x) for x in rig.session.steered), 10)
    _steer_drawn(c, "steer two")
    out["again_rows"] = steer_rows(c, "steer two")
    out["steered_end"] = list(rig.session.steered)
    # the checker's walk: the busy line holds 'alpha'; ' beta' typed after it, then an Enter whose send fails; Steer
    # then sends 'alpha' only, and the answer must not take out ' beta', which was never sent
    typed(c, "alpha")
    enter(c)
    c.wait("!!document.querySelector('[data-testid=\"prompt-busy\"]') && 'busy'", 10)
    type_end(c, " beta")
    gate.refuse_next()
    enter(c)
    wait_for(lambda: gate.S._client is gate.client, 10)
    time.sleep(0.5)
    out["drift_during"] = c.js(f"{INPUT}.value")
    c.click_on("document.querySelector('[data-testid=\"prompt-steer\"]')")
    wait_for(lambda: len(rig.session.steered) > len(out["steered_end"]), 10)
    out["drift_after"] = settled(c)
    out["drift_steered"] = list(rig.session.steered)[len(out["steered_end"]):]
    empty_box(c)
    c.click_on(f"[...{card}.querySelectorAll('[data-testid=\"prompt-ask-btn\"]')].find((b) => b.dataset.label === 'Allow')")
    wait_for(lambda: not rig.session.busy, 10)
    return {"steer": out}


def bare_model(c, rig, gate) -> dict:
    outs, slashes = c.js(f"{OUTS}.length"), gate.slashes
    typed(c, "/model")
    enter(c)
    out = {"picker": c.wait("!!document.querySelector('[data-testid=\"prompt-model-picker\"]') && 'open'", 10)}
    time.sleep(0.8)
    out.update(box=c.js(f"{INPUT}.value"), new_outs=c.js(f"{OUTS}.length") - outs, slash_requests=gate.slashes - slashes)
    press(c, "Escape", "Escape", 27)
    empty_box(c)
    return {"model": out}


def interrupted(c, rig, gate) -> dict:
    from halo_harness import events
    notes = "[...document.querySelectorAll('[data-testid=\"prompt-note\"]')].map((n) => n.textContent)"
    rig.controller.events.put(events.turn_done(turn=rig.session.turn_count, reason="interrupted"))  # Studio's Stop
    first = c.wait(f"{notes}.length === 1 && {notes}", 10)
    rig.controller.events.put(events.turn_done(turn=rig.session.turn_count, reason="interrupted"))  # the terminal's Esc
    second = c.wait(f"{notes}.length === 2 && {notes}", 10)
    rig.controller.events.put(events.turn_done(turn=rig.session.turn_count, reason="end_turn"))
    time.sleep(0.8)
    return {"interrupted": {"first": first, "second": second, "after_end_turn": c.js(f"{notes}.length")}}


def answered_elsewhere(c, rig, gate) -> dict:
    from halo_harness import events
    out: dict = {}
    for text, where in (("please ask term", "terminal"), ("please ask phone", "remote")):
        typed(c, text)
        enter(c)
        card = f"{ASKS}.filter((a) => !a.dataset.answered).pop()"
        c.wait(f"!!{card} && 'card'", 15)
        c.js(f"(window.__ppCard = {card}) && 1")
        rig.controller.events.put(events.ask_answered("perm_1", "permission", "Allow", where))
        rig.session.resolve_permission("perm_1", SimpleNamespace(action="allow", scope="once", message="", rule=None))
        done = c.wait("window.__ppCard.dataset.answered && [...window.__ppCard.querySelectorAll('[data-testid=\"prompt-ask-done\"]')]"
                      ".map((x) => x.textContent)", 10)
        out[where] = {"lines": done, "buttons": c.js("window.__ppCard.querySelectorAll('[data-testid=\"prompt-ask-btn\"]').length")}
        wait_for(lambda: not rig.session.busy, 10)
    return {"elsewhere": out}


def bang(c, rig, gate) -> dict:
    """3.6.0.12 BS: `!echo BANG-ONE` + Enter runs in the session through the slash door: the line once with its answer
    line, one tool row on the session's stream (the Feed's and this panel's), no turn; an asking `!` shows the panel's
    own ask card, and its Allow runs the command. The fake session's engine allows `echo` and asks for the rest."""
    from halo_harness.permissions import Decision
    eng, had = rig.session.permission_engine, rig.session.permission_engine.__dict__.get("decide")
    eng.decide = lambda name, inp, tool=None: Decision(
        "allow" if str((inp or {}).get("command", "")).startswith("echo") else "ask", "asks first")
    sel = lambda q: f"[...document.querySelectorAll('{q}')]"  # noqa: E731
    tools, feed = sel("[data-testid=prompt-line][data-kind=tool]"), sel("[data-testid=session-live-line][data-kind=tool]")
    last = f"{OUTS}.at(-1)?.querySelector('[data-testid=\"prompt-slash-lines\"]')?.textContent"
    out: dict = {}
    try:
        turns, outs, t0, f0 = rig.session.turn_count, c.js(f"{OUTS}.length"), c.js(f"{tools}.length"), c.js(f"{feed}.length")
        typed(c, "!echo BANG-ONE")
        enter(c)
        out["lines"] = c.wait(f"{OUTS}.length > {outs} && ({last} || '').includes('BANG-ONE') && {last}.split('\\n')", 15)
        out["tool_rows"] = c.wait(f"{tools}.length > {t0} && {tools}.length - {t0}", 10)
        time.sleep(1.0)  # a second row or a turn would have landed by now
        out.update(rows_once=c.js(f"{tools}.length - {t0}"), feed_rows=c.js(f"{feed}.length - {f0}"),
                   line_rows=c.js(f"{OUTS}.filter((o) => o.querySelector('.spp-out-cmd').textContent === '!echo BANG-ONE').length"
                                  f" + {TURNS}.filter((t) => t.textContent.includes('!echo BANG-ONE')).length"),
                   tool_text=c.js(f"{tools}.at(-1).textContent"), turns=rig.session.turn_count - turns, box=settled(c))
        typed(c, "!touch bang-asked.txt")
        enter(c)
        out["asked"] = c.wait(f"{OUTS}.length > {outs} + 1 && {last}", 15)
        card = f"{ASKS}.filter((a) => !a.dataset.answered).pop()"
        out["ask_buttons"] = c.wait(f"{card} && [...{card}.querySelectorAll('[data-testid=\"prompt-ask-btn\"]')].map((b) => b.dataset.label)", 15)
        c.click_on(f"[...{card}.querySelectorAll('[data-testid=\"prompt-ask-btn\"]')].find((b) => b.dataset.label === 'Allow')")
        out["ask_ran"] = bool(wait_for(lambda: (rig.cwd / "bang-asked.txt").exists(), 10))
        out["ask_done"] = c.wait(f"{ASKS}.map((a) => a.querySelector('[data-testid=\"prompt-ask-done\"]')?.textContent).filter(Boolean).pop()", 10)
        out["ask_turns"] = rig.session.turn_count - turns
    finally:
        if had is None:
            eng.__dict__.pop("decide", None)
        else:
            eng.decide = had
    return {"bang": out}


class PromptOneDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.prompt_rig import PromptRig
        with PromptRig() as rig:
            gate = Gate()
            try:
                yield ((opened, (c, rig)), (p72, (c, rig, gate)), (steer, (c, rig, gate)), (bare_model, (c, rig, gate)),
                       (interrupted, (c, rig, gate)), (answered_elsewhere, (c, rig, gate)), (bang, (c, rig, gate)))
            finally:
                gate.close()


if __name__ == "__main__":
    sys.exit(PromptOneDriver(sys.argv[1:]).main())
