# Studio: Local -> Pool

Read this when you look at the pool from Studio: its members and their free VRAM, what the pool can run, the Scan, or the Library's Pool preset.

Part of [Halo Studio](STUDIO.md), which lists every part. The other Local pages are in
[STUDIO-local.md](STUDIO-local.md); what a pool is and the arithmetic of its fit are in [POOL.md](POOL.md).

## The Pool page (3.3.8.0 R1)

Local's ninth page, read-only this round: nothing on it launches a process, loads a model or changes a host. Its
first line says so ("warm and stop arrive in R2") and why the pool exists at all (pooling adds capacity, not speed).
It reads the members and the recommendation when it opens and every 30 seconds while it is open; the Scan runs only
when its button is pressed. Three blocks:

- **Members**: one row per member of `pool.json` -- the host and RPC port (a paired host's name, `local`, or a
  worker's address), the GPU, the **free VRAM** of its total (its title: usable with the duty steward's helper out,
  the models resident, the claims, and where it was read: the paired host's card, this machine's card, or "as you
  stated it"), the **link** the host card reads ("2.5 GbE", "Wi-Fi (adapter)", "unknown"), the **RTT** of the last
  scan ("0.4 ms", "12 ms -- Wi-Fi?", "not probed (Scan)"), its **share** of the tensor split, and **Remove** (pool.json
  only). The head line sums the free VRAM and gives the split; a validation line stands under it.
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

## The Library's Pool preset

The Library's tenth preset, **Pool**, replaces the rows with the pool catalog's models as Hugging Face GGUF rows: each
keeps its card and its fit on the host picked (46 GB on a 24 GB card spills: the reason to pool) and adds the pool
badge -- "pool: fits (2 nodes, 32k Q8_0)", "pool: 1 node holds it", "pool: no" -- with its verdict and preview under
the row. Its Download is the hub row's own; a pool row has no Pull to an Ollama host and the preset no Save as role
template (the pool serves one model across its members, it fills no lineup role). The bundle line shows the members'
head ("2 of 2 members with their VRAM read, 60.0 GB free; ...").

## The routes

All under `local/` (studio/pool_api.py, dispatched by studio/local_api.py), the same guard as every Studio route;
each answer carries `cli`, the `halo pool` line that does the same:

| Route | Answers |
|---|---|
| `GET local/pool/members` | the members with their budget rows, the split and where it came from, the head, the validation lines, `rpc_port`, `not_yet`, the last scan's line |
| `GET local/pool/recommend?batch=1` | `{rows, others, hidden, head, nodes, free_gb}`: the ranked rows, what does not fit, the batch-only models left out |
| `GET local/pool/verdict?model=` | one catalog model's fit and preview (404 for a name not in the catalog) |
| `POST local/pool/scan {port?, subnets?, own_subnet?}` | `{candidates, members, networks, notes, line}`; a GET is 405: a scan is never a page load |
| `POST local/pool/members {op: add \| remove, name, host?, port?, weight?, vram_gb?}` | pool.json edited; 422 with the line when refused |
| `GET local/library?preset=pool` | the Library's answer with the pool rows (`pool` on each) and `pool.head` |
