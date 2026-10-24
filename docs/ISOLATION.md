# Isolation

Read this when a lineup's workers should run in a container or as another OS user, get their keys from a secret broker, or see only some of the tools.

Halo 3.1.8.0 R5. Nothing changes by default. A lineup or a bio may declare
three opt-ins; each is a rule you set, shown as a `halo doctor` row and as
one line in the run report when it is on:

| Opt-in | Where | What it does |
|---|---|---|
| `isolation: container \| user` | a lineup (every worker) or a bio (its workers; the bio wins) | the Orchestra worker runs inside a per-run container or as a scoped OS user, the same worktree inside |
| `secrets: {broker: 1password \| env}` | a lineup or a bio (the bio wins); the refs in a bio's `environment.secrets` | each ref is read at spawn into the worker's environment only |
| `tools.capabilities` | a lineup (whole, per tier, per member card) or a bio | the agent is built with only the tools of those capabilities |

`isolation` and `secrets` apply where Halo starts a worker process: an
Orchestra lane (`halo orchestra run`, Studio, the supervisor's goals, a team
stage of kind `orchestra`, a workflow), all through
`orchestra/adapters.py` `spawn_worker`. An in-process sub-agent shares its
parent's process, so neither applies to it; `tools.capabilities` applies
wherever an agent is built (the top session, a lineup member, a worker).

