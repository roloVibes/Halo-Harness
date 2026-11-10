# Studio: blocks and groups

Read this when you compose the lineup on Agents -> Cast as blocks (a tier with its purpose, a workflow square with the agents inside it) or watch Agents -> Live box the sub-agents of one task.

Part of [Halo Studio](STUDIO.md), which lists every part; the Agents section itself is [Studio: Agents](STUDIO-agents.md).

## Blocks: the tiers and the squares on one board (3.3.16.3)

The owner, 2026-11-10: "different blocks that you can almost like drag and drop in the agents tab ... here is the media
workflow ... here's my thinking block". On **Cast** a **block** is a titled box with a purpose, the agents inside it and
how main reaches it, and two things are drawn as blocks with one look: a lineup **tier** (its box, its cards inside, its
`purpose` line under the name: "the one you talk to", "the workers, picked per task" on the auto lineup) and an enabled
workflow **square**, in a column right of the tiers. Main is the one card in no block; its line runs into each square
block's title bar, under the tiers so it crosses no card. A square block's title bar is its name and its purpose (its
DOES line) with the chevron and its `x` (off for this lineup; the file stays); open, one small card per bio of its
lineup -- the lead first, its model's short name (`auto: picked per task` for an `auto` one) and what the model takes;
folded, the 3.3.16.0 card's TAKES / GIVES / COSTS lines; its footer is its limits and its cost band. The chevron's state
is kept per lineup in this browser. The YAML model stays: a square is a workflow file, a tier a lineup tier.

A click on a square block opens its summary in the inspector -- purpose, who is inside, costs, limits, where its file is
-- then one Edit row per page: **Purpose** (the DOES line, saved into a square of yours; a shipped or a pack's square says
how to copy it first), **Agents** (the lead and its members, each on its model), Enable, Budget, Limits, YAML. A click
on a card or on the canvas clears it. A tier's purpose line opens the tier's Purpose form (its `...` menu has it too).
The Workflows view (`W`) is still the squares alone with the library open; every door, key and test id keeps working.

## Live in groups (3.3.16.3)

The owner: "I just see one top level box and then a bunch of tiny sub-agent boxes, and I wish I could see better
groupings of these sub-agents". On **Live** (and Session's Map, the same tree) agents are boxed by what they were started
for, and the parent's line goes to the box, not to each agent:

- **a task** -- the sub-agents one step of a parent started together (the Agent calls of one reply; an agent row's
  `spawn.step`), two or more: the box is titled by the task in a few words, from what the events hold and never a model
  call -- the one description they share, else the parent's own line just before the calls (its first clause), else
  the words their descriptions start with, else the first description "and N more";
- **a square** -- a square's agent and every agent under it: titled `square <name>`, its DOES line under it, the
  engine's lane colour on its edge;
- **a tier** -- an agent of an explicit lineup tier in no box above: the tier's faint group, titled by its purpose (a
  lineup with no tiers keeps the faint group of the card its agents match);
- an agent started alone is not boxed.

A box's title bar is the task, then one line of counts (N agents, how many working / waiting / done, its cost, how long
it has run), then -- when Auto picked the models -- the pick in plain words ("3 readers on kimi-k3 for a pdf in the
task", from the picks' recorded reasons) or a square's DOES line. Its agents sit in a grid inside it (four to a row at
the spread density, five at compact), so ten sub-agents are a tidy block. The chevron (or Enter on the bar) folds it to
the bar, which keeps the strongest state's colour and turns amber while one of its agents waits on you. Boxes nest one
level (a square's box inside a task's); deeper, the agents are a tree inside the outer box. The bar's hover card says
what the group is for, who is in it, how it stands and who started it. Session's timeline has a **by group** toggle:
a title row over each group's lanes.
