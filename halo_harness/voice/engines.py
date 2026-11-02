"""halo_harness.voice.engines -- the engine seam (Halo 3.3.9.0 R1; docs/VOICE.md "The engines"):

    load(row, device, path) -> Engine        a catalog row's engine on cpu | cuda from the model's folder
    Engine.transcribe(pcm16, sample_rate) -> [{start, end, text}]       (STT)
    Engine.speak(text, voice) -> iterator of PCM16 mono chunks at Engine.sample_rate, one per sentence   (TTS)
    devices() -> ["cpu"] or ["cpu", "cuda"]  what the engines see (CTranslate2's CUDA count, onnxruntime's providers)
    missing(engine) -> [module]              the extra's packages that are not importable here (no import is made)

Built: faster-whisper (CTranslate2; int8 on the CPU, float16 on CUDA) and kokoro-onnx (onnxruntime; the CUDA
provider on cuda). A declared row (parakeet-tdt, qwen3-tts) raises NoEngine with the catalog's one line; a missing
package raises ExtraMissing with the install line. HALO_VOICE_ENGINE=fake (tests only) is voice/engine_fake.py.
The engines' packages are the optional extra `halo-harness[voice]`; nothing here is imported until an engine loads.
"""

from __future__ import annotations

import importlib.util
import os
import re
from pathlib import Path
from typing import Iterator

from halo_harness.voice import ENGINE_ENV, INSTALL_LINE

NEEDS = {"faster-whisper": ("faster_whisper", "ctranslate2", "numpy"),
         "kokoro-onnx": ("kokoro_onnx", "onnxruntime", "numpy")}
EXTRA = ("faster_whisper", "kokoro_onnx", "onnxruntime", "numpy", "soundfile")
_SENTENCE = re.compile(r"(?<=[.!?;:])\s+")


class ExtraMissing(RuntimeError):
    def __init__(self, modules):
        self.modules = list(modules)
        super().__init__(f"the speech engines are not installed ({', '.join(self.modules)} missing): {INSTALL_LINE}")


class NoEngine(RuntimeError):
    pass


def fake_on() -> bool:
    return os.environ.get(ENGINE_ENV, "").strip().lower() == "fake"


def missing(engine: str = "") -> list:
    """The packages of the extra (or of one engine) that are not importable; the fake engine needs none."""
    if fake_on():
        return []
    mods = NEEDS.get(engine, EXTRA) if engine else EXTRA
    out = []
    for m in mods:
        try:
            if importlib.util.find_spec(m) is None:
                out.append(m)
        except (ImportError, ValueError):
            out.append(m)
    return out


def sentences(text: str) -> list:
    parts = [p.strip() for p in _SENTENCE.split(str(text or "").strip()) if p.strip()]
    return parts or [str(text or "").strip()]


def devices() -> list:
    if fake_on():
        return [d for d in os.environ.get("HALO_VOICE_FAKE_DEVICES", "cpu").split(",") if d] or ["cpu"]
    out = ["cpu"]
    try:
        if importlib.util.find_spec("ctranslate2") is not None:
            import ctranslate2
            if ctranslate2.get_cuda_device_count() > 0:
                return out + ["cuda"]
        if importlib.util.find_spec("onnxruntime") is not None:
            import onnxruntime
            if "CUDAExecutionProvider" in onnxruntime.get_available_providers():
                return out + ["cuda"]
    except Exception:
        return out
    return out


class Engine:
    kind = "stt"
    sample_rate = 16000

    def __init__(self, row, device: str, path) -> None:
        self.row, self.model, self.device, self.path = row, row.name, device, Path(path)
        self.compute = "int8" if device == "cpu" else "float16"

    def transcribe(self, pcm16: bytes, sample_rate: int) -> list:
        raise NoEngine(f"{self.model} transcribes nothing: it is a {self.kind.upper()} model")

    def speak(self, text: str, voice: str) -> Iterator[bytes]:
        raise NoEngine(f"{self.model} speaks nothing: it is a {self.kind.upper()} model")


def _float16k(pcm16: bytes, rate: int):
    import numpy as np
    audio = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0
    if rate != 16000 and len(audio):
        n = max(1, int(len(audio) * 16000 / rate))
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)
    return audio


class Whisper(Engine):
    kind = "stt"

    def __init__(self, row, device, path) -> None:
        super().__init__(row, device, path)
        from faster_whisper import WhisperModel
        self.m = WhisperModel(str(self.path), device=device, compute_type=self.compute)

    def transcribe(self, pcm16: bytes, sample_rate: int) -> list:
        lang = "en" if self.model.endswith(".en") else None
        segs, _info = self.m.transcribe(_float16k(pcm16, sample_rate), beam_size=1, language=lang)
        return [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()} for s in segs]


class Kokoro(Engine):
    kind = "tts"
    sample_rate = 24000

    def __init__(self, row, device, path) -> None:
        super().__init__(row, device, path)
        self.compute = "fp32"
        import kokoro_onnx
        onnx, voices = self.path / row.files[0], self.path / row.files[1]
        if device == "cuda":
            import onnxruntime
            sess = onnxruntime.InferenceSession(str(onnx), providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
            self.k = kokoro_onnx.Kokoro.from_session(sess, str(voices))
        else:
            self.k = kokoro_onnx.Kokoro(str(onnx), str(voices))

    def speak(self, text: str, voice: str) -> Iterator[bytes]:
        import numpy as np
        for s in sentences(text):
            samples, rate = self.k.create(s, voice=voice, speed=1.0, lang="en-us")
            self.sample_rate = int(rate)
            yield (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16).tobytes()


BUILT = {"faster-whisper": Whisper, "kokoro-onnx": Kokoro}


def load(row, device: str, path) -> Engine:
    if fake_on():
        from halo_harness.voice.engine_fake import FakeEngine
        return FakeEngine(row, device, path)
    cls = BUILT.get(row.engine)
    if cls is None or not row.built:
        from halo_harness.voice.catalog import no_engine_line
        raise NoEngine(no_engine_line(row))
    gone = missing(row.engine)
    if gone:
        raise ExtraMissing(gone)
    try:
        return cls(row, device, path)
    except ImportError as e:
        raise ExtraMissing([getattr(e, "name", None) or str(e)]) from None