A worker that cannot run as declared stops with one line ([Stop
lines](#stop-lines)), like a worker whose harness would not start: the lane
fails with it, the run stops with `lane <n>: <line>` (`failure.kind: worker`).

Not the same key: the older `isolation: worktree` of a `.claude/agents/*.md`
file ([SUBAGENTS.md](SUBAGENTS.md)) is for in-process sub-agents.

## `isolation: container`

```yaml
isolation: container                 # alone: the defaults below
isolation:
  mode: container
  image: halo-harness-worker:<version>   # the default
  network: host                      # host (the default) or none
  mounts: ["<host path>:<container path>[:ro]"]
  env: [GITHUB_TOKEN]                # host env names the worker may see
```

The worker's `halo -p` argv becomes (`isolation/container.py` `wrap`):

```sh
docker run --rm --network host \
  -v <run>/wt/worker-<n>:/work -w /work -v <run>:/run -v <run>/state-<n>:/root/.halo \
  [-v <repo>/.git:<repo>/.git]       # a POSIX host: git works in /work
  [-v <each mount>] \
  -e HALO_ORCHESTRA_RUN=/run -e HALO_ORCHESTRA_LANE=<n> -e PYTHONIOENCODING=utf-8 \
  -e GITHUB_TOKEN [-e <each broker key>] [-e HALO_TOOLS_CAPS ...] \
  <image> halo -p "<the lane's prompt>" --output-format json --permission-mode auto [--agent <bio>] [--model <ref>]
```

`podman` runs it when there is no docker. `-e <NAME>` carries a name only:
docker takes the value from its own environment, so no value is ever in an
argv. The container sees only those names: the isolation's `env`, the
broker's keys and the run's own variables.

The host's `~/.halo` is never mounted. The worker gets a scoped state dir,
`<run>/state-<n>/` (`isolation/seed.py`), seeded with the host config's
model keys (`model`, `team`, `effort`, `roles`, `routing`, `models` and the
provider sections, with every key-shaped field such as `token`, `api_key`
or `headers` dropped at any depth), `routes.json` the same way, the model
catalogs, and the run's lineup and every bio it assigns, resolved. A
credential reaches the worker only through a name in `env` or a broker ref.

`network: host` is the default because every worker calls its model
provider; `network: none` (no network at all) fits a worker that talks only
to a model inside the image. The claims and the lane file are written
through the `/run` mount, which on a Linux host is the same file system;
Docker Desktop (Windows, macOS) runs containers in a VM, where file locks
across the mount are not guaranteed.

### The image

`halo isolation image` prints the default image name
(`halo-harness-worker:<version>`) and the Dockerfile Halo ships
(`halo_harness/isolation/Dockerfile`: `python:3.12-slim`, git and ripgrep,
then `pip install "git+https://github.com/roloVibes/Halo-Harness.git@v<version>"`).
`halo isolation build [--image NAME] [--dry-run]` builds it at this harness's
version; `halo isolation check` prints the two doctor rows and what your
lineups and bios declare ([COMMANDS-supervise.md](COMMANDS-supervise.md#halo-isolation)).

## `isolation: user`

```yaml
isolation: {mode: user, user: halo-worker, group: halo, env: [GITHUB_TOKEN]}
```

On a POSIX host the worker runs as that user:

```sh
sudo -n -u halo-worker --preserve-env=BRIDGE_STATE_DIR,GITHUB_TOKEN,HALO_ORCHESTRA_LANE,HALO_ORCHESTRA_RUN,PYTHONIOENCODING -- \
  <python> -m halo_harness -p "<prompt>" --output-format json --permission-mode auto ...
```

`--preserve-env` carries names only. Before the worker starts, the lane's
worktree and the run folder (without the other lanes' worktrees) are made
group-writable for that user (`isolation/scoped_user.py` `share`: the group
is `group:` or the user's primary group, set on every file and folder;
folders get setgid so new files keep the group). Its state dir is the
seeded `<run>/state-<n>/` (`BRIDGE_STATE_DIR`). Four things are yours to
set up once: the user; a group you are both in; the folders above the run
folder (the repo, `.halo/orchestra/`) and the harness's python letting that
user through (read and execute for the group or others); and a sudoers line
that lets you run that python as the user with no password and with its
environment, e.g. `you ALL=(halo-worker) NOPASSWD:SETENV: /path/to/halo/python`.
Windows has no scoped user in this round: the lane stops with
"isolation: user is not available on Windows; use container".

## `secrets: broker`

```yaml
secrets: {broker: 1password, account: my-team}   # on the lineup or the bio
environment:                                      # the bio's
  secrets:
    - {env: OPENROUTER_API_KEY, ref: "op://Engineering/OpenRouter/credential"}
    - {env: GITHUB_TOKEN, ref: "op://Engineering/GitHub/token"}
  pass_to_tools: [GITHUB_TOKEN]
```

At spawn, `isolation/secrets.py` reads each ref with the broker:
`1password` runs `op read <ref>` (the 1Password CLI on PATH; `account`
becomes `--account <account>`); `env` reads `ENV:<KEY>` from the
environment Halo started in (for tests and for people without a broker; it
is not a secret store). The values go into the worker's environment only:
never a file, never a transcript, never a frame. The lane file and the
report keep the broker and a count. The worker's environment also names
the keys (`HALO_SECRET_KEYS`), so its own `tool_child_env` strips them from
every tool child (Bash, PowerShell, MCP, hooks) unless
`environment.pass_to_tools` names them (`HALO_SECRET_PASS`); the harness's
own provider keys (`OPENROUTER_API_KEY` and the rest of
`_HARNESS_SECRET_ENV_KEYS`) never reach a tool child either way. What the
runner keeps of the worker (its reply and error tails) has every value
replaced by `<redacted>`. A ref that cannot be read is one line naming the
ref, and the lane stops. With `isolation`, whether the isolation can run is
checked first, so no secret is read for a lane that would not start.

`halo secrets check [--lineup L | --bio B]` checks the broker on PATH and
reads each ref, printing names and `ok` only. A second broker is one file, `halo_harness/isolation/brokers/<name>.py`,
with `NAME`, `CLI`, `present(which)` and `read(ref, *, account, runner,
which, environ) -> str` that raises `BrokerError` with one line, plus its
row in `brokers.MODULES` (`1password` lives in `onepassword.py`: a module
name cannot start with a digit).

## `tools.capabilities`

```yaml
tools: {capabilities: [read, edit, bash]}          # a lineup (every member) or a bio
tiers:
  - {name: checkers, members: [reviewer], tools: {capabilities: [read]}}
agents:
  - {agent: coder, role: coder, tools: {capabilities: [read, edit, bash, web]}}
```

The list names capabilities; `isolation/capabilities.py` maps every tool
name in the registry to one (`TABLE`):

| Capability | Tools |
|---|---|
| `read` | Read, Glob, Grep |
| `edit` | Edit, Write, NotebookEdit, OrchestraClaim, OrchestraClaims, OrchestraRelease, OrchestraNote |
| `bash` | Bash, BashOutput, PowerShell, TaskStop |
| `web` | WebFetch, WebSearch |
| `agent` | Agent, Task, TaskCreate, TaskList, TaskUpdate |
| `mcp:<server>` | every `mcp__<server>__*` tool and the claude.ai connector `connector__<server>`; `mcp` alone is every server; any `mcp` entry keeps ToolSearch, ListMcpResourcesTool and ReadMcpResourceTool |
| `media` | Media |
| `recall` | Skill, TodoWrite, knowledge_add, knowledge_search |
| `other` | any name outside the table (AskUserQuestion, EnterPlanMode, ExitPlanMode, SendUserMessage) |

An agent whose lineup or bio declares the list is built with only those
tools: the registry is narrowed before the model sees the tool list (the
top session in `headless.build_session`, a lineup member in
`agent/subagent.py`, the session catalog's deferred MCP pool too). Which
list wins, nearest first: the member's card, its tier, its bio, the
lineup's own. No list anywhere: every tool, as before. The list only ever
narrows: the bio's or the agent file's `tools`/`disallowedTools`,
`--disallowedTools`, deny rules and the permission mode still apply to what
is left. An Orchestra worker takes its list from its run (the lane's
lineup and bio, `HALO_TOOLS_CAPS`), never from the main of the lineup it
happens to load.

The Agent tool's description says what the members may use ("Under lineup
ci each member sees only the tools of its capabilities: coder: read, edit,
bash; reviewer: read."); `/tools` lists the session's tools by capability
and what narrowed them ("tools: read, edit, bash (by lineup ci)" or
"(by bio reviewer)"); Studio's Agent panel shows the same line.

## Where it shows

| Where | What |
|---|---|
| `halo doctor` | `isolation`: the modes this host can run (docker or podman on PATH; sudo on a POSIX host, and `sudo -n` as each user a lineup or bio names) and who declares one; `secrets`: the broker found or not. A declared mode or broker this host lacks is a `[WARN]` line |
| `lanes/<n>.json` | `isolation: {mode, image \| user, by}`, `secrets: {broker, refs, by}`, `tools: {capabilities, by}`, `opt_ins` (the lines) -- only when the lane declares one |
| the run report | `opt_ins: [{lane, lines}]`, printed as `lane <n>: <line>` |
| `halo goal show` | the same lines under the run |
| Studio | the Orchestra run view (each lane's lines under its title), the Agent panel (the agent row's `opt_ins`), the Roles Inspector's Lineup tab (Isolation, Secrets broker, Tool capabilities: plain field rows) |

The lines: `isolation: container (<image>)` or `isolation: user (<name>)`,
`secrets: 1password (2 refs)`, `tools: read, edit, bash (by bio coder)`.

## Stop lines

| Line | When |
|---|---|
| `isolation: container asked, no docker or podman on this host` | neither is on PATH |
| `isolation: user is not available on Windows; use container` | `mode: user` on Windows |
| `isolation: user asked, no sudo on this host` | no sudo on PATH |
| `isolation: user '<name>' does not exist on this host` / `isolation: user: no group '<g>' on this host` | the user or the group is unknown |
| ``secrets: 1password asked, no `op` on PATH`` | the broker's CLI is missing |
| `secrets: could not read <ref> (op exited <code>)` | `op read` failed for that ref |
| `secrets: ENV:<KEY> is not set in this environment` | the `env` broker's key is unset |
| `secrets: <n> ref(s) in environment.secrets, no secrets.broker set` | refs without a broker |

## A worked example

```yaml
# ~/.halo/teams/ci.yaml
name: ci
agents:
  - {agent: boss, role: main}
  - {agent: coder, role: subagent}
  - {agent: reviewer, role: reviewer, tools: {capabilities: [read]}}
isolation: {mode: container, env: [GITHUB_TOKEN]}    # the host network: the default
secrets: {broker: 1password, account: my-team}
tools: {capabilities: [read, edit, bash, agent]}
```

```yaml
# ~/.halo/agents/coder.yaml
name: coder
models: {preference: or:vendor/coder-model}
environment:
  secrets: [{env: OPENROUTER_API_KEY, ref: "op://Engineering/OpenRouter/credential"}]
```

`halo orchestra new` with `"lineup": "ci"` in the goal, then `halo orchestra
run`: lane 2's worker (the goal's `subagent` role, so bio `coder`) runs as

```sh
docker run --rm --network host -v <run>/wt/worker-2:/work -w /work -v <run>:/run \
  -v <run>/state-2:/root/.halo -e HALO_ORCHESTRA_RUN=/run -e HALO_ORCHESTRA_LANE=2 -e PYTHONIOENCODING=utf-8 \
  -e GITHUB_TOKEN -e HALO_OPT_INS -e HALO_SECRET_KEYS -e HALO_TOOLS_CAPS -e HALO_TOOLS_CAPS_BY -e OPENROUTER_API_KEY \
  halo-harness-worker:<version> halo -p "<prompt>" --output-format json --permission-mode auto
```

with `OPENROUTER_API_KEY` read by `op read` a moment before, and the report
says `lane 2: isolation: container (halo-harness-worker:<version>)`,
`lane 2: secrets: 1password (1 ref)`, `lane 2: tools: read, edit, bash,
agent (by lineup ci)`.
