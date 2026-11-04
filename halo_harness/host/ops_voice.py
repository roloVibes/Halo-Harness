"""halo_harness.host.ops_voice -- the host's voice door and its speech servers for the LAN (Halo 3.3.9.0 R3; docs/HOST.md
"The voice door", docs/VOICE-glasses.md has the wire shape with a worked example).

    POST voice/turn?session=<id>&voice=<name>   body: one utterance, audio/pcm;rate=N (16-bit mono, 8,000-48,000 Hz) or
        audio/wav, up to 30 s. The `control` grant. The host's stt server hears it, the transcript goes to the session's
        control socket exactly as typed text (voice/turn.py), and the reply comes back as a framed stream:
            Content-Type: application/x-halo-voice; one frame = 1 byte kind + 4 bytes big-endian length + payload
            J {"heard": text}            the transcript, first
            J {"rate": 24000}            the audio's sample rate, before its first A frame (again only if it changes)
            A <PCM16 mono at `rate`>     the reply's audio as the tts server makes it
            N {"note": line}             a line the reply's audio does not say (a tts failure, a timeout)
            J {"done": true, transcript, reply, rate, audio_bytes, card, line, session}   the trailer, last
        refused before the stream starts: one line as {"error"} -- no grant, no session, no stt / tts server, the 30 s
        budget, an audio shape it cannot read
    POST voice/stt    the host's stt server for a peer's loop (`voice.stt_server: stt@<host>`): the body as the speech
                      server takes it, its JSON back
    POST voice/tts    {input, voice, response_format: pcm} -> the PCM stream of the host's tts server
    door(svc) -> the `GET me` block: {door, grant, stt, tts, sessions, max_s, takes, gives}

The host calls the speech servers and the session; no model runs in this process. Each request is one audit line (its
op voice_turn | voice_stt | voice_tts, the seconds, the session); the pair key and the audio are never logged.
"""

from __future__ import annotations

import http.client
import json
import struct
from typing import Optional

ROUTES = ("turn", "stt", "tts")
MAX_BODY = int(30 * 48000 * 2) + 65536
TAKES = "audio/pcm;rate=16000 (16-bit mono; 8,000-48,000 Hz) or audio/wav, up to 30 s"
GIVES = "application/x-halo-voice: J {heard}, A <PCM16 24 kHz>..., J {done, transcript, reply, card}"


def frame(kind: bytes, payload: bytes) -> bytes:
    return kind + struct.pack(">I", len(payload)) + payload


def speech(svc, kind: str) -> Optional[dict]:
    """The host machine's running stt / tts server: {name, url (its /v1 base), model}, or None."""
    for s in svc.view.servers():
        if str(getattr(s, "runtime", "") or "") == f"voice-{kind}":
            base = str(s.url).rstrip("/")
            return {"name": s.name, "url": base if base.endswith("/v1") else base + "/v1", "model": s.model}
    return None


def door(svc) -> dict:
    from halo_harness.voice.turn import MAX_S, public, sessions
    rows = sessions(svc.home)
    said = {k: ({"name": g["name"], "model": g["model"]} if g else None) for k, g in
            (("stt", speech(svc, "stt")), ("tts", speech(svc, "tts")))}  # its loopback url means nothing to a peer
    return {"door": "POST /host/v1/voice/turn", "grant": "control", **said, "sessions": [public(r) for r in rows],
            "max_s": MAX_S, "takes": TAKES, "gives": GIVES}


def _start(h, ctype: str, extra: Optional[dict] = None) -> None:
    h.send_response(200)
    for k, v in (("Content-Type", ctype), ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                 ("Connection", "close"), *((extra or {}).items())):
        h.send_header(k, v)
    h.end_headers()
    h.close_connection = True
    h._status = 200


def _missing(svc, kind: str) -> str:
    from halo_harness.fleet.identity import fleet_name
    model = "faster-whisper:small.en" if kind == "stt" else "kokoro-82m"
    return f"no {kind} server runs on {fleet_name(svc.home)}: there, halo local serve --{kind} {model}"


def post(h, route: str, raw: bytes, hid: str) -> None:
    name = route.partition("/")[2]
    h._act = {"op": f"voice_{name}"}
    if name not in ROUTES:
        return h._json(404, {"error": f"no voice route {name!r}: POST voice/turn | voice/stt | voice/tts"})
    if name == "turn":
        return _turn(h, raw, hid)
    # finding 54 (3.3.11.0 security review M11): stt and tts proxy
    # routes must observe the same control grant and allow_control
    # checks that voice/turn already enforces -- without this, a
    # paired peer with the default `view` grant gets free GPU
    # speech-server proxying through loopback.
    from halo_harness.host import grants
    rec = h.svc.pairing.member(hid)
    if not grants.holds(grants.grants_of(rec), "control"):
        return h._json(403, {"error": grants.missing_line("control",
                              f"voice/{name}", rec, h.svc.home), "grant": "control"})
    if grants.cap(h.svc.home) == "none":
        return h._json(403, {"error": grants.none_line(h.svc.home),
                              "grant": "control", "cap": "none"})
    got = speech(h.svc, name)
    if got is None:
        return h._json(409, {"error": _missing(h.svc, name)})
    h._act["params"] = {"server": got["name"], "bytes": len(raw)}
    return _proxy(h, got["url"], name, raw)


