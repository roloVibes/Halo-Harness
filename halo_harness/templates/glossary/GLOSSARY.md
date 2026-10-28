# Glossary

Read this when a word in Halo is new to you.

Each word has one paragraph, and that paragraph is the one everything else shows: `halo explain <word>`
prints it, the TUI's `/explain <word>` shows it in a card, and Studio lists
every word under the `?` menu's Glossary (each section's "How this works"
page links the words it uses). `halo explain` with no word lists them all.

## lineup

A lineup (a team template, `~/.halo/teams/<name>.yaml`) says which agent bio, on which model, plays each role in your sessions, and in which tier each card sits. Each entry of its `agents:` list is a card. Halo ships six (`halo teams list`); a copy of one is yours to edit (Studio's Roles section, or `halo teams new <name> --from <shipped>`), and `halo teams use <name>` makes it the one new sessions use. `halo start` begins by copying `halo-dev-cycle` to `my-halo-dev-cycle`.

## bio

An agent bio (`~/.halo/agents/<name>.yaml`) describes one agent: its prompt, the models it prefers, its tools, its limits and the shape of what it hands back. A lineup's card points at a bio, and one bio can play several cards. Studio's Bios panel and `halo agents` edit bios; the coach's cards name the bio they would change.

## role

A role is the part a card plays in a session: `main` (the agent you talk to, exactly one per lineup), `subagent` (what the main agent spawns for a task), `reviewer`, `researcher`, `custom` and the others `halo roles` lists. When two cards share a role, the card's alias (`as:`) tells them apart, and routing and tiers use that alias.

## tier

A tier is a box of cards in a lineup's `tiers:` list: a member spawns only into the next tier down, `main` sits alone in tier 0, and `max_parallel` caps how many members of one tier run at once. A lineup with no tiers has one, `all`, holding every card. Studio's Roles canvas draws each tier as a box you drag cards between.

## team

A team (a team file, `<repo>/.halo/team.yaml`) is a project's people and work on one board: the brief every agent reads first, its members, the blocks their work lands in and the stages that run in order. `halo team init` writes one from the template and Studio's Team section shows it as a board. A lineup says who plays which part in a session; a team says who works on which part of a project.

## member

A member is one part of a lineup put to work on a team's project, on this machine or on a fleet harness (`harness:`). Each stage names the members that work on it; while the stage runs they write only inside its write blocks, and a part another member holds comes back naming the holder.

## block

A block is a place a team's work lands: a file, a folder or a git tree, each with its claim ledger (who holds which part, one change line per write). Stages read and write blocks, and a block that changes and then settles can start the stage that waits on it (`block_change:<block>`).

## stage

A stage is one step of a team's work: an agent turn or an Orchestra run, with the blocks it reads and writes, its members and its trigger (manual, `stage_done:<stage>` or `block_change:<block>`). A stage with a gate stops for your Accept, Redo or Stop before the stages after it start.

## lane

A lane is one worker's share of an Orchestra run: one job of the plan, with its claims, its own git worktree and branch, its state (joined, writing, written, in review, merged, or waiting when its piece came back), how often its piece came back and what it cost. `halo orchestra lanes` lists them; Studio's Lanes panel draws them with their hand-off edges.

## part

A part is one piece of a fleet mission: a slice of the goal given to the harness whose capabilities fit it, with its claims, its outputs and its hand-back. The hub's lead splits a mission into parts, and before you approve you can drag a part to another harness on Studio's map.

## step

A step is one box of a run's workflow, each with its state (pending, running, planned, done, failed or skipped): an Orchestra run's goal, lead, split, workers, merge, test, gate and done; and the seven screens of `halo start`.

## mission

A mission is one goal for the whole fleet: the hub's lead splits it into parts and gives each to the harness that can do it, you approve the plan, the parts run on their own machines, and the report says who did what and what it cost per harness. `halo fleet mission new` and Studio's Mission panel start one.

## gate

A gate is a check a run stops at before it goes on. An Orchestra run's gate runs your test on the merged branch and sends a failing piece back to its worker, up to the return cap; a team stage's gate waits for you to Accept, Redo with an instruction, or Stop.

## claim

A claim says who is writing which unit right now (`basket.py#total`: a function, a section or a whole file), so two agents never overwrite each other. A claim goes claimed, writing, written, released, and a claim on a unit someone else holds comes back naming the holder. `halo orchestra claims` lists the live ones; each team block keeps its own ledger.

## hand-off

A hand-off passes work from one lane, part or stage to the next: a job with `after` waits for another one, and with `needs` it takes that job's summary, its units or a file it saved, then starts from that job's finished head. A job that takes nothing sees only the goal. Studio labels each hand-off edge with what it carries.

## plan

The plan is the lead's split of a goal into jobs, one per lane, each with a title, its claims, an optional bio and model, `after` and its hand-offs. With `plan: review` (`halo orchestra run --review`) the run waits until you approve it (`halo orchestra approve`, or Approve and run on Studio's plan canvas) or reject it with a reason; every edit is checked before it is saved.

