# Local models: the fit, the prompt budget, the host log, the battery, the search, the host -- rolo's brief (2026-10-29)

Parts A-L of rolo's `local-model-fit.md` (the measured readout that precedes them stays on his machine: the
incident, the deleted tags, the captured payload). Measurements are from his RTX 4090 box on Ollama 0.40.13.
The ROADMAP entry "ADDED 2026-10-30 ... the local-model brief" maps each part to a round. Workers: read the part
your brief names in full; the knowledge-base ids it cites are rolo's, not in this repo.

## 7. Copy-paste brief for the Halo Harness session

### Part A — the fit verdict itself (weights + KV vs VRAM)

**Feature: "Fit" for local models (Halo Studio → Local tab)**

Goal: for every Ollama model on every configured host, Halo says up front whether it fits the target
GPU at a given context window, at what speed, and can offer a fitted, verified variant — so a user
never discovers a bad fit by crashing llama-server mid-task.

Why (real incident): a tag with no explicit `num_ctx` let Ollama auto-fit per request; a
65,536-token request spilled the KV cache to CPU (`splits = 7`) and llama-server died with
`CUDA error: an illegal memory access` — four crashes in one evening, all while serving a remote
client, plus 93 model reloads in a day from models swapping in and out.

What the API already gives you (verified on Ollama 0.40.13):
- `GET /api/tags` → every tag and its `size` in bytes (includes the mmproj blob if present).
- `POST /api/show {model}` → `model_info` with everything needed to *predict* KV size:
  `<arch>.block_count`, `<arch>.attention.head_count_kv`, `<arch>.attention.key_length`,
  `<arch>.attention.value_length`, `<arch>.context_length`; plus `details`: `family`,
  `parameter_size`, `quantization_level`, `runner`.
- `GET /api/ps` → for each loaded model: `size`, `size_vram`, `context_length`.
  **`size_vram < size` means part of the model is on CPU — the single most reliable "it didn't fit" signal.**
- VRAM: locally `nvidia-smi --query-gpu=memory.total,memory.used,memory.free`; on a LAN host run it
  there, or read that host's Ollama log line `gpu memory id=0 … available="X GiB"`.

The arithmetic (validated against measurements on this box):
- KV bytes per token = `block_count × (key_length + value_length) × head_count_kv × bytes_per_element`
  with `bytes_per_element` = 1 for `q8_0` KV, 2 for f16.
  Check: qwen3-coder:30b → 48 × (128+128) × 4 × 1 = 49,152 B/token; at 32,768 ctx = 1.50 GiB, and the
  server logged `CUDA0 KV buffer size = 1632.00 MiB`. ✔
- Required VRAM ≈ weights + KV(ctx) + compute overhead (measured ≈ 1.2 GB with flash-attn on,
  batch 512). Cross-check: `/api/ps` size for the pinned coder = 18.9 GiB at 32,768 =
  17.3 GB weights + 1.71 GB KV + ~1.2 GB buffers. ✔
- Usable VRAM on this box ≈ 20.6 GB; keep ≥ 2 GB headroom.
- Max safe ctx = `floor((usable − headroom − weights − overhead) / kv_per_token)`.

Minimum useful version:
1. Per-model row: name, size, family, quant, and a **fit badge** — `fits @ 32768` /
   `fits only with CPU spill (slow)` / `too big for this GPU` — computed from the arithmetic above
   against the selected host's VRAM.
   **Also check the prompt side:** the badge should flag when the model's window cannot hold Halo's own
   prompt for the current session (measured ~25 k tokens and growing with tool output — see §6b). A
   32 k model that fits in VRAM can still be unusable if the harness prompt overflows it, because
   Ollama silently truncates to half the window and the model loses its instructions.
2. A context slider or preset windows that updates the badge live, showing predicted VRAM and
   headroom.
3. Optional **"Create fitted variant"**: write a Modelfile (`FROM <tag>`, `PARAMETER num_ctx <n>`,
   `PARAMETER num_gpu 999`, **no TEMPLATE line**), run `ollama create <name>-gpu -f …`, then
   **verify** — load it and check `size_vram == size` in `/api/ps` (and, when the log is readable,
   `offloaded N/N layers`, a `CUDA0 KV buffer size` line, `splits = 2` during generation) — and report
   the measured tok/s. Before running, state what it does, what it writes and how long it takes.
4. Mark which tags are fitted/verified and which are raw library tags.

### Part B — the prompt-budget gotcha (fix this in the same pass)

A fit verdict based only on VRAM is incomplete: the harness's own payload can overflow a model's window
and be silently halved. Captured from a real Halo session against `mythos-sec:24b-gpu` (32,768-token
window) — the user's typed input was two words:

| call | prompt tokens | output |
|---|---|---|
| 1 | 1,231 | 1 (probe-shaped) |
| 2 | 25,622 | 1,337 @ 258 tok/s |
| 3 | **41,104 → truncated to 16,386** | 1,081 |
| 4 | 72 | — |

Payload: system prompt 14,351 chars (~3,587 tok) + user message 104,934 chars (~26,233 tok) =
123,025 chars (~30,756 tok) — and **87 % of the user message is the auto-memory block, included twice**:

- `# Memory (auto-loaded from MEMORY.md)` — 19,732 chars, **twice**
- `## Topic files (read on demand …)` — 25,452 / 26,086 chars, **twice**
- memory + CLAUDE.md + harness sections = 91,002 chars (~22,750 tok); the redundant copy alone is
  45,184 chars (**~11,300 tok**)
- the actual session summary is only ~6,600 chars (~1,650 tok)

Ollama truncates an over-window prompt by keeping `n_keep = 4` tokens from the **start** plus the
**tail** — so the task summary at the front is dropped while the memory boilerplate at the end survives,
and the model answers without knowing the task. Verified bounds: a 21,239-token prompt passes through
untouched; a 41,239-token prompt is always cut to 16,386 (32,768/2 + 2), with or without `num_predict`.

Required:
1. **Dedupe** the auto-memory / CLAUDE.md block in the assembled prompt (~11.3 k tokens per request, free).
2. **Trim the memory + topic index for local-model sessions** (the topic-file list alone is 25 k chars).
3. **Order the payload so the task summary survives truncation**, or refuse to send an over-window prompt
   instead of letting it be silently halved.
4. **Warn before sending**: "prompt 30,756 tok vs window 32,768 (usable 16,386) — this session will be truncated."

Good already: Halo sends `num_gpu: 41` (all layers) and `num_ctx: 32768`.

### Part C — read the host's Ollama log (part of "setting up local models")

When Halo connects to or configures an Ollama host it should also find that host's Ollama log and treat it
as the source of truth for fit and failure: the API tells you what is loaded, the log tells you whether it
**fit** and why it broke.

Where the logs are:
- **Windows:** `%LOCALAPPDATA%\Ollama\server.log`, plus rotated `server-1.log`, `server-2.log`, … and `app.log`
- **Linux (systemd):** `journalctl -u ollama -n 500`; user install: `~/.ollama/logs/server.log`
- **macOS:** `~/.ollama/logs/server.log`
- **LAN host:** the same paths on that machine — read them there if Halo can run there; otherwise fall back
  to `/api/ps` (`size_vram < size` = CPU spill) plus the hints below.

Setting it up: verify the log exists and is live (mtime advances while a request runs). If more detail is
needed Halo can offer a short `OLLAMA_DEBUG=1` window — but warn that it is very verbose, and note that it
still does **not** log request bodies (see the proxy recipe below).

Lines worth parsing (all observed on 0.40.13):
- **fit:** `load_tensors: offloaded N/N layers to GPU`; `llama_kv_cache: CUDA0 KV buffer size = …`;
  `CPU KV buffer size = …` (any real value = spill); `sched_reserve: graph … splits = N`
  (2 = fully on GPU; 14 / 117 = CPU-spilled)
