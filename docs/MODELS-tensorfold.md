# Models: TensorFold, a native engine for the Mac and NVIDIA

Read this when you want to serve a Hugging Face model with TensorFold -- one binary, Metal on an Apple Silicon Mac (beside mlx_lm.server) or CUDA on Linux and Windows, no Python -- and need to know how to install it, which models it qualifies and how big they are, whether one fits your machine, and what the steward says about it.

Part of [Models](MODELS.md), which lists every part. The other local servers: [MODELS-steward-servers.md](MODELS-steward-servers.md); the Mac's first native engine, mlx_lm.server: [MAC.md](MAC.md); the big-MoE engines: [MODELS-freetoken.md](MODELS-freetoken.md), [MODELS-strata.md](MODELS-strata.md).

## What it is (3.3.9.3)

[TensorFold](https://github.com/ashhart/TensorFold) (Apache-2.0) serves language models from one Zig binary. It reads
a Hugging Face checkpoint, tokenizes requests and runs Metal kernels on an Apple Silicon Mac or CUDA kernels on an
NVIDIA card directly: serving needs no Python and no MLX. It holds the checkpoint whole in the card's memory -- the
Mac's unified memory, or VRAM -- and serves several requests at once ("streams", up to eight by default as memory
allows). Its server speaks OpenAI's chat, completions and Responses APIs and Anthropic's Messages on
`http://127.0.0.1:8080`, with `/v1/models`, `/health`, Prometheus `/metrics`, `/memory`, and a `/dashboard` with
`--dashboard`.

To Halo it is one more local runtime, `tensorfold`, beside llama-server, LM Studio, mlx_lm.server, FreeToken and
Strata: an OpenAI-compatible local server reached as `hf:local/<model>@tensorfold` on its machine and
`hf:local/<model>@<host>` from a peer. On the Mac it is the second native engine beside mlx_lm.server.

Every TensorFold fact on this page is from its README, RUNBOOK.md, docs (`api.md`, `WINDOWS.md`), packaging and
source (`zig/src/server/`, `zig/src/native/cuda_startup.zig`, `tools/release/package.sh`), read 2026-11-02 at main
532589e4 and release v1.2.1, and **unverified against a live run**: no TensorFold has run against Halo yet. The log
lines the steward reads are written from that source; a live log may word them otherwise.

## Install

| Machine | How | What Halo says when it is missing |
|---|---|---|
| Apple Silicon Mac (macOS 13+) | `brew install ashhart/tensorfold/tensorfold` -- the formula links `tensorfold` and `tensorfold-native` | that line |
| Linux x86_64 / aarch64, NVIDIA driver R580+ (CUDA 13), glibc 2.28+ | `halo local serve --runtime tensorfold --yes` fetches the release archive (below), or install it by hand from the releases page | the fetch, with its size and destination |
| Windows with an NVIDIA card | built from source: TensorFold's `docs/WINDOWS.md` (Zig 0.17.0, the CUDA toolkit, MSVC's C++ build tools, `zig build native install -Dsm=89 -Dstrip=true`); set `huggingface.tensorfold_bin` to its `zig-out\native\bin\tensorfold-native.exe` | the build guide |

Where Halo looks, in order: `huggingface.tensorfold_bin` (a path, or the program and its first arguments), then
`tensorfold` or `tensorfold-native` on PATH, then the archive Halo fetched.

### The fetched Linux archive

On Linux x86_64 or aarch64 with no binary found, `halo local serve --runtime tensorfold` offers to fetch TensorFold
the way it fetches llama-server (providers/local_runtime_fetch_tf.py on the same fetcher): it reads the release list
of `ashhart/TensorFold`, takes the newest `v<version>` release that carries both files for this CPU, and says the file,
its size (about 41 MB for 1.2.1), its URL and where it goes before anything moves; `--yes` answers yes.

| Platform | Archive | Checksum |
|---|---|---|
| `linux-x86_64` | `tensorfold-<version>-linux-x86_64.tar.gz` | `tensorfold-<version>-linux-x86_64.tar.gz.sha256` |
| `linux-aarch64` | `tensorfold-<version>-linux-aarch64.tar.gz` | `tensorfold-<version>-linux-aarch64.tar.gz.sha256` |

Two checks before the unpack: GitHub's per-asset digest, and the `.sha256` file's own hex (`<hex>  <archive name>`);
a mismatch stops it with nothing unpacked. The archive unpacks into `~/.halo/runtimes/tensorfold-v<version>/`, its
`bin/tensorfold-native` beside its `lib/` and `share/` (kept together, as TensorFold asks), never added to PATH;
`halo local runtime remove tensorfold-v<version>` takes it out. The Mac app's `app-v...` releases are skipped; the Mac
takes Homebrew.

## The models

