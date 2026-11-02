"""tests.test_voice_client -- Halo 3.3.9.0 R3: `halo voice client`, the voice door's reference client
(halo_harness/voice_client_cli.py), against tests/helpers/voice_door_rig.DoorRig's host:

1. `--host pc --input-file ask.wav --output-file reply.wav`: "you said: ...", "reply: ...", the card's line measured on
   the host, the reply's audio as a 24 kHz WAV of both sentences; `--json` prints the trailer;
2. the one lines: no paired host of that name (exit 1, the pair commands), no session there (exit 1, the host's line),
   `--mic` without the voice extra (exit 2, the install line; --input-file named);
3. `--mic`'s recorder: one utterance from the first voiced frame to 250 ms of quiet (the fake microphone, the fake VAD).
No model, no audio device, nothing leaves 127.0.0.1.
Run: python -m tests.test_voice_client
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.turn_session import text_step  # noqa: E402
from tests.helpers.voice_door_rig import DoorRig, wav  # noqa: E402

test, TESTS = new_registry()
REPLY = "The door works. Here is the reply."


def _client(*argv) -> "tuple[int, str]":
    from halo_harness.voice_cli import cmd_voice
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        code = cmd_voice(["client", *argv])
    return code, out.getvalue()


def _ask() -> Path:
    d = Path(tempfile.mkdtemp(prefix="vg_client-"))
    (d / "ask.wav").write_bytes(wav(600))
    return d


@test
def test_one_turn_from_a_file(ctx: Ctx):
    d = _ask()
    with DoorRig([text_step(REPLY)], transcripts=["does the door work"]) as r:
        code, out = _client("--host", "pc", "--input-file", str(d / "ask.wav"), "--output-file", str(d / "reply.wav"))
        ctx.check(f"you said, the reply, the card from the host, the file, got {code} {out!r}", code == 0
                  and out.startswith("you said: does the door work\n") and f"reply: {REPLY}" in out
                  and "(measured on pc; the LAN to it is extra)" in out and f"the reply's audio: {d / 'reply.wav'}" in out)
        with wave.open(str(d / "reply.wav"), "rb") as w:
            ctx.check("the reply's audio is a 24 kHz WAV of both sentences", w.getframerate() == 24000
                      and w.getnframes() == 2 * 960)
        code, out = _client("--host", "pc-host", "--input-file", str(d / "ask.wav"), "--output-file", str(d / "r2.wav"),
                            "--json")
        t = json.loads(out[out.index("{"):]) if "{" in out else {}
        ctx.check(f"--json: the trailer, got {code} {t}", code == 0 and t.get("done") is True and t.get("reply") == REPLY)
        ctx.check("two turns, two audit rows by op", len(r.rig.rig.audit_rows(2, op="voice_turn")) == 2)


@test
def test_the_one_lines(ctx: Ctx):
    from halo_harness.voice import INSTALL_LINE, audio
    d = _ask()
    with DoorRig([text_step("x")], session=False):
        code, out = _client("--host", "mac", "--input-file", str(d / "ask.wav"))
        ctx.check(f"no paired host named mac, got {code} {out!r}", code == 1
                  and out.startswith("no paired halo host named mac: on mac, `halo host serve`"))
        code, out = _client("--host", "pc", "--input-file", str(d / "ask.wav"))
        ctx.check(f"no session there: the host's line, got {code} {out!r}", code == 1
                  and "no running halo session on pc-host" in out)
        real = audio.missing
        audio.missing = lambda: ["sounddevice"]
        try:
            code, out = _client("--host", "pc", "--mic")
        finally:
            audio.missing = real
        ctx.check(f"--mic without the extra: the install line, got {code} {out!r}", code == 2 and INSTALL_LINE in out
                  and "--input-file <wav> needs nothing" in out)


@test
def test_the_mic_recorder_takes_one_utterance(ctx: Ctx):
    from halo_harness.voice.audio import FRAME, silence, tone
    from halo_harness.voice.audio_fake import FakeAudio
    from halo_harness.voice.vad import Fake
    from halo_harness.voice_client_cli import record
    mic = FakeAudio()
    mic.feed(silence(192) + tone(320) + silence(400) + tone(320))  # whole 32 ms frames
    pcm = record(mic, Fake())
    ctx.check(f"from the first voiced frame to 250 ms of quiet, got {len(pcm)} bytes", len(pcm) == 2 * FRAME * (10 + 8))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
