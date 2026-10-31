# halo host

Read this when a machine serves models and you want every harness on the LAN to read its card, its models, its log and its profiles without a session or ssh there.

`halo host` (3.3.7.0) is a small Halo process on the machine that serves models: the PC with the GPU, the old
box with the 3080, the Mac running Ollama. It runs with no session open, watches that machine's model servers,
and answers paired harnesses on the LAN. A laptop with no GPU then reads the PC's hardware card, its catalog with
a fit verdict, its verified capability profiles and its server log the way it reads its own -- no ssh, no
logging proxy. The commands are in [COMMANDS-host.md](COMMANDS-host.md).

## What it is, and what it is not

The host is an in-depth monitor that informs the harness:

- **It is not an agent.** No model, no goals, no work of its own, no conversation. It has no opinion: it reads,
  computes and reports. "Agent" in Halo means a sub-agent and nothing else; the model-backed role that judges
  what the host finds is the [steward](MODELS-ollama-steward.md).
- **It is not outside Halo.** It is a Halo component, installed, configured and updated by Halo (`halo host
  install`, `halo host status`), running as `halo host`. It talks only to Halo peers on the LAN: no cloud, no
  relay, no third party.
- **It is not autonomous.** Its default is *monitor*: what it finds waits for the next harness that asks. It
  acts only on a typed request from a harness or the steward (the vocabulary below, 3.3.7.0 R2), within the grant
  that peer holds, plus its own deterministic invariants -- mechanics with no judgement in them.
- **No model is ever in it.** It runs no model, ever, not even with the duty steward on (that is its own
  process). Its watch is the steward's job with the rules in "off" mode (findings only, nothing applied, no note
  written by a model). A model that answers "does this fit" would turn arithmetic into an opinion, so the fit and
  the routing answers are computed. It loads a model only when a peer with the grant asks (`control/warm`).
- **Prompt sizes, never prompt content.** A log line that carries a request body (Ollama's debug lines do) is
  replaced by its size before it leaves the machine.
- **Every request leaves one audit line** in `<state>/host/audit.jsonl`: `{at, peer, path, ok, ms}`; an acting
  request's line adds `{op, params, evidence, dry, landed, fix, change_id?, job?}`.

## What it serves

Every route is under `/host/v1/`, signed with the peer's pair key (the fleet protocol's HMAC headers, a 120 s
window, a replay guard) and inside TLS with the host's own pinned certificate when `cryptography` is installed.

| Route | Answers |
|---|---|
| `GET ping` | the host (id, name, version, port, started) and this peer's grants |
| `GET card` | per Ollama server it serves: the hardware card (`halo ollama hardware`'s), its log status, the other clients (the ledger's `from`s over a day), the usable memory ("22.0 GB usable"); the host's start time and its audit count |
| `GET catalog?window=N` | every model there with the fit planner's verdict at that window from the host's own budget (fits, says, need, the largest window it holds), its speed card, its measured facts and whether its profile is verified there |
| `GET profiles` | the battery profiles verified there, each with its digest, Ollama version, probe set and date |
| `GET events?since=&kind=` | the classified server events (the newest 500) |
| `GET tail?n=` | the newest lines of the server log, at most `host.tail_max` (400), request bodies replaced by their size |
| `GET stream` | server-sent events: a `card` frame on open and every minute, an `event` frame per new event, a `resources` frame per new sample, a ping every 10 s |
| `POST simulate {model \| size_gb, window, kv?}` | would it fit here: the installed row, else the packaged library snapshot's size and published shape, else the size given with a typical shape (said to be an estimate) |
| `POST route {need: {model \| size_gb, window, tools?, vision?}}` | `{fits, now, warm, evicts, load_s, verdict}`: can it run here, and right now (free VRAM now, or loaded at that window already), which loaded models would have to unload, how long the load takes (the speed card) |
| `GET me` | this peer's grants, the host machine's `fleet.allow_control`, what applies now, its pending rows, the vocabulary |
| `GET findings` | the steward's rules over the host's own ledger and events, each finding with `where` (host / client) and `suggest` |
| `GET changes` | the host's change rows, newest first, each with its fix row (`verdict`, before, after, the verify line) |
| `GET job/<id>`, `GET jobs` | a job's progress (the battery, the bench, a twin's verify, a pull) |
| `GET pending` | this peer's own rows queued under `fleet.allow_control: ask` |
| `POST control/<op>`, `manage/<op>` | the typed vocabulary below |
| `POST admin/<op>` | the `admin` grant, then 501: admin operations are not part of this version (nothing runs a shell on a host) |
| `POST request {grant, why?}` | a peer asks the owner for a grant: a pending row |
| `POST ledger {lines}` | a peer's calls to a server this host serves, kept in the host's ledger with `from` = the peer (the answer carries the host's profiles under the peer's own names) |

