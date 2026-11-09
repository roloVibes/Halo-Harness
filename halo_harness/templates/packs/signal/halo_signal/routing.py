"""halo_signal.routing -- what the phone's text means. `route(b, rt, text, media)` returns `(kind, outcome)` for the
audit line (never the text).

Order: `send` after a held text (answers.held_line) submits it; an open card's answer; a held line when a card that
takes only its own answers is open; a `/command` of the bridge (chat.py), else any other `/x` runs in the session as
its slash command; plain text is the prompt (a steer while a turn runs). A prompt with no session attached starts one
in the phone's home folder (session.ensure) and waits for it; a file or a voice note the phone sent rides with it
(media.py).
"""

from __future__ import annotations

from halo_signal import answers, chat, media
from halo_signal.session import call, ensure, one_line


def _fail(b, aci: str, resp: dict) -> str:
    b.say(aci, "Error: " + one_line(resp.get("error"), 400))
    return "error"


def route(b, rt, text: str, files=None) -> tuple:
    t = (text or "").strip()
    if rt.held is not None:
        held, rt.held = rt.held, None
        if t.lower() == "send":
            return prompt(b, rt, held)
    if not t and not files:
        return "empty", "ignored"
    if t and not t.startswith("/") and not files:
        done = answers.answer_open_card(b, rt, t)
        if done:
            return "answer", done
        line = answers.held_line(rt, t)
        if line:
            b.say(rt.aci, line)
            return "held", "asked"
    if t.startswith("/") and files:  # 3.3.14.0 R2 (REVIEW #20): a command takes no file; it is not kept
        for f in files:
            media._drop(f.get("path", ""))
        b.say(rt.aci, "A file sent with a /command is not kept: send it on its own.")
        files = []
    if t.startswith("/"):
        name, _, args = t[1:].partition(" ")
        handler = chat.HANDLERS.get(name.lower())
        if handler is not None:
            return f"cmd:{name.lower()}", handler(b, rt, args.strip()) or "ok"
        if rt.client is None:
            b.say(rt.aci, f"No session is attached for {t.split()[0]}: send a text to start one, or /sessions.")
            return "slash", "no_session"
        resp = call(b, rt, "slash", line=t)
        if not resp.get("ok"):
            return "slash", _fail(b, rt.aci, resp)
        b.say(rt.aci, (resp["result"].get("output") or "").strip() or f"Ran {t.split()[0]}.", markdown=True)
        return "slash", "ok"
    if files:
        t, image, why = media.inbound(b, rt, t, files)
        if why:
            b.say(rt.aci, why)
        if not t and image is None:
            return "file", "dropped"
        return prompt(b, rt, t, image)
    return prompt(b, rt, t)


def prompt(b, rt, text: str, image=None) -> tuple:
    state = ensure(b, rt)
    if state == "starting":
        rt.waiting.append({"text": text, "image": image})
        return "prompt", "waiting"
    return submit(b, rt, text, image)


def submit(b, rt, text: str, image=None) -> tuple:
    fields = {"text": text or "(see the attached image)", "origin": {"via": "signal", "by": rt.aci[:8]}}
    if image is not None:
        fields["image"] = image
    resp = call(b, rt, "submit", **fields)
    if not resp.get("ok"):
        return "prompt", _fail(b, rt.aci, resp)
    b.transport.typing.start(rt.aci)
    return "prompt", "steered" if (resp.get("result") or {}).get("steered") else "ok"


def started(b, rt, row, line: str) -> None:
    """The session a text asked for is up (or not): attach it and send what waited."""
    from halo_signal.session import attach
    rt.starting = False
    waiting, rt.waiting = rt.waiting, []
    err = attach(b, rt, row) if row else (line or "it did not start")
    if err:
        b.say(rt.aci, f"The session did not start: {one_line(err, 300)}")
        return
    for item in waiting:
        kind, outcome = submit(b, rt, item["text"], item.get("image"))
        b.audit.record(rt.aci, 0, item["text"], kind, outcome)
