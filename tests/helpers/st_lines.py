"""tests.helpers.st_lines -- Halo 3.3.9.2: the lines a Strata server and `strata launch` print, in Strata's own wording
(serve/server.py, strata_cli/launch/cmd.py and runner.py at main ffa80d73: from the source, unverified against a live
run). tests/helpers/fake_strata.py prints them and the steward tests seed fixture logs with them.
"""
from __future__ import annotations


def starting() -> str:
    return "[strata] starting the engine: reading the model's weights ..."


def experts(mode: str = "ram", gb: int = 43) -> str:
    if mode == "mapped":
        return (f"[strata] mapping the experts from the model files (about {gb} GB, --mmap-experts): they are not loaded "
                "into RAM - the OS file cache reads them as the GPU's expert cache fills and as requests need them.")
    if mode == "budget":
        return (f"[strata] loading the most-used experts into RAM (up to 40 GiB; the rest are read from the model files "
                "as needed) and locking part of them for the GPU.")
    return f"[strata] loading the experts into RAM (about {gb} GB) and locking part of them for the GPU."


def loaded(seconds: int = 31) -> str:
    return f"[strata] experts loaded: 43.0 GiB at 2.1 GB/s ({seconds} s so far)"


def ready(port: int, ctx: int = 32768, key: bool = True) -> str:
    return (f"ready: http://127.0.0.1:{port}/v1  (OpenAI: /v1/chat/completions, Anthropic: /v1/messages, "
            f"context {ctx} tokens{', API key required' if key else ''})")


def parallel(asked: int, runs: int) -> str:
    return f"[strata] parallel requests: {asked} asked, the engine runs {runs} (its log says why)"


def waited(seconds: int) -> str:
    return (f"[strata] parallel: a request has waited {seconds} s for a free slot (busy: [0, 1], in use: [0, 1], "
            "ending: []) (issue #1603)")


def done(tokens: int, seconds: int, tok_s: float, hit: float = 81.2, pcie: float = 0.0) -> str:
    extra = f" (+{pcie:.1f}% of the routed experts over PCIe)" if pcie else ""
    return (f"[strata] done: {tokens} tokens in {seconds} s ({tok_s:.1f} tok/s) (stop, cancel=False), expert cache "
            f"{hit:.1f}% hit{extra}")


def engine_request(prompt: int, reused: int, pp: float, gen: int, tg: float) -> str:
    return (f"prompt {prompt} tokens = {reused} reused + {prompt - reused} read in {1000 * (prompt - reused) / pp:.1f} ms "
            f"({pp:.1f} tok/s), {gen} generated in {1000 * gen / tg:.1f} ms ({tg:.1f} tok/s)")


def ram_tight() -> str:
    return ("[strata] WARNING: RAM is tight - the model's experts take 43.0 GB of this PC's 48 GB, leaving 5.0 GB for "
            "everything else. Windows will slow down (paging to disk). Close other programs, or run START-HERE --setup "
            "and pick a smaller size (Q2_0 / IQ2_XS).")


def download(done_gb: float, total_gb: float) -> str:
    return f"    Downloading {done_gb:.1f} of {total_gb:.1f} GB"


def engine_download(pct: int) -> str:
    return f"    Downloading the engine… {pct}%"


def no_engine() -> str:
    return ("[X] Strata couldn't find an engine for this computer: no released engine runs this graphics card. The model "
            "files were downloaded; nothing was started.")
