# Models: references, picks and provider enablement

Read this when you type a model name or prefix (`or:`, `dbx:`, `cc:`, `cx:`, `ol:`, `hf:` ...), choose a model for a job, or turn a provider on or off.

Part of [Models](MODELS.md), which lists every part.

## Model reference forms

Every remote request below is paced per gateway host by the Governor
(shared across every halo process on the machine, with failover between
hosts) -- see [GOVERNOR.md](GOVERNOR.md). `cc:`/`cx:` drive a CLI child,
not HTTP, so they are not governed.

| Form | Example | Resolves to |
|---|---|---|
| `or:vendor/model` | `or:deepseek/deepseek-v3.2` | OpenRouter |
| bare `vendor/model` (exactly one `/`) | `deepseek/deepseek-v3.2` | OpenRouter |
| `dbx:databricks-<name>` | `dbx:databricks-kimi-k3` | Databricks |
| `dbx:system.ai.<name>` | `dbx:system.ai.my_model` | Databricks |
| `dbx:<endpoint>@anthropic` | `dbx:databricks-kimi-k3@anthropic` | Databricks, forced onto the native Anthropic gateway for this one call |
| bare `databricks-*`/`system.ai.*` | `databricks-claude-opus-5-5` | Databricks (same as the `dbx:` form) |
| `cc:<name>` | `cc:opus`, `cc:sonnet` | your Claude subscription, via the installed `claude` binary |
| `ant:<name>` | `ant:opus`, `ant:claude-3-5-haiku` | `api.anthropic.com` pay-as-you-go (`ANTHROPIC_API_KEY`) |
| a bare subscription alias, no prefix | `opus`, `sonnet`, `fable`, `haiku` | at a Databricks work box: `dbx:<ANTHROPIC_DEFAULT_*_MODEL>`; else `cc:` if logged in and no key is set; else `ant:` if a key is set; else an error naming both |
| `ol:<model>` | `ol:qwen3:30b` | Ollama, the default host (see "Ollama" below) |
| `ol:<model>@<hostname>` | `ol:qwen3:30b@lan`, `ol:gpt-oss:20b@cloud` | Ollama, a named entry in `ollama.hosts` -- local, LAN, or Ollama Cloud |
| `hf:<org>/<model>` | `hf:Qwen/Qwen3-32B` | Hugging Face Inference Providers (the router), `:fastest` (highest throughput) implied |
| `hf:<org>/<model>:<suffix>` | `hf:openai/gpt-oss-120b:groq`, `hf:Qwen/Qwen3-32B:cheapest`, `hf:...:preferred` | same router, a specific partner provider or the `:cheapest`/`:preferred` selection mode -- the whole suffix passes through verbatim on the wire |
| `hf:endpoint/<name>` | `hf:endpoint/my-prod` | a dedicated Hugging Face Inference Endpoint, a named entry in `huggingface.endpoints` (see "Hugging Face" below) |
| `hf:local/<model>` | `hf:local/qwen3-30b` | a local OpenAI-compatible server (llama-server, vLLM, LM Studio, ...) -- a configured `huggingface.local_servers` default entry, else the first auto-detected one (see "Hugging Face" below) |
| `hf:local/<model>@<name>` | `hf:local/qwen3-30b@bench` | the same, a NAMED entry in `huggingface.local_servers` -- never an auto-detected server, which has no name of its own to address |
| `hf:mlx/<org>/<repo>` | `hf:mlx/mlx-community/Qwen2.5-7B-Instruct-4bit` | round 5f, experimental, Apple Silicon only: a Halo-managed `mlx_lm.server` for this exact Hugging Face Hub repo, started on first use and reused afterward -- see "Apple Silicon (`hf:mlx/*`, round 5f)" below and [MAC.md](MAC.md) |
| `oai:<model>` | `oai:gpt-5`, `oai:gpt-6-astra` | the real OpenAI API (`OPENAI_API_KEY`) -- chat completions, or the Responses dialect for the two models that need it -- see "OpenAI API" below |
| `cx:<model>` | `cx:astra`, `cx:gpt-6.1-sol` | your Codex ChatGPT subscription, via the installed `codex` binary -- see "Codex subscription (ChatGPT)" below |
| `xp:<slug>` | `xp:space-bunny-alpha`, `xp:nemotron-3.5-lightning` | the Experiential Labs gateway (`EXPLABS_API_KEY`) -- chat completions by default, or the Responses dialect per `experiential.dialect_overrides` -- see "Experiential Labs" below |
| `xp:claude-<slug>` | `xp:claude-haiku-4.5`, `xp:claude-opus-5` | the SAME gateway, routed through Halo's native Anthropic passthrough so thinking stays native while an Anthropic-shaped rung serves the call -- see "Experiential Labs" below |
| a `routes.json` alias | whatever `aliases` defines | resolved recursively (max 4 hops) before any of the above rules apply |

