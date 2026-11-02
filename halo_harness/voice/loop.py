"""halo_harness.voice.loop -- the voice loop: talk to a Halo session and hear it answer (Halo 3.3.9.0 R2; plans/
local-model-fit-brief.md Part K; docs/VOICE.md "The loop"):

    microphone (voice/audio.py, 16 kHz mono, 32 ms frames) -> VAD (voice/vad.py: speech start after START_FRAMES
    voiced frames, its end after end_silence_ms of quiet) -> the utterance to R1's STT server (partial transcripts every
    PARTIAL_MS while the person still speaks) -> controller.submit(transcript) exactly as typed text (a turn that runs
    is steered) -> the reply stream (voice/speak.py: the aggregator's sentences to the TTS server, played as they come)

    VoiceLoop(controller, stt_url=, tts_url=, audio=, vad=, mode="hands-free"|"ptt", ...)
    .start() / .stop()          the microphone thread; the event tap on the session
    .on_frame(pcm)              one frame (the thread's call; tests drive it with a fake clock)
    .ptt()                      push-to-talk: the first press starts an utterance, the next ends it (a terminal sends no
                                key release)
    .say_file(frames)           --input-file: one utterance from a WAV, then the turn and its reply

Barge-in: speech that starts while a reply is queued, playing or still being written stops the playback (Speaker.cut,
within START_FRAMES frames: ~100 ms) and the rest of that reply is not spoken; the new utterance goes to the session as a
steer. Every update is a `voice` event on the session's event sink (state on, off, listening, partial, heard,
interrupted, speaking, idle, card, note), which the TUI draws (tui/voice_view.py) and the control socket forwards.
Each turn's latency card lands in <state>/voice/turns.jsonl (voice/latency.py).
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from halo_harness.voice.audio import FRAME_MS, RATE
from halo_harness.voice.latency import Card, line, record
from halo_harness.voice.speak import Speaker

START_FRAMES = 3
PREROLL = 8
END_SILENCE_MS = 250
PARTIAL_MS = 1000


def _thread(fn) -> None:
    threading.Thread(target=fn, name="halo-voice-stt", daemon=True).start()


def event(state: str, **data):
    from halo_harness.events import Event
    return Event("voice", {"state": state, **data})


class VoiceLoop:
    def __init__(self, controller, *, stt_url: str, tts_url: str, audio, vad, mode: str = "hands-free",
                 voice: str = "af_heart", budget_ms: int = 1500, state_dir=None, clock=time.perf_counter,
                 run: Optional[Callable] = None, end_silence_ms: int = END_SILENCE_MS, partial_ms: int = PARTIAL_MS,
                 sink: Optional[Callable] = None) -> None:
        self.c, self.stt_url, self.audio, self.vad, self.mode = controller, stt_url, audio, vad, mode
        self.budget_ms, self.state_dir, self.clock = budget_ms, state_dir, clock
        self.run = run or _thread
        self.end_silence_ms, self.partial_ms, self.sink = end_silence_ms, partial_ms, sink
        self.speaker = Speaker(tts_url=tts_url, voice=voice, audio=audio, post=self.post, done=self._done, clock=clock)
        self.talking = self.ptt_down = False
        self.voiced = self.quiet_ms = 0
        self.utt: list = []
        self.pre: list = []
        self.last_voice = self.started_at = self.last_partial = 0.0
        self.cards: list = []
        self.utterances = 0
        self.turns = threading.Event()
        self._stop = threading.Event()
        self._mic: Optional[threading.Thread] = None
        self.errors: list = []
        self.link: dict = {}  # 3.3.9.0 R3: {kind: {host, ms}} for a speech server on another halo (voice/remote.py)

    # ---- surface ---------------------------------------------------------------------------------------------
    def post(self, state: str, **data) -> None:
        try:
            self.c.events.put(event(state, **data))
        except Exception:
            pass
        if self.sink is not None:
            self.sink(state, data)

    def start(self, *, mic: bool = True) -> "VoiceLoop":
        self.c.add_event_tap(self.speaker.tap)
        if mic:
            self._mic = threading.Thread(target=self._listen, name="halo-voice-mic", daemon=True)
            self._mic.start()
        self.post("on", mode=self.mode)
        return self

    def stop(self) -> None:
        self._stop.set()
        try:
            self.c.remove_event_tap(self.speaker.tap)
        except Exception:
            pass
        self.speaker.cut()
        self.speaker.close()
        self.audio.close()
        self.post("off")

    def _listen(self) -> None:
        for frame in self.audio.frames():
            if self._stop.is_set():
                return
            self.on_frame(frame)

    # ---- the microphone --------------------------------------------------------------------------------------
    def on_frame(self, pcm: bytes) -> None:
        now = self.clock()
        if self.mode == "ptt":
            if self.ptt_down:
                self.utt.append(pcm)
                self.last_voice = now
            return
        if self.vad.is_speech(pcm):
            self.voiced += 1
            self.quiet_ms = 0
            self.last_voice = now
            if self.talking:
                self.utt.append(pcm)
            else:
                self.pre.append(pcm)
                if self.voiced == 1:
                    self.started_at = now
                if self.voiced >= START_FRAMES:
                    self.utt, self.pre = self.pre[-PREROLL:], []
                    self._begin(now)
        elif self.talking:
            self.utt.append(pcm)
            self.quiet_ms += FRAME_MS
            if self.quiet_ms >= self.end_silence_ms:
                self._end(now)
        else:
            self.voiced = 0
            self.pre = (self.pre + [pcm])[-PREROLL:]
        if self.talking and now - self.last_partial >= self.partial_ms / 1000.0:
            self.last_partial = now
            snap = b"".join(self.utt)
            self.run(lambda: self._partial(snap))

    def _begin(self, now: float) -> None:
        self.talking, self.quiet_ms, self.last_partial = True, 0, now
        if self.speaker.active():  # barge-in: the reply stops here, the rest is not spoken
            self.speaker.cut(steered=bool(getattr(getattr(self.c, "session", None), "busy", False)))
        self.post("listening")

    def _end(self, now: float) -> None:
        pcm, self.utt = b"".join(self.utt), []
        self.utterances += 1
        self.talking, self.voiced, self.quiet_ms = False, 0, 0
        card = Card(self.clock, self.budget_ms)
        card.link = dict(self.link)
        card.mark("spoke", self.last_voice)  # read as the frame arrived: the end of that speech
        card.mark("heard", now)
        self.run(lambda: self._utterance(pcm, card))

    def ptt(self) -> str:
        """Push-to-talk (Ctrl+Space, /voice ptt): press to talk, press again to send."""
        now = self.clock()
        if not self.ptt_down:
            self.ptt_down, self.utt = True, []
            if self.speaker.active():
                self.speaker.cut()
            self.post("listening", ptt=True)
            return "listening: press Ctrl+Space again to send"
        self.ptt_down = False
        self._end(now)
        return "sent to the speech-to-text server"

    def say_file(self, frames: list) -> None:
        """--input-file: the frames through the VAD; a file the VAD heard no speech in is sent whole."""
        before = self.utterances
        for f in frames:
            self.on_frame(f)
        if self.talking or self.ptt_down:
            self._end(self.clock())
        elif self.utterances == before:
            self.utt, self.last_voice = list(frames), self.clock()
            self._end(self.clock())

    # ---- the session -----------------------------------------------------------------------------------------
    def _partial(self, pcm: bytes) -> None:
        from halo_harness.voice.client import VoiceError, transcribe
        try:
            text = transcribe(self.stt_url, pcm, RATE)
        except VoiceError:
            return
        if text and self.talking:
            self.post("partial", text=text)

    def _utterance(self, pcm: bytes, card: Card) -> None:
        from halo_harness.voice.client import VoiceError, transcribe
        try:
            text = transcribe(self.stt_url, pcm, RATE)
        except VoiceError as e:
            self.errors.append(str(e))
            self.post("note", text=str(e))
            self.turns.set()
            return
        card.mark("text")
        if not text:
            self.post("note", text="heard nothing to send (the transcript was empty)")
            self.turns.set()
            return
        steer = bool(getattr(getattr(self.c, "session", None), "busy", False))
        card.steered = steer
        self.post("heard", text=text, steer=steer)
        self.speaker.begin(card)
        self.c.submit(text)

    def _done(self, card: Card) -> None:
        said = line(card)
        self.cards.append(card)
        if self.state_dir is not None:
            try:
                record(self.state_dir, card)
            except OSError:
                pass
        if "audio" in card.t or card.interrupted:
            self.post("card", text=said, row=card.row())
        self.turns.set()
