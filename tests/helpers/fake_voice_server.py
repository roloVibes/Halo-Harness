"""tests.helpers.fake_voice_server -- Halo 3.3.9.0 R1: Halo's own speech server (halo_harness/voice/server.py) by
another entry point, with the fake engine (halo_harness/voice/engine_fake.py: a fixed transcript, a sine of N ms) and
no extra. The tests set `huggingface.voice_server_cmd` to [python, this file] (tests/helpers/hf_local_env.HfHome), the
way fake_llama_server.py stands in for llama-server: `halo local serve --stt | --tts` runs it exactly as it runs the
real one, with the same arguments, the same log lines and the same routes. Nothing loads a model.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
os.environ["HALO_VOICE_ENGINE"] = "fake"

if __name__ == "__main__":
    from halo_harness.voice.server import main
    sys.exit(main(sys.argv[1:]))
