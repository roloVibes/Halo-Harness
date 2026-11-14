# The docs map

Read this when you do not know which doc to open: every doc, by what you want to do, with one line on when to read it.

**Multi-agent. Multi-workflow. Fully visible.** The multi-agent, multi-workflow harness you can watch: every model's
thinking, hand-offs and cost, live, and yours to steer. See, shape and steer multi-model agent work, on any model,
including your own.

- **See** what every agent thinks, says to another agent, runs and costs, live: Studio's Session and Agents -> Live
  ([STUDIO-sections.md](STUDIO-sections.md#session), [STUDIO-live.md](STUDIO-live.md)).
- **Shape** the work: lineups and blocks on a canvas, `when` connections, workflows, steering, goal runs
  ([STUDIO-agents.md](STUDIO-agents.md), [STUDIO-blocks.md](STUDIO-blocks.md), [ORCHESTRA.md](ORCHESTRA.md)).
- **Mix** models: a model per role across providers, the `auto` lineup, `/model` mid-session
  ([MODELS.md](MODELS.md), [ROLES.md](ROLES.md)).
- **Local** models first-class: the steward, fit badges, benchmarks, `halo host`, the pool
  ([STUDIO-local.md](STUDIO-local.md), [MODELS-ollama-steward.md](MODELS-ollama-steward.md)).
- **Start** in Studio's Setup; an existing Claude Code setup is read in place, and none is needed
  ([INSTALL.md](INSTALL.md), [STUDIO-setup.md](STUDIO-setup.md)).

Everything else is a pack ([PACKS.md](PACKS.md)).

Each doc opens with the same "Read this when" line it has here. The longest docs are split by task: the
original file is a short entry page and its parts are listed under it. New to Halo? Start with
[INSTALL.md](INSTALL.md), then the [HANDBOOK.md](HANDBOOK.md).

## I want to set up

Install Halo, connect your models and providers, and fix what goes wrong.

- [INSTALL.md](INSTALL.md) (Install): read this when you install, upgrade or update Halo.
- [MAC.md](MAC.md) (Mac quick-start (Apple Silicon)): read this when you check Halo with local models on an Apple Silicon Mac.
- [LOCAL-MODELS.md](LOCAL-MODELS.md) (Local and cloud models): read this when you set up Ollama, Hugging Face or the OpenAI API end to end.
- [HOST.md](HOST.md) (halo host): read this when a machine serves models and you want every harness on the LAN to read its card, its models, its log and its profiles without a session or ssh there.
- [POOL.md](POOL.md) (The pool: one model across several machines): read this when you want to run a model too big for any one of your GPUs across the GPU memory of several machines on your LAN, warm or stop it, or you want to know what the pool can and cannot do.
- [VOICE.md](VOICE.md) (Voice: talk to a session, the speech models and Halo's speech server): read this when you want to talk to a Halo session and hear it answer on your own machine, or want speech-to-text or text-to-speech locally: the voice loop, its modes, barge-in and latency card, the voice-local bundle, the speech models Halo knows, how to download and serve one, where it runs, and what the steward says about it.
- [VOICE-glasses.md](VOICE-glasses.md) (Voice through Meta's glasses: the phone-app contract): read this when you want to build the phone app that carries Meta's Ray-Ban or Oakley glasses into a Halo session -- what the app has to do step by step, the host's voice door it talks to with a worked example, the latency budget, and the honest limits of the glasses.
- [VOICE-cpu.md](VOICE-cpu.md) (Voice on a box with no GPU): read this when you want the voice loop on a machine with no GPU (a Kali VM, a laptop, a small server): which speech models to run on the CPU, how to point the loop at another halo's GPU instead, and how to read what it measures.
- [DATABRICKS.md](DATABRICKS.md) (Databricks): read this when you run Halo against Databricks model serving, at work or with a team preset.
- [PROVIDERS-copilot.md](PROVIDERS-copilot.md) (Copilot at work): read this when you want Halo to use your work's Microsoft 365 Copilot: register the app, sign in, ask it from a terminal, put it in a lineup or give agents the `copilot_ask` tool, and read what each error line means.
- [MODELS.md](MODELS.md) (Models): read this when you need the exact behaviour of a model route: how a model name resolves, what each provider sends, the catalogs and the prices.
  - [MODELS-references.md](MODELS-references.md) (Models: references, picks and provider enablement): read this when you type a model name or prefix (`or:`, `dbx:`, `ant:`, `oai:`, `ol:`, `hf:` ...), choose a model for a job, or turn a provider on or off.
  - [MODELS-ollama.md](MODELS-ollama.md) (Models: Ollama hosts, requests and the catalog): read this when you point Halo at an Ollama host and want to know what it sends, how context is sized and how the host is checked.
  - [MODELS-ollama-tuning.md](MODELS-ollama-tuning.md) (Models: Ollama fit, calibration and the gym): read this when a local model does not fit, calls tools badly, or you want `halo gym` scores and role defaults for your GPU.
  - [MODELS-switching.md](MODELS-switching.md) (Models: switching models and effort on a local model): read this when you move a session from one model to another (`/model`, a lineup's per-task pick, a resumed session, a compaction model) or wonder what the effort level does on a local model.
  - [MODELS-prompt-budget.md](MODELS-prompt-budget.md) (Models: what Halo sends a local model): read this when a local model answers as if it never saw the task, you want to know what a request to a model is made of in tokens, or a request is larger than the model's window.
  - [MODELS-prompt-diet.md](MODELS-prompt-diet.md) (Models: the local prompt diet): read this when you want to know what Halo's own first turn costs a local model before you use it, why a tool is not in a local model's list, or why the reply's room is smaller than 16,384.
  - [MODELS-vision.md](MODELS-vision.md) (Models: which models can see): read this when you want to share a screenshot or an image with a model and need to know which models can see, how Halo knows, and what happens when the model in use cannot.
  - [MODELS-cards.md](MODELS-cards.md) (Models: what a local model can do): read this when you pick a local model and want to know what it is (thinking, tools, vision, coding or embedding), how Halo will call it, whether it fits this machine, and what to do when it cannot run the main agent.
  - [MODELS-ollama-steward.md](MODELS-ollama-steward.md) (Models: the Ollama steward): read this when you want to know what the Ollama steward knows, records, finds and changes across your halos and model servers.
  - [MODELS-ollama-steward-host.md](MODELS-ollama-steward-host.md) (Models: the steward and the host): read this when the model you tune is served by a `halo host` and you want to know where the steward runs, how its fixes land on that host and what comes back.
  - [MODELS-ollama-steward-sched.md](MODELS-ollama-steward-sched.md) (Models: scheduling the local models): read this when a lineup runs several local models on one card (or across machines) and you want to know what stays loaded, when a model is swapped in, what each swap costs and where each lane should run.
  - [MODELS-ollama-steward-guards.md](MODELS-ollama-steward-guards.md) (Models: guards and the off-hours refresh): read this when you want to know how Halo keeps the record of your local models true with no effort: who else is using a card, when the battery and the bench re-run on their own, and what happens when a tag changes or is deleted.
  - [MODELS-steward-servers.md](MODELS-steward-servers.md) (Models: the steward and the local servers): read this when you run llama-server, LM Studio, mlx_lm.server or another local engine and want to know what the steward reads in each one's log, what each log can and cannot say, what the steward changes on Halo's side and which server-side line it states.
  - [MODELS-engines.md](MODELS-engines.md) (Models: other local engines): read this when you run (or want to run) a local engine beyond llama-server and mlx_lm.server -- FreeToken, Strata or TensorFold -- and need to know what Halo does with it, how to install it, whether a model fits your box, what the steward reads in its log, or how to add another engine.
  - [MODELS-adviser.md](MODELS-adviser.md) (Models: the roster adviser): read this when you want Halo to tell you which local models you are missing, which overlap, which do not suit their roles and which have a newer line -- with the numbers and one click each.
  - [MODELS-bundles.md](MODELS-bundles.md) (Models: bundles and reservations): read this when you want to turn on a capability that holds a local model for one use (voice, a verifier, a compactor, embeddings) and need to know before anything downloads whether it fits, what it reserves and where the rest of the work goes.
  - [MODELS-ollama-steward-chat.md](MODELS-ollama-steward-chat.md) (Models: the steward's chat and its candidates): read this when you want to ask the steward about your local models in plain words, see what its answer cost, let it make a Halo-side change, or choose the small model it runs on.
  - [MODELS-ollama-logs.md](MODELS-ollama-logs.md) (Models: the Ollama server log): read this when you want to know how Halo reads an Ollama host's server log, whether that log is live, how the log drives a call's recovery, what a crash fingerprint holds and what Halo proposes when a crash repeats, how a failed local call walks the degradation ladder, what the answer post-mortem reads and how the model shelf retires a model.
  - [MODELS-huggingface.md](MODELS-huggingface.md) (Models: Hugging Face): read this when you use the Hugging Face router, a dedicated endpoint, or a local llama-server, LM Studio or MLX server (`hf:`).
  - [MODELS-openai-codex.md](MODELS-openai-codex.md) (Models: the OpenAI API): read this when you use `oai:` with an OpenAI key.
  - [MODELS-experiential.md](MODELS-experiential.md) (Models: Experiential Labs): read this when you route models through the Experiential Labs gateway (`xp:`).
  - [MODELS-families.md](MODELS-families.md) (Models: families, Qwen and reasoning effort): read this when a model family behaves differently (DeepSeek, Kimi, GLM, Qwen) or you set the reasoning effort.
  - [MODELS-catalog.md](MODELS-catalog.md) (Models: the catalog, prices and the picker): read this when you refresh the model list, read a price or DBU cost, use the `/model` picker, or go offline.
- [CONFIG.md](CONFIG.md) (Configuration): read this when you want to know which file sets what: every config file, key and environment variable Halo reads.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) (Troubleshooting): read this when something looks wrong: each symptom, the doctor line that names it, and the fix.

## I want to run agents

Work in the TUI and on the command line, and give agents bios, lineups, roles and jobs.

- [CREW-FORMATS.md](CREW-FORMATS.md) (Crew files: agents, workflows and maps): read this when you write or read an agent, a workflow or a map file by hand, want to know where Halo keeps them, or want to know what an agent file becomes when a session spawns it.
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
  - [COMMANDS-remote.md](COMMANDS-remote.md) (Commands: remote control): read this when you control sessions remotely.
  - [COMMANDS-host.md](COMMANDS-host.md) (Commands: halo host): read this when you run `halo host` on a machine that serves models, pair a harness with it, or install it as a service.
  - [COMMANDS-pool.md](COMMANDS-pool.md) (Commands: halo pool): read this when you put several machines' GPUs together for one model: list or edit the pool's members, scan the LAN for rpc-server ports, ask what the pool can run, or run the preflight, warm, stop and read the running pool.
  - [COMMANDS-copilot.md](COMMANDS-copilot.md) (Commands: halo copilot): read this when you sign in to your work's Microsoft 365 Copilot from a terminal, ask it a question about your mail, meetings, chats or files, or sign out again.
  - [COMMANDS-voice.md](COMMANDS-voice.md) (Commands: halo voice, the voice loop and the speech servers): read this when you talk to a session from the command line (`halo voice`, `halo voice on|off`, an input file, `halo voice client` through a halo host), list the microphones, read the voice turns' latency, or list, download, remove or serve a speech model.
  - [COMMANDS-local-servers.md](COMMANDS-local-servers.md) (Commands: a local server's log and events): read this when you want to read a llama-server, LM Studio or mlx_lm.server log from a terminal, see the events the steward found in it, or know why a server's log is not read.
  - [COMMANDS-local-guards.md](COMMANDS-local-guards.md) (Commands: refresh, advise and the guards): read this when you re-measure stale local models by hand, ask Halo what to add or retire, or point a role at the nearest equivalent of a deleted tag.
  - [COMMANDS-ollama-chat.md](COMMANDS-ollama-chat.md) (Commands: the steward's chat and candidates): read this when you ask the steward a question from a terminal, or want the list of models that could run it.
  - [COMMANDS-supervise.md](COMMANDS-supervise.md) (Commands: the supervisor, its goals and knowledge): read this when you give Halo a goal to work on without sitting at a terminal, keep what it verified and decided, or isolate its workers.
  - [COMMANDS-packs.md](COMMANDS-packs.md) (Commands: packs): read this when you list, inspect, install, enable, grant, update, roll back or remove a pack, or name where packs come from, on the command line (`halo pack`).
  - [COMMANDS-packs-kit.md](COMMANDS-packs-kit.md) (Commands: the pack kit): read this when you start a pack, check one, or install your own folder so every edit shows at once (`halo pack new`, `halo pack test`, `halo pack install --link`).
  - [COMMANDS-workflows.md](COMMANDS-workflows.md) (Commands: workflows): read this when you list, show, check or run a workflow from the command line (`halo workflow`), or list, enable and test workflow squares (`halo workflows`).
  - [COMMANDS-whatsnew.md](COMMANDS-whatsnew.md) (Commands: what changed): read this when you want to know what a Halo version changed on a box with no repo (`halo whatsnew`).
  - [COMMANDS-proxy.md](COMMANDS-proxy.md) (Commands: the proxy, exit codes and config checks): read this when you run the old proxy, read an exit code, or list and check the config files in effect.
- [SLASH-COMMANDS.md](SLASH-COMMANDS.md) (Slash commands, keys, and prompt prefixes): read this when you want what a `/command`, a key or a prompt prefix does in the TUI.
  - [SLASH-COMMANDS-session.md](SLASH-COMMANDS-session.md) (Slash commands: sessions, models and context): read this when you manage the session, its model, memory, permissions or config from the prompt (`/clear`, `/model`, `/recall`, `/config` ...).
  - [SLASH-COMMANDS-agents.md](SLASH-COMMANDS-agents.md) (Slash commands: agents, lineups, roles and review): read this when you work with bios, lineups, roles or `/review` from the prompt.
  - [SLASH-COMMANDS-providers.md](SLASH-COMMANDS-providers.md) (Slash commands: providers, remote control and upkeep): read this when you set up providers, rate limits or remote control, or run `/doctor`, `/update` and `/bugreport`.
  - [SLASH-COMMANDS-tui.md](SLASH-COMMANDS-tui.md) (Slash commands: themes, Studio and the TUI): read this when you change themes, open Studio, copy, rewind or tune the TUI, run the guided first run or the checks, look up a word, or add your own commands, skills and images.
  - [SLASH-COMMANDS-keys.md](SLASH-COMMANDS-keys.md) (Slash commands: prefixes, keys and cards): read this when you want the `@path` and `!cmd` prefixes, a key binding, or the keys a card answers to.
- [GLOSSARY.md](GLOSSARY.md) (Glossary): read this when a word in Halo is new to you.
- [AGENTS.md](AGENTS.md) (Agent bios and team templates): read this when you write or edit an agent bio or a lineup, field by field.
- [ROLES.md](ROLES.md) (Roles): read this when you point different kinds of work at different models with roles.
- [PACKS.md](PACKS.md) (Packs): read this when you add a pack of bios, lineups, skills, commands, hooks and MCP servers to Halo, or take one out again.
- [WORKFLOWS.md](WORKFLOWS.md) (Workflows): read this when you write or run a pack's workflow: its stages compiled to an Orchestra run, its typed artifacts, events and memory.
- [WORKFLOWS-squares.md](WORKFLOWS-squares.md) (Workflow squares): read this when you want the main agent to hand a task to a saved workflow (a square): the contract, where squares come from, how the router picks one, the receipts and the Workflows board.
- [ORCHESTRA.md](ORCHESTRA.md) (The Orchestra): read this when several agents should write the same files at once: the Orchestra and its plan, lanes and judge.
- [WORK.md](WORK.md) (One unit of work): read this when you want the one model under an Orchestra lane and a supervisor goal.
- [SUPERVISE.md](SUPERVISE.md) (The supervisor): read this when you want to give Halo a goal at night and open Studio in the morning to see what finished, what waits on you and what it cost.
- [OUTCOMES.md](OUTCOMES.md) (Verified outcomes and measured routing): read this when you want to know what an agent's work showed (its tests, sources, commands, files), how each outcome is recorded per bio and model, and how a bio can route to the model that succeeded most here.
- [ISOLATION.md](ISOLATION.md) (Isolation): read this when a lineup's workers should run in a container or as another OS user, get their keys from a secret broker, or see only some of the tools.
- [KNOWLEDGE.md](KNOWLEDGE.md) (Knowledge: findings and decisions): read this when you want what Halo verified or decided to outlive the session that found it: findings and decisions, who writes them, the files, the agents' tools and citing what was reused.
- [RECALL.md](RECALL.md) (Recall): read this when you search what Halo remembers -- memory topics, past sessions, the coach library, findings, decisions and your own notes (an Obsidian vault) -- or point it at a folder of your notes.
- [COMFYUI.md](COMFYUI.md) (ComfyUI in Halo): read this when you want Halo to render images or video with ComfyUI on your own GPU.
- [SUBAGENTS.md](SUBAGENTS.md) (Sub-agent visibility and scale): read this when you watch or limit sub-agents: the tasks panel, concurrency and depth.
- [REVIEW.md](REVIEW.md) (Code review: `/review` and `halo review`): read this when you review code with `/review` or `halo review`.
- [GOVERNOR.md](GOVERNOR.md) (The Governor): read this when requests to one gateway slow down, fail over or queue: the shared rate limiter.

## I want to use Studio

The browser console: every agent of your session live, your lineups and their runs (Agents), and designs.

- [STUDIO.md](STUDIO.md) (Halo Studio): read this when you use Halo Studio, the browser console where you watch every agent work: the Session dashboard, your lineups and their runs in Agents, and designs.
  - [STUDIO-shell.md](STUDIO-shell.md) (Studio: the shell): read this when you find your way around Studio's header, sections, panels and Start views, or open it on a bio, a lineup or the team's door.
  - [STUDIO-session.md](STUDIO-session.md) (Studio: steering and exporting a session): read this when you steer an agent from Session's Live column and want to know which agent and which call it reaches, or save a session as one Markdown trace file, or ask why an answer came out as it did, or type a turn into the session from Studio with the Prompt panel, or run a session from Studio with no terminal at all.
  - [STUDIO-sections.md](STUDIO-sections.md) (Studio: how each section works): read this when you want the one-screen story of a section (Session, Agents, Local, Packs, Setup, Settings).
  - [STUDIO-builder.md](STUDIO-builder.md) (Studio: Agents -> 1 · Agents and the builder): read this when you make or change an agent in Studio's Agents tab, ask the builder box to do it for you, try an agent once before you use it, or want to know what the builder can and cannot change, what it costs and how Undo works.
  - [STUDIO-workflows.md](STUDIO-workflows.md) (Studio: Agents -> 2 · Workflows and the step runner): read this when you make or change a workflow in Studio's Workflows tab, ask the builder box to draft one, try a workflow once before you use it, run one from a session, or want to know what runs underneath, what a repeat costs and what stops a run.
  - [STUDIO-agents.md](STUDIO-agents.md) (Studio: Agents): read this when you work with your agents in Studio's Agents section: the lineup and its bios (Cast), what runs now and what ran (Live, a goal run on it, History), the board of squares (Workflows), and the doors the old Team, Roles, Orchestra and Runs left.
  - [STUDIO-live.md](STUDIO-live.md) (Studio: Agents -> Live, the living canvas): read this when you watch what runs now on Studio's Agents -> Live: why it shows only what is happening, where the past went (History and replays), the plan drawn under the agents, what each agent waits on, the one sentence under the bar, the three zoom levels, the scrubber that takes the canvas back in time, the glance (one phone-width page) and the alert when something starts waiting on you.
  - [REPLAY.md](REPLAY.md) (Replays: scrub a run back in time, save it as one file, film a clip, compare two runs, read its report card): read this when you want to see what a session looked like at an earlier moment on Studio's Agents -> Live, save a run's replay as one file to open on another machine, turn a stretch of it into an animated clip, compare two runs side by side (`halo replay list | save | open | clip | compare`), or read a finished run's report card (`halo report`).
  - [STUDIO-blocks.md](STUDIO-blocks.md) (Studio: blocks and groups): read this when you compose the lineup on Agents -> Cast as blocks (a tier with its purpose, a workflow square with the agents inside it) or watch Agents -> Live box the sub-agents of one task.
  - [STUDIO-feed.md](STUDIO-feed.md) (Studio: the live feed): read this when you want how Studio's pages get their live frames: the Server-Sent Events stream, its kinds and its catch-up.
  - [STUDIO-orchestra.md](STUDIO-orchestra.md) (Studio: a goal run on Live and in History): read this when you run an Orchestra goal from Studio: Run a goal on Agents -> Live, the run as a job on Live, its plan review, its lanes in the inspector, and its report in History.
  - [STUDIO-live-panels.md](STUDIO-live-panels.md) (Studio: Attention, costs, hand-offs and recordings): read this when you answer what waits on you from Studio, watch what your sessions spend, hand an agent's work on, record a session, hop between agents with the keys, or want to know what Studio reads and writes for them.
  - [STUDIO-team-roles.md](STUDIO-team-roles.md) (Studio: Team and Roles): read this when a link sent you to Studio's Team or Roles section: since 3.3.16.0 both are Agents (STUDIO-agents.md).
  - [STUDIO-packs.md](STUDIO-packs.md) (Studio: the Pack Manager): read this when you install, grant, enable, set up, update or remove packs from Studio's Packs section.
  - [STUDIO-local.md](STUDIO-local.md) (Studio: the Local section): read this when you watch the machines that serve your local models and what they serve: the live resources and traffic, every host with its controls, every model with its fit, the library of models you could install, and the Hugging Face models on disk with the local servers Halo starts for them.
  - [STUDIO-local-media.md](STUDIO-local-media.md) (Studio: Local -> the Media panels): read this when you check ComfyUI from Studio: whether it answers, its models and its workflows, in the Media panels the palette opens on Local.
  - [STUDIO-local-routes.md](STUDIO-local-routes.md) (Studio: the Local section's routes): read this when you call Studio's Local routes yourself or want the live frames the Local section listens to.
  - [STUDIO-local-steward.md](STUDIO-local-steward.md) (Studio: Local -> Steward): read this when you talk to the steward from Studio, choose the model it runs on, or press a button its answer left.
  - [STUDIO-local-pool.md](STUDIO-local-pool.md) (Studio: Local -> Pool): read this when you look at the pool from Studio: its members and their free VRAM, Warm and Stop with the preflight, what the pool can run, the Scan, or the Library's Pool preset.
  - [STUDIO-local-voice.md](STUDIO-local-voice.md) (Studio: Local -> Voice): read this when you talk to a Halo session from Studio with your browser's microphone, start or stop the speech servers, download a speech model, turn a session's voice loop on or off, or read the last turns' latency cards.
  - [STUDIO-setup.md](STUDIO-setup.md) (Studio: the Setup section): read this when you set this box up from Studio's Setup section: what each block writes and the routes behind it.
  - [STUDIO-redesign-brief.md](STUDIO-redesign-brief.md) (Studio: a brief for a new look): read this when you design a new look for Halo Studio, or hand the job to a design session: what Studio is made of, what a look must be expressed as, and what must not change.
  - [STUDIO-security.md](STUDIO-security.md) (Studio: saving, security, SSH and shortcuts): read this when you save and apply from Studio, run it over SSH, check what it lets a page do, or want every shortcut.
- The design pack (3.3.13.0 R2: the Design section, out of the core) keeps its own docs: the project on disk, a design turn,
  the craft apps and the Studio section with its routes, in [its README](../halo_harness/templates/packs/design/README.md)
  and its docs/DESIGN.md and docs/STUDIO-design.md.

## I want to control a session from elsewhere

Control from another process or your phone.

- [REMOTE.md](REMOTE.md) (Remote control): read this when you control a running session from another process, or wire a transport (a phone, a chat) to Halo.

## I want to develop Halo

How Halo is built, tested and released, and the record of how it got here.

- [DEVELOPMENT.md](DEVELOPMENT.md) (Development): read this when you work on Halo itself: the repo layout, the test suites and the release flow.
- [CONTRIBUTING.md](CONTRIBUTING.md) (Contributing): read this when you send a change to Halo: the house rules and which suite to run.
- [ARCHITECTURE.md](ARCHITECTURE.md) (Architecture): read this when you want how Halo works inside: the session loop and every subsystem around it.
  - [ARCHITECTURE-session.md](ARCHITECTURE-session.md) (Architecture: the session loop): read this when you change how a request is built: the session log, pruning, providers, reasoning replay, the tool catalog and the repair layer.
  - [ARCHITECTURE-permissions.md](ARCHITECTURE-permissions.md) (Architecture: permissions, hooks and MCP): read this when you change permission rules and modes, the hooks protocol, or how MCP servers start and cache.
  - [ARCHITECTURE-runtime.md](ARCHITECTURE-runtime.md) (Architecture: steering, compaction, sub-agents and telemetry): read this when you change steering and interrupts, compaction, sub-agents and plan mode, or telemetry.
  - [ARCHITECTURE-tui.md](ARCHITECTURE-tui.md) (Architecture: the TUI event model): read this when you change how the TUI turns session events into widgets.
  - [ARCHITECTURE-modules.md](ARCHITECTURE-modules.md) (Architecture: the module map): read this when you look for the module behind a Studio, Orchestra or team feature.
  - [ARCHITECTURE-modules-two.md](ARCHITECTURE-modules-two.md) (Architecture: the module map, part two): read this when you look for the module behind the Ollama steward, packs, the extension API, isolation, Setup or Settings.
- [PACK-AUTHORING.md](PACK-AUTHORING.md) (Writing a pack: the kit, the loop, the checks): read this when you write a pack, or point a Halo session at a folder to write one, and want it to work the first time.
- [EXTENSION_API.md](EXTENSION_API.md) (The extension API): read this when you write a pack, or change what Halo promises a pack: the manifest, the lifecycle, what a pack may import and what each part's status is.
- [PACKS-inventory.md](PACKS-inventory.md) (Packs: the inventory of extension points): read this when you change how a pack plugs into Halo: the extension points a pack reuses and the places that assumed nothing outside Halo adds files.
- [WIZARD.md](WIZARD.md) (The wizard interaction model): read this when you change or add a wizard screen: the ten rules every screen follows.
- [MEDIA.md](MEDIA.md) (The front-page media): read this when you regenerate the front-page pictures and animations.
- [PRIVACY.md](PRIVACY.md) (Privacy and the public repo): read this when you check what Halo keeps out of the repo, or audit a checkout before you publish it.
- [harness/README.md](harness/README.md) (`docs/harness/` -- the build history): read this when you look for the research notes, briefs and reviews behind a Halo release.
- [design-review-2026-09-23.md](design-review-2026-09-23.md) (Design review notes — 2026-09-23 (Opus 5.5 advisor pass on the foundation plan)): read this when you want the history of the first design review (2026-09-23); it is a record, not a guide.
- [m4-6-brief.md](m4-6-brief.md) (Milestones 4–6 brief (Databricks live route, Claude passthrough, overflow/compaction, reasoning log, probe)): read this when you want the history of milestones 4 to 6 of the original proxy; it is a record, not a guide.
- [review-findings-m4-6.md](review-findings-m4-6.md) (Review findings — M4–M6 integration (Opus 5.5 advisor pass, 2026-09-23)): read this when you want the history of the milestone 4 to 6 review; it is a record, not a guide.
