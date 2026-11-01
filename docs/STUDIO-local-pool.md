# Studio: Local -> Pool

Read this when you look at the pool from Studio: its members and their free VRAM, Warm and Stop with the preflight, what the pool can run, the Scan, or the Library's Pool preset.

Part of [Halo Studio](STUDIO.md), which lists every part. The other Local pages are in
[STUDIO-local.md](STUDIO-local.md); what a pool is and the arithmetic of its fit are in [POOL.md](POOL.md).

## The Pool page (3.3.8.0 R1)

Local's ninth page. Its first line says why the pool exists at all (pooling adds capacity, not speed) and that
rpc-server is for a trusted LAN only. It reads the members and the recommendation when it opens and every 30 seconds
while it is open, the running pool every 10 seconds (every 1.5 s while a Warm runs); the Scan runs only when its
button is pressed. Four blocks:

- **Members**: one row per member of `pool.json` -- the host and RPC port (a paired host's name, `local`, or a
  worker's address), the GPU, the **free VRAM** of its total (its title: usable with the duty steward's helper out,
  the models resident, the claims, and where it was read: the paired host's card, this machine's card, or "as you
  stated it"), the **link** the host card reads ("2.5 GbE", "Wi-Fi (adapter)", "unknown"), the **RTT** of the last
  scan ("0.4 ms", "12 ms -- Wi-Fi?", "not probed (Scan)"), its **share** of the tensor split, and **Remove** (pool.json
  only). The head line sums the free VRAM and gives the split; a validation line stands under it.
- **Run -- Warm and Stop** (3.3.8.0 R3, below).
- **Scan**: the button connects to the RPC port (`pool.rpc_port`, 50052) on this machine's /24 and on every member;
  each responder is listed with its connect time, the paired host at that address, and **Add as <name>** (a paired
  host by its name -- unless a member already counts that machine's card -- else by its address). The answer is kept,
  so the members' RTT column fills from it.
- **What the pool can run**: the recommendation table -- rank, model and its tags (`b7186+`, `batch-only`), the badge,
  what it needs of what is free, the window (`32k F16 / 32k Q8_0`, or the node a single-node row runs on), the speed
  (measured elsewhere or extrapolated), and **Download <N> GB** on what fits: the existing Hugging Face download +
  verify job, the licence card first ([STUDIO-local.md](STUDIO-local.md#hugging-face)). Under each row the verdict, the
  preview before any download and, one click away, every number behind it (the matched-memory block, the build line,
  the speed's source). The check box shows the batch-only models.

## Warm and Stop (3.3.8.0 R3)

The **Run** block: the pool's state line ("the pool serves Qwen3-Next-80B-A3B Q4_K_M: running", "loading",
"degraded (worker2 down)", "down: the pool's llama-server exited (...)", "the pool is not running"); while it runs,
one row per member (up / down / this GPU, its address, its claim and the lease left). Below it: the **model** (what
fits the pool, from the recommendation), the **Wi-Fi switch** (keep a Wi-Fi member: a slower decode; off, the
preflight leaves it out and says so), **Warm** and **Stop**.

While the pool is stopped the block shows the **preflight** of the model picked -- its eight checks, one row each
with its lines and "ok" or "blocks" (fit, link, rpc, versions, build, gguf, resident, window; [POOL.md](POOL.md#the-preflight))
-- and **Warm is enabled only when every check is green**; its title says the first block otherwise, or the 10
minute cooldown. Warm answers at once and the block follows it: the claims on every member (each resident model it
pivots out is a line), each worker's rpc-server, llama-server, the `pool` entry; the lines of the Warm stay under the
block. **Stop** stops llama-server, removes the entry, releases the claims and says how each pivoted-out model comes
back. Warm and Stop are changes under the steward contract (one warm per 10 minutes, the auto-revert on the first
three calls). A pool this Studio did not warm (`halo local serve --pool --keep`) is adopted when the page reads it:
this Studio renews its claims from then on.

## The speed card and the findings (3.3.8.0 R4)

Under Warm and Stop, two blocks (`routes/local/PoolWatch.tsx`):

- **Bench** -- its cost line first ("local: ~129 s on the pool (pc, me: their GPUs are busy for it), writes the pool's
  speed card; no tokens leave the LAN"; "the pool is not running" while it is stopped), **Bench** and **Quick bench**
  (the pool's `-c` alone), the penalty line -- "pool: 30-45 tok/s extrapolated (no pool speed card yet ...)" until a
  card exists, then "pool: 11.2 tok/s measured, -38 % vs pc alone" (the reason on hover) -- the card's lines, the
  bench's lines as they land, and the bundles that hold the pool ("big-reasoner holds the pool for ... (priority
  high)"). `halo local bench --host pool` does the same.
- **Findings** -- the steward's pool-degraded, pool-rtt and pool-spill, one line each (the Steward page lists them
  too, under the server `pool`).

Each member's row under the running pool names the bundle its claim belongs to ("19.7 GB claimed by pool:<model>")
and shows every other bundle's claim on that card as a chip. The members' link cell says which spoke for the link on
hover (the OS's adapter before the probe's RTT).

| Route | What |
|---|---|
| `GET local/pool/bench` | the cost line, the pool's card, its penalty line, the bundles holding the pool |
| `POST local/pool/bench {quick?}` | the bench in the background (202); 409 with the one line when it cannot run now |
| `GET local/pool/findings` | the steward's pool findings |

## The Library's Pool preset

The Library's tenth preset, **Pool**, replaces the rows with the pool catalog's models as Hugging Face GGUF rows: each
keeps its card and its fit on the host picked (46 GB on a 24 GB card spills: the reason to pool) and adds the pool
badge -- "pool: fits (2 nodes, 32k Q8_0)", "pool: 1 node holds it", "pool: no" -- with its verdict and preview under
the row. Its Download is the hub row's own; a pool row has no Pull to an Ollama host and the preset no Save as role
template (the pool serves one model across its members, it fills no lineup role). The bundle line shows the members'
head ("2 of 2 members with their VRAM read, 60.0 GB free; ...").

## The routes

All under `local/` (studio/pool_api.py and, 3.3.8.0 R3, studio/pool_act_api.py; dispatched by studio/local_api.py), the same guard as every Studio route;
each answer carries `cli`, the `halo pool` line that does the same:

| Route | Answers |
|---|---|
| `GET local/pool/members` | the members with their budget rows, the split and where it came from, the head, the validation lines, `rpc_port`, the last scan's line |
| `GET local/pool/run` | 3.3.8.0 R3: the running pool (`state`, `line`, `members` with their claims, `degraded`, the auto-revert's `judge`), `warm` (the Warm in progress and its lines), `cooldown`; adopts a pool this process does not hold |
| `GET local/pool/preflight?model=&allow_wifi=1&window=` | the preflight: `ok`, `checks`, `blocks`, `line`, the window and the KV cache it would use; 404 for a model not in the catalog |
| `POST local/pool/warm {model, allow_wifi?, window?}` | 202 and `busy` at once (the launch waits for /health in the background); 409 inside the 10 minute cooldown or while a Warm runs |
| `POST local/pool/stop` | the stop's lines |
| `POST local/pool/rpc {member, to: on \| off \| status}` | a member's rpc-server through its halo host |
| `GET local/pool/recommend?batch=1` | `{rows, others, hidden, head, nodes, free_gb}`: the ranked rows, what does not fit, the batch-only models left out |
| `GET local/pool/verdict?model=` | one catalog model's fit and preview (404 for a name not in the catalog) |
| `POST local/pool/scan {port?, subnets?, own_subnet?}` | `{candidates, members, networks, notes, line}`; a GET is 405: a scan is never a page load |
| `POST local/pool/members {op: add \| remove, name, host?, port?, weight?, vram_gb?}` | pool.json edited; 422 with the line when refused |
| `GET local/library?preset=pool` | the Library's answer with the pool rows (`pool` on each) and `pool.head` |
