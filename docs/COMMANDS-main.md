# Commands: `halo` and its model and session flags

Read this when you start `halo` with flags: the main command, its model and session flags.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo` (the main command)

```
halo [PROMPT] [flags...]
```

With no `-p`/`--print`, `halo` opens the full-screen TUI (see
`docs/SLASH-COMMANDS.md`); a `PROMPT` positional argument pre-fills it as the
first turn. `-p`/`--print` runs one headless turn instead and exits -- this
is what every worked example on this page uses. Outside a real terminal
(piped stdin, cron, a subprocess with no tty), the bare (non-`-p`) form
prints one line and exits 2 rather than hanging, since nothing could ever
drive a full-screen UI there:

```sh
echo | halo
```
```
halo: a full-screen session requires an interactive terminal (stdin is not a tty) -- use -p/--print for a non-interactive run
```
(exit code 2)

A bare `-p` positional prompt, or stdin (UTF-8, 10 MB cap) when no positional
is given, is the text of the first turn:

```sh
halo --demo -p
```
```
All done -- that's a scripted demo turn.
```

```sh
halo --demo -p --output-format json
```
```json
{"type": "result", "subtype": "success", "is_error": false, "result": "All done -- that's a scripted demo turn.", "session_id": "demo-session", "num_turns": 1, "stop_reason": "end_turn", "usage": {"input_tokens": 270, "output_tokens": 100}, "total_cost_usd": 0.0, "structured_output": null, "model": "or:deepseek/deepseek-v4.1-flash", "permission_denials": [], "background_notices": []}
```

An unresolvable `--model` is a clean, scriptable usage error (exit 2), with a
near-miss suggestion when the OpenRouter catalog is cached (`halo
models --refresh`) and something close matches:

```sh
halo -p --model not-a-real-model-ref "hi"
```
```
halo: invalid --model: no route: 'not-a-real-model-ref' (accepted forms are dbx:, or:, ant:, oai:, xp:, ol:, hf:, vendor/model, a bare databricks-*/system.ai.* name, a Claude alias such as sonnet, or a routes.json alias)
```

Exit codes across every route: `0` success, `1` the turn ran and ended in an
error (upstream failure, budget exceeded), `2` a usage/config error (bad
flag value, no prompt given, invalid model), `130` `Ctrl+C` during a `-p`
turn (POSIX `128+SIGINT`).

### Model & session flags

#### `--model MODEL`, `--small-model MODEL`
What: the main model for this session, and the model used for
background/small tasks (title generation, `/improve` drafting when
`improve.model` isn't set) respectively. Reads: `~/.halo/config.json`
(`model` key), `routes.json`'s `aliases`/`default` and `small`, `HALO_MODEL`
(legacy `BRIDGE_MODEL`) env, only when neither flag is given -- see `docs/MODELS.md` for the full
resolution order. Default: `or:deepseek/deepseek-v4.1-flash` (see
`model.DEFAULT_MODEL_REF`) when nothing else resolves.
```sh
halo -p --model or:deepseek/deepseek-v3.2 --small-model or:deepseek/deepseek-v3.2 "hi"
```

#### `--effort {low,medium,high,xhigh,max}`
What: requests a reasoning-effort level, mapped per-provider (a thinking
budget for `ant:`/Databricks Claude passthrough, `reasoning.effort` on
OpenRouter, `reasoning_effort` on Databricks chat) -- ignored (no field
added) for a model whose profile doesn't support it. Related config:
`effortLevel`/`modelSettings.<id>.effortLevel` in `settings.json` set a
session's *default* effort when `--effort` is omitted (`docs/CONFIG.md`).

#### `--offline`
Halo 2.0.3 round 5e, Halo-only (not a Claude Code flag). What: enforces
offline mode for this one process -- sets `HALO_OFFLINE=1` in this
process's own environment (never written to `~/.halo/config.json`; `/offline
on` is the persisted equivalent). The one HTTP choke point
(`providers/http.py`'s `open_upstream`/`urlopen_tls`) then refuses any
connection whose host isn't loopback or an allow-listed local host (every
`ollama.hosts` entry, `huggingface.local_servers` entry, or managed
local-server-registry entry) -- update checks, catalog refreshes, the
Hugging Face router, OpenRouter, Databricks, Anthropic and WebFetch/
WebSearch are all refused the same way; the claude.ai connectors bridge's
background discovery is skipped instead (its real network call happens
inside a spawned `claude` subprocess, outside this process's own choke
point). The refusal is always one plain sentence: "offline mode: not
connecting to \<host\>". See [CONFIG.md](CONFIG.md)'s `network.offline`
section and [SLASH-COMMANDS.md](SLASH-COMMANDS.md)'s `/offline`.
```sh
halo --offline -p "reply with the single word pong" --model ol:qwen3-coder:30b
```

#### `--private`
Halo 3.0.5.0 (Fleet), Halo-only. What: this session registers nothing and
opens no control socket, so Studio, `halo remote` and the fleet never see
it (sets `HALO_FLEET_PRIVATE=1` for this process, so the Orchestra workers
it starts are private too; never written to `~/.halo/config.json`). The
TUI shows a `private` chip; `/private off` lists it again; `fleet.private:
true` makes every session private. See [FLEET.md](FLEET.md).
```sh
halo --private
halo --private -p "summarize the diff"
```

#### `-c`, `--continue`
What: resumes the most recently modified session for the current directory
(by the session `.jsonl` file's own mtime). Reads:
`~/.halo/sessions/<slug>/*.jsonl`. With no earlier session for the directory
(and likewise a bare `-r`), `-p` stops with exit 2 and a message -- it never
quietly starts a new session.
```sh
halo -p -c "keep going"
```

#### `-r`, `--resume [ID_OR_TEXT]`
What: with an id (or unique id prefix), resumes that exact session; with
free text, resumes the one session that text uniquely matches by title/first
prompt/cwd/model, or -- in print mode -- lists the ambiguous candidates
instead of guessing; with nothing at all, opens the TUI's session picker
(pre-filtered if this flag's own value made the CLI resume ambiguous).
```sh
halo -p -r a1b2c3d4 "one more thing"
```

#### `--fork-session`
What: combined with `-c`/`-r`, continues from that session's log *without
overwriting it* -- the new turns land in a fresh session id, the source is
untouched (same file-copy mechanism as `/fork`). With
`--no-session-persistence` the fork is deleted again when the run ends.

#### `--session-id UUID`
What: use this exact session id for a brand-new session (must not already
exist). Mirrors Claude Code's own flag; mainly useful for scripted/SDK-style
callers that want a known id up front.

#### `-n`, `--name NAME`
What: sets this session's title (same effect as `/rename` after the fact).
Writes: `~/.halo/sessions/<slug>/index.json`.

#### `--agent AGENT`, `--agents JSON_OR_FILE`
What: `--agent` pins this top-level session to run as if it were the named
sub-agent (its own tool/model/permission-mode restrictions apply from turn
one); `--agents` adds extra agent definitions inline -- a literal JSON object
string in the TUI, or (in `-p`) either a literal JSON string or a path to a
JSON file holding `{name: {description, prompt, tools, model, ...}}`. See
`docs/CONFIG.md`'s agents section for the full discovery precedence these
sit on top of.

#### `--team TEAM`

What: run THIS session under that team template (`halo teams list` names
them; `docs/AGENTS.md` for the schema) -- the lineup's sections are
ENFORCED by the live agent loop through `teams_runtime.py` (Halo 2.0.5
round 5): `routing` maps a task kind to a role/alias at spawn time,
`delegation` caps depth/parallel and shapes the hand-back, `budget` stops
delegation with its reason when exhausted, `escalation` switches on its
triggers, `context`/`permissions` apply to every member, `pipeline` gates
stages in order, and member bios' `hooks`/`schedule`/`triggers` arm.
Overrides config's own active `team:` key for this one run, never
persisted; an unknown name degrades to a stderr line and no team (same
shape as an unknown `--agent`). The team's own resolved role table rides
ON TOP of the persisted one, so a `--team` run needs no config change.
```sh
halo --team halo-dev-cycle
halo -p --team balanced "delegate the research and review"
```

#### `--role NAME=MODEL[:EFFORT]`

What: overrides one of the ten built-in roles (`orchestrator`, `planner`,
`coder`, `reviewer`, `judge`, `researcher`, `tester`, `compaction`, `small`,
`subagent_default`) -- or any custom name a team.json/loaded template
already defines -- for this run only -- a built-in/custom sub-agent whose
own role resolves to `NAME` uses `MODEL` (and `EFFORT`, if given) instead of
whatever `~/.halo/config.json`/`team.json`'s own `roles` table (or the
cost-aware default) says, even beating that agent's own file `model:` (a
freshly-typed, run-only override the user gets to trump a shared/managed
agent file with). Repeatable (`--role coder=... --role researcher=...`); a
later repeat of the SAME role wins. A bad `NAME=MODEL` (missing `=`, an
unrecognized role name, an empty model) is a clean exit-2 usage error before
any Session is built. See `docs/ROLES.md` for the full precedence chain,
`/role`/`/roles`, role templates, and `stats --roles`.
```sh
halo -p --role researcher=or:deepseek/deepseek-v4.1-flash "use the Researcher agent to summarize this repo"
```

#### `--file SPEC [SPEC ...]`
What: attaches one or more local files as context before the first turn (an
image becomes a real vision content block when the model profile supports
it; anything else becomes a text snapshot) -- the same path resolution a
model's own Read tool call would use. **Argparse quirk**: this flag is
`nargs="+"`, so it greedily consumes every following bare word as another
SPEC -- put the prompt *before* `--file`, or use a `--` separator, or the
prompt itself disappears into the file-spec list:
```sh
halo -p "summarize the attached file" --file ./notes.txt
```
Claude Code's own `file_id:relative_path` cloud-resource form (a
claude.ai-hosted file) has no backing store in this standalone harness and
prints one clear stderr notice instead of pretending to work; on Windows, a
path to a file that does *not* exist can be misread as that form too (both
shapes contain a `:`) -- see `docs/TROUBLESHOOTING.md`.

#### `--add-dir DIRECTORY [DIRECTORY ...]`
What: extends the session's allowed working directories beyond `--cwd`
(path-rule matching and the mode table's "in workdir" checks then also
accept these). Related config: `permissions.additionalDirectories` in
`settings.json` does the same thing persistently.

#### `--cwd CWD`
What: the working directory for this session (settings/CLAUDE.md/memory/
trust are all resolved relative to it). Default: the process's actual `cwd`.
