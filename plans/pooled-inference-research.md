# Distributed LLM inference across home-LAN machines — consolidated research

Compiled 2026-10-31 from three web-research agents + two earlier agents (LAN recon,
ecosystem survey). Every measured fact carries its source; extrapolations are labeled.

## 1. The capability: llama.cpp RPC is the only viable path

- Pipeline parallelism (layer sharding): `rpc-server` on worker machines, `llama-server
  --rpc host:port,... --tensor-split` on the client. CUDA, Metal, Vulkan workers mix.
  Officially labeled proof-of-concept / insecure — trusted LAN only.
  https://github.com/ggml-org/llama.cpp/tree/master/tools/rpc
- Only the hidden state (~8 KB/token) + final logits (~1 MB/token, large vocabs) cross
  the wire; the RPC path is fully synchronous — nodes idle on each other.
  https://github.com/ggml-org/llama.cpp/discussions/9136
- Tensor parallelism over RPC (`--split-mode row`) FAILS with RPC devices — layer
  split only. https://github.com/ggml-org/llama.cpp/issues/23568
- Everything else is out: exo (Apple-only tier 1), Petals (dormant), b4rtaz
  distributed-llama (power-of-2 nodes, ≥10GbE), vLLM/Ray (datacenter interconnects),
  MLX distributed (Apple-only). Ollama 0.40.x has no native clustering; PR #10844
  (llama.cpp-RPC based) open and unmerged — watchlist.
- PR #16276 (one RPC server per node, Oct 2025) improved prefill significantly;
  pin a recent build. https://github.com/ggml-org/llama.cpp/discussions/16445

## 2. The physics: pooling adds CAPACITY, not speed

Measured, repeatedly:

| Setup | Local | Pooled (RPC) | Penalty | Source |
|---|---|---|---|---|
| Qwen2.5-72B Q4, M2 Ultra vs +DGX Spark @10GbE | 11.1 tok/s | 5.9 tok/s | −47% | kjaiswal/llama-cpp-distributed-benchmarks |
| Same-model class, all-GPU RPC vs CPU-offload-25-layers | 3.16 (offload) | 4.9–5.5 | RPC beats offload | note.com/takkunblue |
| gpt-oss-120b, 2-node layer-split | 42.7 (1 node) | 33.8 | −21% | llamaperf.com/model/gpt-oss |
| RPC decode penalty range | — | — | −28% best, −55% worst | llama.cpp #22850 |
| Dense 72B → 60B-A3B MoE, same RPC config | 4.9 | 21.6–25.1 | 4-5× faster by model choice | note.com/takkunblue |

