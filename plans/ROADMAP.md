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

## ADDED 2026-10-09 ~23:45 (rolo): Ctrl+C copies; a second press asks before quitting; PowerShell never kills the session (2.0.7 fix pass round 7c)

rolo: "When I press Ctrl+C once in a Halo session in PowerShell, it closes. I
need Ctrl+C for copying. The first Ctrl+C should copy; if a user does that
twice they probably want to quit, and a popup should show confirming they
want to quit Halo."

Halo already had a double-press design (first press interrupts or notifies,
second within a window quits), so the single-press close is the Windows
console delivering Ctrl+C as a control event before the key reaches the
TUI. Round 7c: own the key on the Windows console for the TUI's lifetime;
first Ctrl+C copies the selection or the last reply (never interrupts a
turn; Esc does that); second press within 3 s opens a Quit Halo? card
that never quits by itself; `quit_on_double_ctrl_c: false` makes the
second press copy again. Brief: `plans/briefs/2.0.7-fixpass/round-7c-ctrl-c.md`;
runs right after round 7b, before round 8.

## ADDED 2026-10-17 (rolo: "Add all of those suggestions"): four OpenFlow ports -- two into 3.0.7.0, three as 3.0.9.0 "Hand-offs and the graph"

rolo asked (2026-10-17 morning) whether anything in OpenFlow is worth
adding. Two MIT projects carry the name: philbotar/OpenFlow (a Rust/Tauri
agent harness: a workflow graph of agent nodes with hand-offs, parallel
dependency layers, per-node models, a post-run review) and
SeeRay11/OpenFlow (a canvas on the opencode engine: role cards wired into
a pipeline, a per-node model test, a pre-flight that refuses missing
agents). Neither has anything Halo lacks at the engine level (parallel
lanes with claims, human gates, flow files in the repo, auto/ask with every
decision journaled, steer and take-over, mixed providers, MCP reconnect
are all in). Four ideas are worth porting; one is deliberately NOT taken.

**Into 3.0.7.0, as part of the Roles port (small, wiring on what exists):**

- **"Test this model" button** in the bio editor and the lineup editor:
  one click sends a one-token probe to the lane's model ref and shows
  ok / the error, the same probe `halo doctor roles` runs. Also on the
  Team step of the wizard.
- **Run-start preflight**: `halo orchestra run`, `halo flow run` and a
  mission start refuse a lineup with a dead model id, a missing bio or a
  tool allow-list that names no tool, naming each problem and the fix,
  instead of letting sub-agents come back empty (the 404-silently case the
  doctor check already finds after the fact). `--force` runs anyway.

**3.0.9.0 "Hand-offs and the graph"** (after Team 3.0.8.0; medium rounds,
one Opus worker each, in this order):

- **R1 Hand-off artifacts with per-lane context control.** Each Orchestra
  lane and each Mission part declares what it hands downstream (files,
  a summary, a named artifact) and each downstream lane declares what it
  may see (upstream output, the goal only, a named artifact). The
  sequenced Mission part then starts from the earlier part's head, not the
  mission base (the open 3.0.6.0 item). Shown in the run console and the
  mission panel as an edge label.
- **R2 The editable, validated graph between plan and run.** Orchestra
  plans lanes from the goal today and runs them; the Studio step in
  between: the planned lanes on a canvas (the Roles canvas look), drag to
  reorder or re-parent, set each lane's bio and model, add or drop a lane;
  Run refuses cycles, broken edges, a lane with no bio and the preflight
  problems above. The same canvas opens a saved flow. "Draft with AI"
  is the existing planner; this round only makes its output editable.
- **R3 The post-run coach.** After a run (Orchestra, flow, mission) an
  advisory card: which bio's prompt to tighten and why (from the pieces
  sent back), which lane should have had a cheaper or stronger model
  (cost and return-cap evidence from report.json and events.jsonl), which
  tool allow-list blocked work (denied calls), which lanes waited on each
  other. Advisory only: it writes nothing; "apply" opens the bio editor
  with the suggestion filled in. `halo orchestra coach [RUN]` prints the
  same.

**Not taken:** SeeRay11's import of another CLI's stored keys from its
`auth.json`. That is the subscription terms risk decided on 2026-10-09;
Halo's consent gate exists to avoid exactly that.

Sources: github.com/philbotar/OpenFlow, github.com/SeeRay11/OpenFlow
(both read 2026-10-17). Session: the CI flake-fix session that left
master green at 22ec617.

## ADDED 2026-10-18 (rolo: "Love it do all that!"): 3.1.0.0 through 3.1.3.0 -- the assessment after the 3.0.9.0 run, as four versions

rolo asked what could be better, "from ease of use to capabilities", and
said do all of it. The assessment (same morning) named three first: the
first-run experience, too many nouns for one idea (lane / part / stage /
step are one unit of work implemented four times), and the suite's cost
(an hour per CI pass, one shared state dir across 500 modules, Chrome
drivers each scoping by hand; nine of the last ten red runs were test
infrastructure). Then ease of use (discovery, two editors, config in six
places), capabilities (serial scheduling, an advisory-only coach,
delegation unverified on a second machine, per-machine memory, reactive
cost control) and engineering (files split by line count, line endings,
the Windows runner on every push). Ordered so each version makes the next
cheaper. Same cycle as 3.0.7.0-3.0.9.0: one Opus worker per round in a
worktree, briefs outside the tree, suites, push, CI watched to its
conclusion, release gated on the exact sha, install refresh.

**3.1.0.0 "Suite and repo health"** (engineering first: it pays on every push after)

- R1 Test isolation and CI tiers: `tests/run_all.py` gives every module its
  own scoped state dir (a fresh `BRIDGE_TEST_HOME` per module, the real-home
  guards kept, the per-process "scoped once" helper made per-module); one
  Chrome driver base (`tests/helpers/chrome_driver.py`) that scopes the home,
  finds Chrome, runs one headless instance at a time and caches one run per
  argv, with every existing driver moved onto it; the suite split into a
  fast tier (no Chrome, no TUI pilots) and a full tier; the workflow runs
  Linux on every push and Windows on tags, nightly and `workflow_dispatch`;
  a release still needs BOTH platforms green on the exact sha
  (`release.py` dispatches the Windows run for the sha and waits for it,
  so the gate rule holds without a Windows run per push); `docs/CONTRIBUTING.md`
  and `plans/CYCLE.md` say so.
- R2 File hygiene and line endings: `.gitattributes` `* text=auto eol=lf`
  (binaries marked) and one normalise commit; files named by line count
  (`*_more.py`, `*2.py`, `*_io.py` where the split is arbitrary, `design_panel2.js`
  is gone already) re-split by responsibility with the 250-line cap kept;
  `scripts/release.py` and the tests that pin file names updated; nothing
  else in flight while this round runs.

**3.1.1.0 "The first ten minutes"** (ease of use)

