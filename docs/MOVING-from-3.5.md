# Moving from 3.5 (Halo 3.6.0.0)

Read this when you used lineups, bios, squares, blocks or the old Agents canvas on Halo 3.5 and want to know what is gone, what to use instead, and what happens to your old files.

## Updating: From 3.5.0.1, once

On Windows, do not run `halo update` in a shell to leave 3.5.0.1: its updater runs the reinstall from inside the
running halo, which holds the files it replaces, and can leave the install half replaced. Type `/update` in a session
instead (it installs after that halo has exited), or close every Halo window, run `halo studio --stop`, and run the
repair line (the Windows installer does the same, and stops while a halo still runs):

```powershell
uv tool install --reinstall --constraints https://raw.githubusercontent.com/roloVibes/Halo-Harness/v3.6.0.0/requirements.lock "git+https://github.com/roloVibes/Halo-Harness@v3.6.0.0"
```

On every platform, if you turned on `halo host install`, run `halo host stop` before the update: 3.5.0.1's updater
does not see the LAN host. From 3.6.0.0 on, `halo update` sees and stops it itself.

## What you see first

Nothing changes in a session you start the way you always did. A session that names no map runs exactly as a 3.5
session with no lineup set: the same tools, the same sub-agents and model picks, the same depth, no money cap, nothing
added to the prompt ([CREW-sessions.md](CREW-sessions.md#which-map)). Studio's Map tab draws it on the shipped
`starter` map.

If your `~/.halo` holds lineups, bios or squares you wrote (Halo's own shipped copies do not count), Halo says ONE line,
once, in the terminal and in Studio's Attention: they are no longer read, and where the new files live. A configured
`team:` is named in the same line. Halo never deletes, moves or converts a file of yours.

## What is gone, and what to use

| On 3.5 | On 3.6 |
|---|---|
| a lineup (`~/.halo/teams/*.yaml`, `halo teams`, `--team`, config `team:`) | a map (`~/.halo/crew/maps/*.yaml`): `halo maps use <name>`, `--map <name>`, Studio's Agents -> 3 · Map |
| a bio (`~/.halo/agents/*.yaml`, `halo agents` on bios) | an agent (`~/.halo/crew/agents/*.yaml`): `halo agents new / edit / try`, Agents -> 1 · Agents |
| a square / block (`halo workflow`, `halo blocks`, the board) | a workflow (`~/.halo/crew/workflows/*.yaml`): `halo workflows new <name> --from <starter>`, Agents -> 2 · Workflows |
| `halo teams`, `halo roles`, `halo blocks`, `halo workflow`, `/teams`, `/roles` | each prints one line saying where to go, and exits 0 |
| the Cast canvas, Live, the Board, the Lineups / Bios / Inspector / Problems / Models panels | the three tabs: 1 · Agents, 2 · Workflows, 3 · Map (the Map lights up while a session runs) |
| Live's node menu: Take over, Pin its stream, Record | Take over: a button in the Map's drawer beside Pause; Pin: the drawer's filter by box; Record: the scrubber's "Save this run's replay" |
| a lineup's schedules and triggers, tiers, pipeline gates, escalation, shared memory, isolation and secrets | not carried: a map has lines and a money cap (`caps.session_usd`); the run engine keeps its own worktrees |
| `halo doctor --teams` | `halo doctor --agents` checks your agent files and the map in use |
| `halo local warm <lineup>`, `halo local place <lineup>` | the same verbs take a map (the one in use when none is named) |
| a goal's lineup (`halo supervise`, Orchestra) | the goal's map: its job's session runs `--map <name>`; a lineup's acceptance test is no longer taken |
| `halo roles point <role> <model>`, `/role`, `roles.*` | kept: the model table; on a session with no map it reaches the agent of that name |
| the squares a lineup enabled (`workflows:` in a lineup), `halo workflows enable / disable / when` | config `workflows.enabled` and `workflows.when.<square>` (`halo config set`, Studio's Settings); the `Workflow` tool reads only these |
| a `roles` table in config.json turned into the lineup `migrated` at session start | nothing is migrated: `roles.*` is the model table a session reads as it is |
| `halo config where`'s Active lineup, Lineup folders and Bio folders rows; `halo doctor --config`'s lineup and bio checks | gone with the files they listed (the old-files line still names your old files); `halo config where` lists the agent, workflow and map folders in their place |
| the block templates (`halo blocks add`, Studio's "Blocks you can start from") | the workflow starters: `halo workflows new <name> --from <starter>` |

Old addresses still land somewhere sensible: `?view=cast|live|roles|team|orchestra` open the Map, `?view=workflows`
the Workflows tab, `--edit bio:<n>` / `lineup:<n>` the Agents tab with the old files' line.

## Your old files

Old files are not read and not converted. To keep one, make the new file and copy what you need: a bio's
`context.system_prompt` is an agent's `instructions`, its `models.preference` the agent's `model`, its `tools.allow`
the agent's `uses`. Or ask the builder in Studio ("make an agent like this: ...", pasting the text). The formats are in
[CREW-FORMATS.md](CREW-FORMATS.md).

## Packs

Extension API 2.0: a pack ships `crew/agents`, `crew/workflows` and `crew/maps`. A pack written for 1.x still runs: its
bios are read as agents, its lineups as maps and its plain workflows as workflows, each named `<pack>--<name>`, and
`halo pack list` and `halo pack doctor` say in one line what is not carried. See
[EXTENSION_API.md](EXTENSION_API.md#a-packs-crew-agents-workflows-and-maps).

## Other machines

A session running on another of your machines is listed (on the Map's picker and in History) and opened on that
machine; Studio here does not light it.

## Not yet moved (3.6.0.0)

Two shipped packs still read 3.5 files: the **first-run** pack (`halo start`) rehearses a lineup of yours, and the
**coach** pack's Apply writes bio and lineup fields. They keep the lineup and bio readers they need until they are
re-made on agents and maps. A session never reads those files.