Parsing order (`model.py::parse_model_ref`): an exact match in
`routes.json`'s `aliases` is resolved first, recursively; everything after
that follows the table above, checked top to bottom. A ref that matches
nothing raises a clean `InvalidModelError` naming every accepted form (exit
2 from the CLI, with a near-miss suggestion when the catalog is cached).

A trailing `[1m]` suffix (a long-context variant marker) passes through
unchanged on every full id/alias form.

### `cc:`/`ant:` alias table

The same bare names resolve for both prefixes (`providers/cc_models.py`
`CC_ALIASES`/`ANT_ALIASES`); `opus` and `sonnet` are deliberately-moving
"latest" pointers (today both resolve to the `-5-5` point release) --
every other name is a specific, pinned version. `/model`, `halo
models` and the init picker show the resolved id next to each alias (e.g.
`cc:opus -> claude-opus-5-5 (latest Opus)`) for exactly this reason: `opus`
and `opus-5.5` are the same model.

| Alias | `cc:` resolves to | `ant:` resolves to |
|---|---|---|
| `fable` | `claude-fable-5-1` | `claude-fable-5-1` |
| `opus` (latest Opus) | `claude-opus-5-5` | `claude-opus-5-5` |
| `opus-5.5` | `claude-opus-5-5` | `claude-opus-5-5` |
| `opus-5` / `opus-5.0` | `claude-opus-5` | `claude-opus-5` |
| `opus-4.8` | `claude-opus-4-8` | `claude-opus-4-8` |
| `opus-4.6` | `claude-opus-4-6` | `claude-opus-4-6` |
| `sonnet` (latest Sonnet) | Claude Code's own `sonnet` pointer (today `claude-sonnet-5-5`) | `claude-sonnet-5-5` |
| `sonnet-5.5` | `claude-sonnet-5-5` | `claude-sonnet-5-5` |
| `sonnet-5` | `claude-sonnet-5` | `claude-sonnet-5` |
| `haiku` | Claude Code's own `haiku` pointer (today `claude-haiku-4-5-20251001`) | `claude-haiku-4-5-20251001` |

`halo models --cc --refresh` re-pings each alias (a cheap `-p
--max-turns 1` call) and caches the REAL id it got back to
`~/.halo/cc-models.json`, consulted before this static table for
`sonnet`/`haiku` specifically (the two whose target moves as Anthropic
ships new point releases) -- so a stale hardcoded id here is never the
only source once a refresh has run.

### `cx:` alias table

Short names Halo adds on top of the documented ChatGPT-plan ids
(`providers/codex_models.py` `CODEX_ALIASES`) -- every one is a specific,
pinned id; none of them move the way `cc:opus`/`cc:sonnet` do.

| Alias | `cx:` resolves to |
|---|---|
| `astra` | `gpt-6-astra` |
| `sol` | `gpt-6.1-sol` |
| `luna` | `gpt-6-luna` |

The full id also works directly (`cx:gpt-6-astra`). No live `/models
refresh` has run against this table (no ChatGPT login on the build host) --
`halo models --cx --refresh` is implemented the same way `--cc --refresh`
is (a cheap one-token headless call per id, refused ones marked) but
unexercised; see `docs/harness/CODEX-RESEARCH.md` section 2.

## Which model for what (Halo 3.0.1.0)

