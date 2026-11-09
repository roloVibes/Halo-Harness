"""tests.helpers.engine_lines -- sample log lines per descriptor of halo_harness/engines/descriptors.py, in each engine's
own wording as its source prints them (FreeToken main at dacac5f: utils/logger.py's `[YYYY-MM-DD|HH:MM:SS|pid=N] LEVEL`
stamp with ANSI colours, engine.py, api_server.py, scheduler/status.py, moe/offload_cache.py, kernel/_toolchain.py;
Strata main at ffa80d73: serve/server.py and strata_cli/launch; TensorFold main at 532589e4: zig/src/server/log.zig,
serve.zig, chat.zig, live.zig, zig/src/native/cuda_startup.zig). From the source, unverified against a live run. The
fake engine (tests/helpers/fake_engine.py) prints them and tests/test_engines_steward.py reads them: one wording.
"""
from __future__ import annotations

import time

_B, _R, _C = "\x1b[1m", "\x1b[0m", {"INFO": "\x1b[32m", "WARNING": "\x1b[33m", "ERROR": "\x1b[31m"}


def ft(msg: str, level: str = "INFO", at: float = None) -> str:
    t = time.strftime("%Y-%m-%d|%H:%M:%S", time.localtime(time.time() if at is None else at))
    return f"{_B}[{t}|pid=4242]{_R} {_C.get(level, '')}{level:<8}{_R} {msg}"


def tf(msg: str, at: str = "2026-11-02T10:00:00.000Z") -> str:
    return f"{at} [tensorfold] {msg}"


def ft_load(port: int = 1919, warmup_s: float = 4.2, at: float = None) -> list:
    return [ft("Auto-selected MoE strategy: offload", at=at), ft("MoE experts: nvfp4 via b12x", at=at),
            ft(f"Prefill warmup complete for lengths [1, 8192] in {warmup_s:.3f} s", at=at),
            ft(f"API server is ready to serve on 127.0.0.1:{port}", at=at)]


def tf_capacity(sm: int = 89, device: str = "NVIDIA GeForce RTX 4090", streams: int = 4) -> str:
    return tf(f"CUDA sm_{sm} device 0 ({device}): model 16.02 GiB; {streams} streams at once, 1.12 GiB each at a "
              "32768-token window, of 6.1 GiB left after a 1.0 GiB reserve")


def tf_serving(name: str, port: int, loaded_s: float = 4.2) -> str:
    return tf(f"serving {name} at http://127.0.0.1:{port}/v1 (sampling: temperature 1.0, top_p 0.95; drafts: on; "
              f"context: 32768; loaded in {loaded_s:.1f}s)")


def tf_done(tokens: int = 16, tok_s: float = 40.0, queued: float = 0.0) -> str:
    return tf(f"done chatcmpl-1 prompt=120 cached=0 thinking=False effort=none tokens={tokens} sha=0f3a9c finish=stop "
              f"rounds={tokens} accepted=0/0 ttft=0.120 decode=0.400 elapsed=0.520 queued={queued:.3f} tok/s={tok_s:.1f}")


def st_ready(port: int, ctx: int = 32768) -> str:
    return (f"ready: http://127.0.0.1:{port}/v1  (OpenAI: /v1/chat/completions, Anthropic: /v1/messages, context {ctx} "
            "tokens, API key required)")


def st_done(tokens: int = 120, seconds: int = 4, tok_s: float = 30.0) -> str:
    return f"[strata] done: {tokens} tokens in {seconds} s ({tok_s:.1f} tok/s) (stop, cancel=False), expert cache 81.2% hit"


