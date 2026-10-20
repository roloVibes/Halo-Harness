# Slash commands: sessions, models and context

Read this when you manage the session, its model, memory, permissions or config from the prompt (`/clear`, `/model`, `/recall`, `/config` ...).

Part of [Slash commands, keys, and prompt prefixes](SLASH-COMMANDS.md), which lists every part.

## Built-in commands

### `/help`
Lists every registered command (built-ins, custom commands, skills, MCP
prompts), one line each, alphabetically, with its description.

### `/clear`
Starts a genuinely new session: fires `SessionEnd(clear)` then
`SessionStart(clear)`, builds a fresh session log, and clears the visible
transcript -- not just a view reset. Bare `-p` prints a no-op note (each
`-p` call is already a single fresh turn with nothing to clear).

### `/compact [instructions]`
Runs the real compaction algorithm synchronously (see
`docs/ARCHITECTURE.md`'s Compaction section) when a live session is
attached; an optional instructions string steers what the checkpoint
summary should emphasize. On a bare `-p` turn with no prior history, it's a
no-op note. A failed attempt leaves the conversation byte-for-byte
unchanged and says so.

### `/cost`
Total cost and turn count for the session so far (`"n/a"` when the route
doesn't report cost, e.g. Databricks). A second line (H15 part 2 addendum
4) appears once a background fetch has ever succeeded -- the same cached
figure the status bar's own "OR $12.40 left"/"OR $3.21 used" segment and
`/providers` show, naming which of three kinds it is: "OpenRouter: $12.40
remaining (this key's own limit; key: <label>, as of HH:MM:SS)", "...
(account credits, via the management key; ...)", or "OpenRouter: $3.21
used so far (this key's spend so far -- no limit set, no management key
configured; ...)". Omitted entirely when OpenRouter isn't enabled or
nothing has been fetched yet. See `docs/ARCHITECTURE.md`'s status bar
section for exactly where the figure comes from and how often it refreshes.
Halo 2.0.3 round 5e: on an `ol:`/`hf:local`/`hf:mlx` session, a third line
("Saved vs cloud: ...") shows the running total of what the SAME input/
output tokens would have cost against the session's reference price (the
configured `routing.escalation.to`, or the vendored catalog's median price
when none is set), the reference price itself, and which one it is --
omitted entirely on a cloud-model session. See [MODELS.md](MODELS.md)'s
"Saved versus cloud" section for the arithmetic.

### `/context`
A live breakdown of the current request's system/tools/messages/pruned
token counts against the model's context window, plus the token count at
which auto-compaction will trigger.

### `/model [ref]`
No argument: opens the model picker -- a filterable, arrow-key list
(`Up`/`Down`/`PageUp`/`PageDown`/`Home`/`End` move the highlight, typing
filters, `Enter` confirms, `Esc` cancels, `Ctrl+O` opens a short list to set a
ROLE for the highlighted model -- `roles.<name>`, the same table `/roles`
reads, see `docs/ROLES.md`; works from this screen's default state, filter
box included -- you never have to move focus off it first) grouped by
provider/family with one header per group (OpenRouter, `Anthropic API
(key)` -- only shown once `ANTHROPIC_API_KEY` is set --
`Databricks (<family>)` per family, an `Ollama (<host>)` group
per configured Ollama host, and an `hf:local/*`/`hf:mlx/*` group per
registered local server or served model-dirs file -- fix pass C-2: the
picker used to have no way to reach a local model by name at all).
Every row shows the SAME columns regardless of provider: context window,
max output, and USD/1M-token prices (`ctx=200k out=64k in=$1.00/M
out=$5.00/M`, blank -- never `?` -- for anything not published, including
every local row, which has no per-token price), plus,
for a Databricks row, a `[<family> · <path>]` tag naming which gateway
path it resolves to right now (see `docs/DATABRICKS.md`); an `ant:`
row's own tag instead names the resolved model id (e.g. `ant:opus` shows
`[-> claude-opus-5-5 (latest Opus)]`, see `docs/MODELS.md`'s alias table).
Databricks
pricing/context data comes from models.dev (refreshed by `/models
refresh`) when that endpoint is listed there, else from `model_table.json`
(context only), else blank -- never guessed. With a model reference (any
form `docs/MODELS.md` documents, including a bare `databricks-*`/
`system.ai.*` name or any name that matches a cached Databricks endpoint)
given directly as `/model <ref>`, switches the session to it immediately,
no picker -- mid-session model changes are logged as a fresh `meta` node.
A `cc:`/`cx:` ref (routes removed in 3.1.5.0) shows the one removed-route
line as the `/model` error instead.

### `/models [refresh]`
Bare: renders the cached Databricks table INSTANTLY, without touching the
network -- one row per endpoint (family, the family's default gateway
path, chat-capable yes/no by the endpoint's own `task`, plus the same
ctx/output/price columns `/model`'s picker shows) plus the catalog's age.
An old cache from before this table tracked gateway types shows `path
unknown (refresh needed)` rather than a silently wrong guess. `refresh`
re-lists the workspace catalog AND re-fetches models.dev's own pricing
data, both off the UI thread, and reports a one-line added/removed/changed
diff; on failure, the (unchanged) cached table is still shown, plus one
line naming the error. See `docs/DATABRICKS.md`.

### `/dbx`
An alias that always behaves like `/models refresh`, regardless of any
argument typed after it.

### `/xp routes <slug>`
Halo 2.0.4 round 2: prints the Experiential Labs gateway's waterfall rung
list for one model slug (`GET /api/models/<slug>/providers`) -- which
provider route(s) a model can resolve to, and `gateway.routing.route_id`
values to pin one. A real, bounded network call (needs `EXPLABS_API_KEY`
already configured); runs off the UI thread in the TUI, same as
`/providers`/`/doctor`. See "Experiential Labs" in `docs/MODELS.md`.

### `/mcp`
`[TUI-only for the interactive dialog]` -- lists configured MCP servers
with live health in `-p`; in the TUI, opens an interactive status dialog
(reconnect a server, approve a pending `.mcp.json` entry). 2.0.4 round 6
adds the deep dive: `D` diagnoses the highlighted server (resolve, a
real spawn+handshake with stdout/stderr, an env/PATH diff, a config-shape
check, then one proposed fix from a model) without applying anything;
`A` is the explicit yes -- diagnoses again and, when the proposal is a
config-edit/path/url fix, writes it and re-tests (a fix that verifies
healthy is remembered, so the identical failure elsewhere self-heals with
no model call next time). Each row shows its own last diagnosis (when,
the verdict, the fix proposed or applied) once one has run. See
`docs/TROUBLESHOOTING.md`'s "The deep dive" section, and `halo doctor
--mcp deep` (`docs/COMMANDS.md`) for the same thing from the CLI.

### `/ollama [--host NAME] [--refresh]`
Halo 2.0.3 round 3: per-configured-host Ollama analysis -- reachable,
version, loaded models (`size` vs `size_vram` as one plain offload
sentence, trained vs. effective context, the KV-bytes/token figure), and
-- local hosts only -- OS-level GPU memory. `--host` narrows to one
configured entry; `--refresh` bypasses the short-TTL catalog cache. In
`-p`, prints the same text `halo ollama` does; in the TUI, opens an
interactive dialog (`r` re-reads live). See `docs/MODELS.md`'s Ollama
section.

### `/local [refresh]` / `/local add <path>` / `/local forget <path>` / `/local <question>`
Halo 2.0.3 round 5 widens this from Ollama-only (round 3); round 5c adds
`add`/`forget`. Bare `/local`
(or `/local refresh`) opens the shared local-model discovery view --
Ollama hosts, running Hugging Face local servers (auto-detected plus any
configured `huggingface.local_servers` entry), and the Hugging Face Hub
cache, merged into one list with a group label per source/host; `[TUI-
only for the interactive dialog]` -- in `-p`, prints the same text `halo
local` does (see `docs/COMMANDS.md`); in the TUI, opens an interactive
dialog (`r` re-reads live, and additionally probes every manual Hugging
Face entry -- a bare open never does). `/local <question>` (any other
text) answers `<question>` from the `small` role -- now an `ol:` OR `hf:`
ref -- via a one-shot call that never touches the main transcript's
context: the question and answer show up as a note, never as a logged
user/assistant turn, so nothing here is replayed into a later request.
Needs `roles.small` set to an `ol:`/`hf:` model (`/roles`, `/role small
ol:...`, or the model picker's `Ctrl+O` action); errors plainly, never
silently, when it isn't. Round 5b part 2: when the session's main model
is also `ol:` on the SAME host and `roles.small` resolves to a DIFFERENT
local model that would not fit beside it in GPU memory, `/local` answers
from the main model instead for this one question -- see
`docs/MODELS.md`'s "VRAM-aware role defaults" section. `/local add <path>`
adds a folder to `huggingface.model_dirs` (scanned recursively for
`.gguf` files and safetensors/MLX folders -- the fourth source the merged
view above shows); `/local forget <path>` removes one -- both persist to
`~/.halo/config.json` immediately and print a plain confirmation or
refusal, in `-p` and the TUI alike (there is no separate dialog for
these two -- see `docs/MODELS.md`'s "Finding and using file-backed
models"). Serving/importing a file (`halo local serve|import`, or the
`/local` dialog's `s` key) is a CLI/dialog action, not a second `/local`
sub-verb -- see `docs/COMMANDS.md`.

### `/memory`
Shows the auto-memory directory path, whether `MEMORY.md` exists, and how
many topic files are indexed.

### `/recall <query>` (2.0.7, the old 2.0.6 scope)
Semantic search over auto-memory topics and past sessions on the LOCAL
embedding model -- ranks every indexed memory file and session log
(title, first prompt, last answer) by cosine similarity to the query and
shows the top 8 with scores. Needs `embeddings.model` set in
`~/.halo/config.json` (e.g. `"nomic-embed-text"` pulled on your Ollama
host; `embeddings.base_url`/`api_key` for an OpenAI-compatible server).
The index (`~/.halo/index/embeddings.jsonl`) refreshes incrementally
before each search; the CLI twin is `halo recall <query>`
(`docs/COMMANDS.md`). `/recall --fleet <query>` (3.1.2.0 R3) asks the hub
this machine runs or joined to fan the query out to every online member,
each answering from its own index; the hits are merged by score and shown
with their harness ([FLEET.md](FLEET.md) "Recall across the fleet").

### `/ask <question>` (2.0.7 round 0e)
The concierge secretary: `roles.concierge` (e.g.
`or:z-ai/glm-5.3-flash` -- vision=True at a fraction of the main model's
price) answers quick questions and "what's been done" updates WITHOUT
waking the orchestrator -- a one-shot call over a deterministic digest of
the session's recent history (prompts, actions, tool results, status
notices), never through the session log: the question and answer render
as a command note, never a logged user/assistant turn, so nothing here is
replayed into a later request. The same role powers the eyes (images
arriving on a blind active model get concierge descriptions folded into
the turn) and the pending-notice digest (a status block the main model
would otherwise see verbatim is compressed to a couple of lines, with the
full text archived in the log). Unset -> `/ask` says how to configure it;
every other surface degrades silently to the pre-0e behavior. Set it with
`/roles` or `roles.concierge` in `~/.halo/config.json` -- see
[AGENTS.md](AGENTS.md).

### `/permissions`
Shows the active permission mode and the allow/ask/deny rule counts.
`[TUI-only]`: opens an interactive rules dialog instead of a text summary.

### `/plan` `[TUI-only]`
In `-p`, prints the current permission mode and a note that plan review
needs the TUI. In the TUI, a plan review is actually driven by the
`plan_review` event/`PlanCard` (see [Cards](SLASH-COMMANDS-keys.md#cards-and-their-keys) below),
not by typing `/plan` -- this command is a status check, not how you
respond to one.

### `/resume [id-or-text]` `[TUI-only picker]`
In `-p`: with text, reports the matching session id (you still pass it via
`-r` on the command line to actually resume); with nothing, lists recent
sessions for this directory. In the TUI, opens the session picker with a
live fuzzy filter over title/first prompt/cwd/model, pre-filtered by any
text typed after `/resume`. Picking a session (here or from Ctrl+P) switches
the live session to it between turns: the transcript is replaced by the
resumed conversation, and hooks and the cost meter follow
the new session. While a turn is running the pick is refused with a
notification; wait for it or press Esc, then pick again.

### `/status`
A one-screen dashboard: version, current model, cwd, permission mode, MCP
server count, theme, and cost so far.

### `/config [key=value|where]`
Read-only in headless mode (shows `model=... permissionMode=... theme=...`
and refuses a write with a pointer to `~/.claude/settings.json`/`--settings`).
`/config where` prints the table `halo config where` prints: every file in
effect for this folder and home, what each sets, and which file wins a key
two files set (see [COMMANDS.md](COMMANDS.md)'s `halo config where`).
This is **not** the same store as `halo config` (which reads/writes
`~/.halo/config.json`, this harness's own settings) -- see
`docs/CONFIG.md`.

### `/skills`
Lists every discovered skill as `/name`.
