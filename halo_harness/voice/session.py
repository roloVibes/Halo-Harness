"""halo_harness.voice.session -- voice on a live session: `/voice on | off | ptt | status` (Halo 3.3.9.0 R2; docs/
VOICE.md "Voice in a session", docs/SLASH-COMMANDS-session.md):

    slash(controller, args) -> text   the one entry: the TUI (tui/slash_voice.py), the control socket (`halo voice on`
                                      reaches Controller.run_slash) and Studio's slash box all land here
    on(controller, mode=None, *, audio=None, say=None) -> (ok, lines)
    off(controller) -> lines          stops the loop and the speech servers it started
    ptt(controller) -> text           Ctrl+Space: press to talk, press again to send
    get(controller) -> VoiceLoop | None    status_lines(controller) -> lines

`on` checks in order, each a missing piece said in one line with its command: the extra (sounddevice, the engines --
the install line), a microphone (`halo voice devices`; `halo voice --input-file <wav>` without one), the speech
servers (started with their cost line first: voice/ensure.py), the VAD (silero-vad, else a level gate and its
download line). One loop per session; `voice.mode` (hands-free | ptt) is the default mode.
"""

from __future__ import annotations

import threading
from typing import Optional

_LOOPS: dict = {}
_LOCK = threading.Lock()
MODES = ("hands-free", "ptt")
USAGE = "Usage: /voice [on | off | ptt | status]"


def get(controller):
    return _LOOPS.get(id(controller), (None, None))[0]


def _mode(asked: Optional[str]) -> str:
    if asked in MODES:
        return asked
    from halo_harness.theme import get_config_value
    v = str(get_config_value("voice.mode", default=None) or "hands-free").lower()
    return v if v in MODES else "hands-free"


def ptt_key() -> str:
    from halo_harness.theme import get_config_value
    v = get_config_value("voice.ptt_key", default=None)
    return str(v).strip().lower() if isinstance(v, str) and v.strip() else "ctrl+space"


def _missing(state_dir) -> list:
    from halo_harness.voice import audio, engines
    from halo_harness.voice.ensure import running
    from halo_harness.voice.launch import server_cmd
    gone = list(audio.missing())
    seam = server_cmd()[1]
    from halo_harness.voice.remote import parse, setting  # 3.3.9.0 R3: a server on another halo needs no engine here
    if not seam and not all(running(k, state_dir) or parse(setting(k)) for k in ("stt", "tts")):
        gone += [m for m in engines.missing() if m not in gone]
    return gone


def _note(controller, text: str) -> None:
    from halo_harness.voice.loop import event
    try:
        controller.events.put(event("note", text=text))
    except Exception:
        pass


def _model_line(controller, pk: dict) -> list:
    ref = pk.get("reserved")
    have = str(getattr(getattr(getattr(controller, "session", None), "model_ref", None), "raw", "") or "")
    if not ref or not have or have == ref:
        return []
    return [f"the session answers with {have}; the {pk['bundle']} bundle keeps {ref} resident for voice: /model {ref} "
            "answers from it"]


def _state(controller):
    return getattr(controller, "state_dir", None)