- **headroom:** `gpu memory id=0 library=CUDA available="X GiB" free="Y GiB"`
- **truncation:** `truncating input prompt limit=X prompt=Y keep=4 new=Z` — the payload overflowed and the middle was dropped
- **failures:** `CUDA error: an illegal memory access`; `llama-server terminated` (exit `0xc0000409` is just
  the Windows death after a CUDA abort, not a second bug); `| 500 |`; `| 499 |`;
  `aborting chat request due to client closing the connection` (a client timeout, not a server fault)
- **aborted loads:** `client connection closed before llama-server finished loading`

Gotchas when reading it:
- **It rotates** on upgrade/restart — read the whole set (`server*.log`, by mtime), not just `server.log`.
- `server.log` can contain invalid UTF-8 and **ripgrep silently stops early** on it — use `grep -a` or read bytes.
- `OLLAMA_DEBUG_LOG_REQUESTS=1` does **not** log request bodies on 0.40.13 (verified, also with
  `OLLAMA_DEBUG=1`). To see exactly what Halo sends, run a logging proxy: move Ollama to `127.0.0.1:11436`
  (start `ollama serve` directly with `OLLAMA_HOST` — **not** the tray app) and bind the proxy on `11434`.
  On Windows the existing **port-based** Ollama firewall rule covers the new listener, so no client change is
  needed (verified reachable from another LAN machine). Trap: on Windows a listener with SO_REUSEADDR can
  bind a port Ollama already holds, after which the tray app reports "existing instance found" and its
  server never starts — kill every ollama process, confirm `netstat` shows the port free, then start
  `ollama serve` yourself. Reference implementation: `~/ollama-watch\fitprobe.py`.
- This PC already has a read-only watcher worth absorbing instead of reinventing:
  `~/ollama-watch\watch.ps1` tails the log, writes `alerts.log` + `status.json`, and asks a
  local model to explain each alert.

Deliverable: in the Local tab (or a Logs panel), per host and per model — last load result (layers on GPU,
KV placement, splits), measured tok/s, any truncation warning for the current session, and error lines with
timestamps; a one-click "tail log" and the file path. The fit badge should cite the log as evidence:
"verified — 41/41 layers, splits = 2, 258 tok/s" vs "unverified" vs "spilled — 59/66 layers, 16 tok/s".

Acceptance: with the Local tab open against this PC, every tag shows a fit verdict that matches
reality; creating a fitted variant for a raw tag yields a tag that loads with `size_vram == size` at the
chosen window; Halo can read that host's own Ollama log and say whether the last load fit; and it can warn
that a prompt will be truncated *before* a bad answer appears.

Do not: change host-side Ollama settings or delete models without an explicit, itemised confirmation;
treat a client-side `num_ctx` as enforceable (0.40.13 has no server-side cap — `OLLAMA_CONTEXT_LENGTH`
is only a default); or rely on `OLLAMA_DEBUG_LOG_REQUESTS` for request bodies.

Reference: sections 1–6c of this file hold the measured numbers, the verified inventory, the deleted tags
and the captured payload. Harness knowledge entries: `f-20261029-ed2069`, `f-20261029-f73f5f`,
`d-20261029-ff66cf`, `f-20261029-891dbe`, `f-20261029-805e52`.

### Part D — reviewed against the repo (HEAD `6d75a1b3`, 3.3.5.0 R3): what exists, what to add

**Read first — much of the local-model groundwork is already in the tree. Do not rebuild it:**

- **window truth:** `halo_harness/agent/model_window.py::window_of` (7 sources in `SOURCE_ORDER`, clamped by
  learned cap / `max_ctx` / card fit / `HARD_CONTEXT_CAP`); `providers/ollama_calibrate.py` measures the cap
  by loading and reading `/api/ps` `size` vs `size_vram`, persisting `~/.halo/ollama-fit.json`;
  `agent/ollama_window.py::prepare_window` runs before every Ollama call (reply reserve, pre-send compaction,
  `trim_recovery`).
- **fit & hardware:** `ollama_steward/hardware.py::hardware_card` (GPUs, server settings, loaded models,
  `other_users`, via startup log / `/api/ps` / ssh); `ollama_steward/fit.py::plan` with the options
  `windows · one-at-a-time · other-host · twin · smaller-quant · kv-q8_0`; `models_library/shapes.py::KNOWN`
  gives pre-install fit badges.
- **server log:** `ollama_steward/server_log.py` (tail, rotation, journald fallback);
  `server_rules.py::classify` already parses `prompt-trimmed` (and computes the window from `limit/prompt/keep`),
  `reply-cut`, `window-full`, `cpu-spill`, `gpu-memory`, `slow-load`, `load-failed`, 499/500/503.
- **hosts:** `providers/ollama_discover.py::discover("local"|"lan"|"all")` — `/24` sweep, `halo ollama discover`.
- **switching:** `agent/model_switch.py::run_switch` + `SwitchReport`, `model_card_switch.py`,
  `model_switch_child.py::fit_child_prompt`, `ollama_steward/ledger_switch.py`.
- **roles/lineups:** `ol:<model>@<host>` and `hf:local/…` in role tables; `templates/teams/local-first.yaml`;
  `roles.py::vram_aware_override` (`fits_beside_main`, for small/researcher/judge/subagent_default).
- **acceptance:** `doctor_local.py` (`halo doctor --local`).
- **note:** a stale 2.0.x clone sits at `~/Documents\vibes\appDev\Halo-Harness` — read the live
  repo (`~/Halo-Harness`) only.

**D1 — the orchestration cluster (the big one): different local models per agent, switched in when needed.**
The pieces exist; nothing *schedules* them.

1. **Pivot scheduler** (ROADMAP 3.3.5.0 R6 plans it): one resident local model per card; when a lane needs a
   different one, unload → load is a first-class, visible step ("pivot: coder → reasoner, 25 s, fits history
   to the new window") — `model_switch_child.fit_child_prompt` already fits a child's first request.
2. **Warm policy:** `keep_alive` exists per `host|model` profile but nothing decides it for a session. Add a
   per-card warm set (models that co-reside) and pre-warm at session start (`halo local warm`) — the
   cold-load item from the 2026-10-07 notes.
3. **Switch cost in the plan:** `fit.py` already knows `load_ms` from the ledger but `model_switch.plan` never
   reads it. Surface it, plus a run-level preview: *"this lineup swaps 7× on one card ≈ 3 min of loading"*
   (the single-GPU swap tension, ROADMAP ~487).
4. **Local→local escalation:** `escalation.py` is local→cloud only. Add a speciality hop (small local →
   bigger local) under the same `low_confidence` / `tool_failures` / `context_overflow` triggers, so
   "switch when needed" stays offline.
5. **Spawn-time fit verdict:** extend `vram_aware_override` past its four roles; before a child spawns on a
   different local model, state whether it fits beside main, what it evicts, and the swap time — as the
   child's first event.
6. **Per-role local profiles:** the profile key is `host|model`; allow `host|model|role` so a lane can carry
   its own window / keep_alive / tools_max.
7. **Auto pick with fit + warm state:** `models_auto.pick` weighs cost/index; add "fits on this card /
   already warm / needs a swap" so Auto cannot pick a thrashing model.
8. **Lineup hygiene at `teams use`:** flag verify+worker sharing weights, and warn about swap cost when they
   do not (ROADMAP ~484-490).

**D2 — prompt-side fit (what actually broke on 2026-10-29).**

9. **Preflight as a decision, not a silent edit:** `prepare_window` compacts when over the ceiling; instead
   say *"prompt 30,756 · window 32,768 · usable 16,386 → will truncate"* with [bigger-window model] [compact]
   [send anyway].
10. **Truncation direction:** Ollama keeps `n_keep = 4` from the **start** plus the **tail**, so a task
    summary at the front is what dies. Order the payload for survival (task last) or refuse to send.
11. **Halo's own footprint:** dedupe the auto-memory block (it appeared **twice**, 87 % of a 26 k-token
    message) and show a composition view (system / tools / memory / history) with token counts; add a lean
    local-model profile (trim the topic index, cap tool schemas).
