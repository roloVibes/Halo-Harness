# Halo Studio

Read this when you use Halo Studio, the browser view of your lineups, runs, designs, fleet and team.

`halo studio` opens your lineups and agent bios as an editable graph in the
browser. It is the visual front door to the same files the wizard and the
CLI edit: a lineup is `~/.halo/teams/<name>.yaml` (or `.halo/teams/` in a
project), a bio is `~/.halo/agents/<name>.yaml`, and Studio reads and writes
them through the exact functions `halo teams` and `halo agents` use. Nothing
is a second source of truth.

```sh
halo studio                 # starts a local server, opens the browser in the mode you used last
halo studio --mode roles    # straight into Roles (lineups and bios), --mode design
halo studio --mode fleet    # 3.0.5.0: every harness and agent, live (also orchestra)
halo studio --mode team     # 3.0.8.0: the project's team on one board
halo studio --no-open       # prints the URL only (SSH, a headless box)
halo studio --port 8765     # a fixed port instead of a free one
halo studio --stop          # stop the Studio running in the background
```

One Studio per machine (3.0.2.0): while it serves, `~/.halo/studio.json`
holds its pid, port and token (private), and a second `halo studio` reuses
that instance (prints its URL, opens the browser) instead of starting
another. The wizard's **Open Studio (Roles)** button starts it detached, so
it outlives `halo init`; `halo studio --stop`
ends it. `halo_harness/studio/launch.py` is the small module behind both.

Inside the TUI, `/roles` and `/design` open Studio straight into that
mode from the live session; `/studio [roles|design|orchestra|fleet|team]` is the long form and
`/studio url` prints the URL without opening a browser. A model running in a
Halo session knows this too: the system prompt names Studio, its modes
and the command, so "open the GUI for roles" runs `halo studio --mode roles`.

This page is the entry point; the content lives in the parts below, one per task.

## The parts

| Part | Read it when | What is in it |
|---|---|---|
| [Studio: the shell](STUDIO-shell.md) | you find your way around Studio's header, sections, panels and Start views, or open it on a bio, a lineup or the Team | The shell (3.0.3.0) · Opening Studio on a bio, a lineup or the Team (`halo studio --edit`) · The first ten minutes (3.1.1.0) |
| [Studio: how each section works](STUDIO-sections.md) | you want the one-screen story of a section (Orchestra, Roles, Design, Fleet, Team) and the live feed | How each section works · The live feed |
| [Studio: the Orchestra console](STUDIO-orchestra.md) | you run an Orchestra goal from Studio: the run console, the plan canvas and the coach | Orchestra: the run console |
| [Studio: Fleet](STUDIO-fleet.md) | you watch or steer every harness and agent from Studio's Fleet section | Fleet: every harness, every agent · How this works: Attention · How this works: Costs and caps · How this works: Conflicts and project rooms · How this works: Hand-offs · How this works: Recordings · How this works: Replay · How this works: Who can do what · How this works: Missions · How this works: While you were away · Keys: hop around · Live Roles: the lineup lights up |
| [Studio: Team and Roles](STUDIO-team-roles.md) | you edit a team board or a lineup on the Roles canvas | Team: people, blocks and stages on one board · What you see (Roles) |
| [Studio: Design mode](STUDIO-design.md) | you make prototypes, pages or decks with Studio's Design section on your own creative apps, or render pictures with the Media panels | Design mode: prototypes, pages and decks on your own apps · Media: the ComfyUI panels · Media routes (3.0.4.0) |
| [Studio: saving, security, SSH and shortcuts](STUDIO-security.md) | you save and apply from Studio, run it over SSH, check what it lets a page do, or want every shortcut | Validate, save, apply · Security model · Over SSH · Shortcuts · Files |
