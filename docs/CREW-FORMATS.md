# Crew files: agents, workflows and maps (3.6.0.0)

Read this when you write or read an agent, a workflow or a map file by hand, want to know where Halo keeps them, or want to know what an agent file becomes when a session spawns it.

Since 3.6.0.0 R1, Studio's Agents tab makes agents in a new format, one YAML file per thing, each with a `format:` line
so a later change can be told apart. Workflows and maps use the same folders; workflows have their tab since R2
([2 · Workflows](STUDIO-workflows.md)), maps get theirs next (the Map). The older lineups, bios and workflow squares are separate files: nothing here
reads or converts them.

## Where they live

| Folder | What | Who changes it |
|---|---|---|
| `~/.halo/crew/agents/`, `workflows/`, `maps/` | yours | the Agents tab, the builder, you |
| `<repo>/.halo/crew/...` | this project's, read only in a trusted folder | you (Studio saves a project agent where it was) |
| `halo_harness/templates/crew/...` | the starters Halo ships: 10 agents, 5 workflows, 2 maps | read-only; Copy in Studio makes yours |

A name is lowercase letters, digits and dashes, starting with a letter, at most 48 characters; the file is
`<name>.yaml`. When two scopes hold the same name, the project's is nearest, then yours, then the starter.

## An agent: `format: agent/1`

```yaml
format: agent/1
name: security-reviewer
does: Reviews pull requests for security problems and says only what would break.
instructions: |
  Read the pull request's diff and the files it touches.
  If nothing would break, answer exactly: "No security problems found."
model: auto                  # a model from your catalog, or auto (Halo picks one per task)
needs: [pdf]                 # with auto only: images | audio | video | pdf | reasoning | long-text
uses: [read, mcp:github]     # read | edit | bash | web | skill:<name> | mcp:<server>
careful: ask-changes         # ask-changes | ask-commands | own
more: {max_usd: 1.0, max_turns: 30, reads: [SECURITY.md]}
```

| Field | Means |
|---|---|
| `does` | one line in your words; the list and the Agent tool show it |
| `instructions` | what the agent is told; empty: "You are <name>. <does>" |
| `model` | a catalog ref, or `auto` |
| `uses` | read: Read, Glob, Grep · edit: Edit, Write, NotebookEdit · bash: Bash, PowerShell, BashOutput, TaskStop · web: WebFetch, WebSearch · `skill:<n>`: that skill · `mcp:<server>`: that server's tools |
| `careful` | `ask-changes`: every edit and every command waits for your OK (the `default` mode) · `ask-commands`: edits go ahead, a command waits (`acceptEdits`) · `own`: nothing waits (`auto`; your deny and ask rules still hold) |
| `more` | `fallback` (a model), `effort`, `thinking`, `max_turns`, `max_minutes`, `max_usd`, `reads` (files it always reads), `worktree` (its own copy of the repo), `offline` (no web tools), `check` (`{ask, expect}`) |

Hooks, schedules, triggers, isolation, secrets brokers, per-tool rules and `extends` are not in this format.

**What a session does with it.** Your agents (and a trusted project's) are agent definitions the session's **Agent**
tool can spawn by name, next to the built-ins and `~/.claude/agents` (crew/spec.py, `config/agents_md.discover_agents`:
above `~/.claude/agents`, below a project's `.claude/agents`). A file with a problem is left out. Maps decide who
hands work to whom from 3.6.0.0 R3; until then main picks an agent by its `does` line.

## A workflow: `format: workflow/1`

```yaml
format: workflow/1
name: ship-a-fix
for: Make the change the task asks for, test it, have it checked for security problems.
steps:
  - name: Make the change
    agents: [implementer]
    gets: the task
    hands: the diff
  - name: Check it
    agents: [tester, security-reviewer]      # at the same time
    gets: the diff
    hands: failures and problems
    when: always                             # always | {needs: [pdf]} | {says: [fix]} | ask
    repeat: {until: the tests pass and the review finds nothing, max: 3}
own_copy: false
max_usd: 0.50                                # optional: what one run may spend; the run stops there
```

| Field | Means |
|---|---|
| `for` | one line in your words: what it is for |
| `steps[].agents` | agent names; several run at the same time |
| `steps[].gets` / `hands` | what the step works from / what it hands on (words the agents are given) |
| `steps[].when` | `always` (or none) · `{needs: [pdf, images, audio, video, code, review]}` · `{says: [words]}` · `ask` (only when the request names the step or one of its agents) |
| `steps[].repeat` | `{until: <words>, max: 1-10}`: after the step, one yes/no check by its last agent; no runs it again, at most `max` times |
| `own_copy` | kept in the file; in this version it changes nothing (an agent with `more.worktree` gets its own worktree) |
| `max_usd` | dollars one run may spend; with the session's cap, checked before every call |

**What a session does with it.** A session's Workflow tool runs a workflow of yours (or a trusted project's) by name on
the step runner: each step's agents spawned as children by their names, the hand-on text carried to the next step
([the step runner](STUDIO-workflows.md#what-runs-underneath-the-step-runner)).

## A map: `format: map/1`

```yaml
format: map/1
name: everyday
boxes:                                       # main is always there
  - {id: plan, workflow: plan-it}
  - {id: sec, agent: security-reviewer}
  - {id: pick, agent: [researcher, writer]}  # a list: main decides per task
lines:
  - {from: main, to: plan, when: {says: [plan, outline]}}
  - {from: main, to: sec, when: {says: [security, review]}}
  - {from: main, to: pick, when: main-decides}
main: {agent: main}
caps: {session_usd: 20}
```

A line goes from a box (or `main`) to another box; nothing hands work to `main`. Lines that make a circle are a problem
the file check names ("the lines make a circle (plan -> ship -> review -> plan)"): a loop lives inside a workflow as
`repeat`.

## Checking a file

`halo_harness/crew/formats.py` answers one plain line per problem (`agent_problems`, `workflow_problems`,
`map_problems`); Studio shows them when you Save and on the list's `problem` tag. Tests: `tests/test_crew_formats.py`.
