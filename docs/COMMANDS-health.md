# Commands: doctor, audit, update and the installers

Read this when you check, audit, update or reinstall Halo.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo doctor`

A read-only environment check; every `[WARN]`/`[MISSING]` line ends with
`-> fix: <command>` or `-> see: <reference>`. Never writes anything.

```sh
halo doctor --help
```
```
usage: halo doctor [-h] [--work] [--json] [--probe-all] [--both]
                          [--tools] [--only GLOB] [--learn] [--local] [--model REF]
                          [--agents] [--teams] [--mock] [--mcp {deep}] [--apply]
                          [--from DIR] [name]

Check the health of your halo installation.

options:
  -h, --help   show this help message and exit
  --work       Run the Databricks work-box preset (VPN reachability, token
               validity, route-split/reasoning-replay probes) instead of the
               general checks
  --json       Machine-readable output: a JSON list of {id, status, message,
               fix, see}
  --probe-all  With --work: the full work matrix -- one short pong per chat-
               shaped Databricks endpoint on its chosen path
  --both       With --probe-all: also probe Claude/GLM/Kimi endpoints via the
               anthropic gateway
  --tools      With --probe-all: also check one Read tool-call per endpoint
  --only GLOB  With --probe-all: only endpoints matching this glob
  --learn      With --work --probe-all: also send one minimal probe per
               optional parameter to each endpoint and learn which ones it
               rejects (Halo 2.0.5 round 3 -- opt-in, spends real tokens/DBUs,
               prints the cost estimate first; see `halo rules`)
  --local      Run the 60-second local-model acceptance check (load, tool
               call, structured output, compaction summary) instead of the
               general checks
  --model REF  With --local: the ol:/hf:local/hf:mlx model to check (default:
               the configured default model if it is ol:, else the first
               model in the default Ollama host's catalog); an
               hf:mlx/<org>/<repo> ref starts its managed mlx_lm.server
               first if one isn't already running
  --agents     Validate every agent bio and the active team template, then
               run each bio's own acceptance check against a real model call
  --teams      Validate the active (or named) team template and exercise its
               first required pipeline gate
  name         With --teams: this team template instead of the active one
  --mock       With --agents/--teams: never call a real model (tests only)
  --mcp {deep} Run the MCP connectivity deep dive (--mcp deep [name]) instead
               of the general checks
  name         With --mcp deep: only this server (default: every currently-
               failing one)
  --apply      With --mcp deep: apply the model's proposed fix for each
               failing server (after showing it), then re-test
  --from DIR   With --mcp deep: diagnose a captured corpus directory (halo
               bugreport / halo mcp test output) instead of live servers --
               never applies anything
```

With `--json`, `--agents`, `--roles`, `--teams`, `--local` and `--work
--probe-all` print only the JSON value (no heading text ahead of it), so the
output pipes straight into `jq`.

`halo doctor --local [--model ol:x]` (round 5d; round 5f extends `--model`
to `hf:local/*`/`hf:mlx/*`) is the 60-second "works out of the box" proof
for a local model on THIS machine: load, one real Read tool call, one
structured-output call (the same constrained-decoding path the repair loop
uses), and one summary of a small fixture transcript, each printed as
`[PASS]`/`[FAIL]` with a plain reason and the elapsed time, in that fixed
order even when an earlier step failed. Exit 0 iff all four passed. An
`hf:mlx/<org>/<repo>` ref on anything but Apple Silicon fails all four
steps with the one plain "MLX runs on Apple Silicon only" reason -- still
a clean, deterministic answer, never a crash. See [MODELS.md](MODELS.md)'s
"Finding and using file-backed models"/"Apple Silicon (`hf:mlx/*`, round
5f)" sections; new local-model users are pointed at this command first.

`halo recall <query> [--k N] [--no-refresh] [--build-only] [--fleet] [--json]`
(2.0.7, the old 2.0.6 scope; `--fleet` and `--json` are 3.1.2.0 R3) is
semantic search over auto-memory topics and past sessions on a LOCAL
embedding model -- Ollama's native `/api/embed` on
the default (or named) host, or any OpenAI-compatible `/v1/embeddings`
server. The index lives at `~/.halo/index/embeddings.jsonl` and refreshes
incrementally (mtime-keyed: unchanged files are never re-embedded). Each
hit shows its similarity score, kind (memo/sess; 3.1.6.0 `lib`: an entry of
the coach's improvement library, its EXPERIENCE.md --
[ORCHESTRA.md](ORCHESTRA.md#the-library)), title and path.
DISABLED until configured: set `embeddings.model` in `~/.halo/
config.json` (e.g. `"nomic-embed-text"`, `ollama pull nomic-embed-text`
first; `embeddings.host` names a non-default Ollama host;
`embeddings.base_url`/`api_key` point at an OpenAI-compatible server
instead). `--build-only` rebuilds the index without searching; exit 0
with hits, 1 with none, 2 when unconfigured/usage. `--fleet` (3.1.2.0 R3)
asks the hub this machine runs or joined to fan the query out to every
online member, each answering from its own index; the hits are merged by
score and printed with their harness, and the exit is 3 when there is no
fleet to ask ([FLEET.md](FLEET.md) "Recall across the fleet"). `--json`
prints the hits (or the merged `{hits, harnesses}`) as JSON. The TUI twin is
`/recall [--fleet] <query>` (`docs/SLASH-COMMANDS.md`). The generic
OpenAI-compatible local-server CHAT route -- `local:<model>` or
`local:<model>@<name>` against a `local.servers` config entry (LM
Studio, llama.cpp server, vLLM; per-server `context` discovery) -- is
the same version's sibling, configured under `local.servers` in
`~/.halo/config.json`.

`halo doctor --agents [--mock]` (2.0.4 round 4) validates every agent
bio's shape (`halo_harness/agents_yaml.py`) and the ACTIVE team template
(`team` in config.json -- every agent it references must exist), then
runs each bio's own `acceptance` block against a real one-shot model
call (`halo -p <prompt> --model <ref> --max-turns 1`); `--mock` (tests
only) never calls a real model. See [AGENTS.md](AGENTS.md).

`halo preflight [--lanes A,B] [--json] [--skip-local] [--no-vision]
[--timeout S]` (2.0.7 cyber Pillar 2) is the exit-code-gated
verify-everything check a long autonomous run is worth starting under.
Local tools are verified BY EFFECT (the bytes really land on disk, the
grep really matches -- a tool that "succeeds" without the effect fails
the gate), and each provider lane gets ONE measured canary: a real
completion, one tool call the lane must actually emit and the probe must
actually run (catches lanes whose replies never carry tool calls), an
image the lane must accept when its profile claims vision (catches lying
vision flags), and a truncation check comparing the usage echo against
what was sent. Every result is recorded into the canary census
(`<state_dir>/canary-census.json`) for lane ranking. Default lanes: the
pinned default model, or `--lanes`; `--json` prints the machine-readable
report; exit 0 iff everything passed, 1 any failure, 2 a usage error.
The in-run counterpart runs automatically during long sessions: a
one-time truncation warning when a usage echo accounts for under half of
what was sent, and a periodic health note (calls, filtered, failures,
spend, context fill) every 25 model calls or 10 minutes (env-tunable via
`HALO_CANARY_EVERY_N_CALLS`/`HALO_CANARY_EVERY_S`).

`halo doctor --teams [NAME] [--mock]` (2.0.5 round 5) validates the named
(or active) team template and then exercises its FIRST `required`
pipeline gate end to end -- the same gate the live agent loop runs
between stages (`agents_doctor.check_team_gates` through
`teams_runtime.TeamControl.evaluate_stage`, the stage's own acceptance
or its bio's): one real model call unless `--mock`, exit 0 iff the gate
passed and the template resolved.

`halo doctor --mcp deep [name] [--apply] [--from DIR]` (2.0.4 round 6)
is the deep dive for a server the ordinary `/mcp`/`halo mcp fix` repair
actions couldn't fix: resolve the command/url, a real spawn+handshake
with full stdout/stderr captured, an env-var/PATH diff against your
shell, and a config-shape check -- then ONE concrete fix from a model
(config edit, missing package, wrong path, port/url, or an env var to
set), shown and applied only on `--apply` (a config-edit/path/url fix is
the only kind halo ever writes itself; a re-test follows, and a fix that
verifies healthy is remembered by its failure signature so the next
occurrence anywhere is fixed with no model call at all). No `name` ->
every currently-failing server. `--from DIR` reads a captured corpus
(`halo mcp test`/`halo bugreport` output, never the live servers) instead
-- never applies. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)'s "The
deep dive" section for the full per-step evidence and the corpus
directory layout.

Bare `halo doctor` checks: Python version, `~/.claude` layout, the env
file, OpenRouter/Databricks/Experiential configuration, `claude`/
`node`/`npx`/`rg`/Git Bash on PATH, the Chrome native-messaging host,
plugin-provided MCP servers, the OS/WSL/Kali platform hint, `~/.local/bin` on
PATH (Linux), tmux mouse mode (inside tmux), the three cached-catalog ages,
session count + `/improve` config, clipboard backend, configured MCP servers
(eager vs. lazy), the resolved default model, how many of the seven
providers are enabled (`databricks`/`openrouter`/`anthropic`/
`typesafe`/`huggingface`/`openai`/`experiential` -- see "`halo
providers`" below), and the `halo` command itself on PATH. Exit 0 unless
something is `[MISSING]` (a `[WARN]` alone, e.g. "no Databricks
configured", never fails the command).

**Install once, run anywhere.** The "command on PATH" check fails WARN when
`halo` either isn't found at all or resolves to this checkout's own
`bin/` wrapper (which only works from inside the checkout) -- its own
`-> fix:` names the exact reinstall command for whichever tool is on this
box: `uv tool install --reinstall .` (run from the checkout) when `uv` is
present, else `pip install --user -e .`. Either one needs re-running after
every `git pull` -- an editable/tool install does not auto-refresh the
installed console script on its own.

```sh
BRIDGE_TEST_HOME=/tmp/demo-home halo doctor
```
```
halo doctor
  [OK] Python 3.11.7
  [MISSING] ~/.claude directory: /tmp/demo-home/.claude -> fix: claude
  [WARN] OpenRouter: not configured (no OPENROUTER_API_KEY found) -> fix: halo init --preset home
  [WARN] Databricks: not configured (no host/token found) -> fix: halo init --preset work
  [OK] Sessions: 0 logged under ~/.halo/sessions; stats cache last written never
  [OK] /improve: enabled=True hint=True model=(small/session model) since_days=7 max_candidates=8
  [OK] MCP servers: none configured
  [OK] Default model: not set in config.json -- built-in default 'or:deepseek/deepseek-v4.1-flash' applies (HALO_MODEL/routes.json still win when set)
  [OK] Providers: 0/6 enabled (none)
  [WARN] halo command: not found on PATH -> fix: pip install --user -e . (run from this checkout -- repeat after every `git pull`)
```
(trimmed -- a real run has one line per check; see `docs/TROUBLESHOOTING.md`
for what each WARN/MISSING line means)

`doctor --work` and `doctor --work --probe-all` are Databricks-specific --
see `docs/DATABRICKS.md`.

## `halo audit`

Finds exactly the things that must never reach a public repo, before
they do: real user-profile paths, private-range and link-local IP
literals, LAN hostnames and `.local` names, known machine/vendor names,
stray `%SystemDrive%`/`%USERPROFILE%`-style cache files, key- and
token-shaped strings, e-mail addresses, and any real path under the
state dir. The rule set lives in `halo_harness/privacy_rules.py` and is
the same one `tests/test_privacy_scan.py`'s own regression guard
imports, so the two can't drift apart. See `docs/PRIVACY.md` for what
Halo never writes to the repo in the first place.

### `audit privacy [--history] [--json] [--since REV] [--cwd DIR]`

Working-tree mode (the default) scans every tracked file plus every
untracked, non-ignored file as it sits on disk right now. Each finding
prints one line, `path:line: <kind>: <masked excerpt>` -- the matched
value is always replaced with `<redacted>` before anything is printed or
serialized; exit 1 if anything was found, 0 if the tree is clean:
```sh
halo audit privacy
```
```
halo audit privacy: clean -- nothing found.
```

`--history` scans every DISTINCT blob reachable from HEAD instead (each
one exactly once, however many commits carry it unchanged), reported as
`commit:path:line: <kind>: <masked excerpt>` at the earliest commit that
introduced it, plus a summary split into paths to purge entirely (a
file that should never have been committed at all, e.g. a stray cache
file) versus paths that stay, with specific text needing replacement
(e.g. a hostname inside a doc that otherwise stays). `--since REV`
narrows the range to `REV..HEAD` instead of every commit reachable from
HEAD. `--json` gives the same fields as one JSON object instead of text
lines, for feeding a history-rewrite plan. An allowlist at `tests/
privacy_scan_allowlist.txt` (one exact, already-vetted fake value per
line) exempts deliberate fixture values from either mode.

## `halo update`

Checks the installed build (PEP 610 `direct_url.json`, or `git` in a live
checkout) against what's available upstream (cached 24h in
`~/.halo/update-check.json`), and, unless `--check`, applies it. Since
2.0.6 every release carries a checksummed artifact (the tag's own
source archive plus its `checksums.txt`, both attached to the GitHub
release), and an update to a TAG verifies the target release has that
checksums asset before installing -- a tag without one is refused as a
broken or foreign release (`--no-verify` skips the check; an unreadable
release fails open with a warning, never blocking an explicitly
requested update on a network blip). On the stable channel the target is
the newest tag, so a plain `halo update` (no `--to`) is checked and
installed at that tag; the check confirms the release carries a
`checksums.txt`. On the stable channel the report also compares an install
made FROM the release archive (`halo-harness-<version>.tar.gz`, recorded as
`archive_info` in `direct_url.json`) with its release's `checksums.txt`
(`installed archive: match` / `mismatch` / `no-hash` / `no-checksums`). A
`git+https://...` install and a checkout install keep no archive (the
installer builds a wheel from a clone), so for them there is nothing to
hash and the report prints no such line. See
"Update" in `docs/INSTALL.md` for the full walkthrough; `/update` inside
the TUI is the same check with an update-and-restart dialog.

```sh
halo update --help
```
```
usage: halo update [-h] [--check] [--to TAG_OR_BRANCH_OR_COMMIT]
                   [--channel {stable,main}] [--force] [--refresh]

Check for, or apply, a halo update.

options:
  -h, --help            show this help message and exit
  --check               Report only -- never reinstalls
  --to TAG_OR_BRANCH_OR_COMMIT
                        Pick an exact revision instead of the channel's latest
  --channel {stable,main}
                        stable tracks the newest v* tag, main tracks the
                        branch halo came from
  --force               Reinstall even if another halo process looks like it's
                        running
  --refresh             Ignore the 24h cache, always check live
```

`halo update --check` prints installed vs. available, up to 15 commits
between them, and the exact reinstall command this box would run, then
exits 0 (up to date), 10 (an update is available), or 1 (couldn't tell --
offline, no git, rate-limited). Without `--check`, it refuses (exit 1) if
another `halo` process looks like it's running on this machine (excluding
itself) unless `--force` is also given -- a reinstall under a running TUI
has broken the install on Windows before; close other sessions first, or
pass `--force` once you're sure none is actually using the install. On
success it runs the reinstall command live (output visible) and reports
the before/after commit by re-running `halo --version` as a fresh process.

```sh
halo update --check
```
```
installed: halo 2.0.2 (c93480d, master)
available (main): e1f2a3b (master)
3 commit(s):
  e1f2a3b fix: ...
  ...
to apply: halo update  (it runs: uv tool install --reinstall git+https://github.com/roloVibes/Halo-Harness)
```

The last line is what `halo update` runs for you; you never type it. A plain
`halo update` on an install that is already at the newest commit prints one
line, `halo update: already up to date -- <commit> is the newest on <channel>`,
and runs nothing.

## The installer scripts (`install-halo.sh`, `install-halo.ps1`)

`bash scripts/install-halo.sh [--ref <tag|branch|commit>] [--yes] [--no-clone] [--dry-run] [--dir=<path>]`
and `install-halo.ps1 [-Ref <tag|branch|commit>] [-Yes] [-NoClone] [-DryRun] [-CloneDir <path>]`.
Without `--ref` the scripts install the newest `vX.Y.Z` tag of the repository (found with
`git ls-remote --tags`), never a moving branch; `--ref master` tracks master on purpose. Both print the
tag and the commit they install. The clone path checks the ref out detached and installs with
`uv tool install --reinstall --constraints requirements.lock .`; `--no-clone` installs
`git+https://github.com/roloVibes/Halo-Harness@<ref>` with that ref's `requirements.lock` as the
constraints. The uv bootstrap is version-pinned. The README one-liner fetches the script from a tag URL
(`.../Halo-Harness/v2.0.10/scripts/install-halo.sh`), not from `master`. `--dry-run` prints every command
(including the `git ls-remote` that picks the tag) without running any. The final PATH step
(`uv tool update-shell`, which edits a shell startup file) is asked first, skipped by
`--no-modify-path` / `HALO_NO_MODIFY_PATH=1`, and printed rather than run under `--dry-run`.
