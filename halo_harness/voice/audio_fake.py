"""halo_harness.voice.audio_fake -- the fake audio seam (Halo 3.3.9.0 R2; tests only: HALO_VOICE_AUDIO=fake, docs/
DEVELOPMENT.md). Audio.open returns it and no device is opened:

    feed(pcm)          what the microphone hears (cut into audio.FRAME frames); frames() yields them
    captured           [(rate, pcm)] every chunk played
    hold=True          play() keeps "speaking" until release() or stop_output() (a barge-in test's long reply);
                       stopped_at is the `clock` reading when stop_output() first cut it
"""

from __future__ import annotations

import queue
import threading
from typing import Optional

from halo_harness.voice.audio import split


class FakeAudio:
    """The test seam: no device. feed(pcm) is what the microphone hears; captured is [(rate, pcm)] played."""

    def __init__(self, hold: bool = False, clock=None) -> None:
        self.q: "queue.Queue" = queue.Queue()
        self.captured: list = []
        self.hold, self.clock = hold, clock
        self.cut, self.closed, self.playing, self.released = (threading.Event() for _ in range(4))
        self.stopped_at: Optional[float] = None
        self.inp = {"index": 0, "name": "fake microphone"}
        self.out = {"index": 0, "name": "fake speaker"}

    def feed(self, pcm: bytes) -> None:
        for f in split(pcm):
            self.q.put(f)

    def frames(self):
        while not self.closed.is_set():
            try:
                yield self.q.get(timeout=0.05)
            except queue.Empty:
                continue

    def play(self, pcm: bytes, rate: int) -> bool:
        if self.cut.is_set():
            return False
        self.captured.append((rate, pcm))
        self.playing.set()
        if self.hold:
            self.released.wait(30)
        return not self.cut.is_set()

    def release(self) -> None:
        self.released.set()

    def stop_output(self) -> None:
        if not self.cut.is_set() and self.clock is not None:
            self.stopped_at = self.clock()
        self.cut.set()
        self.released.set()

    def resume_output(self) -> None:
        self.cut.clear()
        if self.hold:
            self.released.clear()
        self.playing.clear()

    def close(self) -> None:
        self.closed.set()
        self.stop_output()
