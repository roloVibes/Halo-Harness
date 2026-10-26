# Halo Studio

Read this when you use Halo Studio, the browser console where you watch every agent work: the Session dashboard, your lineups in Roles, runs, designs, fleet and team.

`halo studio` opens your lineups and agent bios as an editable graph in the
browser. It is the visual front door to the same files the wizard and the
CLI edit: a lineup is `~/.halo/teams/<name>.yaml` (or `.halo/teams/` in a
project), a bio is `~/.halo/agents/<name>.yaml`, and Studio reads and writes
them through the exact functions `halo teams` and `halo agents` use. Nothing
is a second source of truth.

**What Studio shows is what is on disk, as it changes (3.2.2.0):** a lineup
your session edits, `halo teams apply`, a bio saved from the terminal appear
within two seconds, no refresh (the server watches the lineup, bio, config
and layout files and sends `files_changed`). A form you are editing keeps
your draft and offers **Reload** or **Keep mine**; a file deleted on disk
leaves the list. How: [The live feed](STUDIO-sections.md#the-live-feed).

```sh
halo studio                 # starts a local server, opens the browser in the mode you used last
halo studio --mode roles    # straight into Roles (lineups and bios), --mode design
halo studio --mode fleet    # 3.0.5.0: every harness and agent, live (also orchestra)
halo studio --mode team     # 3.0.8.0: the project's team on one board
halo studio --session       # 3.1.4.0: the Session dashboard on this harness's newest live session (or --session <id>)
halo studio --mode setup    # 3.3.0.0: Setup, the wizard's blocks as forms, each with its own Save (STUDIO-setup.md)
halo studio --no-open       # prints the URL only (SSH, a headless box)
halo studio --port 8765     # a fixed port instead of a free one
halo studio --stop          # stop the Studio running in the background
```

**Session** (`halo studio --session`) is where you watch and steer your own
session: its agent tree and its cost on the left, and on the right the Live
column, every agent's line in the Fleet log's columns (the time, the kind,
who) under a timeline lane per live agent, with an agent and a kind pick, and
the Steer box always at its foot, addressed to the agent you pinned or else
the session's main agent, Pause and Stop beside it (3.1.7.0). How it works:
[Session](STUDIO-sections.md#session). Since 3.3.0.0 the box names its target and the call it reaches, and **Export** saves the session as one Markdown trace: [Studio: steering and exporting a session](STUDIO-session.md). Its spend, tokens, turns and context
move on the session's own `message_end` and `status` frames, the moment the
terminal's status bar moves (3.1.8.0); the frames the tab reads and the
delays that remain, each with its number, are in
[The live feed](STUDIO-sections.md#the-live-feed).

One Studio per machine (3.0.2.0): while it serves, `~/.halo/studio.json`
holds its pid, port and token (private), and a second `halo studio` reuses
that instance (prints its URL, opens the browser) instead of starting
another. The wizard's **Open Studio (Roles)** button starts it detached, so
it outlives `halo init`; `halo studio --stop`
ends it. `halo_harness/studio/launch.py` is the small module behind both.
Since 3.2.2.0 Studio ends with the halo session that quits: a quit
(`/quit`, Ctrl+C twice, Ctrl+D, Ctrl+Q) stops the Studio in `studio.json`
too (its shutdown route, then the signal) and says so in its last line
(`stopped: Studio (pid 4242)`), unless another halo session of this home is
still open (the last one to quit ends it). `halo update` stops it before
installing; `halo studio` afterwards starts the new version.

Inside the TUI, `/roles` and `/design` open Studio straight into that
mode from the live session; bare `/studio` (3.1.4.0) opens the **Session**
section (`Alt+1`) on the session you are in, `/studio [session|roles|design|orchestra|fleet|team|packs|setup]`
opens that section, and `/studio url` prints the URL without opening a browser.
The sections' keys are `Alt+1`..`Alt+8`: Session, Team, Roles, Fleet,
Design, Orchestra, Packs, Setup. A model running in a
Halo session knows this too: the system prompt names Studio, its modes
and the command, so "open the GUI for roles" runs `halo studio --mode roles`.

This page is the entry point; the content lives in the parts below, one per task.

## The parts

| Part | Read it when | What is in it |
|---|---|---|
| [Studio: the shell](STUDIO-shell.md) | you find your way around Studio's header, sections, panels and Start views, or open it on a bio, a lineup or the Team | The shell (3.0.3.0) · Opening Studio on a bio, a lineup or the Team (`halo studio --edit`) · The guided first run (3.1.1.0) |
| [Studio: steering and exporting a session](STUDIO-session.md) | you steer an agent from Session's Live column and want to know which agent and which call it reaches, or save a session as one Markdown trace file | The steer's target · Follow, and the view holding still · Keys · Export: the session as a trace file · Files |
| [Studio: how each section works](STUDIO-sections.md) | you want the one-screen story of a section (Session, Team, Roles, Fleet, Design, Orchestra, Packs, Setup) and the live feed | How each section works · The live feed |
| [Studio: the Orchestra console](STUDIO-orchestra.md) | you run an Orchestra goal from Studio: the run console, the plan canvas and the coach | Orchestra: the run console |
| [Studio: Fleet](STUDIO-fleet.md) | you watch or steer every harness and agent from Studio's Fleet section | Fleet: every harness, every agent · How this works: Attention · How this works: Costs and caps · How this works: Conflicts and project rooms · How this works: Hand-offs · How this works: Recordings · How this works: Replay · How this works: Who can do what · How this works: Missions · How this works: While you were away · Keys: hop around · Live Roles: the lineup lights up |
| [Studio: Team and Roles](STUDIO-team-roles.md) | you edit a team board or a lineup on the Roles canvas | Team: people, blocks and stages on one board · What you see (Roles) |
| [Studio: Design mode](STUDIO-design.md) | you make prototypes, pages or decks with Studio's Design section on your own creative apps, or render pictures with the Media panels | Design mode: prototypes, pages and decks on your own apps · Media: the ComfyUI panels · Media routes (3.0.4.0) |
| [Studio: the Pack Manager](STUDIO-packs.md) | you install, grant, enable, set up, update or remove packs from Studio's Packs section | Packs: the Pack Manager (3.2.0.0 R6) |
| [Studio: the Setup section](STUDIO-setup.md) | you set this box up from Studio's Setup section: what each block writes and the routes behind it | Setup: the wizard's blocks as forms (3.3.0.0) · What each block writes · The routes |
| [Studio: saving, security, SSH and shortcuts](STUDIO-security.md) | you save and apply from Studio, run it over SSH, check what it lets a page do, or want every shortcut | Validate, save, apply · Security model · Over SSH · Shortcuts · Files |