TensorFold's README qualifies each model on named machines; Halo's table (tensorfold/catalog.py) keeps those words,
the sizes the README states and the `tensorfold pull` line. A few of them:

| Model | Repo | Size (the README's) | Qualified on |
|---|---|---|---|
| Qwen3.5-2B MLX 4-bit | `mlx-community/Qwen3.5-2B-MLX-4bit` | not published | one Mac (M5 Max) or one GB10 |
| Qwen3.8-27B MLX 4-bit | `TensorFold/Qwen3.8-27B-MLX-4bit` | 16 GiB | one Mac (M5 Max / M3 Ultra) or one GB10 |
| Nemotron 3.5 Lightning 30B-A3B MLX 4-bit | `TensorFold/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-MLX-4bit` | not published | one Mac (M1-M5), a GB10, RTX 3090 |
| Qwen3.6-35B-A3B MLX 4-bit MTP | `TensorFold/Qwen3.6-35B-A3B-MLX-4bit-MTP` | 20.9 GB | one GB10, native CUDA only |
| Qwen3.6-35B-A3B NVFP4 | `nvidia/Qwen3.6-35B-A3B-NVFP4` | 20.9 GiB with the drafter | one GB10 |
| Gemma 4 12B (converted MLX 4-bit) | `google/gemma-4-12B-it` + its conversion | 6.3 GB | one M5 Mac; M1-M4 refused |
| LFM2.5-24B-A2B MLX 4 / 8-bit | `LiquidAI/LFM2.5-24B-A2B-MLX-4bit` | not published | one Mac (M4 Pro) |
| GLM-5.3-Flash FP4-Local / XSFP4 / NVFP4 | `nvidia/GLM-5.3-Flash-FP4-Local` ... | 165.3 / 165.7 / 190.4 GiB | two GB10s (TP=2), not one machine |

`halo models browse --source hf tensorfold` lists them all in the Library, each with its `tensorfold pull` line (the download is
yours to run) and the TensorFold fit as its badge. TensorFold's Qwen3.6-35B-A3B MLX checkpoint is qualified on native
CUDA only: its recipe's Metal path is the older Python engine's, so on a Mac the fit says it does not fit; the Mac's
models are the 2B, the 27B, Nemotron 3.5 Lightning, LFM2.5 and Gemma 4 (M5).

## Serve

```sh
halo local serve --runtime tensorfold --model TensorFold/Qwen3.8-27B-MLX-4bit
halo local serve --runtime tensorfold --model ~/models/my-checkpoint --window 65536 --parallel 4
```

The model is a Hugging Face repo id or a checkpoint folder (one with its `config.json`):

- a repo in the Hugging Face cache TensorFold reads (`HF_HUB_CACHE`, else `HF_HOME/hub`, else
  `~/.cache/huggingface/hub`): served by its repo id, as `tensorfold serve <repo>` takes it;
- a repo Halo's download job put in a `huggingface.model_dirs` folder (the cache's own layout): served by its snapshot
  folder's path;
