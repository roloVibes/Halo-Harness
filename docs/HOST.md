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
  acts only on a typed request from a harness or the steward, and this release (R1) answers reads only.
- **No model is ever in it.** It never loads a model and never runs one. Its watch is the steward's job with the
  rules in "off" mode (findings only, nothing applied, no note written by a model). A model that answers "does
  this fit" would turn arithmetic into an opinion, so the fit and the routing answers are computed.
- **Prompt sizes, never prompt content.** A log line that carries a request body (Ollama's debug lines do) is
  replaced by its size before it leaves the machine.
- **Every request leaves one audit line** in `<state>/host/audit.jsonl`: `{at, peer, path, ok, ms}`.

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
| `POST control/*`, `manage/*`, `admin/*` | 403 with one line naming the grant this peer does not hold; R2 gives them meaning |

## Grants

Every peer holds `view`: everything in the table above. `control` (warm, unload, pivot, the window and cache
settings, a re-probe), `manage` (pull, delete, retire, restart, revert) and `admin` (a raw command) are granted per
peer, one by one, and arrive in 3.3.7.0 R2 with the typed operations behind them. Until then Studio's Load,
Unload, probe and bench on a host-served machine say so in one line.

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

`host.port` (7431), `host.bind` (`0.0.0.0`), `host.enabled` (true), `host.tail_max` (400); see
[CONFIG.md](CONFIG.md). Files under `<state>/host/`: `serve.json`, `codes.json`, `peers.json`, `audit.jsonl`,
`cert.pem` / `key.pem`, and `stop` while `halo host stop` asks it to end.

## What R2 adds

The host acts: the typed `control` / `manage` / `admin` operations and their per-peer grants, the fix loop (the
steward sends a named operation with the finding it acts on, the host applies it, measures before and after, and
keeps or reverts it), the session-less command path, probe and bench through the host, and the optional duty
steward. R3 puts the routing answer to work across the fleet.
