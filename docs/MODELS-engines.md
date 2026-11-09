# Models: other local engines

Read this when you run (or want to run) a local engine beyond llama-server and mlx_lm.server -- FreeToken, Strata or TensorFold -- and need to know what Halo does with it, how to install it, whether a model fits your box, what the steward reads in its log, or how to add another engine.

Part of [Models](MODELS.md), which lists every part. The steward's side of every local server: [MODELS-steward-servers.md](MODELS-steward-servers.md); the pool, which spreads one model across several machines instead: [POOL.md](POOL.md).

## One adapter, one table (3.3.13.0)

Halo knows these engines through **one OpenAI-compatible adapter** (`halo_harness/engines/`) whose per-engine
knowledge is **one short descriptor table** (`halo_harness/engines/descriptors.py`). Each entry names the engine's port,
its OpenAI-compatible base path, its health and queue routes, how to recognise it on a port, its program and its
`--version` line, the install line per OS, where it runs, its managed start (and stop), the handful of its log lines
the steward reads (each with the sentence the steward says), the fix it states for each, its fit rule and its tuning
flags. To Halo each engine is a local server of runtime `<id>`: `hf:local/<model>@<id>` on this machine,
`hf:local/<model>@<host>` from a peer.

What Halo does: starts and stops an engine you installed (`halo local serve --runtime <id>`, `halo local stop <id>`),
recognises one you started yourself on its port, reads its log and queue, says whether a model fits, benches it,
serves it to paired peers through `halo host`, and places lanes on it. What Halo does **not** do: download or install
an engine, or download a model for one (the engine's own download is yours to run; Halo says its size and the command
first). Nothing runs unless the runtime word names an engine, its program is configured or on PATH, or its port
answers: a user with none of them sees no change, and llama-server and mlx_lm.server are untouched.

**`verified: false`.** Every port, route, pattern and figure in the table is from the engine's own source and docs,
read on the date the entry says. None has been checked against a live run yet: a live log may word a line otherwise.
An owner's live run turns an entry's `verified` to true.

## The table

