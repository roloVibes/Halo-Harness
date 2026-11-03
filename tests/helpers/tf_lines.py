"""tests.helpers.tf_lines -- Halo 3.3.9.3: TensorFold's own log lines, as the fake server prints them and the reader's
tests feed them. Each is written from TensorFold's source (main at 532589e4: zig/src/native/cuda_startup.zig's capacity
format, zig/src/server/serve.zig's serving line, zig/src/server/chat.zig's done line, zig/src/server/log.zig's ended line
and its TENSORFOLD_LOG_TIME stamp, zig/src/server/live.zig's status line) and a GLM receipt (docs/receipts/glm-fp4local-
80517fc3/tp2/serve/x9-nv/serve.txt): from the source, unverified against a live run. The Metal capacity line's wording
and the driver refusal's are guesses (the source read names neither): the reader keys on "N streams at once" and the
backend word only.
"""
from __future__ import annotations


def stamp(line: str, at: str = "2026-11-02T10:00:00.000Z") -> str:
    return f"{at} {line}"


def cuda_capacity(sm: int = 89, device: str = "NVIDIA GeForce RTX 4090", model_gib: float = 16.02, streams: int = 4,
                  window: int = 32768) -> str:
    return (f"[tensorfold] CUDA sm_{sm} device 0 ({device}): model {model_gib:.2f} GiB; {streams} stream"
            f"{'s' if streams != 1 else ''} at once, 1.12 GiB each at a {window}-token window, of 6.1 GiB left after a "
            "1.0 GiB reserve; prompts in passes of up to 2048 rows, a 2.0 GiB prompt cache; own glue kernels")


def metal_capacity(chip: str = "Apple M3 Max", model_gib: float = 16.02, streams: int = 8, window: int = 32768) -> str:
    return (f"[tensorfold] Metal ({chip}, unified memory): model {model_gib:.2f} GiB; {streams} streams at once, "
            f"0.50 GiB each at a {window}-token window")


def serving(name: str, port: int, window: int = 32768, loaded_s: float = 4.2) -> str:
    return (f"[tensorfold] serving {name} at http://127.0.0.1:{port}/v1 (sampling: temperature 1.0, top_p 0.95; "
            f"drafts: on; context: {window}; loaded in {loaded_s:.1f}s)")


def profile() -> str:
    return "[tensorfold] profile: stable; registered overrides: none"


def done(prompt: int = 120, tokens: int = 16, tok_s: float = 40.0, queued: float = 0.0, ttft: float = 0.12,
         rid: str = "chatcmpl-1", cached: int = 0) -> str:
    decode = tokens / tok_s if tok_s else 0.0
    return (f"[tensorfold] done {rid} prompt={prompt} cached={cached} thinking=False effort=none tokens={tokens} "
            f"sha=0f3a9c finish=stop rounds={tokens} accepted=0/0 ttft={ttft:.3f} decode={decode:.3f} "
            f"elapsed={ttft + decode + queued:.3f} queued={queued:.3f} tok/s={tok_s:.1f}")


def ended(rid: str = "chatcmpl-2", why: str = "OutOfMemory") -> str:
    return f"[tensorfold] ended {rid} reason=error ({why}) prompt=12 tokens=0 after=1.25s"


def live(connections: int = 6, waiting: int = 2) -> str:
    return (f"[tensorfold] {connections} connections ({waiting} waiting) · decode 142 tok/s · prefill 1,210 "
            "tok/s")


def key_file_refused() -> str:
    return "tensorfold: API key file cannot be opened safely"


def driver_refused() -> str:
    return "tensorfold: this NVIDIA driver supports CUDA 12.4; this build needs CUDA 13.0 (driver R580 or newer)"


def load(name: str, port: int, *, backend: str = "cuda", sm: int = 89, streams: int = 4, window: int = 32768,
         loaded_s: float = 4.2, model_gib: float = 16.02) -> list:
    cap = (metal_capacity(streams=streams, window=window, model_gib=model_gib) if backend == "metal" else
           cuda_capacity(sm=sm, streams=streams, window=window, model_gib=model_gib))
    return [cap, profile(), serving(name, port, window, loaded_s)]
