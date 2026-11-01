# Pooled Inference Capability Specification

> **Provenance**: researched + drafted 2026-10-31 in a rolo halo session. Coder lane: qwen3-coder:30b-gpu on the LAN box (3 rounds). Judge panel: qwen3.8:27b-gpu + kimi-k3 + deepseek-v4-flash (2 rounds, 21 findings → 5 → 0). Independent final verifier: glm-5.3 (10-point check, 9 PASS, remainder fixed by kimi-k3 editorial pass). Companion docs: ../research/RESEARCH.md (evidence + citations), ../docs/MODEL-CANDIDATES.md (ranked model recommendations), ../HANDOFF-FOR-HARNESS-SESSION.md (adoption notes). Do not commit literal LAN IPs anywhere derived from this spec — hostnames only (privacy_rules.py LAN_IP_RE).


---

## 1. Summary  

Pooled inference enables a Halo user to run one large language model across multiple machines on their local area network (LAN), by combining the GPU memory of those machines. This capability is implemented via llama.cpp’s RPC backend, which supports layer-shard (pipeline) parallelism only. Tensor parallelism over RPC — enabled by the parallelism-mode flag `--split-mode row` — fails due to an upstream issue (llama.cpp #23568) and is not supported. Note that `--tensor-split` is a different flag: it is the weight-distribution flag in the client command (`llama-server --rpc host:port,... --tensor-split <weights>`) that assigns layer weights across workers, and it works as intended. The system therefore uses `--tensor-split` to distribute weights across workers while relying exclusively on layer-shard (pipeline) parallelism.

The feature is intended for users with 2 or more machines that together hold sufficient VRAM to run models too large for any single machine. It does **not** increase inference speed; instead, it adds **capacity**. Performance penalties are measurable: -21% (gpt-oss-120b, 2-node, 42.7→33.8 tok/s), -28% best / -55% worst range (llama.cpp #22850), -47% (Qwen2.5-72B over 10GbE, 11.1→5.9 tok/s). Decode is latency-serialized per layer boundary; bandwidth is nearly irrelevant (30–50 Mb/s actual traffic during decode on a 2.5 GbE link); prefill pipelines well.

MoE models with low active parameters are the right pooled choice in absolute terms — same RPC config, dense 72B at 4.9 tok/s vs a 60B-A3B MoE at 21.6–25.1 tok/s. However, the relative penalty vs single-node is **worse** for MoE due to routing overhead: expert routing tables replicate to every RPC device (~20 GB for gpt-oss-120b regardless of split), so mixed-memory pools OOM the smallest node.

The system supports mixed hardware types (CUDA, Metal, Vulkan) within a single pool, but requires careful memory planning. The RPC path is fully synchronous and uses only hidden state (~8 KB/token) plus final logits (~1 MB/token on large vocabularies). Officially proof-of-concept / insecure — trusted LAN only, never past the router.

---

## 2. User Story  

A user has two machines with GPUs of 24 GB and 24 GB VRAM respectively, and wants to run `Qwen3-Next-80B-A3B Q4_K_M`, which requires ~46 GB total VRAM and cannot fit on either machine alone.

### Setup & Discovery  
The user pairs worker machines with `halo host pair` or adds them with `halo host join`, using a six-word pairing code and fingerprint pinning to authenticate each worker. Pool membership is recorded in the pool.json config file defined in §9, where the user adds each member as a hostname/port/weight entry. Discovery is performed using `providers/ollama_discover_net.sweep()` and `sweep_networks()`, which run only on explicit user action. A new probe type targets the RPC server port, distinct from existing Ollama API checks.

### Pairing & Consent  
The user runs `halo host pair` on the controller (the machine that will orchestrate the pool). Workers respond with a six-word code and fingerprint pinning. The controller grants `view | control | manage | admin` permissions via `fleet.allow_control`. Pending requests are answered using `allow <id>` or `deny <id>`.

### Model Recommendation  
The system surfaces recommended models in Studio based on available VRAM, active parameter count, KV context budget, and build vintage. For a ~50–60 GB pool, it suggests:
- Qwen3-Next-80B-A3B Q4_K_M (~46 GB, 3B active, estimated 30–45 tok/s pooled, EXTRAPOLATED)
- gpt-oss-120b (~59 GB MXFP4, 5.1B active, measured 33.8 tok/s, needs matched node memory)
- Llama 3.3 70B Q4_K_M (~42.5 GB, ~3–6 tok/s, batch-only)

### Launch & Use  
Once the pool is configured and a model is selected:
1. The user calls `POST local/warm` to load the model.
2. The system uses `local_sched/place.py` to place the model across nodes.
3. The OpenAI-compatible endpoint becomes available at `/v1/completions` or `/v1/chat/completions`.
4. Sessions can use this endpoint as they would any other LLM backend.

### Setup Scanning  
The harness scans for potential pooled setups during `halo host pair`. If a machine has sufficient VRAM and is reachable via RPC, it is surfaced in Studio under "Pool Candidates".

---

## 3. Architecture  

### Pool Controller  
The pool controller is a **host-shaped server** that:
- Writes `serve.json` to manage model serving.
- Speaks the signed host API (`route`, `pivot`, `warm`, `view`) so `local_sched/place.py` treats it as a regular host.
- Does not use `local_api.dispatch_local`; instead, it uses the standard host API paths.
- **Launch mechanism**: The controller (the client machine) runs `llama-server --rpc host:port,... --tensor-split <weights>` — that process is what serves the OpenAI-compatible API. Workers run only `rpc-server`.

### RPC Workers  
Each worker machine runs:
- `rpc-server` (the small llama.cpp RPC daemon; CUDA, Metal, and Vulkan workers can mix).
- Communicates over synchronous RPC paths with minimal bandwidth usage (~8 KB/token hidden state + ~1 MB/token logits).
- Operates in trusted LAN-only mode; no external exposure.

### Discovery Pass  
- Uses `providers/ollama_discover_net.sweep()` to enumerate LAN addresses.
- Adds a new probe for the RPC server port, distinct from existing Ollama API checks.
- Does not include generic GPU-service discovery (new work).

### Capability Map  
- Per-machine info is reported via `fleet/capabilities_host.py`:
  - `{os, distro, cpu, cores, ram_gb, gpu: [{name, vram_gb}], disk_free_gb}`
- Workers must be running `halo host` to report GPU details.

### Consent & Pairing  
- Workers join the pool via `halo host pair`/`join`.
- Grants are managed through `fleet.allow_control`, with actions gated by user consent.
- Control actions on workers go through the same `control` act path as other hosts.

### Request Path  
- The system exposes an OpenAI-compatible API endpoint (`/v1/completions`, `/v1/chat/completions`) via the pool controller.
- The harness's existing ollama/OpenAI-compatible provider path can call this endpoint directly.

### Lifecycle  
- Start: `POST local/warm`
- Stop: the controller tears down its llama-server process (no route loads a model except POST local/warm).
- Health: periodic checks via `local_sched/place.py`
- Eviction: automatic if a node fails or becomes unresponsive

---

## 4. Discovery & Scanning  

### Reuse of Existing Tools  
- Uses `providers/ollama_discover_net.sweep()` and `sweep_networks()` to scan LAN.
- Adds new RPC port probe type (not currently supported by existing Ollama discovery).
- Discovery sweeps run only on explicit user action — never passively.

### GPU Reporting  
- Per-machine GPU info is collected via `fleet/capabilities_host.py`.
- Reports are shared through the fleet hub.

### Studio Integration  
- Pool candidates are surfaced in Studio under a new tab or section.
- The system displays available VRAM, model fit, and performance estimates.

---

## 5. Consent & Security  

### Pairing & Grants  
- Workers join via `halo host pair` with six-word code + fingerprint pinning.
- Permissions are granted through `fleet.allow_control`.
- Actions on workers follow the same `control` path as other hosts.

### Trusted LAN Only  
- RPC ports are only accessible within the LAN.
- No external exposure of RPC endpoints is allowed.
- All host references must be hostnames or mDNS names; literal LAN IPs are banned by `privacy_rules.py`.

### Offline Mode Compliance  
- RPC ports must be allowlisted via `allowlisted_local_hosts()` (private IPs, local hostnames, or `offline_ok: true`).
- Offline mode rejects non-compliant hosts.
- The privacy scan fails the build on literal LAN IPs — hard build gate.

### Local Model Role Constraint  
- Local models never default to the main role.

---

## 6. Model Recommendation Engine  

### Decision Rules  
1. **Single-node-first rule**: If any single node can hold the model, run it there.
2. **Lowest active params that fits**: Prefer MoE models with fewer active experts.
3. **Matched memory warning**: Warn if a worker has less VRAM than required for a model.
4. **KV context budget**: For 50–60 GB pools:
   - 70B-class KV: ~320 KB/token F16
   - Spec: 16k F16 / 32k Q8_0-KV context (never promise 64k)
5. **Build vintage gating**: 
   - Qwen3-Next specifically requires llama.cpp build b7186+.
   - Perf PR #18683 requires re-converted GGUFs — a general build-vintage concern for any model using that PR's optimizations, not a Qwen3-Next requirement.

### Studio Recommendations  
- Displays a table of model candidates with VRAM, active params, estimated tok/s.
- Example models:
  - Qwen3-Next-80B-A3B Q4_K_M (~46 GB, 3B active, EXTRAPOLATED 30–45 tok/s pooled)
  - gpt-oss-120b (~59 GB MXFP4, 5.1B active, measured 33.8 tok/s, needs matched node memory)
  - Llama 3.3 70B Q4_K_M (~42.5 GB, ~3–6 tok/s, batch-only)

---

## 7. Control Plane & Guards  

### Steward Contract  
All pool actions must join the steward contract:
- Never exceed measured cap.
- At most one change per model every ten minutes.
- If a change leads to worse performance, it rolls back automatically.
- Change-ledger scopes: session / until-restart / keep.
- **Note**: The steward is shipped (Ollama 3.3.4.0, duty-steward process R2, cross-machine placement in local_sched R3). Pool actions join the existing steward contract; they do not reimplement it.

### Host-Level Guards  
- One change per host allowed.
- Cooldown and rate limits apply.

### Failure Modes & Responses  

1. **Worker down mid-generation**: 
   - Detection = controller's rpc connection error or health probe timeout.
   - Response = in-flight request fails (no retry), pool marked degraded, user notified, remaining workers keep serving other models.

2. **VRAM overcommit**: 
   - Detection = rpc-server load failure or size_vram mismatch after load.
   - Response = refuse to start, surface which node and how much is missing, suggest eviction of the competing process — never silently swap to CPU.

3. **Routing-table OOM on small nodes**: 
   - Detection = pre-flight memory check per node (weights × per-node share + routing-table replication overhead) BEFORE launch.
   - Response = block launch with the matched-memory warning.

4. **Wi-Fi latency poisoning**: 
   - Detection = probe RTT check during discovery (warn if a member's RTT exceeds a threshold).
   - Response = exclude wireless members by default, allow explicit override.

5. **Digest/build mismatch**: 
   - Detection = GGUF digest comparison across nodes before launch (same tag, different digest = divergent).
   - Response = block launch, surface the divergence, offer re-pull.

---

## 8. Studio UX  

### Pool Page  
- Displays:
  - Members (hostnames, ports)
  - VRAM per node
  - Tensor split settings
  - Active model name and tok/s
  - Health status

### Recommendations View  
- Shows model candidates with performance estimates.
- Includes build vintage warnings.

### Launch/Stop Controls  
- Buttons to `warm` or `stop` models.
- Refreshes while open using a store pattern similar to `routes/fleet/ostore.ts`.

---

## 9. Config & Naming  

### Config File Shape  
```json
{
  "members": [
    {
      "hostname": "worker1.local",
      "port": 8000,
      "weight": 60
    },
    {
      "hostname": "worker2.local",
      "port": 8000,
      "weight": 40
    }
  ]
}
```

### Example File  
Shipped with an example `pool.json` file in the repo.

### Hostname-Only References  
All hostnames must be resolvable via mDNS or local DNS; literal IPs are banned.

### CLI Surface Suggestion  
```bash
halo pool add <hostname>:<port>  # PROPOSED new command surface
halo pool list                   # PROPOSED new command surface
halo pool remove <id>            # PROPOSED new command surface
halo pool warm <model>           # PROPOSED new command surface
halo pool stop                   # PROPOSED new command surface
```

---

## 10. Implementation Notes for Build Team  

### Reuse Map  
- `providers/ollama_discover_net.sweep()` and `sweep_networks()`
- `fleet/capabilities_host.py` for GPU reporting
- `local_sched/place.py` for placement logic
- `local_api.dispatch_local` for routing (used in Studio API layer)
- `studio/local_sched_api.py` for API surface

### New Work List  
1. Add new RPC port probe in discovery.
2. Implement pool controller as host-shaped server.
3. Build `halo_harness/studio/pool_api.py`.
4. Add `routes/local/Pool.tsx` and store logic.
5. Add failure detection and rollback logic.

### Phased Delivery Suggestion  
1. **Round 1**: Discovery + model recommendation engine
2. **Round 2**: Pool controller + placement integration
3. **Round 3**: Studio UX + guards + CLI surface

### Ollama PR #10844 convergence
Ollama has no native clustering capability today. Ollama PR #10844 wires llama.cpp RPC into Ollama via an `OLLAMA_RPC_SERVERS` environment variable and an `ollama rpc` worker command; the PR is open but unmerged as of this writing. When it merges, pooled serving becomes a single command on existing Ollama hosts, providing a natural convergence path for this spec. This spec notes that path for planning purposes but must not depend on it; the design herein stands on llama.cpp RPC directly.

### Foundation Dependencies  
The capability builds on:
- Ollama steward (3.3.4.0)
- `halo host` (3.3.7.0 R1)
- Duty-steward process (R2)
- Cross-machine placement in local_sched (R3)

---

## 11. Open Questions  

### UNVERIFIED Items  
1. **Worker-grade Windows GPU enumeration**: Not yet tested or confirmed.
2. **NIC speed detection**: No current support for detecting link speeds in the harness.
3. **Per-model RPC benchmarks**: No benchmarking data available at this time.
4. **Host service internals not yet read**: Some internal host logic may need further review before full integration.

---