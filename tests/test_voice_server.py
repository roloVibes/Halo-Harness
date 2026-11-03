"""tests.test_voice_server -- Halo 3.3.9.0 R1: Halo's own speech server (halo_harness/voice/server.py,
server_routes.py, engines.py, engine_fake.py) with the fake engine (HALO_VOICE_ENGINE=fake) on 127.0.0.1:0:

1. STT: `listening on 127.0.0.1:<port>`, /health ok with the device and the model, /v1/models the one model; 16 kHz
   PCM16 (raw and a multipart WAV) -> the fixed transcript with its segments, duration and ms; response_format text;
2. TTS: text -> N ms of PCM16 per sentence at 24 kHz (streamed pcm), and a whole WAV;
3. the log holds the listening line, the load line and one line per request, each parsed back by voice/log_lines;
4. a route of the other kind is a 404 naming it; a body that is not audio is a 400 with the formats;
5. a missing extra: the one install line and exit 2 (a monkeypatched import); a declared model: its one line, exit 2;
   a failed load: the log's `voice load failed:` line and exit 1.
No real engine is imported, no model loads.
Run: python -m tests.test_voice_server
"""
from __future__ import annotations

import contextlib
import io
import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent


@contextlib.contextmanager
def _server(model: str, **env):
    from tests.helpers.voice_files import voice_env
    root = Path(tempfile.mkdtemp(prefix="vs_server-"))
    log = root / "voice.log"
    e = voice_env(BRIDGE_TEST_HOME=str(root), PYTHONPATH=str(REPO), **env)
    p = subprocess.Popen([sys.executable, "-m", "halo_harness.voice.server", "--model", model, "--device", "cpu",
                          "--port", "0", "--log", str(log)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         env=e, cwd=str(root))
    got: list = []
    t = threading.Thread(target=lambda: got.append(p.stdout.readline()), daemon=True)
    t.start()
    t.join(30)
    try:
        line = (got or [""])[0].strip()
        port = int(line.rsplit(":", 1)[1]) if line.startswith("listening on 127.0.0.1:") else None
        end = time.monotonic() + 20
        while port and time.monotonic() < end:
            if _get(port, "/health")[0] == 200:
                break
            time.sleep(0.05)
        yield {"port": port, "line": line, "log": log, "proc": p}
    finally:
        p.terminate()
        p.wait(10)


def _get(port: int, path: str):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except (OSError, ValueError, http.client.HTTPException):  # the error body cut by the exit: IncompleteRead
            return e.code, {}  # raised from e.read() here, not from urlopen (Linux shard 2, run 41572679224)
    except (OSError, ValueError, http.client.HTTPException):  # a server that exits mid-reply (a failed load) reads as
        return 0, {}  # not up: IncompleteRead is an HTTPException, not an OSError (Linux shard 0, run 41524830561)


def _post(port: int, path: str, body: bytes, ctype: str):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body, headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def _wav(pcm: bytes, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


@test
def test_stt_answers_the_openai_shape(ctx: Ctx):
    from halo_harness.voice.engine_fake import TRANSCRIPT
    with _server("faster-whisper:small.en") as s:
        ctx.check(f"listening on a free loopback port, got {s['line']!r}", s["port"] is not None)
        code, body = _get(s["port"], "/health")
        ctx.check(f"health ok, got {code} {body}", code == 200 and body == {"status": "ok", "device": "cpu",
                                                                          "model": "faster-whisper:small.en", "kind": "stt"})
        code, body = _get(s["port"], "/v1/models")
        ctx.check(f"the one model, got {body}", code == 200 and [m["id"] for m in body["data"]] == ["faster-whisper:small.en"])
        pcm = b"\x00\x01" * 16000 * 3
        code, _h, raw = _post(s["port"], "/v1/audio/transcriptions", pcm, "audio/pcm;rate=16000")
        got = json.loads(raw)
        ctx.check(f"raw PCM: the transcript, 3 s, got {code} {got}", code == 200 and got["text"] == TRANSCRIPT
                  and got["duration"] == 3.0 and got["segments"][0]["end"] == 3.0 and isinstance(got["ms"], int))
        b = "vsboundary"
        form = (f"--{b}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\nwhisper-1\r\n--{b}\r\n"
                f"Content-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\nContent-Type: audio/wav\r\n\r\n"
                ).encode() + _wav(b"\x00\x00" * 8000) + f"\r\n--{b}--\r\n".encode()
        code, _h, raw = _post(s["port"], "/v1/audio/transcriptions", form, f"multipart/form-data; boundary={b}")
        got = json.loads(raw)
        ctx.check(f"a multipart WAV, half a second, got {code} {got}", code == 200 and got["text"] == TRANSCRIPT
                  and got["duration"] == 0.5)
        form_text = form.replace(b"name=\"model\"\r\n\r\nwhisper-1", b"name=\"response_format\"\r\n\r\ntext")
        code, h, raw = _post(s["port"], "/v1/audio/transcriptions", form_text, f"multipart/form-data; boundary={b}")
        ctx.check(f"response_format text, got {code} {raw!r}", code == 200 and raw.decode() == TRANSCRIPT
                  and h["Content-Type"].startswith("text/plain"))
        code, _h, raw = _post(s["port"], "/v1/audio/speech", b"{}", "application/json")
        ctx.check(f"the TTS route on the STT server: a 404 naming it, got {code} {raw!r}", code == 404
                  and b"this is the stt server" in raw)
        code, _h, raw = _post(s["port"], "/v1/audio/transcriptions", b"not audio", "text/plain")
        ctx.check(f"not audio: a 400 with the formats, got {code} {raw!r}", code == 400 and b"audio/pcm;rate=16000" in raw)


@test
def test_tts_streams_pcm_and_sends_a_wav(ctx: Ctx):
    with _server("kokoro-82m", HALO_VOICE_FAKE_MS="200") as s:
        ctx.check("listening", s["port"] is not None)
        req = json.dumps({"model": "kokoro-82m", "input": "Hello there. How are you?", "voice": "af_heart",
                          "response_format": "pcm"}).encode()
        code, h, raw = _post(s["port"], "/v1/audio/speech", req, "application/json")
        ctx.check(f"two sentences of 200 ms at 24 kHz, got {code} {len(raw)} {h.get('Content-Type')}", code == 200
                  and len(raw) == 2 * 2 * 4800 and h["Content-Type"] == "audio/pcm;rate=24000")
        req = json.dumps({"model": "kokoro-82m", "input": "One sentence.", "response_format": "wav"}).encode()
        code, h, raw = _post(s["port"], "/v1/audio/speech", req, "application/json")
        with wave.open(io.BytesIO(raw), "rb") as w:
            frames, rate = w.getnframes(), w.getframerate()
        ctx.check(f"a WAV of 200 ms, got {code} {frames} {rate}", code == 200 and rate == 24000 and frames == 4800)
        code, _h, raw = _post(s["port"], "/v1/audio/speech", b'{"input": ""}', "application/json")
        ctx.check(f"no input: a 400, got {code}", code == 400 and b"empty" in raw)


@test
def test_the_log_has_a_line_per_load_and_request(ctx: Ctx):
    from halo_harness.voice.log_lines import parse
    with _server("faster-whisper:small.en") as s:
        _post(s["port"], "/v1/audio/transcriptions", b"\x00\x00" * 32000, "audio/pcm;rate=16000")
        time.sleep(0.1)
        lines = s["log"].read_text(encoding="utf-8").splitlines()
    got = [parse(x) for x in lines]
    whats = [g["what"] for g in got if g]
    ctx.check(f"listening, load, one stt line, got {whats}", whats == ["listening", "load", "stt"])
    load = next(g for g in got if g and g["what"] == "load")
    ctx.check(f"the load line: the model, the device, int8, got {load}", load["model"] == "faster-whisper:small.en"
              and load["device"] == "cpu" and load["compute"] == "int8")
    stt = next(g for g in got if g and g["what"] == "stt")
    ctx.check(f"the request line: 2 s of audio, got {stt}", stt["audio_s"] == 2.0 and stt["device"] == "cpu")
    with _server("kokoro-82m", HALO_VOICE_FAKE_MS="100") as s:
        _post(s["port"], "/v1/audio/speech", json.dumps({"input": "Hi."}).encode(), "application/json")
        time.sleep(0.1)
        tts = [parse(x) for x in s["log"].read_text(encoding="utf-8").splitlines()]
    tts = [g for g in tts if g and g["what"] == "tts"]
    ctx.check(f"the tts line: 3 chars -> 0.1 s, its first audio, got {tts}", len(tts) == 1 and tts[0]["chars"] == 3
              and tts[0]["audio_s"] == 0.1 and isinstance(tts[0]["first_ms"], int))


@test
def test_a_failed_load_is_one_log_line_and_exit_1(ctx: Ctx):
    with _server("faster-whisper:small.en", HALO_VOICE_FAKE_FAIL="1") as s:
        code = s["proc"].wait(20)
        text = s["log"].read_text(encoding="utf-8")
    ctx.check(f"exit 1, got {code}", code == 1)
    ctx.check(f"the load failed line, got {text!r}", "voice load failed: stt faster-whisper:small.en on cpu: RuntimeError: "
              "Library libcublas.so.12" in text)


def _main(*argv) -> "tuple[int, str]":
    from halo_harness.voice.server import main
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


@test
def test_a_missing_extra_and_a_declared_model_exit_2(ctx: Ctx):
    from halo_harness.voice import INSTALL_LINE
    saved = {k: os.environ.pop(k, None) for k in ("HALO_VOICE_ENGINE",)}
    real = sys.modules.get("faster_whisper", "absent")
    sys.modules["faster_whisper"] = None  # the import the engine makes fails, as without the extra
    try:
        code, out = _main("--model", "faster-whisper:small.en", "--path", ".", "--port", "0")
        ctx.check(f"the install line, exit 2, got {code} {out!r}", code == 2 and INSTALL_LINE in out
                  and "faster_whisper" in out)
        code, out = _main("--model", "parakeet-tdt:0.6b")
        ctx.check(f"a declared model, got {code} {out!r}", code == 2 and out.strip() ==
                  "no engine for parakeet-tdt in this build; faster-whisper:large-v3-turbo is the built STT")
        code, out = _main("--model", "nope")
        ctx.check("an unknown model, exit 2", code == 2 and "not in the speech catalog" in out)
    finally:
        if real == "absent":
            sys.modules.pop("faster_whisper", None)
        else:
            sys.modules["faster_whisper"] = real
        os.environ.update({k: v for k, v in saved.items() if v is not None})


@test
def test_the_engine_seam(ctx: Ctx):
    from halo_harness.voice import catalog, engines
    os.environ["HALO_VOICE_ENGINE"] = "fake"
    try:
        e = engines.load(catalog.get("kokoro-82m"), "cpu", ".")
        ctx.check("the fake: CPU only by default", engines.devices() == ["cpu"])
        ctx.check("a TTS model transcribes nothing", isinstance(e, engines.Engine) and e.sample_rate == 24000)
        ctx.check("sentences split on their ends", engines.sentences("One. Two! Three") == ["One.", "Two!", "Three"])
        ctx.check("the fake needs no extra", engines.missing() == [])
    finally:
        os.environ.pop("HALO_VOICE_ENGINE", None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
