# Slash commands: providers, fleet and upkeep

Read this when you set up providers, rate limits, remote control or the fleet, or run `/doctor`, `/update` and `/bugreport`.

Part of [Slash commands, keys, and prompt prefixes](SLASH-COMMANDS.md), which lists every part.

## Built-in commands: providers, fleet and upkeep

### `/providers [list|enable <name>|disable <name>|setup <name>]`
H15 item 21 (rule replaced by the H15 part 2 addendum): the provider-
enablement table -- status, reachable, cached model count -- for
`databricks`, `openrouter`, `anthropic`, `huggingface` (`hf:`),
`openai` (`oai:`, round 5i part 1), `experiential` (`xp:`) and `typesafe` (stores
`TYPESAFE_API_KEY` only, for a later feature; no routed models yet). Each
row's status is `auto (detected from <source>)` once a
real credential is found (no `init` step required), `disabled by
you`/`enabled by you` once an explicit override exists, or `not set up`.
Bare `/providers` (or `list`) prints the table, plus a trailing OpenRouter
balance line once a background fetch has ever succeeded (see `/cost`);
`enable <name>`/`disable <name>` write an explicit override (`true` forces
a provider on with no credentials at all; `false` hides one auto-detection
would otherwise have turned on) right here (`ant`/`dbx`/`or` are
accepted aliases for the canonical names); `setup <name>` needs the
interactive picker `halo init`/`halo providers setup <name>`
show from a real terminal, so headless just points at that command instead
of half-implementing it. See `docs/MODELS.md`'s "Provider enablement"
section for the full prefix/label table and the exact per-provider
detection rule.

### `/gov [host]`

Halo 2.0.5 round 4: the Governor's gateway buckets -- one line per
gateway host the Governor has state for (rate vs ceiling, in-flight,
waiting, cooldown), the SAME table `halo gov` prints. With a host
argument, also that host's recent calls (agent, role, status -- the
per-bucket log tail). Read-only: it inspects persisted bucket state,
never sends a request. See GOVERNOR.md for the whole mechanism.

### `/balances [refresh]`
Halo 2.0.4 round 3 (deliverable 2): one shared balances surface for every
provider whose API offers a balance/credit endpoint -- OpenRouter (`GET
/key`/`/credits`, reusing the SAME cache `/cost`/the status-bar chip
already read), Experiential Labs (`GET /credits`), Databricks (always
"not offered" -- DBU billing is on the workspace side, explicitly
excluded), and Anthropic (no endpoint for a plain key; the organisation
cost report when `ANTHROPIC_ADMIN_KEY` is configured). Every other
provider (Hugging Face, OpenAI, TypeSafe) has no balance concept at all and reads "not offered." Bare
`/balances` never touches the network -- it prints whatever
`~/.halo/balances.json` already has cached, or "not fetched yet";
`/balances refresh` does the one bounded round of fetches and persists
the result. `halo balances [--refresh]` is the CLI twin, same shared
`providers.balances` module -- the two surfaces never disagree. The
status bar's own balance chip (right after cost) shows the SAME cached
figure for whichever provider is the session's current model, falling
back to OpenRouter's reading when the active provider has none of its
own yet.

### `/rules [forget <provider:model>]`
Halo 2.0.5 round 3 (G1): lists every learned PARAMETER-rejection rule
(endpoint, field, action, age) `providers.learned_params` has recorded --
the first time a live 400/422 proves a specific endpoint rejects a
request field this harness sent (`reasoning_effort`, `temperature`,
`top_p`, `tool_choice`, `max_tokens`, `max_completion_tokens`, `thinking`,
`output_config`, `response_format`, `parallel_tool_calls`, `strict`,
`store`, `stream_options`, `metadata`, `stop`), the smallest fix is
applied and the request retried ONCE, and -- only once that retry is
confirmed to have worked -- remembered for every later request against
that same endpoint; a `model_table.json` row's own explicit value always
wins. `/rules forget <provider:model>` clears every learned parameter
rule for that one endpoint (never its other learned facts, such as
`tools_rejected`). `halo rules [--forget <provider:model>]` is the CLI
twin, same shared `providers.learned_params` module; `halo models
--forget-rules` is the blunt, every-endpoint reset; `halo doctor --work
--probe-all --learn` pre-learns these rules instead of waiting to
discover them one real turn at a time.