## Grants

Every peer holds `view`: everything in the table above but the acting routes. The owner gives more, peer by peer:

```sh
halo host peers                          # name, id, grants, last seen, requests
halo host grant bob@laptop control       # warm, pin, unload, pivot, the profile fields, the stated KV / flash lines, battery, bench, verify a twin
halo host grant bob@laptop manage        # pull, delete, retire, revert, the stated restart / env lines (and control's ops)
halo host revoke bob@laptop manage
```

`admin` is its own grant (`manage` never implies it); its operations are not part of this version. The host
machine's `fleet.allow_control` caps every grant:

| `fleet.allow_control` | What a peer's grant does |
|---|---|
| `none` | view only, for every peer: the host is strictly a monitor |
| `ask` (the default) | a `control` / `manage` request is queued as a pending row (`<state>/host/pending.jsonl`, `host.ask_ttl_s`, 600 s); the owner answers it with `halo host pending`, `halo host allow <id>` / `halo host deny <id>`, or the Hosts page of that machine's Studio (ASKED OF THIS HOST); once allowed, the same request from that peer runs once within the TTL. A dry preview is never queued |
| `all` | the grants apply as given |

A peer without the grant gets one line naming it and the command that gives it; Studio's Hosts card says the same
and offers "Request control", which writes a pending row of kind `grant` (allowed, it adds the grant).

## The vocabulary

Every operation is a named request with parameters, never a command line: `POST /host/v1/<grant>/<op>` with
`{params, evidence: {finding?, lines?}, scope?, dry?, why?}`. `params.host` names the server (the host's own name
for it; the only one when it serves one). `dry: true` answers `{would, writes, takes, cost}` and lands nothing; a
job-shaped op answers `{job}` and streams `job` frames on `GET stream` (`GET job/<id>` catches up).

