# Commands: Ollama

Read this when you run or watch an Ollama server: `halo ollama` and its subcommands (calibrate, doctor, tune, discover, hardware, traffic, events).

Part of [Commands](COMMANDS.md), which lists every part. `halo gym` and `halo local` are in [Commands: the gym and local models](COMMANDS-local.md).

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
interactive dialog instead (`docs/SLASH-COMMANDS.md`). Halo 3.2.3.0: a
tuned twin (`halo ollama tune`) is listed right under its original with
"tuned twin of <model> (65k window, all layers on the GPU)".

## `halo ollama calibrate`

```sh
halo ollama calibrate <model>
halo ollama calibrate <model> --host <name>
halo ollama calibrate <model> --start <num_ctx>
halo ollama calibrate <model> --no-up
halo ollama calibrate <model> --timeout <seconds>
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

Halo 3.2.3.0: a load counts only when it finished within its budget and
`/api/ps` lists the model at that window; otherwise the step is retried
once with twice the budget, then the run is inconclusive and records
nothing (exit 1). The budget per load is printed first (20 s + 4 s per GB
of the model locally, 40 s + 6 s per GB over the network, 60 s for an
unknown size); `--timeout <seconds>` sets it. Each load prints one line
(safe / tight / offloaded / unknown) and the run ends with one line:
"qwen3-coder:30b on pc: 65k safe, 98k tight (22.1 of 23 GB), 131k does
not fit (6 min 10 s)", or "...: inconclusive (...), the window stays at
32k (trained)". `halo ollama` shows per model the window in use, its
source word (`trained` / `memory` / `calibrated` / `max_ctx` / `prompt
floor`), the last session's prompt floor, `calibrated` / `estimated` /
`inconclusive`, the tight window when one was measured, and the prompt
reading speed.

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

## `halo ollama tune`

```sh
halo ollama tune <model>
halo ollama tune <model> --host <name>
halo ollama tune <model> --window <num_ctx>
halo ollama tune <twin> --remove
halo ollama tune <model> --json
```

Halo 3.2.3.0: makes a tuned twin of `<model>` on the host (the default
host when `--host` is omitted) -- a derived model through Ollama's
`/api/create` whose defaults keep every layer on the GPU at the window
calibration measured as safe. The twin's name is the model's name with
`-halo` added, the tag kept: `qwen3.8:27b` becomes `qwen3.8-halo:27b`
(an untagged `qwen3` becomes `qwen3-halo:latest`). Its Modelfile is
three lines, and it shares the original's weights (no extra disk):

```
FROM qwen3.8:27b
PARAMETER num_ctx 65536
PARAMETER num_gpu 65
```

`num_ctx` is the safe window `halo ollama calibrate` (or the first-use
calibration, or `halo ollama discover --calibrate`) recorded for that
model on that host, or `--window N`; it is held at the model's trained
context. `num_gpu` is the layer count from `/api/show`
(`<family>.block_count` + 1; 999 when unknown, which Ollama caps at the
real count). The command prints the plan line, one line per status
Ollama streams back, the confirmation (`/api/show` on the twin reads both
parameters back), and last the twin's ref:

```
plan: qwen3.8-halo:27b on 'pc': FROM qwen3.8:27b, num_ctx 65,536 (the safe window calibrated on 'pc'), num_gpu 65 (every layer on the GPU); it shares qwen3.8:27b's weights, no extra disk
  using existing layer sha256:...
  writing manifest
  success
made qwen3.8-halo:27b: /api/show reads num_ctx 65536, num_gpu 65
ol:qwen3.8-halo:27b@pc
```

The twin starts calibrated (it carries the window its original measured),
`halo ollama` and `halo local` list it under its original, and the
`/model` picker and Studio's Models rows show it first for that host. Run
the command again after a new calibration to remake the twin at the new
window. `--remove` deletes a twin from the host; a name that is not a
twin is left alone, in one line: "not a twin: qwen3.8:27b is an
original; halo ollama tune makes twins and removes only them". `--json`
prints `{ok, plan, progress, message, ref}` (`{removed, twin, message}`
with `--remove`). Exit 0 done, 1 when the host or the model is missing,
no safe window is recorded (`halo ollama calibrate` first, or
`--window`), Ollama answered with an error, or the name is not a twin; 2 on a usage
error. See [MODELS-ollama-tuning.md](MODELS-ollama-tuning.md)'s "A tuned
twin".

## `halo ollama discover`

```sh
halo ollama discover
halo ollama discover --lan
halo ollama discover --add
halo ollama discover --add pc,gpubox --calibrate
halo ollama discover --add --calibrate --twins
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
- After `--calibrate`, the question "make tuned twins of the models that
  fit? (Enter / n)": Enter makes a tuned twin (`halo ollama tune`) of every
  model that measured a safe window, one line each -- `qwen3:32b on
  gpubox: tuned twin qwen3-halo:32b made (65k window, all layers on the
  GPU) [ol:qwen3-halo:32b@gpubox]`. `--twins` makes them without asking;
  `--no-twins` skips the question (so do `--json` and a stdin that is not
  a terminal, unless `--twins` is given).
- `--json` prints `{servers, notes, added, measurements, twins}`; the
  progress lines go to stderr then.

