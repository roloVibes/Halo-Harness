"""halo_harness.voice.client -- the loop's two calls to R1's speech servers (Halo 3.3.9.0 R2; docs/VOICE.md):

    transcribe(base_url, pcm16, rate=16000) -> str       POST <base>/audio/transcriptions, a raw audio/pcm body
    speak(base_url, text, voice) -> (rate, iterator of PCM16 chunks)   POST <base>/audio/speech, response_format pcm,
                                                          read as the server streams it (one sentence at a time)

`base_url` is the `huggingface.local_servers` entry's url (`http://127.0.0.1:<port>/v1`); 3.3.9.0 R3: a `halo-host:<host>#
<kind>` url (voice/remote.py: `voice.stt_server: stt@pc`) goes through that host's signed voice routes. A failure is
VoiceError with one line (the server, the status, its message); nothing retries by itself.
"""

from __future__ import annotations

import http.client
import json
from typing import Iterator
from urllib.parse import urlsplit

TIMEOUT_S = 30.0
CHUNK = 4800


class VoiceError(RuntimeError):
    pass


def _conn(base_url: str):
    u = urlsplit(str(base_url).rstrip("/"))
    cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
    return cls(u.hostname or "127.0.0.1", u.port or (443 if u.scheme == "https" else 80), timeout=TIMEOUT_S), u.path


def _fail(what: str, base_url: str, r) -> VoiceError:
    try:
        msg = json.loads(r.read().decode("utf-8") or "{}").get("error", {}).get("message", "")
    except (ValueError, AttributeError, OSError):
        msg = ""
    return VoiceError(f"the {what} server at {base_url} answered {r.status}" + (f": {msg}" if msg else ""))


def transcribe(base_url: str, pcm16: bytes, rate: int = 16000) -> str:
    if str(base_url).startswith("halo-host:"):
        from halo_harness.voice import remote
        return remote.transcribe(base_url, pcm16, rate)
    c, root = _conn(base_url)
    try:
        c.request("POST", f"{root}/audio/transcriptions", body=pcm16,
                  headers={"Content-Type": f"audio/pcm;rate={int(rate)}", "Content-Length": str(len(pcm16))})
        r = c.getresponse()
        if r.status != 200:
            raise _fail("stt", base_url, r)
        return str(json.loads(r.read().decode("utf-8") or "{}").get("text") or "").strip()
    except (OSError, http.client.HTTPException, ValueError) as e:
        raise VoiceError(f"the stt server at {base_url} did not answer: {e} (halo local servers)") from None
    finally:
        c.close()


def speak(base_url: str, text: str, voice: str) -> "tuple[int, Iterator[bytes]]":
    if str(base_url).startswith("halo-host:"):
        from halo_harness.voice import remote
        return remote.speak(base_url, text, voice)
    c, root = _conn(base_url)
    body = json.dumps({"input": text, "voice": voice, "response_format": "pcm"}).encode("utf-8")
    try:
        c.request("POST", f"{root}/audio/speech", body=body, headers={"Content-Type": "application/json"})
        r = c.getresponse()
    except (OSError, http.client.HTTPException) as e:
        c.close()
        raise VoiceError(f"the tts server at {base_url} did not answer: {e} (halo local servers)") from None
    if r.status != 200:
        err = _fail("tts", base_url, r)
        c.close()
        raise err
    rate = int(r.getheader("X-Sample-Rate") or 24000)

    def chunks():
        left = b""
        try:
            while True:
                b = left + r.read(CHUNK)
                if len(b) == len(left):
                    return
                cut = len(b) // 2 * 2
                left = b[cut:]
                if cut:
                    yield b[:cut]
        except (OSError, http.client.HTTPException):
            return
        finally:
            c.close()
    return rate, chunks()
