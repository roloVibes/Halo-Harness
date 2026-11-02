"""halo_harness.voice.turn -- one voice turn through a running session's control socket (Halo 3.3.9.0 R3; docs/VOICE.md
"Through the host", docs/VOICE-glasses.md). The host's voice door (`POST /host/v1/voice/turn`, host/ops_voice.py) and
Studio's Talk (studio/voice_act_api.py) both run it; the loop in a session (voice/loop.py) is the same steps in process.

    pcm_of(body, ctype) -> (pcm16 at 16 kHz mono, seconds)   a WAV or audio/pcm;rate=N (8,000-48,000 Hz, mono or the
                              first channel), resampled to 16 kHz; TurnError past MAX_S or for a body it cannot read
    sessions(home=None) -> [{session_id, title, cwd, kind, endpoint, token}]   the live sessions of <home>/run/
                              sessions.json (the pid alive, the endpoint answering a connect)
    pick(rows, want="") -> row   by id (or its start); with no `want`, the one interactive session; TurnError otherwise
    run(pcm, *, stt_url, tts_url, endpoint, token, voice, budget_ms, emit, wait_s) -> the trailer
        the utterance to the stt server -> emit("heard", {text}) -> `submit` on the session's socket exactly as typed
        text (a turn that runs is steered) -> the reply's text through the sentence aggregator -> each sentence to the
        tts server (emit("rate", {rate}) first) -> emit("audio", pcm chunk) as it arrives -> the trailer {done,
        transcript, reply, rate, audio_bytes, card, line, session}; emit("note", {text}) for a line not spoken

The latency card is voice/latency.Card: spoke and heard are the moment the utterance arrived (the far end's VAD already
ended it), then text, token, audio, last. Nothing here runs a model: the speech servers and the session do.
"""

from __future__ import annotations

import array
import io
import queue
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Optional

RATE = 16000
MAX_S = 30.0
WAIT_S = 600.0
KINDS = ["text_delta", "turn_done", "error"]  # text_delta: each delta as it streams (remote/feed.EventHub._raw)


class TurnError(Exception):
    def __init__(self, status: int, line: str) -> None:
        super().__init__(line)
        self.status, self.line = status, line


