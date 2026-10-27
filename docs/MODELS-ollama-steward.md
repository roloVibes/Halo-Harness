# Models: the Ollama steward

Read this when you want to know what the Ollama steward knows, records, finds and changes across your halos and model servers.

Part of [Models](MODELS.md), which lists every part.

## The steward (3.3.4.0)

The Ollama steward watches the traffic of every halo to an Ollama server,
knows the card it runs on, and adjusts Halo's side of the calls; it never
writes to a server or changes a model there, and it recommends a server
change with the exact line to set and what it costs. Round R1 ships the
two things the later rounds read:

- **The knowledge**: `halo_harness/ollama_steward/knowledge/*.md`, shipped
  with the package. `scheduler.md` (the server settings and their
  defaults, how a load places layers, eviction, a request during a load,
  the server's own prompt truncation), `log-vocabulary.md` (every
  server.log line Halo acts on, with a real example, and where the log is
  per OS), `memory.md` (weights by quantization, the KV cache by type and
  model shape, the compute buffer, the margins, Windows WDDM and Apple's
  unified memory, worked examples for qwen3-coder:30b, qwen3.8:27b and
  qwen3.5:9b checked against Halo's own fit arithmetic), `local-servers.md`
  (llama-server, mlx_lm.server, LM Studio, vLLM) and `symptoms.md` (each
  alert kind: symptom, cause, the Halo-side change, the server-side line).
  Every claim ends in a `[S<n>]` tag naming a row of `SOURCES.md` (title,
  URL, version or commit, date read); `tests/test_steward_knowledge.py`
  keeps the tags, the rows and the worked examples in step.
- **The hardware card**: `halo ollama hardware [--host NAME] [--json]`
  ([COMMANDS-ollama.md](COMMANDS-ollama.md)) reads each host's GPUs and
  their memory, the server's own settings (its log's startup env dump:
  models kept loaded, parallel slots, keep-alive, KV cache type, flash
  attention, GPU overhead), what is loaded (`/api/ps`) and what else holds
  the card (`nvidia-smi`'s compute processes), every field empty when
  unknown, each reader that found nothing named on a "not read" line.

What the research found that Halo's own fit gets wrong (input for R3):
the Qwen 3.5 / 3.8 models keep a KV cache in one layer of four, so the
estimate is 4 times too large for them; the server's KV cache type is in
its startup log, not only in the host entry's `kv_cache_type` hint; the
compute buffer, the hybrid models' fixed state, the per-device minimum
and llama.cpp's fit margin are not in the estimate; and a 24 GB card on
Windows reports 22.5 GiB, under the server's 23 GiB line for its 32,768
default window.

R2, every call leaves a record:

- **The ledger**: every call to a local model server -- an `ol:` host
  that is not Ollama's own cloud (native, or an entry with `dialect:
  openai`), an `hf:local/*` / `hf:mlx/*` server -- appends one JSON line
  to `~/.halo/ollama/traffic.jsonl`, written where the loop dispatches
  every call (turns, compaction, small-model calls, tool repairs) and by
  each calibration load: `at`, `host` (the entry's name and url),
  `model`, `ref`, `dialect`, `kind` (`turn`, `compaction`, `small`,
  `repair`, `calibrate`), `num_ctx_sent` and `window_source` (the window
  rule's own source, `trim resend` for a re-send at a raised window),
  `estimate_tokens`, `prompt_eval_count`, `eval_count`, `done_reason`,
  `total_ms`, `load_ms`, `prompt_eval_ms`, `eval_ms`, `eval_tok_s`,
  `trimmed` (Ollama read under 70 % of the prompt, or answered "no user
  query"), `status` (200, 400, 499, 500, 503, `timeout`, `connection`),
  `error` (the server's one line), `retry` (0 for a first send, then 1, 2
  for the re-sends that follow a failed or trimmed call in the same
  turn), `session`, `turn`, `tools_count`, `images` and `from` (this
  machine's fleet name while it has joined a hub). The OpenAI dialect
  fills the counts from `usage` and `done_reason` from `finish_reason`.
  The file rotates to `traffic.1.jsonl` at 20 MB; `ollama.ledger: false`
  turns it off. A fleet member sends its lines to the hub
  (`fleet.ollama.share`, [CONFIG.md](CONFIG.md)): by default the calls
  to a host it does not serve itself, so the machine that serves the
  models holds every halo's calls to it. `halo ollama traffic`
  ([COMMANDS-ollama.md](COMMANDS-ollama.md)) prints the rollups.
- **The events**: `halo ollama events` reads the local server's log
  read-only (a rotation followed, journald on Linux) and, with `--watch`,
  polls `/api/version` and `/api/ps` every 20 s; each rule below becomes
  an event `{kind, severity, say, evidence, at, model, data}` in
  `~/.halo/ollama/events.jsonl`. Every event is written; `notify` marks
  the first of a kind in 10 minutes, the only ones a notice shows. What
  each kind means and what to change is in
  `ollama_steward/knowledge/symptoms.md`; the lines themselves in
  `log-vocabulary.md`.

| Kind | Read from |
|------|-----------|
| `prompt-trimmed` | "truncating input prompt limit=L ... keep=K": the window sent is 2L - K (2,050 is 4,096): a bigger window, not only compaction |
| `reply-cut` | "stop processing: ... truncated = 1" |
| `window-full` | "failed to find a memory slot" |
| `no-user-query` | "chat prompt error ... no user query found" (its own 500 is part of it) |
| `cancel-task` | a 500 within 25 lines of "srv stop: cancel task": the client went away while the prompt was read |
| `http-500` | any other `\| 500 \|` request line |
| `retry-loop` | three or more 500s in 3 minutes for one model |
| `client-gave-up` | `\| 499 \|`, with "aborting load" when it ended a load (and the "Load failed ... context canceled" beside it) |
| `load-failed` | "Load failed" for any other reason |
| `cpu-spill` | "offloaded a/b layers" with a under b, "N overflowing", `/api/ps` `size_vram` under `size` |
| `gpu-memory` | "out of memory", "cudaMalloc failed", "CUDA error", "runtime OOM detected" |
| `queue-full` | `\| 503 \|` |
| `slow-load` | "llama-server started in" over 180 s, or a load still running after 3 minutes |
| `stall` | a request with no progress line for 5 minutes (while watching) |
| `server-down` | `/api/version` unanswered three times in a row |
| `other-error` | any other `level=ERROR` line |
| `loaded`, `unloaded`, `reloaded` | `/api/ps` from one poll to the next; `reloaded` is one model at another window |
| `startup` | a new "server config" block: the hardware card is read again |

R3, the steward judges, plans the fit, adjusts:

- **The corrected fit**: the memory estimate counts only the layers that
  hold a KV cache (one in four for Qwen 3.5 / 3.8), times the server's
  parallel slots, plus the hybrid models' recurrent state, the draft
  layer, the compute buffer, the vision projector, Ollama's per-card
  minimum and, for a client that leaves the layers to llama.cpp, its fit
  margin; the KV cache type comes from the host entry's hint, else from
  the server's own startup log (details in
  [MODELS-ollama-tuning.md](MODELS-ollama-tuning.md)).
- **The findings**: `halo ollama steward findings [--host H] [--since 24h]
  [--json]` ([COMMANDS-ollama.md](COMMANDS-ollama.md)) reads the ledger
  (every member's lines on a hub), the events, the hardware card and the
  learned caps per host and model. A window too small (trims, cut replies,
  a p95 prompt within 10 % of it; a 4,096 or 8,192 window asked for is its
  own finding), too large (prompts far under it, with reloads or a spill),
  two windows for one model, replies cut, a session past 80 % of its
  window that never compacted, a cut reply resent, a slow box, two models
  thrashing one card. Each finding says what it saw (the ledger lines'
  `at`, the events, the numbers) and proposes at most one profile change,
  or a server line only to show.
- **The plan**: `halo ollama steward plan` fits what the halos ask for to
  the card: a window per model, one model at a time (`keep_alive` 0 on the
  second), the second model on another configured host, a tuned twin, a
  smaller quantization, the server's KV cache at q8_0; every option says
  what you lose, and only the first three are Halo-side.
- **The profiles**: `ollama.profiles["<host>|<model>"]` ([CONFIG.md](CONFIG.md))
  is read before every call to that model on every halo: its window is the
  one sent (never over the learned cap or `max_ctx`), its `num_predict`
  the least room the reply keeps (the prompt compacts first), then
  `keep_alive`, `tools_max`, `host_for` and `compact_at`. The hub hands its
  profiles to every member in the answer to the member's ledger push, keyed
  by the member's own name for the host, so the Mac's next call uses what
  the PC learned; a member's own `by: "user"` entry is never overwritten.
- **The modes**: `halo ollama steward run [--once]` applies the findings'
  changes per `ollama.steward.apply`: `auto` (applies them and says one
  line; a session's next call to that model shows the note), `review`
  (proposals, then `halo ollama steward apply <id>`), `off`. Every change
  is one line in `~/.halo/ollama/steward.jsonl` (what, why, the evidence,
  the plan); at most one per host and model in ten minutes, never above a
  measured cap, and a change followed by worse calls (more trims, cuts and
  errors in the next 10 calls than in the 10 before) is rolled back on its
  own. `halo ollama steward undo` reverts the newest change.
- **Two session fixes**: a request whose prompt passes `compact_at` of the
  most its window can be compacts before it is sent, and a reply that used
  up the room the window left it counts as cut (compacted and re-sent,
  never kept or sent again).

Next: R4 the steward's agent, R5 the Studio panel and the TUI.
