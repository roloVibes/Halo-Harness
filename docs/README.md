# The docs map

Read this when you do not know which doc to open: every doc, by what you want to do, with one line on when to read it.

Each doc opens with the same "Read this when" line it has here. The longest docs are split by task: the
original file is a short entry page and its parts are listed under it. New to Halo? Start with
[INSTALL.md](INSTALL.md), then the [HANDBOOK.md](HANDBOOK.md).

## I want to set up

Install Halo, connect your models and providers, and fix what goes wrong.

- [INSTALL.md](INSTALL.md) (Install): read this when you install, upgrade or update Halo.
- [MAC.md](MAC.md) (Mac quick-start (Apple Silicon)): read this when you check Halo with local models on an Apple Silicon Mac.
- [LOCAL-MODELS.md](LOCAL-MODELS.md) (Local and cloud models): read this when you set up Ollama, Hugging Face or the OpenAI API end to end.
- [DATABRICKS.md](DATABRICKS.md) (Databricks): read this when you run Halo against Databricks model serving, at work or with a team preset.
- [MODELS.md](MODELS.md) (Models): read this when you need the exact behaviour of a model route: how a model name resolves, what each provider sends, the catalogs and the prices.
  - [MODELS-references.md](MODELS-references.md) (Models: references, picks and provider enablement): read this when you type a model name or prefix (`or:`, `dbx:`, `ant:`, `oai:`, `ol:`, `hf:` ...), choose a model for a job, or turn a provider on or off.
  - [MODELS-ollama.md](MODELS-ollama.md) (Models: Ollama hosts, requests and the catalog): read this when you point Halo at an Ollama host and want to know what it sends, how context is sized and how the host is checked.
  - [MODELS-ollama-tuning.md](MODELS-ollama-tuning.md) (Models: Ollama fit, calibration and the gym): read this when a local model does not fit, calls tools badly, or you want `halo gym` scores and role defaults for your GPU.
  - [MODELS-switching.md](MODELS-switching.md) (Models: switching models and effort on a local model): read this when you move a session from one model to another (`/model`, a lineup's per-task pick, a resumed session, a compaction model) or wonder what the effort level does on a local model.
  - [MODELS-cards.md](MODELS-cards.md) (Models: what a local model can do): read this when you pick a local model and want to know what it is (thinking, tools, vision, coding or embedding), how Halo will call it, whether it fits this machine, and what to do when it cannot run the main agent.
  - [MODELS-ollama-steward.md](MODELS-ollama-steward.md) (Models: the Ollama steward): read this when you want to know what the Ollama steward knows, records, finds and changes across your halos and model servers.
  - [MODELS-huggingface.md](MODELS-huggingface.md) (Models: Hugging Face): read this when you use the Hugging Face router, a dedicated endpoint, or a local llama-server, LM Studio or MLX server (`hf:`).
  - [MODELS-openai-codex.md](MODELS-openai-codex.md) (Models: the OpenAI API): read this when you use `oai:` with an OpenAI key.
  - [MODELS-experiential.md](MODELS-experiential.md) (Models: Experiential Labs): read this when you route models through the Experiential Labs gateway (`xp:`).
  - [MODELS-families.md](MODELS-families.md) (Models: families, Qwen and reasoning effort): read this when a model family behaves differently (DeepSeek, Kimi, GLM, Qwen) or you set the reasoning effort.
  - [MODELS-catalog.md](MODELS-catalog.md) (Models: the catalog, prices and the picker): read this when you refresh the model list, read a price or DBU cost, use the `/model` picker, or go offline.
- [CONFIG.md](CONFIG.md) (Configuration): read this when you want to know which file sets what: every config file, key and environment variable Halo reads.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) (Troubleshooting): read this when something looks wrong: each symptom, the doctor line that names it, and the fix.

## I want to run agents

Work in the TUI and on the command line, and give agents bios, lineups, roles and jobs.

