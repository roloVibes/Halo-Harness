# The pool: one model across several machines

Read this when you want to run a model too big for any one of your GPUs across the GPU memory of several machines on your LAN, or you want to know what the pool can and cannot do yet.

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
- **Wi-Fi poisons decode.** A round trip per layer boundary makes a Wi-Fi member the pool's slowest link; R2's launch
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

## What R1 does not do

Nothing in R1 launches a process, loads a model or changes a host: no `rpc-server`, no `llama-server`, no warm, no
stop. The only network traffic is the Scan you press and the host-card reads Halo already does. R2 (the controller)
starts `rpc-server` on a worker through its `halo host` (the `rpc_server on|off` host op, behind grants), launches
`llama-server` through `halo local serve` with `-ngl 999 --host 127.0.0.1` (and `--cache-type-k/-v q8_0` past the F16
budget, never a CPU fallback), checks the RPC and build versions of every node before launch, and makes the pool the
`huggingface.local_servers` entry named `pool` (`hf:local/<model>@pool`; the name is reserved now) that answers
`route` like a host. R3 adds Warm / Stop on the page, the pool's own measured tok/s and its penalty against one node,
and a bundle's claim on the pool.

## Config

`pool.rpc_port` (50052): the rpc-server port `add` defaults to and `scan` probes. `pool.scan_subnets` ([]): the CIDRs
`scan` covers besides this machine's /24 (a /24 at most each). See [CONFIG.md](CONFIG.md). Files: `~/.halo/pool/pool.json`
(the members), `~/.halo/pool/scan.json` (the last scan).
