"""tests.test_doctor_voice -- Halo 3.3.9.0 R1: `halo doctor --voice` (halo_harness/doctor_voice.py) on a scratch home
(tests/helpers/hf_local_env.HfHome, the fake speech server as `huggingface.voice_server_cmd`):

1. the extra: installed, or the one install line (a monkeypatched import stands for a box without it);
2. each catalog model: present with its folder, or the download line with its GB; a declared one says it has no engine;
3. the devices through the engine seam: the fake says CPU only (N cores), HALO_VOICE_FAKE_DEVICES=cpu,cuda says CUDA;
4. the speech servers: none, then `stt` with its model, device, url and /health 200; `--json` is the same rows;
5. (3.3.9.0 R3) a CPU box (the fake devices()): the recommended pair and its commands, or the other halo it uses.
No real engine, no model, nothing downloads.
Run: python -m tests.test_doctor_voice
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.hf_local_env import HfHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.voice_files import put  # noqa: E402

test, TESTS = new_registry()
SMALL = "faster-whisper:small.en"


def _doctor(*argv) -> "tuple[int, str]":
    from halo_harness.doctor import cmd_doctor
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = cmd_doctor(["--voice", *argv])
    return code, out.getvalue()


@test
def test_the_extra_line(ctx: Ctx):
    from halo_harness.voice import INSTALL_LINE
    with HfHome():
        real = sys.modules.get("faster_whisper", "absent")
        sys.modules["faster_whisper"] = None
        try:
            code, out = _doctor()
        finally:
            sys.modules.pop("faster_whisper", None) if real == "absent" else sys.modules.__setitem__("faster_whisper", real)
        ctx.check(f"the header and the install line, got {code} {out[:300]!r}", code == 0 and out.startswith(
            "halo doctor --voice\n") and f"WARN  the speech engines are not installed (faster_whisper" in out
            and INSTALL_LINE in out)


@test
def test_each_model_and_the_devices(ctx: Ctx):
    with HfHome() as h:
        os.environ["HALO_VOICE_ENGINE"] = "fake"
        where = put(h.models, SMALL)
        code, out = _doctor()
        ctx.check("the fake engine says so", "INFO  the fake engine (HALO_VOICE_ENGINE=fake)" in out)
        ctx.check(f"present with its folder, got {out!r}", f"OK    {SMALL} (stt) present: {where}" in out)
        ctx.check("absent: the download line", "INFO  kokoro-82m (tts) not present -- halo voice download kokoro-82m "
                  "(0.34 GB)" in out)
        ctx.check("declared: no engine", "no engine for parakeet-tdt in this build" in out)
        ctx.check(f"CPU only with the cores, got {code}", code == 0 and f"CPU only ({os.cpu_count()} cores)" in out)
        os.environ["HALO_VOICE_FAKE_DEVICES"] = "cpu,cuda"
        _code, out = _doctor()
        ctx.check("CUDA through the seam", "OK    CUDA visible to the engines" in out)
        ctx.check("no server yet", "no speech server running (halo local serve --stt | --tts <model>)" in out)


@test
def test_a_cpu_box_hears_the_recommended_pair(ctx: Ctx):
    from halo_harness import theme
    from halo_harness.voice import engines
    with HfHome():
        os.environ["HALO_VOICE_ENGINE"] = "fake"
        real = engines.devices
        engines.devices = lambda: ["cpu"]  # the fake devices(): a Kali-class box, no GPU
        try:
            _code, out = _doctor()
            ctx.check(f"CPU only, then the pair with its RAM and the commands, got {out!r}", "CPU only (" in out and (
                "INFO  the CPU pair: faster-whisper:base.en (int8, ") in out and "+ kokoro-82m (" in out
                and "halo config set voice.stt_model faster-whisper:base.en; halo config set voice.device cpu" in out
                and "voice.stt_server stt@<host> (docs/VOICE-cpu.md)" in out)
            theme.set_config_value("voice.stt_server", "stt@pc")
            _code, out = _doctor()
            ctx.check(f"with stt@pc it says the other halo instead, got {out!r}", "OK    speech through another halo on the "
                      "LAN (stt: stt@pc): its GPU hears and speaks" in out and "the CPU pair" not in out)
            engines.devices = lambda: ["cpu", "cuda"]
            _code, out = _doctor()
            ctx.check("a CUDA box gets no pair line", "the CPU pair" not in out and "another halo" not in out)
        finally:
            engines.devices = real


@test
def test_a_running_server(ctx: Ctx):
    from halo_harness.local_cli import cmd_local
    with HfHome() as h:
        os.environ["HALO_VOICE_ENGINE"] = "fake"
        put(h.models, SMALL)
        with contextlib.redirect_stdout(io.StringIO()):
            ctx.check("served", cmd_local(["serve", "--stt", SMALL, "--device", "cpu"]) == 0)
        _code, out = _doctor()
        ctx.check(f"stt with its model, device, url and health, got {out[-400:]!r}", f"OK    stt: {SMALL} on cpu at "
                  "http://127.0.0.1:" in out and "/health 200 (ok)" in out)
        _code, raw = _doctor("--json")
        rows = json.loads(raw)
        ctx.check("--json: the same rows", any(r["step"] == "server stt" and r["level"] == "OK" for r in rows)
                  and any(r["step"] == "extra" for r in rows))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