12. **Size compaction to the window** rather than a fixed template.

**D3 — logs and diagnostics.**

13. **Remote logs:** `server_log.py` refuses a remote host ("the server log of X is on that machine") while
    `hardware.py` already supports `ssh:` hosts — wire that path (this is exactly what blocked the diagnosis
    here; the workaround was a local proxy on the host's own port).
14. **Close the loop:** `trim_recovery` reacts to reply counts, never to the log's own `prompt-trimmed` /
    `cpu-spill` events — let the log drive recovery.
15. **Crash forensics:** on `llama-server terminated`, capture the load command plus the signature
    (`CUDA error` / exit `0xc0000409` / `splits > 2` / FA + q8_0 KV) and file one plain-language entry.
16. **Verify logging is live** per host and offer a short `OLLAMA_DEBUG=1` window; request bodies still need
    the proxy recipe in Part C.

**D4 — catalog and metadata.**

17. **Measured model cards:** tok/s, TTFT, tool-call accuracy, window *verified vs assumed*, KV/token,
    modality, spec-decode on/off, and quirks ("ignores system prompts", "answers in `thinking`"). Today only a
    cached `tool_calls` probe exists per digest; the gym's speed card is still roadmap-only.
18. **Raw tag vs fitted variant:** mark them apart, offer one-click "delete the raw tag, keep the variant",
    and warn at pull time when weights can never fit ("23 GB on a 23 GB card — it will always spill").
19. **Doctor:** resolve every role's model id (the 2026-10-07 dead-id bug) and flag **Ollama version drift**
    per host — this PC sat on 0.40.6 with 0.40.13 staged for a day, and the staged update was the crash fix.

**D5 — hosts and the multi-machine reality.**

20. **Host card:** GPU + total/usable VRAM, driver, Ollama version, log path + readable?, loaded model,
    `other_users` — `hardware_card` already gathers most of it; surface it.
21. **Traffic view including foreign clients** (the Kali agent asking this box for a 128 k window) so
    contention is visible before it hurts.

**D6 — intuitiveness.**

22. One decision per panel; plain language on screen ("fits", "spills to CPU (slow)", "too big") with numbers
    behind `?`; every suggestion a button that states what it does, costs, writes and how long; and
    revert-on-session-end for any tuning Halo applies (keep_alive, ctx, env, pinned model).

### Part E — every local model gets a capability & placement profile (part of fit / setup)

**The problem it solves:** today a user can point any local model at any role and only finds out it was the
wrong tool after a bad answer. Three real cases from this box:

- `mythos-sec:24b-gpu` **cannot emit a tool call at all** — with a schema attached it generated 34 tokens and
  returned empty content and no `tool_calls`. It must never be a tool-using sub-agent.
- `qwen3.6-abliterated:27b-q4-gpu` answers in `message.thinking`, so a small `num_predict` makes its `content`
  look empty — a "failure" that is really a budget problem.
- `mythos-sec` (13.4 GB) and `qwen3-coder` (17.3 GB) **cannot co-reside** (30.7 GB vs 20.6 GB usable), so any
  lineup naming both is really asking for a pivot.

**E1 — the battery (run during fit/setup, cache the result).**
Six one-shot probes, ~8 requests per model, a couple of minutes, no cost. Cache next to the existing
capability cache (`providers/ollama_capability`) keyed by **model digest + Ollama version + probe-set version**
so it re-runs when any of them changes. Reference implementation already written and running:
`~/ollama-watch\capability_battery.py`.

| probe | what it sends | what it proves |
|---|---|---|
| tools | one function schema, "use the tool" | can this model be a sub-agent at all? |
| system role | system "reply exactly BANANA" | may instructions live in the system prompt? |
| user instruction | the same demand in the user turn | does it obey meta-constraints? |
| structured output | a schema'd triage request | valid JSON? fenced? right keys? |
| reference fidelity | one factual identifier | can its IDs be trusted? |
| reasoning split | any probe returning `thinking` | answers land in `thinking`, not `content` |
| speed | `eval_count / eval_duration` from the structured probe | measured tok/s on this host |
| fit | `fit.py` + `/api/ps` (`size_vram == size`) | window, KV/token, co-reside vs pivot |

**E2 — what the profile records, per model per host:** `tools: yes|no` (probed, never inferred from the family) ·
`system_role: honoured|weak` · `instruction: task-shaped|strict` · `output: json|fenced-json|prose` ·
`identifiers: trusted|unverified` · `reasoning: none|thinking` · `window: trained vs usable (verified)` ·
`kv_per_token` · `size_gb` · `speed tok/s` + `ttft` · `resident: co-resides-with X | pivot-only` ·
**`interactive: yes|no` — is it even worth talking to directly?** (needs system role honoured + instruction
following) · `quirks: []` (free text the user sees: "ignores system prompts", "answers in thinking",
"invents CWE ids", "first request after load pays ~10 s").

**E3 — placement rules (apply automatically, show as a verdict).**

- **no tools → never a tool-using sub-agent.** Allowed: `compaction`, `bulk`/`small` single-shot steps, and any
  explicit non-agentic step. This is the most important gate — today nothing checks it at spawn.
- **system role weak →** move the instruction into the user turn automatically, and say so.
- **thinking →** raise that model's reply reserve (small budgets return empty `content` and look like failure).
- **fenced json →** strip fences in the wire conversion before parsing.
- **identifiers unverified →** never let it emit authoritative IDs (CVE/CWE/hash); resolve with a tool or a
  stronger model.
- **32 k window →** chunk inputs; never give it a role that receives whole sessions.
- **pivot-only →** it cannot share the card; a lineup naming it plus another big model is a pivot schedule and
  the preview must say so.
- **interactive: no →** do not offer it as a chat/`/model` target; show it as a step model.

**E4 — the Local tab (and the fit/setup flow) must show it, in plain language.**
Per model card: **Use it for** (2-4 lines from the profile) · **Don't use it for** · **Where it sits** (a
placement chip: `bulk worker · non-agentic`, `compactor`, `coder`, `reasoner`, `pivot-only`, `not interactive`)
· **Limits** (window trained vs usable, size, co-reside/pivot, measured tok/s, cold-load time) · the fit badge
from Parts A/C.

**E5 — when it fails, say why and what to do instead.** Halo should never show a raw error.

| what the user sees | what Halo should say |
|---|---|
| empty reply, no tool call, model "did nothing" | "no tool calling on this model (probed <date>) — it can't run agentic steps; use it for single-shot extraction, or route this step to <model with tools>" |
| reply cut / truncation in the log | "prompt N tok exceeded the window M (usable M/2) and the task summary was dropped — compact, or use <65 k model>" |
| empty `content` on a reasoning model | "it answered in `thinking`; the reply budget was too small — retry with ≥300 tokens" |
| slow first answer | "cold load of 17 GB, ~25 s — pin it (`keep_alive -1`) or pre-warm" |
| CPU spill (`splits > 2`, `size_vram < size`) | "it didn't fit (59/66 layers on GPU) — lower the window to <n> or use <smaller model>" |
| an invented identifier | "its reference IDs are unverified — resolve with a tool or <model>" |
| a swap every turn | "two models can't co-reside on this card — make one resident and pivot explicitly" |