### `/effort [level]`
1.0.1 hotfix 19/20. Bare `/effort` shows the effective level, its source
(`flag`/`settings`/`default`/`session`), and the accepted levels for the
current route -- in the TUI it instead opens an inline selector card in
the transcript (Claude Code style): a horizontal row of the route's own
accepted levels (never the full vocabulary -- an Anthropic route never
offers `xhigh`, which that endpoint schema rejects), current one
bracketed, one-line description underneath. **Left/Right** or **h/l**
move, **Enter** applies, **Esc** cancels and keeps the old value (either
way, focus returns to the prompt); a model with no adjustable effort at
all shows a one-line card that closes on any key. `/effort <level>` (in
either mode) sets it immediately, clamped to what the route accepts
(`xhigh` on a route without it becomes `max`) -- effective from the next
message, remembered for the rest of the session. `--effort`/settings
`effortLevel` still set the STARTING value; every Anthropic-family route
(`ant:`/a Databricks Claude foundation endpoint) defaults to `high`
when nothing more specific was set anywhere. See
[MODELS.md](MODELS.md)'s "Reasoning effort" section for the accepted-level
table per route family.

### `/remote [status|pair [N]|off]`
Halo 2.0.9. Bare `/remote` in the TUI opens the remote-control dialog: the
Signal bridge's state (off, starting, connected, rate-limited, stopped), the
control-socket line, the paired phones (ACI prefix, number, paired time, signed,
blocked) and the contact requests waiting for you. `a` approves the highlighted
request and shows the one-time code large, then the signing phrase and link once
(`w` = "I wrote it down"); `s` turns signing on or off for a phone, `u` unpairs,
`v` reverifies after a safety-number change, `o` is the kill switch, `r`
refreshes, Esc closes. The bridge itself is never started in the TUI: when it is
not running the dialog says to run `halo remote signal run`. The bridge's notices
(changed safety number, rate limit, captcha) arrive as notifications.

`/remote status`, `/remote pair` (list the requests), `/remote pair <N>`
(approve request N, print the code) and `/remote off` do the same as text in
the transcript, and are what print mode answers. While a phone is attached to
this session the status bar shows a `⇄ remote` chip. See
[REMOTE.md](REMOTE.md).

### `/private [on|off]`
Halo 3.0.5.0 (Fleet). `/private on` makes this session private: it closes
its control socket and leaves `~/.halo/run/sessions.json`, so Studio,
`halo remote` and the fleet no longer see it, and the status bar shows a
`private` chip. `/private off` opens the socket again and lists the
session. Bare `/private` prints the state and the control-socket line.
`halo --private` starts a session private, and `fleet.private: true` in
`~/.halo/config.json` makes every session start private. A `halo -p` run
started private stays private. See [FLEET.md](FLEET.md).

### `/mission [id]`
Halo 3.0.6.0 (Fleet Missions). The fleet's missions (id, state, parts, cost,
harnesses, goal), or one mission's parts by harness with their state and
cost: the same as `halo fleet mission status [id]`. Making, planning, running
and stopping a mission is `halo fleet mission ...` (see [MISSIONS.md](MISSIONS.md)).

### `/fleet [text]`
Halo 3.0.5.0 (Fleet). Bare `/fleet` opens the fleet table as a dialog: one
row per agent of every harness this machine sees (harness, session, agent
indented under its parent, state, what it is doing, cost), refreshed every
2 s. It reads Studio's `GET /api/fleet` when Studio runs (every member of
its hub included), else the hub this machine serves, else this harness
alone. Keys: Up/Down select, `s` steer that agent (type the note, Enter),
`k` stop it (press `k` twice: the first press asks), `p` pause or resume
it, `r` refresh, Esc or `q` close. A command for another harness goes
through the hub and is applied only as that harness's owner allows
(`fleet.allow_control`). `/fleet text` prints the same table in the
transcript, and is what print mode answers. The terminal twin is
`halo fleet`. See [FLEET.md](FLEET.md).

### `/offline [on|off]`
Halo 2.0.3 round 5e. Bare `/offline` reports whether offline mode is on and
where that reading came from (`--offline`/`HALO_OFFLINE` for this one
process, or the persisted `network.offline` key). `/offline on`/`/offline
off` persists `network.offline` to `~/.halo/config.json` AND takes effect
immediately for the rest of this process (no restart) -- in the TUI the
status bar's "offline" chip updates right away, the same "direct push, no
event round-trip" pattern `/effort` uses. While on, the one HTTP choke
point (`providers/http.py`) refuses any connection whose host isn't
loopback or an allow-listed local host (every `ollama.hosts` entry, every
`huggingface.local_servers` entry, every managed local-server-registry
entry); the refusal is always the one plain sentence "offline mode: not
connecting to \<host\>". See [CONFIG.md](CONFIG.md)'s `network.offline`
section and [COMMANDS.md](COMMANDS.md)'s `--offline`.

