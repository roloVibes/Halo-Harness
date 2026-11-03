"""tests.helpers.studio_prompt -- Session's Prompt panel (Halo 3.3.11.0 R1) through real keys and clicks in
headless Chrome on the driver base (tests/helpers/chrome_driver.Driver), over tests/helpers/prompt_rig.py (a
scripted fake session on its real control socket behind the real Controller, an in-process Studio).
tests/test_studio_prompt.py runs it as a subprocess:

    python -m tests.helpers.studio_prompt prompt   `?prompt=1` opens Session with the keyboard in the Prompt box;
                                                   a turn typed there shows "from Studio" and its reply, its
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


def press(c, key: str, code: str, vk: int, mods: int = 0) -> None:
    """One key with modifiers (1 Alt, 2 Ctrl, 8 Shift), as the keyboard sends it."""
    for kind in ("rawKeyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key=key, code=code, windowsVirtualKeyCode=vk, modifiers=mods)


def enter(c) -> None:
    press(c, "Enter", "Enter", 13)


def typed(c, text: str) -> None:
    """The box focused, then `text` typed into it."""
    c.click_on(INPUT)
    c.type_text(text)


def turn_of(text: str) -> str:
    return f"{TURNS}.find((t) => t.textContent.includes({text!r}))"


def opened(c, rig) -> dict:
    c.go(rig.url(f"&session={rig.sid}&prompt=1"))
    c.wait(f"!!{P} && {P}.dataset.session === {rig.sid!r} && 'ok'", 40)
    focused = c.wait(f"document.activeElement === {INPUT} && 'focused'", 10)
    return {"opened": True, "focused": focused, "panel_to": c.js("document.querySelector('[data-testid=\"prompt-to\"]')?.textContent")}


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
    from tests.helpers.fleet_rig import wait_for
    got = wait_for(lambda: rig.session.permission_decisions.get("perm_1"), 10)
    out["ask_decision"] = getattr(got, "action", None)
    out["ask_turn_ended"] = bool(wait_for(lambda: not rig.session.busy and rig.session.turn_count == 2, 10))
    return out


def busy_then_queue(c, rig) -> dict:
    typed(c, "please ask again")
    enter(c)
    from tests.helpers.fleet_rig import wait_for
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
            yield ((opened, (c, rig)), (a_turn, (c, rig)), (a_slash, (c, rig)), (an_ask, (c, rig)), (busy_then_queue, (c, rig)))


if __name__ == "__main__":
    sys.exit(PromptDriver(sys.argv[1:]).main())