**E6 — wire it into what exists (reuse, do not add parallel machinery):** the probe result belongs in
`providers/ollama_capability` (it already caches a tool-calls probe per digest); the placement rules belong in
`roles.py` and `models_auto.pick` (so Auto stops picking non-tool models for tool roles); the failure mapping
belongs in `server_rules.classify` plus the loop's error path; the card belongs in `models_library` and the
Local tab; `doctor_local.py` should fail a role assignment whose model lacks the required capability.

**Acceptance:** for every installed model, Halo can answer "what is this good for, what must I not use it for,
where does it go, and what are its limits" — and when it fails in a role it says why and names a better use or
model, without the user reading a log.

**E7 — the battery run on this box (2026-10-29, `capability_battery.py`, Ollama 0.40.13, RTX 4090).**
`json` = the schema'd triage request produced parseable JSON with all four keys; a `no` may mean prose or
wrong keys, so the real battery must record *why* (invalid / keys / prose) to drive the repair loop.

| model | tools | system role | meta-instr | json | fence | thinking | tok/s | ref-id |
|---|---|---|---|---|---|---|---|---|
| `qwen3-coder:30b-gpu` | **yes** | **yes** | **yes** | **yes** | no | no | 187.3 | 285 (close) |
| `mythos-sec:24b-gpu` | **no** | **no** | **no** | yes | **yes** | no | **297.5** | CWE-20 (wrong) |
| `qwen3.8:27b-gpu` | yes | yes | no | **no** | no | **yes** | 96.0 | **284 ✓** |
| `qwen3.8-obliterated:27b-q4-gpu` | yes | yes | no | yes | no | **yes** | 47.0 | **284 ✓** |
| `bugtrace:latest` | yes | **no** | no | yes | no | **yes** | 49.8 | 601 (wrong) |
| `qwen3.6-abliterated:27b-q4-gpu` | yes | **no** | no | **no** | no | **yes** | 47.0 | none |

Cross-model lessons (these are the rules the Local tab should teach):

- **Only 1 of 6 models passed all four behavioural gates** (`qwen3-coder`). It is the only one that can safely
  hold a full tool-using agent role; every other model needs a gated role or a single-shot step.
- **3 of 6 ignore the `system` role** (mythos, bugtrace, qwen3.6-abliterated) — so "put the instruction in the
  user turn" should be the default for local models, not a fallback.
- **5 of 6 ignore meta-constraints** ("reply with exactly one word: BANANA") — never ask a local model for a
  strict format without a repair loop or a post-parse check.
- **4 of 6 are reasoning models** — their answers arrive in `message.thinking`, so an empty `content` usually
  means "reply budget too small", not failure.
- **4 of 6 got a plain reference identifier wrong** — never let a local model emit authoritative CVE/CWE/hash
  IDs; resolve them with a tool or a stronger model.
- **Speed spans 6.3×** (47 → 297 tok/s) — send bulk/mechanical passes to the fast end (mythos) and keep the
  27B reasoners for judgement.

Placement verdicts that fall straight out of the table:

- `qwen3-coder:30b-gpu` — **full agent.** Coding, tool-using sub-agent roles, anything needing format
  obedience. Keep it resident.
- `mythos-sec:24b-gpu` — **bulk worker, non-agentic, not interactive.** Extraction, classification,
  compression, shortlisting. Fastest model on the box; pivot-only.
- `qwen3.8:27b-gpu` — **reasoner** (planning/review/judge) with a JSON repair loop; good IDs, ignores
  meta-constraints.
- `qwen3.8-obliterated:27b-q4-gpu` — the most obedient 27B: tools + system role + JSON + good IDs → **reasoner
  where structured output matters.**
- `bugtrace:latest` — **agentic security work through the user turn** (what Kali already does); do not trust
  its IDs.
- `qwen3.6-abliterated:27b-q4-gpu` — exploratory/uncensored **single-shot reasoning**; needs a JSON repair
  loop and the user turn.

### Part F — the Local tab's capability-filtered model search (browse Ollama + Hugging Face)

Goal: before downloading anything, the user picks the **capabilities** they need and the **resources** they
have, and Halo returns a short, explained, ranked list — where every row says what it costs and whether the
capability is *known* or merely *expected*.

**F1 — the core idea: two kinds of truth, never blurred.**
A model's card tells you its *declared* facts (architecture, params, quant, modality, context, licence). The
battery (Part E) tells you its *probed* behaviour on this machine. Only the second is trustworthy for role
placement — `mythos-sec:24b-gpu` fits the card perfectly and cannot emit a tool call. So every filter and every
result row carries one of three states:

- **declared** — read from metadata (cheap, available pre-download, sometimes wrong),
- **expected** — inferred from family/size/tags (heuristic, say so),
- **verified** — probed on this host (the only one that may gate a role).

**F2 — the filters.**

*Role & capability* (the ones asked for, plus the rest):

| filter | means | known pre-download from | verified by |
|---|---|---|---|
| `tools` | emits native tool calls | family + chat template + HF tags | battery probe |
| `thinking` / reasoning | answers in `thinking` | family, tags, GGUF metadata | battery probe |
| `coder` | code-specialised | name/family/tags (`coder`, `code-`) | a code probe |
| **`agentic-ready`** | **tools + system role + instruction + JSON, all four** | nothing reliable | the battery (today: 1 of 6 models passed) |
| `planner` / `orchestrator` | long window + instruction + JSON | size/family heuristics | battery |
| `verifier` / `judge` | reasoning + trustworthy reference IDs | nothing reliable | battery |
| `compactor` | long input → short output | window + speed | a compression probe |
| `bulk` | fast, high volume, single-shot | params/arch, measured tok/s | speed probe |
| `abliterated` / uncensored | not safety-tuned | HF tags, model name | a refusal probe |
| `vision` | image input | mmproj/projector present, tags | a vision probe |
| `audio` | speech in/out | tags, architecture | a probe |
| `embedding` / `reranker` | vectors, cross-encoder | architecture + dims | dims probe |
| `security` / `pentest` | security-flavoured | tags (weak signal — say so) | a task probe |
| `math`, `multilingual` | domain-trained | tags, card | a probe |
| `long-context recall` | actually *remembers* at N | claimed context only | a needle probe (claimed ≠ real) |
| `tool-call accuracy` | multiple tools, correct args | nothing | a multi-tool probe |

*Fit & resources* (evaluated against the selected host, live):

| filter | means | how |
|---|---|---|
| `fits at window N` | weights + KV(N) + overhead ≤ usable VRAM | `shapes.py::KNOWN` + quant + card; verified by load (`size_vram == size`) |
| `fully on GPU` | no CPU spill | log `splits = 2` |
| `co-resides with <model>` | two models fit together | computed; verified via `/api/ps` |
| `quant ≤ X` | Q4/Q5/Q6/Q8 ceiling | file metadata |
| `params ≤ N B`, `disk ≤ N GB` | size ceilings | metadata |
| `speed floor ≥ X tok/s` | measured on this box | estimated from params×arch pre-download, then measured |
| `cold-load ≤ N s` | size ÷ disk speed | computed, then measured |
| `KV efficiency` | KV per token per GB — mythos ≈ 10 KB/token vs the coder's 48 KB | shape metadata |

*Supply, licence, platform:*

`licence` (Apache/MIT vs research-only vs unknown — matters for anything shippable) · `gated on HF` ·
`source` (Ollama library / HF GGUF / HF safetensors / MLX) · `runs on this OS+GPU` (MLX = Apple only,
CUDA = NVIDIA, ROCm/Vulkan = AMD) · `supported by this Ollama version` (a brand-new architecture may not load)
· `freshness` (updated within N months) · `verified by the gym` · **`exclude: crashed on this host`** — the
server log already knows which models died and with what signature (Part C), so Halo can grey those out with a
reason instead of letting the user rediscover it.