- a repo nowhere on disk: nothing starts; one line says its size from TensorFold's table and the two routes --
  `tensorfold pull <repo>` (TensorFold's own download into the Hugging Face cache, yours to run) or `halo local
  download <repo>` -- exit 2. Halo never downloads a checkpoint by itself.

The command Halo runs: `tensorfold serve <repo | folder> --name <model> --host 127.0.0.1 --port <a free loopback port>
--context <N> --api-key-file <file>` (`--parallel N` when given). The window is `--window`, else the table's default
for the model, else 32,768. The key is Halo's (`HALO_SECRET_TENSORFOLD_API_KEY` in the env file, never config.json),
written to `~/.halo/local/servers/tensorfold.key` owner-only (0600: TensorFold refuses a key file others can read),
so it never sits on a command line. TENSORFOLD_LOG_TIME=1 stamps each of its log lines.

TensorFold opens its port only once the checkpoint is in memory. Halo waits up to two minutes for `/health`; a bigger
load goes on in the background and is said, never a timeout. A refusal at startup (a driver older than R580, a key
file it will not read) is said with its line, exit 2. It is the server `tensorfold` for `halo local servers | log |
stop`; the stop takes the entry and the key file out. `--lan` binds every address (behind the same key) so peers reach
it. `--keep` keeps it after the last Halo process exits.

The entry Halo writes: `{name: tensorfold, url, log, runtime: tensorfold, model, pid, tensorfold: true, lan,
api_key_env}`. A TensorFold server started by hand on 8080 (or any probed port) is found by the loopback auto-detect:
its `/v1/models` rows say `owned_by: tensorfold`, their `context_length` is the window, and it is listed as
`auto:<port>` with runtime `tensorfold`. A hand-started server with a key needs a `huggingface.local_servers` entry
carrying it.

## The fit

TensorFold holds the checkpoint whole in the card's memory, so its fit is the ordinary VRAM rule with TensorFold's
own figures (local_sched/fit_tf.py): the checkpoint's size plus TensorFold's reserve must fit, and what is left holds
the window's KV and the streams. The reserve: a 32nd of a discrete card, at least 1 GiB; on unified memory a tenth of
RAM, at least 4 GiB (TensorFold states that one for the GB10; Halo applies it to the Mac, whose Metal reserve is not
stated). On the Mac the budget is the unified memory the hardware card says the GPU may use. One line per model and
host, for example:

- a 24 GB 4090: "fits: Qwen3.8-27B MLX 4-bit (16 GiB) on pc: the 4090's 24 GB, less TensorFold's 1.0 GB reserve,
  leaves 7.0 GB for the 32,768-token window's KV and its streams ...";
- a Mac with 64 GB (48 GB for the GPU): "fits: ... leaves 26 GB ..."; Qwen3.6-35B-A3B MLX: "does not fit:
  TensorFold qualifies ... on CUDA only";
- a 10 GB 3080: "does not fit: Qwen3.8-27B MLX 4-bit (16 GiB) needs 17 GB with TensorFold's 1.0 GB reserve";
- an NVFP4 checkpoint on an RTX 30 / 40 card (sm_80 to sm_89, no thread-block clusters): it fits with "runs
  TensorFold's fallback path: slower" said; a two-machine model is out on one machine; a model TensorFold publishes no
  size for is "unknown" with `tensorfold info <repo>` named.

`halo local serve --runtime tensorfold` prints the fit here before it starts; it never stops you.

## What the steward reads

The log (ollama_steward/server_log_tensorfold.py): the capacity line ("CUDA sm_89 device 0 (...): model 16.02 GiB; 4
streams at once, ..."; Metal's wording is not in the source read, so the reader keys on "N streams at once" and the
backend word), the serving line ("serving <model> at http://127.0.0.1:P/v1 (...; context: N; loaded in S s)"), one
"done ..." line per request (its tok/s and its queued seconds), "ended ... reason=error (...)", the max-tokens-while-
thinking warning, and a fatal "tensorfold: ..." startup line. The queue (server_stats_tensorfold.py): `/health`'s
`live.waiting` on a server without keys; with keys `/health` says only `{"status": "ok"}`, so for Halo's own server the
steward reads `tensorfold:requests_waiting` from `/metrics` with Halo's key. Three findings, keyed `<server>|<model>`,
each with a stated line never applied:

- **tf-waiting** -- requests queue past the streams TensorFold accepted: `--parallel` with more streams if memory holds
  them (a count that does not fit is refused at startup), or a smaller model; at most that many of Halo's lanes on it.
- **tf-backend-fallback** -- an NVFP4 checkpoint on an sm_80-89 card runs the fallback path, slower: the model's MLX
  4-bit checkpoint, or a newer card.
- **tf-load** -- a load still going a minute after Halo started it, or one that took over three minutes: said, never a
  timeout; a restart costs it again.

`halo ollama explain tf-waiting` (and the others) answers from the knowledge.

## Through the host (the Mac as a host)

A TensorFold server on the Mac is a host-served local server: with `halo host` running there, the join reply and the
announce list it (`kind: server`, `runtime: tensorfold`, its model). Started with `--lan`, the host's catalog offers its
entry and key to paired peers, and the PC or Kali reach it as `hf:local/<model>@<the Mac's host name>` (or
`@tensorfold`) at the Mac's LAN address. No model runs inside `halo host`: it only lists and offers.

## In placement

Placement (`halo local place`, the adviser) sees a TensorFold server beside the Ollama hosts, mlx_lm.server, the pool,
FreeToken and Strata: the model it serves is warm; another model of TensorFold's table is a restart with the loading
tax said -- the checkpoint read into memory (its GB over 1.5 GB/s) and its `tensorfold pull` if it is not there -- and
a model TensorFold does not name is out.

## `halo doctor --local`

When the runtime is configured (`huggingface.tensorfold_bin`, or a tensorfold server in the roster): `tensorfold
--version` and `tensorfold capabilities --json` (the backends this binary has -- `metal` or `cuda` -- the engine and
its families), each OK, or a WARN with this machine's install line; a CUDA build on a Mac is a WARN.

## Not done this round

The capability battery against a TensorFold server (it is Ollama-shaped); Studio pages beyond the Library badge;
`/dashboard`, `/stats`, `/memory` and `/v1/load`; TensorFold's two-machine serving (GLM-5.3, Flash Next on two Macs);
Living Weights (`--slide`), Cortheon mode and its compaction; `tensorfold benchmark`. The Mac's live check and the
Windows native build are the owner's.
