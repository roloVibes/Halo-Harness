"""halo_harness.voice.vad -- voice activity: is this 32 ms frame speech? (Halo 3.3.9.0 R2; docs/VOICE.md "The loop")

    load(path=None) -> (Vad, line | None)   Silero VAD (the catalog's `silero-vad`, its onnx through onnxruntime) when it
        is on disk and the extra is installed; else a level gate with the one line that says why and the command
    Vad.is_speech(frame) -> bool            frame = audio.FRAME samples of 16 kHz mono PCM16
    Vad.kind                                "silero" | "level" | "fake"

HALO_VOICE_ENGINE=fake (tests only, the engine seam's flag) is the fake: any frame louder than the level gate's floor
is speech, a silent one is not. Silero v5's call is written from memory of its model card (`verified: false` in the
catalog): input [1, 64 + 512] float32 (the last 64 samples of the previous frame first), state [2, 1, 128], sr int64;
outputs the speech probability and the next state.
"""

from __future__ import annotations

import array
import math
from typing import Optional

from halo_harness.voice.audio import FRAME, RATE

LEVEL_RMS = 500.0
THRESHOLD = 0.5
CONTEXT = 64


def rms(frame: bytes) -> float:
    a = array.array("h", frame[: len(frame) // 2 * 2])
    return math.sqrt(sum(x * x for x in a) / len(a)) if len(a) else 0.0


class Vad:
    kind = "level"

    def is_speech(self, frame: bytes) -> bool:
        return rms(frame) >= LEVEL_RMS

    def reset(self) -> None:
        pass


class Fake(Vad):
    kind = "fake"


class Silero(Vad):
    kind = "silero"

    def __init__(self, onnx_path) -> None:
        import numpy as np
        import onnxruntime
        self.np = np
        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = opts.intra_op_num_threads = 1
        self.s = onnxruntime.InferenceSession(str(onnx_path), sess_options=opts, providers=["CPUExecutionProvider"])
        self.reset()

    def reset(self) -> None:
        np = self.np
        self.state = np.zeros((2, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, CONTEXT), dtype=np.float32)

    def prob(self, frame: bytes) -> float:
        np = self.np
        x = (np.frombuffer(frame[: FRAME * 2], dtype=np.int16).astype(np.float32) / 32768.0).reshape(1, -1)
        if x.shape[1] < FRAME:
            x = np.pad(x, ((0, 0), (0, FRAME - x.shape[1])))
        inp = np.concatenate([self.context, x], axis=1)
        out, self.state = self.s.run(None, {"input": inp, "state": self.state, "sr": np.array(RATE, dtype=np.int64)})
        self.context = x[:, -CONTEXT:]
        return float(np.asarray(out).reshape(-1)[0])

    def is_speech(self, frame: bytes) -> bool:
        return self.prob(frame) >= THRESHOLD


def load(path=None) -> "tuple[Vad, Optional[str]]":
    from halo_harness.voice import INSTALL_LINE
    from halo_harness.voice.engines import fake_on
    if fake_on():
        return Fake(), None
    from halo_harness.voice.catalog import get
    from halo_harness.voice.install import present
    row = get("silero-vad")
    where = path or present(row)
    if where is None:
        return Vad(), (f"silero-vad is not present: a level gate stands in -- halo voice download silero-vad "
                       f"({row.download_gb:g} GB)")
    try:
        from pathlib import Path
        p = Path(where)
        return Silero(p if p.suffix == ".onnx" else p / row.files[0]), None
    except ImportError:
        return Vad(), f"silero-vad needs onnxruntime (the voice extra): a level gate stands in -- {INSTALL_LINE}"
    except Exception as e:
        return Vad(), f"silero-vad did not load ({type(e).__name__}: {e}): a level gate stands in"
