# Commands: Ollama, the gym and local models

Read this when you run local models: `halo ollama`, `halo gym`, `halo local`.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo ollama`

```sh
halo ollama
halo ollama --host <name>
halo ollama --refresh
```

Halo 2.0.3 round 3: per-configured-host analysis for `ollama.hosts`
(`docs/CONFIG.md`) -- reachability, version, loaded models (`size` vs
`size_vram` as one plain offload sentence, trained vs. effective
context, the KV-bytes/token figure, this round's `tools_max` and its
rough per-request prompt-token cost), and -- local hosts only -- OS-level
GPU memory. `--host NAME` narrows to one configured entry instead of
every one; `--refresh` bypasses the short in-memory catalog TTL and
re-reads `/api/tags`+`/api/show` now. With no `ollama.hosts` configured
at all, probes the same synthesized default (`OLLAMA_HOST`, else
`127.0.0.1:11434`) a bare `ol:<model>` ref would use. Round 5b adds a
"what fits" column per catalog model (not just loaded ones) -- the
learned calibration cap or "not calibrated," and the one-phrase source
of the num_ctx decision -- plus the last turn's own tokens/second and
prefill seconds when one has happened on that host/model since. See
[MODELS.md](MODELS.md)'s Ollama section; the TUI's own `/ollama` opens an
interactive dialog instead (`docs/SLASH-COMMANDS.md`).

## `halo ollama calibrate`

```sh
halo ollama calibrate <model>
halo ollama calibrate <model> --host <name>
halo ollama calibrate <model> --start <num_ctx>
halo ollama calibrate <model> --no-up
```

Halo 2.0.3 round 5b: loads `<model>` on the chosen host (the default host
when `--host` is omitted) at a candidate `num_ctx` and reads `/api/ps`
back, stepping DOWN by powers of two until it is fully resident in GPU
memory (`size_vram >= size`) or the candidate drops below 4096, whichever
comes first -- this loads the model several times in a row, by design.
`--start` overrides the first candidate tried; left unset, it is the
GPU-based fit estimate when a local or `ollama.hosts[].ssh` read exists,
else 32768. Once a fitting candidate is found, round 5b part 2 keeps
STEPPING UP by powers of two (bounded by the model's own trained context
and the 131072 hard cap) to find the true ceiling rather than settling for
the first lucky guess -- `--no-up` skips that phase and keeps the first
fitting candidate. Prints the host/model being calibrated, the starting
candidate, and the result (the fully-resident `num_ctx` and how many
steps it took, or "does not fit... even at num_ctx=4096"); either outcome
is recorded in `~/.halo/ollama-fit.json` (a "does not fit" result is a
real, remembered fact too, not a failure to retry on the next run). The
SAME procedure also runs automatically the first time a model is used on
a host with no learned cap at all -- `ollama.auto_calibrate: false`
(`docs/CONFIG.md`) opts out of that; this command is always available
regardless, for an explicit re-measurement after a GPU/driver/other-
process change. See [MODELS.md](MODELS.md)'s "Fit calibration" section.

## `halo ollama doctor`

```sh
halo ollama doctor
halo ollama doctor --host <name>
```

Halo 2.0.3 round 5b part 2: the same per-host analysis `halo ollama`
prints, plus the documented host-tuning recommendations Halo cannot read
back from any API (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=
q8_0`, `OLLAMA_NUM_PARALLEL=1` on a single-user box, `OLLAMA_KEEP_ALIVE`,
`OLLAMA_CONTEXT_LENGTH`) and exactly where each one lives per OS of the
HOST -- the OS Halo itself runs on for a local host, all three briefly for
a remote one. A loopback-only host also gets a one-line "reachable from
this machine only" hint naming the per-OS switch that would share it on
the LAN. `halo doctor`'s own Ollama section prints the identical checklist
text, one line per host. See [MODELS.md](MODELS.md)'s "Host setup
checklist" section.

## `halo ollama discover`

```sh
halo ollama discover
halo ollama discover --lan
halo ollama discover --add
halo ollama discover --add pc,gpubox --calibrate
halo ollama discover --lan --json
```

Halo 3.2.3.0: the Ollama servers on this machine -- `OLLAMA_HOST`,
127.0.0.1 and [::1] on `ollama.discover.ports` (default `[11434]`), this
machine's LAN address, `host.docker.internal`, the WSL door -- each
confirmed with `/api/version` and `/api/tags`, about 4 s. One line per
server: its name, address, version, the models it serves, and
`configured` (an `ollama.hosts` entry already) or `new`:

```
pc        http://127.0.0.1:11434       0.12.6    3 models: qwen3:30b, gpt-oss:20b, llama3.2:3b  configured
gpubox    http://192.0.2.20:11434      0.12.6    2 models: qwen3:32b, gemma3:27b  new
```

- `--lan` also sweeps the network: the /24 of this machine's LAN address
  plus `ollama.discover.subnets`, a 10 s cap; it runs only when asked.
- `--add` writes every `new` row as an `ollama.hosts` entry; `--add
  NAME,NAME` writes the named ones. An existing host is never repointed,
  the first entry stays the default, no key is written; the models are
  `ol:<model>@<name>` at once.
- `--calibrate` then measures every model of the hosts just added (and of
  a configured host named in `--add`), one progress line per model --
  `qwen3:32b on gpubox: 32k fits, 65k does not (2 min 10 s)` -- recorded
  in `~/.halo/ollama-fit.json` like `halo ollama calibrate`.
- `--timeout S` is the calibration's per-step budget (its own default
  otherwise).
- `--json` prints `{servers, notes, added, measurements}`; the progress
  lines go to stderr then.

Exit 0 when a server was found, 1 when none was, 2 on a usage error.
`halo ollama` and `halo local` list a local server that is found but not
an `ollama.hosts` entry as "found, not added (halo ollama discover
--add)". See [LOCAL-MODELS.md](LOCAL-MODELS.md)'s "Found on this
machine", "Found on the network" and "Measured after finding", and
[MODELS-ollama.md](MODELS-ollama.md)'s "Discovery".

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
halo local
halo local --refresh
```

Halo 2.0.3 round 5: the shared local-model discovery view, merging THREE
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
