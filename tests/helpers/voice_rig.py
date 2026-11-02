"""tests.helpers.voice_rig -- Halo 3.3.9.0 R2: the voice loop's test rig (tests/test_voice_loop.py, test_voice_bundle,
test_voice_control). Nothing opens an audio device, nothing loads a model, nothing leaves 127.0.0.1:

    speech_servers(transcripts=None) -> (stt_url, tts_url, info)   R1's real speech routes (voice/server_routes.py) in
        process on 127.0.0.1:0, the fake engine behind them; `transcripts` (a list) are the STT's answers in turn (the
        last repeats); info["stt"] / ["tts"] count the requests and keep the texts spoken
    VoiceRig(steps) -- `with VoiceRig([...]) as r:` a real Controller over a real Session (tests/helpers/turn_session)
        whose model replies are scripted on the mock OpenAI upstream; r.controller, r.state, r.audio (FakeAudio),
        r.loop(**kw) -> a started VoiceLoop on the rig's servers (a synchronous `run`, the fake VAD), r.clock (a fake
        clock: r.tick(ms) moves it), r.events (every event the session's sink carried), r.wait(pred) (re-checked at
        each event: no sleep)
    gated(chunks_a, gate, chunks_b) -> a scenario that streams chunks_a, waits for `gate` (a threading.Event), then
        streams chunks_b: a turn that is still running while the test speaks again
    talk(loop, ms=300, quiet=320) -> feeds one utterance (the fake VAD hears tone() as speech) frame by frame, the fake
        clock moving 32 ms a frame
HALO_VOICE_ENGINE=fake and HALO_VOICE_AUDIO=fake are set for the rig's life and restored after.
"""
from __future__ import annotations

import os
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from tests.helpers.mock_openai import end_sse, start_sse, write_sse_chunk

_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "HALO_VOICE_ENGINE", "HALO_VOICE_AUDIO", "HALO_VOICE_FAKE_MS")


class _Http(ThreadingHTTPServer):
    daemon_threads = True


class _Stt:
    kind, sample_rate, compute = "stt", 16000, "int8"

    def __init__(self, texts, info):
        self.texts, self.info = list(texts), info

    def transcribe(self, pcm16, rate):
        self.info["n"] += 1
        text = self.texts[min(self.info["n"] - 1, len(self.texts) - 1)]
        return [{"start": 0.0, "end": round(len(pcm16) / 2 / rate, 2), "text": text}]


class _Tts:
    kind, sample_rate, compute = "tts", 24000, "fp32"

    def __init__(self, info):
        self.info = info

    def speak(self, text, voice):
        from halo_harness.voice.engine_fake import sine
        self.info["n"] += 1
        self.info["said"].append(text)
        yield sine(40, self.sample_rate)


def speech_servers(transcripts=None):
    from halo_harness.voice.server_routes import State, make_handler
    from halo_harness.voice.engine_fake import TRANSCRIPT
    info = {"stt": {"n": 0}, "tts": {"n": 0, "said": []}, "servers": []}
    urls = []
    for kind, engine in (("stt", _Stt(transcripts or [TRANSCRIPT], info["stt"])), ("tts", _Tts(info["tts"]))):
        st = State(kind, "faster-whisper:small.en" if kind == "stt" else "kokoro-82m", "cpu", lambda _l: None, "af_heart")
        st.engine, st.status = engine, "ok"
        httpd = _Http(("127.0.0.1", 0), make_handler(st))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        info["servers"].append(httpd)
        urls.append(f"http://127.0.0.1:{httpd.server_address[1]}/v1")
    return urls[0], urls[1], info


def gated(chunks_a: list, gate: threading.Event, chunks_b: list, *, hold_s: float = 10.0):
    def scn(h, body):
        start_sse(h)
        for c in chunks_a:
            write_sse_chunk(h, None, c)
        gate.wait(hold_s)
        for c in chunks_b:
            write_sse_chunk(h, None, c)
        write_sse_chunk(h, None, "[DONE]")
        end_sse(h)
    return scn


def text_chunks(*pieces, stop: bool = True) -> list:
    out = [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]}]
    out += [{"choices": [{"index": 0, "delta": {"content": p}}]} for p in pieces]
    if stop:
        out.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
    return out


class VoiceRig:
    def __init__(self, scenario, *, model: str = "or:mock/voice-loop", transcripts=None, hold: bool = False) -> None:
        self.scenario, self.model, self.transcripts, self.hold = scenario, model, transcripts, hold
        self.t = [1000.0]
        self.events: list = []
        self.cv = threading.Condition()

    def _tap(self, ev) -> None:
        with self.cv:
            self.events.append(ev)
            self.cv.notify_all()

    def wait(self, pred, timeout: float = 10.0) -> bool:
        """Until pred() holds (re-read at every event the session's sink carries), or the timeout."""
        with self.cv:
            return bool(self.cv.wait_for(pred, timeout))

    def kinds(self) -> list:
        return [e.kind for e in list(self.events)]

    def clock(self) -> float:
        return self.t[0]

    def tick(self, ms: float) -> None:
        self.t[0] += ms / 1000.0

    def __enter__(self) -> "VoiceRig":
        from halo_harness.controller import Controller
        from tests.helpers.mock_openai import MockUpstream, SCENARIOS
        from tests.helpers.turn_session import Calls, new_session
        self._saved = {k: os.environ.get(k) for k in _VARS}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ.update(HALO_VOICE_ENGINE="fake", HALO_VOICE_AUDIO="fake")
        self.mock = MockUpstream().start()
        SCENARIOS[self.model.split("/", 1)[1]] = self.scenario if callable(self.scenario) else Calls(self.scenario)
        self.session = new_session(mock=self.mock, model=self.model)
        self.state = Path(tempfile.mkdtemp(prefix="vl_state-"))
        self.controller = Controller(session=self.session, cwd=self.session.cwd, state_dir=self.state)
        self.controller.add_event_tap(self._tap)
        self.controller.start()
        self.stt_url, self.tts_url, self.info = speech_servers(self.transcripts)
        from halo_harness.voice.audio_fake import FakeAudio
        self.audio = FakeAudio(hold=self.hold, clock=self.clock)
        self.loops: list = []
        return self

    def loop(self, **kw):
        from halo_harness.voice.loop import VoiceLoop
        from halo_harness.voice.vad import Fake
        args = dict(stt_url=self.stt_url, tts_url=self.tts_url, audio=self.audio, vad=Fake(), clock=self.clock,
                    run=lambda fn: fn(), state_dir=self.state, budget_ms=1500)
        args.update(kw)
        loop = VoiceLoop(self.controller, **args).start(mic=False)
        self.loops.append(loop)
        return loop

    def voice(self, state: str) -> list:
        return [e.data for e in self.events if e.kind == "voice" and e.data.get("state") == state]

    def __exit__(self, *exc) -> None:
        for loop in self.loops:
            try:
                loop.stop()
            except Exception:
                pass
        try:
            self.controller.quit()
        finally:
            for s in self.info["servers"]:
                s.shutdown()
            self.mock.stop()
            for k, v in self._saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def talk(rig, loop, ms: int = 300, quiet: int = 320) -> float:
    """One utterance, frame by frame; returns the fake clock at its first voiced frame."""
    from halo_harness.voice.audio import FRAME_MS, silence, split, tone
    first = None
    for f in split(tone(ms)):
        rig.tick(FRAME_MS)
        first = rig.clock() if first is None else first
        loop.on_frame(f)
    for f in split(silence(quiet)):
        rig.tick(FRAME_MS)
        loop.on_frame(f)
    return first