**F3 — presets first, checkboxes second.** Nobody wants a wall of filters, so the tab opens with role buttons
that expand into the filter bundle: **Coder · Reasoner/planner · Bulk worker · Compactor · Verifier ·
Security/pentest · Multimodal · Embeddings · Offline-only**. Each preset is inspectable and **saveable as a
role template**, which closes the loop with the per-role local profiles in Part D.

**F4 — the inverse flow: "find a model for this role".** From a lineup gap ("your `verify` role has no model")
or a plain sentence ("I need a local coder that can use tools"), Halo ranks candidates by: passes the role's
gates → fits at the chosen window → measured speed → download size → licence. One button: **download and
verify** (pull, run the battery, write the profile, offer to assign the role).

**F5 — every result row explains itself.** Name, source, params/quant, **fit badge at the chosen window**, and
the two verdicts side by side: `fits: yes · role-ready: no (no tool calls)`. Plus a cost preview — download
size and estimated time, VRAM at the chosen window, cold-load time, expected tok/s, and which resident model it
would evict. Expected-vs-verified is labelled per capability, so nothing is promised that hasn't been probed.

**F6 — the resource strip stays visible.** Host, GPU, usable/free VRAM, disk free, resident model — and every
filter re-evaluates against it live ("fits at 32,768 with 2.8 GB free").

**F7 — wire it into what exists.** `models_library/browse.py` already carries
`CAPS = ("tools","vision","embedding","thinking","audio")` and `models_library/shapes.py::KNOWN` already gives
pre-install fit shapes — extend both rather than adding new machinery; the verified half comes from the Part E
cache (`providers/ollama_capability`), and `doctor_local.py` can check that a model actually delivered the
capability it was chosen for.

**Acceptance:** a user can ask "find me a local coder that fits my card and can use tools" and get a short,
ranked, explained list where every row states its cost and distinguishes expected from verified — and nothing
downloads until they press the button.

### Part G — fifteen more, from the deep dive

**Talking to it right**

1. **A per-model dialect record, applied automatically.** Part E gates *where* a model goes; this is the twin —
   *how Halo addresses it*: instruction placement (user turn for the 3 of 6 that ignore `system`), fence
   stripping, reply reserve, JSON repair loop, stop-token quirks, "tends to loop". Stored with the profile,
   user-visible and editable ("how Halo talks to this model").
2. **Prompt-cache awareness.** Ollama reuses the KV prefix when the front of the prompt is stable, so tool and
   memory order must not shuffle between turns. And the log says which models cannot cache at all — mythos logs
   *"forcing full prompt re-processing due to lack of cache data (likely due to SWA or hybrid/recurrent
   memory)"*, i.e. every turn re-reads the whole prompt. Show "cache reused: N %" per call and warn on hybrids.
3. **Tool-schema budget per model.** Halo's tool catalog is part of the ~3.6 k system prompt; a 32 k model
   cannot hold the long tail. Choose which tools to expose from the model's profile and window (`tools_max`
   already exists in the switch report — make it capability-driven). This is what makes small-window models
   usable as agents at all.
4. **Warm-up truth.** The first request after a load is ~10 s of graph capture (measured: 5.7 tok/s, then
   199 tok/s steady). Never benchmark or report latency on the first call; warm silently and label it "warming".

**Making the cost visible**

5. **A loading tax in the cost meter.** Cloud cost is dollars; local cost is *seconds of loading plus VRAM
   contention*. This box did 93 loads in a day (84 in one hour) at 20-55 s each — roughly an hour of pure
   loading, invisible in every UI. Track it per session and per lineup, beside the existing "saved vs cloud"
   meter.
6. **A warm-set planner (bin packing).** Instead of "one model at a time", compute what can live together:
   coder 17.3 GB + a 1.5 B helper ≈ 19 GB fits; any 27 B means a pivot. Show a small budget view; let a lineup
   declare its warm set.
7. **The KV-quantisation dial.** q8_0 KV is what let 32 k fit here. Surface the trade per model — "f16 KV →
   32 k, q8_0 KV → 64 k on this card" — with the quality caveat *and* the crash note, since FA + q8_0 V was
   implicated in the four crashes of 2026-10-29.
8. **A model shelf with retirement.** Seven tags and 21 GB were freed here by hand. Show last-used, disk cost,
   whether any role ever picked it, and one-click "retire" that leaves a note so re-pull is trivial.

**Explaining outcomes**

9. **An "answer post-mortem" button.** Not only crashes — *quality* failures. One click reconstructs what the
   model actually saw: truncated? memory-dominated? thinking-only? no tools? empty content from a small budget?
   Every piece exists (log + payload capture + profile); it should be one line, not a log hunt.
10. **An explicit degradation ladder.** repair loop → smaller ask (fewer tools, shorter prompt) → a different
    local model → cloud if allowed → ask the user. Each rung visible as one line, so local models feel reliable
    rather than brittle.
11. **Failure fingerprints shared across the fleet.** Store the fingerprint (family + flags + signature:
    `FA + q8_0 KV + spill → CUDA IMA`) so the Mac and Kali recognise a known failure instantly instead of
    re-diagnosing. The knowledge base exists; it needs the fingerprint form.

**Across machines and time**

12. **A placement solver across the fleet.** With a 4090, SAMUS's 10 GB 3080, the Mac (MLX) and Kali, decide
    *where* each role's model runs — coder on the PC, compactor on SAMUS, embeddings on the Mac — instead of
    piling everything on one card. The multi-host form of the pivot scheduler; the roadmap already flags the
    research item.
13. **Off-hours gym refresh.** The 4090 idles at 92 MB most of the day. Run the capability battery and
    benchmarks when the card is free, never during a session, and stamp each model "verified <date>" so
    profiles stay trustworthy with no user effort.