# (engine, line, the event kind, the steward's sentence) -- what each descriptor's patterns make of its own lines
SAMPLES = [
    ("freetoken", ft("Auto-selected MoE strategy: offload"), "engine-loading", "loading with the offload MoE strategy"),
    ("freetoken", ft("API server is ready to serve on 127.0.0.1:1919"), "load-result", "loaded and serving on 127.0.0.1:1919"),
    ("freetoken", ft("Decode batch, #running-req: 1, #token: 8200, token usage: 0.11, gen throughput (token/s): 21.50, "
                     "#queue-req: 0"), "timing", "decoding at 21.50 tok/s"),
    ("freetoken", ft("MoE decode, pinned 40 layers: hit 31.0%, per layer-step miss 5.52 fetch 5.52 cpu 0.00"),
     "engine-disk-bound", "the expert cache hits 31.0% of the experts a step asks: the misses stream over the host "
                          "link, so the link is the limit"),
    ("freetoken", ft("MoE decode, pinned 40 layers: hit 82.0%, per layer-step miss 1.44 fetch 1.44 cpu 0.00"), None, None),
    ("freetoken", ft("--moe-cpu-layers auto: banks 60.00 GiB > pin budget 25.60 GiB; locking 22 head+tail MoE layers for "
                     "CPU decode ([0, 1, 2])", "WARNING"), "engine-backend-fallback",
     "60.00 GiB of expert banks over a 25.60 GiB pin budget (WSL caps CUDA pinning): 22 layers decode on the CPU, slower"),
    ("freetoken", ft("Prefill warmup complete for lengths [1, 8192] in 312.480 s"), "engine-loading",
     "the startup warmup took 312.480 s: FreeToken compiled its CUDA kernels (once per install)"),
    ("freetoken", ft("Prefill warmup complete for lengths [1, 8192] in 4.200 s"), None, None),
    ("freetoken", "RuntimeError: nvcc 12.4 would build kernels linking libcudart.so.12, but torch 2.11.0 ships CUDA 13.0 "
                  "(libcudart.so.13). Install a CUDA 13.x toolkit", "other-error",
     "the CUDA toolchain does not match: FreeToken compiles its kernels with nvcc from CUDA 13"),
    ("freetoken", "ValueError: expert banks need 60.0 GiB of pinned host RAM but the pin budget is 25.6 GiB (WSL caps)",
     "other-error", "the expert banks need 60.0 GiB pinned, the pin budget is 25.6 GiB: the load stopped"),
    ("strata", "[strata] starting the engine: reading the model's weights ...", "engine-loading",
     "starting the engine: reading the weights"),
    ("strata", "[strata] mapping the experts from the model files (about 43 GB, --mmap-experts): they are not loaded",
     "engine-disk-bound", "the experts are mapped from the model files: what RAM cannot hold is read from the SSD, much "
                          "slower"),
    ("strata", "[strata] WARNING: RAM is tight - the model's experts take 43.0 GB of this PC's 48 GB, leaving 5.0 GB for "
               "everything else.", "engine-disk-bound", "RAM is tight: the experts take 43.0 GB of 48 GB"),
    ("strata", st_ready(8080), "load-result", "ready on 127.0.0.1:8080, window 32768"),
    ("strata", "[strata] parallel requests: 4 asked, the engine runs 3 (its log says why)", "engine-slots",
     "4 parallel requests asked, the engine runs 3 (the VRAM guide: 12 GB runs 1, 20 GB 2, 24 GB 3, 32 GB and more 4)"),
    ("strata", "[strata] parallel: a request has waited 12 s for a free slot (busy: [0, 1])", "engine-waiting",
     "a request waited 12 s for a free slot"),
    ("strata", st_done(), "timing", "a reply of 120 tokens at 30.0 tok/s"),
    ("strata", "    Downloading 12.5 of 76.0 GB", "engine-loading",
     "the first launch is downloading the set: 12.5 of 76.0 GB (Strata's own download, not a timeout)"),
    ("strata", "[X] Strata couldn't find an engine for this computer: no released engine runs this graphics card.",
     "other-error", "Strata did not start its engine"),
    ("tensorfold", tf_capacity(), "engine-slots", "TensorFold runs 4 streams at once"),
    ("tensorfold", tf_serving("Qwen3.8-27B-MLX-4bit", 8080, 298.4), "load-result",
     "Qwen3.8-27B-MLX-4bit loaded in 298.4 s on 127.0.0.1:8080, window 32768"),
    ("tensorfold", tf_done(), "timing", "a reply of 16 tokens at 40.0 tok/s"),
    ("tensorfold", tf_done(queued=2.5), "engine-waiting", "a reply waited 2.500 s in TensorFold's queue past its streams"),
    ("tensorfold", tf("6 connections (2 waiting) · decode 142 tok/s"), "engine-waiting", "6 connections, 2 waiting"),
    ("tensorfold", tf("ended chatcmpl-2 reason=error (OutOfMemory) prompt=12 tokens=0 after=1.25s"), "other-error",
     "TensorFold ended a request: OutOfMemory"),
    ("tensorfold", "tensorfold: this NVIDIA driver supports CUDA 12.4; this build needs CUDA 13.0 (driver R580 or newer)",
     "other-error", "TensorFold did not start: this NVIDIA driver supports CUDA 12.4; this build needs CUDA 13.0 (driver "
                    "R580 or newer)"),
]
