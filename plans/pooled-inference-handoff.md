# HANDOFF — Pooled inference capability, for the Halo-Harness build session

From: rolo's Mac halo session, 2026-10-31. This folder is research + spec only —
nothing here touches any harness tree. Everything is yours to review, adopt,
rewrite, or reject.

## What this is

The capability: **run one LLM larger than any single machine can hold, across the
GPU memory of multiple machines on the user's LAN**, via llama.cpp RPC (layer-shard
pipeline parallelism). Workers run `rpc-server`; a controller runs
`llama-server --rpc ... --tensor-split` and serves an OpenAI-compatible API. The
user's setup-scanning surfaces pool candidates and model recommendations; the pool
appears as a host-shaped server so `local_sched/place.py` scores it with no new
placement path.

Why this matters to the roadmap: pooled inference is unclaimed territory between
the shipped steward/`halo host`/local_sched work (3.3.4.0–3.3.7.0) and the parked
3.0.1.1 P2P research. The closest ancestor (3.0.1.1's "peer Halo instances sharing
GPUs") was routing-only; this is the execution gap.

## What to read, in order

0. `code/` — **pool_kit, the reference implementation** (README.md maps each module to its
   spec section and harness adaptation target; 33/33 hermetic tests; verified by an
   independent model). Built so the build session doesn't start from scratch.
1. `docs/SPEC-DISTRIBUTED-LLM.md` — the capability spec (11 sections: architecture,
   discovery, consent, recommendation engine, guards + 5 failure modes with
   detection/response, Studio UX, config, phased delivery, open questions).
2. `research/RESEARCH.md` — every measured fact with citations (llama.cpp RPC
   mechanics, the capacity-not-speed penalty table, the MoE analysis, the harness
   integration map verified against GitHub master 3.3.7.0 on 2026-10-31).
3. `docs/MODEL-CANDIDATES.md` — ranked model recommendations for a ~50–60 GB pool
   (Qwen3-Next-80B-A3B first, gpt-oss-120b second, Llama 3.3 70B batch-only).
4. `research/PIPELINE-RECORD.md` — how the spec was produced (coder/judge
   pipeline, all verdicts) — relevant if you want to reuse the pattern.

## Load-bearing facts (do not lose these in adoption)

- Pooling adds **capacity, not speed**: measured −21%/−28%/−47%/−55% vs single-node.
  Decode is latency-serialized per layer boundary; bandwidth nearly irrelevant.
- MoE with low active params is the right pooled choice in **absolute** tok/s
  (4.9 → 21.6–25.1 measured, same config) but its **relative** penalty is worse.
- Expert routing tables **replicate to every RPC device** (~20 GB for gpt-oss-120b)
  — matched-memory pools or the smallest node OOMs.
- KV honesty for 70B-class on a 50–60 GB pool: 16k F16 / 32k Q8_0-KV. Never 64k.
- llama.cpp RPC is officially proof-of-concept/insecure — trusted LAN only.
- Two separate build-vintage facts: Qwen3-Next needs b7186+; PR #18683 needs
  re-converted GGUFs (general concern, not Qwen3-Next-specific).
- Constraints already in your codebase: literal LAN IPs fail the privacy scan
  (hostnames/mDNS only); offline mode needs `allowlisted_local_hosts()` /
  `offline_ok`; local models never default to main role; discovery sweeps are
  explicit-user-action only; steward contract (measured cap, 1 change per model
  per 10 min, auto-rollback) governs every pool control action.
- Watchlist: Ollama PR #10844 (llama.cpp-RPC in Ollama) — when it merges, pooled
  serving becomes one command on existing Ollama hosts; spec must not depend on it.

## Suggested adoption

The spec's §10 proposes three rounds: (1) discovery + recommendation engine,
(2) pool controller + placement integration, (3) Studio UX + guards + CLI.
Unverified items live in §11 — GPU enumeration on worker-grade Windows boxes,
NIC speed detection, per-model RPC benchmarks, and the host service internals
(`halo_harness/host/service.py`, `ops_control.py`, `host_pair_cli.py`,
`fleet/hub_hosts.py`) which were not read during research and should be verified
against master before implementation.

## Hard rule for anything committed

No literal LAN IPs, no personal hostnames from rolo's network — the spec uses
`worker1.local`-style placeholders throughout, keep it that way.