14. **Drift and deletion guards.** Tags are mutable and disposable: detect when a tag's digest changes
    (invalidate profile, window truth, benchmarks) and when a role points at a deleted tag ("`qwen3.8:27b` was
    deleted — nearest equivalent `qwen3.8:27b-gpu`"). The 2026-10-07 dead-model-id bug is the same class, and
    the cleanup on 2026-10-29 created exactly this risk.
15. **An offline-promise badge.** A session badge "100 % local — 0 tokens left this machine", with a per-call
    line naming the host it went to. The honest form of the enforced-offline mode already on the roadmap.

### Part H — the model-host agent: the abilities travel, the models stay put

**The problem (all observed on 2026-10-29):** everything useful lives on the *host*, not on the machine you are
sitting at. `server_log.py` explicitly refuses a remote host ("the server log of X is on that machine, not this
one"); fit needs `nvidia-smi` and `/api/ps` *there*; warm/pin/pivot/keep_alive are host-side actions; the
capability battery is only meaningful where the GPU is. Working from the Mac, the only route to any of it was
ssh plus a hand-rolled logging proxy — and the Mac's Halo had no idea its prompts were being halved or that the
PC was thrashing.

**The idea: `halo agent` — a headless model-host service.** A small always-on process on every machine that
hosts models (the PC, SAMUS, the Mac, Kali), bound to the LAN only. It is not a full Halo session: no TUI, no
orchestration. It answers peers, watches its own host, and holds the host-side state. The steward gets a body.

**What it serves (one small JSON API, LAN-only):**

- **host card** — GPUs, total/usable/free VRAM, driver, Ollama version, disk free, resident model + keep_alive,
  other clients and what they asked for.
- **catalog + fit** — the host's models with a fit verdict for any requested window, computed from the host's
  own measured budget rather than guessed.
- **capability profiles** — the Part E battery results, verified *on that host*, with digest and date.
- **probe on demand** — "run the battery on model X" so a peer without the GPU can still get a verified
  profile.
- **log access** — the classified events (`prompt-trimmed`, `cpu-spill`, `load-failed`, crash signatures) plus
  a bounded tail, so a remote Halo can diagnose without ssh. Prompt *sizes* yes; prompt *content* no, by default.
- **live events** — subscribe to what the host is doing (the `watch.ps1` alerts.log is the primitive version).
- **control, opt-in per peer** — warm/pin, unload, pivot (unload A → load B), pull/delete, set keep_alive.
- **fit simulation** — "would this model fit here if I pulled it?" answered against the real budget.
- **routing answer** — "can you run a 27 B at 64 k right now?" so a client can place work across the fleet
  (Part G #12's data source).

**Control and security:** read-only until a peer is explicitly granted control (`fleet.allow_control`,
`served_here` already model this); per-peer tokens; LAN bind only, no cloud relay; an audit line per request
(which is also the offline-promise evidence for Part G #15).

**Fallback ladder when no agent is installed:** direct Ollama API (`/api/tags`, `/api/show`, `/api/ps`) → ssh
(`hardware_card` already supports `ssh:` hosts) → agent. The agent is the upgrade, not a new dependency.

**The principle it establishes:** anything that needs the GPU, the log or the disk lives **on the host**, in the
agent — the battery (Part E), the off-hours gym (G13), the warm policy and pivots (Part D1/R6), the log watch
(Part C). The client Halo just asks. That is also what makes the same abilities work from a laptop that has no
GPU at all.

**Wire it into what exists:** this is a promotion, not a new stack — `fleet/hub.py`, `fleet/hub_http.py`,
`fleet/capabilities_host.py`, `fleet/control_models.py` and `fleet/ollama_share.py` already carry most of the
plumbing, and the 3.3.4.0 steward is the brain. What is missing is a *headless* entry point that runs with no
Halo session on that machine, the log/probe endpoints, and the peer-grant model.

**Acceptance:** from the Mac or Kali — no GPU, no ssh — Halo can list the PC's models with fit verdicts and
verified capability profiles, explain why the last answer was truncated or slow by reading the PC's own log,
keep the right model warm, and place a task on whichever host actually fits it.

**H9 — does the agent need its own model?**

Decision: **split by fact vs judgement. The agent computes; the client's model explains; the host keeps a small
model only as an optional narrator.**

- **Facts and mechanics — no model, ever.** Host card, fit arithmetic, window truth, the capability battery,
  log classification (`server_rules.classify` already does it), warm/pin/pivot, drift detection, placement
  arithmetic. These are *computed*, not asked. Evidence from this session: the KV arithmetic
  (48 × 256 × 4 × 1 = 49,152 B/token) matched the server's own `CUDA0 KV buffer size = 1632.00 MiB` exactly —
  putting a model in that path could only add error.
- **Judgement and prose — the client's model, by default.** The agent returns **structured findings** (event +
  evidence + suggested actions), e.g. `{"event":"prompt-trimmed","prompt":41104,"limit":16386,
  "suggest":["compact","use a 64k model"]}`. The client Halo renders it, because it has the session context and
  knows what the user was doing — its explanation will beat the agent's. Requests carry `explain: true|false`.
- **A small model on the host — optional, evictable, two jobs only:** narration when no capable client is
  attached (a plain curl, a phone, a harness with no model), and summarising the agent's own background work
  ("re-verified 4 models overnight; mythos dropped to 240 tok/s after the driver update"). Opt-in, 1.5-3 B,
  unloaded the moment the card is needed.
- **Bootstrapping rule:** the agent must work with **zero models available** (fresh host, nothing pulled), so a
  model is an enhancement, never a dependency — the same shape as the fallback ladder.
- **Never** let a model answer "which model should I use" or "does this fit" — those are arithmetic plus the
  battery; a model turns them into opinions.
- **Honesty about its own footprint:** if the agent does keep a helper resident it must subtract it from the
  budget it reports, or report both ("20.6 GB usable; 18.6 GB with my 2 GB helper"). Today's surprise — a model
  that fit on paper and then spilled — is exactly what that line prevents.
- **Boundary inherited from the steward:** the agent adjusts *Halo's* side only; it never rewrites the host's
  Ollama configuration, and control stays opt-in per peer.

**H10 — the fix loop: the host senses and applies, the steward decides, the outcome is verified or reverted.**

Rolo's refinement (2026-10-29): the steward — the model-backed role that exists to keep local LLMs working
well — lives *in the harness* and works *with* the host agent, and the host agent must be able to **apply the
fixes the steward sends it**. So the host agent is not a viewer: it is **eyes and hands**. Three roles, one loop:

```
host agent (no model)            steward (a model)                 harness (the user)
  sense  ──findings──▶   decide ──fix request──▶  apply ──▶ verify ──▶ keep | revert
  act    ◀──────────────  (evidence cited)                      report + explain
```

**H10.1 — the contract is a typed fix vocabulary, not a shell.** The steward sends *named operations* with
parameters, never command lines:

- `view` (default grant): host card, catalog + fit, profiles, log events, live subscription, probe on demand.
- `control`: `warm`/`pin` (`keep_alive`), `unload`, `pivot` (unload A → load B), `set_num_ctx`,
  `set_kv_cache_type`, `set_flash_attn`, `rerun_battery`.
- `manage`: `pull`, `delete`, `retire`, `restart_ollama`, `set_env`, `revert <change-id>`.
- `admin`: a raw command capability — available, but an *explicit per-peer grant*, never the default.

This is not a permission classifier: it is the interface, and every operation is previewable, revertible and
auditable. A typed vocabulary is what makes a model-driven fixer trustworthy — you can read the audit trail of
what it changed and undo it.

**H10.2 — every fix carries its evidence.** The steward must cite the finding it is acting on:
*"lowering `num_ctx` to 32,768 because the log says `limit=16386 prompt=41104`"*. Findings are structured
(H9), so this is cheap, and it makes a hallucinating steward visible instead of destructive.

**H10.3 — apply, measure, keep or revert.** The agent applies the fix, re-reads the host (load line, `size_vram`,
`splits`, tok/s) and reports the before/after. If the metric did not improve, it **auto-reverts** and says so.
That is the safety net — undo, not paternalism — and it is the existing "verified outcomes" pattern applied to
the host. Guards that are mechanics, not policy: one change at a time per host, a cooldown between changes, and
a rate limit, so a model in a loop cannot thrash the card the way it did on 2026-10-29 (93 loads in a day).

**H10.4 — some fixes belong on the client, not the host.** A truncated prompt cannot be fixed by the host: the
fix is *compact the session* or *use a 64 k model*, which the harness applies. So the fix protocol runs in both
directions — host-side fixes the agent applies, client-side fixes the agent *requests* and the harness performs.
The steward decides; the fix lands wherever it belongs.

**H10.5 — the steward has three homes, one vocabulary.** (a) a strong/cloud model inside a harness (best
judgement), (b) a cheap local model inside a harness (offline, slower thinking), (c) a small model resident on
the host agent itself — the H9 narrator promoted to a *duty steward* that closes the loop when nobody is
attached. Same role, same fix vocabulary, chosen by policy.

**H10.6 — invariants stay deterministic.** The agent enforces the mechanical ones with no model at all: never
load a model that does not fit, keep exactly one resident per card, honour `keep_alive`, subtract its own
footprint from the budget it reports, refuse a fix that would breach the card. Judgement and novel situations go
to the steward; arithmetic and policy-free mechanics never do.

**H10.7 — naming, so "which agent?" never comes up.** The headless service is **the host** (`halo host`); the
model-backed role is **the steward**. "Agent" then means a Halo sub-agent and nothing else.

**H10.8 — acceptance:** unplug the steward and the host still serves, senses and enforces its invariants; plug
the steward in and it can, from any machine on the LAN, see a spill, send `set_num_ctx 32768`, watch the agent
verify 16 → 188 tok/s, keep the change, and write one line of audit that names the finding it acted on.

**H10.9 — what the host is, and is not (confirmed by rolo, 2026-10-29).**

The host is **an in-depth monitor that informs the harness**. It is *not* a separate agent living outside Halo
Harness. Precisely:

- **Not an agent.** No model (H9), no goals, no self-directed work, no conversation. It has no opinion.
- **Not outside Halo.** It is a Halo component — installed, configured and updated by Halo (`halo host install`
  / `halo host status`), running as `halo host`. It is not a random program you start by hand, and it talks only
  to Halo peers on the LAN (no cloud, no relay, no third party).
- **Not autonomous by default.** Its default state is *monitor*: findings accumulate and are handed to the next
  harness that connects. It acts only on a typed request from a harness or steward (H10.1) — plus its own
  deterministic invariants (H10.6), which are mechanics with no judgement in them.
- **The one deliberate exception** is the optional duty steward (H10.5c): a small model resident on the host that
  closes the loop when nobody is attached. That is an **explicit opt-in, off by default**.
- **Strictly-monitor mode stays available:** with the `control` and `manage` grants disabled and the duty steward
  off, the host only senses and enforces its invariants — everything else waits for a harness to ask.
- **No model is ever *in* the host agent — not even with the duty steward enabled.** The duty steward is a
  separate, opt-in process that uses the host's Ollama like any other client; the monitor itself stays
  model-free. The thinking always happens in a **Halo sub-agent** (a role with a model card — the steward), which
  reads the host's findings and drives the host when needed.

### Part I — glossary: the field names Parts E and F use, in plain terms

**Battery columns (Part E1)**

- **`tools`** — can it call tools? One function definition is attached and the model is asked to use it. Without
  this a model can never be a Halo sub-agent (sub-agents act by calling tools); it can only do single-shot
  text-in/text-out work. *Measured: 5 of 6 can; `mythos-sec` cannot.*
- **`sysrole`** — does it respect the `system` message? Halo keeps its instructions, rules and persona there, so
  a model that ignores it quietly loses its instructions. *Measured: 3 of 6 honoured it; `mythos-sec`,
  `bugtrace` and `qwen3.6-abliterated` did not.*
- **`instr`** — does it obey a formatting demand ("answer in one word", "no prose", "just the code")? This is a
  *strictness* measure, not a quality score: the probe is a deliberately silly demand, so failing it means "weak
  at strict format obedience". *Measured: only `qwen3-coder` obeyed.*
- **`json`** — can it produce parseable structured output with the exact keys asked for? Mechanical workflow
  steps (extraction, classification) are consumed by code, so malformed JSON breaks the pipeline. *Measured: 4 of
  6; `qwen3.8:27b` and `qwen3.6-abliterated` wrote prose instead.*
- **`fence`** — does it wrap the JSON in a ```json code fence? Not a failure, a parsing chore: the caller must
  strip the fence. *Measured: only `mythos-sec` fenced.*
- **`think`** — is it a reasoning model that writes its chain of thought into a separate `thinking` field? With a
  small output budget all the tokens go to thinking and `content` returns **empty**, which looks like a broken
  model but is a budget problem. *Measured: 4 of 6 are reasoning models.*
- **`tok/s`** — generation speed (tokens ÷ generation time), per machine. Decides what can be a bulk worker.
  *Measured: `mythos-sec` 297, coder 187, `qwen3.8` 96, the 27B denses ~47-50.*
- **reference fidelity** — asked for the CWE number of "improper access control" (correct: 284). If a workflow
  emits identifiers other systems trust (CVE, CWE, hashes, ports), a hallucinated ID is worse than no answer.
  *Measured: only the two `qwen3.8` variants were right.*

**Derived labels (Parts E3, F2)**

- **`agentic-ready`** — the composite gate: tools **and** system role **and** instruction **and** JSON. Answers
  "can this hold a tool-using role at all?" *Measured: only `qwen3-coder`.*
- **`interactive`** — worth talking to directly (chat, `/model`)? Needs system role + instruction following +
  tolerable speed.
- **`pivot-only` vs `co-reside`** — can it stay loaded beside another model, or does it need the card to itself
  (weights + KV vs usable VRAM)? If two cannot co-reside, using both means a **pivot**: unload one, load the
  other, 20-55 s on this box.
- **`window: trained vs usable`** — the context the model was trained for versus the largest window that actually
  fits the GPU. More than fits = spill; more than trained = degraded answers.
- **`KV per token`** — the memory each token of context costs; the difference between holding 64 k and not.
  `mythos-sec` ≈ 10 KB/token, the coder ≈ 48 KB/token.
- **`spill` / `fit`** — does it load entirely on the GPU, or push layers/KV into system RAM? Spill is 5-10×
  slower and was the crash configuration on 2026-10-29. Detected via `size_vram == size` (`/api/ps`) and `splits`
  (the log).

**Architecture words that are not tests**

- **MoE (mixture of experts)** — only a fraction of the network runs per token, so it is much faster and cheaper
  than its parameter count suggests (`mythos-sec` and the coder are both MoE).
- **Hybrid attention** — attention on only some layers (`mythos-sec`: every third), which is why its KV is ~5×
  cheaper per token.
- **Abliterated / uncensored** — refusal behaviour fine-tuned away; matters for security work where a normal
  model balks.
- **MTP / speculative decoding** — the model carries a small head that drafts its own next tokens for speed
  (`qwen3.8` has it; also implicated in the 2026-10-29 crashes).
- **Context window / `num_ctx`** — how many tokens of conversation plus reply the model can hold at once. Ollama
  reserves part of it for the reply and truncates an over-window prompt to half the window, keeping the first 4
  tokens plus the tail (Part B).
- **`keep_alive`** — how long a loaded model stays in VRAM after its last request (`-1` = pinned forever).
- **`pivot`** — unload model A and load model B on a card that cannot hold both.

### Part J — Halo should recommend what a user could use (the roster adviser)

Halo reviews the installed roster against the roles, the host budget and the capability profiles, then tells the
user what is missing, what overlaps and what to add or retire — in plain language, with the numbers, and with a
one-click add. (Rolo, 2026-10-29: "suggesting what a user could use would be a good feature to add".)

**Inputs:** installed models + their profiles (Part E) · the host budget and co-residency arithmetic (Parts A/C) ·
the lineup's roles and which have no model · family spread (verification diversity) · the host log (models that
spilled, truncated or crashed here).

**Four kinds of suggestion:**

1. **Gap** — "you have no embedding model, so memory search, dedupe and 'find similar' are unavailable." Each gap
   says what it unlocks, then 1-3 concrete options from the Part F search with size, fit at the chosen window and
   licence, and a one-click add.
2. **Overlap** — "three uncensored 27B models cover the same ground at 47-50 tok/s; keep this one." Names the one
   to keep (measured capability, not vibes) and what retiring the others frees.
3. **Mismatch** — "your verifier is the same family as your coder, so blind spots overlap"; "every summary costs a
   16 GB pivot because there is no compactor"; "nothing can co-reside with the resident model".
4. **Freshness** — when capability is equal, prefer the newer library entry (rolo's preference), and flag a model
   whose family has been superseded.

**Rules:** every suggestion states what it does, what it costs (download size, VRAM at which window, pivot or
co-reside) and how long; nothing downloads until pressed; ranked by value per gigabyte; re-checked when the
roster, the Ollama version or the host changes; and available as a scheduled off-hours "roster review" (G13).

**Acceptance:** a user who has never thought about local-model tiers sees, in one panel, what they have, what they
are missing, what overlaps, and what to do — with the numbers.

### Part K — voice mode: talk to Halo (and through Meta glasses)

Feature: drive a Halo session by voice, entirely locally, and optionally through Meta's glasses. Researched
2026-10-29; the parts below are the current best options, not guesses.

**The local loop (all measured options, late 2026):**

- **STT:** `faster-whisper large-v3-turbo` (~3 GB int8, 10-20× realtime on a 4090) or **NVIDIA Parakeet TDT
  0.6B v3** (6.05 % WER, ~50 ms per sentence, <2 GB) behind a VAD chunker; Voxtral Mini 3B when native streaming
  matters most.
- **TTS:** **Kokoro-82M** (<1 GB, Apache-2.0, 54 voices, ~75-100 ms to first audio) as the realtime default;
  **Qwen3-TTS 0.6B/1.7B** (Apache, cloning from a ~3 s reference, streams from ~97 ms) if the user wants their own
  voice. IndexTTS-2 already sits under `C:\ComfyUI\models` but is the weakest fit for a low-latency loop.
- **Glue:** Pipecat or LiveKit Agents (both take local endpoints). Pipeline: Silero VAD → streaming STT → LLM →
  sentence aggregator → streaming TTS. Fully-local round trips have been measured at **750-900 ms**; keep it
  there with partial transcripts, sentence-level chunking, a warm prompt cache and ~250 ms barge-in.
- **One-model options:** `lfm3-omni` (2B: text/image/video/audio in, speech out) and `phonon` (TTS that speaks as
  it generates) are in the Ollama library; Moshi (full-duplex, Apache) has no official Windows support (WSL2
  only).
- **Footprint:** STT + TTS together stay under ~10 GB (about 6 GB in the recommended pairing), so voice mode
  implies a pivot unless the answering model is small.

**The glasses path — Meta Wearables Device Access Toolkit (DAT), stable 1.0 since 2026-09-30:**

- **Supported:** Ray-Ban Meta Gen 1/2, Ray-Ban Display, Oakley Meta HSTN and Vanguard — through an iOS/Android
  app. The glasses are phone peripherals, never a standalone platform.
- **Microphone:** HFP Bluetooth capture (bidirectional, mono 8-16 kHz, but it drops A2DP output to voice quality)
  or in-stream PCM alongside a camera stream (16 kHz mono, keeps A2DP) — **in-stream is still beta and cannot
  ship in a production app**.
- **Speaker:** A2DP output only — fine for TTS.
- **Wake word:** fixed "Hey Meta"; "Hey Meta, start *<app>*" invocations exist but are experimental and
  unpublished, so a custom wake word must be detected phone-side on the streamed audio.
- **Prior art:** `charlie-robison/glasscode` (glasses → phone → Mac running faster-whisper + a coding agent — the
  closest match to this use case), `rayl15/OpenVision` (iOS + local MLX models), `straff2002/OpenGlasses`,
  `farmountain/SmartGlass-AI-Agent`. All hobby-grade.
- **Latency budget:** glasses → phone (~50-150 ms BT) → LAN → PC (STT 50-300 ms, LLM first token 0.1-1.3 s, TTS
  300-700 ms) → A2DP back (~150-300 ms) ≈ **2-3 s**, against Meta's own cloud path at ~1 s.
- **Honest limits:** no custom wake word on the glasses; no always-on background mic streaming; no in-stream
  audio in production; no code or UI on the glasses; the phone always sits in the loop.
- **Meta AI cannot be removed** (setup requires a Meta account), but the DAT lets your app own the whole audio
  loop, so Meta's servers are not in the path while a session is active.

**Acceptance:** a Halo session can be driven by voice end-to-end on the local machine — speak, and hear the
answer — and the same loop works through the glasses, started by a tap or "Hey Meta, start *<app>*".

### Part L — capability bundles with resource reservations (the "tick" system)

Rolo's idea (2026-10-29): a tick that **reserves** local models for one use — communication — so nothing else
competes for them, plus an orchestration that ties reserved local work, task work and API models together so they
never stomp on the GPU; and that tells the user up front which models to download, or that it simply will not
work, before they waste time.

**L1 — a tick is a bundle, not a checkbox.** Turning on "Meta glasses", "voice", "bulk worker" or "verifier"
installs a *capability bundle* that declares four things:

1. **needs** — the models it requires, each with alternatives by size (voice: a small chat model, an STT, a TTS).
2. **reservation** — what it claims exclusively, and for how long (voice: 1.7 B chat @ 8 k, ~1.2 GB, warm, high
   priority).
3. **routing** — where the *other* work goes while the bundle is on (task work → the coder when it fits, else
   cloud; never by evicting a reserved model).
4. **feasibility** — the arithmetic that decides whether the bundle can run on this host at all.

**L2 — reservation semantics.** A reservation is a deterministic claim the host enforces (H10.6): the reserved
model keeps `keep_alive -1`, is never evicted by non-reserved work, and any request that would breach the
remaining budget is **refused or queued** rather than allowed to stomp. The UI shows it plainly: *"2.6 GB reserved
for voice; 18.0 GB free for tasks."*

**L3 — the honest verdict, before anything downloads.** Weights + KV(window) + overhead against usable VRAM minus
existing reservations, with three outcomes in plain language:

- **ready** — everything present, it fits, here is the expected latency.
- **needs N downloads** — exact tags, size and fit for each, total time, one button.
- **won't work** — and why, with the ways out: *"this bundle needs 24 GB; you have 20.6 GB usable. Options: run
  STT on CPU instead of GPU (−1.5 GB); use the 1.7 B voice model instead of the 7 B (−3 GB); free 4 GB by
  lowering the coder's window from 32 k to 16 k."* Never a silent failure, never a wasted download.

**L4 — routing around reservations.** While a bundle holds its reservation, the orchestrator places everything
else: a task that wants the coder gets it **if** it fits beside the reservation, otherwise it is queued, pivoted
(with the cost shown) or sent to a cloud model — one visible line: *"voice holds 1.2 GB; sending this task to
<cloud model> rather than evicting it."* That is the "don't compete for usage" requirement, enforced as host
policy rather than left to a model's judgement.

**L5 — what a bundle declares.** Halo already has a pack format (3.2.0.0); a bundle is a pack with a resource
claim:

```yaml
bundle: meta-glasses
needs:
  chat: {any_of: [lfm3:1.7b, qwen3-coder:30b-gpu], window: 8192}
  stt:  {any_of: [faster-whisper:large-v3-turbo, faster-whisper:small.en], device: cpu-or-gpu}
  tts:  {any_of: [kokoro-82m], device: cpu}
reservation: {model: lfm3:1.7b, vram_gb: 1.2, keep_alive: -1, priority: high}
routing: {task_work: coder-or-cloud, never_evict: reserved}
latency_budget_ms: 1500
```

**L6 — the bundles worth shipping:** voice/glasses · bulk worker · verifier (a different family from the coder) ·
compactor · embeddings/memory · translation · vision · offline-only · coder-first (no reservation).

The **glasses bundle worked out on this box:** reserve `lfm3:1.7b` @ 8 k (1.2 GB, warm), run STT (`small.en`) and
TTS (Kokoro) on CPU so they cost no VRAM, keep the coder as the task-work target, and let cloud models absorb task
work while a voice session is live. Verdict: **fits today** — 1.2 GB reserved leaves ~17.7 GB, so the coder (18.9
GB) still fits *beside* it, barely. GPU STT would break that, which is exactly the kind of thing the feasibility
line must say out loud.

**L7 — acceptance:** a user ticks "Meta glasses" and gets one line — ready, or needs these downloads, or won't
work plus the options. While it runs, nothing evicts the voice model, and task work is routed elsewhere with a
single visible line saying where it went.
