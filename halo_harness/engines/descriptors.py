"""halo_harness.engines.descriptors -- THE table: one entry per local engine Halo knows beyond llama-server and
mlx_lm.server (docs/MODELS-engines.md renders it). Adding an engine is one entry here, never a round.

Every figure and pattern is from the engine's own source and docs, read on the date `source` says, and `verified` is
False until an owner's live run against that engine: a live log may word its lines otherwise.

An entry: id (the `runtime` word of a huggingface.local_servers entry), label, url, what, source, default_port,
base_path, health (the route that answers once the server is up), stats (None, or the queue read: a /health `live`
block, else a Prometheus /metrics), detect (owned_by on /v1/models rows, or /health keys), programs + version (the
program on PATH and its --version pattern), install {os: the owner's install line: Halo never installs an engine},
requires, backends / os / arch (where it runs), start (the managed start, or None: detect-only), log (a stamp pattern
and (word, pattern, sentence[, condition]) rows), fixes {word: (the fix line, its cost)}, fit, tune, verified.
"""

from __future__ import annotations

from typing import Optional

WORDS = {"loading": "engine-loading", "loaded": "load-result", "slots": "engine-slots", "waiting": "engine-waiting",
         "backend-fallback": "engine-backend-fallback", "disk-bound": "engine-disk-bound", "error": "other-error",
         "timing": "timing"}
SEVERITY = {"loading": "info", "loaded": "info", "timing": "info", "slots": "warn", "waiting": "warn",
            "backend-fallback": "warn", "disk-bound": "warn", "error": "error"}
_OOM = r"out of memory|OutOfMemory|cudaMalloc failed|cudaHostAlloc refused|hipErrorOutOfMemory|CUDA_ERROR_OUT_OF_MEMORY"

FREETOKEN = {
    "id": "freetoken", "label": "FreeToken", "url": "https://github.com/FlashML-org/FreeToken", "license": "Apache-2.0",
    "what": "a big Mixture-of-Experts model on one machine: the routed experts in host RAM, an LRU cache of them on "
            "the GPU, each miss streamed over PCIe",
    "source": "main at dacac5f, read 2026-11-02", "default_port": 1919, "base_path": "/v1", "health": "/health",
    "stats": None, "detect": {"owned_by": "FreeToken"}, "programs": ("ft",), "version": r"freetoken version (\S+)",
    "install": {"linux": 'uv pip install "freetoken[accel]"'},
    "requires": "Linux x86_64, an NVIDIA driver r580+ (CUDA 13) and nvcc on PATH (the CUDA 13 toolkit); under WSL2 "
                "CUDA pinned memory is capped near half of RAM",
    "backends": ("cuda",), "os": ("linux",), "arch": ("x86_64", "amd64"), "first_wait_s": 1800.0,
    "start": {"model": "dir", "wait_s": 120.0, "key": {"env": "FREETOKEN_API_KEY", "lan_only": True},
              "argv": ["serve", "--model", "{path}", "--served-model-name", "{name}", "--host", "{host}", "--port",
                       "{port}", "--moe-collect-stats"]},
    "log": {"stamp": r"^\[(\d{4}-\d\d-\d\d)\|(\d\d:\d\d:\d\d)[^\]]*\]\s*(?:\w+\s+)?", "patterns": [
        ("loading", r"Auto-selected MoE strategy: (?P<strategy>\w+)", "loading with the {strategy} MoE strategy"),
        ("loaded", r"API server is ready to serve on (?P<where>\S+)", "loaded and serving on {where}"),
        ("timing", r"Decode batch, .*gen throughput \(token/s\): (?P<tok_s>[\d.]+)", "decoding at {tok_s} tok/s"),
        ("timing", r"Prefill batch, .*#new-token: (?P<tokens>\d+).*input throughput \(token/s\): (?P<tok_s>[\d.]+)",
         "a prefill of {tokens} tokens at {tok_s} tok/s"),
        ("disk-bound", r"MoE decode, (?P<group>\w+) (?P<layers>\d+) layers?: hit (?P<hit>[\d.]+)%",
         "the expert cache hits {hit}% of the experts a step asks: the misses stream over the host link, so the link "
         "is the limit", ("hit", "<", 50.0)),
        ("backend-fallback", r"banks (?P<banks>[\d.]+) GiB > pin budget (?P<budget>[\d.]+) GiB; locking (?P<locked>\d+)",
         "{banks} GiB of expert banks over a {budget} GiB pin budget (WSL caps CUDA pinning): {locked} layers decode "
         "on the CPU, slower"),
        ("loading", r"Prefill warmup complete for lengths .* in (?P<seconds>[\d.]+) s",
         "the startup warmup took {seconds} s: FreeToken compiled its CUDA kernels (once per install)",
         ("seconds", ">=", 60.0)),
        ("error", r"expert banks need (?P<banks>[\d.]+) GiB of pinned host RAM but the pin budget is (?P<budget>[\d.]+)",
         "the expert banks need {banks} GiB pinned, the pin budget is {budget} GiB: the load stopped"),
        ("error", r"nvcc [\d.]+ would build kernels|Install a CUDA \d+\.x toolkit|nvcc: (?:not found|command not found)",
         "the CUDA toolchain does not match: FreeToken compiles its kernels with nvcc from CUDA 13"),
        ("error", _OOM, "FreeToken ran out of GPU or pinned memory"),
        ("error", r"^\w*(?:Error|Exception): (?P<why>.{1,160})", "FreeToken logged an error: {why}")]},
    "fixes": {"disk-bound": ("a smaller model, a bigger cache share (ft ctl cache --moe N, live), or NVLink-class "
                             "hardware", "VRAM from the KV cache, or a smaller model's quality"),
              "backend-fallback": ("serve it from native Linux, or a smaller checkpoint",
                                   "a reboot into Linux, or a smaller model's quality"),
              "loading": ("nothing: later requests do not pay the kernel compile; the session's wait allows it", "none")},
    "fit": {"rule": "paged-moe", "gpu_share": 0.9, "fit_share": 0.75, "tight_share": 0.9, "spare_gb": 0.0,
            "tight_gb": 0.0, "map_share": None, "wsl_pin_share": 0.4, "link": "PCIe at 32-64 GB/s (FreeToken's figure)",
            "disk_bps": 1.5e9},
    "tune": {"ctx-size": "--max-seq-len-override {value}", "n-predict": "--max-output-tokens 32768"},
    "verified": False,
}

