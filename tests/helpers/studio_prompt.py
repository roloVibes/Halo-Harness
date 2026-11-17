"""tests.helpers.studio_prompt -- Session's Prompt panel (Halo 3.3.11.0 R1) through real keys and clicks in
headless Chrome on the driver base (tests/helpers/chrome_driver.Driver), over tests/helpers/prompt_rig.py (a
scripted fake session on its real control socket behind the real Controller, an in-process Studio).
tests/test_studio_prompt.py runs it as a subprocess:

    python -m tests.helpers.studio_prompt prompt   `?prompt=1` opens Session with the keyboard in the Prompt box;
                                                   a turn typed there shows its reply (no "from Studio" word), its
                                                   receipt's marks reaching replied; `/eff` + Tab completes from
                                                   the slash list and `/effort high` prints the session's lines;
                                                   a permission ask answered from the panel's card; a send while
                                                   busy refused -> Queue it -> the queued turn runs when the
                                                   running turn ends, its marks reaching replied

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

P = "document.querySelector('[data-testid=\"prompt-detail\"]')"
INPUT = "document.querySelector('[data-testid=\"prompt-input\"]')"
TURNS = "[...document.querySelectorAll('[data-testid=\"prompt-turn\"]')]"
ASKS = "[...document.querySelectorAll('[data-testid=\"prompt-ask\"]')]"


def press(c, key: str, code: str, vk: int, mods: int = 0, commands: "list | None" = None) -> None:
    """One key with modifiers (1 Alt, 2 Ctrl, 8 Shift), as the keyboard sends it; `commands`: the editing commands the
    key down carries (what macOS's key bindings would add)."""
    for kind in ("rawKeyDown", "keyUp"):
        extra = {"commands": commands} if commands and kind == "rawKeyDown" else {}
        c.call("Input.dispatchKeyEvent", type=kind, key=key, code=code, windowsVirtualKeyCode=vk, modifiers=mods, **extra)


def enter(c) -> None:
    press(c, "Enter", "Enter", 13)


def typed(c, text: str) -> None:
    """The box focused, then `text` typed into it."""
    c.click_on(INPUT)
    c.type_text(text)


def turn_of(text: str) -> str:
    return f"{TURNS}.find((t) => t.textContent.includes({text!r}))"


def opened(c, rig) -> dict:
    import os

    from tests.helpers.studio_ui_order import PAGE_PLATFORM_ENV
    if os.environ.get(PAGE_PLATFORM_ENV):  # fx jb9: the page believes it runs on that system (e.g. MacIntel)
        c.call("Emulation.setUserAgentOverride", userAgent=c.js("navigator.userAgent"), platform=os.environ[PAGE_PLATFORM_ENV])
    c.go(rig.url(f"&session={rig.sid}&prompt=1"))
    c.wait(f"!!{P} && {P}.dataset.session === {rig.sid!r} && 'ok'", 40)
    focused = c.wait(f"document.activeElement === {INPUT} && 'focused'", 10)
    return {"opened": True, "focused": focused, "panel_to": c.js("document.querySelector('[data-testid=\"prompt-to\"]')?.textContent"),
            "page_platform": c.js("navigator.platform || ''")}


def keeps_the_keyboard(c, rig) -> dict:
    """fx jb4: the Prompt opened again while a person types in its box (a new session's own late openPrompt, once the
    event bridge listens; Alt+Enter) leaves the keyboard in the box: the panel took it, so a typed turn or its Enter
    went nowhere (realcheck studio, Windows installed leg, run 43788371968: the question never reached the model)."""
    import time
    c.click_on(INPUT)
    c.js(f"(() => {{ window.__ppLost = 0; {INPUT}.addEventListener('focusout', () => {{ window.__ppLost++; }}); return 1; }})()")
    press(c, "Enter", "Enter", 13, 1)  # Alt+Enter: openPrompt, the call NewSession.focusWhenListed makes
    c.type_text("kept")
    time.sleep(1.2)  # past the composer's own refocus timers (0..1000 ms)
    out = {"lost_focus": c.js("window.__ppLost"), "kept_text": c.js(f"{INPUT}.value"),
           "still_in_box": c.js(f"document.activeElement === {INPUT}")}
    empty_box(c)  # the box empty again for the next step
    out["emptied"] = c.wait(f"{INPUT}.value === '' && 'empty'", 5)
    return out


def empty_box(c) -> None:
    """fx jb9: the box's text selected through the DOM, then Backspace with its editing command (macOS's Chrome runs
    no editing for a synthetic key without one): the same on Windows, macOS and Linux. Ctrl+A is select-all only on
    Windows and Linux."""
    c.js(f"{INPUT}.select(); 1")
    press(c, "Backspace", "Backspace", 8, commands=["deleteBackward"])


NO_SELECT_ALL = ("(() => { window.__noSelectAll = (e) => { if ((e.ctrlKey || e.metaKey) && (e.key || '').toLowerCase() === 'a') "
                 "e.preventDefault(); }; window.addEventListener('keydown', window.__noSelectAll, true); return 1; })()")


def empties_on_any_keyboard(c, rig) -> dict:
    """fx jb9: the box empties where Ctrl+A is no select-all (macOS: Ctrl+A moves the caret to the line's start, and a
    synthetic Cmd+A carries no editing command), so the step after never starts on a box that still holds text (macOS
    CI run 43802574156: 'waited 5s for ... value === ""'). The chord's default is stopped here, as a Mac's Chrome
    never runs it."""
    c.click_on(INPUT)
    c.type_text("on a mac")
    c.js(NO_SELECT_ALL)
    try:
        empty_box(c)
        try:
            emptied = c.wait(f"{INPUT}.value === '' && 'empty'", 5)
        except TimeoutError:
            emptied = None
        out = {"any_keyboard_emptied": emptied, "any_keyboard_left": c.js(f"{INPUT}.value"),
               "any_keyboard_in_box": c.js(f"document.activeElement === {INPUT}")}
    finally:
        c.js("window.removeEventListener('keydown', window.__noSelectAll, true); 1")
    if out["any_keyboard_emptied"] is None:  # the next steps start on an empty box either way
        c.js(f"{INPUT}.select(); 1")
        press(c, "Delete", "Delete", 46)
    return out


def a_turn(c, rig) -> dict:
    typed(c, "hello from the panel")
    enter(c)
    t = turn_of("hello from the panel")
    out = {"turn_via": c.wait(f"{t}?.dataset.via", 15), "turn_chip": c.js(f"{t}?.querySelector('[data-testid=\"prompt-via\"]')?.textContent")}
    out["reply"] = c.wait("[...document.querySelectorAll('[data-testid=\"prompt-text\"]')].map((x) => x.textContent).join(' ').includes('fake session') && 'reply'", 15)
    out["turn_marks"] = c.wait(f"{t}?.dataset.receiptState === 'replied' && 'replied'", 20)
    out["turn_lit"] = c.js(f"{t}.querySelectorAll('.spp-mark[data-on]').length")
    out["turn_title"] = c.js(f"{t}.querySelector('[data-testid=\"prompt-receipt\"]').title")
    out["cleared"] = c.js(f"{INPUT}.value === ''")
    out["users_after_turn"] = rig.users()
    return out


def a_slash(c, rig) -> dict:
    typed(c, "/eff")
    out = {"slash_list": c.wait("[...document.querySelectorAll('[data-testid=\"prompt-slash-item\"]')].map((i) => i.dataset.name)", 10)}
    press(c, "Tab", "Tab", 9)
    out["completed"] = c.wait(f"{INPUT}.value === '/effort ' && {INPUT}.value", 5)
    c.type_text("high")
    enter(c)
    out["slash_lines"] = c.wait("[...document.querySelectorAll('[data-testid=\"prompt-slash-lines\"]')].map((x) => x.textContent).find((t) => t.includes('ran /effort high'))", 15)
    out["slash_not_a_turn"] = len(rig.users()) == 1
    return out


def an_ask(c, rig) -> dict:
    typed(c, "please ask now")
    enter(c)
    card = f"{ASKS}.filter((a) => !a.dataset.answered).pop()"
    out = {"ask_buttons": c.wait(f"{card} && [...{card}.querySelectorAll('[data-testid=\"prompt-ask-btn\"]')].map((b) => b.dataset.label)", 15)}
    c.click_on(f"[...{card}.querySelectorAll('[data-testid=\"prompt-ask-btn\"]')].find((b) => b.dataset.label === 'Allow')")
    out["ask_done"] = c.wait(f"{ASKS}.map((a) => a.querySelector('[data-testid=\"prompt-ask-done\"]')?.textContent).find(Boolean)", 10)
    from tests.helpers.session_rig import wait_for
    got = wait_for(lambda: rig.session.permission_decisions.get("perm_1"), 10)
    out["ask_decision"] = getattr(got, "action", None)
    out["ask_turn_ended"] = bool(wait_for(lambda: not rig.session.busy and rig.session.turn_count == 2, 10))
    # 3.6.0.2 P23: wait until the session's own `ask_answered` (where studio) has reached the card (data-heard)
    out["ask_heard"] = c.wait(f"{ASKS}.filter((a) => a.dataset.answered).pop()?.dataset.heard && 'heard'", 15)
    out["ask_done_lines"] = c.js(f"[...{ASKS}.filter((a) => a.dataset.answered).pop().querySelectorAll('[data-testid=\"prompt-ask-done\"]')]"
                                 ".map((x) => x.textContent)")
    return out


def busy_then_queue(c, rig) -> dict:
    typed(c, "please ask again")
    enter(c)
    from tests.helpers.session_rig import wait_for
    card = f"{ASKS}.filter((a) => !a.dataset.answered).pop()"
    c.wait(f"!!{card} && 'card'", 15)
    out = {"busy_session": bool(wait_for(lambda: rig.session.busy, 5))}
    typed(c, "queued turn text")
    enter(c)
    out["busy_line"] = c.wait("document.querySelector('[data-testid=\"prompt-busy\"]')?.textContent", 10)
    out["busy_kept_text"] = c.js(f"{INPUT}.value")
    c.click_on("document.querySelector('[data-testid=\"prompt-queue\"]')")
    out["busy_gone"] = c.wait("!document.querySelector('[data-testid=\"prompt-busy\"]') && 'gone'", 10)
    out["not_steered"] = rig.session.steered == []
    out["held"] = rig.controller.prompt_queue.held is not None
    c.click_on(f"[...{card}.querySelectorAll('[data-testid=\"prompt-ask-btn\"]')].find((b) => b.dataset.label === 'Allow')")
    t = turn_of("queued turn text")
    out["queued_via"] = c.wait(f"{t}?.dataset.via", 20)
    out["queued_marks"] = c.wait(f"{t}?.dataset.receiptState === 'replied' && 'replied'", 20)
    wait_for(lambda: rig.session.turn_count == 4 and not rig.session.busy, 10)
    out["users"] = rig.users()
    out["receipt_states"] = [(r["kind"], r["state"]) for r in rig.receipts()]
    return out


class PromptDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.prompt_rig import PromptRig
        with PromptRig() as rig:
            yield ((opened, (c, rig)), (keeps_the_keyboard, (c, rig)), (empties_on_any_keyboard, (c, rig)), (a_turn, (c, rig)), (a_slash, (c, rig)), (an_ask, (c, rig)), (busy_then_queue, (c, rig)))


if __name__ == "__main__":
    sys.exit(PromptDriver(sys.argv[1:]).main())
