# Commands: `halo init`, `halo start`, `halo explain` and `halo setup`

Read this when you set Halo up (`halo init`, `halo setup`), run the ten-minute start (`halo start`) or look up a word (`halo explain`).

Part of [Commands](COMMANDS.md), which lists every part.

## `halo init`

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

**Halo 2.0.5 round 2**: an **Agents** step joins right before Roles (after
the keys step's own model enumeration) -- list every agent bio (project/
user/shipped), create/edit/duplicate/delete, and import a `.claude/
agents/*.md` file as a bio; the Roles step is retitled **"Roles and
lineup"** and gains a Lineup pane (pick, edit, or build a new lineup --
assignments by model or by agent bio, the `about:` "how the pieces work
together" text) shown first, with the pre-existing role-template editing
moved to its own "Legacy roles" pane rather than removed. `--step STEP`
jumps straight to any one step (see the flag table below); see
[AGENTS.md](AGENTS.md) for the bio and lineup fields (edited in Studio
since 3.1.1.0).

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

**Halo 2.0.3 round 5**: the INTERACTIVE Providers step's tab bar gains two
more tabs beyond the four above -- `Ollama (local or LAN)` (detects/
registers the local daemon, or add a LAN/cloud host with an optional key)
and `Hugging Face` (paste `HF_TOKEN`, add a dedicated endpoint, add a
local server by URL with an optional key, or rely on auto-detection --
any subset, all optional) -- both Skippable, same Back/Skip/Next footer.
Deliberately NOT `--provider`/`--preset` CLI-flag choices (the piped/
non-tty fallback above still only ever offers the original four): neither
has one sensible hardcoded default model the way the table below's four
providers each do, so there is nothing non-interactive `--provider
ollama`/`--provider huggingface` could safely default to without a real
catalog already cached. See [MODELS.md](MODELS.md)'s Ollama/Hugging Face
sections and [CONFIG.md](CONFIG.md)'s "Providers" section.

**Halo 2.0.3 round 5b part 2**: both of those two tabs now open with a
short detection summary -- GPU/unified memory, whether Ollama is already
reachable and what it has, any running local server, and model folders
already known -- filled in by a background probe (never the UI thread; a
slow probe just leaves the "detecting..." placeholder a little longer,
the rest of the tab is usable immediately either way). For each already-
installed Ollama model it names the largest fully-resident context
(learned cap or fit estimate, labelled); for free room, one or two
illustrative model classes/quantizations that would fit with a 32k
context -- an estimate, never a download from here. See
[MODELS.md](MODELS.md)'s "The wizard detects before it asks" section.

**Halo 2.0.3 round 5i**: the Providers step gains an "OpenAI API (key)"
tab (paste `OPENAI_API_KEY`, Save) -- Skippable, same pattern as every tab
above; see [MODELS.md](MODELS.md)'s "OpenAI API" section.

```sh
halo init --help
```
```
usage: halo init [-h] [--provider {databricks,openrouter,anthropic,claude}]
                 [--preset {home,work,claude}] [--model REF] [--yes]
                 [--no-live] [--no-fixes] [--team PATH|URL] [--step STEP]

Set up halo in one command: pick a provider to set up, configure its
credentials, set a default model, run doctor, send a live pong, and offer the
Linux setup fixes. Repeat for another provider, then pick the overall default.

options:
  -h, --help            show this help message and exit
  --provider {databricks,openrouter,anthropic,claude}
                        set up this provider non-interactively (repeatable,
                        first-listed first); omit for the interactive provider
                        picker
  --preset {home,work,claude}
                        deprecated alias for --provider: home=openrouter,
                        work=databricks, claude=claude
  --model REF           override the provider's own default model
  --yes                 accept every default without prompting
  --no-live             skip the catalog refresh and the live pong
  --no-fixes            skip the Linux rg/PATH fixes step
  --team PATH|URL       a team.json preset (host/default model/gateway
                        preference/DBU price -- never a token); overrides
                        .halo/team.json / ~/.halo/team.json
  --step STEP           jump directly to one wizard step by key or 1-based
                        number (e.g. --step agents), interactive only
```

