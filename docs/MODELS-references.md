# Models: references, picks and provider enablement

Read this when you type a model name or prefix (`or:`, `dbx:`, `ant:`, `oai:`, `ol:`, `hf:` ...), choose a model for a job, or turn a provider on or off.

Part of [Models](MODELS.md), which lists every part.

## Model reference forms

Every remote request below is paced per gateway host by the Governor
(shared across every halo process on the machine, with failover between
hosts) -- see [GOVERNOR.md](GOVERNOR.md).

| Form | Example | Resolves to |
|---|---|---|
| `or:vendor/model` | `or:deepseek/deepseek-v3.2` | OpenRouter |
| bare `vendor/model` (exactly one `/`) | `deepseek/deepseek-v3.2` | OpenRouter |
| `dbx:databricks-<name>` | `dbx:databricks-kimi-k3` | Databricks |
| `dbx:system.ai.<name>` | `dbx:system.ai.my_model` | Databricks |
| `dbx:<endpoint>@anthropic` | `dbx:databricks-kimi-k3@anthropic` | Databricks, forced onto the native Anthropic gateway for this one call |
| bare `databricks-*`/`system.ai.*` | `databricks-claude-opus-5-5` | Databricks (same as the `dbx:` form) |
| `ant:<name>` | `ant:opus`, `ant:claude-3-5-haiku` | `api.anthropic.com` pay-as-you-go (`ANTHROPIC_API_KEY`) |
| a bare Claude alias, no prefix | `opus`, `sonnet`, `fable`, `haiku` | at a Databricks work box: `dbx:<ANTHROPIC_DEFAULT_*_MODEL>`; else `ant:` if `ANTHROPIC_API_KEY` is set; else an error naming the `ant:` form |
| `ol:<model>` | `ol:qwen3:30b` | Ollama, the default host (see "Ollama" below) |
| `ol:<model>@<hostname>` | `ol:qwen3:30b@lan`, `ol:gpt-oss:20b@cloud` | Ollama, a named entry in `ollama.hosts` -- local, LAN, or Ollama Cloud |
| `hf:<org>/<model>` | `hf:Qwen/Qwen3-32B` | Hugging Face Inference Providers (the router), `:fastest` (highest throughput) implied |
| `hf:<org>/<model>:<suffix>` | `hf:openai/gpt-oss-120b:groq`, `hf:Qwen/Qwen3-32B:cheapest`, `hf:...:preferred` | same router, a specific partner provider or the `:cheapest`/`:preferred` selection mode -- the whole suffix passes through verbatim on the wire |
| `hf:endpoint/<name>` | `hf:endpoint/my-prod` | a dedicated Hugging Face Inference Endpoint, a named entry in `huggingface.endpoints` (see "Hugging Face" below) |
| `hf:local/<model>` | `hf:local/qwen3-30b` | a local OpenAI-compatible server (llama-server, vLLM, LM Studio, ...) -- a configured `huggingface.local_servers` default entry, else the first auto-detected one (see "Hugging Face" below) |
| `hf:local/<model>@<name>` | `hf:local/qwen3-30b@bench` | the same, a NAMED entry in `huggingface.local_servers` -- never an auto-detected server, which has no name of its own to address |
| `hf:mlx/<org>/<repo>` | `hf:mlx/mlx-community/Qwen2.5-7B-Instruct-4bit` | round 5f, experimental, Apple Silicon only: a Halo-managed `mlx_lm.server` for this exact Hugging Face Hub repo, started on first use and reused afterward -- see "Apple Silicon (`hf:mlx/*`, round 5f)" below and [MAC.md](MAC.md) |
| `oai:<model>` | `oai:gpt-5`, `oai:gpt-6-astra` | the real OpenAI API (`OPENAI_API_KEY`) -- chat completions, or the Responses dialect for the two models that need it -- see "OpenAI API" below |
| `xp:<slug>` | `xp:space-bunny-alpha`, `xp:nemotron-3.5-lightning` | the Experiential Labs gateway (`EXPLABS_API_KEY`) -- chat completions by default, or the Responses dialect per `experiential.dialect_overrides` -- see "Experiential Labs" below |
| `xp:claude-<slug>` | `xp:claude-haiku-4.5`, `xp:claude-opus-5` | the SAME gateway, routed through Halo's native Anthropic passthrough so thinking stays native while an Anthropic-shaped rung serves the call -- see "Experiential Labs" below |
| a `routes.json` alias | whatever `aliases` defines | resolved recursively (max 4 hops) before any of the above rules apply |

