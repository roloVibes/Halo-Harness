# Commands: the gym and local models

Read this when you run local models: `halo gym`, `halo local`.

Part of [Commands](COMMANDS.md), which lists every part. `halo ollama` and its subcommands are in [Commands: Ollama](COMMANDS-ollama.md).

## `halo gym`

```sh
halo gym
halo gym --models ol:qwen3-coder:30b,ol:gpt-oss:20b
halo gym --roles small,judge
halo gym --quick
```

Halo 2.0.3 round 5d: runs the fixed task battery (tool-call accuracy, edit
success, context recall, instruction adherence, tokens/second, prefill
seconds -- see [MODELS.md](MODELS.md)'s "The model gym" section for what
each one means) against each `--models` ref, or every model in the default
Ollama host's own catalog when `--models` is omitted; `hf:local/...` and
`hf:mlx/...` refs run the same battery through their own server (Halo 2.0.3
round 5f follow-up: tokens/second is then a wall-clock estimate and prefill is
not reported); a cloud ref may be named for comparison but is never included
by default. `--roles`
also prints each model's weighted composite for those roles right under
its card (default: `small`, `researcher`, `judge`, `subagent_default`).
`--quick` halves the battery size for a faster, noisier read. Every
model's card is saved to `~/.halo/gym/<host>/<digest>.json` and printed as
it finishes.

## `halo gym show`

```sh
halo gym show
halo gym show qwen3-coder:30b
```

Prints the saved per-model card(s) from `~/.halo/gym/` -- a bare name or
full `ol:` ref both match (tag-aware, same as the Ollama catalog's own
matching); omit it to print every saved card, newest-measured first. Never
runs a fresh probe -- `halo gym` is what measures.

## `halo gym propose`

```sh
halo gym propose
halo gym propose --roles small,judge
halo gym propose --main ol:qwen3-coder:30b
halo gym propose --apply
halo gym propose --apply --name my-local-roles
halo gym propose --candidates cloud
```

Turns saved `halo gym` scores into a role-table proposal -- the best LOCAL
model per supporting role, respecting the round 5b VRAM-aware rule, with
one plain sentence per role naming the composite score behind it (or
saying plainly that no candidate has a usable score for that role yet).
`--candidates local|cloud|all` picks the ranking pool (default `local`,
the original behavior; `cloud` ranks the `or:`/`dbx:`/`xp:`/endpoint
refs the gym can already run against; `all` ranks both together -- the
tokens-per-second term normalizes within the chosen pool, never a cloud
model against a local GPU's ceiling).
`main` is never proposed; `--main REF` only changes which model the VRAM
rule compares candidates against (the configured default model otherwise).
`--apply` saves the proposal as a role template through the existing `halo
roles template import` path (`gym-proposed` by default, `--name` to
change) -- `halo roles template load <name>` (or the picker) is the
separate step that makes it the live table. See [ROLES.md](ROLES.md)'s
"Data-driven roles" section.

## `halo local`

```sh
halo local [page]                  # 3.3.5.0: Studio's Local section (resources, hosts, models, library, ...)
halo local hosts                   # 3.3.5.0: Local -> Hosts as lines
halo local models [--host H]       # 3.3.5.0: Local -> Models as lines
halo local resources               # 3.3.5.0: one sample of this machine now
halo local --terminal [--refresh]  # the merged local-model view below, here
halo local download <repo> [<file>] [--dir D] [--yes]   # 3.3.5.0 R5: a Hugging Face repo into a model folder
halo local ls [--dir D] [--host H] [--window N] [--json] # what is on disk per folder, sizes, the fit word
halo local rm <path> [--force]                           # the uses card, then the files go
halo local serve <path> [--runtime llama-server|mlx] [--window N] [--port P] [--keep]
halo local stop <id|port>  /  halo local servers [--json]  /  halo local log <id> [-n N]
```

Halo 3.3.5.0: on a real terminal `halo local` opens Studio on its **Local** section (`Alt+0`; bare, on its Hugging
Face page since R5;
[STUDIO-local.md](STUDIO-local.md)) through the same door `halo settings` uses: a Studio already running for this home
takes it in its open page, else one starts in the background and the browser opens `?mode=local` (`halo local hosts`
opens the Hosts page; `halo local models` and `halo local resources` print). A page word opens that page: `halo local
hosts` prints, `halo local library` opens Library. `--terminal` (or `--refresh`, or no TTY, or a box where no browser can
open, after the URL) prints the merged view below instead, as `halo local` did before.

- `halo local hosts` prints one block per host Halo knows -- kind, URL, who serves it, the version, what is loaded and
  its VRAM share, who called it in the last 24 hours, the steward's open finding, and whether Load / Unload work from
  here (and through which machine) or why not.
- `halo local models [--host H]` prints one line per installed model per host: the fit meter's level on that host's
  card, the window and its source, the card's chips.
- `halo local resources` takes one sample of this machine now: GPU use, VRAM and what holds it, RAM, CPU and the
  temperature, each with the tool or file it came from (or why there is none).

Halo 2.0.3 round 5: the shared local-model discovery view (`halo local --terminal`), merging THREE
sources into one list, in this order, with a group label per source/host:
each configured Ollama host's own catalog (same analysis `halo ollama`
shows), running Hugging Face local servers (auto-detected on the default
ports plus any configured `huggingface.local_servers` entry), and the
Hugging Face Hub cache (models on disk, from `hf download`, not
necessarily being served by anything right now). Bare `halo local` never
probes a MANUAL Hugging Face local-server entry over the network (shown
as "configured, not probed yet" instead) -- `--refresh` additionally
probes every one of those, and bypasses the Ollama catalog's own short
TTL cache; auto-detected servers are probed either way (background-probe-
gated, same `BRIDGE_TEST_NO_BACKGROUND_NET` seam every other probe in this
codebase honours). Round 5c adds a fourth source to that merged list:
every `.gguf` file/safetensors or MLX folder found under `huggingface.
model_dirs` (`/local add`/`forget` manage that list, below), each row
carrying its format, size, and -- read from the file itself -- trained
context and quantization where the file says so. See
[MODELS.md](MODELS.md)'s Hugging Face section; the TUI's own `/local` (no
arguments) opens the same view as an interactive dialog instead
(`docs/SLASH-COMMANDS.md`). Halo 3.2.3.0: below the list, an Ollama found
on this machine that is not an `ollama.hosts` entry yet shows under
"Ollama (found, not added):" (`halo ollama discover --add` adds it).

