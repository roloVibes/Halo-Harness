"""halo_harness.voice_client_cli -- `halo voice client`: the reference client of a halo host's voice door (Halo 3.3.9.0
R3; docs/COMMANDS-voice.md, docs/VOICE-glasses.md). What a phone app for the glasses has to do, from any halo:

    halo voice client --host <h> [--input-file x.wav | --mic] [--session ID] [--voice NAME] [--output-file reply.wav]
                      [--json]
        one utterance (a WAV, or the microphone until a 250 ms pause, up to 30 s) -> POST /host/v1/voice/turn on the
        paired host <h> (the `control` grant there) -> "you said: ...", the reply's audio played (or written to
        --output-file) as it streams, "reply: ...", the latency card from the host's side

The host runs the stt server, the session and the tts server; this side records and plays. --mic needs the voice extra
(sounddevice); --input-file needs nothing extra.
"""

from __future__ import annotations

import argparse
import json
import wave

MIC_MAX_S = 30.0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo voice client", description="One voice turn through a halo host's voice door.")
    p.add_argument("--host", required=True, help="the paired halo host (its name, e.g. pc)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--input-file", help="a 16-bit PCM WAV (any rate from 8 to 48 kHz, mono or the first channel)")
    src.add_argument("--mic", action="store_true", help="record one utterance from the microphone (the voice extra)")
    p.add_argument("--session", default="", help="the session there (its id or its start); default: the one running")
    p.add_argument("--voice", default="", help="the TTS voice (default: the host's voice.tts_voice)")
    p.add_argument("--output-file", default="", help="write the reply's audio as a WAV instead of playing it")
    p.add_argument("--json", action="store_true", help="the trailer as JSON")
    return p


def record(audio, vad, end_silence_ms: int = 250, max_s: float = MIC_MAX_S) -> bytes:
    """One utterance from the microphone: from the first voiced frame to `end_silence_ms` of quiet (or max_s)."""
    from halo_harness.voice.audio import FRAME_MS
    got, quiet, voiced = [], 0, False
    for f in audio.frames():
        speech = vad.is_speech(f)
        if speech:
            voiced, quiet = True, 0
        if voiced:
            got.append(f)
            quiet = 0 if speech else quiet + FRAME_MS
            if quiet >= end_silence_ms or len(got) * FRAME_MS >= max_s * 1000:
                break
    return b"".join(got)


def _body(a) -> "tuple[bytes, str, object]":
    if a.input_file:
        with open(a.input_file, "rb") as f:
            return f.read(), "audio/wav", None
    from halo_harness.voice import INSTALL_LINE, audio
    if audio.missing():
        raise SystemExit(f"--mic needs the voice extra (sounddevice): {INSTALL_LINE}; --input-file <wav> needs nothing")
    from halo_harness.voice.vad import load
    vad, _line = load()
    dev = audio.Audio.open()
    print("listening: speak, and a pause of 250 ms sends it")
    pcm = record(dev, vad)
    return pcm, "audio/pcm;rate=16000", dev


def main(argv: list) -> int:
    from halo_harness.voice import remote
    from halo_harness.voice.client import VoiceError
    a = _parser().parse_args(argv)
    c, why = remote.client_for(a.host)
    if c is None:
        print(why)
        return 1
    try:
        body, ctype, dev = _body(a)
    except SystemExit as e:
        print(e)
        return 2
    except OSError as e:
        print(f"the input did not open: {e}")
        return 1
    pcm, trailer, rate = [], {}, 24000
    try:
        for kind, payload in remote.turn(c, body, ctype, session=a.session, voice=a.voice):
            if kind == "J" and "heard" in payload:
                print(f"you said: {payload['heard']}", flush=True)
            elif kind == "J" and "rate" in payload and not payload.get("done"):
                rate = int(payload["rate"])
            elif kind == "J":
                trailer, rate = payload, int(payload.get("rate") or rate)
            elif kind == "N" and payload.get("note"):
                print(payload["note"])
            elif kind == "A":
                pcm.append(payload)
                if not a.output_file:
                    dev = _play(dev, payload, rate)
    except VoiceError as e:
        print(str(e))
        return 1
    if trailer.get("error"):
        print(trailer["error"])
        return 1
    if a.output_file:
        with wave.open(a.output_file, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"".join(pcm))
    if a.json:
        print(json.dumps(trailer, indent=2))
        return 0
    print(f"reply: {trailer.get('reply') or ''}")
    if trailer.get("line"):
        print(f"{trailer['line']} (measured on {a.host}; the LAN to it is extra)")
    if a.output_file:
        print(f"the reply's audio: {a.output_file} ({sum(len(x) for x in pcm):,} bytes at {rate:,} Hz)")
    return 0


def _play(dev, chunk: bytes, rate: int):
    """The speaker, opened on the first chunk; without the extra the audio is not played (--output-file keeps it)."""
    from halo_harness.voice import audio
    if dev is None:
        if audio.missing():
            return False
        dev = audio.Audio.open(input=False)
    if dev is not False:
        dev.play(chunk, rate)
    return dev
