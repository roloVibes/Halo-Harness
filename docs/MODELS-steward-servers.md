# Models: the steward and the local servers

Read this when you run llama-server, LM Studio or mlx_lm.server and want to know what the steward reads in each one's log, what each log can and cannot say, what the steward changes on Halo's side and which server-side line it states.

Part of [Models](MODELS.md), which lists every part. The steward itself: [MODELS-ollama-steward.md](MODELS-ollama-steward.md); Ollama's own log: [MODELS-ollama-logs.md](MODELS-ollama-logs.md).

## Every local server is a source (3.3.8.0 R2)

The steward reads every local server's log the way it reads Ollama's, keeps the same events and the same findings, and
changes the same Halo-side fields. A **server** is one of:

- a `huggingface.local_servers` entry ([CONFIG.md](CONFIG.md)): its `name`, and when set its `log` (the path of the
  log the steward reads) and `runtime` (`llama-server`, `lmstudio` or `mlx`, for a server the probe cannot tell);
- a server Halo started (`halo local serve`): its id (`llama-8080`), its registry row, the log Halo keeps for it
  (`<state>/local/servers/<id>.log`) and the command Halo ran;
- a server the loopback probe found (`auto:<port>`; 1234 is LM Studio).

A manual entry on the port of a server Halo started keeps its name and takes that server's log and command. A ledger
line of an `hf:local/*` or `hf:mlx/*` call is named by its server (`ollama_steward/servers_hf.py`), so the rollups, the
rules, the rollback judge and the host's verify read one name per server. Nothing here starts, restarts or configures
a server; the only writes are Halo's profile fields and Halo's own state.

## Where each server's log is read

