# Studio: the Setup section

Read this when you set this box up from Studio's Setup section: what each block writes and the routes behind it.

Part of [Halo Studio](STUDIO.md), which lists every part.

## Setup: the wizard's steps, one page at a time (3.3.0.0; pages since 3.3.1.0)

**What it is.** This box's setup, `Alt+8` (`halo studio --mode setup`, `?mode=setup`, `/studio setup`): the
terminal wizard's blocks (`halo init`) as pages, in the wizard's order. Every block writes what the wizard
writes, through the wizard's own writers: settings in `~/.halo/config.json` (the same as `halo config set`),
keys in the env file. The page reads the state again whenever config.json or a lineup moves on disk (a `halo
config set` in a terminal shows at once).

**The rail.** Across the top, the steps as the terminal wizard's step rail names them ([WIZARD.md](WIZARD.md)
rule 4): Providers, Local models, Default model, Permissions, Theme, Team, Linux fixes (a step only while
this box needs them), Check, Summary. The current step is lit, a done step is ticked, a step still to do is
plain; a click opens any step's page. A step is done when its block has what it needs: a provider set;
nothing for Local models; a model picked; a permission mode; a theme; a lineup or `auto`; the fixes
applied; a check run at least once. Under the steps, the rail's one line says what is set now: the
providers set up here ("no provider set" until one is), the default model, the lineup, the permission mode,
the terminal theme and the last check ("ok 12:04", "2 failed 12:04", "not run").

**The pages.** One block per page under a head that says which step it is ("STEP 3 OF 8"), what the block
decides, and, behind "How this page works", how to use it. Each block keeps its own **Save** and its own
line (`saved`, `1 changed` or `problem`, with the lines the server answered under it). **Back** and
**Next** sit at the foot (Next on the page before the Summary says **Summary**); `Ctrl+Left` /
`Ctrl+Right` are Back / Next outside a text field; Enter in a block's field is that block's Save (a card's
form submits itself). Focus lands on the content when a page opens (rule 7). The page open is remembered
for this home (this browser's storage, under a hash of the state dir), so a reload opens it again; a
door's `?block=` wins. There are no panels here: nothing to move, resize or Arrange, the room is the page.

**The Summary**, the last page (rule 10): one row per step with what it holds and a **Change** jump to its
page; then the last check's result with **Run the ticked checks** (the checks ticked on the Check page:
doctor, catalog and hello until changed there) and **The Check page**; then the guided first run's card
(what `halo start` does, the models it calls, the estimate, the time, what it writes) and its Run button.
At its foot (3.3.3.0) the primary **Done: start halo**: it marks this box set up (`POST setup/done`), the
terminal that ran `halo init` starts halo ([WIZARD.md](WIZARD.md)), and the page goes to Session with nothing
opened over it; the rail's "set up this box" line is gone, and stays gone on a reload, which opens Session.