| Engine | What it is | Port | Recognised by | Runs on | Start / stop | Fit rule |
|--------|------------|------|---------------|---------|--------------|----------|
| `freetoken` -- [FreeToken](https://github.com/FlashML-org/FreeToken) (Apache-2.0; main at dacac5f) | a big Mixture-of-Experts model on one machine: the routed experts in host RAM, an LRU cache of them on the GPU, each miss streamed over PCIe | 1919 | `/v1/models` `owned_by: FreeToken` | Linux x86_64, NVIDIA driver r580+ (CUDA 13), nvcc on PATH | `ft serve --model <dir> --served-model-name <name> --host 127.0.0.1 --port P --moe-collect-stats`; Halo stops the process; its first request compiles kernels for minutes (the session waits 30 minutes for that first one; later requests keep the normal wait) | paged-moe |
| `strata` -- [Strata](https://github.com/Niko1221/Strata) (MIT; main at ffa80d73) | one big Mixture-of-Experts model on one machine, natively on Windows, Linux and the Mac: experts in RAM, the rest from the SSD | 8080 | `/health` `"service": "strata"` (asked only for rows with `meta.n_ctx`) | NVIDIA, AMD or Apple Silicon | `strata launch --family F --model S --yes --no-tui --access local --port P --api-key-env ...` after `strata launch --plan` says nothing to download; its own supervisor runs the server; the stop is `strata launch --stop --preset <its launch>` | paged-moe |
| `tensorfold` -- [TensorFold](https://github.com/ashhart/TensorFold) (Apache-2.0; main at 532589e4, release v1.2.1) | a Hugging Face checkpoint held whole in the card's memory, one Zig binary: Metal on Apple Silicon, CUDA on NVIDIA | 8080 | `/v1/models` `owned_by: tensorfold` | Apple Silicon or NVIDIA (CUDA 13, driver R580+) | `tensorfold serve <repo or dir> --name <name> --host 127.0.0.1 --port P --context N [--parallel N] --api-key-file <0600 file>`; Halo stops the process | vram |

The install line per OS -- the owner's to run, never Halo's:

| Engine | Linux | macOS | Windows |
|--------|-------|-------|---------|
| `freetoken` | `uv pip install "freetoken[accel]"` | none | none (WSL2 with Ubuntu: Linux) |
| `strata` | `curl -fsSL https://github.com/Niko1221/Strata/releases/latest/download/install.sh -o install.sh && sh install.sh` | the same | in PowerShell: `irm https://github.com/Niko1221/Strata/releases/latest/download/install.ps1 \| iex` |
| `tensorfold` | the release archive `tensorfold-<version>-linux-<x86_64\|aarch64>.tar.gz` from its releases page (check its `.sha256`), then `huggingface.engine_bins.tensorfold` at its `bin/tensorfold-native` | `brew install ashhart/tensorfold/tensorfold` | built from source (its `docs/WINDOWS.md`), then `huggingface.engine_bins.tensorfold` at `tensorfold-native.exe` |

The models each engine names in its own docs (16 FreeToken checkpoints, 24 Strata sets, 24 TensorFold models, with
the sizes they state) are the Library's download targets (`halo models browse --source hf <id>`) when the search names
the engine or it is set up here (`halo_harness/engines/models.py`).

## Serve one

```
halo local serve --runtime freetoken --model ~/models/Qwen3.6-35B-A3B-NVFP4      # a checkpoint folder
halo local serve --runtime strata --model qwen/IQ3_XXS                           # <family>/<set>
halo local serve --runtime tensorfold --model TensorFold/Qwen3.8-27B-MLX-4bit    # a repo in the Hugging Face cache
halo local servers        halo local log <id>        halo local stop <id>
```

The program is `huggingface.engine_bins.<id>` (a path, or the program and its first arguments) or the engine's own on
PATH; the old `huggingface.<id>_bin` words are still read, and `halo doctor --local` names the new one. Exit 0 serving
(or still loading in the background), 1 not started (no such model, another model runs, an entry of that name Halo
did not write), 2 the program or the model is missing, or the engine's plan says its first start downloads (the GB and
the command said). `--lan` binds every address behind Halo's key (`HALO_SECRET_<ID>_API_KEY` in the env file, never on
a command line or in config.json); 3.3.14.0: once it serves, one request without the key goes to its loopback port, and
only a refusal (401 / 403) is announced as "behind Halo's key" -- an engine that answers it is stopped and started
again on 127.0.0.1, the line and the registry row (`lan_off`) say why. Every managed server (an engine, llama-server,
mlx, the speech servers) gets a tool child's environment: Halo's provider keys left out, its own key added.
`--window` and `--parallel` go to an engine that takes them. The registry row and
the `huggingface.local_servers` entry are named by the engine id and carry `engine: <id>`; an entry Halo wrote before
3.3.13.0 (`freetoken: true`, `strata: true`, `tensorfold: true`) is still Halo's. `halo local bench --host <id>` runs
the speed card through the engine's OpenAI-compatible route, its cost line first.

## The fit

Two rules, the engine's figures in its entry:

- **paged-moe** (FreeToken, Strata): RAM and the disk link, not VRAM. The experts live in host RAM with the engine's
  spare, the dense part on the card. FreeToken: the dense part within 90 % of the card, the experts within 75 % of RAM
  to fit and 90 % to be tight, under WSL2 a pin cap of 40 % of RAM makes it slower. Strata: the experts plus 10 GB to
  fit, plus 6 GB to be tight, and up to twice the RAM it maps them from the model files, slower; its VRAM guide (12 GB
  runs 1 request, 20 GB 2, 24 GB 3, 32 GB and more 4); DeepSeek wants a 12 GB card and 46 GB of RAM.
- **vram** (TensorFold): the checkpoint whole in the card's memory plus the engine's reserve (a 32nd of the card, at
  least 1 GB; on unified memory a tenth of RAM, at least 4 GB); NVFP4 on sm_80-sm_89 cards is slower; a model qualified
  on two machines is out on one.

A Library row's badge, `halo local place` and the adviser read the same line; a speed card from the bench replaces
the table's speed with "measured".

## The steward

The steward reads an engine's log through its descriptor: the first pattern that matches a line makes the event --
`engine-loading`, `load-result`, `timing`, `engine-slots`, `engine-waiting`, `engine-backend-fallback`,
`engine-disk-bound`, `other-error` -- with the descriptor's sentence and the line's numbers. A descriptor with a queue
route (TensorFold) is also read each tick, loopback only: `/health`'s `live` block, else `/metrics` with Halo's key.
One rule turns the events into findings, one per kind, keyed `<server>|<model>`, each with the descriptor's fix line,
never applied by itself ([MODELS-steward-servers.md](MODELS-steward-servers.md)).

## Through the host and in placement

`halo host` lists an engine's server among its servers and offers it in its catalog's `engines` (`{<id>: {url, model,
api_key}}`) when it was started with `--lan`; a paired peer resolves `hf:local/<model>@<host>` (the table's order picks
among a host's engines) or `@<id>` through it. Placement scores each engine server like a host: warm for the model it
serves, else a restart with its loading tax (its size over the disk's speed, the download said), any other model out.

## Adding an engine

One entry in `halo_harness/engines/descriptors.py` -- about ten lines: its id (the `runtime` word), label, url, port,
routes, how it is recognised, its program and `--version` pattern, its install lines, where it runs, its start (or
`None`: detect-only), its log patterns with sentences, its fixes, its fit rule and figures, `verified: False` -- and,
optionally, the models it names in `engines/models.py`. `tests/test_engines_descriptors.py` checks the entry is
complete; sample lines in `tests/helpers/engine_lines.py` pin what its patterns make of its own wording.
