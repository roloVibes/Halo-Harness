"""halo_harness.voice.catalog -- the speech catalog (Halo 3.3.9.0 R1; docs/VOICE.md "The catalog"; plans/
local-model-fit-brief.md Part K).

    ROWS                          the seven models: STT faster-whisper large-v3-turbo / small.en / base.en and
                                  parakeet-tdt 0.6b, TTS kokoro-82m and qwen3-tts 0.6b, VAD silero-vad
    get(name) -> Row | None       by its catalog name, case-insensitive
    of_kind(kind) -> [Row]        built_for(kind) -> the first built row of that kind (the one `serve` names)
    VOICE_GB / VOICE_PREFIXES     the GPU footprints and the name prefixes packs/manifest_bundle.py imports
    library_link(row, card) -> the Library's "audio" fact source naming the catalog row, or None
    footprint(row) -> "1.5 GB on the GPU, 3.1 GB on the CPU"

A row: {name, kind, engine, repo, files, download_gb, gpu_gb, cpu_gb, built, verified, note}. `files` are the files
the engine loads from the repo (empty: every file); `download_gb` is what `halo voice download` fetches; `gpu_gb` /
`cpu_gb` the footprint while it serves (weights + the engine's working set, int8 on the CPU). `built` says this
build has an engine for it (faster-whisper through CTranslate2, Kokoro through kokoro-onnx, 3.3.9.0 R2: Silero VAD
through onnxruntime in the voice loop, voice/vad.py); a declared row is listed,
downloadable and fitted, and `serve` says in one line which built model serves its kind. The repo ids and the sizes
are written from memory of the model cards (`verified: false`): `halo voice models` prints "(repo unverified)".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Row:
    name: str
    kind: str
    engine: str
    repo: str
    files: tuple = field(default_factory=tuple)
    download_gb: float = 0.0
    gpu_gb: float = 0.0
    cpu_gb: float = 0.0
    built: bool = False
    verified: bool = False
    note: str = ""

    def to_json(self) -> dict:
        out = asdict(self)
        out["files"] = list(self.files)
        return out


_WHISPER = ("config.json", "model.bin", "tokenizer.json")
ROWS = (
    Row("faster-whisper:large-v3-turbo", "stt", "faster-whisper", "deepdml/faster-whisper-large-v3-turbo-ct2",
        _WHISPER + ("preprocessor_config.json", "vocabulary.json"), 1.6, 1.5, 3.1, True, False,
        "the most accurate built STT; 10-20x realtime on a 24 GB card, a few x on a CPU"),
    Row("faster-whisper:small.en", "stt", "faster-whisper", "Systran/faster-whisper-small.en",
        _WHISPER + ("vocabulary.txt",), 0.5, 0.5, 0.9, True, False, "English only; the CPU default (int8)"),
    Row("faster-whisper:base.en", "stt", "faster-whisper", "Systran/faster-whisper-base.en",
        _WHISPER + ("vocabulary.txt",), 0.15, 0.2, 0.4, True, False, "English only; the smallest, for a slow CPU"),
    Row("parakeet-tdt:0.6b", "stt", "parakeet-tdt", "nvidia/parakeet-tdt-0.6b-v3", ("parakeet-tdt-0.6b-v3.nemo",),
        2.5, 1.2, 2.4, False, False, "declared: ~50 ms a sentence on a GPU; NeMo's runtime is not in this build"),
    Row("kokoro-82m", "tts", "kokoro-onnx", "fastrtc/kokoro-onnx", ("kokoro-v1.0.onnx", "voices-v1.0.bin"),
        0.34, 0.3, 0.5, True, False, "54 voices, ~75-100 ms to first audio; the realtime default (voice af_heart)"),
    Row("qwen3-tts:0.6b", "tts", "qwen3-tts", "Qwen/Qwen3-TTS-0.6B", (), 1.8, 1.4, 2.4, False, False,
        "declared: clones a voice from a ~3 s reference; its runtime is not in this build"),
    Row("silero-vad", "vad", "silero-vad", "snakers4/silero-vad", ("silero_vad.onnx",), 0.002, 0.0, 0.05, True, False,
        "the voice-activity detector the voice loop chunks the microphone with (onnxruntime); no server of its own"),
)
VOICE_GB = {r.name: r.gpu_gb for r in ROWS if r.kind in ("stt", "tts")}
VOICE_PREFIXES = ("faster-whisper", "whisper", "parakeet", "kokoro", "qwen3-tts", "silero")
DEFAULT_VOICE = "af_heart"


def get(name) -> Optional[Row]:
    want = str(name or "").strip().lower()
    return next((r for r in ROWS if r.name == want), None)


def of_kind(kind: str) -> list:
    return [r for r in ROWS if r.kind == kind]


def built_for(kind: str) -> Optional[Row]:
    return next((r for r in ROWS if r.kind == kind and r.built), None)


def no_engine_line(row: Row) -> str:
    """The one line `serve` says for a declared row."""
    if row.kind == "vad":
        return f"{row.name} has no server of its own: R2's voice loop runs it beside the STT"
    alt = built_for(row.kind)
    return (f"no engine for {row.engine} in this build; " + (f"{alt.name} is the built {row.kind.upper()}" if alt else
            f"no {row.kind.upper()} engine is built yet"))


def footprint(row: Row) -> str:
    return f"{row.gpu_gb:g} GB on the GPU, {row.cpu_gb:g} GB on the CPU"


def unverified(row: Row) -> str:
    return "" if row.verified else " (repo unverified)"


def by_repo(repo) -> Optional[Row]:
    want = str(repo or "").strip().lower()
    return next((r for r in ROWS if want and r.repo.lower() == want), None)


def library_link(row: dict, card: Optional[dict] = None) -> Optional[str]:
    """The Library's speech rows (models_library/truth_rules.audio): a row whose repo or name is a catalog row names
    it -- the size, whether this build serves it, and the command."""
    for key in ("repo", "id", "name", "model"):
        raw = str((row or {}).get(key) or (card or {}).get(key) or "")
        hit = by_repo(raw) or get(raw)
        if hit is not None:
            return (f"the speech catalog: {hit.name} ({hit.kind}, {hit.download_gb:g} GB; "
                    + ("halo voice download " + hit.name if hit.built else "declared, no engine in this build") + ")")
    return None