STRATA = {
    "id": "strata", "label": "Strata", "url": "https://github.com/Niko1221/Strata", "license": "MIT",
    "what": "one big Mixture-of-Experts model on one machine, natively on Windows, Linux and the Mac: the experts in "
            "host RAM, the rest streamed from the SSD",
    "source": "main at ffa80d73, read 2026-11-02", "default_port": 8080, "base_path": "/v1", "health": "/health",
    "stats": None, "detect": {"health": {"service": "strata"}, "window": "n_ctx"}, "programs": ("strata",),
    "version": r"^strata (\S+)",
    "install": {"windows": "in PowerShell: irm https://github.com/Niko1221/Strata/releases/latest/download/install.ps1 "
                           "| iex (then open a new terminal so strata is on PATH)",
                "posix": "curl -fsSL https://github.com/Niko1221/Strata/releases/latest/download/install.sh -o "
                         "install.sh && sh install.sh (it puts strata in ~/.local/bin)"},
    "requires": "a graphics card: NVIDIA RTX 20-50, AMD Radeon RX 7000 / 9000 or Apple Silicon; the first launch "
                "downloads the set (tens to hundreds of GB, the owner's to run)",
    "backends": ("cuda", "rocm", "metal"), "os": ("windows", "linux", "macos"), "arch": (), "first_wait_s": None,
    "start": {"model": "set", "wait_s": 180.0, "supervised": True, "key": {"env": "{key_env}"},
              "argv": ["launch", "--family", "{model_head}", "--model", "{model_tail}", "--yes", "--no-tui", "--access",
                       "{access}", "--port", "{port}", "--api-key-env", "{key_env}"],
              "plan": ["launch", "--family", "{model_head}", "--model", "{model_tail}", "--plan", "--output", "json",
                       "--port", "{port}", "--access", "{access}"],
              "status": ["launch", "--status", "--output", "json"], "stop": ["launch", "--stop", "--preset", "{name}"],
              "log_line": r"^\s*Engine log\s+(\S.*?)\s{2,}\(follow it",
              "server_log": "{log_dir}/../runtime/{profile}.server.log"},
    "log": {"stamp": None, "names_model": False, "patterns": [
        ("loading", r"starting the engine: reading the model's weights", "starting the engine: reading the weights"),
        ("disk-bound", r"mapping the experts from the model files",
         "the experts are mapped from the model files: what RAM cannot hold is read from the SSD, much slower"),
        ("disk-bound", r"RAM is tight - the model's experts take (?P<experts>[\d.]+) GB of this PC's (?P<ram>\d+) GB, "
                       r"leaving (?P<left>[\d.-]+) GB", "RAM is tight: the experts take {experts} GB of {ram} GB"),
        ("disk-bound", r"the RAM budget for experts is (?P<budget>[\d.]+) GiB \(--resident-budget-gib\), but this PC "
                       r"has (?P<free>\d+) GiB free", "the experts' RAM budget is {budget} GiB: the rest is read from disk"),
        ("loaded", r"^ready: http://(?P<where>\S+?)/v1\s+\(OpenAI: .*?context (?P<window>\d+) tokens",
         "ready on {where}, window {window}"),
        ("slots", r"parallel requests: (?P<asked>\d+) asked, the engine runs (?P<runs>\d+|one at a time)",
         "{asked} parallel requests asked, the engine runs {runs} (the VRAM guide: 12 GB runs 1, 20 GB 2, 24 GB 3, "
         "32 GB and more 4)"),
        ("waiting", r"parallel: a request has waited (?P<waited>\d+) s", "a request waited {waited} s for a free slot"),
        ("timing", r"done: (?P<tokens>\d+) tokens in (?P<secs>\d+) s \((?P<tok_s>[\d.]+) tok/s\)",
         "a reply of {tokens} tokens at {tok_s} tok/s"),
        ("loading", r"Downloading the engine\W+(?P<pct>\d+)%", "downloading the engine ({pct} %): not a timeout"),
        ("loading", r"Downloading (?P<done>[\d.]+) of (?P<total>[\d.]+) GB",
         "the first launch is downloading the set: {done} of {total} GB (Strata's own download, not a timeout)"),
        ("error", r"Strata couldn't find an engine for this computer|the engine did not start|the engine exited before",
         "Strata did not start its engine"),
        ("error", r"the GPU reported a fatal error \((?P<why>[^)]*)\)", "Strata's GPU failed: {why}"),
        ("error", _OOM, "Strata ran out of memory"),
        ("error", r"(?:503: |400 invalid request: |the engine reported an error: )(?P<why>.{1,160})",
         "Strata logged an error: {why}")]},
    "fixes": {"disk-bound": ("a smaller set (halo models search strata lists them with their experts' GB), or more RAM",
                             "a smaller set's quality, its download, or a RAM upgrade"),
              "slots": ("at most the engine's slots of Halo's lanes on this server at once, or a bigger card",
                        "lanes wait for each other"),
              "waiting": ("fewer lanes on this server at once", "lanes wait for each other")},
    "fit": {"rule": "paged-moe", "gpu_share": None, "fit_share": 1.0, "tight_share": 1.0, "spare_gb": 10.0,
            "tight_gb": 6.0, "map_share": 2.0, "wsl_pin_share": None, "link": "the SSD", "disk_bps": 1.5e9,
            "slots": ((32, 4), (24, 3), (20, 2), (0, 1))},
    "tune": {"ctx-size": "--context {value}", "cache-type": "--kv {kv}"},
    "verified": False,
}

