"""tests.helpers.voice_door_rig -- Halo 3.3.9.0 R3: a halo host with speech servers and a running session, and a peer
paired with it, in one process (tests/test_host_voice.py, test_voice_remote.py, test_voice_client.py).

    DoorRig(steps, transcripts=None, grants=("control",), cap="all", session=True, kinds=("stt", "tts"))
        -- `with DoorRig([...]) as r:` (`kinds`: the speech servers the host runs)
        r.rig        tests/helpers/host_act_rig.PeerRig: this process's home is the peer (bob@peer), the host runs on a
                     second scratch home whose local servers are the two speech servers below (its `servers` reader)
        r.stt_url / r.tts_url / r.info   tests/helpers/voice_rig.speech_servers: R1's real speech routes in process on
                     127.0.0.1:0 with fake engines (info counts the requests and keeps the texts spoken)
        r.controller a real Controller over a real Session whose replies are scripted on the mock OpenAI upstream, with
                     its control socket (ControllerHandle + ControlServer) registered in the HOST's run/sessions.json
        r.client()   the peer's HostClient for the host     r.wav(ms) -> a 16 kHz WAV of a tone (what the stt hears)
No model, no audio device, nothing leaves 127.0.0.1 (the host rig refuses a connect beyond it).
"""
from __future__ import annotations

import io
import json
import os
import wave

from tests.helpers.host_act_rig import PeerRig
from tests.helpers.voice_rig import speech_servers

MODEL = "or:mock/voice-door"


def wav(ms: int = 500, rate: int = 16000) -> bytes:
    from halo_harness.voice.audio import tone
    from halo_harness.voice.turn import resample
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(resample(tone(ms), 16000, rate))
    return buf.getvalue()


class DoorRig:
    def __init__(self, steps, *, transcripts=None, grants=("control",), cap: str = "all", session: bool = True,
                 kinds=("stt", "tts")) -> None:
        self.steps, self.transcripts, self.grants, self.cap, self.with_session = steps, transcripts, grants, cap, session
        self.kinds = kinds
        self.server = self.handle = self.controller = self.mock = None

    def __enter__(self) -> "DoorRig":
        from halo_harness.ollama_steward.servers_hf import Server, base
        self.stt_url, self.tts_url, self.info = speech_servers(self.transcripts)
        self.servers = [Server("stt", base(self.stt_url), "voice-stt", "halo", model="faster-whisper:small.en"),
                        Server("tts", base(self.tts_url), "voice-tts", "halo", model="kokoro-82m")]
        self.servers = [x for x in self.servers if x.name in self.kinds]
        self.rig = PeerRig(cap=self.cap, grants=self.grants, servers=self.servers).__enter__()
        if self.with_session:
            self.start_session()
        return self

    def start_session(self) -> None:
        from halo_harness.controller import Controller
        from halo_harness.fleet import identity
        from halo_harness.remote.control_socket import ControlServer
        from halo_harness.remote.handle import ControllerHandle
        from tests.helpers.mock_openai import SCENARIOS, MockUpstream
        from tests.helpers.turn_session import Calls, new_session
        home = os.environ["BRIDGE_TEST_HOME"]
        self.mock = MockUpstream().start()
        SCENARIOS[MODEL.split("/", 1)[1]] = Calls(self.steps)
        session = new_session(mock=self.mock, model=MODEL)
        os.environ["BRIDGE_TEST_HOME"] = home  # new_session scopes a home of its own: the peer's stays this process's
        identity.forget_cache()
        self.controller = Controller(session=session, cwd=session.cwd)
        self.controller.start()
        self.handle = ControllerHandle(self.controller)
        self.handle.attach()
        self.server = ControlServer(self.handle).start()
        self.register()

    def register(self, extra: list = ()) -> None:
        run = self.rig.home / "run"
        run.mkdir(parents=True, exist_ok=True)
        rows = [{"session_id": self.handle.session_id, "cwd": str(self.controller.cwd), "pid": os.getpid(),
                 "endpoint": self.server.endpoint, "token": self.server.token, "kind": "tui", "title": "the host's session"}]
        (run / "sessions.json").write_text(json.dumps({"version": 1, "sessions": rows + list(extra)}), encoding="utf-8")

    def client(self):
        return self.rig.client()

    def __exit__(self, *exc) -> None:
        try:
            if self.server is not None:
                self.server.close()
            if self.handle is not None:
                self.handle.detach()
            if self.controller is not None:
                self.controller.quit()
        finally:
            for s in self.info["servers"]:
                s.shutdown()
            if self.mock is not None:
                self.mock.stop()
            self.rig.__exit__(*exc)
