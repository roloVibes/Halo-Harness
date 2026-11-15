# Slash commands: agents, maps and review

Read this when you work with your agents, the map a session runs on, or `/review` from the prompt.

Part of [Slash commands, keys, and prompt prefixes](SLASH-COMMANDS.md), which lists every part.

## Built-in commands: agents, maps and review

### `/agents [new <name>|edit <name>|live]`
Halo 3.6.0.0 R5: your agents are files in `~/.halo/crew/agents/` (agent/1). Bare `/agents` lists the agents this
session may hand work to; `/agents live` the session's running agents. `/agents edit <name>` opens Studio's
Agents -> 1 · Agents on that agent; `/agents new <name>` makes a blank one of yours first, then opens it there. The
terminal's `halo agents` (list / show / new / edit / try) does the same from a shell.

### `/map`
Halo 3.6.0.0 R5: the map this session runs on, read-only: its name, main, one line per hand-off (`main -> coder (agent
coder): main decides per task`), the chains, and the boxes nothing hands work to yet. Every session runs on a map --
the shipped `starter` until you pick one (`halo maps use <name>`, or **My sessions use this** on Studio's Map). To
change it, open Studio (`halo studio`, Agents -> 3 · Map).

### `/teams`, `/roles`
Halo 3.6.0.0 R5: lineups are gone. Each prints one line saying where to go (the map) and changes nothing. `/role
<name> <model> [effort]` below still sets one role's model for this session.

### `/tools`
Halo 3.1.8.0 R5: the tools this session's agent sees, one line per
capability (read, edit, bash, web, agent, `mcp:<server>`, media, recall,
other) with the tool names in it, then what narrowed the list ("Narrowed to
tools: read, edit, bash (by lineup ci)", or "(by bio reviewer)") or that
nothing does, then an Orchestra worker's isolation and secrets lines. A
lineup or bio narrows it with `tools.capabilities`; see
[ISOLATION.md](ISOLATION.md#toolscapabilities).

### `/edit <agent:name|workflow:name|map:name>`
Halo 3.1.1.0 R3; 3.6.0.0 R5: opens Studio on that agent (Agents -> 1 · Agents), workflow (2 · Workflows) or map (3 ·
Map); a bare name is an agent, else a workflow, else a map. The old forms (`bio:<name>`, `lineup:<name>`, `team`)
say that lineups and bios are no longer read and open the tab that replaced them.

### `/role <name> <model> [effort]`
Halo 2.0.2: sets ONE role for THIS session only -- mutates the live
session's own role table directly (never persisted; `/roles save <name>`
is the explicit "keep this" action), so the very next `Agent`/`Task` call
that resolves this role picks it up. `<name>` must already be a known role
(a built-in, or a custom name a team.json/loaded template actually defined)
-- an unknown name errors with the list of known ones. See `docs/ROLES.md`.

### `/review [target] [--level low|medium|high] [--dimensions a,b] [--fix] [--no-verify]`
Halo 2.0.10: review a change with parallel dimension reviewers (correctness,
security, performance, tests, docs-consistency; one read-only sub-agent each,
on the `reviewer` role) and a judge that checks every finding (`judge` role).
`target` is nothing (this branch against its base, uncommitted changes
included), a range `a..b`, a branch, a PR number (`#123`, needs `gh`), or paths
and globs reviewed as they are. The reviewers appear live in `/tasks`; the
result lands in the transcript as a header line ("N findings (c confirmed, p
plausible) from d reviewers in t s, $cost") and one card per finding: severity,
`file:line` (click it, or press `c`, to copy), the verdict badge and the short
summary, with the failure scenario folded (Enter or a click unfolds it, `y`
copies the finding). `--fix` has a `coder` sub-agent apply a minimal fix per
CONFIRMED finding in the working tree (never committing) and re-verifies it;
`--no-verify` skips the judge. Esc aborts every reviewer. Runs on a worker
thread. In print mode (`-p "/review ..."`) it prints the text form; `halo
review` is the CLI form, with `--json`. See `docs/REVIEW.md`.

### `/setup [roles]`
Halo 3.3.0.0 R4: `/setup` opens Studio's **Setup** section, and `/setup team`
(`/setup roles` is the same) opens it on its Team block
(`?mode=setup&block=team`); one line in the transcript says it opened (or,
when no browser took it, gives the URL and says `/setup --terminal` is the
terminal screen). `/setup --terminal [team|roles]` is Halo 2.0.2 round 7's
screen: the init wizard's own Team setup screen over the live session (a modal
screen stack, not a separate program) -- bare `/setup --terminal` chains it ->
a short summary. Saving a role template there updates the LIVE session's own
role table immediately, no restart needed. `halo setup [team|roles]
[--terminal]` is the CLI equivalent (prints the current roles table with no
TTY instead of blocking). See [STUDIO-setup.md](STUDIO-setup.md) and
`docs/ROLES.md`.
