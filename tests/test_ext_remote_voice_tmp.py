"""tests.test_ext_remote_voice_tmp -- a converted voice note never stays in the temp folder (Halo 3.3.14.0 R2, REVIEW #29
REMOTE-4 / PACKS-7; halo_harness/ext/remote.py `transcribe` / `_wav`): with a stand-in ffmpeg (it writes the WAV) and a
stand-in speech server, a transcribed note, a note the server could not read and a note ffmpeg could not convert each
leave no halo-voice-* folder behind. No program and no server runs.
Run: python -m tests.test_ext_remote_voice_tmp"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_no_converted_note_is_left_behind(ctx: Ctx):
    from halo_harness.ext import remote as R
    from halo_harness.voice import client, ensure, turn
    scratch = Path(tempfile.mkdtemp(prefix="voice-tmp-test-"))
    note = scratch / "note.m4a"
    note.write_bytes(b"\x00\x01")
    outcome = {"rc": 0}

    def run(argv, **_kw):
        if outcome["rc"] == 0:
            Path(argv[-1]).write_bytes(b"RIFF....WAVE")
        return SimpleNamespace(returncode=outcome["rc"])
    saved = (R.shutil, R.subprocess, R.tempfile, ensure.running, turn.pcm_of, client.transcribe)
    R.shutil = SimpleNamespace(which=lambda name: "ffmpeg", rmtree=shutil.rmtree)
    R.subprocess = SimpleNamespace(run=run, SubprocessError=subprocess.SubprocessError)
    R.tempfile = SimpleNamespace(mkdtemp=lambda prefix="": tempfile.mkdtemp(prefix=prefix, dir=str(scratch)))
    ensure.running = lambda kind: "http://127.0.0.1:9/v1"
    turn.pcm_of = lambda data, ctype: (b"\x00\x00", 0.1)
    heard = {"text": "make it blue"}

    def fake_transcribe(url, pcm):
        if heard["text"] is None:
            raise RuntimeError("the speech server answered 500")
        return heard["text"]
    client.transcribe = fake_transcribe
    left = lambda: [p.name for p in scratch.glob("halo-voice-*")]  # noqa: E731
    try:
        got = R.transcribe(note)
        ctx.check(f"transcribed, got {got}", got[0] == "make it blue")
        ctx.check(f"no converted folder left, got {left()}", left() == [])
        heard["text"] = None
        got = R.transcribe(note)
        ctx.check(f"a server error is one line, got {got}", got[0] is None and "could not be transcribed" in got[1])
        ctx.check(f"and leaves nothing, got {left()}", left() == [])
        outcome["rc"] = 1
        got = R.transcribe(note)
        ctx.check(f"ffmpeg failing is one line, got {got}", got[0] is None and "did not convert" in got[1])
        ctx.check(f"and leaves nothing, got {left()}", left() == [])
        ctx.check("the phone's own file is the inbox's to delete", note.exists())
    finally:
        R.shutil, R.subprocess, R.tempfile, ensure.running, turn.pcm_of, client.transcribe = saved
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
