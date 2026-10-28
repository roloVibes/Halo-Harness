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
```

Halo 3.3.5.0: on a real terminal `halo local` opens Studio on its **Local** section (`Alt+0`;
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

### `halo local serve <model> [--runtime llama-server|mlx_lm] [--port N] [--keep]`

Starts a managed `llama-server` (`.gguf`) or `mlx_lm` (a safetensors/MLX
folder, Apple Silicon only) child process on a free loopback port, sized
to this machine's own fitted context, and records it in `~/.halo/run/
local-servers.json`. `<model>` is either an exact path, or a name shown by
a bare `halo local`. Stopped when Halo exits unless `--keep` is given.
When the chosen runtime isn't found (on `PATH`, or already fetched into
`~/.halo/runtimes/`), `llama-server` is offered as a download (named size
and URL, verified against the GitHub Releases API's own per-asset
`digest`) -- nothing downloads without a `y`/`--yes`; declining prints the
one-line install hint for this OS instead. See [MODELS.md](MODELS.md)'s
"Finding and using file-backed models" section for the full story.

Round 5f: `<model>` with `--runtime mlx_lm` also accepts a bare Hugging
Face Hub repo id instead of a path or folder (`halo local serve
mlx-community/Qwen2.5-7B-Instruct-4bit --runtime mlx_lm`) -- the explicit,
non-`--model` form of `hf:mlx/<org>/<repo>` (see [MODELS.md](MODELS.md)'s
"Apple Silicon" section and [MAC.md](MAC.md)); `mlx_lm` itself is never
fetched by `halo local serve` the way `llama-server` is -- it's the
optional `uv tool install "halo-harness[mlx]"` extra instead.

### `halo local stop <model>`

Stops a model `halo local serve` (or the `/local` dialog's `s` key)
started, by the SAME `<model>` name it was started with. Works even in a
brand new `halo` process -- it reads `~/.halo/run/local-servers.json` and
kills by the recorded pid, rather than needing a live handle.

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
  each `/api/create` status and the ref ([MODELS-ollama-tuning.md](MODELS-ollama-tuning.md)).
- `loaded`: what `/api/ps` holds: the model, its share on the GPU, its window, until when.