| Op | Grant | What it does | What it writes | Stated or applied | Revertible |
|---|---|---|---|---|---|
| `warm {model, num_ctx?, keep_alive?, beside?}` | control | a load (Ollama's warm generate), after the invariants | nothing on disk | applied (an API call) | `unload` |
| `pin {model, num_ctx?, beside?}` | control | the same, `keep_alive -1` | nothing on disk | applied | `unload` |
| `unload {model}` | control | `keep_alive 0` | nothing | applied | `warm` |
| `pivot {from, to, num_ctx?, keep_alive?}` | control | unload A, load B; one event each | nothing | applied | `pivot` back |
| `set_num_ctx`, `set_num_predict`, `set_keep_alive`, `set_tools_max {model, value}` | control | the Halo-side profile field (a fix: it cites a finding), then the verify window | `ollama.profiles`, a row in `changes.jsonl` with its scope, a row in `fixes.jsonl` | applied (Halo's side) | `manage/revert <id>`; the verify reverts it when calls go worse |
| `set_kv_cache_type {value}`, `set_flash_attn {on}` | control | the exact line for the host's OS | nothing | **stated**: `applied: false` | the revert line beside it |
| `rerun_battery {model, force?}`, `bench {model, quick?}`, `verify_twin {model, window?}` | control | the battery / the bench / a twin's verify, on the host, as a job | the profile / the speed card / the twin's record | applied | re-run |
| `pull {model}` | manage | a pull job | Ollama's blob store | applied | `delete` |
| `delete {model, force?}`, `retire {model, why?, force?}` | manage | after the uses card: a live session refuses it, a role or lineup naming it too unless `force` | Ollama's blob store; retire adds a shelf line | applied | `pull` (the re-pull line) |
| `restart_ollama {}`, `set_env {key, value}` | manage | the exact line for the host's OS | nothing | **stated** | the revert line |
| `revert {change}` | manage | the change put back | `ollama.profiles`, a revert line | applied | -- |

Code never changes a host-side Ollama setting, restarts a server or sets `OLLAMA_DEBUG`: the KV type, flash
attention, the env and a restart are stated actions, the line you run there (`ollama_steward/tune_lines.py`).

## The fix loop

A **fix** is a request that changes a profile field or cites a finding. The host enforces, with no model:

- a profile fix names the finding it acts on (`evidence`), else 422 "a fix names the finding it acts on";
- one change in flight per host: a second answers 409 "one change at a time: set_num_ctx landed 40 s ago on pc,
  verifying (2 of 5 calls, at most 560 s more)";
- a cooldown between changes on the same host|model (`host.cooldown_s`, 120) and a rate limit per peer
  (`host.changes_per_hour`, 10; 429), each one line naming the key.

After a profile fix lands the host records `before` (the card's loaded row from `/api/ps`, the newest load's
layers and splits, the ledger's median tok/s, trims, cut replies and errors over the last 10 calls) and watches the
next `host.verify_calls` (5) calls or `host.verify_s` (600 s), whichever comes first. Then it writes `after` and the
verdict into the fix's row and an `event` frame: "set_num_ctx 32768 on pc|qwen3-coder:30b: 16 -> 188 tok/s, no
trims -- kept". Calls that went worse (more trims, cut replies and errors, or a tok/s 10 % lower) revert it and say
so. A window with no calls in it measures nothing: the fix is kept and the line says so. A person's Load is not a
fix: the invariants guard it.

## The invariants

Deterministic, no model: `warm` / `pin` / `pivot` run the fit planner first and refuse a model that does not fit at
the asked window with the plan's verdict line; a second resident is refused unless `beside: true` and the plan says
both fit (one resident per card otherwise); the asked `keep_alive` goes on the load and comes back in the answer; a
request whose dry run says the card would be breached is refused in the same words. The card and `route` answers
carry `usable_gb` and `usable_with_helper_gb`: "20.6 GB usable; 18.6 GB with the helper (qwen3.5:9b, 2.0 GB)".

## Peers act through the host

With `control` on a host, Studio's Load, Unload, Probe and Bench on a machine that host serves go through it, no
fleet member session needed (Pull and Delete with `manage`); the battery and the bench run on the host and their
frames come back as this Studio's jobs (the bench's speed card is kept here too). The Hosts card shows the grants,
"through halo host at <addr>", and a server-setting picker that asks the host for the stated line. A hub whose
member announced a host forwards there too once the hub is paired with it (`fleet/hub_host_cmd.py`).

The steward on any peer lands a change for a host-served model through the host (`control/set_*`, the finding
cited), mirrors it in its own profile and writes the host's verdict back into its journal; a reverted change takes
the mirror with it ([MODELS-ollama-steward-host.md](MODELS-ollama-steward-host.md)). A peer's steward job folds
the host's own findings into its run, and the `client` ones (a prompt that outgrew its window, a cut reply) become
its own work: compaction, a bigger-window model. A peer's calls to a host-served server reach the host's ledger
(`POST ledger`), so the verify window and the bench's busy wait see every client.

## The duty steward

`halo host steward on --model ol:qwen3.5:9b@pc` is an explicit opt-in, off by default: a separate process (`halo host
steward run`, its pid in `<state>/host/steward.json`) running the steward on a small local model through this
machine's Ollama like any other client. It has its own peer record (`duty: true`, `control` by default; `ask` does
not queue it, `none` still caps it), reads `GET findings` and the card every `host.steward.every_s` (300 s), writes
one note per pass (the stream's `note` frames), and lands its fixes through the same vocabulary with the finding
cited -- the guards and the verify judge them like anyone's. Its model is kept 2 minutes and unloaded the moment a
peer's `warm` or `pivot` needs the card; its footprint is the helper line above. `halo host steward off` stops it
and drops its peer record. Its limits: one note and at most two fixes per pass, only Halo-side fields.

## Pairing

The host issues the code, the way a hub does:

```sh
halo host pair                                   # on the host: six words, one peer, ten minutes
halo host join 192.0.2.10 --code "acorn ..."     # on the peer (the port defaults to 7431)
```

The exchange is the hub's (one round of Diffie-Hellman authenticated with the code, the host's certificate
fingerprint inside its answer). The peer keeps the host in `~/.halo/fleet.json` under `hosts` --
`{url, name, host_id, key_ref, fingerprint, tls, serves: [{name, port, addr}], grants, joined_at, state}` -- and the
pair key in `fleet/keys/<key_ref>.key` (0600). The host keeps the peer, its grants and its key in
`<state>/host/peers.json`. `serves` is what the peer matches its own `ollama.hosts` entries by: an entry whose
address and port are one of them reads through that host.

## The ladder

How a harness reads a host it does not serve, in order:

1. **local** -- the server runs on this machine;
2. **host** -- a paired `halo host` serves it (`ollama_steward/host_client.py`): its card, its log, its events and
   its profiles, each line saying "via host <addr>";
3. **ssh** -- the `ollama.hosts` entry has `ssh:` (the 3.3.6.0 reads);
4. **member** -- a fleet member's ledger push carries that machine's events;
5. **api-ps** -- `/api/tags`, `/api/show` and `/api/ps` only (a spill reads as `size_vram < size`).

The brief's fallback ladder for a machine with no host is direct API, then ssh; the host is the upgrade, so when a
host answers it wins over ssh for the log and the card. The catalog itself still comes from that server's own
`/api/tags` (the direct API). A host that does not answer is said so in one line and not asked again for 30 s.
`halo local hosts` prints the rung of each host, `halo ollama hardware --host X` and `halo ollama log --host X`
name "via host" in their source line, and Local -> Hosts shows "served by halo host at <addr>" on the card.

## Running it

```sh
halo host serve                 # in the background; returns once it listens
halo host serve --foreground    # here, until Ctrl+C or `halo host stop`
halo host status                # running since, port, peers, last request, what it watches
halo host stop
```

It does not start under offline mode (`network.offline`), and says so in the hub's own line. It writes
`<state>/host/serve.json` while it runs (`{pid, port, bind, tls, fingerprint, name, url, started, grants_file,
watches}`). One steward job runs per state directory: when Studio or the fleet hub already runs it, the host keeps
that one. When this machine joined a fleet hub, the host sends its ledger lines there with no session open and
announces itself (`POST /fleet/v1/host`), so the hub's Studio lists it ([FLEET.md](FLEET.md#the-hub-knows-hosts)).

## Install as a service

`halo host install` writes the service file through the writer `halo supervise --service` uses, under
`<state>/host/`, and prints the one command that enables it; Halo never runs it:

| OS | File | Enable |
|---|---|---|
| Linux | `halo-host.service` (a systemd user unit) | `systemctl --user link <file> && systemctl --user enable --now halo-host.service` |
| macOS | `com.halo.host.plist` (a launchd agent) | `launchctl bootstrap gui/$(id -u) <file>` |
| Windows | `halo-host-task.xml` (Task Scheduler, at logon) | `schtasks /Create /TN "Halo Host" /XML "<file>"` |

The service runs `python -m halo_harness.cli host serve --foreground` (with `--port` / `--bind` when given).
`install` says so in one line, and writes nothing, on a machine that serves no Ollama host (`--anyway` writes it
all the same); `halo host uninstall` removes the file it wrote and prints the disable command.

## Config

`host.port` (7431), `host.bind` (`0.0.0.0`), `host.enabled` (true), `host.tail_max` (400); R2: `host.ask_ttl_s` (600),
`host.cooldown_s` (120), `host.changes_per_hour` (10), `host.verify_calls` (5), `host.verify_s` (600),
`host.steward.enabled` (false), `host.steward.model`, `host.steward.every_s` (300); see [CONFIG.md](CONFIG.md).
Files under `<state>/host/`: `serve.json`, `codes.json`, `peers.json`, `audit.jsonl`, `pending.jsonl`,
`fixes.jsonl`, `steward.json` / `steward.key` while the duty steward is on, `cert.pem` / `key.pem`, and `stop` while
`halo host stop` asks it to end.

## What R3 adds

The routing answer put to work across the fleet: the placement solver asks each paired host `route` and picks by
fit, warm state and load time; the pivot scheduler uses `pivot`.