def resample(pcm: bytes, rate: int, to: int = RATE) -> bytes:
    """Linear interpolation, PCM16 mono (an 8 kHz HFP capture or a 48 kHz browser mic to the 16 kHz the stt takes)."""
    if rate == to or not pcm:
        return pcm
    src = array.array("h", pcm[: len(pcm) // 2 * 2])
    n = max(1, int(len(src) * to / rate))
    step = (len(src) - 1) / max(1, n - 1) if n > 1 else 0.0
    out = array.array("h", bytes(2 * n))
    for i in range(n):
        x = i * step
        j = int(x)
        k = min(j + 1, len(src) - 1)
        out[i] = int(src[j] + (src[k] - src[j]) * (x - j))
    return out.tobytes()


def pcm_of(body: bytes, ctype: str) -> "tuple[bytes, float]":
    import re
    ctype = (ctype or "").lower()
    if "wav" in ctype or body[:4] == b"RIFF":
        try:
            with wave.open(io.BytesIO(body), "rb") as w:
                ch, width, rate, pcm = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.readframes(w.getnframes())
        except (wave.Error, EOFError) as e:
            raise TurnError(400, f"not a WAV file ({e}): send 16-bit PCM, audio/wav or audio/pcm;rate=16000") from None
        if width != 2:
            raise TurnError(400, f"a {8 * width}-bit WAV: send 16-bit PCM")
        if ch > 1:
            pcm = array.array("h", pcm)[::ch].tobytes()
    elif ctype.startswith("audio/pcm") or ctype.startswith("audio/l16") or ctype.startswith("application/octet-stream"):
        m = re.search(r"rate=(\d+)", ctype)
        rate, pcm = (int(m.group(1)) if m else RATE), body[: len(body) // 2 * 2]
    else:
        raise TurnError(415, f"Content-Type {ctype or 'none'}: send audio/pcm;rate=16000 (16-bit mono) or audio/wav")
    if not 8000 <= rate <= 48000:
        raise TurnError(400, f"a {rate:,} Hz utterance: the door takes 8,000-48,000 Hz (16,000 is what the stt hears)")
    secs = len(pcm) / 2 / float(rate)
    if secs > MAX_S:
        raise TurnError(413, f"the utterance is {secs:.1f} s: the voice door takes up to {MAX_S:g} s (16 kHz PCM)")
    if secs < 0.1:
        raise TurnError(400, "the utterance is shorter than 0.1 s: nothing to hear")
    return resample(pcm, rate), secs


def sessions(home=None) -> list:
    import json
    from halo_harness.bg_run import pid_alive
    from halo_harness.remote import client
    if home is None:
        from halo_harness.config.paths import bridge_home
        home = bridge_home()
    try:
        data = json.loads((Path(home) / "run" / "sessions.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for r in (data.get("sessions") if isinstance(data, dict) else None) or []:
        if not isinstance(r, dict) or not r.get("session_id") or not r.get("endpoint"):
            continue
        if isinstance(r.get("pid"), int) and not pid_alive(r["pid"]):
            continue
        if not client.probe(str(r["endpoint"])):
            continue
        out.append({"session_id": r["session_id"], "title": r.get("title") or "", "cwd": str(r.get("cwd") or ""),
                    "kind": r.get("kind") or "tui", "endpoint": r["endpoint"], "token": r.get("token")})
    return out


def public(row: dict) -> dict:
    return {k: row.get(k) for k in ("session_id", "title", "cwd", "kind")}


def pick(rows: list, want: str = "", where: str = "this machine") -> dict:
    if want:
        hit = [r for r in rows if str(r["session_id"]).startswith(want)]
        if len(hit) == 1:
            return hit[0]
        raise TurnError(404 if not hit else 409, f"no running session {want!r} on {where}" if not hit else
                        f"{len(hit)} sessions on {where} start with {want!r}: give more of the id")
    tui = [r for r in rows if r.get("kind", "tui") == "tui"] or rows
    if len(tui) == 1:
        return tui[0]
    if not tui:
        raise TurnError(409, f"no running halo session on {where}: start `halo` there (GET me lists the sessions)")
    ids = ", ".join(str(r["session_id"])[:8] for r in tui)
    raise TurnError(409, f"{len(tui)} sessions run on {where} ({ids}): name one with session=<id>")


def _reader(c, stop) -> "queue.Queue":
    """The session's frames on their own thread, so its bounded feed drains while a sentence is spoken; None: closed."""
    q: "queue.Queue" = queue.Queue()

    def read() -> None:
        while not stop.is_set():
            try:
                ev = c.next_event(0.5)
            except (OSError, ValueError, ConnectionError):
                q.put(None)
                return
            if ev is not None:
                q.put(ev)
    threading.Thread(target=read, name="halo-voice-turn", daemon=True).start()
    return q


def run(pcm: bytes, *, stt_url: str, tts_url: str, endpoint: str, token: Optional[str], voice: str = "af_heart",
        budget_ms: int = 1500, emit: Callable, wait_s: float = WAIT_S, session_id: str = "",
        clock=time.perf_counter) -> dict:
    from halo_harness.remote.client import ControlClient
    from halo_harness.voice.aggregate import Aggregator
    from halo_harness.voice.client import VoiceError, speak, transcribe
    from halo_harness.voice.latency import Card, line
    card = Card(clock, budget_ms)
    card.mark("spoke")
    card.mark("heard")
    try:
        text = transcribe(stt_url, pcm, RATE)
    except VoiceError as e:
        raise TurnError(502, str(e)) from None
    card.mark("text")
    if not text:
        raise TurnError(422, "heard nothing to send (the transcript was empty)")
    emit("heard", {"text": text})
    try:
        c = ControlClient(endpoint, token, timeout=10.0)
    except OSError as e:
        raise TurnError(409, f"the session's control socket did not answer ({e}): is it still running?") from None
    agg, reply, out, stop = Aggregator(), [], {"bytes": 0, "rate": 24000}, threading.Event()

    def say(sentence: str) -> None:
        try:
            rate, chunks = speak(tts_url, sentence, voice)
        except VoiceError as e:
            emit("note", {"text": str(e)})
            return
        out["rate"] = rate
        emit("rate", {"rate": rate})
        for ch in chunks:
            card.mark("audio")
            out["bytes"] += len(ch)
            emit("audio", ch)
    try:
        c.call("subscribe", kinds=KINDS)
        r = c.call("submit", text=text)
        if not r.get("ok"):
            raise TurnError(409, f"the session did not take it: {r.get('error')}")
        card.steered = bool((r.get("result") or {}).get("steered"))
        q = _reader(c, stop)
        end = time.monotonic() + wait_s
        while time.monotonic() < end:
            try:
                ev = q.get(timeout=min(1.0, max(0.05, end - time.monotonic())))
            except queue.Empty:
                continue
            if ev is None:
                emit("note", {"text": "the session's control socket closed before the reply ended"})
                break
            if ev.get("agent_id") is not None:
                continue
            kind, data = ev.get("event"), ev.get("data") or {}
            if kind in ("text_delta", "text_chunk"):
                card.mark("token")
                reply.append(str(data.get("text") or ""))
                for s in agg.feed(str(data.get("text") or "")):
                    say(s)
            elif kind == "error":
                emit("note", {"text": str(data.get("message") or data.get("error") or data)[:300]})
            elif kind == "turn_done":
                for s in agg.flush():
                    say(s)
                break
        else:
            emit("note", {"text": f"the reply did not end within {wait_s:g} s: what it said so far was spoken"})
    finally:
        stop.set()
        c.close()
    card.mark("last")
    card.text = "".join(reply)
    return {"done": True, "transcript": text, "reply": card.text, "rate": out["rate"], "audio_bytes": out["bytes"],
            "card": card.row(), "line": line(card), "session": session_id}