The catalog states what a model accepts and produces (OpenRouter's
`input_modalities` and `output_modalities`, `pricing.image_output`, the
subscription profiles' `vision` flag, a local model's declared capabilities).
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

### Media models (Halo 3.0.4.0)

Diffusion checkpoints, video models, upscalers, TTS voices and their LoRAs,
VAEs and encoders are a different kind of asset from the models above, so
they have their own inventory, keyed by what a model PRODUCES. They come from
a ComfyUI server (see [COMFYUI.md](COMFYUI.md) "Inventory") and never appear in
`/model`, the roles or the org tables: a `comfy:` ref is not an LLM.

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

### Subscription-routes consent (Halo 2.0.7 round 7b)

The owner's own decision: "if Halo discovers subscription creds that
might lead to a ban, that feature should be off by default and then a big
alert and acceptance needs to happen before that even turns on." `cc:` and
`cx:` are therefore gated by a SEPARATE consent step, ahead of (and
independent from) the ordinary provider-enablement table below -- a
detected, logged-in `claude`/`codex` subscription still never offers its
route until this is accepted. This is a user choice the owner built in,
never safety/refusal logic: the words used everywhere are "accepted" /
"not accepted" / "available after acceptance".

Halo 3.0.2.0 closes the one door that stayed open: the shipped agent bios
(orchestrator, implementer, reviewer, researcher, verifier, watchdog,
release-manager) and the `halo-dev-cycle` lineup's escalation target
named `cc:` models by preference, so Roles mode in Studio and the wizard's
lineup preview showed a subscription model as the default pick even
before acceptance (the role table itself fell through to the default
model, with a note). They now name the same models over OpenRouter
(`or:anthropic/claude-sonnet-5`, `or:anthropic/claude-opus-5.5`,
`or:anthropic/claude-fable-5.1`, `or:anthropic/claude-haiku-4.5`).
`tests/test_subscription_defaults.py` keeps every shipped template, the
catalog, the Studio model list and the resolved shipped bios free of
`cc:`/`cx:` while the gate is off.

