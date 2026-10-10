# Halo Harness roadmap (as approved by rolo through 2026-10-01 ~22:30)

Repo: github.com/roloVibes/Halo-Harness (public). <old-name> is frozen
at v1.0.1. rolo authorised autonomous completion of every version below
and upload to GitHub; no input needed to move forward.

- 2.0.0 (DONE, tagged): rename, state-dir migration, intro.
- 2.0.1: `HALO-2.0.1-gaplist-brief.md` (rounds W1..W5 + W3 additions),
  `GLM-brief.md`, `HALO-2.0.1-liveness-tips-brief.md` (Parts A, B, C).
  Rounds: W1 run-anywhere (done, uncommitted) -> W1b launch hang +
  single executable (running) -> W2 GLM + liveness + tips + effective
  values -> W3a defects + consistency + pending-card dock + bugreport +
  timeline + mode toast + cc version pin -> W3b hygiene + model quality
  -> W4 unbuilt surfaces (thin) -> W5 coverage -> release (3 platforms,
  Kali live, Opus review, fix pass, CHANGELOG, tag v2.0.1, push).
- 2.0.2: `HALO-2.0.2-brief.md` (A three columns, B balances, C
  enumeration, C2 Codex + OpenAI incl. the Responses dialect, D jev,
  E verification, F research corrections, G learned rules + error
  translation + catalog auto-refresh + command consolidation + group
  labels + Codex pin + legacy-env WARN). Also `JEV-brief.md`,
  `RESEARCH-2.0.2.md`.
- 2.0.3: `HALO-2.0.3-brief.md` (model gym, soak test + watchdog, CI +
  release script, invariants doc + test, legacy env file no longer read,
  proxy maintained-only, alias code removed).
- 2.0.4: `HALO-2.0.4-ollama-brief.md` (local and LAN Ollama models:
  Phase 0 research doc, Phase 1 `ol:` provider on the native API with
  per-request context ownership and timing telemetry, Phase 2 hardware
  and host analysis `/ollama`, Phase 3 roles main/small/sub-agent/
  compaction + `/local`, Phase 4 gym ranking + init tab + docs/OLLAMA.md).
  Deferred by rolo: modular agents from other repos.
