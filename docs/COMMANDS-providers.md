# Commands: providers, rate limits and models

Read this when you set up providers, read balances and rules, or refresh the model list.

Part of [Commands](COMMANDS.md), which lists every part.

## `halo providers`

```
Usage: halo providers [list|enable <name>|disable <name>|setup <name>]
Providers: databricks, openrouter, anthropic, typesafe, huggingface, openai, experiential
```

Detected credentials AUTO-enable a provider (H15 part 2 addendum) --
OpenRouter/Anthropic API (key)/TypeSafe/OpenAI API once their key is
found (env file, shell env, or the settings env chain), Databricks once a
host AND token are found (same sources, plus `~/.databrickscfg`), Hugging
Face (Halo 2.0.3 round 4) once `HF_TOKEN` is found OR at least one
`huggingface.endpoints` entry is configured. No `halo init` run
is required for this. `~/.halo/config.json`'s `"providers"` block
stores OVERRIDES only -- `enable <name>`/`disable <name>` write an explicit
`true`/`false` there that always wins over auto-detection (`ant`/`dbx`/
`or`/`hf`/`oai`/`xp` are accepted aliases for the canonical names);
`setup <name>` needs a real terminal and runs the same per-provider tab `halo init`
shows. For `openai`, `huggingface` and `experiential` (which `halo init
--provider` does not take) it opens the init wizard on a terminal, and
otherwise says what to set (`OPENAI_API_KEY`, `HF_TOKEN` or
`EXPLABS_API_KEY`) before `halo providers enable <name>`.

Bare `halo providers` (or `list`) prints one row per provider --
status (`auto (detected from <source>)` / `disabled by you` / `enabled by
you` / `not set up`), reachable, cached model count -- plus a trailing
OpenRouter balance line once a background fetch has ever succeeded (see
`halo models`/`/cost`), and (round 5i part 1) a plain note once OpenAI
API is enabled: it has no public balance endpoint for ordinary keys, so
this prints a pointer at `/cost` here (the standalone CLI has no live
session to read a number from) or, from `/providers` inside a running
session on an `oai:` model, that session's own computed spend. See
`docs/MODELS.md`'s "Provider enablement" section for the full prefix/
label table.

```sh
halo providers
```
```
provider                    status                                   reachable                                  models
Databricks                  not set up                               not set up                                      -
OpenRouter                  auto (detected from env file / shell env) reachable                                     412
Anthropic API (key)         not set up                                not set up                                      -
TypeSafe                    not set up                                not set up                                      -
```

## `halo gov`

```
Usage: halo gov [host] [--json]
```

Halo 2.0.5 round 4: the Governor's gateway buckets -- rate vs ceiling,
in-flight, waiting, cooldown per gateway host -- and, given a host
argument, that host's recent calls (agent, role, status). Read-only.
The TUI's `/gov [host]` prints the same table. See
[GOVERNOR.md](GOVERNOR.md).

## `halo balances`

```
Usage: halo balances [--refresh]
```

Halo 2.0.4 round 3 (deliverable 2): one shared balances surface --
OpenRouter (`GET /key`/`/credits`), Experiential Labs (`GET /credits`),
Databricks (always "not offered" -- DBU billing is on the workspace
side, explicitly excluded by the owner), Anthropic (no endpoint for a
plain key; the organisation cost report when `ANTHROPIC_ADMIN_KEY` is
set). Every other provider (Hugging Face, OpenAI, TypeSafe) reads
"not offered" -- no balance concept
exists for it at all. Bare `halo balances` never touches the network --
reads `~/.halo/balances.json`, or "not fetched yet"; `--refresh` does
the one bounded round of fetches and persists the result there. `/balances`
(TUI and headless) is the same surface, backed by the SAME `providers.
balances` module, so the two never disagree; the status bar's own
balance chip (right after cost) and `halo doctor` read the same cache.

