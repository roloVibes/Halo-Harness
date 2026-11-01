# The pool: one model across several machines

Read this when you want to run a model too big for any one of your GPUs across the GPU memory of several machines on your LAN, warm or stop it, or you want to know what the pool can and cannot do.

A **pool** (3.3.8.0 "Pooled") is a set of paired hosts whose GPU memory serves one model together over llama.cpp
RPC: each worker runs `rpc-server`, the controller runs `llama-server --rpc worker1.local:50052,... --tensor-split
0.55,0.45` and serves an OpenAI-compatible API. The commands are in [COMMANDS-pool.md](COMMANDS-pool.md), the page
in [STUDIO-local-pool.md](STUDIO-local-pool.md); the research and the spec behind it are
`plans/pooled-inference-research.md` and `plans/pooled-inference-spec.md`.

## The facts, in plain words

- **Pooling adds capacity, not speed.** Every measured pooled decode is slower than the same model on one machine
  that can hold it: 21 % (gpt-oss-120b on two nodes, 42.7 -> 33.8 tok/s), 28-55 % (llama.cpp's own range), 47 %
  (Qwen2.5-72B over 10 GbE). Decode waits for a round trip at every layer boundary; the bandwidth hardly matters
  (30-50 Mb/s of real traffic on a 2.5 GbE link), the latency does. Prompt processing pipelines well. So Halo's first
  rule: if one node holds the model, run it there -- the pool is for what no single node can hold.
- **A mixture of experts with few active parameters is the pooled choice.** Its relative penalty is worse, but its
  absolute speed is far higher: the same RPC setup ran a dense 72B at 4.9 tok/s and a 60B-A3B at 21.6-25.1. A dense
  70B pooled (3-6 tok/s) is a batch lane, never interactive.
- **Routing tables go to every node.** A mixture of experts' routing data is copied to every RPC device (~20 GB for
  gpt-oss-120b, whatever the split), so a mixed pool runs its smallest node out of memory first: matched node memory
  matters more than node count.
- **The window is said honestly.** On a 50-60 GB pool a 70B-class model holds about 16k of context at F16 and 32k
  with the KV cache at Q8_0; Halo never promises more than 32k on a pool.
- **Builds matter.** Qwen3-Next needs llama.cpp b7186 or newer, on the controller and on every rpc-server.
- **Trusted LAN only.** llama.cpp's RPC is a proof of concept with no authentication: never past your router.
- **Wi-Fi poisons decode.** A round trip per layer boundary makes a Wi-Fi member the pool's slowest link; the launch
  leaves one out unless you allow it.

## What R1 does

R1 knows the pool and tells the truth about it before anything runs:

- **Members** (`~/.halo/pool/pool.json`): `{name, host, rpc_port, weight?, vram_gb?}`. `host` is a paired host's
  name (`halo host join`, [HOST.md](HOST.md)), `local`, or the hostname or IP address of a worker that runs
  `rpc-server` by hand. A name twice, a host:port twice, a port out of range, or a second member on a machine a card
  already counts is refused with one line.
- **Free VRAM per member**, from its host card: usable with the duty steward's helper out, minus the models resident
  there, minus what bundles claim (a claimed model that is resident counts once). The source is named: "the card of
  halo host pc-host at ...", "this machine's card", or "VRAM as you stated it" (`--vram`, for a worker whose GPU no
  card enumerates). The host card also carries the **link** of the adapter that carries the host's own address --
  wired or wireless and its speed ("1 GbE", "2.5 GbE"), read from the OS on that machine (Windows `Get-NetAdapter`,
  Linux `/sys/class/net/<if>/speed` and `/wireless`, macOS `networksetup -listallhardwareports`).
- **The tensor split** is proportional to free VRAM, not to card size; for a model, to what each node has left for
  layers after its own copy of the routing tables and 1 GB of buffers. Every member's `weight` set: the weights.
