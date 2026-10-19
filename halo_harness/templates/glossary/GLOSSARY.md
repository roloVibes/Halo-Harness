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