def on(controller, mode: Optional[str] = None, *, audio=None, say=None, mic: bool = True) -> "tuple[bool, list]":
    from halo_harness.voice import INSTALL_LINE
    from halo_harness.voice import audio as A
    from halo_harness.voice.ensure import ensure, picks
    from halo_harness.voice.latency import budget
    from halo_harness.voice.loop import VoiceLoop
    from halo_harness.voice.vad import load
    with _LOCK:
        loop = get(controller)
        if loop is not None:
            if mode in MODES and loop.mode != mode:
                loop.mode = mode
                loop.post("on", mode=mode)
            return True, status_lines(controller)
        state = _state(controller)
        gone = _missing(state) if audio is None else []
        if gone:
            return False, [f"voice needs the voice extra ({', '.join(gone)} missing): {INSTALL_LINE}"]
        if audio is None and mic and A.resolve("input") is None:
            return False, ["no microphone here (halo voice devices lists them): halo voice --input-file <wav> drives "
                           "one turn from a file"]
        said: list = []

        def _say(text: str) -> None:  # the cost line goes out before the servers start, not after
            said.append(text)
            (say or (lambda t: _note(controller, t)))(text)
        urls, started, lines = ensure(state, say=_say)
        lines = [ln for ln in lines if ln not in said]
        if urls is None:
            return False, lines
        vad, vad_line = load()
        if vad_line:
            lines.append(vad_line)
        lines += _model_line(controller, picks(state))
        mode = _mode(mode)
        from halo_harness.theme import get_config_value
        voice = str(get_config_value("voice.tts_voice", default=None) or "af_heart")
        try:
            dev = audio or A.Audio.open(input=None if mic else False)
        except Exception as e:
            from halo_harness.voice.ensure import stop
            return False, lines + [f"the audio device did not open ({type(e).__name__}: {e}): halo voice devices"] + \
                stop(started, state)
        loop = VoiceLoop(controller, stt_url=urls["stt"], tts_url=urls["tts"], audio=dev, vad=vad, mode=mode,
                         voice=voice, budget_ms=budget(picks(state)["budget_ms"]), state_dir=state)
        loop.started = started
        loop.link = dict(urls.get("link") or {})  # 3.3.9.0 R3: a speech server on another halo: the card's link stage
        _LOOPS[id(controller)] = (loop, started)
        loop.start(mic=mic)
    how = (f"push-to-talk: {ptt_key()} to talk, again to send" if mode == "ptt" else
           "hands-free: speak, and a pause of 250 ms sends it; speaking over a reply stops it")
    return True, lines + [f"voice on ({how}); vad: {vad.kind}; /voice off stops it"]


def off(controller) -> list:
    from halo_harness.voice.ensure import stop
    with _LOCK:
        loop, started = _LOOPS.pop(id(controller), (None, None))
    if loop is None:
        return ["voice is off (/voice on starts it)"]
    loop.stop()
    return ["voice off"] + stop(started or [], _state(controller))


def ptt(controller) -> str:
    loop = get(controller)
    if loop is None:
        return f"voice is off: /voice ptt turns it on in push-to-talk ({ptt_key()} to talk)"
    if loop.mode != "ptt":
        loop.mode = "ptt"
        loop.post("on", mode="ptt")
    return loop.ptt()


def status_lines(controller) -> list:
    from halo_harness.voice.ensure import picks, running
    from halo_harness.voice.latency import budget, line, rows
    state = _state(controller)
    loop = get(controller)
    pk = picks(state)
    out = [f"voice is {'on: ' + loop.mode if loop else 'off'}" + (f" (vad {loop.vad.kind})" if loop else "")]
    from halo_harness.voice.remote import parse, setting
    for kind in ("stt", "tts"):
        if parse(setting(kind)):
            out.append(f"  {kind}: {setting(kind)} (voice.{kind}_server: through that halo host, over the LAN)")
            continue
        url = running(kind, state)
        model, device = pk[kind]
        out.append(f"  {kind}: {model}" + (f" on {url}" if url else f" (not running: /voice on starts it, "
                                                                    f"{device or 'voice.device'})"))
    out.append(f"  budget {budget(pk['budget_ms']):,} ms (target 750-900 ms)" +
               (f"; the {pk['bundle']} bundle is on" if pk["bundle"] else ""))
    last = rows(state, 1) if state is not None else []
    if last:
        out.append("  last turn: " + line(last[-1]))
    if loop is not None and loop.mode == "ptt":
        out.append(f"  push-to-talk: {ptt_key()} to talk, again to send")
    return out


def slash(controller, args: str = "") -> str:
    words = (args or "").split()
    sub = words[0].lower() if words else "status"
    if sub == "status":
        return "\n".join(status_lines(controller))
    if sub in ("on", "hands-free"):
        mode = "hands-free" if sub == "hands-free" else (words[1] if len(words) > 1 else None)
        return "\n".join(on(controller, mode)[1])
    if sub == "off":
        return "\n".join(off(controller))
    if sub == "ptt":
        if get(controller) is None:
            return "\n".join(on(controller, "ptt")[1])
        loop = get(controller)
        loop.mode = "ptt"
        loop.post("on", mode="ptt")
        return f"push-to-talk: {ptt_key()} to talk, again to send (/voice on hands-free goes back)"
    return USAGE