### `halo local add <path>` / `halo local forget <path>`

Adds/removes one folder from `huggingface.model_dirs`, persisted to
`~/.halo/config.json` immediately -- the CLI twin of `/local add`/`/local
forget` (`docs/SLASH-COMMANDS.md`). `add` refuses a path that isn't an
existing directory, or one already in the list; `forget` refuses a path
that isn't in the list. Neither touches the network.

### `halo local download <repo> [<file>]` (3.3.5.0 R5)

Downloads a Hugging Face repo, or one file of it, into a `huggingface.model_dirs` folder through the hub cache's own
layout (`models--<org>--<name>/snapshots/<commit>/<file>`; Studio's Local -> Hugging Face lists it after). It prints
the repo's licence line first (`cardData.license`; a gated repo's terms and what it says), then the files and their
sizes and the folder, and asks; nothing moves before the answer. `<file>` is one file, a GGUF quant word (`Q4_K_M`,
`BF16`: its shards together), or nothing: an MLX repo's every file, a GGUF repo's one quant (Q4_K_M first). The
progress is one line; **Ctrl+C** keeps the part file, and the same line resumes it (`Range` from the bytes it has). Each
file is checked against the hub's checksum (an LFS file's sha256, a small file's git blob id) before it lands. A gated
repo needs `HF_TOKEN` (Setup -> Providers -> Hugging Face); the token goes to huggingface.co only. `HF_ENDPOINT` names
another hub (a mirror).

- `--dir D`: a `huggingface.model_dirs` folder (default: the first; `halo local add <path>` adds one).
- `--yes`: accept the licence line without asking (without a terminal, the line to run is printed).

### `halo local ls` (3.3.5.0 R5)

What is on disk in each `huggingface.model_dirs` folder: per model its kind (gguf, mlx, safetensors), its size (a GGUF
quant in shards summed), the fit word at the window on the host's card (`fits`, `tight`, `spill`, `no`, `?`), the repo
and file, and the server Halo started that serves it with its `hf:local/<model>` ref; a download stopped part-way shows
its bytes kept.