- R1 The guided first run: `halo start` (also the wizard's last step and
  Studio's "Start here" overlay on a fresh home): copies a lineup, makes a
  sample repo, runs one orchestra goal with `plan: review`, opens the plan
  canvas, approves, shows the report and the coach, each step one screen
  with one sentence of why; `halo explain <thing>` (lineup, bio, tier,
  team, stage, block, lane, part, flow, mission, gate, hand-off, coach)
  prints the one-paragraph definition the docs and Studio's glossary share
  (`docs/GLOSSARY.md`, `/glossary`, the `?` menu); the Start views link to
  the next section in the story.
- R2 Config and discovery: `halo config where` lists every file in effect
  for this repo and home (config.json, `.halo/`, the active lineup, team,
  flows, env files) with what each sets; `halo doctor --config` checks all
  of them against one schema set and reports conflicts; `docs/README.md`
  becomes the map (one line per doc, by task), the four longest docs are
  split by task, and every doc opens with "read this when".
- R3 One editor: Studio is the editor of record for bios and lineups; the
  TUI's bio and lineup editors become read-only views with `e` opening
  Studio on that item (`halo studio --edit bio:<name>` / `lineup:<name>`),
  the wizard's Team step opens the same; field parity (every field the TUI
  showed exists in Studio's forms); the TUI keeps `/agents` and `/teams`
  listings and the Try it probe.

**3.1.2.0 "One run model"** (capabilities, the big one)

- R1 The unit of work: `halo_harness/work/` holds the shared model a lane,
  a mission part, a team stage and a flow step all are: id, kind, claims,
  reads / writes (hand-offs), state machine, gate, acceptance, cost, the
  ledger line and the report row; the four engines keep their front doors
  and adapt onto it (no behaviour change, every existing test green); one
  ledger format and one report shape, the coach rules written once over
  the shared shape (the four kinds' rules folded into it).
- R2 Scheduling: members of a team stage run in parallel under the tier's
  `max_parallel`; orchestra and flow stages may run on a fleet member
  (`harness:`) through the same path a delegated agent stage uses; a
  downstream lane whose upstream the gate sent back is marked stale and
  re-based (or re-run) before the merge, never merged stale; a cost
  forecast on the plan canvas and in `halo orchestra plan` (catalog prices
  x the lead's token estimate per lane, the run's budget shown against it)
  and a budget line in a team file that stops a stage before it starts.
- R3 Delegation verified and shared memory: the live two-machine check of
  a delegated team stage and a mission part is scripted
  (`tools/live_fleet_check.py`, the owner runs it with his Kali VM) and its
  findings fixed; the recall index is shared across the fleet through the
  hub (`halo recall --fleet`, a member answers a recall query from its own
  index, results merged by score), so a box does not re-learn what another
  already knows.

**3.1.3.0 "The coach loop"** (capabilities)

- R1 The coach asks a model: `coach --model` (and the Coach tab's "Ask the
  model" per card) adds one paragraph per card from the run's own lineup
  lead, with the evidence as its context; Apply writes the change after one
  confirm card (bio, lineup or plan), with Undo; a coach summary line lands
  in the run report and in the Fleet digest.
- R2 The terminal keeps up (DONE 2026-10-19, from the owner's live use):
  periodic repaints in place instead of a screen layout each
  (`tui/widgets/inplace.py`), mouse-report heads held until their tail or
  dropped (never typed) on Windows, size records settled before one Resize,
  the level band at 24 rows and back at once after a resize; then the release.
- Moved to 3.1.4.0: Studio polish from the first-run work, whatever the
  guided run exposed (the owner's notes from his live check come first).

Not taken: moving the Windows suite off the release gate entirely (the
owner's rule stands: both platforms green on the exact sha before a tag).

## ADDED 2026-10-19 ~14:00 (rolo: "Yep dashboard is the way"): 3.1.4.0 "The session dashboard" -- Studio polish from the owner's live check, then one live view of your own session

Why: the owner's live check of 3.1.3.0 (the Fleet view, default layout, one
harness) found the Activity log wrapping one letter per line, the Fleet view
"really busy", and this: Fleet shows far more of what agents and sub-tasks do
than Roles does, and that visibility belongs to the user's own session ("OH!
What about a gui dashboard instead that shows all that on what is going on in
a users session?" ... "I love seeing what fleet does but have that for the
session visualization"). Roles stays the lineup editor (its live rows already
come from the Fleet store: one badge per card, one agent at a time in the
Live tab); the map, the timeline, the log and the attention queue get a home
scoped to this harness and the session you are in.

**3.1.4.0 "The session dashboard"** (capabilities)

- R1 Studio polish from the live check: (1) no Fleet panel wraps a line one
  character per row at the default layout widths: the Activity log line puts
  time, kind and who on one row and the text on a full-width row below when
  the panel is narrow (a container query), the text column keeps a minimum
  width and breaks at words; the same check on Attention rows, Map cards,
  People and the glance faces; (2) a calmer default Fleet layout: People,
  Costs, Attention, Map and Activity open, Mission, Health, Capabilities and
  Agent one click away (the palette and the rail list them as before); the
  Mission panel's five how-it-works paragraphs fold into "How this works"
  once a goal or a plan exists; glance text at 12 px; (3) the two Windows
  timing flakes of the v3.1.3.0 tag run get their margins
  (`test_h5b_f14_command_hook_timeout_kills_the_whole_process_group`'s
  elapsed bound, `test_team_step_ctrl_n_and_ctrl_e_open_studio`'s wait).
- R2 The Session dashboard: a new Studio section **Session** (Alt+8, "This
  session, live") made of the Fleet panels scoped to this harness: Map (one
  card per session on this box, its agent tree, the working node lit),
  Activity (the timeline lanes and the log of this harness, one session when
  chosen), Attention (this harness's rows), Agent (the inspector) and Cost
  (this session's spend, tokens, turns, elapsed, model). No copy of a Fleet
  component: the Fleet stores take a scope (harness, session). Studio lands
  on Session when `?mode=session` (with `&session=<id>` selecting one), or
  when nothing is saved and this harness has a live session; `/studio` in
  the terminal (and `halo studio --session <id>`) opens Studio on the
  session you are in; a working card on the Roles canvas, a run in Orchestra
  and a map node's menu link into it ("Watch in Session"). Fleet keeps
  everything it has; then the release.

Not taken: duplicating the map and the log into Roles (two busy places, and
design time blurred into run time; a working card links to Session instead);
renumbering Alt+1..7 (Session takes Alt+8).

## ADDED 2026-10-19 ~14:35 (rolo: "Actually. Remove orgs and Flow entirely. Too bloated"): 3.1.4.0 R3 "Org and Flow are gone"

Supersedes the "Not taken" line above: Session takes Alt+6 after the
removal, not Alt+8 (the keys are positional).

- R3 Org and Flow are gone. Org in all three senses: Halo's own
  organizations from 2.0.2 (`/org`, `halo org`, `Agent(org=)`, the org
  budget tracker and its approval gates, the wizard's Orgs step, the org
  templates); the Paperclip integration and the Org section; the lineup
  `org:` section with `reports_to` and the Roles "reports" edges. Flow in
  full: the Flow section and rail, `halo_harness/flows`, `halo flow`, `halo
  postiz`, the flow coach rules, Team's stage kind `flow` and the template's
  `post` stage, Mission's part kind `flow`, the Work unit kind `step`, the
  `flow_*` feed kinds, the `flow_gate` attention rows, posts.json /
  metrics.jsonl, Postiz. Media (ComfyUI renders, the Media panels and
  palette commands) stays with Design. Shared pieces move instead of dying:
  the team gate actions, the media render file list, the Media palette
  commands, the Start-view styles, the media Studio test rig. Nothing under
  a user's home is deleted: a leftover `orgs` / `paperclip` config section
  is ignored with a doctor line, a leftover lineup `org:` section warns
  once, a team stage of kind `flow` fails validation naming 3.1.4.0.
  Hotkeys: Orchestra 1, Roles 2, Design 3, Fleet 4, Team 5, Session 6.
  Runs in parallel with R1 and R2; merged last.

## ADDED 2026-10-19 ~16:55 (rolo, live check of 3.1.3.0: "The roles and other agent studio gui sections needs the drop downs of model selections there or to be much clearer"): 3.1.4.0 R4 "The model is where you look"

- R4 The model is where you look: one compact model select (the catalog
  grouped by provider, the resolved model named beside it, "more..." opens
  the full picker table, Test runs the one-token probe, an empty catalog
  says why and offers Refresh) wherever an agent is configured. Roles: the
  Inspector shows it above its tabs for the selected card ("runs on:
  <model>"; it writes the slot's override; a link changes the bio's own
  model), the canvas card's model pill is a click that focuses it, the bio
  form puts MODELS first with the picker table folded. Orchestra: the goal
  form shows it without opening the disclosure. Design: the new-project
  dialog and the Projects panel use it. Team: a stage shows the model it
  resolves to with a way to change it. Runs in parallel with R3; merged
  after it.

## ADDED 2026-10-19 ~18:10 (rolo: "Add 1 and 2 from Google harness research"): 3.1.5.0 "The coach probes" -- tiers on the canvas, then two ideas from Google's Harness²

Why: Google Cloud AI Research's Harness² (arXiv 2610.14224,
github.com/google-research/harness2, Apache-2.0, 2026-10-09) improves the
harness around a frozen model. Per task it proposes two candidate harnesses
(an invariant one for planning / tool use / context / delegation, a domain
one for procedure and constraints), runs each on the same task, contrasts
trajectories and deliverables with a reference run and composes, citing
what it saw; across tasks a reflection step keeps an improvement library
(an adopted harness plus an EXPERIENCE file: when it applies, the lessons,
the evidence) that later proposals draw on. Its eight harness components
are Halo's bio, lineup, skills, memory and hooks; Halo's coach proposes and
applies with Undo but never probes. The paper's ablations: no library -3,
no split editors -3 to -4, no composition -2 points; naive self-refinement
without a reference run and probes made coding worse. Also here: the tiers
round the owner asked for on the Roles canvas the same day.

**3.1.5.0 "The coach probes"** (capabilities)

- R1 Tiers on the canvas (the owner, 2026-10-19: "how do I create custom
  tiers ... a media tier ... trigger that whole tier ... much easier to add
  in the canvas"): an Add tier button in the canvas bar (name it, an empty
  box appears, drag cards in, rename inline); a tier `model` its members
  inherit unless a bio overrides it (the 3.1.4.0 model select on the tier
  box); a tier `trigger` (schedule, file_change, event, message) that starts
  the tier's lead with its members available; the tier box's own menu
  (rename, model, trigger, max_parallel, delete); a single tier lays its
  members out under main as a tree with the routing-word labels clear of
  each other (they overlapped and read as a chain).
- R2 The coach probes (Harness², task level): `halo coach <run> --probe
  [--k N]` and the Coach tab's Probe button. The run's lead drafts two
  candidate overlays for the run's lineup and bios (invariant: planning,
  tool use, context budget, delegation; domain: procedure, knowledge,
  constraints for this goal); each candidate runs the same goal again in
  its own worktree under the run's budget cap; the judge bio compares the
  anonymized deliverables and trajectories with the reference run; the
  coach composes (merge, adopt one, or keep) with a why line that cites
  what it saw; Apply writes the composed overlay with Undo, as today. k
  parallel candidates when asked; off by default; the cost shown before the
  probe starts and in the report ("probe: k runs, $X, picked: ...").
- R3 The improvement library (Harness², harnessing level): every Applied or
  probe-adopted overlay lands in `~/.halo/coach/library/<entry>/` as the
  overlay files plus EXPERIENCE.md (when it applies: the project, the goal's
  words, the lineup; the lessons; the evidence: the contrast that supported
  it). The next run starts from the base lineup; the coach cites matching
  entries in its proposals ("three earlier runs like this adopted ...");
  `halo coach library` lists, shows and forgets entries; the fleet shares
  entries through the hub's recall (`halo recall --fleet`), so a box reuses
  what another learned; then the release.

Not taken: letting library entries inherit automatically (the paper keeps
the base harness and reuses only through proposals, and so does Halo: Apply
after one confirm, with Undo); an in-run editor that rewrites the harness
mid-task (the probe runs are whole runs, judged at the end).

## ADDED 2026-10-20 ~00:20 (rolo: "I have some GitHub and app changes. Trying to focus halo harness"): 3.1.5.0 "Focus" -- two removals, Session and Roles polished, the front page; "The coach probes" becomes 3.1.6.0

Why, in the owner's words after the 3.1.4.0 release: "as we developed we
created some cool stuff that might outshine where we started. I think
studio should be featured more in GitHub." "Honestly remove the
subscription model listing like the claude code subscription and whatever
OpenAI codex does. It's just not worth it to do that, remove that and
update even mentioning that model provider mention." "Steering and
watching a model think part isn't something new, but how we see how all
the agents talking more and visualizing tie jobs like I see in fleet, which
will be in the new dashboard ... that really shows you the model and flow
thinking. When that is available we need that featured." "The dock that
cannot hide can go from speaking to it. More about the parts of each studio
tab like agents and more info how that glow looks and goes, what parts of
each studio does. We can remove much of the talk about the design part in
studio. We can keep it but not the main direction. Also remove all the game
themes like doom and Metroid, unnecessary at this point. Remove mentioning
code review with a judge and don't mention you can add signal to this. One
paste instead of screenshots can be removed from the feature page too."
"Dashboard and roles I think should be the biggest focus of studio with
lots of graphics along with a more polished look and feel."

**3.1.5.0 "Focus"** (product and front page)

- R1 The subscription routes are gone: the Claude Code (`cc:`) and Codex
  (`cx:`) subscription routes, their providers, login detection, the
  consent machinery (`halo subscriptions accept|scrub|status`, the scrub
  that rewrote refs to OpenRouter equivalents), their catalog and picker
  rows, wizard rows, config keys, docs, glossary words and tests. The
  API-key providers (`ant:`, `oai:`, `or:`, `dbx:`, `ol:`, `hf:`, `xp:`)
  are untouched; a `cc:`/`cx:` ref left in a file or on `--model` is one
  clear line ("removed in 3.1.5.0: use an API route, e.g. ant:...").
- R2 The game themes are gone: the 2.0.7 theme pack (DOOM, Metroid, Mario,
  Beetlejuice, Alien), the level band and its scenes, the HUD status-bar
  skins, `/doom` `/metroid` `/mario` `/beetlejuice` `/alien` `/level`, the
  theme intro lines, the animated level captures and theme screenshots,
  the wizard's game rows, their docs and tests. The ordinary themes stay
  (the status bar is always the ordinary one). A saved game theme in
  config.json falls back to the default theme with one line.
- R3 Session and Roles, polished: the two sections the owner wants Studio
  known for get the full holo treatment (plans: the visual direction of
  2026-10-13 -- glass panels, HUD brackets, cyan + amber, mono data,
  restrained motion). Session: the map's working node and its edges glow
  and settle with the agent's state, the agent tree reads as one picture
  (who spawned whom, what each runs on, what it costs), the Cost panel
  draws a context-fill bar and spend over time, a tool's running time on
  the node. Roles: the card's live glow explained by the card itself (a
  legend on hover: working, waiting, done, failed), the tier boxes and
  routing edges drawn with the same brackets, the MODEL strip and pill
  finished, the canvas empty state inviting. The Session landing layout (the owner,
  00:35: "I just like the visualization of what I saw the one agent doing
  while I was in the fleet tab. I want that kind of insight going. Like the
  entire right side on the dashboard landing page is like scrolling
  visually seeing everything working in real time"): the map and the cost
  on the left; the ENTIRE right side one live, auto-scrolling column of
  everything working now -- every live agent's thinking, tool calls and
  output interleaved as they happen (the Agent panel's three streams, for
  every agent at once), each line tagged with its agent and lit with its
  state, a click pinning one agent's stream, Follow on by default. Both
  sections get an animated capture (SVG or GIF through the existing capture
  tools) for the page.
- R4 The front page: README.md (and the GitHub repository description and
  social preview) lead with Halo Studio, Session and Roles as the biggest
  focus with lots of graphics: the Session dashboard and Fleet's agent map
  as the headline ("how we see all the agents talking ... really shows you
  the model and flow thinking"), the Roles canvas with the live glow (what
  it looks like and when it comes and goes), then each section's parts --
  Orchestra, Fleet, Team -- with Design kept short. Steering and watching a
  model think stay, but no longer lead. Gone from the page: the
  subscription section, the dock that cannot hide, code review with a
  judge, remote control from Signal, one paste instead of screenshots, the
  levels. The feature table and the comparison follow the same cut.
  docs/README.md's map and the captures follow. Then the release.

**3.1.6.0 "The coach probes"** = the section ADDED 2026-10-19 ~18:10 above
(R1 tiers on the canvas, R2 the coach probes, R3 the improvement library),
unchanged, after 3.1.5.0.

Not taken: removing the judge, the Signal bridge or the clipboard paste
themselves (the owner said "remove mentioning"; the features stay); removing
Design (it stays, shorter on the page).

## ADDED 2026-10-20 ~08:20 (rolo: "Omg keep going do not stop"): 3.1.6.0 starts at once; R4 a Studio hero

3.1.6.0 "The coach probes" (R1 tiers on the canvas, R2 the coach probes, R3
the improvement library, as ADDED 2026-10-19 ~18:10) starts right after the
3.1.5.0 release, no pause. One round joins it:

- R4 A Studio hero: `docs/media/hero.svg` (`tools/hero_svg.py`) still says
  "for people who'd rather not be locked into one AI coding ecosystem" with
  five model chips -- the page now leads with Studio. The hero becomes the
  wordmark over the Session dashboard (a crop of `studio-session.png` with
  the Live column), one line "The Claude Code-compatible harness for any
  model, with Studio: every agent, live", and the social preview
  (`docs/media/social-preview.png`, 1280 x 640) the same picture; the
  README's first image and alt text follow; `tools/hero_svg.py` gets the
  image path (Pillow for the PNGs, the SVG embedding the crop) and
  `--check`. The GitHub social preview itself is a hand upload (no API):
  the owner uploads the PNG once.

## ADDED 2026-10-20 ~10:30 (rolo, live on Kali: "Copying the words in a session chat text not yet sent does not work. I can't copy the text then paste it somewhere else."): 3.1.6.0 R5 copying the draft on Linux

- R5 Copying the draft out of the TUI on Linux: `Ctrl+Shift+C` and `/copy
  draft` copy the whole prompt draft; a selection + Ctrl+C keeps copying the
  selection; every copy says what landed (the tool, OSC 52, the count) and
  on a Linux box with no `xclip` / `wl-copy` / `xsel` names the apt install
  and ALSO writes the text to `<state>/clipboard.txt` so the words are never
  lost; `halo doctor` gets a clipboard row with its fix; one status hint the
  first time a mouse drag lands ("hold Shift to select with the terminal").
  Stock Kali terminals ignore OSC 52 and ship none of the tools, which is
  what the owner hit.

## ADDED 2026-10-20 ~11:50 (rolo: "The session tab should be the first tab in studio"): 3.1.6.0 R6 Session is the first tab

- R6 Session is the first tab: the Studio sections run Session (`Alt+1`),
  Team (`Alt+2`), Roles (`Alt+3`), Fleet (`Alt+4`), Design (`Alt+5`),
  Orchestra (`Alt+6`) -- the owner's own list of 2026-10-20 12:40
  ("session, team, roles, fleet, design"; Orchestra was not in it and keeps
  the last key until he says otherwise). One registry (routes/index.tsx SECTIONS) is the order; the rail, the
  palette, the Start view, the F1/`?` key help, the section help pages, the
  modes banner (tools/studio_modes_banner.py -> docs/media/studio-modes.png)
  and every doc line that names an `Alt+N` follow it. `/studio <section>`,
  `halo studio --fleet|--session` and the section ids never change. Studio
  still lands on Session when a session is live and on the Start view
  otherwise. Pinned: the order and the keys in Chrome; a docs check that no
  `Alt+N` line disagrees with the registry.

## ADDED 2026-10-20 ~12:15 (rolo, with a photo of the Fleet view: "I want what fleet has with tool running too within the session tab. More of insight and ability to jump in and steer is awesome. I like what you got going in session tab right now too"): 3.1.7.0 "Session: the insight and the steer"

Runs right after 3.1.6.0 ships (its worker starts at once, in parallel).

- R1 Session has what Fleet has, and the steer is always at hand: the Live
  column keeps its narrative rows (what each agent types, every tool call
  with its target and running clock, its result, what it hands back) and
  gains Fleet's Activity structure in the same column -- a time stamp and a
  KIND tag (TOOL / TEXT / STATE / ASK / YOU) on every row like the Fleet
  log's columns, the timeline strip (one lane per live agent, 5 / 15 / 60
  min, a lane click pins that agent) above the rows, an agent select and a
  kind select beside Follow (pin stays); the Steer box sits at the bottom
  of the column at all times, addressed to the pinned agent or, with none,
  to the session's main agent, with Pause and Stop beside it, and every
  agent tag and map node has "steer" one click away (click = pin + the box
  focused). The Activity panel stays as the long history. Pinned in Chrome:
  the columns, the strip, the filters, a steer sent from the column with
  nothing pinned reaches main and echoes as YOU.

Not taken: a second log panel open by default (one column, as the owner
likes it); changing the Fleet view.

- R2 Captures carry no real names (found by the Session-first round,
  2026-10-20): the committed studio-orchestra.png and
  studio-orchestra-coach.png show the build host's real `<user>@<host>`
  harness name in the rail's Fleet tree and the start of a real home path
  in the Goal panel's TEST COMMAND field, because tools/capture_orchestra.py
  (and the capture tools that share its rig) read this machine's harness
  identity and the seeded repo's absolute test command, and the privacy
  check scans SVGs only. Every capture tool seeds a placeholder identity
  (`you@studio`) and a repo-relative test command; every PNG and GIF is
  re-captured; the capture rig refuses to run when the identity it would
  draw is the real one; test_privacy_scan gains a check that the capture
  tools never read the real identity (the tools' source, not OCR).

## ADDED 2026-10-21 ~00:10 (the owner pasted an outside review of the repo, 2026-10-20: "a multi-model agent harness with a multi-agent orchestration layer and an integrated control plane"; its five directions, checked against what Halo has): 3.1.8.0 "The supervisor"

What the review got right and what Halo already has: the agent is separate
from the model (bios, lineups, tiers, one model order); Orchestra splits,
runs, merges, judges and gates; schedules and triggers run jobs but disarm
when their session closes (docs/AGENTS.md); a run that stopped on a crash
resumes once (docs/ORCHESTRA.md "resume: picking ..."); a budget is a
forecast that warns, never a stop; the coach, the probes and the library
(3.1.6.0) learn from runs after the fact; recall spans memory, sessions and
the library across the fleet. The gaps the review names, in Halo's words:

- R1 The supervisor: `halo supervise` (and Studio's Session landing when it
  runs): a daemon that owns a goal queue (`halo goal add <what> [--repo]
  [--budget]`), starts each goal as an Orchestra run or a plain `halo -p`
  job without a TUI, keeps every schedule and trigger armed while it runs
  (a session no longer has to be open), resumes a run from its last
  checkpoint after a crash (events.jsonl + lanes/*.json already carry it),
  enforces `budget_usd` as a stop (hold_if_over for the whole queue, not a
  warning), and parks every decision it cannot take (an ask, a plan review,
  a gate return past the cap) in Attention with one key each. The morning
  view: Studio opens on what finished, what waits on you, what it cost.
- R2 Replanning while it runs: the supervisor watches a run's forecast,
  returns and blocks; past a threshold it asks the lead for a new plan for
  the lanes left (a different model for a lane, a split, a second
  specialist, a retry with the contrast as context) and re-approves it
  through the same plan review (auto when `supervise.replan: auto`).
- R3 Verified outcomes: every agent task ends with evidence of its kind
  (code: the test run; research: the sources fetched; a security check:
  the reproduction), the judge reads the evidence, not the summary; runs.json
  keeps outcome, cost and kind per bio and model; `halo models --measured`
  and the Roles pill show measured success per model and task kind, and a
  lineup may route by it (`models.preference: measured`).
- R4 Knowledge that outlives a session: verified findings and decisions as
  first-class recall kinds (`finding`, `decision`), written by the judge and
  by Apply, carried over the fleet like the library; an agent cites what it
  reused; the owner's Obsidian vault as a recall source (a folder of
  Markdown the index reads).

- R5 Opt-in isolation (the owner, 2026-10-21 00:30: "apply all those
  suggestions"): nothing changes by default; a lineup or a bio may declare
  `isolation: container|user` for its workers' worktrees (a per-run
  container image or a scoped OS user, the same worktree inside), `secrets:
  broker` with a secret broker (1Password CLI first) feeding a bio's `env`
  at spawn instead of the host's environment, and `tools.capabilities` (a
  list a lineup declares; an agent sees only those tools). Each is a
  doctor row and one line in the run report when on.

- R6 Studio keeps up with the terminal (the owner, live, 2026-10-21 ~03:30:
  "There is a delay between what I see in halo terminal and what is
  displayed in the session tab of studio. The money count didn't match for
  a minute. Let's make sure what is in halo studio is real-time of what
  the terminal view of halo shows"): the session publishes its running
  totals (cost, tokens in and out, turns, the context fill) as a frame at
  every model-call end and every state change, Studio's Session tab reads
  cost, turns and state from frames first and the GET row only as a
  fallback, every cache or heartbeat on that path is named with its delay
  and either removed for the local harness or cut to under a second, and a
  test holds the Session tab's cost to the terminal's figure within one
  second on a live rig.

Not taken: "explicit approval boundaries for dangerous actions", permission
classifiers and refusal language (the owner's standing direction: auto mode
allows everything except explicit deny/ask rules; nothing is added "for
safety"). The review's public one-liner became the GitHub description on
2026-10-21 00:25 (`gh repo edit`), and its four-paragraph description the
README's opening, by the owner's word.

## ADDED 2026-10-21 ~01:25 (the owner pasted "HALO HARNESS: EXPANSION PLATFORM AND AGENT ORCHESTRATION DEVELOPMENT", a ten-phase implementation program: "one harness, one Studio, multiple independently maintained capability packs"): 3.2.0.0 "Packs"

The program's phases map to rounds; its Phase 7 (the persistent supervisor)
IS 3.1.8.0 R1 and is not repeated here. Every round: reuse the registries
Halo has (shipped templates, agents/teams load order, skills, hooks, MCP,
the config schema, Studio's section registry and panel specs, the palette,
Fleet's capabilities catalog, work/adapters, recall kinds), versioned
public contracts, backward compatibility (the six sections and every CLI
unchanged with no pack installed), tests for malformed manifests,
incompatible versions, missing dependencies and uninstall, Linux and
Windows. Permissions are explicit rules the user sets (deny/ask lists,
capability lists a pack requests and the user grants); no classifier, no
refusal language, nothing "for safety".

- R1 The audit and the contract, the manifest, the registry, the lifecycle
  (Phases 1-2): a brief inventory in docs/PACKS-inventory.md; `pack.yaml`
  (id + namespace, name, version, description, author, license,
  `halo_api: {min, max}`, capabilities, requires, contributions: agents,
  teams, skills, workflows, tools/mcp, studio, fleet, artifacts, events,
  config schema, permissions requested, migrations); discovery under
  `~/.halo/packs/<id>/` and `<repo>/.halo/packs/<id>/`, validation,
  dependency and compatibility resolution, conflict detection;
  `halo pack list|inspect|install <path|git>|enable|disable|update|remove|
  doctor` (names checked against the CLI conventions); a disabled pack
  changes nothing; remove keeps user-made artifacts and config; the stable
  surface `halo_harness/ext/` (`HALO_API_VERSION`, the typed contracts) so a
  pack never imports internals; docs/EXTENSION_API.md (status per section:
  stable / draft / planned) with machine-readable schemas (JSON schema for
  pack.yaml) and fixtures; `plans/PACKS-PROGRESS.md` (done, open
  dependencies, test results, decisions).
- R2 Roles and lineups from packs (Phase 3): a pack's bios, instructions,
  model capabilities (never one provider), tool and permission needs,
  memory namespaces, budgets, delegation rules, lineup templates, workflow
  assignments, acceptance checks; namespaced ids `<id>--<name>` (R1 settled it: a `/` breaks the bio and lineup name rule and file names); user and
  project definitions keep precedence; Studio's Roles groups templates by
  pack with preview, clone, customize, apply; apply never overwrites a
  user-defined bio without a confirm.
- R3 Studio contributions (Phase 4): a versioned contribution registry:
  sections, panels, tabs in existing sections, template categories, Fleet
  badges and inspectors, event renderers, workflow visualizations,
  artifact viewers, config forms, palette actions, Attention views;
  contributions load through one controlled mechanism (a declared bundle
  under the pack, loaded by the Studio server with the pack's id and a
  typed data contract, no core file patched); nothing shows for a disabled
  pack; the auth, local-first and privacy model unchanged.
- R4 Fleet capabilities from packs (Phase 5): packs register worker
  capabilities (tool adapters, runtimes, environments, hardware, model
  availability, platform, capacity, data locality, execution permissions
  required); missions and recommendations use them; a task gains no
  permission because another machine can run it (the worker enforces its
  own rules); advertisements carry no credentials, private paths, tokens or
  environment; pack-specific inspectors and mission metadata.
- R5 Workflows and artifacts (Phases 6 and 8): a declarative workflow
  format on top of Orchestra (prerequisites, typed inputs and outputs,
  sequential and parallel stages, conditions, role assignment, capability
  needs, human gates, retries, timeouts, budgets, verification with
  evidence, completion conditions, resumable checkpoints), runnable on any
  compatible model; typed artifact schemas and viewers; events as typed
  publications with subscriptions; task / project / long-term context
  namespaces per pack with provenance, retention and explicit sharing;
  built on recall, the coach library, hand-offs and the EventBridge.
- R6 The Pack Manager in Studio and the reference pack (Phases 9-10):
  discover, capabilities, dependencies, requested permissions, enable and
  disable, model and tool settings, templates, presets, compatibility
  warnings, health, update, uninstall; trusted local and configured sources
  only; a generic "Documentation Review" pack (a reviewer bio, a writer
  bio, a review workflow, a Studio review panel, a typed review report
  artifact, a Fleet capability requirement) that installs, runs, renders
  and uninstalls without a core change -- the regression test and the
  third-party guide.
- R7 Compatibility hardening and the docs (the program's slice 9):
  migration and rollback procedures, the contract's status table final,
  fixtures for every failure mode, the release.

Not taken: a public marketplace (the program says not for the first
release); any pack mechanism that patches core files; a second
orchestration engine beside Orchestra.

### After 3.2.0.0 (the Packs program's open points, carried by R7 from plans/PACKS-PROGRESS.md)

- the supervisor's goal queue (`halo goal add --lineup`) and Studio's Orchestra goal form read no pack lineup's acceptance yet: one `packs.lineup_run.goal_defaults` call each (R2). (closed 3.2.1.0 R1)
- `bio_models.TAGS` / `row_tags` is the one place to add 3.1.9.0 R1's enriched capability tags (R2). (closed 3.2.1.0 R1)
- the packs registry cache keys on pack.yaml and state.json, not a pack's bio files: an edit inside an installed pack's agents/ shows after the next install, update or enable (R2). (closed 3.2.1.0 R1)
- a pack's own Studio section comes back after a reload only once the registry loads; the first paint is the saved core section (R3). (closed 3.2.1.0 R1)
- `capacity.parallel` is advertised and shown to the planner, not held back by the hub; a part a worker refuses is not re-planned onto another harness; `fleet.capabilities.hide` does not hide a pack capability (R4). (closed 3.2.1.0 R3)
- a pack's fleet inspector lines show their file only for a pack that runs on Studio's own harness; Studio's Mission form and `halo fleet mission new` send no `lineup` for the mission metadata (R4). (the lineup half closed 3.2.1.0 R1; the inspector lines closed 3.2.1.0 R3)
- the replanner (3.1.8.0 R2) may change a workflow run's lanes; a workflow run should keep its stage set (or replanning be off for it) (R5). (closed 3.2.1.0 R2)
- `gate: human` is the plan review before any stage, not a hold before one stage; a workflow's own `budget_usd` is a stop only under `--as goal`, "not enforced yet" in a plain Orchestra run (R5). (closed 3.2.1.0 R2)
- check that 3.1.8.0 R3's verified-outcomes gate reads a workflow stage's evidence rows, not only the summary (R5). (closed 3.2.1.0 R2)
- Orchestra's own new-run form has no workflow picker: a pack's workflow starts from the Pack Manager's Run <workflow> or `halo workflow run` (R5/R6). (closed 3.2.1.0 R2)
- a lineup's `workflows:` stays a list of names; a workflow runs by `<pack>/<name>` (R5). (closed 3.2.1.0 R2)
- the glossary's closed list has no "pack" yet (R1's note; `halo explain pack`, Studio's Glossary) (R7). (closed 3.2.1.0 R1)
- a hook's shell `command` gets `${CLAUDE_PLUGIN_ROOT}` substituted as text, so on Windows Git Bash eats the path's backslashes; the exec form (`args`) and `${halo_python}` are safe, the shell form of every plugin is not (R7 found it). (closed 3.2.1.0 R4)
- rollback keeps one version back (`<id>.previous`); no history beyond it, and the CLI does not pause between the migration notes and the swap (`--dry-run` is the look before) (R7). (closed 3.2.1.0 R4)
- the shipped doc-review pack says `halo: {min: "3.1"}` until the version bump: the bump commit that makes `__version__` 3.2.0.0 sets `{min: "3.2"}` (test_reference_pack fails until it does) (R7). (closed 2026-10-24: scripts/release.py sets it at release)
- the full Chrome tier as a whole and a Kali/Linux pass of the packs program have not run on a worker (every round). (closed 3.2.1.0 R5 on WSL Ubuntu: the whole Chrome tier and the whole fast tier green there, the packs commands by hand; the Kali VM did not answer, see below)

### After 3.2.1.0 (R2's open points: a workflow run keeps its shape)

- `gate: human` stays the plan review before the run starts (`workflows/compile.py`: any stage with it makes the whole goal `plan: review`); a hold before one stage, after the run started and before that stage's lanes, is not a thing yet (R2).
- the replanner is off for the whole of a workflow run: a move inside a stage (a lane's model or bio, a retry within the stage's `retries`) is not separated from the split and specialist moves, which add lanes; a per-stage replan needs `replan_plan.check` to refuse those two for a pinned run and the lead's replan prompt to offer only the rest (R2).
- the workflow's `budget_usd` stop is checked before each worker pass: passes already running finish and can carry the spend past the cap by their own cost (the supervisor's guard under `--as goal` adds each lane's forecast; a plain run has no forecast check) (R2).
- Orchestra's workflow picker lists every workflow of a running pack, whether or not its prerequisites hold here (a grant, a capability): the compile says what is missing when Run is pressed (R2).
- the Pack Manager's Templates and `halo pack inspect` list a pack lineup's `workflows` as written (bare names); only `halo teams show` prints the resolved `workflow_refs` (R2).

### After 3.2.1.0 (R3's open points: the hub holds what a pack declares)

- `capacity.parallel` is held by the hub that runs the missions: parts another hub sends the same member are not counted, and the member's worker takes any number of parts itself (R3).
- a refused part is re-planned by the rules (prefer, load, name) with no second lead call, and only for the two `refusal()` lines; its claims and dependencies stay as planned (R3).
- a member's inspector `text` is the file as of its last catalog gather (every pack change, `--refresh`, or an hour): an edit of an installed pack's inspector file reaches the hub with the next gather (R3).
- `halo pack doctor`'s fleet-hidden row is a warning (doctor has no info level), so a pack capability you hide on purpose makes `halo pack doctor` exit 1 (R3).
- the Mission panel's `waiting` and replanned lines have no Chrome step; the states, the lines and the status table are pinned in tests/test_packs_fleet_hold.py (R3).

### After 3.2.1.0 (R5's open points: the Linux pass)

- the Kali VM did not answer during the round (no route to it): the packs modules, the Chrome packs modules with Kali's own chromium and the packs commands by hand have run on WSL Ubuntu only; the owner's `halo update` there after the release is the first Kali run (R5).
- a skill's or a command's body gets no `${CLAUDE_PLUGIN_ROOT}`, and a custom command's body (`commands/**/*.md`) none of the `${CLAUDE_...}` variables; a skill's body gets four (R5 corrected SLASH-COMMANDS-tui.md, which listed the plugin root) (R5).
- the wizard's Linux-fixes step installs ripgrep into the real `~/.local/bin` and edits the real rc file, by design; a test that walks the wizard on a box without `rg` on PATH must pin `init_wizard.linux_fixes_needed` (tests/test_round2c_wizard_ux's `_Env` does now). The suite's real-home guards watch `~/.halo` and `~/.rolo-claude` only, so a test writing elsewhere in the real home is not caught (R5 found one by the file's mtime) (R5).
- WSL's Chromium is not the runner's (a 1500x757 viewport, wider fonts, other pointer paths) and WSL2's wall clock steps back about a second at times: a red there is a red to look at, a green there is not the release gate (docs/DEVELOPMENT.md "The Chrome tier on Linux") (R5).

## ADDED 2026-10-21 ~02:20 (rolo: "There should be an auto role template, prob the default one until a user finds a template they like. Auto should give the agent the ability to call other agents and create whatever orchestration the main model thinks should be the role type with sub agents ... whatever agent is main should know which model is the best from cost, intelligence, what they are best at (like media distillation whether that's video or audio or pdfs) so it knows which agents to use for sub tasks. Maybe some kind of analysis of the available models in the halo model list should occur"): 3.1.9.0 "Auto"

- R1 What each model is good at: a capability profile for every model in
  the catalog (`providers/profiles.py` -> `<state>/models/profiles.json`):
  cost in and out, context and output limits, what it takes in (text,
  image, audio, video, PDF), tool calling, reasoning, open weights, local
  or remote, the observed speed (speed.py), the gym's measured scores where
  a model ran the gym, and measured outcomes from the coach's records when
  they exist; from these, strengths by rule (code, research and long
  context, media distillation by kind, cheap bulk, fast, local and
  offline) with one honest line per model ("vision in, cheap, fast; no
  audio"). `halo models --profile [REF]`, a "best at" column in the Studio
  Models panel and the `/model` picker, `halo models analyze` to rebuild
  (the catalog refresh does it too), and a roster block (one line per
  model, the cheapest and the strongest per strength named) any agent can
  be given.
- R2 The Auto lineup: a shipped `auto` lineup that is the default `team:`
  when none is set (a user who picks another template replaces it; a set
  `team:` is never touched): main is the session's model with open
  delegation over a pool of generic bios (planner, researcher, coder,
  reviewer, media -- image, audio, video and PDF distillation -- writer,
  ops) whose `models.preference` is `auto`; at spawn the model comes from
  the profile and the task's needs (the modalities the task or its
  attachments carry, the lineup's cost band, a reasoning tier for planning
  and review, fast and cheap for bulk work) and the reason is recorded and
  shown (the Roles pill: "auto: <model> -- images in the task, the cheapest
  vision model"); main gets the roster block in its context so it
  delegates deliberately and may override with `--model`; the Roles canvas
  shows Auto with its live choices; `auto` slots into the one model order
  after a tier's model and before the fallbacks.
- R3 Auto learns: the choices and their outcomes feed the measured fields
  (3.1.8.0 R3's measured routing), so a model that keeps failing a kind of
  task drops in the roster; docs and the release.

Not taken: asking each model to describe itself (unreliable); a second
catalog (the profile is a view over the one catalog); media generation
models (diffusion, TTS: `media_models.py`, a different inventory).

## ADDED 2026-10-24 (rolo, after installing 3.2.0.0: "Keep going"): 3.2.1.0 "Packs, the loose ends" -- the "After 3.2.0.0" list becomes five rounds

The sixteen open points the Packs program left (the list above) are the
next version. Each round is one Opus worker in its own worktree
(`~/hh-321/<round>`), briefs and hand-backs under `~/hh-321/briefs/`;
the coordinator merges, gates every push on both runners and releases
3.2.1.0 when R5 is in. Nothing changes for a repo with no pack. No
classifier, no refusal wording: every stop is one factual line the docs
name.

- R1 A pack's lineup reaches the goal, the mission and the glossary:
  `halo goal add --lineup` and Studio's Orchestra goal form read the pack
  lineup's acceptance (`packs.lineup_run.goal_defaults`, one call each);
  Studio's Mission form and `halo fleet mission new` carry the `lineup` in
  the mission metadata; the packs registry cache keys on a pack's bio and
  lineup files too (an edit inside an installed pack's agents/ shows at
  once); after a reload the saved pack section is the first paint, not the
  core section it falls back to today; `bio_models.TAGS` reads 3.1.9.0
  R1's enriched rows (modalities in and out, tool calls, reasoning, open
  weights, local); "pack" joins the glossary's closed list (`halo explain
  pack`, Studio's Glossary).
- R2 A workflow run keeps its shape: the replanner leaves a workflow run's
  stage set alone (it may move work inside a stage, never add or drop one;
  the run says so in one line); a workflow's own `budget_usd` stops a
  plain Orchestra run too, not only one under `--as goal`; the verified-
  outcomes gate reads a stage's evidence rows, not only the summary;
  Orchestra's own new-run form gets the workflow picker (the same compile
  the Pack Manager's Run <workflow> uses); a lineup's `workflows:` names
  `<pack>/<name>` the way `halo workflow run` does (a bare name still
  resolves inside its own pack).
- R3 The hub holds what a pack declares: `capacity.parallel` is held by
  the hub (a part past the capacity waits, the planner is told); a part a
  worker refuses is re-planned onto another harness that has the
  capability, once, with the reason in the mission log; `fleet.
  capabilities.hide` hides a pack capability like a built-in one; a
  member's pack inspector lines name their file the way Studio's own
  harness's do.
- R4 Hooks and the update pause, for everyone: a plugin hook's shell
  `command` with `${CLAUDE_PLUGIN_ROOT}` runs on Windows (the path is
  quoted and forward-slashed before the shell sees it; the exec form stays
  the recommended one, docs say both); `halo pack update` shows the
  migration notes and the files that change, then asks before the swap in
  a terminal (`--yes` skips it, `--dry-run` stays the look before), the
  Pack Manager's confirm already does this. Rollback stays one version
  back: `<id>.previous` is the rule, written in PACKS.md (not taken: a
  version history on disk).
- R5 The Linux pass: the whole Chrome tier and every packs, workflow and
  Studio-packs module run on Linux (the WSL repro box with its headless
  Chromium, then the Kali VM when it answers); every red is a fix with a
  test (a driver that needs an element fallback, a path that is Windows-
  shaped, a hook that needs the shell); the hand-back lists what ran where;
  then the release.

Not taken: a version history for rollback (one back is the rule); asking
the planner to honour capacity by itself (the hub holds it); a second
glossary.

## ADDED 2026-10-25 (rolo, /plan: "the wizard set up should be done thru halo studio, especially during halo init ... there needs to be a settings tab or set up tab in halo studio and it should launch when started"; and, after the wizard's last checkbox crashed on Kali: "we have to be much clearer about what tests will be done, even have options to select which kinds of tests"): 3.2.2.0 "The first run says what it does", then 3.3.0.0 "Setup is Studio"

Two versions, in this order. Each round is one Opus worker in its own
worktree (`~/hh-322/<round>`, then `~/hh-330/<round>`), briefs and
hand-backs under `<dir>/briefs/`; the coordinator merges, gates every push
on both runners and releases each version when its last round is in. No
classifier, no refusal wording: a cost line is information, every stop is
one factual line the docs name.

### 3.2.2.0 "The first run says what it does"

What the wizard's Summary offered as "Run the ten-minute start now (halo
start: a lineup, a sample repo, one Orchestra run)" is `halo start`: a copy
of the shipped `halo-dev-cycle` lineup, a sample git repo under
`~/.halo/start/<date>/`, then one REAL Orchestra run (five workers on the
user's configured models, the lead's plan, the lanes, the report and the
coach), with a two-hour cap. Nothing before it names the cost, the models,
the time or what it writes; it is not a model-strength test (that is `halo
gym`); and `start/engine.py` catches only its own `Stopped`/`StepFailed`, so
any other exception from a step reaches the terminal as a traceback (the
owner's Kali run, 2026-10-25; the VM did not answer ssh, so the exact
traceback is unread).

- R1 The start never crashes: `StartRun.run()` turns any exception from a
  step into that step's `failed` frame with one line (`<Type>: <message>`),
  writes the full traceback to `<state>/start/<date>/<run or start>-error.log`
  and says "the full error is in <path>"; the summary's `reason` is that
  line, the exit code 1, no traceback on the terminal; `start_cli.cmd_start`
  and `studio/start_job.py` do the same for a failure before the walk; the
  wizard's hand-off names the log when the start fails. Tests through
  `HALO_START_FAKE=1`: a step made to raise `TypeError` gives the failed
  frame, the log file, exit 1 and no "Traceback" in stderr (the CLI and
  `POST start`).
- R2 The first-run checks say what each does and the user picks: "the
  ten-minute start" is "the guided first run" everywhere; `halo start`
  opens on a card (what it does in seven sentences, the models it will
  call from the lineup's resolved cards, an estimated cost from the Team
  step's price rows, "free" when every model is local, the time, what it
  writes, that the active lineup is untouched; `halo start --explain` prints
  only the card). `halo_harness/start/checks.py` holds five checks, each
  with its what / cost / time line and a `run`: doctor (free, seconds),
  the model catalog refresh (free, network), hello (one one-turn call to
  the default model, the pong), the gym (`halo gym --quick` on the models
  you tick, cost and time per model) and the guided first run (the card's
  cost); the first three are on by default, the gym and the first run off.
  The wizard's Summary shows the five rows (Space toggles, Finish runs the
  ticked ones in order and prints each result, Esc skips all), the console
  fallback runs the first three, `halo check [--all | --doctor --catalog
  --hello --gym --start]` runs the same list; Studio's Start here shows the
  card before Run. Docs: COMMANDS-init (the Summary's checks), COMMANDS
  (`halo check`, `halo start --explain`), HANDBOOK and README (the guided
  first run), STUDIO-shell; the glossary gains "guided first run".

### 3.3.0.0 "Setup is Studio"

The terminal wizard's eight steps (Providers with its eight tabs, Local
models, Default model, Permissions, Theme, Team, Linux fixes, Summary)
become a **Setup** section in Studio, Alt+8, the last core section (packs'
own sections start at Alt+9); one page, a rail of blocks, each block its
own form with its own Save and its own saved / changed / problem line; a
status strip on top (provider, default model, lineup, last check) and the
Check block from 3.2.2.0's list. `halo init` starts or reuses Studio and
opens it on Setup; `halo init --terminal` runs the terminal wizard, and so
does `halo init` when no browser can open (SSH, no DISPLAY): the URL is
printed with the port-forward hint. `halo setup`, `/setup` and `halo start`
with no provider open Setup too; a fresh home lands on Setup whatever
section was saved; the CLI (`halo config set`, `halo teams apply`, `halo
models`) keeps working for changes. Keys travel browser to server once
over loopback with Studio's token and are never read back (the state says
"set, from the env file, ****1234"); the block for the TUI `theme` key is
"Terminal theme" (Studio's own dark/light switch is a browser setting).

- R1 The Setup section: the registry (Alt+8; `packs/registry.ts` FIRST_KEY
  9; `STUDIO_MODES`, the banner, STUDIO-sections.md, every Alt+N pin),
  `studio/setup_api.py` (`GET setup/state` masked, `POST setup/config` for
  the whitelisted keys `model`/`permission_mode`/`theme`, `POST setup/team`
  = the Team step's three writes as one function both call), the blocks
  Default model, Permissions, Terminal theme, Team and the status strip; a
  Chrome driver that saves each and reads config.json back.
- R2 Providers and local models: one card per provider (state line, a
  key field never prefilled, Save & test = the wizard's own writers and
  probes: `_write_env_var`, `enable_if_was_explicitly_disabled`,
  `reachability_tag`, `refresh_tab_catalog`), Ollama hosts (the merge rule
  that never repoints a host), Hugging Face token/endpoints/local servers,
  model folders and the runtime; unit tests on a fake env file
  (`HALO_ENV_FILE`): the GET never carries a key.
- R3 The check and the fixes: the Check block as a background job with a
  live log (`setup` frames) running 3.2.2.0's checks, the cost card before
  the guided first run can be ticked, the Linux fixes block (shown only
  when needed), the fresh-home landing and the Start here button "Set up
  this box", Studio's `no_provider` answer jumping to Setup.
- R4 The doors and the docs: `halo init` / `halo setup` / `/setup` / `halo
  start` open Setup, `--terminal`, the no-browser fallback; WIZARD.md leads
  with Studio and keeps the terminal wizard as the fallback; COMMANDS,
  STUDIO, STUDIO-sections, README (the first screenshot after install is
  Setup), a screenshots.py capture; "After 3.3.0.0" for what stays open (a
  keyring instead of the env file; pack-declared setup blocks).

### After 3.3.0.0 (what the Setup rounds left open)

- A keyring instead of the env file for Setup's keys (and a remover: a
  removed Ollama host, endpoint or local server keeps its `HALO_SECRET_*`
  line today).
- Pack-declared setup blocks: a pack's own block on the Setup page (its
  settings form there, beside the Pack Manager's).
- The TUI's `/setup` decides by the browser's answer only (studio/edit_open.py
  `open_edit`); the CLI doors also read `HALO_NO_BROWSER`, `SSH_CONNECTION`
  and `DISPLAY` first. One rule for both if a live session over SSH shows a
  need.
- The Models panel (Roles) still reads `model_rows()` uncached (it probes
  Ollama hosts on open); Setup and the cost readers read the cache.
- The live checks on real hardware: `halo init` on the PC (Setup opens in
  the browser), on Kali's desktop, and over SSH into Kali (the URL with the
  port-forward line, then the terminal wizard).

## ADDED 2026-10-25 (rolo, two more for 3.2.2.0: "halo pids keep running after I exit halo. I try to do an update then get errors that it's unable to update bc an instance of halo is running even tho I closed it! Kill all halo pids when a user exits halo" and "Drop the one-liners at the beginning when you launch halo, and just pop up the halo ascii art we use each time halo launches")

- R0 The launch shows the art (done by the coordinator, one commit): the
  intro pool in `tui/intro_lines.py` is the HALO block-art wordmark alone;
  the copy-of-a-copy line and the Red Dragon line are gone; `/intro` and
  `/intro <n>` show the art.
- R3 Halo exits clean, and `halo update` clears what lingers. What outlives
  a session today (surveyed 2026-10-25): the detached Studio server
  (`python -u -m halo_harness studio`, started by a bare `/studio`, `/edit`,
  every "Edit in Studio" button, the wizard's Team step and `halo start`;
  `~/.halo/studio.json` holds its pid; only `halo studio --stop` ends it),
  the supervisor daemon (`halo supervise --daemon`, `supervise/pulse.json`),
  `--bg` runs and schedule fires (`~/.halo/bg/<id>/meta.json`), a schedule
  fire with no registry (a plain Popen nobody tracks). `Controller.quit`
  stops none of them; `halo update` refuses with "another halo process looks
  like it's running (pid N)" and `/update` passes `force=True` and skips the
  check, then runs `uv tool install --reinstall` from inside the halo
  process whose `halo.exe` parent is alive (the Windows "Scripts: Access is
  denied" the docs describe).
  - On exit (`/quit`, Ctrl+C twice, Ctrl+D, Ctrl+Q, the end of `-p`): halo
    stops every halo process this session started or found registered to
    this home: the Studio in `studio.json` (`launch.stop`: the shutdown
    route, then the signal), its own `--bg` runs and schedule fires (a
    session-owned list in `~/.halo/run/children.json`: pid, start time,
    what, written at spawn, pruned at exit), untracked schedule fires (they
    join the registry). The supervisor is the one process that stays: it
    was started on purpose by `halo supervise --daemon` and the docs say
    so; `halo supervise stop` ends it. The quit card says what it stopped
    in one line ("stopped: Studio (pid 4242), 2 background runs").
  - `halo update` stops before it installs: every halo process of this
    install (`other_halo_pids`, extended to `-u -m halo_harness studio`,
    `_bg_wrapper`, `supervise`, and the tool venv's own `python` running
    `mlx_lm.server`), each named with its pid and what it is, is stopped in
    order (the shutdown route or stop file first, then the signal, then the
    hard kill after 5 s); the supervisor is restarted on the new version
    when it was running; `--keep-running` refuses as today (the old default)
    and names each process and the command that stops it. The TUI's
    `/update` no longer installs from inside the halo process: it writes a
    detached updater (`cmd.exe /c` on Windows, `sh -c` on POSIX; never the
    tool venv's python) that waits for this pid to end, stops the lingering
    processes the same way, runs the reinstall, and logs to
    `~/.halo/update.log`; the TUI prints that path and "halo --version
    after it ends" before it exits.
  - Tests: a quit leaves no registered child alive (a fake Studio and a fake
    bg run in a scoped home: both pid files gone, both processes ended);
    `other_halo_pids` matches the four command-line shapes; `halo update`
    stops a fake lingering process and says so; `--keep-running` refuses
    with the names; the detached updater script waits for the pid and
    writes the log (a short-lived parent in the test). Docs: TROUBLESHOOTING
    (the Access-is-denied entry becomes "halo update does this for you"),
    INSTALL, COMMANDS (`halo update --keep-running`), STUDIO (Studio ends
    with the session that started it; `halo studio` starts the new one),
    COMMANDS-supervise (the supervisor survives a quit, comes back after an
    update).

## ADDED 2026-10-25 (rolo, live on Kali: "models stopping or not verbosely saying they are still working on a task or done with something. I am having to ask while in plan mode. sometimes things are getting blocked while in plan mode and I have to like send questions to get it working again"; "plan mode blocks network fetches too, that hinders planning"): 3.2.2.0 R4 the session says what it is doing, and plan mode never leaves you guessing

What the code does today (surveyed 2026-10-25): the status bar spins
(`thinking 18 s`, `tool Bash 4 s`, `waiting 3 s`) and the transcript's
phase line says `no data for 30 s, Esc interrupts, typing steers`, but a
silent model call is only ever restarted by the user typing a steer
(`steer.restart_when_silent`) or by the 300 s read timeout; a finished
turn just loses its spinner (no marker for `end_turn`, `max_tokens`,
`error`, `blocked`), so a model that ends its turn with "Now I'll edit X"
and no tool call looks stopped; the system prompt never asks the model to
say what it is doing, when it is done or when it waits on the user, and
the Kimi family note tells it to add no explanations to tool calls.
Plan mode: Shift+Tab or `--permission-mode plan` writes
`permission_engine.mode` and tells the model NOTHING (no PLAN_MODE_NOTE, no
plan-file path, no ExitPlanMode instruction; leaving plan mode is not told
either); the refusal reads `plan mode: other is banned (an allow rule
cannot lift the plan-mode write ban)` with no way out named; only Read,
Glob, Grep, Agent, TodoWrite, ToolSearch, AskUserQuestion and the two plan
tools are exempt, so WebFetch, WebSearch, BashOutput, Skill and every MCP
tool, read-only or not, are refused as `other`; the plan card's `[1]
Approve [2] Approve, manual [3] Keep planning` line comes AFTER the plan
text in a dock capped at 12 lines, so a long plan hides the keys.

- R4 The session says what it is doing, and plan mode never leaves you
  guessing. (a) A turn ends with a marker line in the transcript and in
  Studio's Session feed: `◼ done · 42 s · 3 tools · $0.012`, `◼ waiting
  on you: <the question | the plan | permission for Bash>`, `◼ stopped:
  <max_tokens | the provider error | blocked by a rule>`; (b) the system
  prompt asks for a one-line "what I am doing" before a group of tool
  calls and "what I found / what is next" when a turn ends, and to say in
  one line when it waits on the user; the Kimi note loses "do not add
  explanations" (one short line per group is the rule for every family);
  (c) a turn that ends with a promise and no tool call ("Now I'll...",
  "Let me...", "Next I will...") is nudged once by the harness ("You ended
  your turn while saying you would do more. Continue.") -- a user-role
  notice, shown in the transcript as `↳ nudged: the reply promised work
  and stopped`; `turn.nudge_promises: false` turns it off; (d) a silent
  call with no first byte for `steer.silent_restart_s` (default 60 s) is
  aborted and resent once, `↳ no data for 60 s, resending the call`, the
  second time waits the read timeout; (e) plan mode: entering by Shift+Tab
  or at startup injects the same PLAN_MODE_NOTE the EnterPlanMode tool
  gives (the plan file path, "call ExitPlanMode with the plan"), leaving
  plan mode injects "Plan mode is off: implement"; the dynamic context
  states the current permission mode each turn; a `/plan [on|off|status]`
  slash command; (f) plan mode allows every read: WebFetch, WebSearch,
  BashOutput, Skill, ToolSearch, knowledge_search, recall, an MCP tool
  whose annotations say `readOnlyHint`, read-only Bash as today; the
  refusal for a write reads `plan mode: <Tool> writes; research with the
  read tools and the web, then call ExitPlanMode with the plan (Shift+Tab
  or /plan off leaves plan mode)`; (g) the plan card puts its keys line
  FIRST, above the plan text, and the status bar keeps `needs you` until
  it is answered. Tests pin each: the marker per reason, the nudge once
  and off by config, the 60 s resend, the note on Shift+Tab in and out,
  WebFetch/an MCP read allowed in plan mode and a write refused with the
  new text, the card's first line. Docs: PERMISSIONS (plan mode's list and
  text), TUI/HANDBOOK (the markers, the nudge, the resend), SLASH-COMMANDS
  (`/plan`), CONFIG (`turn.nudge_promises`, `steer.silent_restart_s`).

## ADDED 2026-10-25 (rolo, live in Studio: "When I move the parts in halo studio over another block like in roles, they disappear. Moving one block should shrink the ones next to them without things disappearing. It should be intuitive to be flexible and move adjustable without the user having to move one box then each other one individually"): 3.2.2.0 R5 the canvas makes room

What the code does today (surveyed 2026-10-25). Two layers can "disappear":
(1) the **workspace panels** (`ui/src/lib/workspace/`: every section is
panels on a 24-column grid, saved per section in localStorage
`halo.studio.layout.<section>`): a moved panel's `arrange` -> `pushDown`
moves every panel it overlaps straight DOWN (`grid.ts:89-107`), never
sideways, never narrower or shorter, and `compact` lifts them back only as
far as their columns allow; Roles' Canvas, Bios and Models panels are
full-height (`h: 0` = fill), so a pushed panel lands at or below the
bottom of the viewport inside `.workspace { overflow: auto }` -- still
there, scrolled out of sight; STUDIO-shell.md promises "the others make
room"; (2) the **Roles canvas cards** (`routes/roles/Canvas.tsx`,
`layout.ts`, positions in `<state>/studio/layouts/<lineup>.json` via `PUT
layout/<name>`): fixed 224x112 opaque cards with no z-index after a drop
(DOM order wins, one card covers another), a drop inside another tier's
box is a tier move even when it lands on a card, a drop on a collapsed
tier's strip joins that tier and the card is then hidden with it (a true
disappearance), no collision pass on drop, and node ids carry an index
(`alias|role|agent#i`) so removing a card re-keys the later ones and their
saved positions stack. Design's Artboards share the free-x/y pattern; the
Orchestra plan and the Fleet map compute their layouts and have no overlap
problem. No shared drag helper exists; all layout code is hand-written.

- R5 The canvas makes room. Panels: `arrange` resolves an overlap by
  making room sideways first -- the overlapped neighbour gives up columns
  down to its `minW` (and the moved panel takes what is left), then trades
  places when both are full width, and pushes down only as the last resort
  and never below the visible rows (`fillRows` reaches the controller
  through `WorkspaceApi.metrics`); an edge resize acts as a splitter (the
  adjacent panel shrinks or grows by the same columns or rows); nothing
  leaves the viewport on a move; "Reset layout" (exists) and a new
  "Arrange" (one press: the section's default grid for the panels you have
  open) sit in the workspace menu. Canvas cards: a drop runs a no-overlap
  pass (the dropped card keeps its spot, the cards and boxes it collides
  with nudge aside within their tier, the tier box regrows), collapsed
  tiers are not drop targets (the box expands when a card is held over it
  for a moment, or the drop is refused with the toast "tier <name> is
  collapsed"), a drop onto a card in another tier asks nothing and lands
  beside it, the selected or last-dropped card is on top (z-index), live
  drag pushes neighbours too (through the `pos` memo) so the user sees the
  room being made; node ids become stable per card (`alias|role|agent` plus
  an ordinal among identical cards) so removing one card keeps every other
  card's saved spot; Design's Artboards reuse the same no-overlap helper
  (`ui/src/lib/geometry.ts`: rectangle hit tests, nudge-apart, splitter
  math, under 250 lines). Tests: a CDP title-bar drag of Roles' Inspector
  over the Canvas -> every panel's rectangle inside the viewport and
  `overlaps == []`; an edge resize moves the neighbour; the canvas drivers
  (`studio_roles*.py`): a drop onto another card leaves both visible and
  not overlapping, a drop over a collapsed tier does not hide the card,
  removing a card keeps the others' positions; `tsc`, the dist rebuilt
  twice identical. Docs: STUDIO-shell.md (what a move does now, Arrange),
  STUDIO-roles (the canvas rules).

## ADDED 2026-10-25 (rolo, live: "I have to refresh the page for updates that occur. When working with halo and prompting I asked to update the roles but I had to refresh halo studio to see the changes made"): 3.2.2.0 R6 Studio sees what the session changes

Today Studio's live feed carries what Studio itself does and what a session
streams (`focus`, `fleet`, `team`, `start`, `orchestra_state`, `design_turn`,
`pack_changed`, `dropped`, ...), and `studio/packs_studio_live.py` polls the
packs registry and publishes `pack_changed` when a pack file moves. Nothing
watches the files a session or the CLI write: a lineup edited by the model
(`~/.halo/teams/<name>.yaml`, `.halo/teams/`), a bio (`agents/`), `halo
teams apply` / `halo roles` / `halo config set` (config.json's `team`,
`roles.*`, `model`), a layout file. The Roles page shows what it loaded.

- R6 Studio sees what the session changes: `studio/files_live.py` (the
  packs watcher's shape) polls, every 1.5 s, the mtimes and names under
  the user and project `teams/` and `agents/` folders, `config.json`, the
  `studio/layouts/` folder and the packs' bio/lineup folders already
  covered, and publishes `{"event": "files_changed", "data": {"kind":
  "lineups" | "bios" | "config" | "layouts", "names": [...]}}` once per
  change set (debounced 300 ms); the pages re-read on it the way Fleet does
  on `dropped`: Roles (the lineup list, the open lineup and its canvas, the
  Bios panel, the Inspector; an unsaved draft in a form is kept and the
  page says "<name> changed on disk" with Reload / Keep mine), Team, the
  Session section's lineup pill and model, Orchestra's goal form lineup
  list, Models' default, the Pack Manager's Templates; a lineup or bio
  deleted on disk leaves the list and the open one shows "deleted on disk".
  The CLI writers publish nothing themselves (the watcher sees every
  writer, the model's Edit tool included). `lib/events.ts KNOWN_KINDS +=
  "files_changed"`. Tests: the watcher (a temp home: touch a lineup, the
  frame names it; a burst is one frame), a Chrome driver that writes a
  lineup file while Roles is open and sees the canvas change without a
  reload, the draft-kept path; docs STUDIO.md ("what Studio shows is what
  is on disk, as it changes") and STUDIO-roles.
## ADDED 2026-10-26 (rolo, from the MacBook using this PC's Ollama as the main model: "encountered errors. Fault was in Halo Harness. Is there a way to have halo harness communicate with ollama servers on the network so that this does not happen?"; and: "add calibration for connecting to ollama models on the network after discover and enum of the models"): 3.2.3.0 "Ollama on the network" -- before 3.3.0.0

The incident (another session read this PC's Ollama log): Halo's prompt is
about 11,000 tokens; the Mac's Halo asked the LAN host for an 8,192 window,
Ollama trimmed the prompt to about 4,100 tokens (the first answer without
Halo's instructions), the automatic tool follow-up lost the user's question
in the trim and Ollama answered 500 "no user query found in messages"; Halo
retried six times, then showed "Ollama had an internal error". What the code
does today (surveyed 2026-10-26, `providers/ollama_calibrate.py`,
`ollama.py`, `ollama_hw.py`, `ollama_request.py`, `ollama_stream.py`,
`agent/loop.py`, `providers/stream.py`, `errors.py`):

- First-use calibration (`run_auto_calibration`, 20 s per step, once per
  host+model per digest and server version) loads the model at a candidate
  `num_ctx` and reads `/api/ps`; a load that times out is never seen -- a
  `/api/ps` without the model counts as "not resident" and the loop halves
  (or, stepping up, stops and records the last size), so a slow host (this
  PC needs 20-55 s for a 17 GB model) yields a SMALL `fits`, never
  "unknown"; the `/api/ps` entry's own `context_length` is never compared to
  the candidate (a late, larger load is credited to a smaller candidate).
- `num_ctx` is a plain `min()` over the hard cap, the trained context,
  `host.max_ctx`, the fit estimate, the learned cap and the defaults
  (`resolve_num_ctx_and_source`): a saved 8192 wins everything and `max_ctx`
  cannot raise it; for a remote host whose model is loaded, the fit estimate
  IS the loaded context -- a model loaded at 8192 keeps reporting 8192.
- No prompt-size estimate precedes an Ollama call; `prompt_eval_count` is
  read (it feeds compaction) but never compared to the prompt or the window;
  the docs say the prompt is "NOT silently truncated" (Ollama returns 400
  only when the request's own `num_ctx` is exceeded, and trims otherwise).
- A 500 is retryable (`MAX_RETRIES = 5`, six sends, backoff to 30 s); the
  raw message is dropped for the generic sentence; "no user query found in
  messages" is matched nowhere.

- R1 The window tells the truth. (a) Calibration: a load is a measurement
  only when `/api/ps` lists the model with a `context_length` equal to the
  candidate; a timeout or a missing entry is `unknown` (the step is retried
  once with the budget doubled, then the run ends `inconclusive` and records
  NOTHING -- never a small `fits`); the per-step budget scales with the
  model's size and the host (local: 20 s + 4 s per GB; remote: 40 s + 6 s
  per GB; the CLI's `--timeout` overrides); the first-use run keeps its 20 s
  wait for the turn but the measurement continues in the background and is
  recorded when it ends; a recorded cap below the prompt floor (below) is
  discarded and re-measured. (b) The window follows the prompt:
  `providers/ollama_prompt.py` estimates the request's tokens (chars / 3.5
  for the serialized messages and tools, plus a 1,024 reserve for the reply)
  before every Ollama call; `num_ctx` is at least that floor, raised above
  the saved cap up to the trained context and the host's memory (the fit
  estimate from memory, not from the loaded context: a remote model loaded
  at N no longer reports N as its fit); when even that cannot hold the
  prompt, the turn compacts first and says so in one line ("the prompt
  (11k tokens) is larger than <model>'s window on <host> (8k): compacted").
  The estimate carries the NEW tool results, so it drives compaction before
  the send (today the gate reads the previous turn's count and one large
  tool result walks past the window): a request that does not fit the window
  Halo can get compacts first, said in one line ("the request (14k tokens, 9k
  of it tool output) is larger than <model>'s window on <host> (8k):
  compacted"). After the call `prompt_eval_count` is compared to the
  estimate: a count far under it is a trimmed request, and so is Ollama's
  500 "no user query found in messages"; both mean "the context is full",
  recovered once per turn in this order: raise the window when there is room
  under the trained context and the memory estimate and re-send, else
  compact and re-send; never the same request unchanged, never six times
  ("<host> trimmed the request (4.1k of 11k tokens): compacted and
  re-sent"). (c) Errors: that 500 is a `prompt_trimmed` error with its raw
  text kept and no retry beyond the recovery above; any other Ollama 500
  keeps three sends (not six) and its raw text. (d) Docs: LOCAL-MODELS
  "calibration and learned caps", MODELS-ollama ("not silently truncated"
  corrected; the 16384 fallback), MODELS-ollama-tuning (the cap is one
  `min()` candidate and the prompt floor sits under it), COMMANDS-local
  (`halo ollama calibrate --timeout`); `halo ollama` shows per model: the
  window in use, its source, the prompt floor, "calibrated / estimated /
  inconclusive". Tests: mock_ollama gains a per-model load delay; slow-load
  cases (a 25 s load with a 20 s budget ends inconclusive, records nothing,
  the window stays the trained context capped by memory); the prompt floor
  wins over a saved cap (test_ollama_precedence_5b); a trimmed
  `prompt_eval_count` re-sends once with the line; the 500 text is a
  `prompt_trimmed` error with no retry.
- R2 The servers are found, then measured. `providers/ollama_discover.py`
  (the design in the 3.3.0.0 R5 entry below: this machine's doors --
  `OLLAMA_HOST`, loopback on `ollama.discover.ports`, this machine's LAN
  address, Docker, WSL -- and the network sweep of the /24 plus
  `ollama.discover.subnets`, a 10 s cap, confirmed by `/api/version` and
  `/api/tags`, never on its own); `halo ollama discover [--lan] [--add
  [NAMES]] [--calibrate] [--json]`: one line per server with its models,
  `--add` writes `ollama.hosts` entries (never repointing an existing host,
  the first stays default), `--calibrate` then measures every model of the
  added hosts with R1's budgets, one progress line per model ("qwen3.8:27b
  on pc: 32k fits, 65k does not (2 min 10 s)"), and `--json` gives it all;
  the wizard's Ollama tab and Local models step: **Find Ollama servers**
  (local), **Scan this network**, a tick per found server, Save adds them
  and offers "Calibrate the found models now (loads each once; about N
  minutes)"; `detection_summary_lines` reports every local Ollama found;
  `halo local` lists a found-but-not-added server. The Studio Setup card
  comes with 3.3.0.0 R5. Tests: two mock servers on loopback ports with
  different models -> both found, the configured one marked; a loopback
  CIDR exercises the sweep; `--add` never repoints; `--calibrate` runs R1's
  calibration per found model through the mock (delays included);
  `BRIDGE_TEST_NO_BACKGROUND_NET=1` -> the LAN scope returns one line and
  nothing else. Docs: LOCAL-MODELS ("Found on this machine", "Found on the
  network", "Measured after finding"), MODELS-ollama, COMMANDS-local,
  WIZARD (the Ollama tab), README.

## ADDED 2026-10-26 (rolo: "For ollama, I need the ability to discover and use local ollama models on the current halo computer's internal hosting envs, plus the ability to find multiple ollama servers serving models on the same network. There could be 1 ollama locally and multiple ollama servers on the network hosting different models"): 3.3.0.0 R5 Ollama everywhere -- the servers on this machine and on the network are found, not typed

Today (surveyed 2026-10-26): every Ollama host is an `ollama.hosts[]` entry
typed by hand (the wizard's Ollama tab: name, url, key), and with none Halo
makes one default host from `OLLAMA_HOST` or 127.0.0.1:11434; the ref grammar
is `ol:<model>` for the default host and `ol:<model>@<host>` for a named one
(`model.py:316-330`); the catalog asks each host `/api/tags` + `/api/show`
(`providers/ollama.py`, 30 s cache) and `halo local`, `/model`, `halo models`
and Studio's Models panel group rows as `Ollama (<name>)`;
`detection_summary_lines` probes the DEFAULT host only; nothing probes another
port, WSL, Docker or the LAN; the repo has no subnet sweep, mDNS or zeroconf
(`providers/huggingface_local_probe.py` is the one port-list prober, loopback
only, serial; `fleet/hub.lan_address()` finds this machine's LAN address with
a UDP connect that sends nothing). Offline mode lets through only private,
single-label or `.local` `ollama.hosts` entries (`providers/http.py`).

- R5 Ollama everywhere. `providers/ollama_discover.py` (new, under 250
  lines): `discover(scope, budget_s)` -> rows `{url, name, version, models,
  configured, where}`. **Local** (`scope="local"`, about 3 s): `OLLAMA_HOST`,
  127.0.0.1 and ::1 on the ports in `ollama.discover.ports` (default
  `[11434]`; a second local daemon on another port is the common case), this
  machine's own LAN address on those ports, the Docker and WSL doors
  (`host.docker.internal`, on Windows the WSL distro's address from `wsl
  hostname -I` when `wsl.exe` exists, on WSL the Windows host from
  `/etc/resolv.conf`'s nameserver), each confirmed by `/api/version` (1.5 s)
  then `/api/tags`. **The network** (`scope="lan"`, a 10 s cap, 64 threads):
  the /24 of `lan_address()` plus `ollama.discover.subnets` (CIDRs) swept
  with a 0.3 s TCP connect on the ports, responders confirmed the same way;
  a name from reverse DNS, else `ollama-<last octet>`; the sweep never runs
  in `BRIDGE_TEST_NO_BACKGROUND_NET=1` and never on its own (a button, a
  command, a wizard step -- the user asks). A found server that matches an
  `ollama.hosts` url is `configured: true`; adding one writes an
  `ollama.hosts` entry (never repoints an existing host, the first stays
  default), so its models are `ol:<model>@<name>` at once and offline mode
  lets it through (private address).
  - `halo ollama discover [--lan] [--add] [--add NAME,NAME] [--json]`: one
    line per server (name, url, version, the models it serves, "configured" /
    "new"), `--add` writes the new ones (all, or the named); `halo ollama`
    and `halo local` list a found-but-not-added server as "found, not added
    (halo ollama discover --add)"; `detection_summary_lines` reports every
    local Ollama it finds, not the default alone.
  - The wizard's Ollama tab and Local models step: **Find Ollama servers**
    (local, at once) and **Scan this network** (the 10 s cap, a progress
    line) list what they find with the models each serves; a tick per row,
    Save adds them; the typed fields stay for a host the scan cannot reach.
  - Studio Setup's Providers block (R2 of this version built it): the Ollama
    card gets the same two buttons; the scan runs as a background job with
    live rows (`setup` frames); a tick adds the host; the Models panel then
    lists its models under `Ollama (<name>)`, each host a group, the default
    host first.
  - Tests: two `MockUpstream`s on loopback ports with different model lists
    and `ollama.discover.ports` set -> `discover("local")` finds both with
    their models and marks the configured one; a loopback "subnet" (a CIDR
    of 127.0.0.0/30 and the mock ports) exercises the sweep without touching
    the LAN; `--add` writes the hosts, never repoints, the first stays
    default; the wizard tab (pilot) and the Setup card (Chrome) drivers tick
    and save; `BRIDGE_TEST_NO_BACKGROUND_NET=1` makes the LAN scope return
    nothing with one line. Docs: LOCAL-MODELS ("On this machine", "A LAN
    host" become "Found on this machine", "Found on the network"),
    MODELS-ollama, COMMANDS-local (`halo ollama discover`), the README's
    local-models line, SETUP (the two buttons).

## ADDED 2026-10-26 (rolo, his measurements on this PC's GPU: Ollama offloads part of a model to the CPU past a 49,152 window even with room on the card; every layer forced onto the GPU made a 65,536 window safe and 98,304 tight; derived "-gpu" model variants carry that default with no extra disk): 3.2.3.0 R1 gains residency and headroom; R3 a tuned twin

- R1 (added): the request asks for `num_gpu` = every layer when Halo's own
  memory estimate says the model and the window fit the host's GPU memory
  (Ollama's own rule offloads earlier); calibration counts a partly offloaded
  load (`size_vram < size`) as "offloaded", not "fits"; a window is "safe"
  when the measured residency leaves 8 % of the card (or 1.5 GB) free, else
  "tight"; the largest safe window is recorded and the tight one named in the
  line; prompt reading speed (tokens/s from Ollama's eval fields) is recorded
  per host and model and shown in the panel and the pickers' speed column.
- R3 A tuned twin: `halo ollama tune MODEL --host H [--window N]` creates, on
  that host through `/api/create`, a derived model `<model>-halo` whose
  Modelfile keeps every layer on the GPU and sets the measured safe window as
  its default (`num_ctx`, `num_gpu`), sharing the original's blobs; `halo
  ollama` lists it beside the original with "tuned twin of <model>"; the
  pickers show the twin first for that host; the wizard's calibrate offer and
  `halo ollama discover --calibrate` end with "make tuned twins? (Enter / n)";
  `--remove` deletes a twin. Tests through the mock's `/api/create`; docs:
  MODELS-ollama-tuning "A tuned twin", COMMANDS-local.

## ADDED 2026-10-26 (rolo, live in Studio: "if you choose to steer via studio, you can't really tell which call you are steering. Highlight what you are interacting with because that scroller in the session tab can lose where you were steering in real time"): 3.3.0.0 R6 the steer knows its target

Today the Session section's Steer box sits at the foot (3.1.7.0), the live
rows stream above it (`routes/session/LiveRows.tsx`, `Live.tsx`,
`routes/shared/liveFeed.ts`, `liveTree.ts`) and the list follows the newest
row; a steer goes to the selected agent, but nothing on screen says which
agent or which call the words will reach, the selected row is not held in
view, and a new row can move the list while the user is typing.

- R6 The steer knows its target. (a) The Steer box carries a target line
  above its field: "Steering: <agent name> · <its current call, e.g. Bash
  (pytest -q), 12 s>" (or "main · thinking"), updated live, with the same
  glyph and colour as the row; the target row (and its agent's node on the
  tree) is highlighted with a steady outline for as long as it is the
  target; clicking another row or node changes the target and says so.
  (b) The list stops following on its own: while the Steer field has focus,
  or the user has scrolled up, the feed appends below without moving the
  view and a "N new rows · follow" pill appears at the foot; a click (or
  Escape out of the field) follows again; the target row is scrolled into
  view once when chosen and never pushed out while held. (c) The steer's
  own line lands as a row under the target with the target's name
  ("↳ steer to coder: ..."), and the row the model answers with is marked
  "after your steer" so the effect is visible; the turn-end marker (3.2.2.0
  R4) shows in the same list. (d) Keys: Tab from the field cycles the target
  among the live agents, Shift+Tab back; `s` on a focused row makes it the
  target and focuses the field. Tests (Chrome): a target line names the
  agent and its call; a highlighted row stays highlighted while rows arrive;
  with the field focused twenty new rows do not move the view and the pill
  counts them; a steer lands under its target; Tab cycles. Docs:
  STUDIO-session (the target, follow), SLASH-COMMANDS-session if the TUI's
  steer gains the same target line (optional: say so).
  (e) ADDED 2026-10-26 (rolo: "also in the timeline, have an export button
  that saves it as an .md file, like a tracer file so we can save detailed
  logs of sessions"): an **Export** button on the timeline (and on the live
  list's header) writes the session as one Markdown trace file the browser
  downloads, `halo-trace-<session id>-<yyyy-mm-dd-hhmm>.md`: a header (the
  session id, the model and lineup, when it started and ended, the totals:
  turns, tool calls, tokens in and out, cost), then one entry per row in
  time order -- the clock, the agent (with its tier and model), the kind
  (user prompt, assistant text, a tool call with its name and a one-line
  argument summary, the tool's result trimmed to 40 lines with "... (N more
  lines)", a steer with its target, a nudge, a permission answer, a turn-end
  marker, a compaction, an error), each under a `###` heading, tool results
  in fenced blocks; the file carries no provider key and no path under the
  user's home other than the session's own (the privacy scan's rules).
  The same trace from the terminal: `halo session export <id> [--md FILE]`
  (`-` prints it), and `/export` in the TUI writes it beside the session
  log and says the path. Tests: the trace of a seeded session has every
  kind once, in order, with the totals; the browser download carries the
  name (the Chrome driver reads the blob's text through the page); the CLI
  and `/export` write the same bytes; `tests.test_privacy_scan` runs over a
  trace. Docs: STUDIO-session (Export), COMMANDS-sessions (`halo session
  export`), SLASH-COMMANDS-session (`/export`).

### After 3.2.3.0 (the held drop on a slow box)

- On GitHub's Windows runner a card held over a collapsed tier's strip joins the tier (the tier opens, the lineup says so) but its position lands outside the tier's box: run 40285708108 recorded card [870, 419, 109, 54] against the leads box [701, 204, 126, 207]; the box there is one card shorter than on this project's boxes at the same moment (269 tall), so an earlier cross-tier drop's position was not in the box yet when the hold began. On this project's Windows box and WSL the same steps land inside the box at every window size tried (1500x900, 900x600). The drop fix of 3.3.0.0 R1 (`dropPatch` clamps into the box) is in; the two checks that depend on it (`held_in_box`, the spots after a removal) are recorded, not judged, on that runner. 3.3.0.0 R7 reproduces it with latency (a slowed layout save, a slowed lineup save) and makes the cross-tier drop one ordered write: the tier change and the clamped position saved together, the hold never opening on a stale box.

## ADDED 2026-10-26 (the coordinator, from GitHub's runners during the 3.2.3.0 gate): 3.3.0.0 R7 the Studio on a slow box

Two Studio behaviours differ on GitHub's runners from every box here, and both
are timing: (1) the held drop (plans/ROADMAP.md "After 3.2.3.0 (the held drop
on a slow box)": a card held over a collapsed tier's strip joins the tier but
its position lands outside the box; the box was one card shorter at that
moment, so an earlier cross-tier drop's position was not in the box yet when
the hold began); (2) the Fleet map's stale node (the Linux runner, run
40294720639: the session tree said the implementer was `stopped`, the map
node still said `running` after 60 s, one feed listener, nothing dropped --
the 3.2.1.0 re-read on `dropped` and on feed open did not cover it).

- R7 The Studio on a slow box. (a) A cross-tier drop is one ordered write:
  the tier change and the clamped position are saved together (the lineup
  save carries the layout patch, or the layout save waits for the lineup
  save and reads the fresh tier boxes), the hold opens a tier from the
  CURRENT boxes (the tier box recomputed after any pending save), and the
  live drag's `pos` is the only source for the box while a drag is on;
  reproduced first with latency (a slowed `PUT layout`, a slowed lineup save:
  a test flag `HALO_STUDIO_SLOW_MS` the server honours) so the runner's
  failure shows locally, then fixed; the two recorded-only checks are judged
  everywhere again. (b) The Fleet map re-reads its view on every
  `agent_state` frame that ends an agent (`stopped`, `done`, `failed`) and
  on the turn-end marker, and while any node is `running` it re-reads every
  5 s as a floor (a `fleet` poll the page already has for its header);
  reproduced with the same latency flag; the stop test's 60 s wait is judged
  everywhere. Docs: DEVELOPMENT.md "A slow box" (the flag, what it is for).

## ADDED 2026-10-26 (rolo, after installing 3.3.0.0: "I hate the pop up when the settings studio is launched. Don't do that. It's so busy in the studio version of the set up. Have it go thru pages not like a huge confusing blob on one page"): 3.3.1.0 "Setup, one page at a time"

Today Setup (3.3.0.0) is one workspace page with eight panels (Providers,
Local models, Default model, Permissions, Terminal theme, Team, Linux fixes,
Check) over a status strip, and `halo init` opens it with `?first=1`, which
auto-opens the section help ("What this page does") once; a fresh home can
also show the Start here overlay. The owner reads that as a pop-up and a blob.

- R1 Setup, one page at a time. (a) Nothing opens on its own when Setup (or
  any section) loads: `?first=1` no longer opens the help (it only leads the
  strip), the first-visit welcome (`welcomeIfNew`) never fires for Setup, the
  Start here overlay never shows while Setup is the section (its "Set up
  this box" button is Setup's own first page); the help stays one click away
  (the ? in the header). (b) Setup is a paged flow: a step rail across the
  top in the wizard's order -- Providers, Local models, Default model,
  Permissions, Theme, Team, Check -- current step highlighted, done steps
  ticked (a step is "done" when its block has what it needs: a provider
  set, a model picked, ...), the Linux fixes as a step only when needed
  (before Check); one block per page, its own Save stays, **Back** / **Next**
  at the foot, the rail jumps anywhere, Enter in a field is that block's
  Save; a **Summary** page last: one line per step with its value and a
  "Change" jump, the Check block's "Run the ticked checks" and the guided
  first run's card; `?block=<id>` (R4's door) opens that page; the status
  strip becomes the rail's own one-line summary (no second strip). (c) The
  pages keep the workspace's rules out: no panels to move on Setup (one page,
  one block, the room is the page); the Ollama card's Find / Scan / Add /
  Measure live on the Providers page under the Ollama provider as a
  disclosure, closed by default. (d) The capture, the banner tile and the
  docs (STUDIO-setup, STUDIO-sections, WIZARD, README's Setup screenshot)
  follow the first page. Tests: the Chrome driver walks Next from Providers
  to Summary and back, the rail jumps, `?block=team` lands on Team, nothing
  is open on load (no help, no overlay) with and without `?first=1`, the
  Summary's lines and Change jumps; every existing Setup test keeps its
  checks (they address blocks by testid, now one page at a time).

## ADDED 2026-10-27 (rolo, after 3.3.1.0: "the visuals in studio are too cluttered and the pop up is annoying when you open a tab and the left column takes up too much space" -- "Let's do all that!"): 3.3.2.0 "Quiet Studio"

Today the shell is a 248 px left rail (the section list with every Alt+N
printed, a PANELS list with strip/float/add badges, a PACKS list, the Fleet
strip, a LAYOUT block with a paragraph of drag instructions plus Arrange and
Reset), a 340 px inspector always open, a first-visit welcome card that opens
the section help the first time each section shows in a browser (Setup
excepted since 3.3.1.0), and panels that each carry a title bar, HUD
brackets, a glass border and an about line. Three rounds make it quiet; the
holo palette stays, the ornament goes to the thing you are looking at.

- R1 nothing opens on any tab, the icon rail, the inspector asks first.
  (a) No section opens anything on load: the first-visit welcome
  (`lib/store.ts welcomeIfNew`, `SEEN_PREFIX`) is gone for every section,
  the Start here overlay shows only on a fresh home's first section and
  never again once dismissed; the ? in the header and each panel's help
  stay one click away. (b) The left column is an icon rail of about 56 px:
  one icon per core section (and per pack section, with the diamond), its
  title as a tooltip and as a label only while the rail is expanded (a
  chevron at its foot toggles expanded/icons, remembered per browser), the
  current one lit, a session dot when something is live, the Fleet strip
  reduced to its live count on the Fleet icon; Alt+N keeps working but the
  printed shortcuts leave the rows (they live in the Ctrl+K palette and the
  ? help). (c) The inspector (340 px) is closed by default and opens when
  something is selected (a card, a session, a run); closing it returns the
  width to the stage; the choice is remembered per browser. (d) A Focus
  toggle (F outside a text field, and a header button) hides the rail, the
  inspector and the status bar in one keystroke; F again brings them back.
  Tests: a Chrome driver that loads every section of a seeded home and a
  fresh home and finds no dialog, no help panel and no overlay after 2 s
  (except Start here on the fresh home's first section, once); the rail's
  width budget (<= 64 px collapsed, <= 248 px expanded) and its rows
  without printed shortcuts; Alt+1..8 still switch; the inspector closed on
  load and open after a selection; F toggles. Every existing pin on the
  rail (section order, Alt+9 for packs, the banner) follows.
- R2 panels and layout leave the rail. The PANELS list becomes a small "+"
  menu in the section header (add a panel, bring one back, with the same
  strip/float words); Arrange and Reset become palette entries and two rows
  in the header's overflow menu; the drag instructions move into the
  section help ("Moving panels"); the LAYOUT · YOURS/DEFAULT word becomes a
  small badge in the header shown only when the layout is custom. The rail
  holds sections only. Tests: the "+" menu adds and brings back a panel; the
  palette's Arrange works; the rail has no panel rows.
- R3 quieter panels, one thing per section, a density setting. (a) A panel
  is one title line and a plain border; brackets, glow and the mono data
  strip appear only on the focused panel; the per-panel about line goes
  (the panel's help holds it; the ? on the title opens it). (b) Every
  section opens on one thing: Session on the live session, Team on the
  lineup, Roles on the canvas, Fleet on the map, Design on the board,
  Orchestra on the plan, Packs on the manager; the secondary panels start as
  strips at the foot (the saved layout, when the user made one, wins).
  (c) A density setting in the header (comfortable / compact) sets the
  spacing and type scale through two token sets in `styles/tokens.css`,
  remembered per browser. (d) Placeholder lines that say what an empty area
  already says ("reading the setup...", "no sessions yet" over an empty
  list) go. Tests: a capture per section at 1280 px with the rail budget
  and the "one thing" default pinned (the first panel's box covers most of
  the stage), the focused-panel-only ornament (a class on one panel at a
  time), the density tokens switching. Docs: STUDIO.md, STUDIO-shell.md,
  STUDIO-sections.md (rail, inspector, Focus, density, "nothing opens on
  its own"), the README's Studio screenshots re-rendered.
