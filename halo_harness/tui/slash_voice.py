"""halo_harness.tui.slash_voice -- `/voice on | off | ptt | status` in the TUI and Ctrl+Space (Halo 3.3.9.0 R2; docs/
VOICE.md "Voice in a session").

The command runs in voice/session.py (the same code the control socket reaches) on a worker thread: turning voice on
may start the speech servers (seconds; their cost line is said first, as a `voice` note event). Its lines land as
one transcript note. `voice.ptt_key` binds another push-to-talk key than Ctrl+Space when voice turns on.
"""

from __future__ import annotations

_BOUND: set = set()


def _bind_ptt(app) -> None:
    from halo_harness.voice.session import ptt_key
    key = ptt_key()
    if key in ("ctrl+space", "ctrl+@") or key in _BOUND:
        return
    try:
        app.bind(key, "voice_ptt", description="Talk", show=False)
        _BOUND.add(key)
    except Exception:
        pass


def _work(app, args: str) -> None:
    from halo_harness.voice.session import slash
    try:
        text = slash(app.controller, args)
    except Exception as e:  # one line, the session goes on
        text = f"/voice failed: {type(e).__name__}: {e}"
    if text:
        app.call_from_thread(app.transcript.add_note, text, kind="command")


async def handle_voice(app, args: str) -> None:
    sub = ((args or "").split() or ["status"])[0].lower()
    if sub in ("on", "ptt", "hands-free"):
        _bind_ptt(app)
    app.run_worker(lambda: _work(app, args or ""), thread=True, name="voice", group="voice", exit_on_error=False)


def press(app) -> None:
    from halo_harness.voice.session import ptt
    try:
        text = ptt(app.controller)
    except Exception as e:
        text = f"push-to-talk failed: {type(e).__name__}: {e}"
    try:
        app.status_bar.set_notice(text, 10)
    except Exception:
        pass
