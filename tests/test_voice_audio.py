"""tests.test_voice_audio -- Halo 3.3.9.0 R2: the microphone, the speaker and the VAD (halo_harness/voice/audio.py,
audio_fake.py, vad.py), with no device opened and no model loaded:

1. `halo voice devices` lists the inputs and outputs with the configured ones marked (voice.input_device by name or
   index); no microphone says so with the --input-file line; --json;
2. without sounddevice: the one install line (devices, doctor --voice's audio step, `/voice on`, bare `halo voice`,
   exit 2); the extra gains sounddevice (pyproject);
3. Audio.open under HALO_VOICE_AUDIO=fake is the fake: feed() frames out, play() captured, stop_output() cuts and
   stamps the clock; a WAV at another rate is 16 kHz frames plus the trailing quiet;
4. the VAD: the fake hears a tone and not silence; without silero-vad on disk a level gate stands in, said with the
   download line; the level gate's floor.
Run: python -m tests.test_voice_audio
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

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_VARS = ("HALO_VOICE_AUDIO", "HALO_VOICE_ENGINE", "HALO_VOICE_FAKE_INPUTS", "HALO_VOICE_FAKE_OUTPUTS", "BRIDGE_TEST_HOME")


@contextlib.contextmanager
def _env(**kw):
    saved = {k: os.environ.get(k) for k in _VARS}
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="vl_audio-")
    for k in _VARS[:4]:
        os.environ.pop(k, None)
    os.environ.update({k: str(v) for k, v in kw.items()})
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _voice(*argv) -> "tuple[int, str]":
    from halo_harness.voice_cli import cmd_voice
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cmd_voice(list(argv))
    return code, out.getvalue()


@test
def test_devices_lists_and_marks_the_configured_ones(ctx: Ctx):
    from halo_harness import theme
    with _env(HALO_VOICE_AUDIO="fake", HALO_VOICE_FAKE_INPUTS="laptop mic,USB headset",
              HALO_VOICE_FAKE_OUTPUTS="speakers,USB headset"):
        code, out = _voice("devices")
        ctx.check(f"both lists, the defaults marked, got {code} {out!r}", code == 0 and "inputs (voice.input_device):" in out
                  and "  *   0  laptop mic  (default)" in out and "outputs (voice.output_device):" in out)
        theme.set_config_value("voice.input_device", "headset")
        theme.set_config_value("voice.output_device", 1)
        _code, out = _voice("devices")
        ctx.check(f"the configured ones marked (by name, by index), got {out!r}", "  *   1  USB headset" in out
                  and out.count("  *   1  USB headset") == 2 and "  *   0  laptop mic" not in out)
        _code, raw = _voice("devices", "--json")
        got = json.loads(raw)
        ctx.check("--json carries the lists and the picks", got["input"]["name"] == "USB headset"
                  and len(got["outputs"]) == 2)
    with _env(HALO_VOICE_AUDIO="fake", HALO_VOICE_FAKE_INPUTS=""):
        _code, out = _voice("devices")
        ctx.check(f"no microphone: the --input-file line, got {out!r}",
                  "no microphone: halo voice --input-file <wav> drives one turn from a file" in out)


@test
def test_without_sounddevice_the_one_install_line(ctx: Ctx):
    from halo_harness.voice import INSTALL_LINE, audio
    with _env():
        ctx.check("sounddevice is not in the test venv", audio.missing() == ["sounddevice"])
        code, out = _voice("devices")
        ctx.check(f"devices: the install line, exit 2, got {code} {out!r}", code == 2 and INSTALL_LINE in out)
        code, out = _voice()
        ctx.check(f"bare halo voice: the install line, exit 2 (no TUI starts), got {code} {out!r}",
                  code == 2 and INSTALL_LINE in out and "sounddevice" in out)
        from halo_harness.doctor_voice import _audio
        ctx.check("doctor --voice's audio step", _audio()["level"] == "WARN" and INSTALL_LINE in _audio()["line"])
        from halo_harness.voice.session import on
        ok, lines = on(object())
        ctx.check(f"/voice on: the one line, got {lines}", ok is False and len(lines) == 1 and INSTALL_LINE in lines[0])
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    extra = text.split("voice = [", 1)[1].split("]", 1)[0]
    ctx.check("the extra gains sounddevice", '"sounddevice>=' in extra and '"faster-whisper>=' in extra)


@test
def test_the_fake_audio_seam(ctx: Ctx):
    from halo_harness.voice import audio
    from halo_harness.voice.audio_fake import FakeAudio
    with _env(HALO_VOICE_AUDIO="fake"):
        t = [5.0]
        a = audio.Audio.open()
        ctx.check("Audio.open is the fake under HALO_VOICE_AUDIO=fake", isinstance(a, FakeAudio))
        a = FakeAudio(clock=lambda: t[0])
        a.feed(audio.tone(100))
        frames = []
        for f in a.frames():
            frames.append(f)
            if len(frames) == 4:
                break
        ctx.check(f"100 ms is 4 frames of {audio.FRAME} samples, got {[len(f) for f in frames]}",
                  [len(f) for f in frames] == [audio.FRAME * 2] * 4)
        ctx.check("play() is captured", a.play(b"\1\0" * 10, 24000) and a.captured == [(24000, b"\1\0" * 10)])
        a.stop_output()
        ctx.check("a cut stops play() and stamps the clock", a.play(b"\0\0", 24000) is False and a.stopped_at == 5.0)
        a.resume_output()
        ctx.check("resume plays again", a.play(b"\0\0", 24000) is True)
        a.close()
    path = Path(tempfile.mkdtemp(prefix="vl_wav-")) / "x.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(audio.tone(500, rate=48000) * 2)
    frames = audio.wav_frames(path)
    ctx.check(f"a 48 kHz stereo WAV: 16 kHz frames plus 600 ms of quiet, got {len(frames)}",
              all(len(f) == audio.FRAME * 2 for f in frames) and 30 <= len(frames) <= 52)


@test
def test_the_vad(ctx: Ctx):
    from halo_harness.voice import audio, vad
    with _env(HALO_VOICE_ENGINE="fake"):
        v, line = vad.load()
        ctx.check("the fake VAD under the engine seam's flag", v.kind == "fake" and line is None)
        ctx.check("a tone is speech, silence is not", v.is_speech(audio.split(audio.tone(32))[0])
                  and not v.is_speech(audio.silence(32)))
    with _env():
        from halo_harness import theme
        theme.set_config_value("huggingface.model_dirs", [tempfile.mkdtemp(prefix="vl_models-")])
        v, line = vad.load()
        ctx.check(f"silero-vad not on disk: a level gate, said with the command, got {v.kind} {line!r}",
                  v.kind == "level" and line == "silero-vad is not present: a level gate stands in -- halo voice "
                                               "download silero-vad (0.002 GB)")
        quiet = audio.split(audio.tone(32, amp=200))[0]
        ctx.check("the level gate's floor: a whisper of noise is not speech", not v.is_speech(quiet)
                  and v.is_speech(audio.split(audio.tone(32))[0]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