### `/escalation`
Halo 2.0.3 round 5e. Shows the configured hybrid-escalation policy
(`routing.escalation` -- set with `halo config set routing.escalation
'{"to": "...", "when": [...], "ask": true|false}'`, there is no `/escalation
<args>` form of its own) and this session's last few escalation decisions
(trigger, target, whether it asked or switched). Only ever relevant on a
local-model session (`ol:`/`hf:local`/`hf:mlx`) -- see
[MODELS.md](MODELS.md)'s "Hybrid escalation" section for the three
triggers and what "ask" vs. auto actually do.

### `/init`
A **prompt**-kind command: its body is a fixed instruction asking the
model to analyze the codebase and write/update `CLAUDE.md` -- the model
does the actual work as an ordinary turn, this command doesn't write
anything itself.

### `/doctor`
Runs the same read-only checks as `halo doctor` and prints the
lines inline in the transcript.

### `/update`
Checks the installed build against what's available (cached up to 24h) and
prints installed vs. available, the commits between them, and the exact
reinstall command. In `-p`/a plain fallback this is report-only, same as
`halo update --check`. In the TUI it opens a dialog with that same report
plus two keys: `Enter` quits halo and the update runs after it exits
(3.2.2.0: a detached updater waits for halo to end, stops what lingers,
runs the reinstall and `halo --version`, all into `~/.halo/update.log`;
the last lines halo prints give that path and `halo --continue` to resume
the session); `Esc` leaves everything untouched. A background check
(off with `update.check: false`/`update.notify: false` in config.json) adds
a one-line transcript note, at most once a day, when one is already known
to be available -- see `docs/INSTALL.md`'s "Update" section.

### `/export` `[TUI-only]`
In `-p`, prints a note that export needs the TUI's file picker (use
`halo export` or `halo session export <id>` instead -- see `docs/COMMANDS.md`).
In the TUI, `/export [--sanitize] [path]` writes the session as one Markdown
trace (3.3.0.0: the header with the totals, then one entry per row -- prompts,
text, tool calls and their results trimmed to 40 lines, steers, nudges,
permission answers, turn ends, compactions, errors -- keys masked, home paths
as `~`), beside the session log as `halo-trace-<session id>-<yyyy-mm-dd-hhmm>.md`
unless you name a path, and says the path. It is the same file
`halo session export <id>` and Studio's **Export** write
([Studio: steering and exporting a session](STUDIO-session.md)); `Ctrl+X Ctrl+S` runs it too.

### `/bugreport [--copy] [--include-content]`
2.0.1: writes a redacted diagnostic report to `~/.halo/bugreports/<timestamp>.md`
("one paste instead of screenshots") -- halo version, Python/OS/terminal,
install mode, which providers are enabled and WHY (env file, settings env,
databrickscfg, claude.ai login -- never a key, not even a fingerprint), the
current route (ref/provider/dialect/effort requested and sent), permission
mode, MCP servers, `~/.halo/config.json` with secret-shaped values replaced,
settings source paths (paths only), catalog cache age per provider, this
session's own learned permission rules, the last turn's timeline, the last
N session events, and the last 50 `bridge.log` lines. Every line passes
through the same redactor `/export --sanitize`/`halo export --sanitize`
use, plus a stronger pass (long hex/base64 runs, and the literal value of
any secret env var this process can see). `--copy` also copies the report
text to the clipboard; `--include-content` includes prompt/output text, not
just event shapes. `halo bugreport [--last N] [--session ID] [--out FILE]
[--copy] [--include-content]` is the equivalent command when nothing is
running at all (reads the most recent session for the cwd, or `--session
<id>`).

### `/timeline [N]`
2.0.1: shows the last `N` (default 1) turns' own request/tool timing --
request-sent/headers/first-reasoning/first-text/first-tool-call/message-end
elapsed milliseconds, each tool call's start/end/status, steers, and
retries/errors -- recorded by `agent.loop.Session.turn` for every turn
regardless of dialect. 2.0.1 W3b also records each HOOK that ran (event
name + real duration), each PERMISSION ask that blocked the turn (start,
end, resolved decision), and auto-compactions (phase, trigger, tokens
before/after) -- a manual `/compact` isn't a turn, so it never appears
here. `--debug` prints the same lines live as they happen. `halo timeline
--last N [--session ID] [--json]` (a separate command, `docs/COMMANDS.md`)
reads the same records back from a session's own log file instead, for
after the fact or a different process.

### `/add-dir <directory>`
In `-p`, explains that a running session can't be extended this way --
pass `--add-dir` on the command line at startup instead. (The TUI shares
this same headless text today; a directory is normally added via
`--add-dir` at launch.)
