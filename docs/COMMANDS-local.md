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
The first line is the cost -- "about 8 requests to <model> on <host>, 1-3 minutes, no cost; it loads the model" --
then one line per probe (`1/6 warm-up (never timed)`, `2/6 tool call`, `3/6 system role`, `4/6 user instruction`,
`5/6 structured output`, `6/6 reference fidelity`), then the profile: tools, system role, instruction, output,
thinking, ids, tok/s; agentic-ready and interactive; each quirk; where it sits, use it for, don't use it for, the
limits; and what it changed (a thinking model's reply reserve in `ollama.profiles`). A model whose digest, Ollama
version and probe set match a kept profile answers from it at once ("cached, probed <date>"); `--force` runs it
again. `--json` prints the profile (with every probe's raw answer in `evidence`). Exit 1 when the host or the model is
not there, or the model did not load. Studio's Local -> Models runs the same through its **Probe** button
([STUDIO-local.md](STUDIO-local.md#models)). `halo local bench` (the three-window battery and the tuning scans) is not
part of 3.3.6.0.