| Server | The log | When it cannot be read |
|---|---|---|
| started by Halo | `<state>/local/servers/<id>.log`: the server's stdout and stderr, from Halo's own `--- halo starts:` line | -- |
| LM Studio | the newest file of `~/.lmstudio/server-logs/` (else `~/.cache/lm-studio/server-logs/`), found by path, read-only; a new day's file is read from its top | `missing`: "no LM Studio server log under ...: LM Studio writes one while its server runs" |
| llama-server or mlx_lm.server you started | the entry's `log` (start llama-server with `--log-file <path>`) | `unreadable`: "the server log of <name> is not readable from here: start it with `halo local serve` or set `log`" |
| on another machine | through the `halo host` there (its card lists that machine's servers; the tail is sizes only) | "on that machine": no halo host there reads it |

The status line is the one Ollama hosts have (`ollama_steward/log_status_hf.py`): `live`, `stale` (the ledger has calls
the log never saw), `quiet`, `unreadable`, `missing`. llama-server prints no timestamps, so the file's modification time
stands in for its newest line. The steward's job reads each server's log every 10 seconds
(`ollama_steward/server_log_hf.tail_servers`); a log it never read is read from its top when it is at most 4 MB (its load
block holds the window per slot), else from its end. The read positions are `<state>/ollama/server-log-servers.json`.
A server Halo started whose process is gone while its registry row stays (a `halo local stop` drops the row) is one
death event with the command Halo launched it with.

## What each runtime's log can say

| Kind | llama-server | LM Studio | mlx_lm.server |
|---|---|---|---|
| `prompt-trimmed` | `input truncated, n_ctx = N`, `context shift`, "the request exceeds the available context size" (refused, HTTP 400) | "the model is loaded with context length of only N tokens" | not asked: it keeps no fixed window |
| `reply-cut` | `stopped by limit, n_predict = N` (the server's own `-n`) | `"finish_reason": "length"` | not asked |
| `window-full` | `context shift is disabled` | not asked | not asked |
| `cpu-spill` | `offloaded a/b layers to GPU` with a under b | not asked (its app log, not its server log) | not asked: unified memory |
| `gpu-memory` | `cudaMalloc failed: out of memory`, `CUDA error` | "out of memory" | Metal's "Insufficient Memory" |
| `load-failed` | `failed to load model`, `error loading model` | "Failed to load", "Error loading model" | not asked |
| `slow-load` | the load timed by the read clock, over 180 s | not asked | not asked |
| a crash (death line) | `GGML_ASSERT`, `terminate called`, a segfault, or Halo's server whose process is gone | "The model has crashed" | `libc++abi: terminating`, a Traceback's last line |
| `http-500` | `request: POST ... 500` | -- | `"POST /v1/... HTTP/1.1" 500` |
| `load-result` | `n_ctx = N`, `n_ctx_per_seq`, `n_ctx_slot = N`, `n_slots = N`, the layers: the window per slot | the loaded context length, when a line says it | -- |

A kind a runtime's log never prints is "not asked" (`server_rules_hf.not_asked`): each server finding lists them
(`not_asked`), `halo local events` and the Logs page say them, so a quiet log is never read as "nothing wrong".

## The findings for a server

`rules.gather` takes the servers beside the hosts (`servers=`, the roster by default) and runs the server rules
(`ollama_steward/rules_servers.py`) on each `<server>|<model>` group: the same finding shape (`{id, rule, host, server,
runtime, model, key, severity, finding, evidence, proposal, server_hint, stated, not_asked}`), the same apply modes,
the same ten-minute rule and rollback. The cap of a server's window is the server's window per slot (its `n_ctx_slot`):
a Halo-side window is never above what the server holds.

| Rule | Reads | Halo's side | The server's side (stated) |
|---|---|---|---|
| `window-small` | prompts the server cut, shifted or refused; 400s for the context; a p95 prompt within 10 % of the window per slot | `num_ctx` = the server's window per slot, so compaction keeps the prompt under it | `--ctx-size N` (N for every slot) / LM Studio's Context Length |
| `reply-cut`, `cut-resent` | cut replies (the ledger's `length`, the log's lines) | `num_predict`: the reply's room (the request's `max_tokens`) | `--n-predict -1` when the server's own limit cut it |
| `cpu-spill` | layers left on the CPU | -- | `--n-gpu-layers N` / LM Studio's GPU Offload |
| `tools-heavy` | the tool catalog over a third of prompts that outgrow the window | `tools_max`: the most relevant tools only | -- |
| `crash-repeats` | a fingerprint seen twice on one build | a smaller window | the runtime's lines: a smaller `--ctx-size`, `--cache-type-k/-v` |

The next `hf:local` call reads the profile (`providers/hf_profile.py`): the window Halo works to, the reply's room, the
tool budget. The duty steward, the steward job's pass, the chat (its `servers` tool and its context) and Local -> Steward
see the server findings with their runtime.

## The stated lines per runtime

Every server-side line is a stated action (`ollama_steward/tune_lines_hf.py`): the exact flag or setting, the line that
reverts it, what it costs, `applied: false`. Halo never runs it.

| Change | llama-server | LM Studio | mlx_lm.server |
|---|---|---|---|
| the window | `--ctx-size N` (revert: the `--ctx-size` before) | Context Length: N (then reload the model) | none: no fixed window |
| layers on the GPU | `--n-gpu-layers N` | GPU Offload: max | none |
| the KV cache type | `--cache-type-k q8_0 --cache-type-v q8_0` (revert: f16) | K Cache Quantization Type | none |
| the reply's limit | `--n-predict -1` | none (per request) | `--max-tokens N` |
| flash attention | `--flash-attn on` (revert: auto) | Flash Attention | none |

For a server Halo started the line is the restart through Halo: `halo local stop <id>`, then `halo local serve <the
model> --window N`. More detail from a log is said the same way: llama-server's `--verbose` and `--log-file`, LM
Studio's Verbose Logging, mlx_lm.server's `--log-level DEBUG`.

## After a call, the promise and the push

- After each `hf:local/*` or `hf:mlx/*` call the loop reads the lines of that call in the server's log
  (`agent/server_log_recovery.py`, at most 2 s): the kinds go on the call's ledger line (`log_events`), a crash is
  fingerprinted at once with the command Halo launched it with, and a cut, a spill or the server's own limit is one
  line under the turn.
- A crash fingerprint carries the build it ran on (`digest`: the tag's digest for Ollama, the model file's identity for
  a server Halo started) and the runtime: a repeat is counted on one build, and a crash on a build the tag no longer has
  is stale (judged by the digest, not by its age).
- The offline promise folds every sub-agent's own log and its `agent-<id>` ledger lines.
- A terminal-only session pushes its own ledger lines to the `halo host` that serves its model (`host/session_push.py`
  hands them to the forwarder on a daemon thread), so the host's verify, the busy wait and the promise see that peer.

## What the logs cannot say

LM Studio's server log does not print the layers it placed or a load time; mlx_lm.server prints no window, no cut and
no spill; llama-server prints no timestamps (a read from the top cannot time a load). A server started by hand with no
`log` path is read only through the ledger's lines and the probe. The formats above were written from llama.cpp's
server, LM Studio 0.3.x and mlx_lm.server as they print today; a runtime that changes its words is read as "not asked"
until the rule learns the new line.
