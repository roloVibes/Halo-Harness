# Commands: halo host

Read this when you run `halo host` on a machine that serves models, pair a harness with it, or install it as a service.

`halo host` (3.3.7.0 R1; R2: the grants, the pending rows and the duty steward) is the model-free Halo process on the
machine that serves models; what it is, what it serves, the vocabulary and the ladder are in [HOST.md](HOST.md). Part of [Commands](COMMANDS.md), which lists every part.
Exit codes: 0 done, 1 could not (the reason on stderr), 2 usage.

## `halo host serve`

```sh
halo host [serve] [--port N] [--bind ADDR] [--foreground] [--no-tls] [--json]
```

Starts the host: the steward's watch over the Ollama servers this machine serves, the resources sampler, the
ledger forwarder to any fleet hub this machine joined, and the signed listener on `host.port` (7431). Without
`--foreground` it starts a detached `halo host serve --foreground` and returns once that one listens; with it, it
runs here until Ctrl+C or `halo host stop`. `--port 0` picks a free port, `--bind` the address (default
`host.bind`, `0.0.0.0`), `--no-tls` keeps it HMAC-signed plain HTTP even with `cryptography` installed. Offline mode
and `host.enabled: false` each keep it from starting, said in one line; a second `serve` while one runs says where it runs.

## `halo host status`

```sh
halo host status [--peer NAME] [--json]
```

One block: running since, the pid and url, the port and the certificate, the peers paired, the last request and the
audit count, what it watches and whether the steward's watch runs in it. `--peer NAME` asks a host this harness
paired with instead (its start, its version, its audit count, each server it serves with its usable memory and its
log line).

## `halo host stop`

```sh
halo host stop [--json]
```

Asks the host this machine runs to stop (the stop file under `<state>/host/`); it ends within a second and removes
its serve.json.

## `halo host pair`

```sh
halo host pair [--ttl 10m] [--ascii] [--json]
```

A one-time six-word code (and its QR) that pairs one peer with this host, with the `view` grant; the join line to
type on the other machine; the host's fingerprint. The code is single use and expires (`--ttl`, default ten
minutes).

## `halo host join`

```sh
halo host join <host:port|url> --code "<six words>" [--fingerprint HEX] [--json]
```

Pairs this harness with a host (the port defaults to 7431): the exchange is the hub's, the result is kept in
`~/.halo/fleet.json` under `hosts` with the servers it serves, and an `ollama.hosts` entry at one of those addresses
reads through it from then on (`halo local hosts` shows the rung). `--fingerprint` insists on a certificate.

## `halo host install`

```sh
halo host install [--port N] [--bind ADDR] [--os linux|macos|windows] [--anyway] [--json]
```

Writes the service file under `<state>/host/` -- `halo-host.service` (a systemd user unit), `com.halo.host.plist`
(launchd), `halo-host-task.xml` (Task Scheduler at logon) -- running `python -m halo_harness.cli host serve
--foreground`, and prints the one command that enables it. Halo never runs that command. On a machine that serves
no Ollama host it says so in one line and writes nothing, unless `--anyway`. `--os` writes another OS's file.

## `halo host uninstall`

```sh
halo host uninstall [--os linux|macos|windows] [--json]
```

Removes the service file `install` wrote and prints the one command that disables the service if it was enabled.

## `halo host grant` / `halo host revoke`

```sh
halo host grant <peer> view|control|manage|admin [--json]
halo host revoke <peer> <grant> [--json]
```

On the host: gives a paired peer (by name or id) a grant, or takes one back (3.3.7.0 R2; what each covers is in
[HOST.md](HOST.md#the-vocabulary)). `manage` carries `control`'s operations; `admin` is never implied by `manage`, and
its operations are not part of this version. The line says what this machine's `fleet.allow_control` does to it
(`none`: view only for every peer; `ask`: each request queued for you first). `view` stays every paired peer's.

## `halo host peers`

```sh
halo host peers [--json]
```

The peers paired with this host: name, id, grants, last seen and how many requests its audit holds, and this
machine's `fleet.allow_control`. The duty steward's own peer is marked.

## `halo host pending` / `halo host allow` / `halo host deny`

```sh
halo host pending [--json]
halo host allow <id> [--json]
halo host deny <id> [--json]
```

Under `fleet.allow_control: ask`, a peer's `control` / `manage` request (or its "Request control") waits here for
`host.ask_ttl_s` (600 s). `allow` lets the same request from that peer run once within the TTL (a grant request:
adds the grant); `deny` drops it. An expired or answered row says so in one line.

## `halo host steward`

```sh
halo host steward on --model REF [--grant control|manage] [--json]
halo host steward off [--json]
halo host steward status [--json]
halo host steward run [--once] [--json]
```

The duty steward ([HOST.md](HOST.md#the-duty-steward)): `on` writes `host.steward.enabled` and `host.steward.model`,
gives it its own peer record with the `--grant` (default `control`), keeps its model's profile at `keep_alive 2m` and
starts `halo host steward run` as a separate detached process (never the host process). `run` is that process: one
pass every `host.steward.every_s` (300 s), `--once` for one. `off` stops it and drops its peer record; `status` says
whether it runs, its model and its last note.