Parsing order (`model.py::parse_model_ref`): an exact match in
`routes.json`'s `aliases` is resolved first, recursively; everything after
that follows the table above, checked top to bottom. A ref that matches
nothing raises a clean `InvalidModelError` naming every accepted form (exit
2 from the CLI, with a near-miss suggestion when the catalog is cached). A
`cc:` or `cx:` ref (routes removed in 3.1.5.0), on `--model`, `/model`, a
remembered last model or a config `model:`, gets one line instead: `no
route: 'cc:sonnet' (the cc: and cx: routes were removed in 3.1.5.0; use an
API route, e.g. ant:sonnet with ANTHROPIC_API_KEY, or or:anthropic/<model>)`.

A trailing `[1m]` suffix (a long-context variant marker) passes through
unchanged on every full id/alias form.

### `ant:` alias table

Bare names the `ant:` prefix resolves (`providers/anthropic_aliases.py`
`ANT_ALIASES`); `opus` and `sonnet` are deliberately-moving
"latest" pointers (today both resolve to the `-5-5` point release) --
every other name is a specific, pinned version. `/model`, `halo
models` and the init picker show the resolved id next to each alias (e.g.
`ant:opus -> claude-opus-5-5 (latest Opus)`) for exactly this reason: `opus`
and `opus-5.5` are the same model.

| Alias | `ant:` resolves to |
|---|---|
| `fable` | `claude-fable-5-1` |
| `opus` (latest Opus) | `claude-opus-5-5` |
| `opus-5.5` | `claude-opus-5-5` |
| `opus-5` / `opus-5.0` | `claude-opus-5` |
| `opus-4.8` | `claude-opus-4-8` |
| `opus-4.6` | `claude-opus-4-6` |
| `sonnet` (latest Sonnet) | `claude-sonnet-5-5` |
| `sonnet-5.5` | `claude-sonnet-5-5` |
| `sonnet-5` | `claude-sonnet-5` |
| `haiku` | `claude-haiku-4-5-20251001` |

## Which model for what (Halo 3.0.1.0)

The catalog states what a model accepts and produces (OpenRouter's
`input_modalities` and `output_modalities`, `pricing.image_output`, the
`ant:` profiles' `vision` flag, a local model's declared capabilities).
Halo never guesses: a row that states nothing shows `?` and ranks below one
that does.

```sh
halo models --capabilities              # one line per model: in: text,image,audio  out: text
halo models --best-for visual           # reading screenshots, mockups, photos
halo models --best-for audio            # listening
halo models --best-for video            # watching clips
halo models --best-for image            # making pictures (image output)
halo models --best-for design           # iterating a design with the craft tools
```

Each ranking prints a score and a plain reason per model. `visual` weighs
vision, context and a price tier (free rows are usually small or preview
models, the mid range is where the workhorses sit); `design` additionally
requires tool calls (the craft apps are tools), weighs speed and output
length, and demotes a lane that failed `halo preflight`'s image or tool
canary. Studio's model pickers show the same facts as chips (vision, audio,
video, files, image-out) and the Design mode opens its model pick on the
`design` ranking.

### What each model is good at (Halo 3.1.9.0)

Every catalog row (`build_model_rows`, the one source `/model`, `halo models`,
Studio and the roles tables read) carries the same keys beside its price and
context, each empty (`?`) when its source does not say -- never guessed:

