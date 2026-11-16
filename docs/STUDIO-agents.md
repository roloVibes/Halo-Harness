# Studio: Agents

Read this when you work with your agents in Studio's Agents section: its three tabs (make an agent, make a workflow, connect them on the map your sessions run on), where each old view went in 3.6.0.0, and the doors the old Team, Roles, Orchestra and Runs addresses left.

Part of [Halo Studio](STUDIO.md), which lists every part.

## One section, three tabs (3.6.0.0)

Agents (`Alt+2`) is three tabs, first on its bar:

| Tab | Key | What it is | Its page |
|---|---|---|---|
| **1 · Agents** | `1` | make an agent: its name, what it does, its model, what it may use, how careful; Try it, Save; the builder box writes one for you | [STUDIO-builder.md](STUDIO-builder.md) |
| **2 · Workflows** | `2` | put your agents in steps, in order: what each step gets and hands on; Try it on a throwaway copy | [STUDIO-workflows.md](STUDIO-workflows.md) |
| **3 · Map** | `3` | connect them: who main hands work to, and when; every session runs on a map (the shipped `starter` until you pick one); while one runs the map lights up, and History under it replays what ran | [STUDIO-map.md](STUDIO-map.md) |

Agents opens on the Map while a session runs, else on the tab used last; nothing else opens on its own. For this
release `C` and `L` (the old Cast and Live keys) land on the Map and `W` on Workflows. The files live in
`~/.halo/crew/` ([CREW-FORMATS.md](CREW-FORMATS.md)); the terminal has the same three as `halo agents`, `halo
workflows` and `halo maps` ([COMMANDS-agents.md](COMMANDS-agents.md)).

**Gone in 3.6.0.0 (R5):** Cast (the lineup canvas, its tiers, Lineups, Bios, the Inspector, Problems, Models), Live
(the session tree, its plan, its levels and groups), the board of squares (Workflows' squares and their library), the
blocks library and the lineup and bio forms. What each did lives on the three tabs: an agent's form is 1 · Agents, the
steps are 2 · Workflows, who hands work to whom (and when) is the Map, what runs now is the Map lit up, what ran is
History under the Map, a goal run is the Map's Run a goal and its pages in the Map's drawer. Lineups and bios are no
longer read: Halo says so once (`halo doctor` and Studio's Attention say it too) and leaves the files where they are.

### The doors

Every old door still opens, on the tab that replaced it; each terminal answer names the new door once:

| Door | Lands on |
|---|---|
| `Alt+2`, `?mode=agents`, `halo studio --mode agents`, `/studio agents` | the Map while a session runs, else the tab used last |
| `?mode=agents&view=crew`, `workflows` or `map` | that tab (`flows`: Workflows) |
| `?mode=agents&view=cast`, `live`, `orchestra`; `?mode=roles`, `?mode=team`, `?mode=orchestra` | the Map |
| `?mode=agents&run=<id>` | that goal run: its pages in the Map's drawer while it runs or waits on you, its report in History once it ended |
| `halo studio --edit agent:<name>` / `workflow:<name>` / `map:<name>` | that tab, on that file |
| `halo studio --edit bio:<name>` / `lineup:<name>` / `team` | 1 · Agents (a bio) or the Map (a lineup, team), with the line that lineups and bios are no longer read |
| an Attention row's `o` (an Orchestra gate, a supervisor decision) | the run's pages in the Map's drawer, its report in History once it ended |

### What Team's board became

The board (members as columns, stages as boxes, blocks underneath) is gone since 3.3.16.0, the team file and `halo team`
since 3.4.0.0. Who hands work to whom is the Map now.

### Who owns what: the owns line

A goal run's lanes say what they own -- the claim ledger's keys for that lane, `basket.py#add_item` -- on their cards
in the plan review (`plan-owns`), and a lane's **Claims** page in the run's pages (the Map's drawer) lists the ledger's
rows (`lane-claims`): key, holder and state, with Release and Steal while the run is live. They are the run's ClaimLog
as `GET orchestra/<run>` carries it (`claims`); nothing new is stored.

### Workflows: the board of squares (3.3.16.0 R3)

The board of squares went in 3.6.0.0 R5; a workflow is steps of your agents now, on 2 · Workflows
([STUDIO-workflows.md](STUDIO-workflows.md)), and when main hands one work is a line on the Map. `halo workflows new
<name> --from <starter>` copies a starter.

### Hover and click (3.3.16.1)

Resting the pointer on a box of the Map (about 350 ms), or focusing it with the keyboard, shows one card of what the box
is and does (`studio.hover_cards`, Settings -> Studio, on by default); a click opens its detail.

## Cast: the lineup and its bios

Cast went in 3.6.0.0 R5 with the lineups and bios it drew. An agent is a file of yours now (1 · Agents), and the map
your sessions run on says who main hands work to (3 · Map). Your old `~/.halo/teams/` and `~/.halo/agents/` files are
still there, unread.
