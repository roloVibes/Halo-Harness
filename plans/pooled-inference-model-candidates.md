# Model candidates for distributed (pooled) inference on a ~50–60 GB home-LAN pool

Ranked recommendations, 2026-10-31. Pool reference: 2–3 machines ≈ 50–60 GB total GPU
memory (e.g. 24+24+11 GB), llama.cpp RPC layer-split, 1–2.5 GbE.

**Core rule (measured, three independent sources): pooling buys capacity, not speed.
Every measured multi-node RPC decode is 21–55% slower than the same model on a single
node that could hold it. Choose a pooled model for what no single node can hold —
and prefer MoE, because pooled MoE decode is 4–7× faster in absolute terms than
pooled dense.**

## Tier 1 — recommended for the pool

### 1. Qwen3-Next-80B-A3B Q4_K_M (~46 GB weights) — best pooled candidate
- 3B active / 80B total, 512 experts (10 active), hybrid DeltaNet attention.
- Fits a 50–60 GB pool comfortably with KV headroom (16k F16, 32k+ with Q8_0 KV).
- Smallest compute-per-round-trip of any pool-fitting model → highest decode ceiling;
  estimated 30–45 tok/s pooled (EXTRAPOLATED from the measured 28–55% penalty range —
  no published RPC number for this model exists).
- llama.cpp mainline since b7186 (Dec 2025); perf PR #18683 (Jan 2026) requires
  re-converted GGUFs — old GGUFs may fail without #18762. Pin a current build.
- Single-node alternative: one 48 GB card runs it at Q4 (~53–89 tok/s reported). If
  any node in the fleet has ≥48 GB, don't pool it.
- https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Instruct-GGUF

### 2. gpt-oss-120b (MXFP4, ~59 GB weights, 5.1B active) — the capacity pick
- The most-measured distributed model right now: 2-node layer-split = 33.8 tok/s
  (vs 42.7 single-node) — a 21% pooling penalty but genuinely usable decode.
- Barely fits 50–60 GB: weights ~59 GB + KV on top; **plus ~20 GB of expert routing
  tables replicated to EVERY RPC device** — mixed-VRAM pools OOM small cards. Only
  viable with near-matched node memory.
- Single-node floor: 64–80 GB box serves it at ~30–58 tok/s; 48 GB + CPU offload
  ~19 tok/s. Pool only when no node can hold it.
- https://llamaperf.com/model/gpt-oss (measured), MXFP4 native in llama.cpp.

## Tier 2 — works, with caveats

### 3. Llama 3.3 70B Q4_K_M (~42.5 GB) — the dense pick, batch-only
- 80 layers, hidden 8192, KV 320 KB/token (F16) → ~5 GB @16k. Total ~48 GB.
- Best dense generalist at this size class (the >35B dense class is frozen since
  early 2025 — everything newer is MoE).
- Expect ~3–6 tok/s pooled (measured class: 2.8 @1GbE / 5.9 @10GbE single-source;
  4.9–5.5 all-GPU RPC reported). Batch/background lane only, not interactive.
- https://huggingface.co/unsloth/Llama-3.3-70B-Instruct-GGUF

### 4. Qwen2.5-72B Q4_K_M (~47.4 GB) — equal-quality dense alternative
- Same class numbers as Llama 3.3 70B; heavier weights eat KV headroom (32k ctx
  requires Q8_0 KV). Measured 5.9 tok/s over 10 GbE RPC.
- https://huggingface.co/bartowski/Qwen2.5-72B-Instruct-GGUF

### 5. GLM-4.5-Air (106B-A12B) — better single-node than pooled
- Q3_K_M ~52 GB fits marginally, but 12B active ≈ dense-12B reads per token → poor
  latency amortization under RPC (~10–20 tok/s est).
- The poster child for `-ot ".ffn_.*_exps.=CPU"` expert-offload instead: one 24 GB
  GPU + 64 GB system RAM = 8–15 tok/s, no pool needed.
- https://docs.modelplane.ai/recipes/glm-4.5-air/

## Tier 3 — do not pool

| Model | Why not |
|---|---|
| Qwen3-235B-A22B | IQ2_XS alone (~66 GB) eats the pool before KV; IQ1_M (53 GB) is "extremely low quality, not recommended" |
| Mistral Large 2 123B | Q3_K_S ~55+ GB, zero RPC reports, no headroom |
| Command R+ 104B | Q4 doesn't fit; Q3 fits but it's a 2024 RAG model — not worth a pool |
| Llama 4 Scout 17B-16E | 17B active = worst active/compute ratio here; single 3090 + CPU experts = 24.6 tok/s, no pool needed |
| Qwen3.8-Flash-Next (125B+51B) | 76–104 GB even at extreme quants — out of reach |

## Decision rules for the harness (what the spec should encode)

1. If any single node holds the model → run it there; pooling is only for
   model-too-big-for-every-node.
2. Prefer the lowest-active-parameter model that fits the pool (Qwen3-Next-80B-A3B
   first, gpt-oss-120b second when nodes are memory-matched).
3. Dense 70B pooled = batch lane; never promise interactive speed.
4. KV budget rule: reserve headroom — spec 16k F16 / 32k Q8_0 for 70B-class; never
   promise 64k+.
5. Matched-VRAM nodes matter more than node count (routing-table replication trap).
6. Gate on llama.cpp build vintage per model (b7186+ for Qwen3-Next; re-converted
   GGUFs for #18683).
7. A Wi-Fi node's RTT poisons pipeline decode — wired nodes only, or exclude.

## Candidates to watch (unverified, do not spec yet)

- IFM/K2-V2 (dense 70B, Apache 2.0, reasoning-focused): GGUF sizes and llama.cpp
  maturity unverified.
- DeepSeek-V4-Flash (156 GB MXFP4): the existence proof for big pools (21.4 tok/s
  over 2 machines) — relevant if the user's pool is 150 GB+.
- Ollama PR #10844 merging would make pooled serving one command on existing
  Ollama hosts — revisit the whole deployment story when it lands.