- Decode is latency-serialized: every layer boundary is a round-trip; bandwidth is
  nearly irrelevant (2.5 GbE links show 30–50 Mb/s actual traffic during decode —
  discussion #9136).
- Prefill/prompt-processing DOES pipeline well (batched); the pain is decode.
- Community work on layer-offset pipelining and RPC+TP hybrids exists but is unmerged
  (#9136).

### The MoE question — resolved with measurements

Theory says low-active-param MoE makes the round-trip a LARGER fraction of per-layer
time (worse relative penalty). Measurements say: the relative penalty is real, but the
absolute decode ceiling is so much higher that pooled MoE is dramatically faster than
pooled dense in absolute tok/s (4.9 → 21.6–25.1 measured for the same RPC config).
gpt-oss-120b pooled still hits 33.8 tok/s. **Pooled MoE is the right recommendation
for usable throughput; pooled dense 70B is a batch-only lane.**

MoE-specific traps (measured):
- Expert routing tables replicate to EVERY RPC device (~20 GB for gpt-oss-120b
  regardless of split) — mixed-VRAM pools OOM small cards.
  https://github.com/youngharold/tightwad/blob/bc6ffd0f/benchmarks/GPT-OSS-120B-TEST-REPORT.md
- Pipeline-parallel with experts in host RAM was silently disabled by
  `has_tensor_overrides()`; community patch speeds prefill, decode flat ±1–3%
  (discussion #29964).

## 3. Quantization and context facts

- Quant affects weights only; activations/KV cross the wire unquantized. RPC is
  quant-agnostic. KV quant (Q8_0 `--cache-type-k/v`) is an orthogonal lever that
  halves KV size. (discussion #9136; #18273 ran Q8_0 weights + Q8_0 KV over 5 GPUs)
- KV per token (F16): 70B-class (80 layers, 8 KV heads, 128 dim) ≈ 320 KB/token →
  5.0 GB @16k. GLM-4.5-Air ≈ 184 KiB/token. Qwen3-32B ≈ 262 KB/token.
- On a ~50–60 GB pool with a 42–47 GB model: ~6–10 GB left after per-node compute
  buffers → **16k ctx F16 / ~32k ctx Q8_0 KV** is the honest ceiling for 70B-class.
  Don't spec 64k.

## 4. Measured hardware context (the test LAN, 2026-10-31)

- the main PC (`tower`): ≥24 GB VRAM proven (qwen3-coder:30b-gpu fully resident,
  size_vram 20.25 GB), Ollama v0.40.13, 86–96 tok/s on 27B models.
- a second PC (`sagan`): a Windows box, Ollama v0.40.6, GPU present but
  model/VRAM unverified (no model loaded at probe time).
- a laptop: 16 GB unified memory, ~11 GB GPU-wireable, on Wi-Fi (wire it or
  exclude — Wi-Fi RTT craters pipeline decode).
- The router has 2.5 GbE LAN ports. Negotiated PC NIC speeds unverified.
- Pool estimate: ~50–60 GB.

## 5. Harness integration map (GitHub master, 3.3.7.0, 2026-10-31)

The roadmap position: steward shipped (3.3.4.0), `halo host` + duty steward +
`local_sched/` cross-machine placement shipped in 3.3.7.0 R1–R3 (merged 2026-10-31).
**Pooled inference is unclaimed roadmap territory** — the closest ancestor is the
parked 3.0.1.1 "peer Halo instances sharing their GPUs" (routing-only, research-only).

Exact integration points for a pooled "virtual host":

- **Host-shaped server**: a pool controller that writes `serve.json` and speaks the
  signed host API (`route`/`pivot`/`warm`/`view`) so `local_sched/place.py` scores it
  as a host with NO new placement path.
- **Discovery**: `providers/ollama_discover_net.sweep()`/`sweep_networks()` enumerates
  addresses (runs only on explicit user action); a NEW probe type for the rpc-server
  port is needed — the existing probe only confirms Ollama APIs. There is no generic
  "GPU service discovery" today — that is new work.
- **Capability map**: `fleet/capabilities_host.py` reports
  `{os, distro, cpu, cores, ram_gb, gpu: [{name, vram_gb}], disk_free_gb}` per
  machine (nvidia-smi based) — computed per harness and shared via the hub. An RPC
  worker needs a `halo host` (or the pool client) on its machine to report its card.
- **Consent**: workers join as peers via `halo host pair`/`join` (six-word code,
  fingerprint pinning) with grants `view | control | manage | admin`, pending requests
  under `fleet.allow_control` answered `allow <id>`/`deny <id>`. (Correction:
  `fleet/agent_tokens.py` is token accounting, NOT consent.)
- **Steward contract** (any control action must join it): "never above a measured cap,
  at most one change per model per ten minutes, a change followed by worse calls rolls
  back on its own." Change ledger scopes: session / until-restart / keep. Host-level
  (3.3.7.0 H10): one change per host, cooldown, rate limit.
- **Studio pattern**: `halo_harness/studio/pool_api.py` routes registered via
  `local_api.dispatch_local` (like `local/sched`), + `routes/local/Pool.tsx` +
  a store `.ts` with refresh-while-open cycle. ~35 existing `*_api.py` modules to
  copy from (`local_hosts_view.py`, `ollama_steward_api.py` closest).
- **Constraints**: `privacy_rules.py` LAN_IP_RE bans committed literal LAN IPs — use
  hostnames/mDNS names. `providers/http.py` offline mode: pool rpc ports must ride
  `allowlisted_local_hosts()` (private-IP/local-hostname or `offline_ok: true`) or
  offline mode refuses them. Local models never default to main role.

## 6. Open items (flagged, not papered over)

1. the second PC's GPU model/VRAM — unverified (one `nvidia-smi` on that box closes it).
2. Negotiated NIC speeds of the two PCs — unverified remotely.
3. The 2.8/6.1/7.4 tok/s @1/2.5/10 GbE baseline (localaimaster.com) is single-source
   and doesn't fully reconcile with RTT math; the kjaiswal + llamaperf numbers are
   better anchored.
4. No published tok/s exists for Qwen3-Next-80B-A3B over RPC — the 30–45 estimate is
   extrapolated from the measured penalty range.
5. Host service internals (`halo_harness/host/service.py`, `ops_control.py`,
   `host_pair_cli.py`, `fleet/hub_hosts.py`) were not fetched this pass — quote them
   in implementation only after reading.
