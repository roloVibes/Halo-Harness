# Commands: halo pool

Read this when you put several machines' GPUs together for one model: list or edit the pool's members, scan the LAN for rpc-server ports, ask what the pool can run, or run the preflight, warm, stop and read the running pool.

`halo pool` (3.3.8.0) knows the pool, tells the truth about it before anything runs, and runs it: what a pool is,
the arithmetic of the fit, the controller and its failure modes are in [POOL.md](POOL.md).
Part of [Commands](COMMANDS.md), which lists every part. `members`, `add`, `remove`, `recommend`, `verdict`, `scan`
and `preflight` launch nothing; `rpc` starts or stops a worker's rpc-server through its halo host, and `halo local
serve --pool` / `halo pool stop` start and stop the pool. Exit codes: 0 done, 1 could not (the reason on stderr), 2
usage. Every verb takes `--json` (the same answer as JSON).

## `halo pool members`

```sh
halo pool members [--json]
```

The members of `~/.halo/pool/pool.json`, one line each: the GPU and its total, what is usable with the duty steward's
helper out, the models resident there, what bundles claim, the free VRAM that is left, the link ("1 GbE", "2.5 GbE",
"Wi-Fi (adapter)", "unknown"), the RTT of the last scan ("0.4 ms", "12 ms -- Wi-Fi?", "not probed (Scan)") and the
member's share of the tensor split. The head line sums the free VRAM and gives the split; a validation line (a name
twice, a port out of range, a `huggingface.local_servers` entry named `pool` that the pool did not write -- the name
is the running pool's) is marked `!`. A member whose VRAM no card reads says so and how to state it.

## `halo pool add`

```sh
halo pool add <name> <host[:port]> [--weight W] [--vram GB] [--json]
```

Adds a member. `<host>` is a paired host's name (`halo host join`; its card gives the GPU and the free VRAM), `local`
(this machine), or the hostname or IP address of a worker that runs `rpc-server` by hand (`worker1.local:50052`,
`192.0.2.11`, `[2001:db8::1]:50053`); the port defaults to `pool.rpc_port` (50052). `--vram GB` states the VRAM of a
worker whose GPU no card enumerates (a worker-grade box with no `nvidia-smi`): the verdict then says "VRAM as you
stated it". `--weight W` sets its tensor-split weight; when every member has one, the split follows the weights
instead of the free VRAM. A name twice, a host:port twice, a port out of range, or a second member on a machine whose
card a member already counts (its free VRAM would count twice) is refused with one line and nothing is written.

## `halo pool remove`

```sh
halo pool remove <name> [--json]
```

Takes a member out of `pool.json`; nothing on that machine changes.

## `halo pool recommend`

```sh
halo pool recommend [--batch] [--json]
```

What fits the pool, the fewest active parameters first (a mixture of experts with few active parameters is the
pooled choice), then what a single node holds (run it there: pooling is unnecessary, ranked last), then what does
not fit with its numbers. Each row: the verdict, the matched-memory block when the model has routing tables, the
batch-only tag, the build line ("needs llama.cpp b7186+"), the speed line (measured elsewhere or extrapolated) and
the preview before any download ("download 46 GB, ~16 min at the assumed 50 MB/s -- nothing downloads until you press
it"). `--batch` shows the batch-only models (Llama 3.3 70B: 3-6 tok/s pooled), always tagged.

## `halo pool verdict`

```sh
halo pool verdict <model> [--json]
```

One catalog model (its name, display name or repo) on the pool: "a single node holds it -- run it there", "fits the
pool: 2 nodes, split 0.69 / 0.31, 32k F16 / 32k Q8_0", or "does not fit: needs 106.0 GB with 20 GB of routing tables
per node, 60.0 GB free across 2 nodes", every number said, and the preview. A name not in the catalog exits 1 with the
catalog's names.

## `halo pool scan`

```sh
halo pool scan [--port N] [--subnet CIDR ...] [--no-own-subnet] [--json]
```

A TCP connect on the RPC port (`--port`, else `pool.rpc_port`, 50052) to every address of this machine's /24 and of
each `--subnet` (else `pool.scan_subnets`; a /24 at most each), then to every member. Each responder: its connect time
("0.4 ms"; past 10 ms "12 ms -- Wi-Fi?"), the paired host at that address, whether it is a member already, and the
`halo pool add` line when it is not. `--no-own-subnet` skips this machine's /24. Only when you run it: nothing in Halo
scans on its own, and offline mode turns the network scan off. The answer is kept in `~/.halo/pool/scan.json`, so
`halo pool members` and Local -> Pool show each member's RTT. A connect says a port is open and how far away the
machine is; it does not say the far end is rpc-server, nor the link's speed (the host card's link does).

## `halo pool preflight`

```sh
halo pool preflight <model> [--window N] [--allow-wifi] [--json]
```

Every check before the pool launches `<model>`, one row each with its lines (POOL.md "The preflight"): `fit` (each
member's free VRAM read now; a resident Ollama model counts as room Warm pivots out), `link` (a Wi-Fi member left
out unless `--allow-wifi`), `rpc` (each worker's rpc-server through its host, its port probed), `versions`
(`llama-server --version` here against each rpc-server's build), `build` (the model's `min_build` on every node),
`gguf` (the file here, else the one Download line), `resident` (what Warm pivots out first) and `window` (the fit's
F16 window; `--window` past it uses Q8_0 KV up to the Q8_0 window; past that it is refused). The first line is
"preflight green: ..." or "preflight blocks <model>: <the first block>"; it exits 1 when something blocks. Nothing
starts.

## `halo pool rpc`

```sh
halo pool rpc <member> on | off | status [--json]
```

A member's rpc-server through its halo host: `status` reads `GET rpc` (running, pid, port, the bound address, the
version), `on` / `off` ask the host's `rpc_server` op (the `control` grant there; a pending row under
`fleet.allow_control: ask`, one line naming the grant under `none`). A `local` member needs none (llama-server uses
this machine's GPU); for a bare address the line says how to start it there by hand, and `status` probes its port.

## `halo local serve --pool`

```sh
halo local serve --pool <model> [--window N] [--allow-wifi] [--keep] [--json]
```

Warms the pool (a change under the steward contract: one per 10 minutes): the preflight, the claim on every member
with its lease (resident Ollama models pivoted out first, each said), each paired worker's rpc-server on, its version
checked again, then `llama-server -m <gguf> --rpc ... --tensor-split ... -ngl 999 --host <LAN address> --port <p>
--api-key <generated> -c <window>` and the `pool` entry (`hf:local/<model>@pool`). It holds the pool in the
foreground, renewing the claims, until Ctrl+C, which stops it; `--keep` returns once it serves (a Studio on this home
renews the claims while it runs, else they end with their lease).

## `halo pool status`

```sh
halo pool status [--json]
```

The running pool: "the pool serves <model>: running", "loading", "degraded (worker2 down)" (a worker's RPC port does
not answer, or the controller's log shows an RPC failure) or "down" (llama-server exited, its last line said); one
line per member (up / down / this GPU, its claim and the lease left), the RPC lines of the log, and the auto-revert's
verdict once the first three calls are in.

## `halo pool stop`

```sh
halo pool stop [--json]
```

Stops the pool (a change; never held back by the 10 minute rule): llama-server stopped, the `pool` entry removed, the
claims released, the rpc-servers the warm started turned off, and each model it pivoted out back as a stated pivot
line ("pivot: pool -> qwen3.8:27b on pc: qwen3.8:27b reloads on pc, ~25 s").