- `--dir D`: one folder only. `--host H`: the host whose card rates the fit (default: this machine's).
- `--window N`: the window the fit is rated at (default: that host's `max_ctx`, else 32,768). `--json`: the listing.

### `halo local rm <path>` (3.3.5.0 R5)

Deletes a model `halo local ls` lists: its file (a quant's shards together) or its folder; a hub-cache repo whose
snapshot holds no other model goes whole. It prints the uses card first -- what names `hf:local/<model>` or
`hf:mlx/<repo>`: roles, lineups, the default and compaction models, `huggingface.local_servers`, steward profiles, live
sessions -- and asks. A model a server Halo started serves is kept until `halo local stop` ends it.

- `--force`: delete it without asking, whatever names it.

### `halo local serve <path>`

Halo 3.3.5.0 R5: starts a local server for a model on disk -- `llama-server` for a GGUF file, `mlx_lm.server` for an
MLX folder on a Mac -- on a free loopback port, prints each flag and where it comes from (the window `-c` and the layers
on the GPU `-ngl` from the fit planner on this machine's card, capped by the file's trained context; one slot `-np 1`;
the card's KV cache type as `--cache-type-k/v` with `--flash-attn on`; a steward profile's `num_predict` as `-n`), the
command line, then polls `/health` until it answers and prints the URL and the `hf:local/<model>` ref the catalog lists
it under. Its output goes to `<state>/local/servers/<id>.log`; it is recorded in `<state>/run/local-servers.json`, so
Local -> Hosts shows it and a new `halo` process finds it. It stops when the last Halo process on this home exits,
unless `--keep`. `<path>` is a path `halo local ls` lists, any exact `.gguf` file or model folder, or a name
`halo local --terminal` shows. The binary is `huggingface.llama_server_bin` when set, else `llama-server` on `PATH`,
else one Halo fetched; when none is found, `llama-server` is offered as a download (its size and URL, verified against
the GitHub Releases API's own per-asset `digest`) -- nothing downloads without a `y`/`--yes`; declining prints the
install hint for this OS. See [LOCAL-MODELS.md](LOCAL-MODELS.md)'s "Managed local servers".

- `--runtime llama-server|mlx` (`mlx_lm` still reads as mlx): mlx is Apple Silicon only. Round 5f: with `--runtime mlx`
  the model can be a bare Hugging Face repo id (`halo local serve mlx-community/Qwen2.5-7B-Instruct-4bit --runtime
  mlx`), the explicit form of `hf:mlx/<org>/<repo>` ([MAC.md](MAC.md)); `mlx_lm` is the `uv tool install
  "halo-harness[mlx]"` extra, never fetched.
- `--window N`: the window instead of the planner's (a note says when it is past what stays on the GPU).
- `--port P`: the port (default: a free one). `--keep`: keep it running after Halo exits.
- `--yes`: fetch `llama-server` without asking when none is found. `--backend cuda|vulkan|cpu|metal`: which build to
  fetch (default: CUDA when the driver reports a version, else Vulkan; Metal on macOS). `--json`: the result as JSON.

### `halo local stop <id|port>` / `halo local servers` / `halo local log <id>`

`stop` ends a server Halo started -- by its id (`llama-8123`), its port or its model -- terminate, then kill after 10
seconds, from any `halo` process (it reads the registry, not a live handle). A server Halo did not start is stopped
where it was started (the command says so). A round 5c server (`halo local serve` before 3.3.5.0 R5) still stops by its
model name.

`servers` lists the servers Halo started: id, kind, URL, ready / loading / gone, the `hf:local/<model>` ref, the flags
(`-c -ngl -np`), keep, the model's path and the log's path. `--json`: the registry rows.

`log` prints the last lines of a server's log (`<state>/local/servers/<id>.log`: llama-server's own load lines,
`load_tensors: offloaded N/N layers to GPU`, the KV buffer, each request). `-n N`: how many lines (40).

### `halo local warm [MODELS...] [--host NAME] [--keep-alive DURATION]` (2.0.7)

Pre-loads local Ollama models so the FIRST real call skips the
cold-load: one 1-token `/api/chat` per model, `keep_alive` set so the
weights actually STAY (default `30m`, matching a work session; `-1`
forever, `0` drops them right after). Already-resident models (`/api/ps`)
are reported and skipped, never re-paid. With no model args, warms every
`ol:` ref in the roles table plus the default `model` when it is one --
run it before a long autonomous session (`halo local warm`) so the first
implement->verify transitions don't each pay a minute of load.

`halo teams use` (2.0.7) also warns at ACTIVATION when a lineup's local
lanes measured as unable to co-reside on one GPU (the single-GPU model
swap cost), with the fix named -- measured via `fits_beside_main`,
never a guess.

### `halo local import <model> [--name NAME] [--host NAME] [--yes]`

Copies a `.gguf` file into an Ollama host's own model store (writes a
Modelfile, calls `/api/create`) -- after naming the file's size and that
it's about to be copied, nothing happens without a `y`/`--yes`. The result
is an ordinary `ol:<name>` (default: the file's own name). Only `.gguf`
files are offered this path this round -- see [MODELS.md](MODELS.md).

### `halo local runtime remove [VERSION]`

Deletes a fetched `llama-server` runtime from `~/.halo/runtimes/` -- one
version, or every version when none is named.

### `halo local bench | tune | changes | revert` (3.3.6.0 R5)

- `halo local bench [--host H] [--model M | --all] [--quick] [--yes] [--json]` (also `halo models bench`): the cost line
  first ("local: ~N min on <host>, the card is busy meanwhile, writes the speed card; no tokens leave this machine"),
  then one line per window as it lands, then the speed card ([MODELS-cards.md](MODELS-cards.md#the-speed-card-the-bench-3360-r5)).
  `--all`: every installed model on the host, largest first; `--quick`: the ceiling alone; with no TTY it needs `--yes`.
- `halo local tune [--host H] [--json] [--apply ID [--scope session|until-restart|keep] [--session SID]]`: the tuning
  report, each option with its id, what it writes and how long it takes, a server-side one with the line per OS and
  its revert; `--apply` lands a Halo-side option (keep unless named; `session` ends with the newest live session).
- `halo local changes [--host H] [--all] [--json]`: the changes in force, each with its scope (`--all`: reverted too);
  `halo local revert <id> | --all [--scope S] [--host H]` puts one or all back and says what it put back.

## `halo models browse`

```sh
halo models browse [query...]          # 3.3.5.0 R2: Ollama's library and the Hugging Face Hub, each row with its fit
halo models browse ollama/<model>      # one model's tags (ollama/qwen3.5, or ollama/qwen3.5:9b), each with its fit
halo models browse hf/<org>/<repo>     # one hub repo's files (one row per GGUF quant; an MLX repo's weights)
```

The library browser of Studio's Local -> Library ([STUDIO-local.md](STUDIO-local.md)) in a terminal. Each row is the
fit word on the host (`fits`, `tight`, `spill`, `no`, or `?` when no hardware card is read for it), the name and tag or
file, the size on disk, the model card's chips, and the pull line (`ollama pull qwen3.5:9b`, `ollama pull
hf.co/<repo>:<quant>`, `halo local download <repo>`): nothing is pulled here. The head names where each list came from
(`Ollama: live` or `Ollama: snapshot <date>`, the shipped snapshot; `Hugging Face: live`) and the host and window the
fit is worked out at; the foot counts the rows.

- `--source ollama|hf|all` (default `all`): which library.
- `--host H`: the Ollama host whose hardware card the fit is worked out on (default the first `ollama.hosts` entry).
- `--window N`: the window to fit at (default the host's `max_ctx`, else 32,768).
- `--fits`: only the rows that fit there at that window (fits or tight).
- `--intent code|chat|docs|images|embed`: ranked for that intent, as Local -> Models ranks installed models (`docs` is
  long documents: the largest window that runs on that card first).
- `--family F`, `--quant Q`, `--cap tools|vision|embedding|thinking`, `--max-gb N`, `--license L`: the page's filters.
- `--limit N` (default 40; `0` prints every row), `--why` (each row's fit reason with its numbers: weights + KV cache at
  the window against the card's free memory), `--json` (the route's answer), `--refresh` (read ollama.com and the hub
  again; the cache, `<state>/cache/models-library.json`, keeps the catalog a day and a search an hour).

3.3.6.0 R2, the capability-filtered search ([MODELS-ollama.md](MODELS-ollama.md#finding-a-model-for-a-role-3360)):

- `--preset coder|reasoner|bulk|compactor|verifier|security|multimodal|embeddings|offline`: the preset's filter bundle
  (its needs, fit and supply), printed under the head as `search: Coder -- needs coder expected, tools declared`.
- `--need cap[=verified|declared|expected|any]` (repeatable): a capability at its truth floor (`declared` keeps
  verified or declared; `any` also keeps a model that needs a probe); a bare cap is `expected`.
- `--for-role ROLE`: a lineup role's preset (`verify` -> Verifier, `planner` -> Reasoner, `small` -> Bulk worker).
- `--ask "a local coder that can use tools"`: a sentence read as a preset and its extras.
- `--exclude-crashed`: a model with a crash fingerprint on the host is greyed (`[crashed here]`) and put last.
- Each row's capabilities print with their truth marks (`[tools◇ coder≈ agentic-ready?]`: ✓ verified, ◇ declared,
  ≈ expected, ? needs a probe); `--why` adds the two verdicts (`fits: yes · role-ready: not yet (download and
  verify)`), the cost line and the rank line.
- `--save-template [--model M] [--lineup L]`: write `--preset` as the lineup `local-<preset>` (or that role's entry in
  `--lineup`), through the `halo teams` path; nothing else runs.

## `halo ollama log` (3.3.6.0 R3)

```sh
halo ollama log [--host H] [-n 200] [--kind fit|headroom|truncation|failure|all] [--follow]
```

The newest lines of a host's Ollama server log, read-only: this machine's `server.log` and its rotated files (by
modification time, bytes with invalid UTF-8 replaced), `journalctl -u ollama` on a Linux service, or that machine's
log over its `ssh:` entry. First the host's log status line (live, stale, quiet, unreadable, on that machine, missing;
[MODELS-ollama-logs.md](MODELS-ollama-logs.md)), then `# <where it was read>` and each line marked with its group;
`--kind` keeps one group, `-n` how many (at most 5,000), `--follow` reads again every 2 s until Ctrl+C. Exit 1 when
nothing could be read (the line says why) or for an unknown `--host`. `halo ollama events --host H` turns the same
host's new lines into events (over ssh for a host served elsewhere) and lists only its events.

## `halo ollama crashes`

```sh
halo ollama crashes [--host H] [--why] [--json]
```

3.3.6.0 R3: `--why` prints each fingerprint's evidence with where it came from: the signature, the load it died in
(layers on the GPU, splits, the KV buffers, the load time), the KV type, flash attention and Ollama version in force then
(the log's load block, else the host card), the `num_ctx` the nearest ledger line asked for, the model and where it
came from (the event, the load command, the call, the newest load before it), the load command, the evidence lines,
and for a fingerprint seen twice the fixes, Halo's (a smaller window) and the host's (f16 KV, flash attention off, a
fitted twin, a staged update to start), each with what it costs.

3.3.6.0 R2: every crash fingerprint the steward recorded from the hosts' server events, newest first: the host, the
model and its line ("crashed here on 2026-10-29: CUDA error (an illegal memory access) after a spill at 65,536 with
q8_0 KV, flash attention on"), then its family and quant, where the model came from (the event, or the newest load
before it) and the first evidence line. Read-only (`<state>/ollama/fingerprints.jsonl`,
[MODELS-ollama-steward.md](MODELS-ollama-steward.md#crash-fingerprints-3360-r2)).

## `halo models pull | rm | load | unload | copy | rename | twin | loaded`

```sh
halo models pull <name> [--host H]                        # 3.3.5.0 R3: a library tag or hf.co/<repo>:<quant>
halo models rm <name> [--host H] [--force]                # the uses card first
halo models show <name> --host H [--json]                 # the model card + /api/show's facts
halo models load <name> [--host H] [--num-ctx N] [--keep-alive K]
halo models unload <name> [--host H]
halo models copy <src> <dst> [--host H]
halo models rename <src> <dst> [--host H]
halo models twin <name> --window N [--host H]
halo models loaded [--host H]
```

An Ollama host's models from a terminal: the same calls as Studio's Local tab, whose buttons carry these lines as their
titles ([STUDIO-local.md](STUDIO-local.md)). `--host H` names an `ollama.hosts` entry (the default host without it) and
the call goes to that host's address; `--json` prints the answer as JSON on every one. Never a model call.

- `pull`: one progress line (the status, the percent of the layers' bytes, done of total, the speed, the time left);
  **Ctrl+C** stops it, and Ollama keeps the layers it already has (pulling the same name again starts from them; exit
  130). A name Ollama cannot pull prints its error (exit 1).
- `rm`: prints what uses the model (lineups, `roles`, `model`, `compactionModel`, `ollama.profiles`, live sessions); when
  something does, it asks "delete it anyway?" (without a terminal it prints the `--force` line); `--force` deletes it
  anyway. A live session on the model keeps it (exit 1) until the session ends or moves to another model. A tuned twin's
  record in the tune store goes with it.
- `show <name> --host H`: R0b's card, then `/api/show`'s facts (family, parameters, quantization, format, parent,
  trained context), the capabilities, the `PARAMETER` lines, the licence's first line and the template's length;
  `--json` adds `api_show`. `halo models show <ref>` without `--host` is the card alone, as before.
- `load` / `unload`: the warm generate at the profile's window (`--num-ctx N` for another, `--keep-alive 5m | 1h | -1`)
  and `keep_alive: 0`.
- `copy` / `rename`: a new name for the same layers (`/api/copy`); a rename is the copy, then the old name deleted.
- `twin <name> --window N`: the tuned twin (`FROM <name>`, `num_ctx` N, every layer on the GPU), its plan line, then
  each `/api/create` status and the ref ([MODELS-ollama-tuning.md](MODELS-ollama-tuning.md)); 3.3.6.0: then it is
  verified -- loaded at N, `/api/ps` read (`size_vram == size`), the server log's `offloaded N/N layers` and `graph
  splits` when the log is on this machine, one warm call timed (the first after the load never is) -- and the line
  says it: "verified: 41/41 layers, splits = 2, 258 tok/s at 32,768", "spilled: ..." or "unverified: <why>".
- `loaded`: what `/api/ps` holds: the model, its share on the GPU, its window, until when.


## `halo models probe` (3.3.6.0)

```sh
halo models probe <ref> [--host H] [--force] [--json]    # ol:<name>@<host>, or a bare name with --host
halo models probe --all [--host H] [--force] [--json]    # every chat model on the host
```

The capability battery on a local model, where its GPU is ([MODELS-cards.md](MODELS-cards.md#the-profile-what-the-battery-measured-3360)).
The first line is the cost -- "about 9 requests to <model> on <host> (one 1 px image, one tiny call, for the eyes), 1-3 minutes, no cost; it loads the model" --
then one line per probe (`1/8 warm-up (never timed)`, `2/8 tool call`, `3/8 system role`, `4/8 user instruction`,
`5/8 structured output`, `6/8 reference fidelity`, `7/8 two tools in order`, `8/8 one 1 px image (can it see?)` --
3.3.6.0 R6, not sent to a model /api/show says cannot see), then the profile: tools, system role, instruction, output,
thinking, ids, sees / no eyes, tok/s; agentic-ready and interactive; each quirk; where it sits, use it for, don't use it for, the
limits; and what it changed (a thinking model's reply reserve in `ollama.profiles`). A model whose digest, Ollama
version and probe set match a kept profile answers from it at once ("cached, probed <date>"); `--force` runs it
again. `--json` prints the profile (with every probe's raw answer in `evidence`). Exit 1 when the host or the model is
not there, or the model did not load. Studio's Local -> Models runs the same through its **Probe** button
([STUDIO-local.md](STUDIO-local.md#models)); `halo local bench` measures its speed card.

## `halo models measured | dialect | retire | shelf` (3.3.6.0 R4)

- `halo models measured <model> [--host H] [--json]`: the card's Measured block alone, one fact a line, "value
  (source, date, n)" ([MODELS-cards.md](MODELS-cards.md#measured-what-the-model-did-here-3360-r4)).
- `halo models dialect <model> [--host H] [--set field=value ...] [--reset [FIELD]] [--json]`: how Halo talks to the
  model, each field with its `from`; `--set` writes your edit (`reply_reserve=2048`, `loop_guard=on:40`,
  `json_repair=on:2`, `stop_quirks=<|im_end|>`, `instruction_placement=user-turn`, `thinking=off`, `tools_max=8`),
  `--reset` puts one field or all back to what the battery says.
- `halo models retire <model> [--host H] [--why TEXT] [--force]`: the uses card, then the delete and one shelf line
  with its re-pull line; `halo models shelf [--host H] [--json]` lists every installed model's last use, size and
  whether a role picked it, then the retired ones; `--repull <model>` pulls one back (a fitted twin prints its recipe).

`halo session postmortem [--session ID] [--turn N] [--agent ID] [--json]` (in the TUI `/why [turn]`) rebuilds one
answer from the ledger and the session log -- cut, memory, thinking only, no tools, a small budget, the cache -- in
one line with the details beneath; no session: the newest that called a local model, no turn: its newest
([MODELS-ollama-logs.md](MODELS-ollama-logs.md#the-answer-post-mortems-sources-3360-r4)).

`halo session show <id> [--json]` (3.3.7.0 R2, G15) prints the session's offline promise -- "100 % local -- 0 tokens
left this machine", or how many calls left it and to where -- and a line per local call naming the host it went to;
`/cost` and the Session header's chip say the same ([HOST.md](HOST.md)).