- 2.0.5 (approved 2026-10-01 ~23:15, "let's defer to your perspective
  on this and add those to future updates"): semantic search over
  auto-memory and sessions on a local embedding model via Ollama
  `/api/embed` (index under `~/.halo/index/`, `/recall <query>`, memory
  topic files ranked by similarity before they are read); a generic
  `local:` route for OpenAI-compatible local servers (LM Studio,
  llama.cpp server, vLLM) reusing the OpenAI compat profile with a
  configurable base URL plus per-server context discovery. Brief to be
  written when 2.0.4 ships. Modular agents from other repos stay
  undesigned until rolo asks.

## RENUMBERED 2026-10-02 (rolo, /plan): everything after 2.0.1 moves back by one

- 2.0.2 (NEW): roles v2 (planner, judge, tester, compaction, subagent_default,
  per-role effort, tab completion, templates), organizations (CEO / VPs /
  managers / workers, the release-flow org), sub-agent visibility and scale
  (/tasks, Ctrl+T, count/batch spawning, configurable concurrency and
  depth), MCP repair actions, Qwen tool calling, terminal tab title.
  Brief: `2.0.2-brief.md`.
- 2.0.3 = the old 2.0.2 (`2.0.3-brief.md`, `2.0.3-jev.md`, `2.0.3-research.md`).
- 2.0.4 = the old 2.0.3 hardening (`2.0.4-brief.md`).
- 2.0.5 = the old 2.0.4 Ollama (`2.0.5-ollama-brief.md`).
- 2.0.6 = the old 2.0.5 local embeddings + generic local: route.
- 2.0.7 (NEW): DOOM theme (section G of `2.0.2-brief.md`).
The version numbers inside the older brief files still say their old
numbers; this section is the authority.
- 2.0.8 (NEW, approved 2026-10-02): remote control of sessions from Signal,
  self-hosted through signal-cli, both identity models (dedicated number
  first, linked device documented), pairing + safety-number pinning +
  signed commands + local control socket. Brief: `2.0.8-signal-brief.md`.
- 2.0.9 (NEW, 2026-10-02): deep code review as a Halo feature (/review,
  parallel dimension reviewers + judge verification + optional fix pass,
  on the 2.0.2 roles and orgs) and a privacy/secret audit tool for the
  tree and git history with a documented remediation workflow. Brief:
  `2.0.9-review-privacy-brief.md`. The content scrub of personal fixture
  text and docs happens earlier, in 2.0.1 W5.
  2.0.9 ALSO (rolo 2026-10-03): a security review of the code itself,
  separate from the privacy audit -- the harness's own attack surface
  (credential handling and storage, subprocess and shell construction,
  path handling in the file tools, MCP and connector trust boundaries,
  OAuth token storage, the 2.0.8 remote-control crypto and control socket,
  correctness of the user's own permission rules, the install script and
  dependency supply chain, what logs and telemetry record), with findings
  fixed before the tag. This is protection of the user's machine and
  credentials; it adds no refusal or safety logic to the harness.
- 3.0.1.1 (rolo 2026-10-03, RESEARCH ONLY, starts after 2.0.9 ships): a
  secure way for separate Halo instances to work together with no cloud
  and no externally hosted server -- a team at work, friends on different
  home networks, or one person's own sessions on several machines, same
  network or not. Brief with the research questions and deliverables:
  `3.0.1.1-p2p-research-brief.md`.

## REORDERED 2026-10-03 (rolo): Ollama moves before the old 2.0.3

The brief files keep the numbers they were written under; this section is
the authority for the order after 2.0.2.
- 2.0.3 = local and LAN Ollama models (brief `2.0.5-ollama-brief.md`):
  research, the native `ol:` provider, hardware and host analysis, roles
  for local models and `/local`, init tab, docs. The model-gym ranking of
  local models that brief mentions waits for the gym itself (now 2.0.5);
  2.0.3 ships a built-in capability probe instead (context window, tool
  calling, streaming) so `/local` can still say which models can run a
  session.
- 2.0.4 = the old 2.0.3 (briefs `2.0.3-brief.md`, `2.0.3-jev.md`,
  `2.0.3-research.md`): three picker columns, balances for every provider,
  `cc:`/`ant:` enumeration, Codex and OpenAI with the Responses dialect,
  jev, learned gateway rules, error translation, catalog auto-refresh,
  command consolidation and group labels, the `cc:` route v2 (section H).
  PLUS the legacy env file no longer being read, because the 2.0.1
  CHANGELOG already announces that for 2.0.4 and the notice stays true.
- 2.0.5 = hardening (brief `2.0.4-brief.md` minus the env-file drop): model
  gym including the local-model ranking, soak test and watchdog, CI and
  release script, invariants doc and test.
- 2.0.6 embeddings, 2.0.7 DOOM theme, 2.0.8 Signal remote control, 2.0.9
  review + security review + privacy audit + front page, then the 3.0.1.1
  research: unchanged.

## ADDED 2026-10-03 (rolo): self-update and clear install steps, in 2.0.2

- 2.0.2 round 6: `halo update` on the CLI and `/update` inside halo (check,
  apply, update-and-restart with the session resumed), the installed
  commit shown by `halo --version` and `halo doctor`, a once-a-day startup
  note when an update is available, a PowerShell install one-liner, and
  README + docs/INSTALL.md rewritten as short fresh-install and update
  steps per platform. Brief: `2.0.2-round6-update-brief.md`.
- 2.0.2 round 7 (rolo 2026-10-03): the init becomes one wizard with
  explicit Back / Skip / Next / Finish buttons (today the provider tabs
  are a separate app the user leaves with Esc before console prompts take
  over), with new Roles and Organizations steps (template presets, the
  editors embedded, skip for later) and `halo setup roles|orgs` plus
  `/setup` to reopen those screens from the CLI or inside halo. Brief:
  `2.0.2-round7-init-wizard-brief.md`.
- Round 7 additions (rolo 2026-10-03): a Theme step, roles/orgs mode
  switches, and the org features borrowed from Paperclip (templates with
  preview and install, budgets with warning and hard stop, goals on the
  task board, approval gates per position, export/import, `/org resume`).
  Later, from the same source: scheduled routines and heartbeats (cron,
  webhook, API triggers), other agent runtimes as positions (after the
  2.0.4 Codex route), a web dashboard; its private LAN/Tailscale mode
  feeds the 3.0.1.1 research.
- MOVED TWICE (rolo 2026-10-03): the Governor round runs as the LAST round of 2.0.4, after the Codex/OpenAI work ('at the tail end of the openAI update version'). The kit is vendored and reviewed in `plans/governor-import/`. Originally written as 2.0.2 round 8: the Governor, the owner's cross-process
  adaptive rate limiter from another project (report in
  `plans/governor-import/README.md`): AIMD per gateway host with
  Retry-After, priority fairness, hard in-flight cap, health-classified
  failover to a different host, and role lanes (verifier never weaker than
  coder). Ported with improvements (Windows locking, atomic state, log
  rotation, timeout classification). Brief: `2.0.2-round8-governor-brief.md`.

## ADDED 2026-10-03 (rolo): Hugging Face and cloud-hosted models join the 2.0.3 pack

- 2.0.3 covers local AND cloud-hosted models on both Ollama and Hugging
  Face: the `ol:` route reaches a local daemon, a LAN host and the
  ollama.com cloud models by host; a new `hf:` route reaches the Hugging
  Face router (Inference Providers, HF_TOKEN), dedicated Inference
  Endpoints, and local OpenAI-compatible servers running Hub models
  (llama-server, transformers serve, vLLM, TGI, LM Studio, Jan), with one
  `/local` discovery across Ollama models, the HF cache and running
  servers. Research first (how users actually run local HF models), in the
  2.0.3 round-1 research brief.


## ADDED 2026-10-04 (rolo): local-model excellence and "find and use" join 2.0.3

- rolo, after the Ollama LAN fix on the build host: "being able to use local
  llms as best as possible or better than anything out there would be a
  huge win"; the Mac has its own unshared Ollama models; Hugging Face files
  saved locally must be found and USED, with a way to tell Halo where they
  are in a session or in the wizard.
- 2.0.3 gains two rounds between round 5 and the docs round (brief
  `2.0.3-ollama-round2-brief.md`):
  - Round 5b "local-model excellence": fit calibration from Ollama's own
    `/api/ps` telemetry with learned per-host caps (fixes the remote-host
    overload seen live), optional ssh GPU read for remote hosts, stable
    request prefix for KV-cache reuse, VRAM-aware role defaults, tokens per
    second and offload in the UI, a per-OS host checklist (`halo ollama
    doctor`), Apple Silicon unified-memory handling and the Mac's loopback-
    only daemon, MLX and LM Studio detection.
  - Round 5c "find local model files and make them usable": user-named
    model folders (`huggingface.model_dirs`, `/local add`, a wizard "Local
    models" step), fit read from GGUF headers and safetensors configs,
    managed runtime child processes (`halo local serve`) with a consented,
    checksum-verified fetch of the pinned llama.cpp release when none is
    installed, and import into Ollama (`halo local import`).
- Decision recorded (rolo asked about using saved models with no server at
  all): no in-process inference by default; the managed runtime gives the
  same engine and speed without tying the model to the TUI process or
  adding compiled bindings to the install, and it still serves the LAN
  topology. Parked for 2.0.5 as an optional experiment: an in-process MLX
  backend on Apple Silicon (pip-only), measured against the managed server
  before it can become a default.

## ADDED 2026-10-04 (rolo): what makes Halo the best harness for local models

rolo asked for the ideas that give Halo a massive edge for local LLMs and GPU
hardware. Placed as follows (2.0.3 items are in the brief's Round 5b):

- 2.0.3 (Round 5b): schema-constrained tool calls on hosts that support it
  plus a one-round local repair loop; the wizard detects hardware and models
  first and recommends fits in plain sentences.
- 2.0.5 (hardening, the model gym): the gym runs on THIS machine's models
  and hardware, scores each local model per role on real Halo tasks
  (tool-call accuracy, edit success, context recall, tokens per second) and
  proposes the role table from data; a 60-second local acceptance check in
  `halo doctor` (load, tool call, structured output, compaction) with
  PASS/FAIL per model; an enforced offline mode ("nothing leaves this
  machine": only allow-listed local hosts reachable, shown in the status
  bar); hybrid escalation rules (local first, cloud when the local judge
  reports low confidence or tools fail twice) as an explicit, visible
  policy; a "saved versus cloud" meter per session; the in-process MLX
  experiment on Apple Silicon.
- 2.0.6 (embeddings): local embeddings through Ollama or a managed server
  for memory and search, same fit and calibration rules.
- 3.0.1.1 (research): peer Halo instances sharing their GPUs on a LAN
  (the Mac's small model as a helper to the PC's main model and back).

## MOVED 2026-10-04 (rolo): the local-model edge items join 2.0.3

rolo: "Let's do all that and move any you support or research in other
updates added to 2.0.3." Applied as:

- Into 2.0.3 (brief Rounds 5d and 5e): the model gym on this machine with
  `halo gym propose` for the role table, the 60-second local acceptance
  check in `halo doctor --local`, enforced offline mode, explicit hybrid
  escalation rules, the "saved versus cloud" meter.
- Stays where it was, with the reason: the in-process MLX backend stays a
  2.0.5 experiment (it can only be verified on rolo's Mac, which workers
  cannot reach); peer GPU sharing stays 3.0.1.1 research under rolo's own
  rule that it starts only after 2.0.9 ships; the embeddings pack stays
  2.0.6 as its own version (its local fit rules reuse 2.0.3's).
- 2.0.5 hardening therefore keeps: soak and watchdog, MCP connects off the
  TUI startup path, CI and release script, invariants, the carried fix-pass
  items, and the gym's cloud-model ranking extension.
- 2.0.3 round order: 5 (running) -> 5b -> 5c -> 5d -> 5e -> 6 -> Opus review
  -> fix pass -> tag v2.0.3.
- Correction the same hour (rolo: "Any GPU support or research*"): every
  GPU-related item joins 2.0.3 after all. The in-process MLX backend becomes
  2.0.3 Round 5f (experimental extra, live-verified by rolo on the Mac), and
  a docs-only GPU research round (Round 5a: vendor probes, multi-GPU fit,
  remote telemetry, the llama.cpp release matrix, KV quantization per
  backend, power draw, mlx-lm) runs right after round 5. Only the
  Halo-to-Halo collaboration research stays at 3.0.1.1. Round order:
  5 (running) -> 5a -> 5b -> 5c -> 5d -> 5e -> 5f -> 6 -> review -> fix pass
  -> tag v2.0.3.

## ADDED 2026-10-04 (rolo): Experiential Labs (experientiallabs.ai)

rolo found platform.experientiallabs.ai and asked that Halo "know how to use
this platform completely and integrate it". What it is (read from its docs
2026-10-04): an open-source (Apache-2.0, Rust) AI gateway, hosted at
`https://api.experientiallabs.ai/v1`, keys `xpl_...`, OpenAI-compatible
chat completions AND `/v1/responses` AND an Anthropic Messages endpoint
(`/v1/messages`, Claude Code connects with ANTHROPIC_BASE_URL), a catalog
of about 1,089 hosted models by slug (`claude-opus-5`, `qwen3.8-27b`) with
pricing, context, tok/s, TTFT and uptime, a per-model "waterfall" of rungs
(platform credits, BYOK, your own endpoint, a local OpenAI-compatible
server: the last two Pro-only) with request-level routing controls
(`gateway.routing.route_id`, `allow_fallbacks`, `gateway.retry`), cached-
token and `usage.cost` reporting, cost and credits APIs (`/api/v1/credits`,
`/api/v1/usage`), gateway-side tool search (`defer_loading`), structured
output with capability errors instead of silent degradation, disclosed
dropped parameters (`x-experiential-ignored-parameters`), embeddings, and a
local gateway (`exp run`) that fronts Ollama and llama.cpp. It is NOT a
model-file hub like Hugging Face: everything is hosted inference or a
gateway in front of servers you run.

Placement:
- 2.0.3 Round 5g (docs only, after 5f): `docs/harness/EXPERIENTIAL-RESEARCH.md`
  covering every docs page (quickstart, authentication, models, waterfall,
  providers guide, adding models, openai-compatibility, anthropic,
  embeddings, cost and spend APIs, plans and billing, data controls,
  telemetry, coding-agents, `exp run` local gateway config and how local
  models appear), plus the free `jev-latest` model and its relation to the
  "jev" models already seen on Databricks and OpenRouter.
- 2.0.4 round 1 (implementation, the cloud-provider pack): an `xp:<slug>`
  route on the existing openai dialect with the catalog in the picker
  (pricing, context, tok/s, TTFT, uptime columns: the same columns the
  picker work in 2.0.4 adds for every provider), `xp:` Claude slugs through
  the Anthropic Messages passthrough so thinking stays native, cost from
  `usage.cost` and the credits API feeding the balances item, waterfall
  controls mapped onto roles and the 5e escalation policy (`allow_fallbacks`
  off for pinned local-first work), the ignored-parameters header into the
  error translation and learned rules, the `/v1/responses` dialect shared
  with the Codex/OpenAI Responses work, and the local `exp run` gateway
  recognised by `/local` as an OpenAI-compatible server (note its default
  port 8000 collides with vLLM in Halo's probe; detect by `/v1/models`
  shape). BYOK rungs and the Pro-only local rung documented as the user's
  choice; Halo never signs the user up for anything.
- Live facts for the 5g research round and the 2.0.4 `xp:` route (measured
  2026-10-04 with rolo's key, which lives OUTSIDE the repo in the vibes
  folder; never copy it into any file): `GET /v1/models` returned 299 models
  for this key (the public catalog page shows about 1,089; the key's
  enabled rungs decide what the list shows); each entry carries
  `context_window_tokens`, `maximum_output_tokens`, per-million input,
  output, cached-input and cache-write costs, `supports_tools`,
  `supports_structured_output`, `supports_reasoning`, `supported_reasoning_
  efforts`, `reasoning_content_native`, `reports_cached_input_tokens`,
  `data_policy`, `owned_by`, sampling bounds; `jev-latest` answered 503
  `unavailable_route` ("ask the gateway operator to check the alias
  deployments") at that hour; `qwen3.8-27b` answered "pong" with
  `usage.cost` 0.00018208 USD, `completion_tokens_details.reasoning_tokens`
  140 of 144 completion tokens (a thinking model by default), top-level
  `provider` "experiential_cloud", top-level `cost` absent (the docs say
  top-level; the live response puts it in `usage.cost`); `GET
  /api/v1/credits` returned `{total_credits, total_usage}` in USD.
- Halo today cannot drive the gateway through the `or:` route with a base
  URL override: the gateway refuses the OpenRouter dialect's `usage` field
  ("The parameter 'usage' is not supported by this gateway profile. Remove
  the field and resend the request.") with a 400 before anything runs. So
  the 2.0.4 `xp:` route needs its own provider profile (no OpenRouter-only
  fields: `usage.include`, `provider` preferences, `transforms`), reading
  cost from `usage.cost`, and the slug grammar accepts ids without a slash.
- Correction the same afternoon (rolo: "make sure to fully implement
  experiential labs completely, I just see do research. Add it fully to
  halo at some point of 2.0.3"): the `xp:` route and everything listed
  above for 2.0.4 round 1 move INTO 2.0.3 as Round 5h, right after the 5g
  research (brief `2.0.3-ollama-round2-brief.md`, "Round 5h"). 2.0.4 keeps
  only the generic picker columns, balances and Codex work, which 5h's
  catalog columns, credits chip and `/v1/responses` dialect now seed.
  2.0.3 round order: 5b part 2 (running) -> 5c -> 5d -> 5e -> 5f -> 5g ->
  5h -> 6 -> Opus review -> fix pass -> tag v2.0.3.

## ADDED 2026-10-04 (rolo): 2.0.7 becomes a theme pack: DOOM, Metroid, Mario

rolo (voice note, 2026-10-04): when the DOOM theme work starts, also build a
Metroid theme and a Mario theme.

- Three game-inspired themes, each with its own slash toggle: `/doom`,
  `/metroid`, `/mario`. Selecting one applies it; selecting the same one
  again restores the previous theme (the existing `/doom` contract, now
  shared by all three). All three appear in the theme wizard step and in
  `/theme`, so they can be chosen and edited the same way as every other
  theme.
- Metroid: Super Metroid on the SNES is the reference. Its colour schemes
  (Crateria's blues and greys, Brinstar's greens and pinks, Norfair's reds
  and oranges, Maridia's teals, Tourian's greys) as selectable variants or
  a per-area accent, a status bar styled like the game's HUD (energy tanks
  and reserve as the context meter, missile and super-missile style
  counters for turn and tool counts, the area name in place of the cwd), a
  map-grid look for panels and dialogs, and Samus-visor framing for the
  input line. "Really Metroid it out as much as possible", in text-mode
  Unicode only.
- Mario: Super Mario Bros / Super Mario World palettes (sky blue, brick
  red, pipe green, coin gold, question-block orange), a HUD-style status bar
  (coins for cost, a timer-style clock, the world/level slot for the cwd),
  brick and pipe motifs on panel borders, 1-up and coin cues on finished
  tasks and sub-agents.
- DOOM keeps its planned bottom status bar treatment and face indicator
  concept; the three share one "game HUD" status-bar layout engine so each
  is a skin on it.
- Rules: original Unicode and ASCII art only, inspired by the games; no
  ripped sprites, sounds or logos in the repo (it is public). Theme names
  stay as rolo named them. Snapshot tests per theme as for every theme
  today; the toggle-again-restores behaviour pinned once for all three.
- 5g research clarifications (docs/harness/EXPERIENTIAL-RESEARCH.md,
  2026-10-04): the GitHub project is a Python-packaged CLI (`pip install
  experiential`) wrapping a compiled Rust/PyO3 native data plane, so no Rust
  toolchain is needed; "exp run fronts Ollama and llama.cpp" is an inference
  from its generic local-model registration mechanism, not a documented
  integration, so 5h treats the local gateway as any OpenAI-compatible server
  (port 8000 confirmed); `jev-latest` is TypeSafe's typed-decision model (not
  a chat model), matching plans/2.0.3-jev.md; a Claude slug's thinking stays
  native only while an Anthropic-shaped rung serves it; cost APIs split by
  inference key versus a separate provisioning key.
- MOVED 2026-10-04 evening (rolo: "Lets get all the codex and OpenAI stuff
  integrated before experimental labs"): section C2 of the old 2.0.3 brief
  (Codex subscription route `cx:` and the OpenAI API route `oai:` with the
  Responses dialect) moves into 2.0.3 as Round 5i, in two parts (OpenAI API
  first, Codex second), BEFORE 5h Experiential, whose `/v1/responses` work
  now reuses 5i's Responses dialect. 2.0.4 keeps the generic picker columns,
  balances, enumeration, jev, learned rules, `cc:` v2, the env-file drop and
  the Governor. Order: 5e (committing) -> 5i part 1 -> 5i part 2 -> 5h -> 6
  -> review -> fix pass -> tag v2.0.3.
- Addition the same evening (rolo: "Just like how we did with Claude settings,
  figure out where those settings exist for codex and let it implement those
  settings"): 5i part 2 also reads Codex's settings and instructions
  (`~/.codex/config.toml`, `AGENTS.md` files, profiles, its MCP servers) into
  Halo's merged settings view with a per-entry source and one precedence
  (Halo config > Claude Code > Codex, Codex leading on a `cx:` session),
  `settings.primary` to flip it, a wizard "Settings sources" step, and the
  merged view in doctor and `/settings`. Halo never writes Codex's files.

## CUT 2026-10-05 morning (rolo: "Fine do that"): 2.0.3 closes after round 5i

After an overnight stall on a redundant test run and about 25,000 new lines
in one day, the batch is cut before the review grows further: 2.0.3 ends
with round 5i part 2 (Codex), then round 6 (docs and live checks), the
Opus review, the fix pass and the tag. Round 5h (the full Experiential
Labs `xp:` integration) moves to 2.0.4 round 1, on top of the reviewed,
tagged 2.0.3; the 5g research (e9e09ef) already carries everything it
needs. 2.0.4's order becomes: Experiential `xp:` -> picker columns,
balances, enumeration -> jev decision API -> learned rules -> `cc:` v2 ->
legacy env-file drop -> the Governor last.

## REORDERED 2026-10-05 (rolo: "reorder") -- this section is the authority from here on

Why: the manual three-platform runs and an unwatched overnight test stall
cost most of a day; the public repo's history gets harder to rewrite with
every release; 2.0.4 had grown as large as 2.0.3 did.

- **2.0.3** (closing): round 5i part 2 Codex -> round 6 docs + live checks
  -> Opus review -> fix pass -> tag v2.0.3 -> both installs.
- **2.0.3.x patch tags:** anything the review, rolo's Mac run or first use
  turns up after the tag ships as 2.0.3.1, 2.0.3.2, ... instead of waiting.
- **2.0.4 = tooling, history, provider pack:**
  round 0 tooling: a GitHub Actions workflow running test_bridge,
  tests/run_all.py and test_tui.py on Windows and Linux on every push and
  pull request (the orchestrator's manual three-platform runs become the
  exception, not the rule); a release script (version bump, CHANGELOG
  check, tag, push, the two install refreshes); the invariants from the
  old hardening list.
  round 1 history: `halo audit privacy`, then the git history rewrite
  (mirror backup first, announced never asked; removes the stray
  `%SystemDrive%` cache files and anything the audit names), force-push,
  both clones reset.
  rounds 2+: Experiential Labs `xp:` full integration (brief Round 5h, research
  e9e09ef); the three-column picker (price, context, speed); provider
  balances; `cc:`/`ant:` enumeration; catalog auto-refresh; error
  translation; command consolidation.
- **2.0.5 = control pack:** `cc:` route v2; jev decision API; learned
  gateway rules; the legacy env-file drop (announced for 2.0.4 originally,
  now here, with the same notice period); the Governor LAST (rolo's rule,
  kit in plans/governor-import).
- **2.0.6 = hardening:** soak run + watchdog; MCP connects off the TUI
  startup path; the gym's cloud-model ranking; the in-process MLX
  experiment measured against the managed server; every carried fix-pass
  item (doctor budgets for thinking models, confirmation before a
  multi-model gym run, zombie checks on every child-process stop, config
  writers refusing the real home under a test marker, the escalation
  approval card, print-mode saved_usd); invariants extended. ADDED
  2026-10-07 ~05:20, rolo ("the seconds keep ticking and I see a steering
  message, tells me nothing what is going on; need better clarity it's
  not frozen"): **liveness in the TUI** -- during a long turn the phase
  line carries a live elapsed timer that visibly ticks (sub-second
  refresh, so a stalled render is instantly distinguishable from a
  stalled turn), names WHAT is being waited on (model streaming vs tool
  running vs subagent round vs background suite), and shows the age of
  the last sign of life from upstream (bytes N s ago; the existing
  hang-watchdog heartbeat becomes visible instead of only dumping a
  log); background jobs surface their state in the status bar the same
  way. A quiet second counter is not "reassurance" -- it is the
  difference between "wait" and "restart".
- **2.0.7 = embeddings + the wizard deep review:** local embeddings
  through Ollama or a managed server with the same fit rules, memory and
  search, the generic `local:` route. ADDED 2026-10-07, rolo ("do a deep
  review of the wizard. it's cumbersome and confusing... everything to
  do with ROLES, ROLE TEMPLATES, and AGENT BIOS needs to be incredibly
  smooth and clear on what is going on and how to use this" -- the team
  control RUNTIME is not the important part): the priority is the whole
  roles surface -- the wizard's roles step, `halo setup roles`, the
  roles/bios editors, `/roles` -- made so a first-time user always
  knows (1) what a role IS and when it fires, (2) what each field of a
  bio does, (3) what the current lineup is and what it costs, before
  anything is saved. Cut what shows by default, one plain-line
  explanation per focused control, visible consequences (which model,
  what price, when it gets used). The Team step currently stacks
  model+effort+price picks, the role table, bio create/edit/duplicate,
  lineup toggles and validation hints on ONE screen -- that is the
  thing to fix. Its own round, pilot-tested as a first-time user's
  path; other wizard steps after. ADDED 2026-10-07 evening, rolo
  ("copying text from the session to another file seems to not really
  work well"): **copy out of the session is a first-class fix** -- the
  whole copy stack (selection copy, Ctrl+C/Y's copy-turn, `/copy`, the
  transcript widgets' own `copy_text()`) audited and made RELIABLE on
  every platform the harness ships on: OSC 52 as primary only where it
  provably lands, a verified system-clipboard write as the floor
  (clip.exe/PowerShell on Windows, pbcopy on macOS, wl-copy/xclip/xsel
  on Linux -- install-hinted when absent), a visible CONFIRMATION line
  every single time (what was copied, how many chars, through which
  mechanism -- silence is indistinguishable from failure), and
  `halo doctor` reporting the copy path verdict per platform. Also:
  copying a WHOLE turn, a code block, and the raw text of a diff must
  each have one obvious binding, tested end to end. DIAGNOSED 2026-10-07
  (the same evening, live on the owner's box): the external fallback
  round-trips fine (clip.exe present, copy+read verified) and OSC 52
  fires on every copy -- the UX killer is that `_selected_transcript_
  text` deliberately copies the WHOLE text of every widget the drag
  TOUCHED, "even just partially" (its own W4c comment): selecting five
  words of a long answer copies the entire message, and a grazing drag
  copies half the screen. The fix must extract the SELECTED RANGE
  (Textual's own Selection.extract on the widget's cells, or an
  equivalent char-range mapping), never whole-widget text; the
  whole-widget behavior stays only for the explicit copy-turn binding.
  Also verify the BOM: a PowerShell read of the clipboard showed a
  leading U+FEFF -- confirm clip.exe writes no BOM (or strip it), since
  an invisible BOM pasted into a file breaks it silently. ADDED
  2026-10-07 late (rolo: "any errors you encounter using ollama should
  be added to 2.0.7"): the first live delegation run through the local
  lineup (worker + verify, both `ol:qwen3-coder:30b@lan`) completed
  clean at $0.0000 with working tool calls -- NO errors -- but surfaced
  three real items: (1) **cold-load UX**: the first dispatch paid a
  full 18.6 GB model load with nothing in VRAM; a pre-warm or
  keep-alive for team-routed local models (session start, or an
  explicit `halo local warm` command) would cut first-token latency
  from ~a minute to seconds; (2) **lineup hygiene**: the ACTIVE team's
  role table routed worker AND verify to the same model --
  `halo doctor --roles` should flag "verify and worker share a model"
  the way it flags judge/coder family overlap (a verifier on the same
  weights shares its blind spots); (3) **the VRAM/swap tension**: a
  lineup that separates verify onto a DIFFERENT local model forces a
  full model swap per role change on a single-GPU box (qwen3-coder
  18.6 GB + qwen3.8 17.7 GB cannot co-reside on 24 GB) -- the team
  default for single-GPU hosts should either prefer same-model
  verification or warn at `teams use` time. All three are polish, not
  blockers: the delegation stack itself (Ollama dialect, tool calls,
  acceptance, cost attribution at $0.0000) held up on real hardware.
  (4) **DEAD MODEL IDS, found live 2026-10-07**: the reviewer role's
  `or:deepseek/deepseek-v4-pro-0813` returned 404 on OpenRouter --
  every reviewer call this cycle silently produced nothing at $0.0000
  (empty handbacks, no error surfaced in the lineup view). `halo
  doctor --roles` must resolve each role's model id against the
  provider's LIVE catalog (one cached lookup per gateway) and flag
  retired ids; a sub-agent whose model 404s must surface the error in
  its handback line, never hand back empty. Fixed in the lineup by
  moving to `or:deepseek/deepseek-v4-pro` (same family, cheaper).
  (5) **local-worker capability boundary, measured live**: qwen3-coder:30b
  ran mechanical tasks perfectly (suites, verifications, exact-report
  commands — 4/4 clean at $0.0000) but failed BOTH synthesis tasks
  (release-notes drafting) even with a tight spec — it wrote code ABOUT
  the task instead of doing it. The lineup guidance this implies goes in
  docs/ROLES.md: mechanical/verify work -> local; anything needing
  composition or judgment -> the paid implementer (deepseek) or the
  session itself. Not a bug — a routing fact.
- ADDED 2026-10-07 late evening (rolo, live reports): (6) **hover
  repaint bug**: black text lines in the transcript DISAPPEAR when the
  mouse passes over them (no :hover CSS exists in halo — this is
  Textual's mouse-capture repainting dirty regions without preserving
  the cells under them; likely a transcript-widget dirty-marking bug).
  Repro: hover any recent output line. (7) **balances shows USED, not
  REMAINING**: `halo balances` prints "$145.15 used" while the owner
  wants the remaining credit (OpenRouter /api/v1/credits returns
  total_credits + total_usage directly — show "remaining = total -
  usage" first, used second). (8) **Windows fork failures under load**:
  "bash.exe: fatal error in forked process - WFSO timed out after
  longjmp" during concurrent suite gates — the same low-virtual-memory
  class as the documented 2026-09-11 session drops; halo should stagger
  concurrent full suites on one box (a simple per-host gate lock) and
  the runbook says one gate at a time on Windows.
- **2.0.8 = theme pack:** DOOM, Metroid, Mario (see "ADDED 2026-10-04:
  2.0.7 becomes a theme pack"; the content is unchanged, only the number).
- **2.0.9 = Signal remote control** (plan `2.0.8-signal-brief.md`, content
  unchanged, number moved).
- **2.0.10 = review:** `/review` as a Halo feature, the security review of
  the code (section A2 of the old 2.0.9 brief), the front page redo. The
  privacy audit and the history rewrite moved to 2.0.4 round 1.
- **3.0.1.1 = research only, after 2.0.10 ships:** serverless collaboration
  between Halo instances incl. peer GPU sharing.
- Unchanged rules: one commit per round; an Opus review + fix pass before
  every tag; live checks every round; status updates as rolo sets them.
- 2026-10-05 ~09:20, rolo: "just park 3.0.1.1 for another time. Go all the
  way to 2.0.10 do not stop. do not have stupid things hang and lose time
  and money." -> 3.0.1.1 is PARKED (no research until rolo re-opens it);
  the run proceeds through 2.0.10 without pausing between versions; every
  remote or WSL suite invocation now runs under a hard `timeout`, every
  backgrounded run gets a scheduled check within fifteen minutes, and a
  commit never waits on a redundant platform run.
- 2026-10-05 ~09:35, rolo: "remove the jev api in the upcoming feature" ->
  the jev decision API (plans/2.0.3-jev.md section D) is REMOVED from the
  roadmap: 2.0.5 control pack = `cc:` route v2, learned gateway rules, the
  legacy env-file drop, the Governor last. The jev brief stays in plans/ as
  a record only; the jev-router idea remains parked; the Qwen decision-only
  patterns shipped in 2.0.2 are unaffected.
- ADDED 2026-10-05 ~11:15 (rolo): 2.0.4 provider-pack round "roles wizard":
  (1) BUG: the wizard's roles step does not list the models Halo has
  discovered (Ollama catalogs incl. LAN hosts, running local servers, the
  hub cache, the router, OpenAI, Codex and Claude Code enumerations,
  OpenRouter and Databricks catalogs) -- every role's picker must show the
  same merged model list the `/model` picker shows, grouped by provider,
  with the gym score beside a model when one exists; (2) an "Auto" tab when
  editing roles in the wizard: one key fills every role from a preset
  (local-first, balanced, quality) or from `halo gym propose` when gym data
  exists, shows the resulting table with one sentence per choice, and lets
  the user adjust before Save; the same Auto action in `/roles`. Tests: a
  Textual pilot walk through the roles step with a fixture catalog, the
  Auto fill from each preset and from a gym fixture, Save round trip.
- ADDED 2026-10-05 ~11:40 (rolo, from the picker on the Kali VM): 2.0.4
  provider-pack round "Databricks enumeration": many `dbx:` rows show blank
  context, output and prices ("not published"). Measured: models.dev's
  `databricks` provider lists 30 ids and lacks every newer endpoint
  (claude-opus-5 / -5-5, claude-sonnet-5 / -5-5, claude-opus-4-8, deepseek
  v4 flash/pro, gemini 3.5/3.7/3.8 flash, gemma-3-12b, glm-5-3 and -flash),
  while the VENDOR providers in the same file do carry those families
  (anthropic claude-opus-5 / sonnet-5, google gemini-3.5-flash, deepseek
  deepseek-v4-flash / -pro, zai glm-5.3-flash). Deliver: (1) a family
  fallback: strip the `databricks-` prefix, normalise version punctuation
  (opus-4-5 -> opus-4.5, gemini-3-5-flash -> gemini-3.5-flash, glm-5-3 ->
  glm-5.3, deepseek-v4-1-flash -> deepseek-v4.1-flash) and parse the
  external endpoint ids (`us-anthropic-claude-sonnet-4-5-20250929-v1-0` ->
  claude-sonnet-4.5) to look up context, max output and prices in the
  vendor's own models.dev entry, shown with a "vendor list price" marker
  since Databricks pay-per-token may differ; (2) read what Databricks'
  serving-endpoints API does expose per endpoint (task, foundation model
  name, display name) and use the display name where it carries the
  version; (3) refresh the vendored models.dev fallback files at build
  time with a script and a staleness test; (4) blank only when truly
  unknown, with the reason in the picker footer. Tests on fixture catalogs
  for every mapping above and for the external-id parser.
- ADDED 2026-10-05 ~12:05 (rolo): 2.0.4 round "MCP connectivity deep dive".
  rolo: "the mcp list goes from like 0/6 to 0/0 in a session. none of the
  mcp fixes did anything, I still cannot reconnect to many of the mcps. we
  need like a doctor deep dive option to fix these with the use of an llm".
  (1) BUG first: the status bar's MCP counter drops from 0/N to 0/0
  mid-session, so configured servers vanish from the registry after a
  failed connect or reconnect instead of staying listed as down; find the
  path that removes them, keep them listed with their last error, pin the
  count with a test. (2) Diagnosis corpus: capture `halo mcp test <name>`
  and the per-server logs for every failing server on the owner's PC and
  the VM (never into the repo) and read what the 2.0.2 repair actions
  missed. (3) `halo doctor --mcp deep [name]` and `/mcp doctor`: per
  server, resolve the command (PATH, shims, node/python/uv versions),
  spawn with a timeout, run the stdio handshake, initialize and list tools
  (or the HTTP/SSE and websocket equivalents with port and TLS checks),
  capture all stdout and stderr, diff the child environment against the
  user's shell, then hand the evidence plus the server's config to a model
  (the session model or the judge role) that proposes ONE concrete fix per
  server (config edit, missing package, wrong path, port, env var) in a
  plain sentence; apply only on a yes, re-test, and record what worked in
  the learned-rules store so the same failure is fixed automatically next
  time. (4) `/mcp` shows "deep dive" as an action and the last diagnosis
  per server. Tests: a fake stdio server with scripted failure modes
  (bad path, crash on initialize, slow handshake, wrong env), the counter
  pin, the fix application with consent, the learned-rule replay.

## ADDED 2026-10-05 ~12:40 (rolo): 2.0.4 "new labs" coverage -- Space Bunny Alpha, Tencent, TypeSafe, NVIDIA

rolo: "stealth and their Space Bunny Alpha model seems to be a really great
coding agent. Make sure we know how to run that model if we use it in halo
during the 2.0.4 updates" ... "same with tencent, typesafe models, and NVIDIA
models". Looked up live on 2026-10-05 (ids and prices change; re-check in the
round):

- **Space Bunny Alpha** is NOT on OpenRouter's public catalog; it is on the
  Experiential Labs gateway as `space-bunny-alpha` (owned_by `exp`): 1,000,000
  context, 524,288 max output, tools + structured output + reasoning
  (`supported_reasoning_efforts` low/medium/high/xhigh/max, default effort
  `max`, reasoning output hidden), `no_training: true`, priced $0 today
  (preview). So it runs through the 2.0.4 Experiential `xp:` route:
  `halo -m xp:space-bunny-alpha` once 5h lands; the round must prove a full
  tool loop on it (Read/Edit/Bash round trips) and the 1M context meter.
- **NVIDIA**: on Experiential as `nemotron-3.5-lightning` ($0.06/M in,
  $0.22/M out, reasoning, tools), `nemotron-3-super-120b-a12b`,
  `nemotron-3-ultra-550b-a55b` ($0.66/$2.64), `nemotron-3-nano-30b-a3b`,
  `nemotron-nano-9b-v2`/`12b-v2`; on OpenRouter as `nvidia/nemotron-3.5-
  lightning` (262k ctx, $0.06/$0.16) and the same family with `:free`
  variants (`nvidia/nemotron-3.5-lightning:free` 1M ctx, `nvidia/nemotron-3-
  ultra-550b-a55b:free`, `nvidia/nemotron-3-super-120b-a12b:free`,
  `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`) plus the
  `nvidia/switchyard` router (1M ctx, variable price). NVIDIA's own endpoint
  (build.nvidia.com, OpenAI-compatible `https://integrate.api.nvidia.com/v1`)
  is the third way: `oai:` with a custom base URL and an NVIDIA key.
- **Tencent**: OpenRouter `tencent/hy4-preview` (1,048,576 ctx, $0.75/$2.25,
  tools + reasoning), `tencent/hy3` (262k, $0.08/$0.33), `tencent/hy3-preview`,
  `tencent/hunyuan-a13b-instruct` (also on Experiential, $0.14/$0.57), and the
  `hy-mt2-*` translation models (no tools). Run as `or:tencent/hy4-preview`.
- **TypeSafe**: OpenRouter `typesafe/jev-router` (1M ctx, variable price,
  tools + reasoning): the router that picks a model and effort per request
  (the jev decision API itself stays removed from the roadmap; the model id is
  just another `or:` ref). Run as `or:typesafe/jev-router`.

Round work for 2.0.4 (folds into the Experiential 5h round and the picker/
balances/enumeration rounds, no new round):
1. `xp:` catalog mapping must read the gateway's real fields:
   `context_window_tokens`, `maximum_output_tokens`, `pricing.*_nano_usd_per_
   million_tokens` (divide by 1e9 for $/M; 0 = free, null = unknown, show the
   difference), `supported_reasoning_efforts` + default `reasoning_effort`,
   `reasoning_output_hidden`, `supports_tools`, `data_policy.no_training` /
   `zdr` as a picker badge.
2. OpenRouter rows with price `-1` (routers: `openrouter/auto`,
   `typesafe/jev-router`, `nvidia/switchyard`) show "varies", never a negative
   number; 1M/2M contexts format as "1M"/"2M"; `:free` variants sort next to
   their paid row.
3. An `or:`/`xp:` id with no vendored catalog row gets a live lookup (ctx,
   price, tools) instead of blank columns (same gap rolo saw on Databricks).
4. docs/MODELS.md "How to run" table: one line each for Space Bunny Alpha,
   Nemotron 3.5 Lightning (three ways), hy4-preview, jev-router, with the
   data-policy note (preview models: no_training true on Experiential; check
   the OpenRouter row's policy before sending private code).
5. Live check in the round: a real tool loop on `xp:space-bunny-alpha` and on
   `or:nvidia/nemotron-3.5-lightning:free` from the Kali VM with rolo's keys.

## ADDED 2026-10-05 ~13:45 (rolo): 2.0.3.1 = clipboard image paste ("I need to be able to post clipboard pictures into halo")

First patch tag after v2.0.3, ahead of 2.0.4 round 0, because rolo needs it
now and it is self-contained TUI work. What exists today: `Session.turn(text,
images=...)` already takes Anthropic-shaped image blocks, `tui/images.py`
already renders inline images where the terminal can, and
`PromptInput._on_paste` already handles TEXT pastes (`pasted[n]`
placeholders). Nothing reads an IMAGE off the OS clipboard. The round:

1. Paste path. Ctrl+V (and Shift+Insert) whose paste event carries no text,
   plus an explicit `/paste`, read the OS clipboard image; a pasted text that
   is the path of an image file (a drag from Explorer/Finder) attaches that
   file instead. Readers, no new hard dependency, each tried in order with a
   2 s timeout: Windows `powershell -c "[Windows.Forms.Clipboard]::GetImage()"`
   saved as PNG through System.Drawing (fallback `Get-Clipboard -Format
   Image`); macOS `osascript -e 'the clipboard as «class PNGf»'` (fallback
   `pngpaste`); Linux `wl-paste --type image/png` then `xclip -selection
   clipboard -t image/png -o`; WSL `powershell.exe` interop; Pillow
   `ImageGrab.grabclipboard()` when Pillow happens to be installed. Over SSH
   (the Kali VM from Windows Terminal) the terminal has no remote clipboard:
   the chip explains it once and `/paste <path>` or a dragged path works.
2. Storage and limits. `~/.halo/attachments/<session>/clip-<n>.png`; images
   over 1568 px on the long side are downscaled (same rule Claude Code
   applies), hard cap 5 MB, PNG or JPEG; the transcript log stores the PATH,
   never the base64, so resume re-reads the file.
3. Input chip `[Image #1 1024x768]` in the prompt area (Backspace on it
   removes it, `/images` lists pending attachments); on submit the images ride
   on `turn(text, images=[...])`; the transcript shows the inline image via
   tui/images.py when the terminal supports it, else the caption.
4. Dialect conversion. Anthropic-shaped rungs (ant:, cc:, dbx: Claude,
   Experiential Anthropic shape): image blocks as today; OpenAI-shaped
   (or:, oai:, hf:, xp:, dbx: others): `image_url` data URLs; `ol:`:
   `images` base64 on the user message; `cx:`: `codex exec -i <path>` (the
   real flag); `cc:`: the saved path as a file mention. A model whose catalog
   row says no vision gets one clear line ("<model> does not take images;
   attached as a path") instead of a provider 400.
5. Print mode parity: `--image <path>` (repeatable) and stream-json `image`
   content blocks on `user_input`.
6. Tests: a fake clipboard backend per platform shape, the chip, `turn()`
   receiving the block, per-dialect conversion, the downscale and size cap,
   resume from the stored path, a TUI pilot test for Ctrl+V with an empty
   paste. Live: a screenshot pasted into Halo on the build host against a
   vision model on `ant:` and `or:`, and `xclip` on the Kali VM.

## CUT 2026-10-05 ~15:10 (rolo: "can we get thru 2.0.3?"): the minors pass leaves the v2.0.3 tag

The review's 53 minors plus the C-1/C-2 leftovers (plans/2.0.3-release-notes-
for-fix-pass.md) become **2.0.3.2**, after the 2.0.3.1 clipboard patch. The
tag waits only for fix passes A-2 and B-2 (run in parallel from 15:10), the
three-platform suites and one live check on the 4090 host and the Kali VM.

## CUT 2026-10-05 ~18:10 (rolo: "ARE WE STILL ON 2.0.3!?"): no 2.0.3.2 round

The review minors, the C-1/C-2/B-2 leftovers, the two flaky tests, the empty
print-mode error for an unconfigured provider and the two clipboard
follow-ups (all listed in plans/2.0.3-release-notes-for-fix-pass.md) move
to **2.0.6 hardening**. After the v2.0.3.1 tag the next round is **2.0.4
round 0** (tooling), then the rest of 2.0.4 in the REORDERED order.

## ADDED 2026-10-05 ~22:35 (rolo): the roles-wizard round, made precise

rolo: "When you do halo init and set roles, the available models are not
listed when you select edit a role. Maybe an enum of what models you can
reach should occur after you set the keys so when you get to the roles
step, and I'm sure for the business roles too, there aren't models to pick
from and/or autocomplete when you are setting the models to roles or
company org roles." So the round (next after round 3) is:

1. Enumerate RIGHT AFTER the keys step, with the keys just entered in this
   wizard run (not only the saved config): every reachable provider's model
   list (OpenRouter, Anthropic, Databricks, Hugging Face router and local
   servers, OpenAI, Codex, Claude Code, Experiential, every Ollama host
   including LAN hosts) merged into the same list the `/model` picker
   shows, cached for the rest of the wizard, with a one-line progress
   notice per provider and "not reachable" rows that never block the step.
2. The role editor, the company/org roles editor and the TUI `/roles` and
   `/org` editors all pick from that list (grouped by provider, gym score
   beside a model when one exists) with autocomplete on the ref field;
   typing a ref that is not in the list still works, with a one-line note.
3. The "Auto" tab in the roles editor (presets local-first / balanced /
   quality, or `halo gym propose` when gym data exists), adjustable before
   Save; the same action in `/roles`.
4. Tests: a Textual pilot through init with fixture providers, the
   enumeration cache, the pick list and autocomplete in both editors, the
   Auto fill from each preset and from a gym fixture, Save round trips.

## ADDED 2026-10-05 ~22:45 (rolo): agent declaration files (YAML) behind roles and orgs

rolo: "each role should have a yaml file that can be editable too. I think
that's how templates should be used. templateX.yaml, 1st agent: name;
models: preference: x, fallback: y; tools: -tool A (for example caido),
-tool b (example browser); context: CLAUDE.md, halo(agentName).md, obsidian
notes X; limits: max_iterations: x, timeout: 20m". Approved schema
("perf, keep going"), built in round 4 as the storage behind the roles and
org editors:

- Files: `~/.halo/agents/<name>.yaml` (user) and `.halo/agents/<name>.yaml`
  (project); templates shipped in the package under
  `halo_harness/templates/agents/*.yaml` (local-first, balanced, quality,
  researcher, judge, reviewer, and an org starter set). `extends:
  <template>` so an agent file carries only overrides. Precedence: template
  -> agent file -> org position overrides -> CLI flags. Import/export both
  ways with Claude Code's `.claude/agents/*.md` frontmatter (same fields).
- Sections: identity (`name`, `description`, `version`, `tags`, `kind`:
  main/subagent/researcher/judge/reviewer/custom, `extends`); `models`
  (`preference`, `fallback`, `escalation`, `effort`, `temperature`,
  `thinking: native|off`, `context_budget`, `lean_prompt`); `tools`
  (`allow`, `deny`, `mcp_servers`, `permission_mode`, `rules` in the
  settings.json grammar, per-tool limits such as a Bash timeout); `context`
  (files to prepend, Obsidian notes by path/glob/tag, `skills`,
  `system_prompt` inline or file, `memory` on/off + directory); `limits`
  (`max_iterations`, `timeout`, `max_budget_usd`, `max_tokens_per_turn`,
  `concurrency`); `output` (`output_schema`, `report_to`, `handoff`);
  `environment` (`cwd`, `worktree`, `offline`, `env` by reference to the
  shared env file, never a literal secret); `org` (`position`,
  `reports_to`, `delegates_to`); `acceptance` (one smoke prompt + expected
  shape, run by `halo doctor --agents`).
- Deferred to 2.0.5 with the Governor: `hooks` (pre/post tool commands) and
  `schedule`/`triggers`.
- Dependency: PyYAML (small, pure Python) added to pyproject; the loader
  validates every file and reports one plain line per problem.

## ADDED 2026-10-05 ~23:10: 2.0.4 round "xp: contract alignment" (after the MCP deep dive)

The gateway publishes a machine-readable contract at
`https://platform.experientiallabs.ai/llms.txt` (fetched 2026-10-05, ~160 KB;
kept outside the repo). Round 2 was built from the research doc; this round
aligns the `xp:` route with the contract literally: the full error-code
table (e.g. `all_routes_failed` 502 = every rung failed, retry then report;
`unsupported_capability` 400; `model_requires_purchase` 429; the ZDR
refusals 403/409), the honored and refused parameters per endpoint (a
refused parameter is a 400 "The parameter '<x>' is not supported by this
gateway profile", never silently dropped; the `x-experiential-ignored-
parameters` header for the dropped ones), the per-response headers
(`x-request-id`, `x-gateway-provider`, `x-gateway-zdr`,
`x-gateway-route-depth`, `x-gateway-route-reason`) shown on the transcript
line and in `/xp routes`, the ZDR toggle and `provider.zdr` per-request
constraint as a config key, the two lanes (platform-funded versus BYOK) in
the cost line, and `GET /api/v1/generation?id=<x-request-id>` for after-the-
fact attribution in `halo stats --experiential`. Live facts measured
2026-10-05: `qwen3.8-27b` answers with a minimal body (model + messages) at
$0.0000376; `space-bunny-alpha` returned 502 to every body shape that
evening (all rungs down), so a 502 must read as "every route failed, try
again later", never as a Halo error.

## ADDED 2026-10-06 ~00:25 (rolo): agent BIOS and team TEMPLATES are two layers

rolo: "agent names should be their own file ... `<agent_name>.yaml` that has
those sections describing what it does ... a user can create any agent bio.
Template.yaml calls which one of those agent names and assigns them roles."
So the agent-file design (section "ADDED 2026-10-05 ~22:45") splits:

- Agent bios: `~/.halo/agents/<agent_name>.yaml` (user), `.halo/agents/`
  (project), shipped starters `halo_harness/templates/agents/*.yaml`; the
  sections from the earlier design minus any role or position; `extends`
  between bios. Who the agent is and what it does.
- Team templates (lineups): `~/.halo/teams/<template>.yaml`, `.halo/teams/`,
  shipped `halo_harness/templates/teams/*.yaml` (local-first, balanced,
  quality, an org starter). `roles: {main: <agent>, subagent: ...,
  researcher: ..., judge: ..., reviewer: ...}` and `positions: [{title,
  agent, reports_to, delegates_to}]`, with per-assignment overrides.
  Precedence: template assignment -> bio -> CLI flags.
- Config: `team: <template>` (+ overrides) is the active lineup; the wizard's
  roles step and Auto tab pick a template; the role editor assigns an agent
  per role (autocomplete over bio names); the org editor assigns agents to
  positions; bios' models use the enumerated pick list. `halo agents ...`
  and `halo teams ...` CLIs, `/agents` and `/teams`, `halo doctor --agents`
  validates bios and the active template. Legacy role table -> a generated
  `migrated` template + one bio per distinct model, announced once.

## ADDED 2026-10-06 ~00:40 (rolo): a team template is a lineup of many assignments

rolo: "Templates should be able to assign like many sub agents somehow in
those files." Template schema (built in round 4; the `roles:` shorthand
stays as sugar expanding to one assignment per role):

- `agents:` list of assignments {agent, role (main | subagent | researcher |
  judge | reviewer | custom), as (alias), instances, use_for (task kinds or
  keywords), overrides: models/tools/limits}; several per role; exactly one
  main.
- `delegation:` mode (manual | by-skill | round-robin), max_parallel,
  max_depth, handoff (summary | full | structured), forward_text.
- `routing:` task kind -> role or alias, with default.
- `budget:` max_budget_usd, max_total_turns, max_wall_time, agents_may_exceed.
- `escalation:` the existing policy shape (triggers, to, ask, allow_fallbacks).
- `context:` shared files, skills, memory (namespace or blackboard, writers).
- `permissions:` mode, rules, offline.
- `org:` positions [{title, agent, reports_to, delegates_to, instances}],
  reporting {cadence, format}.
- `pipeline:` optional ordered stages [{name, role, gate}]; order shown now,
  gates enforced by the 2.0.5 Governor.
- identity: name, description, version, tags, extends; `acceptance` for
  `halo doctor --teams`.

## ADDED 2026-10-06 ~04:35 (rolo): 2.0.5 round "wizard: agent bios and lineups" (round 2, right after cc: v2)

rolo, after the v2.0.4 tag: "The wizard needs the agent bio setup, and
when you are setting up a template, you need to have those other options
or a text prompt at the bottom (optional) explaining how all the pieces
work together. When you have a role in a template or creating roles in a
new template, or editing roles in a template, you can fill those with
agents that are either an available model, OR the agent bio section that
lists all of those agents with bios which is a more detailed version of
just picking a model for a role in a role template. In that wizard
section a user should be able to create or edit agent bios, have common
sections in these agent bios like model, which opens the available models
list again that was just enumerated to assign that part. Have other common
parts of the bio yaml file that a user can create and edit."

What this adds (2.0.4 round 4 built the enumeration, the pick list and the
Auto tab; the bios and templates exist as files and CLI commands):

1. **An Agents step in `halo init`**, after the keys step and the
   enumeration, before the roles step: lists every bio the loader finds
   (project `.halo/agents/`, user `~/.halo/agents/`, the shipped templates,
   each marked with its scope), with create, edit, duplicate and delete.
   The bio editor is one form over the common sections of the YAML:
   identity (name, description, tags, kind, extends), `models`
   (preference and fallback open the SAME enumerated model pick list the
   roles step uses, plus effort, thinking, context_budget), `tools` (allow
   and deny from the known tool names, mcp_servers from the configured
   servers, permission_mode, rules), `context` (files, skills, memory),
   `limits`, `output`, `environment`, `acceptance`. Save validates with the
   loader and writes `agents/<name>.yaml` (user scope by default, project
   scope on request); one plain line per problem; unknown keys already in
   the file are kept, never dropped.
2. **Role slots take a model OR an agent bio.** Wherever a role is filled
   (the roles table, a role in a new template, a role in an existing
   template, an org position), the picker has two sources: "Models" (the
   enumerated list, as today) and "Agents" (every bio with its description,
   preferred model and a tools summary). Picking a bio records the agent on
   the slot (`agents: [{agent: <name>, role: <role>}]` in a template; the
   roles table keeps the model and the agent name); picking a model keeps
   today's behaviour. "New bio..." from inside the picker opens the editor
   and returns with the new bio selected.
3. **A template editor in the wizard** (new template or edit an installed
   one): the assignments grid (agent or model per role, alias, instances,
   use_for), the other top sections as optional fields (`delegation`,
   `routing`, `budget`, `escalation`, `context`, `permissions`, `org`,
   `pipeline`, `acceptance`; shown collapsed, each with its one-line
   meaning), and at the bottom an optional free-text field **"How the
   pieces work together"** saved as the template's `about:` (multi-line);
   when the team is active that text is appended to every member's
   context as "How this team works", and `halo teams show` prints it.
   Save writes `teams/<name>.yaml` through the loader's validator and
   offers to make it the active `team:`.
4. **The same forms outside the wizard**: `/agents` (list, new, edit) and
   `/teams` (list, new, edit, activate) in a running session, built on the
   same form module; `halo agents new|edit` and `halo teams new|edit` gain
   `--form` to open the TUI form instead of `$EDITOR`.
5. Tests: Textual pilots through the Agents step (create a bio picking its
   model from a fixture catalog, save, reload, edit), the roles step with
   the two picker sources, a new template with one role by model and one
   by bio plus the about text and one advanced section, validation lines
   on a bad save, the slash dialogs, `--form`. Docs: AGENTS.md, ROLES.md,
   the wizard section of HANDBOOK, COMMANDS and SLASH-COMMANDS, CHANGELOG
   `[2.0.5]` "### Wizard: agent bios and lineups".

Order: this is 2.0.5 round 2 (brief `plans/briefs/2.0.5/round-2-wizard-agents.md`);
learned rules + env drop become round 3, the Governor round 4, team control
round 5.

Folded in 2026-10-06 ~04:50 (rolo: "fold them in", from the orchestrator's
review of the two editors): new-from with the inherited/override view and
`extends`; problems inline with a live YAML preview pane; the pick list
filtered by the bio's needs plus a Suggest chord; rules rendered as plain
sentences, budget and timeout hints; Import from `.claude/agents/*.md`; the
lineup grid shows the resolved truth per row with the warnings that need no
Governor; the about text is drafted and marked stale; the roles table is a
read-only projection of the lineup. DEFERRED with a home: "Try it" on a bio
and a lineup smoke run from the forms (cost shown first) -> 2.0.6; lane
warnings (reviewer weaker than coder) and the live cost estimate against
`budget` -> after the Governor (round 4) and team control (round 5), in the
2.0.5 fix pass if time allows, else 2.0.6; export/import of a lineup with
its bios as one folder -> 2.0.6.

## ADDED 2026-10-06 ~09:30 (rolo, after using round 2 on his box): 2.0.5 round 2b "wizard and roles fixes" -- runs BEFORE the Governor resumes

rolo: "The wizard, you need a toggle on and off the roles complete, not
just legacy. When you are editing an agent bio, the top few chat prompts on
the right side of the wizard screen get lost by other parts of the settings
in the agent bio for the wizard. You can't pick from the available models
when you are setting up the bio like I asked. Lots of bugs in that feature.
There needs to be a standard template that just uses the model you pick as
the default. Asking to make changes for role templates or agent bios in the
session works well."

A model review of v2.0.4 rolo ran on his own box (screenshot, 2026-10-06)
adds, under "Weak spots": (1) `halo roles template load <name>` writes the
role mappings but does NOT set `roles.enabled: true`, so the table sits
inert until a hand edit of config.json; (2) no CLI toggle for
`roles.enabled` at all, and no way to point the config at a table without
`load` overwriting the mappings; (3) packaging: the README badge embedded
in METADATA still says version 2.0.1, and the GitHub Releases page is
empty (tags only) because the release script writes the CHANGELOG but
nothing publishes release notes; (4) the "not yet enforced" team sections
accumulate into the Governor round (known; round 5 team control).

What the round does (brief `plans/briefs/2.0.5/round-2b-wizard-roles-fixes.md`):

1. **Roles on/off is one switch**, everywhere: a toggle at the top of the
   wizard's "Roles and lineup" step ("Roles: on / off"), `halo roles on`
   and `halo roles off`, `/roles on|off`; `halo roles` prints the state in
   its first line; `halo roles template load` turns roles on and says so;
   `halo teams use <name>` is the documented non-overwriting way to point
   at a lineup.
2. **A shipped `standard` lineup**: every role resolves to the session's
   default model (the one picked in the Default model step) through a
   `default` model reference resolved at run time, so changing the default
   model moves every role with it. "Roles: off" means the standard lineup;
   it is what a fresh install runs.
3. **Bio editor layout**: the preview pane never covers or pushes out the
   form's top rows; both panes scroll; verified by pilots at 80x24 and
   120x40 where every field can be focused and is visible when focused.
4. **Bio editor model picking**: a visible "Pick..." button beside the
   preferred and fallback fields (Ctrl+P / Ctrl+F stay), the picker fed by
   the same enumeration the Providers step produced (run it with progress
   if it has not happened yet), the bio-needs filter never yielding an
   empty list silently (falls back to all rows with one line saying why),
   and the picked model written into the field immediately.
5. **Bug sweep** of the Agents step, bio editor and lineup editor by
   driving the whole wizard flow in pilots at both sizes, fixing what
   breaks, one line per fix in the hand-back.
6. **Packaging**: `scripts/release.py` updates the README version badge
   and publishes a GitHub release whose notes are the CHANGELOG section
   (through the `gh` CLI when present, else the REST API with the git
   credential token; `--no-github-release` skips it; dry run prints it);
   a test pins the badge to `__version__`.

Order from here: round 2b -> round 2c (below) -> round 4b (cc: steer on
Linux, partial work in the stash) -> round 4 the Governor (partial work in
the same stash) -> round 5 team control -> review -> tag.

## ADDED 2026-10-06 ~10:05 (rolo): 2.0.5 round 2c "wizard interaction model" -- the wizard stops being clunky

rolo: "I think that the wizard is getting a little clunky and confusing. We
really need to make that a lot more intuitive and clear when you're using
the wizard, period. It's sometimes confusing when something is highlighted
and then you gotta click through for the next, like even the selection part
of it in some parts requires you to highlight something in the box and go
down, tab, and say yes, this one, I want to edit this or make changes to
this highlighted one. The wizard can be a lot smoother and less clunky.
Come up with ideas to fix that in these updates."

The interaction model (one page, `docs/WIZARD.md`, every wizard screen
follows it, each rule pinned by a pilot):

1. Highlight is selection for one-of choices (default model, permission
   mode, theme, lineup): the highlighted row is the chosen one, marked
   with a check; Next moves on; no confirm button.
2. Enter does the obvious thing on a highlighted row: open or edit a bio
   or lineup, pick a picker row, use the highlighted lineup. Space toggles
   on/off rows. Buttons stay for the mouse, never the only path.
3. Autocomplete inside model fields: typing filters the enumerated list in
   a dropdown under the field, Enter picks; Ctrl+P still opens the full
   picker with the price, context and speed columns.
4. A step rail across the top (Providers, Local models, Default model,
   Permissions, Theme, Agents, Roles and lineup, Orgs, Summary): current
   step highlighted, done steps ticked; Ctrl+Left / Ctrl+Right are Back
   and Next from anywhere.
5. Quick setup by default: keys -> default model -> done, which activates
   the `standard` lineup with roles off; "Full setup" reveals Agents,
   Roles and lineup, Orgs and Theme.
6. One sentence at the top of each step: what it decides and the current
   choice ("Default model: <ref>. Enter to change.").
7. Focus lands on the content (the list or the first field) when a screen
   opens, never on a button; the focused control and the highlighted row
   look different.
8. At most two levels deep (list, then editor). Save shows a one-line
   toast; errors stay inline; Escape is always Back and never destructive.
9. The footer reads the same on every screen: Enter choose, Space toggle,
   Ctrl+N new, Ctrl+E edit, Del delete, Ctrl+S save, Esc back.
10. The Summary step has "Change" jumps back into each step.

Round 2b's sweep applies rules 1, 2 and 7 immediately; round 2c applies
the rest and re-checks all ten with pilots at 80x24 and 120x40.

Added 2026-10-06 ~10:15 (rolo): "the part when it gets to roles just gets
very confusing. We started with the agent bios before the templates. I feel
like templates might go first. Or maybe that screen should have both
templates and agents in one window of the wizard, as well as that toggle
on or off at the top if you want custom roles enabled. Halo should be able
to spawn its sub-agents if they want and ask you questions; these are kind
of like the custom role templates."

Rule 11, **one Team step instead of Agents + Roles and lineup**: a single
wizard screen titled "Team" with the switch "Custom roles: off / on" at
the top. Off shows one sentence ("Halo uses <default model> for
everything, including the sub-agents it spawns on its own, and still asks
you questions when it needs to") and nothing else. On shows two panes side
by side: left "Lineups" (the templates; the highlighted one is the active
lineup, marked with a check; Enter edits, Ctrl+N new, Ctrl+D duplicate),
right "Agents" (the bios; Enter edits, Ctrl+N new, Ctrl+D duplicate, Del
delete). Editing a lineup opens the lineup editor whose slots pick from
the bios on the right or from the model list. The step rail becomes
Providers, Local models, Default model, Permissions, Theme, Team, Orgs,
Summary; `halo init --step team` reaches it (`--step agents` and `--step
roles` stay as aliases). Roles off never disables delegation: the
`standard` lineup gives every role, including spawned sub-agents, the
default model, and the question card works as today.

## ADDED 2026-10-06 ~10:25 (rolo: "Add these suggestions to 2.0.6"): seven items from a model review of v2.0.4

Source: a ranked "What I'd add" list rolo got from a model reviewing
v2.0.4 on his own box (screenshot). Recorded for 2.0.6 hardening in the
review's order, with what 2.0.5 already covers marked:

1. **Per-role cost attribution** (the review's "if I only got one"): every
   `CostMeter` entry carries the role and bio that spent it (the sub-agent
   runner knows its role); `/stats` and `halo stats` show spend by role,
   cost per task and cost per accepted result, so a role assignment can be
   judged by evidence.
2. **Acceptance-gated sub-agent returns**: when a sub-agent returns, the
   judge role checks the result against the bio's `acceptance` criteria;
   a failure gets one retry with the critique appended; a second failure
   escalates with the failure marked. 2.0.5 round 5 (team control) enforces
   the lineup's `pipeline` gates and `escalation`; 2.0.6 takes whatever
   part of this round 5 leaves open (the per-bio acceptance check on every
   live return, the critique retry).
3. **Session replay for model swaps**: record a native transcript, replay
   it against a different model with the same tools and the same
   transcript prefix, compare the outcomes side by side ("did swapping the
   researcher from one model to another help?" answered with a diff). This
   extends the gym from synthetic evals to real task history.
4. **Parallel native tool calls**: one turn may issue several independent
   read-only tool calls (Read, Grep, read-only Bash) that run in parallel;
   writes stay sequential; the worktree seed covers the dangerous case.
   The wire already supports it (learned params watch the parameter).
5. **Turn checkpoints, the file-state `/rewind`**: snapshot the changed
   files at each turn boundary (stash-style or a file history) so one key
   rolls back a turn's edits after a bad agent run; pairs with item 2's
   retry loop and with permission mode auto.
6. **Roles hygiene**: `template load` flips `roles.enabled` (DONE in 2.0.5
   round 2b); `halo doctor --roles` runs the lineup editor's warning set
   headlessly (dead endpoints, judge in the same model family as coder
   = self-preference bias, not exactly one `role: main`).
7. **Publish and sign releases**: a real GitHub Release per tag (DONE in
   2.0.5 round 2b: notes from the CHANGELOG) plus a checksummed artifact,
   and `halo update` verifying the signature or the tag before installing.

These join the 2.0.6 hardening list in the "REORDERED 2026-10-05" section
(soak and watchdog, MCP connects off the startup path, gym cloud ranking,
the carried fix-pass minors, invariants extended) and the round-2 deferrals
(Try it and smoke runs, export and import bundles, the test-runner
SystemExit fix). Order inside 2.0.6 is decided when 2.0.5 ships; item 1
goes first per the review.

## ADDED 2026-10-06 ~12:45 (rolo): 2.0.5 round 2d "the old name is gone; a README worth looking at" -- right after round 2c

rolo: "Drop all mentions of <old-name> in GitHub, we are far beyond that.
I need better screenshots in the repo too, make it lots cooler, like ascii
art, more visual and etc. Definitely when we add more of the themes."

Measured 2026-10-06 12:45: the previous project name appears in 50 tracked
files outside plans/ (CHANGELOG 92 lines; tests/test_paths.py, the two
installers, docs/INSTALL.md and docs/harness/INSTALL.md, config/paths.py,
doctor.py, providers/config.py, pyproject.toml, theme.py, cli.py, run_all.py)
and 10 files under plans/. In code it is real compatibility: the
`<OLD_NAME>_*` environment aliases (ENV_FILE, THEME, MODEL and more), the
legacy `~/.<old-name>` state-dir migration and doctor's "leftover" checks,
console-script aliases in pyproject, the installers' old command names, the
test runner's real-state guard naming the old directory. The GitHub
description and topics are already clean. The README embeds two images;
ten real TUI renders already exist as SVG under docs/harness/tui-snapshots.

What the round does (brief `plans/briefs/2.0.5/round-2d-name-purge-visuals.md`):

1. **The old name is off the front pages** (rolo 2026-10-06 ~12:50: "just
   don't mention it directly on the first pages of the repo, whatever if
   it's in the change logs"): README.md, `docs/INSTALL.md`,
   `docs/harness/INSTALL.md`, `docs/HANDBOOK.md`, `docs/COMMANDS.md`, the
   package description in `pyproject.toml` and the installers' printed text
   say only `halo` (where a legacy behaviour must be described, say "the
   previous name" or "pre-2.0 installs"); the CHANGELOG, the compatibility
   code, its tests and plans/ history stay as they are; a house invariant
   refuses the string on exactly those front pages from now on.
2. **A README worth looking at**: an ASCII-art banner, a "what it looks
   like" gallery of real TUI renders produced by a reproducible script
   (`scripts/screenshots.py`: Textual pilots over fixture data, SVG out
   under `docs/screenshots/`, one per scene: first launch and intro line,
   a turn with a tool card and the phase line, the model picker with its
   columns, the wizard's Team step, the `/mcp` dialog, the permission card,
   the status bar with balances), captions in one sentence each, a feature
   grid, install in three lines, and a themes section that 2.0.8 fills
   with one render per theme (DOOM, Metroid, Mario); the same banner shows
   on `halo --version` and the intro line pool gets it as the first line.
3. Git history and the CHANGELOG keep the old name; no rewrite (the
   owner's call, 2026-10-06 ~12:50).

## ADDED 2026-10-07 (rolo): cyber scope triaged — what lands in the harness vs halo-hacker

Source plans (Kali VM, ~/Documents/vibes/appDev/): halo-harness-cyber/PLAN.md
(the five pillars) + halo-hacker/PLAN.md (the distributable product, v0.1
built). The owner triaged the pillars 2026-10-07:

**KEPT (harness chassis):**
- Pillar 1.1-1.3 — filter-aware routing: finish_reason/content_filter/
  null-content detection on every response (a filtered refusal is never
  persisted as an answer), per-provider filter profiles MEASURED
  (census-style, not datasheets), transparent reroute of filtered content
  to a filter-free lane. (Pillar 1.4 engagement-scoped context hygiene
  moved OUT.)
- Pillar 2 — verify-everything telemetry: the preflight gate (tools
  verified by effect, tool-call capability by measurement, one canary per
  lane, exit-code gated), continuous canaries during long runs (truncation
  prompt_eval_count-vs-sent, budget burn, response completeness), role
  binding from the census registry.
- Pillar 5 minus fleet: the Governor + lanes — ALREADY SHIPPED as 2.0.5
  round 4 (60fba96).

**OUT (halo-hacker / serverMode territory — never this repo):**
- Pillar 3 — the engagement object (scope wall, evidence store +
  hash-chained audit ledger, findings gates, report generation).
- Pillar 4 — safety-as-architecture (human-gate flags, argv containment,
  engagement isolation, leakcheck, the PII engine).
- Pillar 1.4 — engagement-scoped context hygiene.
- Pillar 5's fleet layer — NO multi-machine/federation work in the harness
  (ed25519 node identity, mTLS, signed envelopes, trust tiers: all out).

**Not triaged by the owner (defaults, override anytime):** proxy-native
HTTP (Caido/interactsh) -> default OUT to halo-hacker (tooling, not
chassis); on-box local-models-only engagement mode -> default OUT
(engagement-flavored; halo's existing offline mode covers the generic
case).

**Placement — DECIDED 2026-10-07 late (rolo: "put those at the head of
2.0.6" = the next release, 2.0.7, as its FIRST rounds): "I want to
implement all cyber features suggested previously that would have
snagged a pen tester like me using a harness, this is supposed to remove
the restrictor plates. NO FLEET features, just what we agreed on."**
So 2.0.7 opens with:
1. **Filter-aware routing (Pillar 1.1-1.3)** — first release round.
2. **Verify-everything preflight + canaries (Pillar 2)** — second.
Both ahead of embeddings/wizard/copy. Everything OUT stays OUT
(engagement objects, safety-as-architecture, fleet: halo-hacker /
serverMode, never this repo).

## ADDED 2026-10-07 night (rolo, live reports from the 2.0.6 release
session): 2.0.7 round 0 "session UX" — two fixes from the owner's own
usage, landing BEFORE the cyber pillars (small, surgical)

1. **DONE already (03d54e7): steer text renders instantly.** A steer
   typed mid-turn showed only "↳ steering…" while the words sat
   invisible for 60s+ (the apply-time bubble assumed "moments later";
   a turn parked inside a sub-agent call breaks that assumption). The
   bubble now renders at submit; apply-time duplicate suppressed.
2. **Notice delivery must stop impersonating the user (round 0b):**
   when a background job or sub-agent finishes while the session is
   between turns, `_apply_pending_job_notices` /
   `_apply_pending_agent_notices` deliver the completion as a
   USER-ROLE message merged into the next turn — so the model reads a
   status blob interleaved with the owner's actual question and
   answers the status first ("typing a question, getting a blob back
   of what's been done, then an answer is not a good flow" — rolo).
   Redesign: deliver pending notices as clearly-marked SYSTEM-role
   status blocks (a distinct log kind + context-builder rendering with
   an explicit "status notices — answer the human first, fold these in
   only where relevant" frame), placed AFTER the human's message in
   the turn. Print mode keeps its current behavior.
3. **Steer-through-tool-calls (round 0c, deeper):** steers apply only
   at safe points BETWEEN tool calls — a steer arriving during a
   running sub-agent or long Bash waits for it to finish (the 60s+ lag
   above). Direction: the per-call loop notices a pending steer, and
   (a) long-running Bash gets the existing kill/abort plumbing, (b) a
   foreground sub-agent gets the steer FORWARDED into itself (children
   already share the parent's abort Event — H6 scope B) so the human's
   words reach the work instead of queueing behind it. Cost guard: an
   interrupted child's partial work is preserved in its log (resumable
   via task_id) before any abort.

## ADDED 2026-10-08 (rolo: media roles + a secretary before the
orchestrator): 2.0.7 round 0e "concierge + media" — one secretary that
is also the eyes, one media agent, not three

Live catalog resolve (the deciding data): `z-ai/glm-5.3-flash` is
vision=True at $0.15/M in + $0.50/M out (1,048k ctx) while the main
`z-ai/glm-5.3` is vision=FALSE at $7.00/M out — the main model CANNOT
see the screenshots the 0d fix now pastes. deepseek-v4-pro/-flash:
blind. qwen/qwen3.8-flash: vision=True.

**The concierge role (secretary + eyes), glm-5.3-flash:**
- quick Q&A and "what's been done" updates answered WITHOUT waking the
  orchestrator (~$0.0004/answer; reads plan files + session log
  deterministically for status, near-zero tokens);
- media first-look: image present + active model blind (always, today)
  -> the concierge describes it, the description enters context;
- the round-0b notice blob lands with IT, never interleaved into the
  human's question.

**One media agent, not three (video/audio/display):** ingestion is
deterministic tooling, not model choice — video -> ffmpeg frame
extraction (local, free) -> images; audio -> whisper on the 4090
(local, free) -> transcript; screenshots already work. All converge on
image blocks or text; the only model question is vision lane or not,
and ModelProfile.vision already answers it.

**The router piece:** media present + blind active model -> route to
the eyes lane automatically (today the image rides as a path mention
with a notification — graceful but useless). The census pattern from
cyber Pillar 2 (measured canary image per lane, not datasheets) also
catches lying vision flags (catalog says google/gemini-3-flash
vision=False — suspicious, census target) and dead model IDs.

**Sequencing (cyber pillars stay first per the standing order):** 0e
lands AFTER rounds 1-2 (filter-aware routing, preflight/canaries) —
the concierge benefits from the census the canaries build. Template
work joins the wizard deep-review round (they are the same surface).

## ADDED 2026-10-09 ~23:10 (rolo): the subscription routes are off until the user accepts the terms risk (2.0.7 fix pass round 7b)

rolo: "I did not know that using the claude subscription in another harness
would result in a ban. If so we need to have a huge alert that tells people
this might happen. If halo discovers subscription creds that might lead to a
ban, that feature should be off by default and then a big alert and
acceptance needs to happen before that even turns on."

The facts (verified in the tree the same evening): Halo never reads the
Claude Code OAuth token or Codex's credentials; `cc:` drives the official
`claude` binary in its documented headless mode and `cx:` the official
`codex` binary; both still use a personal subscription through a
third-party harness, the provider's terms govern the account, and there
have been public reports of account restrictions for tools that use
subscription tokens outside the provider's own products. Decision: `cc:`
and `cx:` are OFF by default (fresh and upgraded installs), every surface
that would use one opens a notice with those facts and the providers'
terms, acceptance is typed (`I accept`) and stored with date and version,
`halo subscriptions status|accept|revoke`, `/subscriptions`, doctor and
`/providers` show the state, README and MODELS.md carry the warning. A
consent gate the owner chose for his users, never safety or refusal
logic. Brief: `plans/briefs/2.0.7-fixpass/round-7b-subscription-consent.md`;
runs right after round 7, before round 8.
