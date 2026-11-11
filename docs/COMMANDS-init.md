# Commands: `halo init`, `halo start`, `halo check`, `halo explain` and `halo setup`

Read this when you set Halo up (`halo init`, `halo setup`), run the guided first run (`halo start`) or the checks (`halo check`), or look up a word (`halo explain`).

Part of [Commands](COMMANDS.md), which lists every part.

## `halo init`

**Halo 3.3.0.0: `halo init` opens Studio.** On a real terminal (no `--provider`, no `--yes`) it starts Studio, or
reuses the one running for this home, on its **Setup** section (`?mode=setup&first=1`: 3.3.1.0 opens nothing over it,
the wizard's steps one page at a time, the rail's line says "set up this box") and prints one line. **3.3.3.0: the
terminal stays until Setup is done, then becomes the session** (3.3.15.0: both end up running and paired):

```text
Setup is open in your browser: http://127.0.0.1:<port>/?mode=setup&first=1#t=<token>. This terminal starts halo when you press Done there (Ctrl+C: stop here; `halo` later starts it).
```

While it waits it keeps `~/.halo/setup-wait.json` (its pid), so the Summary's **Done: start halo** answers "halo is
starting in your terminal"; with no init waiting, Done opens a terminal running halo itself (Windows a console, macOS
Terminal, Linux `$TERMINAL`, then qterminal, xfce4-terminal, gnome-terminal, ... with a display) or says "no terminal
found to start halo in; run `halo` yourself" -- never silent. Done writes `~/.halo/setup-done.json`; the terminal sees
it (that file, or `GET setup/state`'s `done_at` once a second), prints the Summary's four lines and starts halo as bare
`halo` does, in its directory, paired with the running Studio (same home: Session shows it). A busy Studio (a long check)
is waited out; Ctrl+C: "Setup stays open in the browser; run `halo` when you are done there.", exit 0; Studio gone (its
port silent 10 s, no marker): "Studio closed; run `halo` when you are ready.", exit 0. `--no-launch` (or
`HALO_INIT_NO_LAUNCH=1`) returns at once; it, `--yes` and the console flow end on "Start halo with `halo`; `halo studio`
opens Studio beside it ...". `halo start`'s no-provider door and `halo setup <block>` open Setup and never wait.

Setup is the wizard's steps as one page of forms ([STUDIO-setup.md](STUDIO-setup.md)).

**The console setup (3.4.0.0).** The terminal wizard's screens left; Setup is Studio. `halo init --terminal`, and
the fallback when no browser opens here (`HALO_NO_BROWSER`, `SSH_CONNECTION` / `SSH_TTY`, Linux with no `DISPLAY`
/ `WAYLAND_DISPLAY`, or a browser that does not take the URL: Studio starts anyway and its URL is printed with
`halo studio`'s port-forward line first), ask the essentials line by line on stdin and stdout, no Textual screen:
a provider from a numbered list and its key (stored by the variable's NAME in Halo's env file, the writer Setup
uses; a key never goes to config.json), the default model from a short numbered list of the catalog or typed as a
ref, another provider or not, the permission mode, and whether to run `halo doctor` now. It ends on where the
rest is (Studio's Setup: local models, theme, lineup, Linux fixes, checks, machines; its address and the
port-forward line when a Studio runs) and the start line. `--team <path|url>` (a team.json preset: the
Databricks host, the gateway preference, the roles, the default model) is applied there, as `--provider` /
`--yes` and a run with no terminal always did. `halo init --step <page>` is `halo setup <page>`: Studio's Setup on
that page (providers, local, model, permissions, theme, team, linux, check, machines), or the console way to do
the same with `--terminal` or no browser. A role table from before lineups becomes the lineup `migrated` once,
at the next interactive session or `halo init`. The sections below describe the terminal wizard as it was until
3.4.0.0.

One command that sets up a fresh box: **select a provider to set up**
(Databricks, OpenRouter or the Anthropic API -- 1.0.1 hotfix 13 replaced the old home/work/claude "preset" naming a bundle
of choices with a direct provider picker, since "work" was really just
"Databricks" wearing a confusing label), configure its credentials, pick
its default model, run `doctor`, refresh the model catalogs, send one live
"pong", and (Linux only) offer the `rg`/PATH fixes -- then offer to set up
another provider, looping until you're done; with more than one provider
configured, one last pick chooses the overall default model across all of
them. Then (1.0.1 hotfix 18) **select a default permission mode** -- `auto`
(recommended, listed first), `acceptEdits`, `default`, `plan` -- written to
`~/.halo/config.json`'s own `permission_mode` key, which every
future session (`-p` and the TUI alike) starts in unless `--permission-mode`
or `--dangerously-skip-permissions` is given that run (see
[CONFIG.md](CONFIG.md)'s "Providers" section for the full precedence
chain). Every step is idempotent -- re-running only reports what's already
correct. Never writes `~/.claude.json`/`~/.claude/settings.json`, never
prints a key or token.

**Halo 2.0.2 round 7**: on a real terminal, every interactive step above
(Providers, Default model, Permission mode) plus three more -- **Theme**
(the six built-in themes, a live preview of the transcript/status bar in
each), **Roles** (see below), and **Linux fixes**
(skipped automatically when nothing needs fixing) -- run inside ONE
Textual app, `Step N of M: <name>` in the header and `Back` / `Skip` /
`Next` (`Finish` on the last step) in the footer; nothing exits to the
console between steps, and Esc asks "Quit setup? What you saved so far
stays" instead of ending the run silently. A piped/non-tty run (every
script, `--yes`, `--provider`) is unaffected -- it keeps the exact
sequential-picker/numbered-fallback behaviour the worked example below
shows.

**Halo 2.0.5 round 2**: an **Agents** step (the bios) and a Lineup pane joined the wizard (merged into the
Team step in round 2c, below). `--step STEP` jumps straight to any one step (the flag table below); see
[AGENTS.md](AGENTS.md) for the bio and lineup fields (edited in Studio since 3.1.1.0).

**Halo 2.0.5 round 2c** (the wizard interaction model -- the full ten-rule
page is [WIZARD.md](WIZARD.md)): the wizard's first screen now offers
**Quick setup** (keys -> default model -> done -- highlighted, the
default) or **Full setup** (every step); a step rail across the top of
every step after that (Ctrl+Left/Ctrl+Right walk it from anywhere); the
round-2/2b **Agents** step and **"Roles and lineup"** step merge into ONE
**Team** step (a "Custom roles: off / on" switch; on shows Lineups and
Agents side by side, each with Enter/Ctrl+N/Ctrl+D/Del). `--step team`
reaches it; `--step agents`/`--step roles` stay as working aliases, same
as `halo setup team`/`halo setup roles` and `/setup team`/`/setup roles`.
The role-template editor's own
quick filter now also autocompletes under the field as you type (Ctrl+P
still opens the full picker).

**Halo 3.1.9.0**: the Team step preselects the default `auto` lineup (marked
"(default)" while no `team:` is set; Next on it writes nothing), "One model
for everything" clears `team:` instead of writing `team: standard`, and the
Summary (and `halo init`'s printed checks) say the lineup in use and how to
change it ([ROLES.md](ROLES.md#the-auto-lineup-halo-3190)).

**Halo 3.1.1.0**: bios and lineups are edited in Studio. The Team step
gains **Edit in Studio** (Ctrl+E: Studio's inspector on the highlighted
lineup, `halo studio --edit lineup:<name>`); Enter on a lineup shows it
read-only in the terminal (`e` there opens Studio too); Ctrl+N writes a new
lineup and opens it in Studio; Ctrl+A lists the bios (Enter shows one, `e`
opens Studio's bio form on it). See [WIZARD.md](WIZARD.md).

**Halo 2.0.3 round 5**: the interactive Providers step gains `Ollama (local or LAN)` (the local daemon, or a LAN /
cloud host with an optional key) and `Hugging Face` (`HF_TOKEN`, a dedicated endpoint, a local server by URL, or
auto-detection), both Skippable. Not `--provider` choices: neither has one sensible default model to set without a
cached catalog. See [MODELS.md](MODELS.md)'s Ollama / Hugging Face sections and [CONFIG.md](CONFIG.md)'s "Providers".

**Halo 2.0.3 round 5b part 2**: both tabs open with a detection summary from a background probe (GPU / unified
memory, whether Ollama answers and what it has, a running local server, known model folders); per installed Ollama
model the largest fully-resident context (learned cap or fit estimate, labelled), and for free room one or two model
classes that would fit at 32k context -- an estimate, never a download. See [MODELS.md](MODELS.md)'s "The wizard
detects before it asks".

**Halo 2.0.3 round 5i**: the Providers step gains an "OpenAI API (key)"
tab (paste `OPENAI_API_KEY`, Save) -- Skippable, same pattern as every tab
above; see [MODELS.md](MODELS.md)'s "OpenAI API" section.

```sh
halo init --help
```
```
usage: halo init [-h] [--provider {databricks,openrouter,anthropic}]
                 [--preset {home,work}] [--model REF] [--yes] [--no-live]
                 [--no-fixes] [--team PATH|URL] [--step STEP] [--terminal]
                 [--no-launch]

Set up halo. On a terminal it opens Halo Studio on its Setup section
(providers, the default model, permissions, the terminal theme, the lineup,
the checks) and waits: press Done on Setup's Summary and halo starts in this
terminal (Ctrl+C stops waiting; --no-launch returns at once). --terminal asks
the essentials line by line here instead (a provider and its key, the default
model, the permission mode, doctor), and so does a box where no browser can
open (SSH, no DISPLAY, HALO_NO_BROWSER); it ends on the Studio address for the
rest. --provider/--yes set a provider up without asking: its credentials, a
default model, doctor, a live pong and the Linux setup fixes.

options:
  -h, --help            show this help message and exit
  --provider {databricks,openrouter,anthropic}
                        set up this provider non-interactively (repeatable,
                        first-listed first); omit for the interactive provider
                        picker
  --preset {home,work}  deprecated alias for --provider: home=openrouter,
                        work=databricks
  --model REF           override the provider's own default model
  --yes                 accept every default without prompting
  --no-live             skip the catalog refresh and the live pong
  --no-fixes            skip the Linux rg/PATH fixes step
  --team PATH|URL       a team.json preset (host/default model/gateway
                        preference/DBU price -- never a token); overrides
                        .halo/team.json / ~/.halo/team.json
  --step STEP           open Studio's Setup on one page (providers, local, model,
                        permissions, theme, team, linux, check, machines): the
                        same as `halo setup <step>`
  --terminal            ask the essentials line by line here instead of opening
                        Setup in Studio (also what runs when no browser can
                        open: SSH, no DISPLAY, HALO_NO_BROWSER)
  --no-launch           open Setup and return at once (no wait for its Done;
                        HALO_INIT_NO_LAUNCH=1 does the same)
```

| Flag | Reads/writes | Default |
|---|---|---|
| `--provider {databricks,openrouter,anthropic}` | repeatable; each runs its own credentials -> catalog/discovery -> default-model-pick -> live-pong path, in the order given, with no "set up another?" prompt between them | omitted -> the provider list (a numbered list; 3.4.0.0: no arrow-key picker), looping until you pick "Done" |
| `--preset {home,work}` | **deprecated**: a one-line-noticed alias for `--provider openrouter\|databricks` respectively -- kept so existing scripts/docs using it verbatim keep working | -- |
| `--model REF` | writes `~/.halo/config.json`'s `model` key, skipping that provider's own model picker entirely | the provider's own default (`or:deepseek/deepseek-v4.1-flash` / `dbx:databricks-deepseek-v4-1-flash` / `ant:sonnet`) |
| `--yes` | -- | off (interactive prompts; also skips every provider's own model picker) |
| `--no-live` | skips `models --refresh` and the live pong | off |
| `--no-fixes` | skips the `rg`/PATH steps (Linux) | off |
| `--team PATH\|URL` | reads a `team.json`-shaped file/URL (see `docs/DATABRICKS.md`); Databricks only | `.halo/team.json`, then `~/.halo/team.json` |
| `--step STEP` | opens Studio's Setup on that page, the same as `halo setup <step>` (3.4.0.0: the wizard's steps left; until then it jumped the terminal wizard to a step) | omitted -> the whole Setup |
| `--terminal` | the console setup: the essentials line by line (3.4.0.0; the terminal wizard until then) instead of opening Setup in Studio (3.3.0.0 R4) | off: a bare `halo init` on a terminal opens Studio on Setup |
| `--no-launch` | opens Setup and returns at once: no wait for its Done (3.3.3.0 R1); `HALO_INIT_NO_LAUNCH=1` does the same | off: `halo init` waits for Done and starts halo |

`--provider ... --yes` (or the deprecated `--preset ... --yes`) is fully
non-interactive whenever the needed value is already discoverable; when it
isn't (e.g. no OpenRouter key found and `--yes` was passed), it prints a
`[WARN]` naming the env var to set instead of blocking on a prompt.
Credentials go to the same env file every other part of the harness reads
(`HALO_ENV_FILE`/legacy `BRIDGE_ENV_FILE`, else `~/.config/halo/env` --
falling back to a pre-2.0.0 `~/.config/vibes-hacker/env` when that's all
there is -- mode 0600 on POSIX).
The interactive provider list shows each provider's own status tag
(`configured`/`not set up`) and starts the cursor on whichever
one auto-detection would have picked (an existing `OPENROUTER_API_KEY` ->
OpenRouter; else a Databricks host/`ucode-settings.json` -> Databricks; else
an `ANTHROPIC_API_KEY` -> the Anthropic API) -- detection only positions the cursor, it never
decides for you. Each provider's own default-model pick (arrow keys, type
to filter, same `ctx`/`out`/price columns documented under
[`/model`](SLASH-COMMANDS-session.md#model-ref)) is skipped by `--yes`/`--model`;
the interactive picker itself falls back to a numbered list with no real
terminal to draw into.

**The Summary's checks (Halo 3.2.2.0).** The wizard's last screen lists the
checks Halo offers after setup, one row each: its title, then what it does,
what it costs, how long it takes and what it writes, in muted text. Space
(or Enter) ticks a row; Finish runs the ticked ones in order and prints
each one's result lines on the Summary, then Finish again closes setup.
Nothing ticked (or Esc) runs none.

| Row | What it does | Cost | Time | Writes | Default |
|---|---|---|---|---|---|
| Doctor | your config, your files, `halo` on PATH (`halo doctor`) | free | seconds | nothing | on |
| Model catalog | every provider's model list (`halo models --refresh`) | free (network) | seconds, 6 s per provider at most | the catalog caches under `~/.halo` | on |
| Hello | one one-turn call to your default model, which answers pong | one tiny call: the catalog price of about 2k tokens in, a few out (free on a local model) | seconds | one session log | on |
| Steward candidates | 3.3.7.0 R5: the local models that could run the steward here; sets `ollama.steward.model` to the best installed one (with none installed, pulls the known-good small one it names) | free, or the download it names | seconds (a download: its minutes) | `ollama.steward.model` in config.json | on when an installed one fits |
| Model gym, quick | `halo gym --quick` on the models ticked under the rows (your default model and the active lineup's models; local ones ticked) | free for a local model; the gym does not run cloud models and says so | a few minutes per model | one card per model under `~/.halo/gym/<host>/` | off |

The first three are the checks the Summary always ran before 3.2.2.0, so a
plain Finish runs the same ones (3.4.0.0: the guided first run is the first-run pack's Setup check). `--no-live` makes the catalog and
hello rows say "skipped". A `/setup` Summary has the first four rows. The
console path (`--yes`, no terminal) runs doctor, the catalog refresh and
the pong as before. The same list runs any time: [`halo check`](#halo-check-halo-3220).

**Install once, run anywhere.** `init`'s own Summary step ends with the SAME
"command on PATH" line `doctor` prints (see above) -- when `halo`
doesn't resolve to a real installed console script, it names the exact fix
(`uv tool install --reinstall .` when `uv` is present, else `pip install
--user -e .`, both re-run after every `git pull`) and reminds you to run the
command from any directory, since the checkout itself is only ever needed
for `git pull`.

Worked example (a scratch home, so nothing real is touched):
```sh
BRIDGE_TEST_HOME=/tmp/demo-home halo init --provider openrouter --yes --no-live
```
```
halo init
OpenRouter
Credentials:
   [WARN] OpenRouter key not found, and --yes skips the prompt -- set OPENROUTER_API_KEY (or re-run `halo init` without --yes).
   Default model: or:deepseek/deepseek-v4.1-flash -- wrote /tmp/demo-home/.halo/config.json
Checks:
   ...doctor lines...
   (catalog refresh skipped: --no-live)
Live pong: skipped (--no-live)
Default permission mode:
   auto (non-interactive default; pass through settings.json or `halo config set permission_mode ...` to change it)
   Default permission mode: auto -- wrote /tmp/demo-home/.halo/config.json
Linux fixes:
   ...
Summary:
   provider(s) set up this run: openrouter
   default model: or:deepseek/deepseek-v4.1-flash
   wrote /tmp/demo-home/.halo/config.json
   Run `halo` to start.
   [WARN] halo command: not found on PATH -> fix: pip install --user -e . (run from this checkout -- repeat after every `git pull`)
   Run it from any directory -- the checkout is only for `git pull`.
```

## `halo start` (the first-run pack, Halo 3.4.0.0)

`halo start`, the guided first run (one real Orchestra run that rehearses your lineup on a sample repo, its card first:
`halo start --explain`), is the first-run pack since 3.4.0.0 (`halo pack install first-run`, then `halo pack enable first-run --grant-all`). With the pack on, `halo start` and `/start` work as they did, Setup's Check page
has its row ("The guided first run", `pack:first-run:run`) and Studio's Agents section its **First run** panel; with
it off, `halo start` says in one line that it is a pack now and how to get it. Everything it does, its flags and its
error log: [the pack's README](../halo_harness/templates/packs/first-run/README.md).

## `halo check` (Halo 3.2.2.0)

```sh
halo check                          # the default-on checks: doctor, catalog, hello (+ steward when a candidate is installed)
halo check --all                    # all five, in order
halo check --doctor --gym           # the ones named (any of --doctor --catalog --hello --steward --gym)
halo check --gym --models ol:qwen3:8b,ol:llama3.2   # the gym on these models
halo check --explain                # the five rows (what, cost, time, writes) and exit
```

The checks Setup offers (`halo_harness/checks/catalog.py`,
the table under [`halo init`](#halo-init)). Each prints its title, its
what / cost / time line, then its result lines and `[ok]` or `[failed]`;
the last line counts them (`halo check: 2 of 3 passed; failed: catalog`).
`--steward` (3.3.7.0 R5) sets the steward's model from its candidates ([MODELS-ollama-steward-chat.md](MODELS-ollama-steward-chat.md#the-candidates)); `--start` says in one line that the guided first run is the first-run pack's (3.4.0.0). `--models REF,REF` picks the gym's models
(default: your default model and the active lineup's models; the gym runs
local models and names a cloud one as not run). Exit 0 when every check
that ran passed, 1 when one failed, 2 on a usage error. `/check` in the TUI
takes the same flags and prints into the transcript. Studio's
Setup section has the same five checks as its Check block, ticked rows run
as one job with a live log ([STUDIO-setup.md](STUDIO-setup.md#check-and-linux-fixes-3300-r3)).

## `halo explain`

```sh
halo explain                 # every word, with its first sentence
halo explain lineup          # the word's paragraph
halo explain hand-offs       # fuzzy: plurals, hyphens, spaces, a prefix (orch), a near spelling
halo explain --json tier     # {query, word, text, closest}
```

One paragraph per word Halo uses (lineup, bio, role, tier, team, member,
block, stage, lane, part, step, mission, gate, claim, hand-off, plan,
coach, orchestra run, fleet, hub, harness, capability, unit, pack, guided
first run), from
[GLOSSARY.md](GLOSSARY.md): the same text `/explain` shows in the TUI and
Studio's Glossary lists. An unknown word names the closest ones, exit 1.

## `halo setup` / `/setup` (Halo 2.0.2 round 7)

```sh
halo setup              # Studio's Setup (3.3.0.0 R4)
halo setup team         # Setup on its Team page: ?mode=setup&block=team (`halo setup roles` is the same)
halo setup --terminal   # the init wizard's Team step, then a short summary
halo setup team --terminal   # just the Team setup screen (Halo 2.0.5 round 2c)
```

On a real terminal `halo setup` opens Studio on Setup, on the Team page (focused) for
`team` / `roles` (one line says it opened, as `halo init` does). `--terminal` keeps the SAME Team setup
screen `halo init`'s own wizard shows (see [WIZARD.md](WIZARD.md)), reachable again later without
re-running the whole provider flow; so does a box where no browser can open (the URL and the
port-forward line first). With no TTY it prints the current roles table instead of blocking, and exits 0 (3.3.11.0 R3: `halo setup <pack>`, [COMMANDS-packs.md](COMMANDS-packs.md#halo-setup-pack)).
`/setup` and `/setup team` (`/setup roles` stays as an alias) open Setup the same way from a running
session (the line in the transcript says it opened, or gives the URL); `/setup --terminal [team]` pushes
the terminal screen onto the live app (a modal stack over the session, not a separate program): saving a
lineup or a role template there updates the LIVE session's own role table immediately, no restart
needed.