Exit 0 when a server was found, 1 when none was, 2 on a usage error.
`halo ollama` and `halo local` list a local server that is found but not
an `ollama.hosts` entry as "found, not added (halo ollama discover
--add)". See [LOCAL-MODELS.md](LOCAL-MODELS.md)'s "Found on this
machine", "Found on the network" and "Measured after finding", and
[MODELS-ollama.md](MODELS-ollama.md)'s "Discovery".

## `halo ollama hardware`

```sh
halo ollama hardware
halo ollama hardware --host <name>
halo ollama hardware --json
```

Halo 3.3.4.0 R1: each configured host's hardware card, read without
touching the server's settings or its models. In this order, each one
optional: the newest startup block of the local server log
(`%LOCALAPPDATA%\Ollama\server.log`, `~/.ollama/logs/server.log`, else
`journalctl -u ollama` on Linux: the env dump and the "inference compute"
lines), `/api/version` and `/api/ps`, the ssh GPU read of a remote host
with `ssh:`, and `nvidia-smi` (cards and compute processes) or
`system_profiler` + `sysctl` on a Mac where local. A sample:

```text
GPU 0: NVIDIA GeForce RTX 4090 [CUDA] 22.5 GiB, 21.0 GiB free
system RAM: 63.2 GiB
server 0.40.6: keeps 3 models (automatic), parallel 1, keep-alive 30m, KV cache q8_0, flash attention on
loaded: qwen3-coder:30b 18.2 GiB all on the GPU
other: python; not Ollama (in use minus Ollama's models) 5.9 GiB
not read: ssh GPU read (no ssh entry for this host)
```

`--host <name>` reads one configured host; `--json` prints `{host: card}`,
a card `{gpus, unified, ram_bytes, server, loaded, other_users, read_at,
sources}` with `null` for anything unknown. A remote host's log is never
read; under Windows WDDM `nvidia-smi` has no per-process memory, so the
card names the other processes and adds what the card holds beyond
Ollama's models. Exit 0, or 1 for an unknown `--host`.

## `halo ollama traffic`

```sh
halo ollama traffic
halo ollama traffic --host <name> --model <model> --since 7d
halo ollama traffic --json
```

Halo 3.3.4.0 R2: per host and model, the calls this machine's ledger holds
(`~/.halo/ollama/traffic.jsonl`: one line per call to a local model server,
see [MODELS-ollama.md](MODELS-ollama.md)'s "The ledger"); on a fleet hub
that includes every member's calls to it (`fleet.ollama.share`). Above each
host its hardware card in one line, then one line per model: calls (and
how many were compaction), p50 / p95 prompt tokens against the window sent
and p95's share of it, trims, cut replies (`done_reason: length`), 499 /
500 / timeouts, reloads (a call whose `load_ms` passed 2 s), the eval rate's
p50 and the calls per machine:

```text
'default': GPU 0: NVIDIA GeForce RTX 4090 [CUDA] 22.5 GiB, 21.0 GiB free; server 0.40.6: keeps 3 models (automatic), parallel 1, keep-alive 30m, KV cache q8_0, flash attention on
  qwen3.8:27b: 42 calls (3 compaction); prompt p50 12.3k / p95 30.1k of 32.8k (92%); trims 2, cuts 1; 499 0, 500 3, timeouts 0; reloads 4; eval 61 tok/s; from this machine 30, mac@book 12
```

`--host` keeps one host (its name here, or its url), `--model` one model,
`--since` the span (`1h`, `24h` the default, `7d`); `--json` prints the rows.
A member's line that names this machine by its LAN address is counted under
the local host. With nothing recorded it answers `no ledger yet: calls to
<host> are recorded from 3.3.4.0 on`. Exit 0, or 2 for a bad `--since`.

## `halo ollama events`

```sh
halo ollama events
halo ollama events --from-start
halo ollama events --kind cancel-task --since 7d
halo ollama events --watch
halo ollama events --json
```

Halo 3.3.4.0 R2: the local Ollama server's own words as events, newest
last: each run reads the server log's new lines read-only
(`%LOCALAPPDATA%\Ollama\server.log`, `~/.ollama/logs/server.log`, else
`journalctl -u ollama` on Linux), turns them into events with the rules in
[MODELS-ollama.md](MODELS-ollama.md)'s "The events" and adds them to
`~/.halo/ollama/events.jsonl`. The first run starts at the log's end;
`--from-start` reads it from its top (again: its events are added again).
`--watch` keeps reading (every 2 s) and polls `/api/version` and `/api/ps`
every 20 s for loads, unloads and reloads, printing each new event until
Ctrl+C:

```text
2026-10-26 00:15:38 warn  cancel-task [qwen3.8:27b-gpu]: a request was ended while its prompt was still being read (HTTP 500 after 28.46 s): the client's timeout, not a server error -- wait at least as long as the prompt takes at this host's prompt speed
```

`--host` names the host whose log this is (default: the configured host on
this machine), `--kind` keeps one kind, `--since` the span (`24h` the
default), `--json` prints JSON lines. Nothing is sent to the server but
`/api/version` and `/api/ps`. With nothing found it says `no events yet:
<host>'s server log is read from 3.3.4.0 on`, and why when the log is not on
this machine. Exit 0, 1 for an unknown `--host`, 2 for a bad `--since`.