**Nothing opens on its own.** Loading Setup opens no help, no welcome and no Start here overlay, whether
`halo init` opened it or not; the help stays one click away (the `?` in the header, or `?`). 3.3.2.0: no
section opens a welcome any more, and Start here shows only over the section a page opened on, so a page
that opens on Setup gets no offer on the next section either (Setup's Summary offers the guided first run).

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
  first host is the default, and removing the default makes the first one left the default. Under the
  form, behind **Find, scan, add and measure Ollama servers** (a disclosure, closed until opened, 3.3.1.0),
  the card finds servers instead of typing them (3.3.0.0 R5; `halo ollama discover` from a terminal,
  [LOCAL-MODELS.md](LOCAL-MODELS.md) "Found on this machine"):
  - **Find Ollama servers** asks this machine's doors at once, about 4 s: `OLLAMA_HOST`, 127.0.0.1 and
    [::1] on the ports in `ollama.discover.ports` (default `[11434]`; the card names them), this machine's
    LAN address, `host.docker.internal` and the WSL door. Writes nothing.
  - **Scan this network** sweeps the /24 of this machine's LAN address plus `ollama.discover.subnets` as a
    background job (a 10 s cap) with a live line "scanning 192.0.2.0/24 · 3 s" and a **Stop**; it runs
    only when you press it and not in offline mode. Writes nothing.
  - Every server found is a row: its name (reverse DNS, else `ollama-<last octet>`; `-<port>` off the
    default port), its address, its version and the models it serves, then **configured** (already an
    `ollama.hosts` entry, shown under that entry's name) or a tick. **Add the ticked** writes the ticked
    servers as `ollama.hosts` entries `{name, url}`: an existing host is never repointed, the first host
    stays the default, no key is written. The hosts table redraws from the answer, and the Models
    refresh runs, so the Models panel (Roles) lists each new host as `Ollama (<name>)` and its models are
    `ol:<model>@<name>` at once.
  - **Measure the found models** then lists the models of the hosts just added, each ticked: the
    calibration `halo ollama calibrate` runs, one model at a time as a background job (each model is
    loaded at a few windows; about a minute per model), with one log line per model ("qwen3:30b on
    gpubox: 32k fits, 65k does not (2 min 10 s)") and a summary; what settles is recorded in
    `~/.halo/ollama-fit.json`, so the first real turn already knows the window. **Stop** ends it after
    the model in hand. The same as `halo ollama discover --add --calibrate`.
  - The routes (`studio/setup_discover_api.py`, the jobs in `setup_discover_jobs.py`): `POST
    setup/ollama/find` -> `{rows, notes, ports}`; `POST setup/ollama/scan` -> 202 `{job}` (409 while one
    runs), `GET setup/ollama/scan` the latest frame, `POST setup/ollama/scan/stop`; `POST
    setup/ollama/add {names | urls}` -> the fresh state, the lines, `added` and the rows; `POST
    setup/ollama/measure {hosts, models?, timeout?}` -> 202 `{job}` (`models` as `<model>@<host>`;
    `timeout` overrides the calibration's per-step budget), `GET setup/ollama/measure`, `POST
    setup/ollama/measure/stop`. A row is `{url, name, version, models, configured, where}`. Both jobs
    stream `setup` frames on the live feed (`session_id` `setup:scan:<job>` / `setup:measure:<job>`,
    `data.kind` `scan` or `measure`); `GET setup/state` carries `ollama_discover` (the ports, the
    subnets, the latest scan and measure frames). Under `BRIDGE_TEST_NO_BACKGROUND_NET=1` the scan
    answers one note and no rows and Find asks only loopback on `ollama.discover.ports`.
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
its lines as they arrive, the foot says how many failed, and the result is kept as the rail's Last check
(`~/.halo/studio/last-check.json`). The guided first run runs last, through the same job as Start here, and
its seven steps show under its row. **Stop after this check** ends the list before the next one. A ticked
guided first run with no provider set up is refused with the start's own line, and Setup says so.

**Linux fixes** is a step only when this box lacks one of the two fixes the terminal wizard's Linux step
applies: a static `rg` (ripgrep's own release) in `~/.local/bin`, and `~/.local/bin` on PATH for a
non-interactive shell (one line in `~/.zshenv` or `~/.profile`, added once). **Apply** runs them and the
lines say what was written. Otherwise (always on Windows) the block is one line: nothing to fix on this box.

**A fresh home lands here.** While no provider is set up (no key, login or default model: what `halo start`
checks), Studio opens on Setup whatever section was saved (`?mode=` still wins), with no overlay over it;
on another section the Start here overlay's first button is **Set up this box** (Setup opens), and a guided
first run started with no provider opens Setup with a toast instead of an error.

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
  rail's line leads with **set up this box**; nothing else opens (3.3.1.0: no help, no welcome, no Start
  here; 3.3.0.0 opened the help once).
- `?mode=setup&block=<block>` (`halo setup team`, `/setup team`; `roles` is the same block): that block's
  page opens, focused. The blocks: `providers`, `local`, `model`, `permissions`, `theme`, `team`, `linux`,
  `check` (and, in the address, `summary`).

Both words leave the address bar once read, so a reload opens the page plainly, on the page last open (the
token in the fragment stays). A Studio page already open takes the same as a `focus` frame, `{mode: "setup", block, first}`
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
`linux_fixes {needed, items}`, `no_provider` and `model_notes`; 3.3.1.0 adds `home`, a 12-hex hash of the state dir (the key the open page is remembered under).
3.3.3.0 adds `POST setup/done` (`studio/setup_done.py`): `<state>/setup-done.json` `{at, home}` over any earlier
one, a `setup` frame `{stage: "done", at}` (another open tab on Setup with `first` leaves it too), `{ok, done_at}`;
`GET setup/state` gains `done_at` (the marker's time, or null), and a served page is not sent to Setup by "no
provider yet" once it is set. Not agent/loop.py's `.setup_done` (the Setup hook's marker).