| Key | What | Filled from |
|---|---|---|
| `modalities_in` | what it takes in: text, image, audio, video, pdf | OpenRouter's `input_modalities` ("file" is a PDF); models.dev `modalities.input` for Databricks (the exact id, else the vendor family), OpenAI and Experiential (the family); the Anthropic table (text, image, pdf); Ollama's `/api/show` capabilities (vision, audio) |
| `modalities_out` | what it produces: text, image, audio | OpenRouter's `output_modalities` (kept by the probe since 3.1.9.0) and `pricing.image_output`; models.dev `modalities.output`; Claude and Ollama models answer in text |
| `tools` | tool calls, true or false | OpenRouter's `supported_parameters`; models.dev `tool_call`; the Experiential gateway's `supports_tools`; the Hugging Face router's picked provider; every Claude model; Ollama's `tools` capability; a judge / decision-only endpoint is false |
| `reasoning` | `{kind: none, native or openai, efforts: [...]}` | OpenRouter's `reasoning` parameter; models.dev `reasoning` and the effort values of `reasoning_options`; the gateway's `supports_reasoning` and `supported_reasoning_efforts`; `anthropic_caps` (adaptive thinking, xhigh); Ollama's `thinking` |
| `open_weights` | weights you can download | models.dev `open_weights`; every local model; false for Claude |
| `local` | runs on this machine or the LAN | `ol:`, `hf:local/*`, `hf:mlx/*` (a Hugging Face ROUTER model is remote) |
| `measured` | what THIS host measured (empty when nothing) | `gym` (`halo gym`: score, tool-call accuracy, edit success, tokens/s), `tools_probe` (the Ollama tool-call probe), `tools_rejected` (a live 400 learned in the last 24 h), `ttft_s` and `tokens_per_second` (telemetry, 3+ calls), `canary` (`halo preflight`'s census) |

From those, each model gets the kinds it is good at and one honest line:

| Kind | Good at when |
|---|---|
| `visual`, `audio`, `video`, `pdf` | it takes that input in (media distillation by kind) |
| `image` | it makes images |
| `design` | vision plus stated tool calls, scored with context, speed and price |
| `code` | stated tool calls, a capable price tier, context, reasoning and the gym's tool and edit scores (a failed tool canary halves it, a learned rejection rules it out) |
| `research` | 128k or more context (scaled to 500k) plus reasoning |
| `bulk` | cheap in and out: (3 x in + out) / 4 under about $0.40 per 1M tokens; local is free |
| `fast` | MEASURED speed only: telemetry's tokens/s and time to first token, or the gym's run |
| `local` | it runs here |

The line says what the row states and what this host measured, the gaps
after a `;`: `vision+pdf in, tools, reasoning, long context (1M), premium; no
audio`, `tools, cheap, fast; text in only`, `tools (probed), local, free, gym
0.80; text in only`, or `unknown: no catalog data`.

```sh
halo models analyze              # rebuild: one line per model, then the strongest and cheapest per kind
halo models analyze --json       # the cache itself
halo models --capabilities       # in: / out: plus the best-at line
halo models --best-for code      # rank for one kind (any of the eleven)
```

The answer is cached in `~/.halo/models/best-at.json` (`{built, sources,
rows: {ref: {kinds, line, scores, facts}}, best}`, sources by file name) and
rebuilt on the next read whenever a source cache's mtime moved --
`models.json`, `models-dev.json`, `dbx-endpoints.json`, the Experiential,
Hugging Face, OpenAI and Anthropic caches, `stats-cache.json`, the gym
results, `ollama-capabilities.json`, `canary-census.json`,
`learned-rules.json`, `config.json`, `routes.json` -- or once it is six hours
old (an Ollama host's list and the env have no file to watch). So `halo
models --refresh`, the `/model` picker's refresh and Studio's Refresh need
nothing more; `halo models analyze` and Studio's Analyze rebuild at once.

#### Measured success (Halo 3.1.8.0)

What this Halo measured about each model's agent tasks
([OUTCOMES.md](OUTCOMES.md#measured-success)): every checked task (an
Orchestra lane through the gate, a sub-agent through its acceptance) is a
row of `~/.halo/coach/outcomes.jsonl`, and the rate is first-time success
per model and task kind. From 3 checked tasks of a kind, the best-at line
appends it (`tools, cheap, fast, measured: code 4/5; text in only`), the
catalog row's `measured` carries `outcomes: {kind: {n, passed, rate}}`, the
roster's model line says `code 4/5` among what was measured, and an
outcome row that moves a shown number makes the best-at cache stale (the
numbers are one of its watched sources).

```sh
halo models --measured           # one row per model and kind: tasks, first-time passes, the rate, the mean cost
halo models --measured --json    # the same rows
```

`halo models analyze` lists the same table last (its `--json` adds
`measured`). A bio with `models.preference: measured` routes by these rates
([ROLES.md](ROLES.md#measured-a-bio-that-routes-by-what-succeeded-halo-3180)).

#### The roster

The main agent gets the roster: at most 40 lines, the strongest (and the
cheapest, when it differs) model per kind, then one line per model -- its
ref, price in/out per 1M tokens, context, inputs, tools, reasoning, the kinds
it is best at and what was measured -- the session's own model first, "+N
more" when the catalog is longer. Names only: no key, URL or path.

```
# Model roster (what each model in this Halo's catalog is good at; prices are USD per 1M tokens in/out; name one with the Agent tool's `model` when a sub-task needs it)
Per kind, the strongest (and the cheapest when it differs):
- visual: ant:fable; cheapest or:v/ears
- audio: or:v/ears
- bulk: or:v/cheap
Models:
- ant:fable  $10.00/$50.00  1M ctx  in text+image+pdf  tools  reasoning  best at pdf,research,visual,design,code
- or:v/cheap  $0.10/$0.40  128k ctx  in text  tools  no reasoning  best at bulk
```

It rides as a user-role snapshot (kind `roster`) at a new session, after
`/clear` and after a compaction, in the main session only; the system prompt
stays byte-stable (no model list in it), and the Agent tool's description
adds "the roster in your context says what each model is good at; name a
model with `model` when a sub-task needs one". A session start never waits on
a catalog: it reads the cache as it is, and a stale one is rebuilt behind it
for the next session. `models.roster: false` in config.json (or
`HALO_MODELS_ROSTER=0`) leaves it out ([CONFIG.md](CONFIG.md)).

### Media models (Halo 3.0.4.0)

Diffusion checkpoints, video models, upscalers, TTS voices and their LoRAs,
VAEs and encoders are a different kind of asset from the models above, so
they have their own inventory, keyed by what a model PRODUCES. They come from
a ComfyUI server (see [COMFYUI.md](COMFYUI.md) "Inventory") and never appear in
`/model` or the roles tables: a `comfy:` ref is not an LLM.

```sh
halo models --media                   # image-gen, video-gen, upscale, tts + the supporting rows
halo models --media video             # only video-gen and the loras, vaes and encoders of those families
halo models --media --refresh         # rescan the server (COMFY_URL or comfy.url)
halo models --best-for image-gen      # also: video-gen | audio-gen | upscale
halo models --best-for video-gen      # the Wan rows, best first, one reason each
```

What is ranked: the generators (`image-gen`, `video-gen`, `upscale`, `tts`
shown as `audio-gen`). A row scores its file size (a larger file is more
parameters), its quantization (bf16, then fp16, fp8, int8) and a small bonus
when a 4-step distill LoRA for the same family, mode (i2v, t2v, s2v) and noise
expert is installed, shown as the `4-step` chip. What is only listed: LoRAs,
VAEs, text, vision and audio encoders and everything else (`other`, such as a
segmentation model); they are the parts a workflow loads next to a generator,
never a choice of their own. Studio's Design chooser shows the generators as a
second group, "Media models (ComfyUI)"; picking one adds a
`(comfy_model: <file>)` hint to that turn's prompt and leaves the LLM as is.

## Provider enablement

A provider's models reach `/model`/`halo models`/the `init` default
pick/`doctor` once it is **enabled** -- and (H15 part 2 addendum) that
happens AUTOMATICALLY, straight from real credentials, no `init`/`providers
enable` step required: OpenRouter/Anthropic API (key)/TypeSafe auto-enable
once their key is found (env file, shell env, or the settings env chain);
Databricks once a host AND token are found (same sources, plus
`~/.databrickscfg`); Hugging Face (Halo 2.0.3
round 4, extended round 5) once `HF_TOKEN` is found, OR at least one
`huggingface.endpoints` entry is configured, OR at least one `huggingface.
local_servers` entry is configured -- any ONE of the three sources alone
is enough; an auto-DETECTED local server (no config entry at all) is
never checked here (that needs a live network probe, out of scope for
this config/env-only check) -- see `/local`/`halo local` for that;
OpenAI API (key), Experiential Labs, and TypeSafe each follow the same
single-key auto-enable rule as OpenRouter/Anthropic above (`OPENAI_API_
KEY`/`EXPLABS_API_KEY`/`TYPESAFE_API_KEY` respectively).
`~/.halo/config.json`'s
`"providers"` block stores OVERRIDES only: `halo providers enable/
disable <name>` (or `/providers enable/disable <name>`, or completing a
tab in `halo init`) writes an explicit `true`/`false` there that
always wins over auto-detection -- `enabled: false` hides an auto-enabled
provider, `enabled: true` forces one on with no credentials at all. The
prefix table (also used by the `/model` picker's group headers, `init`'s
own tabs, `halo providers`/`/providers`, and `doctor`):

| Prefix | Label | Provider name (`halo providers`) |
|---|---|---|
| `dbx:` | Databricks | `databricks` |
| `or:` | OpenRouter | `openrouter` |
| `ant:` | Anthropic API (key) | `anthropic` |
| `hf:` | Hugging Face | `huggingface` |
| `oai:` | OpenAI API (key) | `openai` |
| `xp:` | Experiential Labs | `experiential` |
| *(none yet)* | TypeSafe | `typesafe` -- stores `TYPESAFE_API_KEY` only, for a later feature |

Ollama (`ol:`) is deliberately NOT in this table -- see "Ollama" below,
which covers its own multi-host reachability model instead of a single
on/off flag.

A hand-typed ref whose provider is explicitly disabled is refused with a
one-line message naming the `halo providers enable <name>` fix. A provider that's detected (real
credentials/login) but explicitly disabled shows one dim hint line in
`/model` instead of a selectable row. `halo providers`/`/providers`
shows each provider's status as one of `auto (detected from <source>)`,
`disabled by you`, `enabled by you`, or `not set up`, plus reachable/cached
model count.