def _proxy(h, base: str, kind: str, raw: bytes) -> None:
    from halo_harness.voice.client import _conn  # the loop's own connection to a speech server (loopback here)
    conn, root = _conn(base)
    route = "/audio/transcriptions" if kind == "stt" else "/audio/speech"
    ctype = str(h.headers.get("Content-Type") or ("audio/pcm;rate=16000" if kind == "stt" else "application/json"))
    try:
        conn.request("POST", root + route, body=raw, headers={"Content-Type": ctype, "Content-Length": str(len(raw))})
        r = conn.getresponse()
        if r.status != 200 or kind == "stt":
            body = r.read()
            try:
                obj = json.loads(body.decode("utf-8") or "{}")
            except ValueError:
                obj = {"error": body.decode("utf-8", "replace")[:300]}
            return h._json(r.status, obj)
        _start(h, r.getheader("Content-Type") or "audio/pcm;rate=24000",
               {"X-Sample-Rate": r.getheader("X-Sample-Rate") or "24000"})
        while True:
            b = r.read(4800)
            if not b:
                break
            h.wfile.write(b)
            h.wfile.flush()
    except (OSError, http.client.HTTPException) as e:
        if not getattr(h, "_status", 0):
            return h._json(502, {"error": f"the {kind} server at {base} did not answer: {e}"})
    finally:
        conn.close()


def _turn(h, raw: bytes, hid: str) -> None:
    from halo_harness.fleet.identity import fleet_name
    from halo_harness.host import grants
    from halo_harness.theme import get_config_value
    from halo_harness.voice import turn as T
    svc, q = h.svc, h._query()
    rec = svc.pairing.member(hid)
    if not grants.holds(grants.grants_of(rec), "control"):
        return h._json(403, {"error": grants.missing_line("control", "voice/turn", rec, svc.home), "grant": "control"})
    if grants.cap(svc.home) == "none":
        return h._json(403, {"error": grants.none_line(svc.home), "grant": "control", "cap": "none"})
    where = fleet_name(svc.home)
    try:
        pcm, secs = T.pcm_of(raw, str(h.headers.get("Content-Type") or ""))
        h._act["params"] = {"seconds": round(secs, 2)}
        row = T.pick(T.sessions(svc.home), str(q.get("session") or ""), where)
    except T.TurnError as e:
        return h._json(e.status, {"error": e.line})
    h._act["params"]["session"] = str(row["session_id"])[:12]
    stt, tts = speech(svc, "stt"), speech(svc, "tts")
    for kind, got in (("stt", stt), ("tts", tts)):
        if got is None:
            return h._json(409, {"error": _missing(svc, kind)})
    voice = str(q.get("voice") or get_config_value("voice.tts_voice", default=None) or "af_heart")
    started = {"on": False}

    def emit(kind: str, data) -> None:
        if kind == "rate" and data.get("rate") == started.get("rate"):
            return  # the audio's rate is said once, before its first A frame, and again only when it changes
        if not started["on"]:
            _start(h, "application/x-halo-voice", {"X-Halo-Voice": "1"})
            started["on"] = True
        if kind == "audio":
            h.wfile.write(frame(b"A", data))
        else:
            started["rate"] = data.get("rate") if kind == "rate" else started.get("rate")
            payload = {"heard": data["text"]} if kind == "heard" else {"rate": data["rate"]} if kind == "rate" else {
                "note": data.get("text")}
            h.wfile.write(frame(b"N" if kind == "note" else b"J", json.dumps(payload).encode("utf-8")))
        h.wfile.flush()
    from halo_harness.voice.latency import budget
    try:
        trailer = T.run(pcm, stt_url=stt["url"], tts_url=tts["url"], endpoint=row["endpoint"], token=row.get("token"),
                        voice=voice, budget_ms=budget(), emit=emit, session_id=str(row["session_id"]))
    except T.TurnError as e:
        if not started["on"]:
            return h._json(e.status, {"error": e.line})
        h.wfile.write(frame(b"J", json.dumps({"done": True, "error": e.line}).encode("utf-8")))
        return None
    h.wfile.write(frame(b"J", json.dumps(trailer).encode("utf-8")))
    h.wfile.flush()
    h._act.update(landed=True)
    try:
        from halo_harness.voice.latency import record
        record(svc.home, trailer["card"], via="host", peer=getattr(h, "_who", "") or "")
    except OSError:
        pass
