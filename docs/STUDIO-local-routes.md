# Studio: the Local section's routes

Read this when you call Studio's Local routes yourself or want the live frames the Local section listens to.

Part of [Halo Studio](STUDIO.md), which lists every part. The pages they serve are in
[STUDIO-local.md](STUDIO-local.md).

## The routes

Studio's API under `/api/local/` (`halo_harness/studio/local_api.py`), the same loopback / origin / token guard as every
Studio route; never a model call:

| Route | What it answers |
|---|---|
| `GET local/hosts` | every host as a card (`studio/local_hosts_view.py`) |
| `POST local/host/<name>/load {model, num_ctx?, keep_alive?}` | a load from here or through the member; 409 with the reason when neither can |
| `POST local/host/<name>/unload {model}` | the same with `keep_alive: 0` |
| `POST local/host/add {url, name}` | the entry written through Setup's Ollama writer |
| `GET local/resources?host=` | the last five minutes of samples and the sampler's state |
| `POST local/resources/watch {on}` | the page's lease on the sampler |
| `GET local/traffic?host=&since=15m` | the ledger's rows, the server events, the per-host minute buckets |
| `POST local/traffic {lines, events}` | another process's ledger tap: `traffic` frames on the live feed |
| `GET local/models?host=` | every model per host with its card, its meter and its intent scores |
| `GET local/library?source=ollama\|hf\|all&q=&host=&window=&fits=1&intent=&family=&quant=&cap=&max_gb=&license=&page=` | the library's rows with their card, fit badge and intent scores, the total, and where each source came from (`studio/models_library_api.py`) |
| `GET local/library/<source>/<id>?host=&window=` | one Ollama model's tags or one hub repo's files, each with its badge |
| `POST local/library/refresh` | the library's cache dropped: the next read is live |
| `GET local/library?...&preset=&for_role=&ask=&need=tools=declared,coder&exclude_crashed=1&edited=1&<fit and supply filters>` | 3.3.6.0 R2: the search (`studio/local_search_api.spec_of`): the rows ranked with their facts, cost and verdicts, and `search`, `presets`, `strip` |
| `GET local/library/presets` | the nine presets, each bundle expanded |
| `POST local/library/template {preset, model?, lineup?, bundle?}` | Save as role template: `local-<preset>`, or the role entry of the lineup named |
| `POST local/library/verify {host, name, role?}`, `GET local/library/verifies` | Download and verify (`studio/local_verify_job.py`); its jobs |
| `POST local/library/assign {role, ref, lineup?}` | the role offer accepted: the lineup's role gets the model |
| `GET local/crashes?host=` | the crash fingerprints (`ollama_steward/fingerprints.py`) |
| `GET local/host/<name>/log?n=200&kind=all\|fit\|headroom\|truncation\|failure` | 3.3.6.0 R3: the bounded tail, each line's group and time, its source, `cli` and `tail_cli` |
| `GET local/host/<name>/log/status`, `GET local/host/<name>/log/models` | the log status (`ollama_steward/log_status.py`); per model the last load, this session's cuts, the errors, the crash |
| `POST local/host/<name>/pull {name}` | a pull job (a second ask joins it); its view and `cli` |
| `POST local/pull/<id>/cancel` | stop it (Ollama keeps the layers it has) |
| `GET local/pulls` | every pull running and the last ended ones |
| `POST local/host/<name>/delete {name, force?}` | 422 with the uses card when something uses it (`force`: delete anyway); 409 while a live session is on it |
| `GET local/host/<name>/uses?model=` | the uses card alone (`studio/local_uses.py`) |
| `GET local/host/<name>/show?model=` | `/api/show`'s facts |
| `POST local/host/<name>/copy {src, dst}`, `.../rename {src, dst}` | a copy; a copy then the delete of the old name |
| `POST local/host/<name>/twin {name, window?, dry?}` | the tuned twin (`dry`: the plan, its name and cost); recorded in the tune store |
| `GET local/host/<name>/loaded` | `/api/ps` (a member's host: its newest resources sample) |
| `POST local/host/<name>/probe {model, force?}` | 3.3.6.0: a probe job (the battery; a second ask joins it), its view, `cost` and `cli`; a member's host: that member's own job |
| `GET local/probes`, `GET local/profiles?host=` | the probe jobs running and the last ended ones; every kept profile (that host's only with `?host=`), without the raw evidence |
| `GET local/hf/dirs?host=&window=` | each model folder and what is on disk in it, with the card, the fit and who serves it (`studio/local_hf_view.py`) |
| `POST local/hf/dirs {path}`, `POST local/hf/forget {path}` | a folder added to or taken off `huggingface.model_dirs` |
| `POST local/hf/download {repo, file?, dir?, accept}` | 422 with the licence line (`needs_accept`) until `accept`; a gated repo without `HF_TOKEN` 422 `needs_token`; then a download job |
| `POST local/download/<id>/cancel`, `GET local/downloads` | stop one (the part file stays); the download jobs |
| `GET local/hf/uses?path=`, `POST local/hf/delete {path, force?}` | the uses card; the delete (409 while a server Halo started serves it, 422 with the card unless `force`) |
| `POST local/hf/serve {path, runtime?, window?, port?, keep?, dry?}` | `dry`: the flags and their sources; else the server started (`studio/local_server_api.py`) |
| `GET local/servers`, `POST local/server/<id>/stop`, `GET local/server/<id>/log?n=`, `GET local/server/<id>/status` | the servers Halo started; stop one; its log's tail; `/health` and `/slots` |

Every R3 answer carries `cli`, the `halo models` line that does the same (`studio/local_control_api.py`). A host a
fleet member serves goes through that member (`ollama_pull`, `ollama_delete`, `ollama_copy`, `ollama_twin`, 3.3.6.0 `ollama_probe`, under its
`fleet.allow_control`); `none` answers 403 with the reason.

Live frames: `resources` (one sample), `traffic` (`{rows}`), `pull` (a job's view: host, name, status, digest,
total, completed, percent, speed, eta, done, error) and `download` (the same view with kind, repo, file, dir and path), `probe` (3.3.6.0: a probe job's view: host,
model, step, of, probe, say, done, ok, error, cost), `twin-verify` (a new twin's verify line) and `verify` (3.3.6.0 R2:
Download and verify's stage: pull, probe, offer, done), beside the steward's own `steward` frames. From a terminal,
`halo local hosts`, `halo local models [--host H]` and `halo local resources` print what the first three pages show, and
`halo models browse` what the Library shows, `halo local ls` what the Hugging Face page shows
([COMMANDS-local.md](COMMANDS-local.md)).

## The measured card, the dialect record and the shelf (3.3.6.0 R4)

| Route | What it answers |
|---|---|
| `GET local/host/<name>/measured?model=` | the measured facts (`providers/measured.py`) and their lines, `cli` |
| `GET local/host/<name>/dialect?model=` | the dialect record, each field's value and `from`, `cli` (`studio/local_card_api.py`) |
| `POST local/host/<name>/dialect {model, set?: {field: value}, reset?: FIELD \| ""}` | your edit (marked `user`) or a reset; 422 with the problem when a value does not fit its field |
| `GET local/host/<name>/shelf` | per installed model: last used, size, picked by a role, never used, the hint (`studio/local_shelf_api.py`) |
| `POST local/host/<name>/retire {name, why?, force?}` | the delete's uses card first (409 while a live session is on it, 422 with the card unless `force`), then the delete and a shelf line; a member's host 409 |
| `GET local/shelf?host=`, `POST local/shelf/repull {host, model}` | the retired models; the pull job that brings one back (a fitted twin: 409 with its recipe) |

