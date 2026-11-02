"""halo_harness.voice.server_routes -- the speech server's routes, OpenAI's audio shapes (Halo 3.3.9.0 R1; docs/
VOICE.md "The server"):

    GET  /health                    200 {"status": "ok", "device", "model", "kind"}; 503 {"status": "loading"} while the
                                    model loads; 500 {"status": "failed", "error"} when the load failed
    GET  /v1/models                 the one model it serves
    POST /v1/audio/transcriptions   (stt) a multipart `file` (a WAV, 16-bit PCM) with `response_format` json | text,
                                    or a raw body `audio/pcm;rate=16000` (16-bit mono) or `audio/wav`
                                    -> {"text", "segments": [{start, end, text}], "duration", "ms"}
    POST /v1/audio/speech           (tts) {"model", "input", "voice", "response_format": "pcm" | "wav"} -> the audio:
                                    pcm streams each sentence as it is made (audio/pcm;rate=24000), wav is sent whole

One request at a time reaches the engine (a lock); every request leaves one log line (voice/log_lines.py).
"""

from __future__ import annotations

import array
import io
import json
import re
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler

from halo_harness.voice import log_lines as L

MAX_BODY = 64 * 2 ** 20


class State:
    def __init__(self, kind: str, model: str, device: str, say, voice: str) -> None:
        self.kind, self.model, self.device, self.say, self.voice = kind, model, device, say, voice
        self.engine = None
        self.status, self.error = "loading", ""
        self.lock = threading.Lock()


class BadAudio(ValueError):
    pass


def multipart(body: bytes, ctype: str) -> dict:
    m = re.search(r'boundary="?([^";]+)"?', ctype or "")
    if not m:
        raise BadAudio("a multipart body without a boundary")
    out = {}
    for chunk in body.split(b"--" + m.group(1).encode("latin-1"))[1:]:
        if chunk.startswith(b"--"):
            break
        head, _sep, data = chunk.partition(b"\r\n\r\n")
        name = re.search(rb'name="([^"]*)"', head)
        if name:
            out[name.group(1).decode("utf-8", "replace")] = data[:-2] if data.endswith(b"\r\n") else data
    return out


def from_wav(data: bytes) -> "tuple[bytes, int]":
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            ch, width, rate, frames = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.readframes(w.getnframes())
    except (wave.Error, EOFError) as e:
        raise BadAudio(f"not a WAV file ({e}): send a 16-bit PCM WAV or audio/pcm;rate=16000") from None
    if width != 2:
        raise BadAudio(f"a {8 * width}-bit WAV: send 16-bit PCM")
    if ch > 1:
        frames = array.array("h", frames)[::ch].tobytes()
    return frames, rate