| Flag | Reads/writes | Default |
|---|---|---|
| `--provider {databricks,openrouter,anthropic}` | repeatable; each runs its own credentials -> catalog/discovery -> default-model-pick -> live-pong path, in the order given, with no "set up another?" prompt between them | omitted -> the interactive provider picker (arrow keys on a real terminal, a numbered list otherwise), looping until you pick "Done" |
| `--preset {home,work}` | **deprecated**: a one-line-noticed alias for `--provider openrouter\|databricks` respectively -- kept so existing scripts/docs using it verbatim keep working | -- |
| `--model REF` | writes `~/.halo/config.json`'s `model` key, skipping that provider's own model picker entirely | the provider's own default (`or:deepseek/deepseek-v4.1-flash` / `dbx:databricks-deepseek-v4-1-flash` / `ant:sonnet`) |
| `--yes` | -- | off (interactive prompts; also skips every provider's own model picker) |
| `--no-live` | skips `models --refresh` and the live pong | off |
| `--no-fixes` | skips the `rg`/PATH steps (Linux) | off |
| `--team PATH\|URL` | reads a `team.json`-shaped file/URL (see `docs/DATABRICKS.md`); Databricks only | `.halo/team.json`, then `~/.halo/team.json` |
| `--step STEP` | jumps the interactive wizard straight to one step, by its key (`team` -- `agents`/`roles` kept as aliases -- or any other step's own key) or 1-based number, skipping the Quick/Full setup choice -- interactive only (needs a real tty, `--yes` skips the wizard entirely); see [WIZARD.md](WIZARD.md) | omitted -> offers Quick/Full setup, then starts at step 1 |

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

## `halo start` (Halo 3.1.1.0)

```sh
halo start                          # the ten-minute start, one screen per step
halo start --yes                    # straight through: no Enter between steps, the plan approved
halo start --json                   # only the summary as JSON at the end (asks nothing)
halo start --lineup balanced        # copy another shipped lineup (default halo-dev-cycle)
halo start --repo ~/src/mine --file basket.py   # run in a git repo of your own
```

The guided first run: seven screens, each with one sentence of why and the
command it runs. Enter runs the step, `q` stops the start there.

1. **The lineup**: copies the shipped lineup (`--lineup`, default
   `halo-dev-cycle`) into your scope as `my-<name>` and shows its cards as a
   table with their tiers. Your active lineup stays what it was
   (`halo teams use my-<name>` makes the copy the one sessions use).
2. **The sample repo**: writes `~/.halo/start/<yyyy-mm-dd>/basket/`
   (`basket-2`, ... on a second start the same day): the Orchestra sample
   `basket.py` (five functions to write) and `test_basket.py`, `git init`
   and one commit. `--repo DIR` uses your own git repo instead; it must
   hold every `--file` (default `basket.py`).
3. **The goal**: `halo orchestra new` + `halo orchestra run --review` with
   the fixed goal "Write the five functions of basket.py" (the run pauses
   after the lead's split). The lineup preflight runs first.
4. **The plan**: the lead's plan as `halo orchestra plan` prints it, two
   sentences on layers and hand-offs, then Enter approves it, `s` opens it
   on Studio's plan canvas (`halo studio --mode orchestra` in the sample
   repo) and waits for the decision made there, `q` rejects it and stops.
5. **The run**: the lanes table (`halo orchestra lanes`), drawn again as
   lanes change, until the run ends.
6. **The report and the coach**: the report's checks (`halo orchestra
   report`) and the coach's cards (`halo orchestra coach`); `halo coach
   --apply ID` writes a card's change after a confirm, `--undo` puts it back.
7. **Where to go next**: Roles (`halo studio --mode roles`), Team (`halo team
   init`) and Fleet (`halo fleet pair`), each with its command.

Options: `--lineup NAME`, `--repo DIR`, `--file F` (repeatable, with
`--repo`), `--model REF` (the model every part uses; default your roles),
`--yes`, `--json`, `--no-studio` (step 4 does not offer the plan canvas).

It runs on the model you configured. With no provider configured it says
so and offers `halo init` (which sets one up; `halo setup` is the team
screen for later), exit 2. `HALO_START_FAKE=1` swaps every model call
for a fake lead, fake workers and a fake judge (`halo_harness/start/fake.py`),
so the whole path runs in a few seconds with no model: the tests use it.
`halo init`'s last step asks "Run the ten-minute start now?" (default No,
and No in a non-interactive run); `/start` in the TUI and Studio's Start
here overlay run the same start. Exit codes: 0 every step done, 1 a step
failed or the start was stopped, 2 usage or no provider.

When a step fails on an error it did not expect (Halo 3.2.2.0), the step
is `[failed]` with one line and the file that holds the full traceback,
and the start ends with exit 1; no traceback is printed:

```text
  TypeError: boom
  the full error is in ~/.halo/start/2026-10-25/start-error.log
[failed]

halo start stopped at repo: TypeError: boom
the full error is in ~/.halo/start/2026-10-25/start-error.log
```

The log is `~/.halo/start/<yyyy-mm-dd>/<run>-error.log` once the step 3
run exists (`start-error.log` before it); each failure is appended under a
timestamp line. A failure before the first step is one stderr line,
`halo start: <Type>: <message> -- the full error is in <path>`. `--json`
carries the line as `reason` and the path as `error_log`; the TUI panel and
Studio's Start here show both lines.

## `halo explain`

```sh
halo explain                 # every word, with its first sentence
halo explain lineup          # the word's paragraph
halo explain hand-offs       # fuzzy: plurals, hyphens, spaces, a prefix (orch), a near spelling
halo explain --json tier     # {query, word, text, closest}
```

One paragraph per word Halo uses (lineup, bio, role, tier, team, member,
block, stage, lane, part, step, mission, gate, claim, hand-off, plan,
coach, orchestra run, fleet, hub, harness, capability), from
[GLOSSARY.md](GLOSSARY.md): the same text `/explain` shows in the TUI and
Studio's Glossary lists. An unknown word names the closest ones, exit 1.

## `halo setup` / `/setup` (Halo 2.0.2 round 7)

```sh
halo setup            # the init wizard's Team step, then a short summary
halo setup team        # just the Team setup screen (Halo 2.0.5 round 2c; `halo setup roles` stays as an alias)
```

The SAME Team setup screen `halo init`'s own wizard shows (see
[WIZARD.md](WIZARD.md)), reachable
again later without re-running the whole provider flow -- "a setup
screen should pop up to set those features up in addition to doing it
within halo." On a real terminal this opens the wizard screen(s); with no
TTY it prints the current roles table instead of blocking,
and exits 0. `/setup` and `/setup team` (`/setup roles` stays as an alias)
do the same thing inside a running session (`tui/slash.py`'s
own handler pushes the screen onto the live app -- a modal stack over the
session, not a separate program): saving a lineup or a role template
there updates the LIVE session's own role table immediately, no restart
needed.
