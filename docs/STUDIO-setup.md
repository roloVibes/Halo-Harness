# Studio: the Setup section

Read this when you set this box up from Studio's Setup section: what each block writes and the routes behind it.

Part of [Halo Studio](STUDIO.md), which lists every part.

## Setup: the wizard's blocks as forms (3.3.0.0)

**What it is** (3.3.0.0 R1). This box's setup on one page, `Alt+8` (`halo studio --mode setup`,
`?mode=setup`, `/studio setup`): the terminal wizard's blocks (`halo init`) as forms you fill in any order,
each with its own **Save** and its own line (`saved`, `1 changed` or `problem`, with the lines the server
answered under it). The status strip on top says what is set now: the providers set up here ("no provider
set" until one is), the default model, the lineup, the permission mode, the terminal theme and the last
check ("ok 12:04", "2 failed 12:04", "not run"). The rail lists the blocks with their line;
a click brings the block's panel back and focuses it. Every block writes what the wizard writes, through
the wizard's own writers: settings in `~/.halo/config.json` (the same as `halo config set`), keys in the
env file. The page reads the state again whenever config.json or a lineup moves on disk (a `halo config
set` in a terminal shows at once).

## Providers and Local models (3.3.0.0 R2)

**Providers** is one card per provider, in the wizard's order (Databricks, OpenRouter, Anthropic,
Ollama, Hugging Face, OpenAI, TypeSafe, Experiential Labs). Each card says whether it is set and where the
key comes from ("set, from the env file, ****1234", "set, from the environment", "not set"), whether the
provider is enabled, and what the last test found ("reachable: ok · 312 models listed"; "not checked"
until a Save & test ran in this Studio). A key field is a password field, never prefilled ("paste a
key"). **Save & test** does what the wizard's Save does: it writes the variables to the env file
(`init_cli._write_env_var`), turns an explicitly disabled provider back on
(`enable_if_was_explicitly_disabled`), probes the host (`reachability_tag`, connect only) and reads the
model list (`refresh_tab_catalog`); the lines under the card say what was written and what the test found.
A Databricks host must be an `https://` URL (anything else is a problem line with an example and nothing is
written); a token-only save keeps the host already set.

- **Ollama**: the hosts in `ollama.hosts` as a table (name, url, default, the env variable its key is kept
  under), add a host by name and URL (a bare `host:port` reads as `http://`), remove one. The wizard's merge
  rule holds: a save with a name already there updates its URL and keeps its tuning (`max_ctx`,
  `keep_alive`, ...), a blank save never repoints a host (with no host it registers the local daemon), the
  first host is the default, and removing the default makes the first one left the default. Finding Ollama
  servers on this machine and scanning the network come with 3.3.0.0 R5 (two buttons say so; `halo ollama
  discover` does it from a terminal).
- **Hugging Face**: the router token (`HF_TOKEN`), dedicated endpoints (`huggingface.endpoints`) and local
  servers (`huggingface.local_servers`, each with a name; no name is the wizard's `default` entry), each
  added or removed on its own.

**Local models**: the model folders (`huggingface.model_dirs`: type a path and Add folder, Remove; the same
as `/local add` / `/local forget`), the runtime `halo local serve` prefers (`huggingface.preferred_runtime`:
`llama-server` or `mlx_lm`), and what is on this machine now (the wizard's detection lines plus how many
models the folders hold), read again after every save.

**The key rule.** A key travels from the browser to Studio once, in the body of one request over
loopback with Studio's token; Studio writes it to the env file and never sends it back: no answer, line or
state carries it, only `set`, its source and its last four characters. config.json never holds a key: a
key for an Ollama host, an endpoint or a local server goes to the env file as `HALO_SECRET_<KIND>_<NAME>`
and config.json keeps that name. Removing a host, an endpoint or a server leaves its variable in the env
file (the answer names it). The env file is `HALO_ENV_FILE`, else `~/.config/halo/env`; the Providers
block names its path.

## Check and Linux fixes (3.3.0.0 R3)

**Check** is the five checks Halo offers after setup (the same list as [`halo check`](COMMANDS-init.md#halo-check-halo-3220)),
one row each with what it does, what it costs, how long it takes and what it writes:

| Row | What it does | Cost | Time | Writes |
|---|---|---|---|---|
| Doctor | your config, your files and that halo is on PATH (`halo doctor`) | free | seconds | nothing |
| Model catalog | every set-up provider's model list (`halo models --refresh`) | free (network) | seconds | the catalog caches |
| Hello | one one-turn call to the default model, which answers pong | one tiny call, priced from the catalog | seconds | one session log |
| Model gym, quick | `halo gym --quick` on the models listed under the row (local models only) | free for local models | minutes per model | a card per model under `~/.halo/gym/` |
| The guided first run | `halo start`: one real Orchestra run on your models | the card's estimate | 5-20 minutes | a lineup copy and a sample repo |

Doctor, Model catalog and Hello are ticked; ticking the gym lists the models it would run on (the default
model and the start lineup's models; untick any). The guided first run's row shows **Show the card** first
(the card `halo start` opens on: the models, the estimate, what it writes); its box can be ticked only
then, and **Run the guided first run** under the card starts it at once. **Run the ticked checks** runs the
ticked rows in that order as one background job; each row shows its state (`>>` running, `ok`, `!!`) and
its lines as they arrive, the foot says how many failed, and the result is kept as the strip's Last check
(`~/.halo/studio/last-check.json`). The guided first run runs last, through the same job as Start here, and
its seven steps show under its row. **Stop after this check** ends the list before the next one. A ticked
guided first run with no provider set up is refused with the start's own line, and Setup says so.

**Linux fixes** shows only when this box lacks one of the two fixes the terminal wizard's Linux step
applies: a static `rg` (ripgrep's own release) in `~/.local/bin`, and `~/.local/bin` on PATH for a
non-interactive shell (one line in `~/.zshenv` or `~/.profile`, added once). **Apply** runs them and the
lines say what was written. Otherwise (always on Windows) the block is one line: nothing to fix on this box.

**A fresh home lands here.** While no provider is set up (no key, login or default model: what `halo start`
checks), Studio opens on Setup whatever section was saved (`?mode=` still wins), the Start here overlay's
first button is **Set up this box**, and a guided first run started with no provider opens Setup with a
toast instead of an error.

**Reading this page opens no connection.** The Default model rows, the check costs and the card come from
the cached catalog: an Ollama host is listed with the models its last read found (Refresh, `halo models
--refresh`, `/local refresh`), and a host nothing has read yet says "not read yet: Refresh". The block's
**Refresh** reads every provider's list again (`POST models/refresh`). The Local models block's detection
lines are the one live read (kept a minute).

## The doors: `halo init` opens Setup (3.3.0.0 R4)

Setup is where a box gets set up: `halo init` on a terminal starts Studio (or reuses the one running for this
home) and opens this page; the terminal wizard is the fallback (`halo init --terminal`, SSH, no browser:
[WIZARD.md](WIZARD.md)). Two words in the page's address say how it was opened (`studio/setup_door.py`, read by
`ui/src/routes/setup/door.ts`):

- `?mode=setup&first=1` (`halo init`, and Enter on `halo start`'s "Open Setup in Studio? [Y/n]"): the
  section's help opens once, titled **What this page does**, the status strip leads with **set up this
  box**, and Start here's offer waits (a guided first run already running still shows). `tour=off` keeps the
  help shut (captures, tests).
- `?mode=setup&block=<block>` (`halo setup team`, `/setup team`; `roles` is the same block): that block's
  panel is brought back if it was collapsed, scrolled into view and focused. The blocks: `providers`,
  `local`, `model`, `permissions`, `theme`, `team`, `linux`, `check`.

Both words leave the address bar once read, so a reload opens the page plainly (the token in the fragment
stays). A Studio page already open takes the same as a `focus` frame, `{mode: "setup", block, first}`
(`POST /api/focus {mode: "setup", block?, first?}`); `halo studio --edit setup`, `setup:first` and
`setup:<block>` open them from a shell. A door that finds no browser here (`HALO_NO_BROWSER`,
`SSH_CONNECTION`, Linux with no `DISPLAY` / `WAYLAND_DISPLAY`, or a browser that does not take the URL)
prints the URL with `halo studio`'s port-forward line and runs the terminal screen instead.

## What each block writes

| Block | Writes | The same as |
|---|---|---|
| Default model | `model` (a ref the catalog of the providers set up here lists) | `halo config set model <ref>` |
| Permissions | `permission_mode` (`auto`, `acceptEdits`, `default` or `plan`) | `halo config set permission_mode <mode>` |
| Terminal theme | `theme` (the six TUI themes, each swatch in its own colours; Studio's own dark / light switch is this browser's) | `/theme <name>` |
| Team | One model for everything: `team` removed, `roles.enabled` false; `auto` with no `team` set: `roles.enabled` true only; a lineup: its `roles.*`, `team: <name>`, `roles.enabled` true | the wizard's Team step (`lineup_choice.py`, which both call) |
| Providers | the env file: `DATABRICKS_HOST`/`DATABRICKS_TOKEN`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `TYPESAFE_API_KEY`, `EXPLABS_API_KEY`, `HF_TOKEN`, `HALO_SECRET_*`; config.json: `ollama.hosts`, `huggingface.endpoints`, `huggingface.local_servers`, `providers.<name>.enabled` | `halo init`'s Providers tabs |
| Local models | `huggingface.model_dirs`, `huggingface.preferred_runtime` | `halo init`'s Local models step, `/local add` |
| Linux fixes | `~/.local/bin/rg`; the PATH line in `~/.zshenv` or `~/.profile` (only the fixes listed) | the wizard's Linux step |
| Check | `~/.halo/studio/last-check.json`; each check writes what its row says | `halo check` |

## The routes

`GET setup/state` (every block's value and rows; a provider is `set` with its source and last four
characters, no key is ever in it), `POST setup/config {key, value}` (only `model`, `permission_mode` and `theme`; a value the
block does not list is a 422 with `problems` and nothing is written), `POST setup/team {lineup}` (a lineup
name, `one-model` or `auto`) and `GET setup/team/<name>/preview` (the Team step's preview lines); each
write answers the fresh state and the lines it wrote (`studio/setup_api.py`, `studio/setup_state.py`).
R2 adds `POST setup/provider/<name> {fields}`, `POST setup/ollama-host {name, url, api_key}`, `POST
setup/ollama-host/remove {name}`, `POST setup/hf` (`{token}`, `{endpoint: {name, url, token}}`,
`{local_server: {name, url, api_key}}`, `{remove_endpoint}`, `{remove_local_server}`), `POST
setup/model-dir {path, remove}` and `POST setup/runtime {runtime}` (`studio/setup_providers_api.py`,
`studio/setup_providers_state.py`); a bad URL or host is a 422 with `problems` and nothing written.
R3 adds `POST setup/check {checks: [keys], models?: [refs]}` (202 with the job; 409 while one runs; 422 for an
unknown key, or `reason: "no_provider"` when the guided first run is ticked with no provider set up), `GET
setup/check` (the job: the last frame per check and the summary, so a reloaded page catches up), `POST
setup/check/stop` and `POST setup/linux-fixes` (`studio/setup_check_api.py`, `setup_check_job.py`,
`setup_check_state.py`). Each check's frames are `setup` frames on `/api/events` (`session_id`
`setup:<job>`, `data: {job, key, title, state: running | done | failed, lines}`, then `{key: "summary",
state: "finished", ok, results}`). `GET setup/state` gains `checks`, `gym_models`, `card`, `last_check`,
`linux_fixes {needed, items}`, `no_provider` and `model_notes`.