- **The fit**, one deterministic function: "a single node holds it -- run it there", "fits the pool: 2 nodes, split
  0.69 / 0.31, 32k F16 / 32k Q8_0", or "does not fit: needs 106.0 GB with 20 GB of routing tables per node, 60.0 GB
  free". The arithmetic: weights + a routing table per node + 1 GB per node + the KV cache at 16k F16 against the
  members' free VRAM, and each node's share against its own; the window is the room left, F16 and Q8_0 (doubled),
  clamped at 32k. The matched-memory block is said only for a model with routing tables. The catalog
  (`local_pool/catalog.py`) holds Qwen3-Next-80B-A3B Q4_K_M (46 GB, 3B active), gpt-oss-120b (59 GB, 5.1B active,
  20 GB routing measured) and Llama 3.3 70B Q4_K_M (42.5 GB, batch-only); every figure that is an estimate says so.
- **The recommendation**: what fits the pool, the fewest active parameters first, then what one node holds, then what
  does not fit; batch-only models only with `--batch`, always tagged; each row with the build line, the speed (the
  number measured elsewhere, or "extrapolated") and the **preview before any download**: "needs 53.6 GB -- 60.0 GB
  free across 2 nodes; 32k Q8_0; one 2 GB routing table per node; download 46 GB, ~16 min at the assumed 50 MB/s --
  nothing downloads until you press it". The download is the existing Hugging Face download + verify job, one button.
