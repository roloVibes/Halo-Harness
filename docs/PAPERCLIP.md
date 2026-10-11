# Paperclip: your lineups as a company of agents

Halo 2.2.0 hands organizations to [Paperclip](https://github.com/paperclipai/paperclip),
the open-source control plane for a company of agents: an org chart with
titles and reporting lines, goals, projects, issues, heartbeats, budgets and
an audit trail, all in one local server with its own UI. Halo brings the
agents: every assignment in a lineup becomes a Paperclip agent that runs
`halo paperclip-run` on a heartbeat, on the model its bio names, and reports
back on the issue it worked.

Three surfaces, one source of truth (Paperclip's database):

- **Studio's Org mode** (`halo studio`, the Roles | Org toggle, `O`): the
  org chart on the canvas, agents editable, issues, the embedded Paperclip
  pages. See [STUDIO.md](STUDIO.md).
- **`halo paperclip`** on the command line (below).
- **Paperclip's own UI** at `http://127.0.0.1:3100` for everything else it
  does (goals, approvals, costs, routines, connections).

## Install

Paperclip needs Node.js 24 or newer. Then either:

```sh
halo paperclip install          # runs: npx paperclipai@latest onboard --yes
```

or Studio's Org mode, which offers the same install with its log in the
page when Paperclip is absent. Onboarding creates `~/.paperclip/` with an
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