def to_wav(pcm: bytes, rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _rate(ctype: str, default: int = 16000) -> int:
    m = re.search(r"rate=(\d+)", ctype or "")
    return int(m.group(1)) if m else default


def make_handler(st: State):
    class Handler(BaseHTTPRequestHandler):
        server_version = "halo-voice/1"

        def log_message(self, *_a):
            pass

        def _json(self, code: int, obj) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _error(self, code: int, message: str) -> None:
            if code >= 500:
                st.say(L.request_failed(self.command, self.path.split("?")[0], code, message))
            self._json(code, {"error": {"message": message, "code": code}})

        def _body(self) -> bytes:
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise BadAudio(f"a body of {n:,} bytes: at most {MAX_BODY:,}")
            return self.rfile.read(n) if n > 0 else b""

        def do_GET(self):  # noqa: N802
            path = self.path.split("?")[0].rstrip("/")
            if path == "/health":
                if st.status == "ok":
                    return self._json(200, {"status": "ok", "device": st.device, "model": st.model, "kind": st.kind})
                if st.status == "failed":
                    return self._json(500, {"status": "failed", "error": st.error, "model": st.model})
                return self._json(503, {"status": "loading", "device": st.device, "model": st.model})
            if path == "/v1/models":
                return self._json(200, {"object": "list", "data": [{"id": st.model, "object": "model", "owned_by": "halo",
                                                                      "kind": st.kind, "device": st.device}]})
            return self._json(404, {"error": {"message": f"no route {path}", "code": 404}})

        def do_POST(self):  # noqa: N802
            path = self.path.split("?")[0].rstrip("/")
            want = {"/v1/audio/transcriptions": "stt", "/v1/audio/speech": "tts"}.get(path)
            if want is None:
                return self._json(404, {"error": {"message": f"no route {path}", "code": 404}})
            if want != st.kind:
                return self._json(404, {"error": {"message": f"this is the {st.kind} server ({st.model}): {path} is the "
                                                  f"{want} server's", "code": 404}})
            if st.status != "ok":
                return self._json(503, {"error": {"message": f"{st.model} is {st.status}", "code": 503}})
            try:
                body = self._body()
                return self._stt(body) if want == "stt" else self._tts(body)
            except BadAudio as e:
                return self._json(400, {"error": {"message": str(e), "code": 400}})
            except (BrokenPipeError, ConnectionResetError):
                return None
            except Exception as e:  # the engine's own failure: one log line, a 500
                return self._error(500, f"{type(e).__name__}: {e}")

        def _stt(self, body: bytes):
            ctype = self.headers.get("Content-Type") or ""
            fmt = "json"
            if ctype.startswith("multipart/form-data"):
                parts = multipart(body, ctype)
                if "file" not in parts:
                    raise BadAudio("no `file` part in the form")
                fmt = parts.get("response_format", b"json").decode("utf-8", "replace").strip() or "json"
                pcm, rate = from_wav(parts["file"])
            elif "wav" in ctype:
                pcm, rate = from_wav(body)
            elif ctype.startswith("audio/pcm") or ctype.startswith("audio/l16"):
                pcm, rate = body[: len(body) // 2 * 2], _rate(ctype)
            else:
                raise BadAudio(f"Content-Type {ctype or 'none'}: send multipart `file` (WAV), audio/wav, or "
                               "audio/pcm;rate=16000")
            duration = len(pcm) / 2 / float(rate)
            t0 = time.monotonic()
            with st.lock:
                segs = st.engine.transcribe(pcm, rate)
            took = time.monotonic() - t0
            st.say(L.stt(duration, took, st.device))
            text = " ".join(s["text"] for s in segs).strip()
            if fmt == "text":
                raw = text.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return None
            return self._json(200, {"text": text, "segments": segs, "duration": round(duration, 3),
                                    "ms": int(round(took * 1000))})

        def _tts(self, body: bytes):
            try:
                req = json.loads(body.decode("utf-8") or "{}")
            except ValueError:
                raise BadAudio("the body is not JSON: {model, input, voice, response_format}") from None
            text = str(req.get("input") or "").strip()
            if not text:
                raise BadAudio("`input` is empty")
            voice, fmt = str(req.get("voice") or st.voice), str(req.get("response_format") or "wav").lower()
            if fmt not in ("pcm", "wav"):
                raise BadAudio(f"response_format {fmt}: this server makes pcm or wav")
            t0, first, total = time.monotonic(), None, 0
            with st.lock:
                chunks = st.engine.speak(text, voice)
                rate = st.engine.sample_rate
                if fmt == "pcm":
                    for chunk in chunks:
                        if first is None:
                            first = time.monotonic() - t0
                            self.send_response(200)
                            self.send_header("Content-Type", f"audio/pcm;rate={st.engine.sample_rate}")
                            self.send_header("X-Sample-Rate", str(st.engine.sample_rate))
                            self.end_headers()
                        self.wfile.write(chunk)
                        self.wfile.flush()
                        total += len(chunk)
                    if first is None:
                        self.send_response(200)
                        self.send_header("Content-Type", f"audio/pcm;rate={rate}")
                        self.end_headers()
                else:
                    out = []
                    for chunk in chunks:
                        first = time.monotonic() - t0 if first is None else first
                        out.append(chunk)
                    wav = to_wav(b"".join(out), st.engine.sample_rate)
                    total = sum(len(c) for c in out)
                rate = st.engine.sample_rate
            took = time.monotonic() - t0
            st.say(L.tts(len(text), total / 2 / float(rate), int(round((first or took) * 1000)), took, st.device))
            if fmt == "wav":
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(wav)))
                self.end_headers()
                self.wfile.write(wav)
            return None

    return Handler