**Bios and lineups never run on a subscription route, accepted or not**
(3.0.2.0, the owner: "it shouldn't occur regardless so people don't get
banned"). `halo_harness/subscription_scrub.py` rewrites every `cc:`/`cx:`
ref in the user and project `agents/` and `teams/` folders to its
OpenRouter equivalent (`cc:claude-opus-5-5` -> `or:anthropic/claude-opus-5.5`,
`cc:opus` -> the family's current row, `cx:gpt-5` -> `or:openai/gpt-5`)
the first time lineups are listed in a process, and `halo subscriptions
scrub` does it by hand and prints what moved. The resolvers do the same
at resolve time for anything written afterwards: `resolve_agent_bio` maps
a bio's preference/fallback/escalation, `resolve_role_table` maps a
lineup's pick with a note, and a ref with no equivalent falls through to
the default model. Acceptance still governs the session model you pick by
hand (`/model cc:...`); it never reaches a bio or a lineup.

A fresh install, and an upgraded install that never saw this round before,
both start at **not accepted** -- no migration ever flips it on.
Until accepted: the `/model` picker and `halo models` show `cc:`/`cx:`
rows as a dim hint ("... detected -- available after acceptance") instead
of selectable models; a hand-typed `--model cc:...`/`--model cx:...` (or
the bare subscription alias, `opus`/`sonnet`/..., when it would otherwise
route to `cc:`) is refused with the same wording; a lineup/bio that names
a `cc:`/`cx:` model resolves to the default model instead, with a plain
one-line note; `halo doctor` and `/providers`/`halo providers` print one
line, `subscription routes: off (not accepted)` or `... on (accepted
<date>, v<version>)`; the `init` wizard's Providers step shows the same
line on the `claude`/`codex` tabs with a button that opens the real
notice.

**The notice** ("Your subscription, a third-party harness", the TUI
screen and `halo subscriptions accept`'s plain-text form use the exact
same words): Halo never reads the Claude Code OAuth token
(`~/.claude/.credentials.json`) or Codex's own stored credentials; `cc:`
drives the official `claude` binary in its documented headless mode,
`cx:` the official `codex` binary the same way; both still use the
user's own personal subscription, through a third-party harness that is
not the provider's own product; the provider's own terms govern the
account, not Halo's; there have been public reports of account
restrictions for tools that use subscription tokens outside the
provider's own products, with no claim made about any individual case.
Both providers' terms are named by title with their URL (the Anthropic
Consumer Terms of Service and the OpenAI Terms of Use), followed by the
sentence that the account -- and what happens to it -- is the user's own
responsibility. Acceptance: typing `I accept` (exact) and Enter; Escape
or anything else leaves the routes off.

Acceptance is per machine, stored in `~/.halo/config.json`'s
`subscription_routes` key (`{accepted, accepted_at, accepted_version,
routes: ["cc", "cx"]}`) with the date and the notice's own `NOTICE_VERSION`
(`halo_harness/subscription_consent.py`) -- a later Halo version whose
notice text actually changed bumps that constant, which asks again even
on a machine that already accepted an older version. `halo subscriptions
status|accept|revoke` and the TUI's `/subscriptions` are the two
surfaces; see `docs/COMMANDS.md`/`docs/SLASH-COMMANDS.md`.

## Provider enablement

A provider's models reach `/model`/`halo models`/the `init` default
pick/`doctor` once it is **enabled** -- and (H15 part 2 addendum) that
happens AUTOMATICALLY, straight from real credentials, no `init`/`providers
enable` step required: OpenRouter/Anthropic API (key)/TypeSafe auto-enable
once their key is found (env file, shell env, or the settings env chain);
Databricks once a host AND token are found (same sources, plus
`~/.databrickscfg`); Claude Code subscription (`cc:`) ONLY when `claude
auth status` reports `loggedIn` with `authMethod` exactly `claude.ai` -- a
`claude` driven by an API token or a custom base URL (a work box's own
settings-driven login) never auto-enables it; Hugging Face (Halo 2.0.3
round 4, extended round 5) once `HF_TOKEN` is found, OR at least one
`huggingface.endpoints` entry is configured, OR at least one `huggingface.
local_servers` entry is configured -- any ONE of the three sources alone
is enough; an auto-DETECTED local server (no config entry at all) is
never checked here (that needs a live network probe, out of scope for
this config/env-only check) -- see `/local`/`halo local` for that;
OpenAI API (key), Experiential Labs, and TypeSafe each follow the same
single-key auto-enable rule as OpenRouter/Anthropic above (`OPENAI_API_
KEY`/`EXPLABS_API_KEY`/`TYPESAFE_API_KEY` respectively); Codex
subscription (`cx:`) follows the SAME `claude auth status`-shaped rule as
`cc:` above, substituting `codex login status`/`authMethod: "chatgpt"`.
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
| `cc:` | Claude Code subscription | `claude_subscription` |
| `hf:` | Hugging Face | `huggingface` |
| `oai:` | OpenAI API (key) | `openai` |
| `cx:` | Codex subscription (ChatGPT) | `codex_subscription` |
| `xp:` | Experiential Labs | `experiential` |
| *(none yet)* | TypeSafe | `typesafe` -- stores `TYPESAFE_API_KEY` only, for a later feature |

Ollama (`ol:`) is deliberately NOT in this table -- see "Ollama" below,
which covers its own multi-host reachability model instead of a single
on/off flag.

A hand-typed ref whose provider isn't enabled is refused with a one-line
message -- for `claude_subscription` specifically (when auto-detection
found nothing, never for an explicit override) that message is the SAME
precise reason (not logged in / claude not installed / logged in via a
non-claude.ai authMethod, each with its own fix) a turn would have failed
with anyway, just surfaced earlier; every other provider names the
`halo providers enable <name>` fix. A provider that's detected (real
credentials/login) but explicitly disabled shows one dim hint line in
`/model` instead of a selectable row. `halo providers`/`/providers`
shows each provider's status as one of `auto (detected from <source>)`,
`disabled by you`, `enabled by you`, or `not set up`, plus reachable/cached
model count.
