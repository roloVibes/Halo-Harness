# Studio: the Setup section

Read this when you set this box up from Studio's Setup section: what each block writes and the routes behind it.

Part of [Halo Studio](STUDIO.md), which lists every part.

## Setup: the wizard's blocks as forms (3.3.0.0)

**What it is** (3.3.0.0 R1). This box's setup on one page, `Alt+8` (`halo studio --mode setup`,
`?mode=setup`, `/studio setup`): the terminal wizard's blocks (`halo init`) as forms you fill in any order,
each with its own **Save** and its own line (`saved`, `1 changed` or `problem`, with the lines the server
answered under it). The status strip on top says what is set now: the providers set up here, the default
model, the lineup, the permission mode and the terminal theme. The rail lists the blocks with their line;
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
  first host is the default, and removing the default makes the first one left the default. Under the
  form the card finds servers instead of typing them (3.3.0.0 R5; `halo ollama discover` from a terminal,
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

## What each block writes

| Block | Writes | The same as |
|---|---|---|
| Default model | `model` (a ref the catalog of the providers set up here lists) | `halo config set model <ref>` |
| Permissions | `permission_mode` (`auto`, `acceptEdits`, `default` or `plan`) | `halo config set permission_mode <mode>` |
| Terminal theme | `theme` (the six TUI themes, each swatch in its own colours; Studio's own dark / light switch is this browser's) | `/theme <name>` |
| Team | One model for everything: `team` removed, `roles.enabled` false; `auto` with no `team` set: `roles.enabled` true only; a lineup: its `roles.*`, `team: <name>`, `roles.enabled` true | the wizard's Team step (`lineup_choice.py`, which both call) |
| Providers | the env file: `DATABRICKS_HOST`/`DATABRICKS_TOKEN`, `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `TYPESAFE_API_KEY`, `EXPLABS_API_KEY`, `HF_TOKEN`, `HALO_SECRET_*`; config.json: `ollama.hosts`, `huggingface.endpoints`, `huggingface.local_servers`, `providers.<name>.enabled` | `halo init`'s Providers tabs |
| Local models | `huggingface.model_dirs`, `huggingface.preferred_runtime` | `halo init`'s Local models step, `/local add` |
| Linux fixes, Check | (3.3.0.0 R3) | `halo doctor` |

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