```sh
halo balances
```
```
Databricks (dbx:): not offered (DBU billing is on the workspace side -- not available as a balance here)
OpenRouter (or:): $12.40 left (key: my-key, as of 14:32:05)
Anthropic API (key) (ant:): not offered (balance not exposed by this API for a plain key (set ANTHROPIC_ADMIN_KEY for organisation spend))
TypeSafe: not offered (no balance concept for this provider)
Hugging Face (hf:): not offered (no balance concept for this provider)
OpenAI API (key) (oai:): not offered (no balance concept for this provider)
Experiential Labs (xp:): $5.00 left (of $10.00 total credits)
```

## `halo rules`

```
Usage: halo rules [--forget <provider:model>]
```

Halo 2.0.5 round 3 (G1): lists every learned PARAMETER-rejection rule
`providers.learned_params` has recorded -- one line per (endpoint, field),
with the action taken (`drop`/`clamp` + its value) and the rule's age.
These are learned the first time a live 400/422 proves a specific
endpoint rejects a request field this harness itself sent (`reasoning_
effort`, `temperature`, `top_p`, `tool_choice`, `max_tokens`,
`max_completion_tokens`, `thinking`, `output_config`, `response_format`,
`parallel_tool_calls`, `strict`, `store`, `stream_options`, `metadata`,
`stop`): the smallest fix is applied and the request retried ONCE, and --
only once that retry is confirmed to have worked -- the fix is remembered
for every later request against that same endpoint. A `model_table.json`
row's own explicit value always wins over a learned rule. Rules older
than 30 days are tried once WITHOUT the fix before being relearned (a
since-fixed/transient rejection self-heals with no action needed).

`--forget <provider:model>` clears every learned parameter rule for that
ONE endpoint (never its other learned facts -- `tools_rejected`/
`reasoning_effort_with_tools` have their own forget surface, `halo mcp
learned --forget`); `halo models --forget-rules` is the blunt, every-
endpoint reset. `/rules` (TUI and headless) renders the SAME listing.
Bare `halo rules` never touches the network -- it only reads `~/.halo/
learned-rules.json`.

```sh
halo rules
```
```
databricks:databricks-glm-5-3         stream_options          drop             2d
databricks:databricks-gpt-5-6-sol     reasoning_effort         clamp -> 'none'  11d
```

`halo doctor --work --probe-all --learn` pre-learns these rules by
sending one minimal request per optional parameter to each configured
Databricks endpoint, instead of waiting for a real turn to discover them
one at a time -- opt-in, prints the cost estimate before sending
anything, never runs without `--learn`.

## `halo work-matrix`

V2b: turns a `doctor --work --probe-all` JSON report (`~/.halo/
work-matrix-<date>.json`, or one copied off the owner's real work VM -- the
report holds endpoint names only, never a host or a token) into a suggested
action per failure. See `docs/DATABRICKS.md`'s own work-matrix section for
exactly which failure classes map to which suggestion.

```sh
halo work-matrix --help
```
```
usage: halo work-matrix [-h] {show,apply} ...

Interpret a `doctor --work --probe-all` JSON report.

positional arguments:
  {show,apply}
    show        Render the report as a table with a suggested action per
                failure
    apply       Write the report's suggested per-endpoint overrides into
                config.json

options:
  -h, --help    show this help message and exit
```

### `work-matrix show <report.json>`
Prints one line per FAILING endpoint (a clean row across the board prints
"nothing to fix"): the endpoint name, its HTTP status, the issue, and the
suggested action. Never writes anything.
```sh
halo work-matrix show ~/.halo/work-matrix-2026-09-29.json
```

### `work-matrix apply <report.json> [--yes]`
Recomputes the SAME classification and writes only the one failure class that
maps onto a real config.json knob (`databricks.gateway.<endpoint>: anthropic`,
for an endpoint whose default dialect was rejected with a 400/404/415/422 while a
`--both`-probed anthropic-gateway companion row answered 200; a 429, a 5xx or a
probe that raised is reported as "retry the probe" and never written) -- lists every override it's about to
write and asks for confirmation first; `--yes` skips the prompt (for
scripting/CI). The other three failure classes (403/IP, a family-wide
tool-call rule, a reasoning-replay rule) have no per-endpoint config.json
knob to write at all -- `show` reports them; fixing them is a code/model-table
change, not a config write. Never touches `~/.claude.json`/`~/.claude/
settings.json`.
```sh
halo work-matrix apply ~/.halo/work-matrix-2026-09-29.json --yes
```

