"""tests.test_voice_control -- Halo 3.3.9.0 R2: voice through the control socket and the `halo voice` entry points
(halo_harness/voice_loop_cli.py; Controller.run_slash's `voice` door, the way `/compact` arrives):

1. `halo voice on` reaches the one running session through its control socket (`slash voice on`): the speech servers
   start (the fake speech server through huggingface.voice_server_cmd), the loop runs on the fake microphone; `halo
   voice off` stops the loop and the servers it started;
2. without the extra the session answers with the one install line; no session, or several, is said with the command;
3. bare `halo voice` is `halo` with `/voice on` (voice.mode ptt: `/voice ptt`) -- the TUI is not started here;
4. `halo voice --input-file <wav> --output-file <wav>` drives one turn from a file: the echo, the reply, its card and
   the reply's audio as a WAV.
No audio device, no model, nothing leaves 127.0.0.1.
Run: python -m tests.test_voice_control
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.hf_local_env import FAKE_VOICE  # noqa: E402
from tests.helpers.remote_rig import Rig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.turn_session import text_step  # noqa: E402

test, TESTS = new_registry()
_FAKES = ("HALO_VOICE_AUDIO", "HALO_VOICE_ENGINE")


def _voice(*argv) -> "tuple[int, str]":
    from halo_harness.voice_cli import cmd_voice
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cmd_voice(list(argv))
    return code, out.getvalue()


@contextlib.contextmanager
def _fakes(**extra):
    saved = {k: os.environ.get(k) for k in _FAKES + tuple(extra)}
    os.environ.update(HALO_VOICE_AUDIO="fake", HALO_VOICE_ENGINE="fake", **extra)
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _register(rig) -> None:
    from halo_harness.remote.registry import make_entry, register
    register(make_entry(session_id=rig.handle.session_id, cwd=rig.cwd, endpoint=rig.server.endpoint,
                        token=rig.server.token))


def _speech_home() -> None:
    from halo_harness import theme
    from tests.helpers.voice_files import put
    models = Path(tempfile.mkdtemp(prefix="vl_models-"))
    for name in ("faster-whisper:small.en", "kokoro-82m"):
        put(models, name)
    theme.set_config_value("huggingface.model_dirs", [str(models)])
    theme.set_config_value("huggingface.voice_server_cmd", [sys.executable, str(FAKE_VOICE)])


@test
def test_on_and_off_through_the_control_socket(ctx: Ctx):
    from halo_harness.voice import session
    with Rig() as rig, _fakes(HALO_VOICE_FAKE_DEVICES="cpu"):
        _register(rig)
        _speech_home()
        code, out = _voice("on")
        ctx.check(f"halo voice on: the session started voice, got {code} {out!r}", code == 0
                  and "voice on (hands-free" in out and session.get(rig.controller) is not None)
        notes = [e for e in list(rig.controller.events.queue) if e is not None and e.kind == "voice"]
        ctx.check(f"the cost lines went to the session first, got {[e.data for e in notes][:3]}",
                  [e.data["text"][:13] for e in notes if e.data.get("state") == "note"] == ["starting stt:", "starting tts:"])
        ctx.check("the loop listens on the (fake) microphone", session.get(rig.controller)._mic is not None)
        code, out = _voice("off")
        ctx.check(f"halo voice off: the loop and its two servers stop, got {code} {out!r}", code == 0
                  and out.startswith("voice off") and out.count("stopped voice-") == 2 and session.get(rig.controller) is None)


@test
def test_the_one_lines(ctx: Ctx):
    from halo_harness.voice import INSTALL_LINE
    with Rig() as rig:
        code, out = _voice("on")
        ctx.check(f"no session registered: said with the command, got {code} {out!r}", code == 1
                  and "no running halo session here: halo voice opens one with voice on" in out)
        _register(rig)
        code, out = _voice("on")
        ctx.check(f"without the extra: the install line from the session, got {out!r}", code == 0 and INSTALL_LINE in out)
        code, out = _voice("on", "--session", "nosuch")
        ctx.check("an unknown --session", code == 1 and "no running halo session here" in out)


@test
def test_bare_halo_voice_is_halo_with_voice_on(ctx: Ctx):
    import halo_harness.cli as C
    from halo_harness import theme
    seen: list = []
    real = C.main
    C.main = lambda argv=None: seen.append(list(argv or [])) or 0
    try:
        with Rig(serve=False), _fakes():
            code, _out = _voice("--model", "or:mock/x")
            theme.set_config_value("voice.mode", "ptt")
            _voice()
    finally:
        C.main = real
    ctx.check(f"halo voice -> halo <flags> '/voice on'; ptt -> '/voice ptt', got {seen}", code == 0 and seen ==
              [["--model", "or:mock/x", "/voice on"], ["/voice ptt"]])


@test
def test_an_input_file_is_one_turn(ctx: Ctx):
    import halo_harness.tui.bootstrap as B
    from halo_harness import theme
    from halo_harness.voice.audio import tone
    from tests.helpers.voice_rig import VoiceRig
    d = Path(tempfile.mkdtemp(prefix="vl_file-"))
    wav, out_wav = d / "ask.wav", d / "reply.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(tone(500))
    with VoiceRig([text_step("The answer is short. That is all.")], transcripts=["what is the answer"]) as r:
        theme.set_config_value("huggingface.local_servers", [
            {"name": "stt", "url": r.stt_url, "voice": True}, {"name": "tts", "url": r.tts_url, "voice": True}])
        real = B.build_controller
        B.build_controller = lambda args: (r.controller, None, None)
        try:
            code, out = _voice("--input-file", str(wav), "--output-file", str(out_wav))
        finally:
            B.build_controller = real
        ctx.check(f"one turn: the echo, the reply, its card, got {code} {out!r}", code == 0
                  and "you said: what is the answer" in out and "reply: The answer is short. That is all." in out
                  and "\nvoice: " in out and f"the reply's audio: {out_wav}" in out)
        with wave.open(str(out_wav), "rb") as w:
            ctx.check("the reply's audio is a 24 kHz WAV of both sentences", w.getframerate() == 24000
                      and w.getnframes() == 2 * 960)
        ctx.check("the card is in turns.jsonl", json.loads((r.state / "voice" / "turns.jsonl").read_text().splitlines()[-1])
                  ["stages"]["audio"] is not None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