## coach

The coach reads a finished run's files (an Orchestra run, a mission or a team run) and suggests what to change next time: a bio's prompt, model or tools, a lane's `after`, a gate that looped. Each card shows its evidence; Ask the model has the run's lead explain it in one paragraph, Apply writes the change after one confirm (the file and its diff first) and Undo puts the file back. `halo coach` prints the cards.

## orchestra run

An Orchestra run is several agents writing the same files at once with nothing lost: a lead splits your goal (WHAT YOU WANT, DONE WHEN, STOP WHEN) into lanes, each worker writes its part in its own worktree under claims, the parts merge one at a time and the gate runs your test. `halo orchestra new` then `halo orchestra run` start one; its folder is `<repo>/.halo/orchestra/<run id>/`.

## fleet

The fleet is every Halo harness you run or joined, on any machine, seen as one: their sessions, every agent in them, what waits on you and what it all costs. A machine joins with a pair code (`halo fleet pair` on the hub, `halo fleet join` on the other machine); `halo fleet` is the live table and Studio's Fleet section the map.

## hub

The hub is the harness the others join (`halo studio --fleet` or `halo fleet serve`): it keeps the fleet's member list, relays commands and hand-offs between harnesses, and its lead plans missions. A joined harness talks to it over a fingerprint-pinned connection.

## harness

A harness is one running Halo install on one machine with its own home (`~/.halo`): its fleet id, its sessions, its lineups and its capabilities. Halo itself is the harness in "Halo Harness": the program that runs a model's turns with Claude Code's tools and configuration.

## capability

A capability is something a harness can do, as its spec card lists it: its hardware (GPU, memory), the models it reaches, its craft apps, its MCP servers and their tools, its skills and its tags. A mission gives each part to a harness whose capabilities fit it, and `halo fleet who "<query>"` ranks the fleet for what you need.

## unit

A unit of work is what a lane, a mission part and a team stage all are underneath (`halo work`, docs/WORK.md): one piece of work with an owner, its claims, its hand-offs, one state machine, a gate, an acceptance and a cost. The three engines keep their own words on top; the shared model gives them one ledger line, one report row and one coach.

## pack

