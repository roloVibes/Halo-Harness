"""halo_harness.voice -- Halo 3.3.9.0 "Voice" R1: the speech models as file-backed local models, and Halo's own
speech server (docs/VOICE.md).

    catalog.py       the speech catalog: STT, TTS and VAD rows (engine, repo, files, download / GPU / CPU GB, built)
    install.py       present(model) -> the folder | None; download and remove through the hub path `halo local` uses
    engines.py       the engine seam: load(row, device, path) -> Engine; devices(); the extra's one install line
    engine_fake.py   the fake engine (HALO_VOICE_ENGINE=fake, tests only): a fixed transcript, a sine of N ms
    log_lines.py     the speech server's log lines, written by the server and read by the steward (one source)
    server.py        `python -m halo_harness.voice.server --kind stt|tts --model <name> ...`: the OpenAI audio routes
    server_routes.py the request handler: /health, /v1/models, /v1/audio/transcriptions, /v1/audio/speech
    launch.py        `halo local serve --stt | --tts <model>`: the subprocess, the registry row, the `stt` / `tts` entry
    device.py        --device auto | cpu | cuda: the stated choice

Nothing in this round captures or plays audio (R2 brings the loop, R3 the host, Studio and the glasses path).
"""

from __future__ import annotations

INSTALL_LINE = 'uv tool install --reinstall "halo-harness[voice]"'
KINDS = ("stt", "tts", "vad")
RUNTIMES = ("voice-stt", "voice-tts")
ENGINE_ENV = "HALO_VOICE_ENGINE"


def is_voice_runtime(word) -> bool:
    """A `huggingface.local_servers` entry or a registry row that is a speech server (never a chat model's server)."""
    return str(word or "").strip().lower() in RUNTIMES


def runtime_for(kind: str) -> str:
    return f"voice-{kind}"


def install_says(what: str = "the speech engines") -> str:
    return f"{what} are not installed: {INSTALL_LINE}"
