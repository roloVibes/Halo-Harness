"""tests.helpers.voice_files -- Halo 3.3.9.0 R1: a speech model "on disk" for the tests (tests/test_voice_*.py, the
bundle rig's speech needs): the files a catalog row's engine loads, a few bytes each, in the hub layout `halo voice
download` writes (<dir>/models--<org>--<name>/snapshots/<commit>/<file>). No real model, no download.

    put(models_dir, name) -> the snapshot folder       hub_files(name) -> {file: bytes} for tests/helpers/mock_hub.py
    voice_env(**extra) -> the env a fake speech server runs with (HALO_VOICE_ENGINE=fake, the scratch home's flags)
"""
from __future__ import annotations

import os
from pathlib import Path

COMMIT = "f1x7u4e0000000000000000000000000000000000"


def hub_files(name: str) -> dict:
    from halo_harness.voice.catalog import get
    row = get(name)
    files = row.files or ("model.safetensors", "config.json")
    return {f: (f"fixture {name} {f}\n".encode("utf-8") * 8) for f in files}


def put(models_dir, name: str) -> Path:
    from halo_harness.voice.catalog import get
    row = get(name)
    snap = Path(models_dir) / ("models--" + row.repo.replace("/", "--")) / "snapshots" / COMMIT
    snap.mkdir(parents=True, exist_ok=True)
    for f, data in hub_files(name).items():
        (snap / f).write_bytes(data)
    return snap


def voice_env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items()}
    env.update(HALO_VOICE_ENGINE="fake", BRIDGE_TEST_NO_BACKGROUND_NET="1", OLLAMA_HOST="http://127.0.0.1:9")
    env.update({k: str(v) for k, v in extra.items()})
    return env