- [HANDBOOK.md](HANDBOOK.md) (Halo Harness handbook): read this when you want the long-form guide: configuration, providers, permissions, steering, hooks, skills, MCP, sessions and themes.
- [COMMANDS.md](COMMANDS.md) (Commands): read this when you want every `halo` subcommand and flag, with examples.
  - [COMMANDS-main.md](COMMANDS-main.md) (Commands: `halo` and its model and session flags): read this when you start `halo` with flags: the main command, its model and session flags.
  - [COMMANDS-main-io.md](COMMANDS-main-io.md) (Commands: `halo` output, prompt, settings, budget, browser, MCP and image flags): read this when you change what `halo` prints or reads, its system prompt, settings, budget, browser, MCP or images.
  - [COMMANDS-main-misc.md](COMMANDS-main-misc.md) (Commands: the other `halo` flags): read this when a `halo` flag is not in the other parts: misc flags, the ones not built yet or not applicable.
  - [COMMANDS-init.md](COMMANDS-init.md) (Commands: `halo init`, `halo start`, `halo check`, `halo explain` and `halo setup`): read this when you set Halo up (`halo init`, `halo setup`), run the guided first run (`halo start`) or the checks (`halo check`), or look up a word (`halo explain`).
  - [COMMANDS-health.md](COMMANDS-health.md) (Commands: doctor, audit, update and the installers): read this when you check, audit, update or reinstall Halo.
  - [COMMANDS-providers.md](COMMANDS-providers.md) (Commands: providers, rate limits and models): read this when you set up providers, read balances and rules, or refresh the model list.
  - [COMMANDS-mcp.md](COMMANDS-mcp.md) (Commands: MCP servers and connectors): read this when you add, list, repair or log in to MCP servers and claude.ai connectors.
  - [COMMANDS-ollama.md](COMMANDS-ollama.md) (Commands: Ollama): read this when you run or watch an Ollama server: `halo ollama` and its subcommands (calibrate, doctor, tune, discover, hardware, traffic, events, steward, explain).
  - [COMMANDS-local.md](COMMANDS-local.md) (Commands: the gym and local models): read this when you run local models: `halo gym`, `halo local`.
  - [COMMANDS-sessions.md](COMMANDS-sessions.md) (Commands: config, sessions, stats and reports): read this when you read or set config (`halo settings` opens Studio's Settings), replay or export a session, read stats, or file a bug report.
  - [COMMANDS-agents.md](COMMANDS-agents.md) (Commands: roles, review, bios and lineups): read this when you manage roles, reviews, bios and lineups from the command line.
  - [COMMANDS-studio.md](COMMANDS-studio.md) (Commands: Studio, design, media, Orchestra and teams): read this when you open Studio or run designs, media, an Orchestra goal or a team from the command line.
  - [COMMANDS-fleet.md](COMMANDS-fleet.md) (Commands: remote control and the fleet): read this when you control sessions remotely or run a fleet and its missions.
  - [COMMANDS-supervise.md](COMMANDS-supervise.md) (Commands: the supervisor, its goals and knowledge): read this when you give Halo a goal to work on without sitting at a terminal, keep what it verified and decided, or isolate its workers.
  - [COMMANDS-packs.md](COMMANDS-packs.md) (Commands: packs): read this when you list, inspect, install, enable, grant, update, roll back or remove a pack, or name where packs come from, on the command line (`halo pack`).
  - [COMMANDS-workflows.md](COMMANDS-workflows.md) (Commands: workflows): read this when you list, show, check or run a pack's workflow from the command line (`halo workflow`).
  - [COMMANDS-proxy.md](COMMANDS-proxy.md) (Commands: the proxy, exit codes and config checks): read this when you run the old proxy, read an exit code, or list and check the config files in effect.
- [SLASH-COMMANDS.md](SLASH-COMMANDS.md) (Slash commands, keys, and prompt prefixes): read this when you want what a `/command`, a key or a prompt prefix does in the TUI.
  - [SLASH-COMMANDS-session.md](SLASH-COMMANDS-session.md) (Slash commands: sessions, models and context): read this when you manage the session, its model, memory, permissions or config from the prompt (`/clear`, `/model`, `/recall`, `/config` ...).
  - [SLASH-COMMANDS-agents.md](SLASH-COMMANDS-agents.md) (Slash commands: agents, lineups, roles and review): read this when you work with bios, lineups, roles or `/review` from the prompt.
  - [SLASH-COMMANDS-providers.md](SLASH-COMMANDS-providers.md) (Slash commands: providers, fleet and upkeep): read this when you set up providers, rate limits, remote control or the fleet, or run `/doctor`, `/update` and `/bugreport`.
  - [SLASH-COMMANDS-tui.md](SLASH-COMMANDS-tui.md) (Slash commands: themes, Studio and the TUI): read this when you change themes, open Studio, copy, rewind or tune the TUI, run the guided first run or the checks, look up a word, or add your own commands, skills and images.
  - [SLASH-COMMANDS-keys.md](SLASH-COMMANDS-keys.md) (Slash commands: prefixes, keys and cards): read this when you want the `@path` and `!cmd` prefixes, a key binding, or the keys a card answers to.
- [GLOSSARY.md](GLOSSARY.md) (Glossary): read this when a word in Halo is new to you.
- [AGENTS.md](AGENTS.md) (Agent bios and team templates): read this when you write or edit an agent bio or a lineup, field by field.
- [ROLES.md](ROLES.md) (Roles): read this when you point different kinds of work at different models with roles.
- [PACKS.md](PACKS.md) (Packs): read this when you add a pack of bios, lineups, skills, commands, hooks and MCP servers to Halo, or take one out again.
- [WORKFLOWS.md](WORKFLOWS.md) (Workflows): read this when you write or run a pack's workflow: its stages compiled to an Orchestra run, its typed artifacts, events and memory.
- [ORCHESTRA.md](ORCHESTRA.md) (The Orchestra): read this when several agents should write the same files at once: the Orchestra and its plan, lanes and judge.
- [TEAM.md](TEAM.md) (Teams: people, blocks and stages (Halo 3.0.8.0)): read this when you set up a team file: who works on a repo, where their work lands and in which order.
- [WORK.md](WORK.md) (One unit of work): read this when you want the one model under an Orchestra lane, a mission part and a team stage.
- [SUPERVISE.md](SUPERVISE.md) (The supervisor): read this when you want to give Halo a goal at night and open Studio in the morning to see what finished, what waits on you and what it cost.
- [OUTCOMES.md](OUTCOMES.md) (Verified outcomes and measured routing): read this when you want to know what an agent's work showed (its tests, sources, commands, files), how each outcome is recorded per bio and model, and how a bio can route to the model that succeeded most here.
- [ISOLATION.md](ISOLATION.md) (Isolation): read this when a lineup's workers should run in a container or as another OS user, get their keys from a secret broker, or see only some of the tools.
- [KNOWLEDGE.md](KNOWLEDGE.md) (Knowledge: findings and decisions): read this when you want what Halo verified or decided to outlive the session that found it: findings and decisions, who writes them, the files, the agents' tools, citing what was reused and the fleet.
- [RECALL.md](RECALL.md) (Recall): read this when you search what Halo remembers -- memory topics, past sessions, the coach library, findings, decisions and your own notes (an Obsidian vault) -- or point it at a folder of your notes.
- [COMFYUI.md](COMFYUI.md) (ComfyUI in Halo): read this when you want Halo to render images or video with ComfyUI on your own GPU.
- [SUBAGENTS.md](SUBAGENTS.md) (Sub-agent visibility and scale): read this when you watch or limit sub-agents: the tasks panel, concurrency and depth.
- [REVIEW.md](REVIEW.md) (Code review: `/review` and `halo review`): read this when you review code with `/review` or `halo review`.
- [GOVERNOR.md](GOVERNOR.md) (The Governor): read this when requests to one gateway slow down, fail over or queue: the shared rate limiter.

## I want to use Studio

The browser console: every agent of your session live, your lineups, runs, fleet, team and designs.

- [STUDIO.md](STUDIO.md) (Halo Studio): read this when you use Halo Studio, the browser console where you watch every agent work: the Session dashboard, your lineups in Roles, runs, designs, fleet and team.
  - [STUDIO-shell.md](STUDIO-shell.md) (Studio: the shell): read this when you find your way around Studio's header, sections, panels and Start views, or open it on a bio, a lineup or the Team.
  - [STUDIO-session.md](STUDIO-session.md) (Studio: steering and exporting a session): read this when you steer an agent from Session's Live column and want to know which agent and which call it reaches, or save a session as one Markdown trace file.
  - [STUDIO-sections.md](STUDIO-sections.md) (Studio: how each section works): read this when you want the one-screen story of a section (Session, Team, Roles, Fleet, Design, Orchestra, Packs, Setup, Settings).
  - [STUDIO-feed.md](STUDIO-feed.md) (Studio: the live feed): read this when you want how Studio's pages get their live frames: the Server-Sent Events stream, its kinds and its catch-up.
  - [STUDIO-orchestra.md](STUDIO-orchestra.md) (Studio: the Orchestra console): read this when you run an Orchestra goal from Studio: the run console, the plan canvas and the coach.
  - [STUDIO-fleet.md](STUDIO-fleet.md) (Studio: Fleet): read this when you watch or steer every harness and agent from Studio's Fleet section.
  - [STUDIO-team-roles.md](STUDIO-team-roles.md) (Studio: Team and Roles): read this when you edit a team board or a lineup on the Roles canvas.
  - [STUDIO-design.md](STUDIO-design.md) (Studio: Design mode): read this when you make prototypes, pages or decks with Studio's Design section on your own creative apps.
  - [STUDIO-packs.md](STUDIO-packs.md) (Studio: the Pack Manager): read this when you install, grant, enable, set up, update or remove packs from Studio's Packs section.
  - [STUDIO-setup.md](STUDIO-setup.md) (Studio: the Setup section): read this when you set this box up from Studio's Setup section: what each block writes and the routes behind it.
  - [STUDIO-security.md](STUDIO-security.md) (Studio: saving, security, SSH and shortcuts): read this when you save and apply from Studio, run it over SSH, check what it lets a page do, or want every shortcut.
- [DESIGN.md](DESIGN.md) (Halo Design): read this when you make designs, pages, decks or logos with Halo Design on your own apps.

## I want to run a fleet

Several harnesses, one picture, one goal; and control from another process or your phone.

- [FLEET.md](FLEET.md) (Fleet): read this when you connect several harnesses into one fleet and watch or steer them from one place.
- [MISSIONS.md](MISSIONS.md) (Fleet missions): read this when you give one goal to the whole fleet and want to follow its parts.
- [REMOTE.md](REMOTE.md) (Remote control): read this when you control a running session from another process or from your phone over Signal.

## I want to develop Halo

How Halo is built, tested and released, and the record of how it got here.

- [DEVELOPMENT.md](DEVELOPMENT.md) (Development): read this when you work on Halo itself: the repo layout, the test suites and the release flow.
- [CONTRIBUTING.md](CONTRIBUTING.md) (Contributing): read this when you send a change to Halo: the house rules and which suite to run.
- [ARCHITECTURE.md](ARCHITECTURE.md) (Architecture): read this when you want how Halo works inside: the session loop and every subsystem around it.
  - [ARCHITECTURE-session.md](ARCHITECTURE-session.md) (Architecture: the session loop): read this when you change how a request is built: the session log, pruning, providers, reasoning replay, the tool catalog and the repair layer.
  - [ARCHITECTURE-permissions.md](ARCHITECTURE-permissions.md) (Architecture: permissions, hooks and MCP): read this when you change permission rules and modes, the hooks protocol, or how MCP servers start and cache.
  - [ARCHITECTURE-runtime.md](ARCHITECTURE-runtime.md) (Architecture: steering, compaction, sub-agents and telemetry): read this when you change steering and interrupts, compaction, sub-agents and plan mode, or telemetry.
  - [ARCHITECTURE-tui.md](ARCHITECTURE-tui.md) (Architecture: the TUI event model): read this when you change how the TUI turns session events into widgets.
  - [ARCHITECTURE-modules.md](ARCHITECTURE-modules.md) (Architecture: the module map): read this when you look for the module behind a Studio, fleet, Orchestra or team feature.
  - [ARCHITECTURE-modules-two.md](ARCHITECTURE-modules-two.md) (Architecture: the module map, part two): read this when you look for the module behind the Ollama steward, packs, the extension API, isolation, Setup or Settings.
- [EXTENSION_API.md](EXTENSION_API.md) (The extension API): read this when you write a pack, or change what Halo promises a pack: the manifest, the lifecycle, what a pack may import and what each part's status is.
- [PACKS-inventory.md](PACKS-inventory.md) (Packs: the inventory of extension points): read this when you change how a pack plugs into Halo: the extension points a pack reuses and the places that assumed nothing outside Halo adds files.
- [WIZARD.md](WIZARD.md) (The wizard interaction model): read this when you change or add a wizard screen: the ten rules every screen follows.
- [MEDIA.md](MEDIA.md) (The front-page media): read this when you regenerate the front-page pictures and animations.
- [PRIVACY.md](PRIVACY.md) (Privacy and the public repo): read this when you check what Halo keeps out of the repo, or audit a checkout before you publish it.
- [harness/README.md](harness/README.md) (`docs/harness/` -- the build history): read this when you look for the research notes, briefs and reviews behind a Halo release.
- [design-review-2026-09-23.md](design-review-2026-09-23.md) (Design review notes — 2026-09-23 (Opus 5.5 advisor pass on the foundation plan)): read this when you want the history of the first design review (2026-09-23); it is a record, not a guide.
- [m4-6-brief.md](m4-6-brief.md) (Milestones 4–6 brief (Databricks live route, Claude passthrough, overflow/compaction, reasoning log, probe)): read this when you want the history of milestones 4 to 6 of the original proxy; it is a record, not a guide.
- [review-findings-m4-6.md](review-findings-m4-6.md) (Review findings — M4–M6 integration (Opus 5.5 advisor pass, 2026-09-23)): read this when you want the history of the milestone 4 to 6 review; it is a record, not a guide.
