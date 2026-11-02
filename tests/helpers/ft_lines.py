"""tests.helpers.ft_lines -- Halo 3.3.9.1: FreeToken's log lines as its source prints them (read 2026-11-02 from
github.com/FlashML-org/FreeToken: utils/logger.py's `[YYYY-MM-DD|HH:MM:SS|pid=N] LEVEL message` with ANSI colours,
engine/engine.py's load lines, server/api_server.py's ready line, scheduler/status.py's batch lines, moe/
offload_cache.py's `--moe-collect-stats` line, kernel/_toolchain.py's nvcc mismatch). From the source, unverified
against a live run. The fake server (tests/helpers/fake_ft_server.py) prints them and tests/test_server_log_ft.py
reads them: one wording for both.
"""
from __future__ import annotations

import time

BOLD, RESET, COLORS = "\x1b[1m", "\x1b[0m", {"INFO": "\x1b[32m", "WARNING": "\x1b[33m", "ERROR": "\x1b[31m"}


def stamp(msg: str, level: str = "INFO", at: float = None, pid: int = 4242) -> str:
    t = time.strftime("%Y-%m-%d|%H:%M:%S", time.localtime(time.time() if at is None else at))
    return f"{BOLD}[{t}|pid={pid}]{RESET} {COLORS.get(level, '')}{level:<8}{RESET} {msg}"


def load(port: int = 1919, *, strategy: str = "offload", experts: str = "nvfp4", slots: int = 1536, pages: int = 40000,
         warmup_s: float = 4.2, at: float = None) -> list:
    return [stamp(f"Auto-selected MoE strategy: {strategy}", at=at),
            stamp("No MoE cache sizing flag given; defaulting to --moe-cache-auto for auto-selected strategy "
                  f"'{strategy}'", at=at),
            stamp(f"Resolved config: moe_strategy='{strategy}', attention_backend='fi', cache_type='radix', page_size=1", at=at),
            stamp(f"MoE experts: {experts} via b12x", at=at),
            stamp(f"--moe-cache-auto resolved moe_cache_size={slots} num_pages={pages} (prefill_overlap=True)", at=at),
            stamp(f"Prefill warmup complete for lengths [1, 8192] in {warmup_s:.3f} s", at=at),
            stamp(f"API server is ready to serve on 127.0.0.1:{port}", at=at)]


def prefill(tokens: int = 8000, tok_s: float = 812.4, at: float = None) -> str:
    return stamp(f"Prefill batch, #new-seq: 1, #new-token: {tokens}, #cached-token: 0, token usage: 0.10, "
                 f"#running-req: 0, #queue-req: 0, input throughput (token/s): {tok_s:.2f}", at=at)


def decode(tok_s: float = 21.5, at: float = None) -> str:
    return stamp(f"Decode batch, #running-req: 1, #token: 8200, token usage: 0.11, gen throughput (token/s): {tok_s:.2f}, "
                 "#queue-req: 0", at=at)


def moe(hit: float = 0.82, miss: float = 1.44, at: float = None) -> str:
    return stamp(f"MoE decode, pinned 40 layers: hit {hit:.1%}, per layer-step miss {miss:.2f} fetch {miss:.2f} cpu 0.00",
                 at=at)


def pin_lock(banks: float = 60.0, budget: float = 25.6, locked: int = 22, at: float = None) -> str:
    return stamp(f"--moe-cpu-layers auto: banks {banks:.2f} GiB > pin budget {budget:.2f} GiB; locking {locked} "
                 f"head+tail MoE layers for CPU decode ([0, 1, 2])", at=at)


def pin_stop(banks: float = 60.0, budget: float = 25.6) -> str:
    return (f"ValueError: expert banks need {banks:.1f} GiB of pinned host RAM but the pin budget is {budget:.1f} GiB "
            "(WSL caps CUDA pinning; FREETOKEN_PIN_BUDGET_GB overrides); pass --moe-cpu-layers auto to lock the layers "
            "over the pin budget for CPU decode, or --moe-cpu-layers <count|fraction|ids> to choose them yourself")


def nvcc_mismatch() -> str:
    return ("RuntimeError: nvcc 12.4 would build kernels linking libcudart.so.12, but torch 2.11.0 ships CUDA 13.0 "
            "(libcudart.so.13). Install a CUDA 13.x toolkit, or set FREETOKEN_ALLOW_CUDA_MISMATCH=1 to override.")


def warmup(seconds: float, at: float = None) -> str:
    return stamp(f"Prefill warmup complete for lengths [1, 8192] in {seconds:.3f} s", at=at)