## `halo models`

Lists (and refreshes) the OpenRouter and Databricks model catalogs.

```sh
halo models --help
```
```
usage: halo models [-h] [--refresh] [--ant] [--urls] [--json] [--forget-rules]
                   [--capabilities] [--best-for KIND]
                   [--media [{image,video,audio,all}]] [--measured]

options:
  -h, --help            show this help message and exit
  --refresh             Re-probe OpenRouter/Databricks instead of using the
                        cache
  --ant                 List the real, reachable Anthropic API models (ant:
                        aliases plus every other id the key can see) instead
                        of the OpenRouter/Databricks catalog; with --refresh,
                        re-fetches GET /v1/models
  --urls                Databricks endpoints: also print the exact URL and
                        path type each one resolves to
  --json                Machine-readable JSON output
  --forget-rules        Also clear every learned parameter-rejection rule for
                        every endpoint
  --capabilities        One line per model: what it accepts (text, image,
                        audio, video, pdf), what it outputs and what it is
                        best at
  --best-for KIND       Rank models for one job: visual | audio | video |
                        image | design | pdf | code | research | bulk | fast |
                        local (with a reason each); image-gen | video-gen |
                        audio-gen | upscale rank the ComfyUI media models
  --media [{image,video,audio,all}]
                        List the ComfyUI media models (diffusion, video,
                        upscale, TTS and their LoRAs, VAEs, encoders) by what
                        they produce; with --refresh, rescans the server
  --measured            Measured success per model and task kind here: checked
                        tasks, first-time passes, the rate and the mean cost
                        (outcomes.jsonl)
```

