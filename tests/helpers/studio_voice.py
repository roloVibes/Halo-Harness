"""tests.helpers.studio_voice -- Studio's Local -> Voice (Halo 3.3.9.0 R3) in headless Chrome with Chrome's FAKE media
device (`--use-fake-device-for-media-stream --use-fake-ui-for-media-stream --use-file-for-fake-audio-capture=<a tone
WAV>`, added through chrome_driver.EXTRA_FLAGS in this driver's process only): no real microphone is opened, no model
loads, nothing leaves 127.0.0.1 (a connect beyond it is refused and recorded in `blocked`).

The scoped home: the stt server runs in process (R1's routes, a fake engine: "what is in the readme"), the tts server
is stopped and starts from Talk through `huggingface.voice_server_cmd` (tests/helpers/fake_voice_server.py, the fake
engine's 500 ms sine per sentence); a real Controller with one scripted reply sits behind its control socket in the
home's sessions registry.

`servers`: the two rows (stt running, tts stopped with its cost line), the catalog's seven rows, a download's size line
(not pressed further), the glasses note, Talk's title -- all read before Talk changes them.
`talk`: Talk's confirm text, Start talking (the fake microphone records), Send; the transcript, the reply, the sink's
bytes, the card's line, the turn in the list, tts now running.
`stop`: the tts row's Stop -> stopped.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import os
import socket
import sys
import tempfile
import time
import wave
from contextlib import ExitStack, contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers import chrome_driver  # noqa: E402
from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_local import PAGE  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_settings import press  # noqa: E402

SRV, CAT, TURN = "[data-testid=voice-server]", "[data-testid=voice-catalog-row]", "[data-testid=voice-turn]"
TALK, SINK = q("[data-testid=voice-talk]"), q("[data-testid=voice-talk-sink]")
REPLY = "The readme says hello. That is all."
FLAGS = ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"]


def _row(kind: str, inner: str) -> str:
    return q(f"{SRV}[data-kind={kind}] {inner}".strip())


def servers(c, url, ctx) -> dict:
    c.go(f"{ctx['base']}?mode=local&page=voice&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'voice'", 40)
    rows = (f"{qa(SRV)}.map((r) => [r.dataset.kind, r.dataset.state, r.querySelector('[data-testid=voice-server-model]')"
            f".textContent, r.querySelector('[data-testid=voice-server-line]').textContent])")
    out = {"servers": c.wait(f"{qa(SRV)}.length === 2 && {rows}", 40)}
    out["catalog"] = c.wait(f"{qa(CAT)}.length === 7 && {qa(CAT)}.map((r) => [r.dataset.name, r.dataset.present || ''])", 20)
    press(c, q(f"{CAT}[data-name='faster-whisper:base.en'] [data-testid=voice-catalog-download]"),
          f"!!{q('[data-testid=voice-download-confirm]')}")
    out["size"] = c.wait(f"{q('[data-testid=voice-download-confirm]')}?.textContent", 15)
    out["note"] = c.wait(f"{q('[data-testid=voice-glasses-note]')}?.textContent", 15)
    out["talk_title"] = c.wait(f"{TALK}?.title", 15)
    out["sessions"] = c.wait(f"{qa('[data-testid=voice-session-select] option')}.length === 1 && "
                             f"{qa('[data-testid=voice-session-select] option')}.length", 15)
    out["dialogs"] = c.js("document.querySelectorAll('[role=dialog]').length")
    return out


def talk(c, url, ctx) -> dict:
    press(c, TALK, f"!!{q('[data-testid=voice-talk-confirm]')}")
    out = {"confirm": c.wait(f"{q('[data-testid=voice-talk-confirm]')}?.textContent", 15)}
    press(c, q("[data-testid=voice-talk-go]"), f"{TALK}?.dataset.state === 'recording'")
    time.sleep(1.5)  # the fake microphone plays its WAV into the recorder
    press(c, TALK, f"{TALK}?.dataset.state !== 'recording'")
    out["transcript"] = c.wait(f"{q('[data-testid=voice-talk-transcript]')}?.textContent", 40)
    out["seconds"] = c.wait(f"Number({TALK}?.dataset.seconds) > 0 && Number({TALK}.dataset.seconds)", 15)
    out["reply"] = c.wait(f"{TALK}.dataset.state === 'done' && {q('[data-testid=voice-talk-reply]')}?.textContent", 40)
    out["sink"] = c.wait(f"Number({SINK}?.dataset.bytes) >= 48000 && Number({SINK}.dataset.bytes)", 20)
    out["line"] = c.wait(f"{q('[data-testid=voice-talk-line]')}?.textContent", 15)
    out["notes"] = c.js(f"{qa('[data-testid=voice-talk-note]')}.map((n) => n.textContent)")
    out["turns"] = c.wait(f"{qa(TURN)}.length === 1 && {qa(TURN)}.map((t) => [t.dataset.via, t.textContent])", 30)
    out["tts"] = c.wait(f"{_row('tts', '')}?.dataset.state === 'running' && {_row('tts', '')}.dataset.state", 30)
    out["error"] = c.js(f"{q('[data-testid=voice-talk-error]')}?.textContent || ''")
    return out


def stop(c, url, ctx) -> dict:
    press(c, _row("tts", "[data-testid=voice-server-stop]"), f"{_row('tts', '')}?.dataset.state === 'stopped'")
    return {"after_stop": c.wait(f"{_row('tts', '')}?.dataset.state === 'stopped' && {qa(SRV)}.map((r) => r.dataset.state)", 20),
            "stop_said": c.wait(f"{_row('tts', '[data-testid=voice-server-said]')}?.textContent", 15)}


def _wav(path: Path) -> Path:
    from halo_harness.voice.audio import tone
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(tone(2000))
    return path


class VoiceDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    def __init__(self, argv=None, **kw):
        super().__init__(argv, **kw)
        self.tmp = Path(tempfile.mkdtemp(prefix="vg_studio-"))
        chrome_driver.EXTRA_FLAGS[:] = FLAGS + [f"--use-file-for-fake-audio-capture={_wav(self.tmp / 'ask.wav')}"]

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness import theme
        from halo_harness.config.paths import bridge_home
        from tests.helpers.hf_local_env import FAKE_VOICE
        from tests.helpers.voice_files import put
        from tests.helpers.voice_rig import speech_servers
        home = bridge_home()
        os.environ.update(BRIDGE_TEST_NO_BACKGROUND_NET="1", OLLAMA_HOST="http://127.0.0.1:9")
        blocked, real = [], socket.create_connection

        def guard(address, *a, **kw):
            if str(address[0]) not in ("127.0.0.1", "localhost", "::1"):
                blocked.append(str(address))
                raise OSError(f"the voice driver keeps every request on 127.0.0.1 (asked {address[0]})")
            return real(address, *a, **kw)
        socket.create_connection = guard
        models = self.tmp / "models"
        for name in ("faster-whisper:small.en", "kokoro-82m"):
            put(models, name)
        stt_url, _tts, info = speech_servers(["what is in the readme"])
        theme.set_config_value("huggingface.model_dirs", [str(models)])
        theme.set_config_value("huggingface.voice_server_cmd", [sys.executable, str(FAKE_VOICE)])
        theme.set_config_value("huggingface.local_servers", [{"name": "stt", "url": stt_url, "voice": True}])
        with ExitStack() as stack:
            ses = stack.enter_context(_Session(home))
            srv, url = serve(home, True)
            base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
            ctx = {"base": base, "frag": frag, "info": info}
            try:
                yield tuple((fn, (c, url, ctx)) for fn in (servers, talk, stop))
            finally:
                self.out["blocked"] = blocked
                self.out["stt_requests"] = info["stt"]["n"]
                self.out["session_turns"] = ses.mock_calls()
                from halo_harness.providers.local_server import stop as stop_server
                stop_server("tts", state_dir=home)  # the one Talk started, if the Stop step did not run
                srv.shutdown()
                srv.server_close()
                for s in info["servers"]:
                    s.shutdown()
                socket.create_connection = real


class _Session:
    """A real Controller with one scripted reply behind its control socket, registered in `home`'s sessions."""

    def __init__(self, home: Path) -> None:
        self.home = home

    def __enter__(self) -> "_Session":
        from halo_harness.controller import Controller
        from halo_harness.remote.control_socket import ControlServer
        from halo_harness.remote.handle import ControllerHandle
        from halo_harness.remote.registry import make_entry, register
        from tests.helpers.mock_openai import SCENARIOS, MockUpstream
        from tests.helpers.turn_session import Calls, new_session, text_step
        keep = os.environ.get("BRIDGE_TEST_HOME")
        self.mock = MockUpstream().start()
        self.calls = Calls([text_step(REPLY)])
        SCENARIOS["voice-talk"] = self.calls
        session = new_session(mock=self.mock, model="or:mock/voice-talk")
        os.environ["BRIDGE_TEST_HOME"] = keep or ""  # new_session scoped a home of its own: Studio's stays this one
        self.controller = Controller(session=session, cwd=session.cwd)
        self.controller.start()
        self.handle = ControllerHandle(self.controller)
        self.handle.attach()
        self.server = ControlServer(self.handle).start()
        register(make_entry(session_id=self.handle.session_id, cwd=session.cwd, endpoint=self.server.endpoint,
                            token=self.server.token))
        return self

    def mock_calls(self) -> int:
        return self.calls.n

    def __exit__(self, *exc) -> None:
        for fn in (self.server.close, self.handle.detach, self.controller.quit, self.mock.stop):
            try:
                fn()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(VoiceDriver(sys.argv[1:]).main())
