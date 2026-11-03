"""tests.helpers.studio_headless -- a session with no terminal from Studio (Halo 3.3.11.0 R2) through real clicks
and keys in headless Chrome on the driver base (tests/helpers/chrome_driver.Driver), over tests/helpers/
headless_rig.py: an in-process Studio whose own launcher spawns `halo --headless --session-for studio` on the
fake upstream (no model call). tests/test_studio_headless.py runs it as a subprocess:

    python -m tests.helpers.studio_headless headless   the Session section's Start view -> New session (the default
                                                       model, Studio's folder) -> Session opens on it with the Prompt
                                                       focused; the header says "no terminal"; a turn typed there
                                                       gets the reply; an ask (a Write) answered from the panel's
                                                       card; End session -> the child ends and leaves the registry

The last stdout line is a JSON object of what it saw (exit 2: no Chrome). Every child is ended by the rig."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

P = "document.querySelector('[data-testid=\"prompt-detail\"]')"
INPUT = "document.querySelector('[data-testid=\"prompt-input\"]')"
ASKS = "[...document.querySelectorAll('[data-testid=\"prompt-ask\"]')]"
TEXTS = "[...document.querySelectorAll('[data-testid=\"prompt-text\"]')].map((x) => x.textContent).join(' ')"


def enter(c) -> None:
    for kind in ("rawKeyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key="Enter", code="Enter", windowsVirtualKeyCode=13, modifiers=0)


def typed(c, text: str) -> None:
    c.click_on(INPUT)
    c.type_text(text)
    enter(c)


def url(server) -> str:
    from halo_harness.studio.server import url_for
    return url_for(server, "session").replace("#t=", "&tour=off#t=")


def start_one(c, rig, server) -> dict:
    from halo_harness.theme import set_config_value
    from tests.helpers.headless_rig import MODEL
    set_config_value("model", MODEL)  # the default the form's picker starts on
    c.go(url(server))
    c.wait("!!document.querySelector('[data-testid=\"session-start\"] [data-testid=\"session-new-start\"]') && "
           "!document.querySelector('[data-testid=\"session-new-start\"]').disabled && 'form'", 40)
    out = {"default_option": c.js("document.querySelector('[data-testid=\"session-new-model\"]').options[0].textContent"),
           "cwd_placeholder": c.js("document.querySelector('[data-testid=\"session-new-cwd\"]').placeholder")}
    c.click_on("document.querySelector('[data-testid=\"session-new-start\"]')")
    out["sid"] = sid = c.wait(f"{P}?.dataset.session", 60)
    from tests.helpers.fleet_rig import wait_for
    row = wait_for(lambda: next((r for r in rig.api(server, "GET", "sessions/started")[1].get("sessions") or [] if r["session_id"] == sid), None), 20)
    if row:
        rig.pids.append(row["pid"])
    out["focused"] = c.wait(f"document.activeElement === {INPUT} && 'focused'", 15)
    out["noterm"] = c.wait("document.querySelector('[data-testid=\"prompt-noterm\"]')?.textContent", 20)
    out["registered"] = (rig.entry(sid, 30) or {}).get("kind")
    return out


def a_turn(c, rig, server) -> dict:
    typed(c, "hello with no terminal")
    try:
        reply = c.wait(f"{TEXTS}.includes('pong from headless') && 'reply'", 90)  # the Linux runner's child is slow to start
    except TimeoutError as e:
        # Linux shard 1 of run 41697734325: no reply in 40 s and nothing to say why. Say where the turn stalled: the
        # receipts' ladder (sent / delivered / read / replied), the child's status over its socket, its log tail.
        sid = c.js(f"{P}?.dataset.session") or ""
        try:
            receipts = rig.api(server, "GET", f"sessions/{sid}/receipts")[1]
        except Exception as x:  # the route itself failing is part of the picture
            receipts = {"error": f"{type(x).__name__}: {x}"}
        try:
            entry = rig.entry(sid, 5)
            status = rig.client(entry).call("status")["result"] if entry else "no registry row"
        except Exception as x:
            status = f"{type(x).__name__}: {x}"
        raise TimeoutError(f"{e}; receipts: {receipts}; child status: {status}; child log tail: {rig.child_log()[-600:]!r}") from None
    return {"reply": reply}


def an_ask(c, rig, server) -> dict:
    typed(c, "please ask for a file")
    card = f"{ASKS}.filter((a) => !a.dataset.answered).pop()"
    out = {"ask_buttons": c.wait(f"{card} && [...{card}.querySelectorAll('[data-testid=\"prompt-ask-btn\"]')].map((b) => b.dataset.label)", 40)}
    c.click_on(f"[...{card}.querySelectorAll('[data-testid=\"prompt-ask-btn\"]')].find((b) => b.dataset.label === 'Allow')")
    out["ask_done"] = c.wait(f"{ASKS}.map((a) => a.querySelector('[data-testid=\"prompt-ask-done\"]')?.textContent).find(Boolean)", 15)
    out["made"] = c.wait(f"{TEXTS}.includes('made it') && 'made'", 40)
    from tests.helpers.fleet_rig import wait_for
    out["file"] = bool(wait_for(lambda: (rig.proj / "headless-made.txt").is_file(), 15))
    return out


def end_it(c, rig, server) -> dict:
    from tests.helpers.fleet_rig import wait_for
    sid = c.js(f"{P}?.dataset.session")
    c.wait(f"{P}?.dataset.busy === undefined && 'idle'", 30)
    c.click_on("document.querySelector('[data-testid=\"prompt-end\"]')")
    c.click_on("document.querySelector('[data-testid=\"prompt-end-yes\"]')")
    gone = wait_for(lambda: not any(r.get("session_id") == sid for r in rig.rows()) and "gone", 60)
    # the registry row goes before the process is fully gone (Windows shard 1, run 41707642102: pid still alive at the
    # read): wait for the exit, then say what survived
    wait_for(lambda: not rig.survivors() and "none", 30)
    alive = rig.survivors()
    return {"ended": gone, "survivors": alive}


class HeadlessDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.headless_rig import HeadlessRig
        with HeadlessRig() as rig:
            rig.spawn_env()
            rig.asking_mode()
            server = rig.studio()
            args = (c, rig, server)
            yield ((start_one, args), (a_turn, args), (an_ask, args), (end_it, args))


if __name__ == "__main__":
    sys.exit(HeadlessDriver(sys.argv[1:]).main())