- **Scan**: a TCP connect on the RPC port (`pool.rpc_port`, 50052) to this machine's /24 (and `pool.scan_subnets`)
  and to every member, only when you run it. Each responder says its connect time ("0.4 ms"; past 10 ms "12 ms --
  Wi-Fi?"). The adapter type, when a host card has it, wins over the RTT: "Wi-Fi (adapter)" is certain, an RTT only
  suspects. A connect says a port is open and how far away the machine is -- not that the far end is rpc-server, nor
  the link's speed.
- The Library's **Pool** preset lists the pool catalog's models with their badge ("pool: fits (2 nodes, 32k Q8_0)" /
  "pool: 1 node holds it" / "pool: no"), and **Local -> Pool** shows the members, the recommendation and Scan.

## The controller (3.3.8.0 R3): the pool runs

`halo local serve --pool <model>` (and the Pool page's **Warm**) launches the pool; `halo pool stop` (**Stop**) takes
it all back. Each step is said, and a refusal is one line that names the mechanic and the number.

### The workers: `rpc-server` behind the host's grants

On a worker, `halo host` starts and stops llama.cpp's `rpc-server` on request: the host op `rpc_server {to: on|off}`
([HOST.md](HOST.md#rpc-server-for-a-pool-3380-r3)), the `control` grant, a pending row under `fleet.allow_control: ask`, one
line under `none` that names the grant it needs. It runs `rpc-server -H <the LAN address this host serves on> -p
<pool.rpc_port> --mem <this machine's free VRAM in MiB>` (the card's usable memory with the helper out, minus the
resident models and the claims -- the pool's own claim left out, it is the room rpc-server serves), keeps its pid,
port, bound address, binary and version in `~/.halo/host/rpc_server.json`, answers `GET rpc` with them, and writes
its output to `~/.halo/host/rpc-server.log`. `halo host rpc on | off | status` does the same on the worker itself;
`halo pool rpc <member> on | off | status` from the controller, through that member's host. The binary is
`pool.rpc_server_bin`, else `rpc-server` on PATH, else the one beside the llama-server Halo would run (llama.cpp's
release archives carry both). This machine (`local`) needs none: llama-server uses its GPU directly.

### The preflight

`halo pool preflight <model>` -- and the Pool page before Warm is enabled -- runs every check and says each one:

| check | what it reads | blocks when |
|---|---|---|
| fit | the fit (above) over each member's free VRAM read **now** (the host card fresh, not the 15 s cache); a model resident there counts as room, since Warm pivots it out first; a claim never does | the pool does not fit (the node and the GB), the matched-memory block, or one node holds it ("run it there") |
| link | the adapter type first (the host card's `link`), the RTT second | a Wi-Fi member is left out unless `--allow-wifi`, `pool.allow_wifi` or the page's switch keeps it, said either way; leaving it out can make the pool not fit |
| rpc | each worker's rpc-server through its host (`GET rpc`), then its port probed | a bare-address worker whose port does not answer (a paired one is started by Warm) |
| versions | `llama-server --version` here against each rpc-server's build | the builds differ (both printed) or the RPC protocols do |
| build | the model's `min_build` on every node | Qwen3-Next below b7186 on any node (the node named) |
| gguf | the catalog row's repo in a `huggingface.model_dirs` folder or the hub cache | the GGUF is not here: the one Download line (46 GB, ~16 min at ...; nothing downloads until you press it) |
| resident | what is resident and claimed on every member | never: it says what Warm pivots out first |
| window | the window asked: the fit's F16 window by default; past it Q8_0 KV up to the Q8_0 window | past the Q8_0 window ("a larger promise never reaches a request") |

A version not known (a worker's rpc-server not running yet) is a note, not a block: llama-server checks the RPC
protocol itself when it connects; Warm reads the version again once the worker's rpc-server runs.

### Claims with a lease

Warm places a **claim on every member** in 3.3.7.0 R5's shape: bundle `pool:<model>`, the member's share (its layers
at the launch window + its routing-table copy + 1 GB of buffers), through the paired host's `control/claim` (in this
machine's claims file for `local`; none for a bare address, said). Before a claim, a member whose free VRAM is short
of its share has its resident Ollama models unloaded -- each a pivot line ("pivot: qwen3.8:27b -> pool (Qwen3-Next)
on pc, unloaded first: the pool's share is never spilled to the CPU") -- and a member still short is the overcommit
line ("refused: worker2 needs 23.1 GB for its share, 20.0 GB free -- 3.1 GB missing"), every claim taken back.

Every pool claim carries a **lease**: `until` = now + `pool.claim_lease_s` (120 s). The process that warmed the pool
renews it every lease / 3 seconds (its heartbeat; the host renews on its own clock), so a killed Studio's claims end
within the lease and the cards are free again: an expired claim is not a claim -- the host's residency, its
invariants and every peer's scheduler leave it out. A Studio that finds a running pool it does not hold adopts it
(its heartbeat renews the claims from then on). A bundle claimed by a halo process (the Pack Manager's tick) gets the
same lease; a bundle turned on from the CLI keeps no lease (until `halo pack off`).

### The launch

```sh
llama-server -m <gguf> --alias <model> --rpc 192.0.2.11:50052,192.0.2.12:50052,192.0.2.13:50052 \
  --tensor-split 0.42,0.42,0.16 -ngl 999 --host <this machine's LAN address> --port <p> --api-key <generated> -c 32768
```

`--rpc` lists the workers in member order, and this machine's GPU (a `local` member) comes last in `--tensor-split`;
the split is the fit's (`model_split`); `-ngl 999` puts every layer on the GPUs -- never a CPU fallback: a node that
runs out of memory while loading is refused with the node and its share, and nothing stays claimed. Past the F16
window the KV cache goes to Q8_0: `--cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on -c <the Q8_0 window>`. The
binary is the one `halo local serve` finds or fetches. Its output goes to `~/.halo/local/servers/pool-<port>.log`,
whose first line shows the command with the key as `***`.

The running pool is the `huggingface.local_servers` entry named `pool` (`hf:local/<model>@pool`): `url` (this
machine's LAN address), `max_ctx` (the fit's window: the window truth clamps every request to it -- a 64k ask gets
32,768 and the reason "the pool's fit (max_ctx)"), `api_key_env` (`HALO_SECRET_POOL_API_KEY`: the generated key lives
in the env file, never in config.json, a log line or `~/.halo/pool/run.json`), `log` and `runtime` (so the steward's
server-log reader tails the controller's log), `members`, `model`, `cache`, `pool: true`. A pool call's ledger line
names `pool` as its host. Stop: the process stopped, the entry removed, the claims released, the rpc-servers it
started turned off, and each model it pivoted out comes back as a stated pivot ("pivot: pool -> qwen3.8:27b on pc:
qwen3.8:27b reloads on pc, ~25 s"), never Ollama's silent load on the next call. `halo local serve --pool` holds the
pool in the foreground (Ctrl+C stops it); `--keep` returns once it serves, and the pool outlives the command.

### Warm and stop under the steward contract

Warm and Stop are changes (`ollama_steward/changes_pool.py`, rows in `~/.halo/ollama/changes.jsonl`: key
`pool|<model>`, field `pool.state`, before / after): one warm per 10 minutes (a second one inside it is one line with
the minutes left; a stop is never held back), and the **auto-revert**: when the pool's first three calls are slower
than the single-node bench card of the same model (their median tok/s under the card's), or half of them failed, the
pool stops and the line says both numbers. With no such card, the failures alone judge (said). `halo local changes
revert <id>` of a warm stops the pool. `halo host steward` and the duty steward keep their hands off the pool.

### The pool in placement

The pool answers `route` like a host (`local_pool/route.py`): a catalog model that fits it, `now` when it runs that
model, the load seconds from the GGUF (on disk at an assumed 1.5 GB/s, else the download at your measured rate), and
degraded when a worker is down. `place.solve` scores it as one more option, minus its penalty: 38, the research's
measured 21-55 % decode penalty against one node (its midpoint) until a bench measures the pool's own -- so a single
node that holds the model wins, and the pool takes a lane no node holds. `halo local place` says the pool's line.

### When something fails

- **A worker down mid-generation**: that request fails once, and the line says so -- "the pool is degraded (worker2
  down): the request failed once and is not retried -- the pool's llama-server answered 500". Nothing retries it
  silently. The pool reads **degraded (worker2 down)** on its page, in `halo pool status` and in `route` (it takes
  no lane): from each worker's RPC port probed, and from the controller's log ("Remote RPC server crashed or
  returned malformed response", a failed connect). Stop, then Warm with the members that answer.
- **VRAM overcommit**: refused before launch with the node and the missing GB; an OOM while loading, with the node and
  its share.
- **A node that cannot hold its routing-table copy**: the matched-memory block before launch.
- **A Wi-Fi member**: left out unless allowed, said.
- **A version mismatch**: blocked with both versions.
- **llama-server exits**: the pool reads **down**, its last log line said.

### From a peer

The controller's `halo host` serves the `pool` entry and its key in its catalog (`GET catalog`'s `pool`, the view
grant every paired peer holds). A peer with no `pool` entry of its own resolves `hf:local/<model>@pool` through it, to
the controller's LAN address with that key and the fit's window. An unpaired machine gets nothing: the host answers
only signed requests from its peers.

### Security

llama.cpp's RPC is a proof of concept with no authentication and no encryption: **a trusted LAN only**. Each worker's
rpc-server binds the LAN address its `halo host` serves on, never 0.0.0.0, and starts only behind that host's grants
(the first answer on a host says the trusted-LAN line once). The controller's llama-server listens on its LAN address
so peers can reach it, behind a key generated at every Warm and handed only to paired peers. Neither should ever be
reachable past your router.

## Config

`pool.rpc_port` (50052): the rpc-server port `add` defaults to and `scan` probes. `pool.scan_subnets` ([]): the CIDRs
`scan` covers besides this machine's /24 (a /24 at most each). `pool.claim_lease_s` (120): the pool's claim lease.
`pool.allow_wifi` (false): keep Wi-Fi members. `pool.bind`: the address the pool's llama-server binds (default: the
LAN address this machine's halo host serves on). `pool.rpc_server_bin`: the rpc-server a worker runs. See
[CONFIG.md](CONFIG.md). Files: `~/.halo/pool/pool.json` (the members), `~/.halo/pool/scan.json` (the last scan),
`~/.halo/pool/run.json` (the running pool), `~/.halo/host/rpc_server.json` (a worker's rpc-server).
