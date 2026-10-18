# Paperclip: your lineups as a company of agents

Read this when you run your lineups as a company of agents in Paperclip.

Halo 2.2.0 hands organizations to [Paperclip](https://github.com/paperclipai/paperclip),
the open-source control plane for a company of agents: an org chart with
titles and reporting lines, goals, projects, issues, heartbeats, budgets and
an audit trail, all in one local server with its own UI. Halo brings the
agents: every assignment in a lineup becomes a Paperclip agent that runs
`halo paperclip-run` on a heartbeat, on the model its bio names, and reports
back on the issue it worked.

Three surfaces, one source of truth (Paperclip's database):

- **Studio's Org section** (`halo studio --mode org`, `Alt+3`; React since
  3.0.7.0): the org chart in its team boxes, agents editable, issues, goals
  and projects live, a link to each one's Paperclip page. See [STUDIO.md](STUDIO.md).
- **`halo paperclip`** on the command line (below).
- **Paperclip's own UI** at `http://127.0.0.1:3100` for everything else it
  does (goals, approvals, costs, routines, connections).

## Org mode is off by default: who orchestrates what

Two different things can orchestrate models on a machine running Halo:

- **Your session.** The model you picked, and with a lineup, one agent per
  role that the session spawns and waits for. It runs when you type and
  stops when the turn ends. Studio's **Roles** mode edits exactly this.
- **Paperclip.** A separate control plane with its own server, scheduler and
  database. It wakes agents on heartbeats and issues, and every wake is a
  fresh `halo paperclip-run` process, whether or not a Halo session is
  open. Studio's **Org** mode is a window onto it.

`paperclip.enabled` in `~/.halo/config.json` is the switch, **off** on a
fresh install. While it is off, `halo paperclip-run` answers every heartbeat
with an idle exit (so a synced company cannot run anything behind your
back), Studio's Org chart says Org mode is off with a "Turn it on" button, and `halo paperclip status` starts with `Org mode: off`. Turning
it on resumes the linked company's Halo agents; turning it off pauses them
(best effort: the switch holds even when Paperclip is not running).

Four doors flip the same key: `halo paperclip on|off`, `/org on|off` in the
TUI, the wizard's Organizations step (`halo init --step orgs`), and the
**Org mode** switch in Studio's Company panel.

## Install

Paperclip needs Node.js 24 or newer. Then either:

```sh
halo paperclip install          # runs: npx paperclipai@latest onboard --yes
```

or Studio's Org section, whose Start view offers the same install with its
log in the page when Paperclip is absent. Onboarding creates `~/.paperclip/` with an
embedded PostgreSQL (port 54329), starts the server on `127.0.0.1:3100`
(loopback only, no login needed in this `local_trusted` mode) and keeps it
in the foreground; `npx paperclipai service install` registers it as a
service that starts at login. Never run it as administrator: the embedded
database refuses. `halo paperclip status` shows health, version and the
companies; `halo doctor` carries the same line.

## Sync a lineup into a company

```sh
halo paperclip sync halo-dev-cycle --new "Halo"      # a new company from the lineup
halo paperclip sync halo-dev-cycle --company Halo    # update an existing one
halo paperclip org --company Halo                     # the org chart as text
```

Sync creates (or updates, never duplicates) one Paperclip agent per
assignment: the alias or role as its name, the bio's description as its
title, Paperclip's role from Halo's (`main` -> `ceo`, `subagent` ->
`engineer`, `reviewer`/`judge` -> `qa`, `researcher` -> `researcher`,
otherwise `general`), the bio's `limits.max_budget_usd` as the monthly
budget, and the adapter `process` with command `halo paperclip-run` in the
project directory (`--cwd`). Reporting lines come from the lineup's
`org.positions` (`reports_to`) when it has them; otherwise every member
reports to `main`. The agents carry `halo_lineup`, `halo_slot`, `halo_agent`
and `halo_role` in their metadata, which is how a second sync finds them.

`halo paperclip pull <lineup>` goes the other way: the company's reporting
lines are written into the lineup's `org.positions`, so the YAML and the
chart agree after you re-parent agents in Studio or in Paperclip.
The file is written where the lineup came from: a project lineup stays a project
file, a user lineup a user file, and a bundled template such as `halo-dev-cycle`
gets your own copy in `~/.halo/teams/` (the command prints the path and says so).
`--project` writes to the project scope instead.

## How a heartbeat runs Halo

Paperclip wakes an agent when it is assigned an issue, mentioned, or on its
schedule, and spawns the adapter command with the run's environment
(`PAPERCLIP_API_URL`, `PAPERCLIP_API_KEY` -- a run-scoped key --,
`PAPERCLIP_AGENT_ID`, `PAPERCLIP_COMPANY_ID`, `PAPERCLIP_RUN_ID` and scratch
directories). `halo paperclip-run` then:

1. reads its agent (`/api/agents/me`) and the lineup/bio names in its
   metadata;
2. picks the issue Paperclip checked out for this run, else the oldest
   open issue assigned to it, and checks it out (every write carries the
   run id in `X-Paperclip-Run-Id`, which Paperclip requires); no issue means
   an idle heartbeat: nothing posted, exit 0;
3. builds the prompt from the heartbeat context (identifier, title,
   description, goal, project, parents, the comment that woke it) and runs
   `halo -p` in the project directory on the bio's preferred model;
4. posts the reply as a comment and marks the issue done, or posts the
   failure and exits 1 so the run is recorded as failed.

The key stays in this process; the child session never sees it. A model
that needs a one-time acceptance on the machine (the `cc:`/`cx:`
subscription routes) fails the first run with that message in the comment:
run `halo subscriptions accept` once and wake the agent again.

## CLI

```
halo paperclip status                     health, version, companies, the linked one
halo paperclip install                    npx paperclipai onboard --yes (Node 24+)
halo paperclip open                       the Paperclip UI in the browser
halo paperclip link [--url U] [--token T] [--company ID|NAME]
halo paperclip sync <lineup> [--company ID|NAME | --new NAME] [--cwd DIR]
halo paperclip pull <lineup> [--company ID|NAME] [--project]
halo paperclip org [--company ID|NAME]
halo paperclip-run                        the adapter entrypoint (Paperclip runs it)
```

`~/.halo/paperclip.json` (owner-only) holds the base URL, an optional board
token (needed only outside loopback mode: `npx paperclipai token board
create`) and the default company id. Nothing else is written outside
`~/.halo`; Paperclip's own data lives under `~/.paperclip/`.

## Halo's built-in orgs

Halo's own organizations (`~/.halo/orgs/*.json`, `/org`, `halo org`, the
wizard's Orgs step) keep working for existing configs, but they are no
longer the default path: the wizard's Orgs step points here, and new org
work happens in Paperclip. [ORGS.md](ORGS.md) keeps the reference under
"Legacy".
