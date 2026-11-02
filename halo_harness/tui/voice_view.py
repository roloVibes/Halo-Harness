"""halo_harness.tui.voice_view -- the TUI's drawing of the voice loop's `voice` events (Halo 3.3.9.0 R2; voice/loop.py):

    on / idle      the status bar's mic chip: "mic" (hands-free) or "mic ptt"     off: the chip goes
    listening      "mic: listening"            speaking: "mic: speaking"
    partial        the partial transcript in the status bar while the person still speaks ("you: ...")
    heard          the prompt echo in the transcript: "you said: ..." (a steer says it steers the running turn)
    interrupted    "(interrupted while speaking)" in the transcript
    card           the latency card, one status-bar line after each turn
    note           one transcript line (a cost line, a missing piece with its command)
"""

from __future__ import annotations

CHIPS = {"hands-free": "mic", "ptt": "mic ptt"}


def chip(app, state: str) -> "str | None":
    mode = getattr(app, "_voice_mode", "hands-free")
    base = CHIPS.get(mode, "mic")
    if state == "listening":
        return f"{base}: listening"
    if state == "speaking":
        return f"{base}: speaking"
    return base


def heard_line(text: str, steer: bool) -> str:
    return f"you said: {text}" + (" (steers the running turn)" if steer else "")


async def apply(app, data: dict) -> None:
    state = str(data.get("state") or "")
    bar = getattr(app, "status_bar", None)
    if state == "on":
        app._voice_mode = data.get("mode") or "hands-free"
    if state in ("on", "idle", "listening", "speaking") and bar is not None:
        bar.set_voice(chip(app, state))
    elif state == "off" and bar is not None:
        bar.set_voice(None)
    elif state == "partial" and bar is not None:
        bar.set_notice(f"you: {data.get('text') or ''} ...", 10)
    elif state == "card" and bar is not None:
        bar.set_notice(str(data.get("text") or ""), 30)
    if state == "heard":
        if bar is not None:
            bar.set_notice(None)
        await app.transcript.add_note(heard_line(str(data.get("text") or ""), bool(data.get("steer"))), kind="note")
    elif state in ("interrupted", "note") and data.get("text"):
        await app.transcript.add_note(str(data["text"]), kind="note" if state == "interrupted" else "command")
