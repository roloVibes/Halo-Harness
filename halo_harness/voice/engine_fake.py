"""halo_harness.voice.engine_fake -- the fake engine (Halo 3.3.9.0 R1; tests only: HALO_VOICE_ENGINE=fake, docs/
DEVELOPMENT.md's test flags). It loads no model and imports nothing of the extra:

    transcribe(pcm16, rate) -> one segment, the fixed TRANSCRIPT, over the audio's own duration
    speak(text, voice) -> a 440 Hz sine of HALO_VOICE_FAKE_MS milliseconds (default 500) per sentence, PCM16 at 24 kHz

HALO_VOICE_FAKE_LOAD_S makes the load take that long (the /health 503 while it loads); HALO_VOICE_FAKE_FAIL=1 makes
the load fail the way a missing CUDA library does (the log's `voice load failed:` line).
"""

from __future__ import annotations

import math
import os
import struct
import time
from typing import Iterator

from halo_harness.voice.engines import Engine, sentences

TRANSCRIPT = "the fake engine heard sixteen kilohertz audio"


def sine(ms: int, rate: int = 24000, hz: float = 440.0) -> bytes:
    n = int(rate * ms / 1000)
    return b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * hz * i / rate))) for i in range(n))


class FakeEngine(Engine):
    def __init__(self, row, device, path) -> None:
        super().__init__(row, device, path)
        self.kind = row.kind
        self.sample_rate = 24000 if row.kind == "tts" else 16000
        delay = float(os.environ.get("HALO_VOICE_FAKE_LOAD_S", "0") or 0)
        if delay > 0:
            time.sleep(delay)
        if os.environ.get("HALO_VOICE_FAKE_FAIL") == "1":
            raise RuntimeError("Library libcublas.so.12 is not found or cannot be loaded (the fake's failure)")

    def transcribe(self, pcm16: bytes, sample_rate: int) -> list:
        dur = len(pcm16) / 2 / float(sample_rate or 16000)
        return [{"start": 0.0, "end": round(dur, 2), "text": TRANSCRIPT}]

    def speak(self, text: str, voice: str) -> Iterator[bytes]:
        ms = int(os.environ.get("HALO_VOICE_FAKE_MS", "500") or 500)
        for _s in sentences(text):
            yield sine(ms, self.sample_rate)
