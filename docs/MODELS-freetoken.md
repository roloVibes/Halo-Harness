# Models: FreeToken, a big Mixture-of-Experts model on one box

Read this when you want to run a Mixture-of-Experts model bigger than your graphics card on one Linux machine with FreeToken, and need to know what to install, which checkpoints it serves, whether one fits your RAM and link, and what the steward says about it.

Part of [Models](MODELS.md), which lists every part. The other local servers: [MODELS-steward-servers.md](MODELS-steward-servers.md); the pool, which spreads one model across several machines instead: [POOL.md](POOL.md).

## What it is (3.3.9.1)

[FreeToken](https://github.com/FlashML-org/FreeToken) (Apache-2.0) serves a large Mixture-of-Experts (MoE) model on
one consumer machine by treating the GPU, the CPU, host RAM and the link between them as one pool. With its default
`offload` strategy the dense layers (attention, embeddings) and the KV cache stay on the GPU, the routed experts live
in host RAM, and an **expert cache** (an LRU cache of expert slots) sits on the GPU; each expert a decode step asks for
that is not in the cache is copied over PCIe. It serves the OpenAI API (and Anthropic's, which Halo does not use) on
`http://127.0.0.1:1919/v1` by default.

To Halo it is one more local runtime, `freetoken`, beside llama-server, LM Studio and mlx_lm.server: an
OpenAI-compatible local server reached as `hf:local/<model>@freetoken` on its machine and `hf:local/<model>@<host>`
from a peer. It is the other answer to "a model bigger than my card": the pool buys capacity across machines at a
speed cost; FreeToken runs one big MoE on one box out of RAM and NVMe. It is MoE-first: for a dense model Ollama,
llama-server and the pool stay the answer.

Every FreeToken fact on this page is from its README, docs and source, read 2026-11-02, and **unverified against a
live run**: no FreeToken has run against Halo yet. The log lines the steward reads are written from its source
(`engine/engine.py`, `moe/offload_cache.py`, `scheduler/status.py`, `server/api_server.py`); a live log may word them
otherwise.

## What it needs

- Linux x86_64 and an NVIDIA GPU (RTX 30, 40 or 50 series) with driver r580 or newer (CUDA 13).
- The CUDA 13 toolkit with `nvcc` on PATH: FreeToken compiles its CUDA kernels on first use (the first request after
  an install takes minutes; later ones do not pay it).
- Python 3.10 or newer; `uv` is what its docs use.
- Enough host RAM for the experts, and a fast NVMe for the biggest checkpoints.

No macOS; AMD is a work in progress on its side. **WSL2** runs it, with one caveat: WSL caps CUDA pinned memory near
half of RAM (FreeToken budgets 40 %), so a large expert bank may not all pin; FreeToken then locks the rest for CPU
decode (slower) with `--moe-cpu-layers auto`, or stops the load and says so.

`halo doctor --local` checks all of it when the runtime is configured (a `freetoken` server, or
`huggingface.freetoken_bin` set): the platform, `ft --version`, the driver line, `nvcc`, and the WSL2 caveat. A missing
piece is one line with the command that installs it; nothing is refused.

## Install on Ubuntu

These are the lines FreeToken's docs and NVIDIA's packages state (the toolkit's apt name follows NVIDIA's own
naming, unverified here):

```sh
sudo ubuntu-drivers install            # or: sudo apt install nvidia-driver-580
sudo apt install cuda-toolkit-13-0     # from NVIDIA's apt repo; puts nvcc under /usr/local/cuda/bin
export PATH=/usr/local/cuda/bin:$PATH
uv venv && source .venv/bin/activate
uv pip install "freetoken[accel]"
ft --version
```

`ft bench bw` measures the host link once per machine (see "The fit" below); `halo local bench --host freetoken --bw`
runs it for you with its cost line first.

## Serve

```sh
halo local serve --runtime freetoken --model ~/models/Qwen3.6-35B-A3B-NVFP4
halo local servers                     # freetoken  freetoken  http://127.0.0.1:P  ready  hf:local/<model>@freetoken
halo local log freetoken               # FreeToken's own log
halo local stop freetoken
```

Halo runs `ft serve --model <dir> --served-model-name <folder name> --host 127.0.0.1 --port <a free loopback port>
--moe-collect-stats` (the last flag puts the expert cache's hit rate on each decode log line, which the steward
reads), with `ft` from `huggingface.freetoken_bin` or PATH. Its output goes to `~/.halo/local/servers/freetoken.log`
after Halo's `--- halo starts:` line; it is the registry row `freetoken` and the `huggingface.local_servers` entry
`freetoken` (url, log, runtime, model, pid), so the session uses it as `hf:local/<model>@freetoken`.

- A load longer than two minutes goes on in the background: the line says how far it got ("still loading (2.0 of
  18.0 GiB)").
- The first request after an install compiles the kernels: the session waits up to 30 minutes for its first byte from
  a FreeToken server (other servers: 5), so it is never cut as a timeout.
- `--lan` binds every address so peers can reach it, behind a key Halo generates (kept in the env file as
  `HALO_SECRET_FREETOKEN_API_KEY`, handed to `ft serve` as `FREETOKEN_API_KEY`, never on its command line).
- A FreeToken server you started by hand on port 1919 is found by the loopback sweep (1919 joined 8080, 8000 and 1234)
  and named by its runtime: its `/v1/models` rows say `owned_by: FreeToken`.

## Which checkpoints

The MoE checkpoints FreeToken's docs name as known-good are the Library's FreeToken download targets (Models ->
Hugging Face, `halo models browse --source hf freetoken`), each with the FreeToken fit as its badge and `halo local download
<repo>` as its pull line. They are listed when the search names FreeToken or the runtime is configured.

| Model | Checkpoints | Weights | Beyond the experts |
|---|---|---|---|
| Qwen3.6-35B-A3B | nvidia/...-NVFP4, Qwen/...-FP8, Qwen/... (BF16) | 35B, 3B active | |
| gpt-oss-120b / 20b | openai/gpt-oss-120b, openai/gpt-oss-20b (MXFP4 experts) | 117B / 21B, 5.1B / 3.6B active | |
| Gemma-4-26B-A4B | nvidia/...-NVFP4, google/gemma-4-26B-A4B-it | 26B, 4B active | image input |
| Qwen3-30B-A3B, Qwen3-VL-30B-A3B | Qwen/Qwen3-30B-A3B, Qwen/Qwen3-VL-30B-A3B-Instruct | 30B, 3B active | |
| DeepSeek-V4.1-Flash | deepseek-ai/DeepSeek-V4.1-Flash | not stated | two 98 GiB tables streamed from NVMe, 6 GiB of scales in RAM |
| Qwen3.8-Flash-Next | nvidia/...-NVFP4, Qwen/...-FP8 | not stated | a 47.7 GiB table pinned in RAM |
| GLM-5.3-Flash, GLM-5.2, MiniMax-M2.5, MiniMax-M3 | their NVFP4 checkpoints | not stated | |

"Not stated" sizes come from the checkpoint itself once downloaded (its `config.json` and safetensors index).

## The fit: RAM and the link, not VRAM

The fit for a FreeToken server is its own rule (`local_sched/fit_ft.py`), one deterministic line per model and host:

- **On the GPU:** the dense bytes (for a catalog row, the active weights at the format's bits per weight) + the KV at
  the window (from `config.json`: 2 x the full-attention layers x the KV heads x the head size x 2 bytes) + one whole
  layer of experts (FreeToken's expert cache must stage one), against 90 % of the card's free VRAM
  (`--memory-ratio` 0.9).
- **In host RAM:** the expert bytes (+ any table FreeToken states) against 90 % of RAM; over 75 % is "tight"; under
  WSL2, over 40 % of RAM is "fits, slower" (the pin cap: those layers decode on the CPU).
- **The link:** `ft bench bw`'s PCIe-gather GB/s once measured (`halo local bench --host freetoken --bw`), else
  "PCIe at 32-64 GB/s extrapolated (FreeToken's figure)".
- **The speed:** the FreeToken speed card's reply tok/s once benched, else "speed not measured yet".

On the fixture boxes (samus: a 10 GB RTX 3080, 64 GB of RAM, Linux; pc: a 24 GB 4090, 64 GB, WSL2):

```
fits: Qwen3.6-35B-A3B on samus, 1.6 GB active on the 3080, 17 GB of experts in RAM over PCIe at 27.9 GB/s measured; speed not measured yet
does not fit: Qwen3.6-35B-A3B needs 60 GB of experts in RAM, 64 GB on samus (58 GB usable)           (the BF16 one)
fits, tight: gpt-oss-120b on samus, 2.5 GB active on the 3080, 55 GB of experts in RAM over PCIe at 32-64 GB/s extrapolated ...
fits, slower: gpt-oss-120b on pc, ... under WSL about 26 GB pins (FreeToken budgets 40 % of RAM), the rest decodes on the CPU
does not fit: FreeToken runs on Linux x86_64 (pc is windows; on Windows, WSL2 runs it with the pinned-memory cap)
```

The arithmetic cannot know how fast a given model decodes over a given link: the speed card measures it.

## The speed card and the battery

`halo local bench --host freetoken [--quick]` runs the 3.3.6.0 battery's windows (8k, 32k, the served model's
`context_length`) and the reply reserve against the FreeToken server, with its cost line first. FreeToken's replies
carry OpenAI `usage` but no per-phase timings, so each window is two calls: the prompt with a one-token reply (its time
is the first token: prompt tok/s), then the same prompt with a 256-token reply, whose prefill FreeToken's prefix cache
spares (its time is the decode). An untimed warm-up goes first so the kernel JIT is never counted. The card lands
under the server's name (`freetoken|<model>`), and the Library's fit line and placement read it.

## In placement and through the host

- **Through the host:** a FreeToken server on the host machine is a host-served local server: the join and the
  announce list it (`kind: server`, `runtime: freetoken`, its model), and with `--lan` the host's catalog offers its
  entry and key, so a peer with no entry of that name reaches it as `hf:local/<model>@<host>` at the host's address.
  A loopback-only server is not offered.
- **Placement** (`halo local place`, the adviser) sees each FreeToken server beside the Ollama hosts and the pool: the
  model it serves is warm (no load); another checkpoint FreeToken names is a restart with the loading tax said ("a
  restart onto gpt-oss-120b, ~41 s reading its experts from disk, the kernel JIT on a first install (minutes, once),
  evicts ..."); a dense model is out. Nothing restarts a server by itself.

## What the steward says

The steward reads FreeToken's log like any local server's (its stamp `[YYYY-MM-DD|HH:MM:SS|pid=N]`, ANSI colours
stripped): the load (the strategy, the expert format, the cache's slots, the warmup), each prefill and decode line's
tok/s, the expert cache's hit rate, the pin-budget lines. Three findings, keyed `<server>|<model>`, each with a stated
fix that is never applied by itself (`halo ollama steward findings`, the Steward page, `halo ollama explain <kind>`):

| Finding | When | What it says |
|---|---|---|
| `ft-expert-thrash` (warn) | the expert cache hits under 50 % over the newest decode stats | the misses cross the host link, so the link is the limit: a smaller model, a bigger cache share (`ft ctl cache --moe N`, live), or NVLink-class hardware |
| `ft-pinned-cap` (warn, error when the load stopped) | under WSL the expert banks did not all pin | run it on native Linux, or a smaller checkpoint |
| `ft-kernel-jit` (info, error when it cannot compile) | the startup warmup or the first call after a load took over a minute | the kernels compiled once, nothing to change; when nvcc is not CUDA 13: install the CUDA 13 toolkit |

## What is not taken

FreeToken's Anthropic-compatible API (Halo speaks OpenAI-compatible to local servers); its desktop app (its README
links one for Windows and Linux at flashml.ai: a separate GUI, not this runtime); its daemon
(`ft daemon`: Halo starts `ft serve` itself, the way it starts llama-server); replacing llama.cpp for dense GGUFs.
