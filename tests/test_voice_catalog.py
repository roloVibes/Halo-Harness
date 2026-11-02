"""tests.test_voice_catalog -- Halo 3.3.9.0 R1: the speech catalog (halo_harness/voice/catalog.py) and `halo voice
models`: the seven rows with their engine, repo, files, sizes and built flag; every repo id marked unverified (written
from memory); the bundle manifest's VOICE_GB / VOICE_PREFIXES are the catalog's own objects (one source); a declared
row's one line; the Library's speech rows name their catalog row; `halo voice models` lists them (3.3.9.0 R2: a bare
`halo voice` opens a session with voice on, tests/test_voice_control.py). Files
only: nothing is downloaded, no engine is imported.
Run: python -m tests.test_voice_catalog
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="vs_catalog-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
NAMES = ("faster-whisper:large-v3-turbo", "faster-whisper:small.en", "faster-whisper:base.en", "parakeet-tdt:0.6b",
         "kokoro-82m", "qwen3-tts:0.6b", "silero-vad")


def _halo(*argv) -> "tuple[int, str]":
    from halo_harness.cli import main
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


@test
def test_the_seven_rows(ctx: Ctx):
    from halo_harness.voice import catalog
    ctx.check(f"the seven, in order, got {[r.name for r in catalog.ROWS]}", tuple(r.name for r in catalog.ROWS) == NAMES)
    kinds = {r.name: r.kind for r in catalog.ROWS}
    ctx.check("four STT, two TTS, one VAD", sorted(kinds.values()) == ["stt"] * 4 + ["tts"] * 2 + ["vad"])
    built = {r.name for r in catalog.ROWS if r.built}
    ctx.check(f"faster-whisper, kokoro and (3.3.9.0 R2) silero-vad are built, got {built}", built == {
              "faster-whisper:large-v3-turbo", "faster-whisper:small.en", "faster-whisper:base.en", "kokoro-82m",
              "silero-vad"})
    ctx.check("every repo is <org>/<name> and unverified", all(r.repo.count("/") == 1 and r.verified is False
                                                                 for r in catalog.ROWS))
    ctx.check("the sizes are numbers, a speech model has a CPU figure", all(r.download_gb > 0 and r.cpu_gb > 0
                                                                            for r in catalog.ROWS))
    big = catalog.get("faster-whisper:large-v3-turbo")
    ctx.check(f"the brief's figures, got {catalog.footprint(big)}", catalog.footprint(big) == "1.5 GB on the GPU, 3.1 GB on "
              "the CPU" and catalog.get("faster-whisper:small.en").download_gb == 0.5)
    ctx.check("the engines load named files", "model.bin" in big.files and catalog.get("kokoro-82m").files == (
        "kokoro-v1.0.onnx", "voices-v1.0.bin"))
    ctx.check("get is case-insensitive, unknown is None", catalog.get("Kokoro-82M") is not None and catalog.get("nope") is None)
    ctx.check("to_json is plain", json.loads(json.dumps(big.to_json()))["files"][0] == "config.json")


@test
def test_one_source_for_the_bundle_manifest(ctx: Ctx):
    from halo_harness.packs import manifest_bundle as M
    from halo_harness.voice import catalog
    ctx.check("VOICE_GB is the catalog's", M.VOICE_GB is catalog.VOICE_GB)
    ctx.check("VOICE_PREFIXES is the catalog's", M.VOICE_PREFIXES is catalog.VOICE_PREFIXES)
    ctx.check("the GPU figures", M.voice_gb("faster-whisper:large-v3-turbo") == 1.5 and M.voice_gb("kokoro-82m") == 0.3)
    ctx.check("a speech name is the voice runtime", M.runtime("parakeet-tdt:0.6b") == "voice" and M.runtime("qwen3.5:9b")
              == "ollama")
    ctx.check("every STT/TTS row has a GPU figure", set(catalog.VOICE_GB) == {r.name for r in catalog.ROWS
                                                                                 if r.kind in ("stt", "tts")})


@test
def test_a_declared_row_says_the_built_one(ctx: Ctx):
    from halo_harness.voice import catalog
    ctx.check("parakeet", catalog.no_engine_line(catalog.get("parakeet-tdt:0.6b")) ==
              "no engine for parakeet-tdt in this build; faster-whisper:large-v3-turbo is the built STT")
    ctx.check("qwen3-tts", catalog.no_engine_line(catalog.get("qwen3-tts:0.6b")) ==
              "no engine for qwen3-tts in this build; kokoro-82m is the built TTS")
    ctx.check("the VAD has no server", "R2's voice loop" in catalog.no_engine_line(catalog.get("silero-vad")))


@test
def test_the_library_links_its_speech_rows(ctx: Ctx):
    from halo_harness.models_library.truth_rules import audio
    from halo_harness.voice.catalog import library_link
    ctx.check("by repo", "faster-whisper:small.en" in (library_link({"repo": "Systran/faster-whisper-small.en"}) or ""))
    ctx.check("by name", "kokoro-82m (tts" in (library_link({"name": "kokoro-82m"}) or ""))
    ctx.check("anything else is None", library_link({"repo": "example-org/Tiny-1B-GGUF"}) is None)
    got = audio({"repo": "Systran/faster-whisper-small.en", "tags": []}, {}, {})
    ctx.check(f"the audio fact names the catalog row, got {got}", got is not None and "the speech catalog: "
              "faster-whisper:small.en" in str(got) and "halo voice download faster-whisper:small.en" in str(got))


@test
def test_halo_voice_models(ctx: Ctx):
    code, out = _halo("voice", "models")
    ctx.check(f"halo voice models lists the seven, got {code}", code == 0 and all(n in out for n in NAMES))
    ctx.check("each repo says unverified", out.count("(repo unverified)") == len(NAMES))
    ctx.check("not present here, with the download line", "not present (halo voice download kokoro-82m, 0.34 GB)" in out)
    ctx.check("the engines' line", "the engines: " in out)
    code, raw = _halo("voice", "models", "--json")
    got = json.loads(raw)
    ctx.check("--json: seven rows, none present", code == 0 and len(got["models"]) == 7
              and not any(m["present"] for m in got["models"]))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
