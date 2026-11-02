"""halo_harness.voice.log_lines -- the speech server's log lines, written here and read here (Halo 3.3.9.0 R1): the
server (voice/server.py, server_routes.py) writes them, the steward's reader (ollama_steward/server_log_voice.py)
parses them with the patterns below -- one source, so the two cannot drift.

    voice server listening on http://127.0.0.1:<port> (stt faster-whisper:small.en)
    voice load: stt faster-whisper:small.en on cpu (int8) in 1.20 s; the GPU had 22,000 MiB free
    voice stt: audio 4.2 s -> text in 0.31 s (13.5x realtime) on cpu
    voice tts: text 84 chars -> audio 3.9 s, first audio 92 ms, in 0.40 s on cpu
    voice load failed: stt faster-whisper:small.en on cuda: <the error>
    voice request failed: POST /v1/audio/transcriptions 500: <the error>
"""

from __future__ import annotations

import re
from typing import Optional

LISTEN = re.compile(r"^voice server listening on (\S+) \((stt|tts) (\S+)\)")
LOAD = re.compile(r"^voice load: (stt|tts) (\S+) on (cpu|cuda) \(([^)]*)\) in ([\d.]+) s"
                  r"(?:; the GPU had ([\d,]+) MiB free)?")
STT = re.compile(r"^voice stt: audio ([\d.]+) s -> text in ([\d.]+) s \(([\d.]+)x realtime\) on (cpu|cuda)")
TTS = re.compile(r"^voice tts: text (\d+) chars -> audio ([\d.]+) s, first audio (\d+) ms, in ([\d.]+) s on (cpu|cuda)")
LOAD_FAILED = re.compile(r"^voice load failed: (stt|tts) (\S+) on (cpu|cuda): (.*)$")
REQ_FAILED = re.compile(r"^voice request failed: (\w+) (\S+) (\d{3}): (.*)$")


def listening(url: str, kind: str, model: str) -> str:
    return f"voice server listening on {url} ({kind} {model})"


def loaded(kind: str, model: str, device: str, compute: str, seconds: float, gpu_free_mib: Optional[int] = None) -> str:
    tail = f"; the GPU had {gpu_free_mib:,} MiB free" if isinstance(gpu_free_mib, int) else ""
    return f"voice load: {kind} {model} on {device} ({compute}) in {seconds:.2f} s{tail}"


def stt(audio_s: float, seconds: float, device: str) -> str:
    rtf = audio_s / max(seconds, 1e-3)
    return f"voice stt: audio {audio_s:.1f} s -> text in {seconds:.2f} s ({rtf:.1f}x realtime) on {device}"


def tts(chars: int, audio_s: float, first_ms: int, seconds: float, device: str) -> str:
    return (f"voice tts: text {chars} chars -> audio {audio_s:.1f} s, first audio {int(first_ms)} ms, "
            f"in {seconds:.2f} s on {device}")


def load_failed(kind: str, model: str, device: str, error: str) -> str:
    return f"voice load failed: {kind} {model} on {device}: {' '.join(str(error).split())[:300]}"


def request_failed(method: str, path: str, status: int, error: str) -> str:
    return f"voice request failed: {method} {path} {status}: {' '.join(str(error).split())[:300]}"


def parse(line: str) -> Optional[dict]:
    """One log line -> {what, ...the numbers}, or None for a line that is not the server's own."""
    text = str(line or "").strip()
    if m := STT.match(text):
        return {"what": "stt", "audio_s": float(m.group(1)), "seconds": float(m.group(2)), "rtf": float(m.group(3)),
                "device": m.group(4)}
    if m := TTS.match(text):
        return {"what": "tts", "chars": int(m.group(1)), "audio_s": float(m.group(2)), "first_ms": int(m.group(3)),
                "seconds": float(m.group(4)), "device": m.group(5)}
    if m := LOAD.match(text):
        free = int(m.group(6).replace(",", "")) if m.group(6) else None
        return {"what": "load", "kind": m.group(1), "model": m.group(2), "device": m.group(3), "compute": m.group(4),
                "seconds": float(m.group(5)), "gpu_free_mib": free}
    if m := LOAD_FAILED.match(text):
        return {"what": "load-failed", "kind": m.group(1), "model": m.group(2), "device": m.group(3),
                "error": m.group(4)}
    if m := REQ_FAILED.match(text):
        return {"what": "request-failed", "method": m.group(1), "path": m.group(2), "status": int(m.group(3)),
                "error": m.group(4)}
    if m := LISTEN.match(text):
        return {"what": "listening", "url": m.group(1), "kind": m.group(2), "model": m.group(3)}
    return None
