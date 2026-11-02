"""halo_harness.voice.speak -- the reply side of the voice loop (Halo 3.3.9.0 R2; docs/VOICE.md "The loop"):

    Speaker(tts_url=, voice=, audio=, post=, done=, clock=)
    .tap(event)         a tap on the session's event sink (Controller.add_event_tap): the main agent's `text_delta`s go
                        through the sentence aggregator; each finished sentence is queued for the TTS server
    .begin(card)        the card of the utterance just submitted (an open one ends first, as steered)
    .active() -> bool   a reply is queued, speaking, or still being written
    .cut(steered=) -> bool   barge-in: playback stops at once, the rest of this reply is not spoken (True: it was speaking)
    .close()

One worker thread speaks: a sentence -> POST /v1/audio/speech (pcm) -> each chunk to the speaker as it arrives, so the
first sentence plays while the model still writes the second. After a cut the speaker stays quiet until the session's
next model call (`message_start`: the steered reply) or the next turn. `done(card)` gets each turn's card once.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable, Optional

from halo_harness.voice.aggregate import Aggregator

_END = object()
_STOP = object()


class Speaker:
    def __init__(self, *, tts_url: str, voice: str, audio, post: Callable, done: Callable, clock=time.perf_counter) -> None:
        self.url, self.voice, self.audio, self.post, self.done, self.clock = tts_url, voice, audio, post, done, clock
        self.q: "queue.Queue" = queue.Queue()
        self.agg = Aggregator()
        self.card = None
        self.muted = False
        self.writing = False
        self.speaking = threading.Event()
        self.idle = threading.Event()
        self.idle.set()
        self.lock = threading.Lock()
        self.errors: list = []
        self._t = threading.Thread(target=self._work, name="halo-voice-speak", daemon=True)
        self._t.start()

    # ---- the session's events (the session's own thread: quick) ----------------------------------------------
    def tap(self, ev) -> None:
        if getattr(ev, "agent_id", None) is not None:
            return
        kind = ev.kind
        with self.lock:
            if kind == "message_start":
                self.writing = True
                if self.muted:
                    self.muted = False
                    self.audio.resume_output()
                self.agg = Aggregator()
            elif kind == "text_delta" and not self.muted:
                if self.card is not None:
                    self.card.mark("token")
                    self.card.text += str(ev.data.get("text") or "")
                for s in self.agg.feed(ev.data.get("text") or ""):
                    self._say(s)
            elif kind == "turn_done":
                self.writing = False
                if not self.muted:
                    for s in self.agg.flush():
                        self._say(s)
                    self.idle.clear()
                    self.q.put((_END, self.card))
                    self.card = None

    def _say(self, sentence: str) -> None:
        self.idle.clear()
        self.q.put((sentence, self.card))

    # ---- the loop's side -------------------------------------------------------------------------------------
    def begin(self, card) -> None:
        with self.lock:
            old, self.card = self.card, card
        if old is not None:
            old.steered = True
            self._finish(old)

    def active(self) -> bool:
        return self.writing or self.speaking.is_set() or not self.idle.is_set()

    def cut(self, *, steered: bool = False) -> bool:
        was = self.speaking.is_set()
        ended: list = []
        with self.lock:
            self.muted = True
            self.agg = Aggregator()
            self.audio.stop_output()
            while True:
                try:
                    item = self.q.get_nowait()
                except queue.Empty:
                    break
                if item is _STOP:
                    self.q.put(_STOP)
                    break
                if item[0] is _END and item[1] is not None:
                    ended.append(item[1])
            if self.card is not None:
                ended.append(self.card)
            self.card = None
            self.speaking.clear()
        for card in ended:
            card.interrupted, card.steered = was, card.steered or steered
            self._finish(card)
        if was:
            self.post("interrupted", text="(interrupted while speaking)")
        self.idle.set()
        return was

    def close(self) -> None:
        self.q.put(_STOP)

    def _finish(self, card) -> None:
        try:
            self.done(card)
        except Exception:
            pass

    # ---- the worker -----------------------------------------------------------------------------------------
    def _work(self) -> None:
        from halo_harness.voice.client import VoiceError, speak
        while True:
            item = self.q.get()
            if item is _STOP:
                return
            if item[0] is _END:
                card = item[1]
                if card is not None:
                    card.mark("last")
                    self._finish(card)
                if self.q.empty():
                    self.speaking.clear()
                    self.post("idle")
                    self.idle.set()
                continue
            sentence, card = item
            if self.muted:
                continue
            try:
                rate, chunks = speak(self.url, sentence, self.voice)
                for chunk in chunks:
                    if self.muted:
                        break
                    if not self.speaking.is_set():
                        self.speaking.set()
                        self.post("speaking")
                    if card is not None:
                        card.mark("audio")
                    if not self.audio.play(chunk, rate):
                        break
            except VoiceError as e:
                if not self.muted:
                    self.errors.append(str(e))
                    self.post("note", text=str(e))
            except Exception as e:  # a speaker that failed mid-sentence: one line, the loop goes on
                if self.muted:
                    continue  # the barge-in's own cut
                self.errors.append(f"{type(e).__name__}: {e}")
                self.post("note", text=f"the speaker failed: {type(e).__name__}: {e}")