A pack is a folder someone else maintains that adds bios, lineups, workflows, skills, commands, hooks, MCP servers, Studio sections and fleet capabilities to your Halo without changing Halo itself; every name it offers carries its id (`doc-review--reviewer`). It lives in `~/.halo/packs/<id>/` (or a repo's `.halo/packs/`), installs disabled, and runs once you enable it and grant what it asks for. `halo pack` installs, enables, updates and removes one (docs/PACKS.md), and Studio's Pack Manager (the Packs section) does the same with buttons.

## guided first run

The guided first run is `halo start`: one real Orchestra run on your own models that walks the pieces Halo is made of (a copy of a shipped lineup, a sample git repo, one goal, the lead's plan for you to approve, the lanes, the report and the coach) in seven screens. It is not a test of your models (`halo gym` measures them). It opens on a card that says the models it will call, an estimated cost, the time and what it writes; `halo start --explain` prints only the card, and Studio's Start here shows it above its Run button.

## setup

Setup is what a box needs before Halo can work on it: the providers it calls, the default model, the permission mode, the terminal theme and the lineup. `halo init` walks it as the terminal wizard, and Studio's Setup section (3.3.0.0) holds the same blocks as forms you fill in any order, each with its own Save; both write `~/.halo/config.json` (and the keys to the env file), the same keys `halo config set` writes.

## provider

A provider is a service Halo calls a model on: OpenRouter, Databricks, the Anthropic API, OpenAI, TypeSafe, Experiential Labs, an Ollama server or Hugging Face. A provider is set up when its key (or its host) resolves; its models then fill the catalog (`halo models`), and a model ref names its provider by its prefix (`or:` OpenRouter, `dbx:` Databricks, `ol:` an Ollama host). `halo init` and Studio's Setup section set one up.

## env file

The env file (`~/.config/halo/env`, or the file `HALO_ENV_FILE` names) holds the provider keys Halo reads, one `NAME=value` line each, written with owner-only permissions; `~/.halo/config.json` keeps only the names of those variables, never a key. `halo init` writes it, every Halo process reads it at start, and a tool's child process never sees its keys.

## config key

A config key is one setting in `~/.halo/config.json`, named by its dotted path (`fleet.enabled`, `ollama.discover.ports`); `halo config get` reads it, `halo config set <key> <value>` writes it, and a key you never set falls back to its default. Studio's Settings section (3.3.3.0) lists every key, one page per group, each row with its help line, its value against its default, Reset to default and the exact `halo config set` line; docs/CONFIG.md's key table is the same list in words.

## steward

The Ollama steward (3.3.4.0) watches every halo's calls to a local model server: one ledger line per call, the server's own log lines and the card it runs on. Its rules find what is wrong per host and model (a window too small, a reply cut, two windows reloading one model), it plans what fits the card, and it changes Halo's side of the calls (a profile) per `ollama.steward.apply`: `auto` applies, `review` proposes, `off` reports. It never writes to a server; a server-side change is a line for you to copy. Fleet's Ollama panel, Settings -> Ollama, `/ollama` and `halo ollama steward` show it.

## profile

A profile (Ollama) is what every halo reads before a call to one model on one host: `ollama.profiles["<host>|<model>"]` in `~/.halo/config.json`, with the window (`num_ctx`), the reply reserve (`num_predict`), keep-alive, the tool cap, another host to ask instead, and when to compact. The steward writes one and says why (`by: steward`), a hub hands its own to its members (`by: hub`), and yours (`by: user`) always wins; `halo ollama steward undo` reverts the steward's newest change.

## fit plan

The fit plan is the steward's answer to "do the models the halos ask for fit this card together?": from the hardware card, what else holds memory and the windows asked, it lists options, each with what you lose: a window per model, one model at a time, a model asked on another host, a tuned twin, a smaller quantization, or a smaller KV cache on the server. A profile change can be applied; a server-side one is only shown with the exact line. `halo ollama steward plan` prints it, and Fleet's Ollama panel shows it with Apply and Copy.

## host

A host is one server Halo sends local-model calls to: an `ollama.hosts` entry (`ol:<model>@<host>`), a Hugging Face local server (`huggingface.local_servers`: llama-server, LM Studio, mlx), or a server Find or Scan found that is not added yet. Each has a URL, a kind, the machine that serves it and what it has loaded; Studio's Local section (3.3.5.0, Alt+0) lists every one on its Hosts page with Load, Unload and Make it fit, and `halo local hosts` prints the same.

## speed card

A model's speed card is what a short benchmark of it on one host measures: its load time, its prompt and reply tokens per second at a few windows, the largest window that stays on the GPU and the reply reserve that avoids cuts. The benchmark comes in 3.3.5.0 R5 (Local -> Benchmarks, `halo local bench`); until then the model card's `speed` is empty and `halo ollama calibrate` measures the largest window alone. Once measured it sits beside the learned window in the fit store, shows on the model card and the fit meter, and reaches every machine through the fleet hub.
