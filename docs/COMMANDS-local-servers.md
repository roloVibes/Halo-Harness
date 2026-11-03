# Commands: a local server's log and events

Read this when you want to read a llama-server, LM Studio or mlx_lm.server log from a terminal, see the events the steward found in it, or know why a server's log is not read.

Part of [Commands](COMMANDS.md), which lists every part.
Exit codes: 0 done, 1 could not (the reason on stderr), 2 usage. What the steward reads in each runtime's log, and what
it cannot: [MODELS-steward-servers.md](MODELS-steward-servers.md).

A `<server>` is any local server the steward reads (3.3.8.0 R2): a `huggingface.local_servers` entry by its `name`, one
the probe found (`auto:<port>`), or one Halo started by its id (`llama-8080`), its port or its model. Both commands are
read-only: nothing is sent to the server and nothing on it changes.

### `halo local log <server> [-n N] [--kind fit|headroom|truncation|failure|all] [--follow]`

The first line names where the log is read, the server, its runtime and its log's state (`live`, `stale`, `quiet`;
llama-server prints no timestamps, so the file's modification time stands in), then the newest lines, each marked with
its group: `fit` (the load: `offloaded N/M layers to GPU`, the KV buffers), `headroom`, `truncation` (`input truncated`,
`context shift`, the context-overflow error, `stopped by limit`), `failure` (CUDA errors, `GGML_ASSERT`, a failed load, a
crashed model, a Traceback, a 500).

- `-n N`: how many lines (40).
- `--kind K`: only one group's lines.
- `--follow`: read again every 2 seconds and print what arrived (Ctrl+C stops).

A server whose log cannot be read prints its status line and why: "the server log of <name> is not readable from here:
start it with `halo local serve` or set `log`" (exit 1). A server on another machine is read through the `halo host`
there, when one is paired.

### `halo local events <server> [--since 24h] [--kind K] [--from-start] [--json]`

Reads the server's log now (from the last read; `--from-start` from its top) and prints its events, newest last: cut and
refused prompts, replies cut by the server's own limit, spills, out of memory, failed loads, crashes, 500s, each load's
window per slot. Then the kinds that runtime's log never prints ("its log never says: prompt-trimmed, cpu-spill ...
(not asked of mlx)").

- `--since`: how far back (`1h`, `24h`, `7d`).
- `--kind K`: one kind (`prompt-trimmed`, `reply-cut`, `cpu-spill`, `gpu-memory`, `load-failed`, `load-result`, ...).
- `--from-start`: read the log from its top; its events are written again.
- `--json`: the events as JSON lines.

`halo ollama crashes` lists a local server's crash fingerprints beside the Ollama hosts' (`llama-8080 [llama-server]
qwen3-8b: crashed here on ...`), `--why` with the command Halo launched it with and that runtime's fixes. `halo doctor
--local` prints one line per local server: its log's state, or a WARN saying how to make it readable.

### `halo local serve --runtime freetoken --model <checkpoint dir> [--port P] [--keep] [--lan] [--json]` (3.3.9.1)

Starts FreeToken's `ft serve` for a Mixture-of-Experts checkpoint folder ([MODELS-freetoken.md](MODELS-freetoken.md)):
the command line first, then the URL and `hf:local/<model>@freetoken`, or "still loading (N of M GiB)" when the load
outlasts two minutes (it goes on; exit 0). It is the server `freetoken` for `halo local servers | log | stop`; the
stop removes the `freetoken` entry Halo wrote. `ft` is `huggingface.freetoken_bin` or the one on PATH. On a machine
that is not Linux x86_64 with driver r580+ and `nvcc`, one line says the three requirements and the install command
for each one missing (exit 2). `--lan` binds every address behind a generated key, for peers through `halo host`.

### `halo local bench --host freetoken [--quick] [--yes] [--json]` and `halo local bench --bw [--model DIR] [--yes]`

The FreeToken server's speed card (the battery's windows and reply reserve, two calls per window), or with `--bw` the
host link measured by `ft bench bw` (about two minutes, the GPU and the CPU busy), the GB/s the FreeToken fit reads in
place of the extrapolated 32-64 GB/s. Both print their cost line first and ask unless `--yes`.

### `halo local serve --runtime strata --model <family>/<set> | --model-path DIR [--port P] [--lan] [--plan] [--json]` (3.3.9.2)

Starts Strata's `strata launch` for a set it names ([MODELS-strata.md](MODELS-strata.md)): `strata launch --plan
--output json` first, and when it says anything is to download (the set's tens to hundreds of GB, the engine, a
drafter) one line with the GB and the `strata launch` command you run yourself (exit 2, nothing started). Otherwise
the command line, then the URL and `hf:local/<model>@strata`, or "still starting" when the launch outlasts three
minutes (it goes on; exit 0). It is the server `strata` for `halo local servers | log | stop`; the stop is `strata
launch --stop` for the launch serving its port, and removes the `strata` entry. The server outlives Halo (Strata's
supervisor runs it). `strata` is `huggingface.strata_bin` or the one on PATH; when it is missing, one line with the
install route for this OS (exit 2). `--lan` is `--access lan` behind Halo's key; `--plan` prints Strata's own plan and
the fit here, and starts nothing.

### `halo local bench --host strata [--quick] [--yes] [--json]` (3.3.9.2)

The Strata server's speed card (FreeToken's: the battery's windows and reply reserve, two calls per window, an untimed
warm-up), with its cost line first; it asks unless `--yes`. The card is kept under the set's name too, so the Strata
fit line says "measured".

### `halo local serve --runtime tensorfold --model <hf repo | checkpoint dir> [--window N] [--parallel N] [--port P] [--keep] [--lan] [--yes] [--json]` (3.3.9.3)

Starts TensorFold's `tensorfold serve` ([MODELS-tensorfold.md](MODELS-tensorfold.md)) for a repo in the Hugging Face
cache (by its id), a repo Halo's download put in a model folder, or a checkpoint folder: the fit here, the command line
(`--name <model> --host 127.0.0.1 --port P --context N --api-key-file <0600 file>`, `--parallel N` when given), then
the URL and `hf:local/<model>@tensorfold`, or "still loading" when the load outlasts two minutes (it goes on; exit 0).
A repo nowhere on disk starts nothing: one line with its size from TensorFold's table, `tensorfold pull <repo>` (yours
to run) or `halo local download <repo>` (exit 2). No binary: one line with this OS's route -- `brew install
ashhart/tensorfold/tensorfold` on the Mac, the native build guide on Windows, and on Linux x86_64 / aarch64 the
release archive Halo fetches (its size, URL and destination said first; `--yes` answers yes; the `.sha256` checked;
`~/.halo/runtimes/tensorfold-<tag>/`, never on PATH, `halo local runtime remove tensorfold-<tag>` takes it out). It is
the server `tensorfold` for `halo local servers | log | stop`; the stop removes the entry and the key file. `--lan`
binds every address behind the same key, for peers through `halo host`.