TENSORFOLD = {
    "id": "tensorfold", "label": "TensorFold", "url": "https://github.com/ashhart/TensorFold", "license": "Apache-2.0",
    "what": "a Hugging Face checkpoint held whole in the card's memory (Metal on Apple Silicon, CUDA on NVIDIA), one "
            "Zig binary with no Python or MLX",
    "source": "main at 532589e4, release v1.2.1, read 2026-11-02", "default_port": 8080, "base_path": "/v1",
    "health": "/health", "detect": {"owned_by": "tensorfold"}, "programs": ("tensorfold", "tensorfold-native"),
    "stats": {"live": "live", "metrics": "/metrics", "waiting": "tensorfold:requests_waiting",
              "running": "tensorfold:requests_running", "lanes": "tensorfold:lanes"},
    "version": r"^tensorfold(?:-native)? v?(\S+)",
    "install": {"macos": "brew install ashhart/tensorfold/tensorfold (Apple Silicon, macOS 13 or newer)",
                "linux": "the release archive tensorfold-<version>-linux-<x86_64|aarch64>.tar.gz from its releases page "
                         "(check its .sha256; it needs glibc 2.28+ and an NVIDIA driver R580+), then point "
                         "huggingface.engine_bins.tensorfold at its bin/tensorfold-native",
                "windows": "built from source (docs/WINDOWS.md in its repo: Zig 0.17.0, the CUDA toolkit, MSVC's C++ "
                           "build tools), then point huggingface.engine_bins.tensorfold at tensorfold-native.exe"},
    "requires": "Apple Silicon (Metal) or an NVIDIA card (CUDA 13, driver R580+)",
    "backends": ("metal", "cuda"), "os": ("macos", "linux", "windows"), "arch": (), "first_wait_s": None,
    "start": {"model": "repo-or-dir", "wait_s": 120.0, "key": {"file": "--api-key-file"}, "window": 32768,
              "env": {"TENSORFOLD_LOG_TIME": "1", "TENSORFOLD_NO_LIVE": "1"},
              "argv": ["serve", "{model}", "--name", "{name}", "--host", "{host}", "--port", "{port}", "--context",
                       "{window}"], "parallel": ["--parallel", "{parallel}"]},
    "log": {"stamp": r"^(\d{4}-\d\d-\d\d)T(\d\d:\d\d:\d\d)(?:\.\d+)?Z\s+", "utc": True, "patterns": [
        ("backend-fallback", r"CUDA sm_(?P<sm>\d+) device \d+ \((?P<device>[^),]*)",
         "an NVFP4 checkpoint on {device} (sm_{sm}, no thread-block clusters) runs TensorFold's fallback path, slower",
         ("sm", "between", (80, 89)), ("model", "has", "nvfp4")),
        ("slots", r"(?P<streams>\d+) streams? at once", "TensorFold runs {streams} streams at once"),
        ("loaded", r"serving (?P<name>\S+) at http://(?P<where>\S+?)/v1 \(.*?context: (?P<window>\d+|unlimited); "
                   r"loaded in (?P<load_s>[\d.]+)s\)", "{name} loaded in {load_s} s on {where}, window {window}"),
        ("waiting", r"done \S+ .*?queued=(?P<queued>[1-9][\d.]*) tok/s=(?P<tok_s>[\d.]+)",
         "a reply waited {queued} s in TensorFold's queue past its streams"),
        ("timing", r"done \S+ prompt=(?P<prompt>\d+) .*?tokens=(?P<tokens>\d+) .*?tok/s=(?P<tok_s>[\d.]+)",
         "a reply of {tokens} tokens at {tok_s} tok/s"),
        ("waiting", r"(?P<conns>\d+) connections? \((?P<waiting>[1-9]\d*) waiting\)", "{conns} connections, {waiting} waiting"),
        ("error", r"warning: a reply reached max_tokens while still thinking", "a reply reached max_tokens while still "
         "thinking: its content is empty"),
        ("error", r"ended \S+ reason=error \((?P<why>[^)]*)\)", "TensorFold ended a request: {why}"),
        ("error", r"^tensorfold(?: serve)?: (?:error: )?(?P<why>.{1,160})", "TensorFold did not start: {why}"),
        ("error", _OOM, "TensorFold ran out of memory")]},
    "fixes": {"waiting": ("--parallel with more streams if memory holds them (TensorFold refuses a count that does not "
                          "fit), or a smaller model; at most its streams of Halo's lanes at once",
                          "each stream takes memory from the window"),
              "backend-fallback": ("the model's MLX 4-bit checkpoint, or a card of sm_90 and later",
                                   "another download, or a newer card")},
    "fit": {"rule": "vram", "reserve_unified": (4.0, 0.1), "reserve_discrete": (1.0, 1 / 32), "fallback_sm": (80, 89),
            "disk_bps": 1.5e9},
    "tune": {"ctx-size": "--context {value}", "n-predict": "--max-tokens 32768"},
    "verified": False,
}

TABLE = {e["id"]: e for e in (FREETOKEN, STRATA, TENSORFOLD)}


def ids() -> tuple:
    return tuple(TABLE)


def get(word) -> Optional[dict]:
    """The entry whose id is `word` (a runtime word, a registry kind, an entry name), or None."""
    return TABLE.get(str(word or "").strip().lower())


def is_engine(word) -> bool:
    return get(word) is not None


def install_line(d: dict, os_name: str) -> str:
    """The owner's install line for THIS OS (Halo never installs an engine), or where the engine does not run."""
    os_name = str(os_name or "").lower()
    inst = d["install"]
    got = inst.get(os_name) or (inst.get("posix") if os_name in ("linux", "macos") else None)
    return got or f"{d['label']} ships nothing for {os_name or 'this OS'} ({d['requires']})"


def kinds(d: dict) -> tuple:
    """The steward event kinds this engine's log can state (server_rules_hf.SAYS)."""
    return tuple(dict.fromkeys(WORDS[p[0]] for p in d["log"]["patterns"]))