Halo 3.0.1.0: `--capabilities` adds what each model takes in (text, image,
audio, video, files) and puts out (image), read from the catalogs, never
guessed; `--best-for visual|audio|video|image|design` ranks the catalog for
that job with a one-line reason per model (vision, context, tools, price,
speed). Halo Design's model pick opens on the `design` ranking. See
[MODELS.md](MODELS.md) "Which model for what". Halo 3.1.9.0: each
`--capabilities` line ends with what the model is best at (`vision+pdf in,
tools, reasoning; no audio`), and `--best-for` also takes `pdf`, `code`,
`research`, `bulk`, `fast` and `local`, scored with tool calls, reasoning,
open weights and what this host measured (the gym, the tool-call probe, a
learned tools rejection, telemetry's speed, the preflight canary census).
Halo 3.1.8.0: `--measured` prints what this Halo measured about each model's agent tasks: one row
per model and task kind with the checked tasks, the first-time passes, the rate and the mean cost
(`--json` for the rows); see [OUTCOMES.md](OUTCOMES.md#measured-success). Halo 3.1.9.0 R3: a row
whose model is dropped for the kind ends with "dropped for code (1/4 in the last 30 days)" (`--json`:
`dropped`); `halo outcomes learned` shows the weights ([ROLES.md](ROLES.md#auto-learns-halo-3190)).

| Flag | Reads/writes |
|---|---|
| (bare) | reads `~/.halo/models.json`/`dbx-endpoints.json`; refreshes automatically the first time either cache is empty |
| `--refresh` | live probe: OpenRouter `GET /api/v1/models` -> `models.json`; Databricks `GET /api/2.0/serving-endpoints` -> `dbx-endpoints.json`; models.dev's public `api.json` -> `models-dev.json` |
| `--ant` | reads `~/.halo/ant-models.json` (real ids `GET /v1/models` returned for this key); `--ant --refresh` re-fetches it -- the `ant:` aliases show first with their `-> <resolved-id>` detail, then any OTHER id the key can reach, with no alias of its own |
| `--urls` | Databricks rows only: adds the exact resolved URL + path type (`mlflow`/`cursor`/`anthropic`/`invocations`) per endpoint -- see `docs/DATABRICKS.md` |
| `--json` | same data as machine-readable JSON |
| `--measured` | Halo 3.1.8.0: reads `~/.halo/coach/outcomes.jsonl` (the checked agent tasks per model and kind); with `--json` the rows |
| `--media [image\|video\|audio\|all]` | Halo 3.0.4.0: the ComfyUI media-model inventory (image-gen, video-gen, upscale, tts, then the supporting loras, vaes and encoders) with size, quant and family; reads `~/.halo/media-models.json`, `--media --refresh` rescans the server (`COMFY_URL` / `comfy.url`: `GET /models/<folder>`, `GET /experiment/models/<folder>`, `GET /object_info`) |
| `--best-for image-gen\|video-gen\|audio-gen\|upscale` | ranks the media inventory by size, quant (bf16 > fp16 > fp8 > int8) and a matching 4-step LoRA, one reason per row; the five LLM kinds above keep their own ranking |

```sh
BRIDGE_TEST_HOME=/tmp/demo-home halo models --ant
```
```
Anthropic API: not configured (no ANTHROPIC_API_KEY found) -- ant: models unavailable
(0 live id(s) known, never cached -- `halo models --ant --refresh` updates it)

alias        ant: target                       context   out cap      in/M     out/M
fable        -> claude-fable-5-1               1000000    128000  $10.00/M  $50.00/M
opus         -> claude-opus-5-5 (latest Opus)    1000000    128000   $4.00/M  $20.00/M
...
```

An unresolvable `--model` elsewhere in the CLI prints a near-miss suggestion
sourced from whatever this command last cached (`difflib`-style, cutoff
0.5) -- keeping the cache fresh with `halo models --refresh` makes
that suggestion useful.

### `halo models analyze` (Halo 3.1.9.0)

```sh
halo models analyze [--json]   rebuild what each model is good at, print one line per model and the picks per kind
```

Rebuilds the best-at cache (`~/.halo/models/best-at.json`) from the cached
catalogs the way `halo models` lists them (no network: `--refresh` pulls the
lists), then prints one line per model -- its ref, the kinds it is good at
(visual, audio, video, image, design, pdf, code, research, bulk, fast,
local) and its one honest line -- and, per kind, the strongest model and the
cheapest when it differs. `--json` prints the cache: `built`, `sources` (by
file name), `rows` (`{ref: {kinds, line, scores, facts}}`) and `best`
(`{kind: {cheapest, strongest}}`). An empty catalog exits 1 with the
`halo models --refresh` hint. Studio's Models panel has the same button
(Analyze, `POST /api/models/analyze`). See [MODELS-references.md](MODELS-references.md#what-each-model-is-good-at-halo-3190).
Halo 3.1.8.0: the text ends with the `--measured` table when something was
measured, and `--json` adds `measured` (its rows). Halo 3.1.9.0 R3: a model
dropped for a task kind ends its line with " -- dropped for <kind> (...)", and
its table rows (and `--json`'s `measured` rows, `dropped`) carry the mark.

### `halo models test <ref>` (Halo 3.0.7.0)

```sh
halo models test <ref> [--json] [--timeout S]   one-token probe: ok and the latency, or the error; exit 1 on failure
```

Sends "Reply with the single word ok" to `<ref>` through the same one-shot
print-mode call a bio's "Try it" uses (`halo -p ... --model <ref>
--max-turns 1`), waits up to 20 s, and prints one line: `<ref>: ok in 812 ms
('ok') -- ~$0.0011 estimated ...` or `<ref>: failed after 20000 ms: no reply
within 20 s -- ...` (the cost part is the smoke estimate from the catalog's
prices). `--json` prints `{ok, latency_ms, error, cost_line, ref, reply}`,
the same body Studio's `POST /api/models/test {ref}` answers. The TUI lineup
editor's `t` key runs it on the focused assignment's model.
