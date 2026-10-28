# Models: Hugging Face

Read this when you use the Hugging Face router, a dedicated endpoint, or a local llama-server, LM Studio or MLX server (`hf:`).

Part of [Models](MODELS.md), which lists every part.

## Hugging Face

Halo 2.0.3 round 4 (`plans/2.0.3-ollama-round2-brief.md`, design doc
`docs/harness/LOCAL-MODELS-RESEARCH.md` section 9). Two fully separate
products, both OpenAI-compatible, both reusing the SAME openai-chat
request/response code every OpenRouter/Databricks-chat call already goes
through (no second wire format) -- the brief's own framing: "this should
be mostly config/routing, not a new wire format."

**Inference Providers (the router)**: `hf:<org>/<model>` (optionally
`:fastest`/`:cheapest`/`:preferred`/`:<provider-name>`, e.g.
`hf:openai/gpt-oss-120b:groq` -- passed through VERBATIM in the wire
`model` field, never parsed or validated by Halo) against
`https://router.huggingface.co/v1`, `Authorization: Bearer $HF_TOKEN`.
`HF_TOKEN` is the ONLY env var name read for this -- the research doc
confirmed only this exact name ("Use a single Hugging Face token for all
providers"); `HUGGING_FACE_HUB_TOKEN`/`HF_API_TOKEN` are NOT accepted as
fallbacks since neither was confirmed as an alias for the router
specifically. `BRIDGE_HF_ROUTER_BASE_URL` (or the `HALO_`/`ROLO_CLAUDE_`
twin, `config/paths.py::env_compat`) overrides the base URL for tests,
exactly like `BRIDGE_OPENROUTER_BASE_URL`. A Team/Enterprise
`huggingface.bill_to` config value (an org name) adds `X-HF-Bill-To` on
every ROUTER request only -- never on a dedicated endpoint call, which has
its own compute-time billing with no such header.

**Dedicated Inference Endpoints**: a fundamentally different product (the
research doc's own framing) -- the user provisions one specific model onto
its own compute and gets back ITS OWN url and token, billed by compute
time, never per-token. `hf:endpoint/<name>` looks `<name>` up in
`huggingface.endpoints` (`~/.halo/config.json`, mirroring `ollama.hosts`'
own shape: a list of `{name, url, token, default}`) and uses that entry's
`url`/`token` AS-IS -- never the router's base URL, never `HF_TOKEN`. An
entry with no `token` sends no `Authorization` header at all (the same
"unauthenticated unless configured otherwise" default `ollama.hosts`
uses); a name that isn't configured gives a plain message naming
`huggingface.endpoints`, never a silent fall-back to the router. The exact
per-endpoint URL *pattern* was UNCONFIRMED this round (no fetched page
gave a concrete example) -- irrelevant to Halo either way, since the user
supplies the full URL directly.

**Dialect**: `openai-chat`, same as OpenRouter -- tools supported,
reasoning passthrough the same way OpenRouter's own `reasoning.effort`
field works, no OpenRouter-only fields (`provider`/`reasoning`/`models`/
`plugins`/`usage`) ever sent to this host. `resolve_model_profile` for an
`hf:` ref: the router's own cached catalog (below) when the bare
`<org>/<model>` id -- suffix stripped -- is known, else the bare
`ModelProfile` dataclass default; a dedicated endpoint ref always gets the
dataclass default (it was never listed by the router's catalog at all).

**Catalog**: `GET /v1/models` on the router, cached in `~/.halo/
huggingface-models.json` (a SEPARATE file from OpenRouter's own
`models.json` -- a colliding bare id between the two routers would
otherwise cross-contaminate one flat file) with the same TTL knob every
other network catalog here shares (`databricks.catalog_max_age_hours`,
default 24h). Refreshed the same way OpenRouter's own catalog is: a
background, staleness-gated worker on `/model` open and at app launch
(never on the UI thread, never when the token is absent -- no network at
all for the picker's first paint), plus an explicit force-refresh. Router
models appear in the `/model` picker under a "Hugging Face" group once the
provider is enabled. The router's exact per-entry `GET /v1/models` field
names were NOT confirmed this round (no fetched page gave a concrete
response body) -- the parser ASSUMES the same shape `probe_openrouter_
models` already parses (OpenRouter's own `/models`: top-level
`context_length`/`pricing.{prompt,completion}`), the closest confirmed
precedent, and degrades to omitted fields rather than raising if a real
response differs. Treat context/pricing from this catalog as best-effort
until verified live.

`/providers`, `halo providers`, and `doctor`'s provider count already show
Hugging Face (unlike Ollama, which stays out of that generic table -- see
above); round 5's three local-server additions below don't change that.

**`hf:local/*` -- a local OpenAI-compatible server** (round 5, research
doc section 8/10): `llama-server`, vLLM, `transformers serve`, LM Studio
or TGI, running ANYWHERE Halo can reach -- `hf:local/<model>` (the default
server) or `hf:local/<model>@<name>` (a NAMED entry in `huggingface.
local_servers`, a list of `{name, url, api_key, default}` mirroring
`ollama.hosts`/`huggingface.endpoints`'s own shape). A manual entry's
`api_key`, when set, goes out as `Authorization: Bearer` on every call to
THAT entry -- pinned apart from `HF_TOKEN` and an `huggingface.endpoints`
token, never a fallback for either. With no manual entry configured (or
none marked `default`), the default server is the FIRST auto-detected one
(below); a NAMED ref that doesn't match a manual entry fails plainly,
never silently falling back to auto-detection. Dialect: `openai-chat`,
identical to the router/an endpoint -- no new wire format.

**Auto-detection**: a background probe of `GET /v1/models` on 127.0.0.1
ONLY, on the documented default ports (research doc section 8): **8080**
(llama-server, TGI), **8000** (vLLM AND `transformers serve` -- both
plain OpenAI-compatible, deliberately treated identically rather than
guessing which one answered), **1234** (LM Studio). Jan's own default
port was never confirmed by the research doc and is NOT guessed -- add it
as a manual entry instead. Overridable for tests (or an unusual setup)
by `huggingface.local_probe_ports` (a config.json int list) or
`HF_LOCAL_PROBE_PORTS` (a comma-separated env var, wins when both are
set); honours `BRIDGE_TEST_NO_BACKGROUND_NET` like every other background
probe in this codebase. A manual entry is never probed in the background
-- only on demand, via `/local refresh` -- using this SAME `GET /v1/
models` call with its own `api_key` as the bearer. Most of these servers
fix their context length at launch time rather than per request (research
doc section 8/10), so Halo reads back whatever `/v1/models` reports (`max_
model_len` for vLLM; other field names are tried heuristically, since no
runtime's exact name beyond vLLM's was confirmed this round) or, as a
secondary best-effort read for any model that reported none, llama-
server's own `/props` endpoint (also unconfirmed at the JSON-shape level
-- degrades to "unknown" rather than guessing). Unknown context falls back
to the plain `ModelProfile` default, same as an unlisted router model.

**mlx_lm.server (round 5b part 2, Apple Silicon)**: Apple's MLX runtime
answers the SAME OpenAI-compatible shape on the SAME default port family
as llama-server (8080) -- the research doc never confirmed `mlx_lm.
server`'s own exact flags, so Halo tells the two apart by what `/props`
answers instead of by port: a server that answers `/props` is labelled
`llama-server` (a confirmed, llama.cpp-specific native endpoint); one that
does NOT, on Apple Silicon (`sys.platform == "darwin"`) specifically, is
labelled `mlx` (a heuristic -- the absence of one tool's own marker, not
a positive MLX signal -- UNCONFIRMED, round 6's live Mac check should
verify or correct it); on any other platform a missing `/props` stays
genuinely unlabelled rather than guessing. `/local` shows the label in
the server's own group name.

**The Hugging Face Hub cache**: `/local` (below) also walks `$HF_HUB_
CACHE`, else `$HF_HOME/hub`, else `~/.cache/huggingface/hub` for `models--
<org>--<name>` directories -- models present on disk (from `hf download`)
but not necessarily being served by anything right now. Reports the
repo id, real on-disk size (summed from `blobs/`, never double-counting
the `snapshots/` symlinks that point back to them), and the format(s)
present (`safetensors`/`gguf`, read from the snapshot symlinks' own
filenames -- a blob's name is a bare content hash). Never follows a
top-level symlink that resolves outside the cache root. A repo under the
`mlx-community` org is labelled "runnable through MLX" in its capability
column -- the Hub org MLX-quantized repos are actually published under.

**LM Studio's own model folder (round 5b part 2)**: `~/.lmstudio/models`
(the documented default; `huggingface.lmstudio_models_dir` overrides it
for a box where LM Studio's own in-app "Model Storage" setting moved it --
that setting's own persistence was not independently confirmed this
round) joins the Hub-cache scan as a second on-disk source, under its own
`LM Studio (cache, not served)` group in `/local`. LM Studio mirrors the
Hub's `<publisher>/<model>/` folder nesting directly (never the Hub
cache's content-addressed `models--org--name`/`blobs`/`snapshots`
structure) -- a bare `.gguf` file in a model folder, or a transformers-
style folder (`config.json` beside `*.safetensors`), each become one row.

**The shared `/local` view** (round 5): `/local` with no arguments (TUI)
or `halo local [--refresh]` (CLI) merge THREE sources into one list, in
this order, with a group label per source/host: each configured Ollama
host's catalog (round 3's analysis, loaded-now and fit included), running
Hugging Face local servers (auto-detected, always; manual entries too,
but only probed for real on `/local refresh` -- a bare open shows them as
"configured, not probed yet"), and the Hugging Face Hub cache. Columns:
size, quant (Ollama only -- not reported by `/v1/models` or derivable from
a cached GGUF without opening it), context, a capability badge (`tools:
probed yes/no` once round 2's own real-inference capability probe has
run for that Ollama model digest, else `tools: declared yes/no` from the
catalog's own claim -- a local HF server's `/v1/models` response declares
no such field at all, so that badge reads `declared: unknown` there), and
"loaded now" where the concept applies (Ollama only). `/local <question>`
answers from `roles.small` (now `ol:` OR `hf:`, see "Ollama" above);
`/local refresh` re-probes everything a bare open doesn't.

**Init tab**: `halo init`'s interactive Providers step gains an `Ollama
(local or LAN)` tab (detects/registers the local daemon, or add a LAN/
cloud host with an optional key, writing `ollama.hosts`) and a `Hugging
Face` tab (paste `HF_TOKEN`, add a dedicated endpoint, add a local server
by URL with an optional key, or rely on auto-detection -- any subset, all
optional, both tabs skippable) -- see `docs/CONFIG.md`'s "Providers"
section for why neither is a `halo init --provider` CLI-flag choice.

**The wizard detects before it asks (round 5b part 2)**: both tabs open
with a short detection summary, filled in by a background worker (never
the UI thread -- every field/button renders immediately regardless of
how long the probe takes; a slow probe just means the summary line stays
"detecting..." a little longer, never a stuck wizard): GPU or unified
memory (labelled an estimate where it is one), whether Ollama is
reachable and what it already has pulled, any running local server, and
model folders already known. For each already-installed Ollama model it
names the largest fully-resident context (the learned cap when one
exists, else the live fit estimate, labelled either way); for whatever
free room is left, one or two illustrative model classes and quantizations
that would likely fit with a 32k context -- derived from the same exact
per-parameter byte table the KV-cache arithmetic uses for weights, plus a
flat ~2 GiB reservation for the context itself (not that class's own real
KV formula, which needs an architecture no not-yet-installed model has)
-- explicitly an estimate, never a download from the wizard itself.

**Finding and using file-backed models (round 5c)**

A model you already have as files on disk -- downloaded by hand, by `hf
download`, or by LM Studio -- does nothing by itself until something
loads it. This is Halo's answer to "I have model files somewhere, how do
I actually talk to them."

**Where Halo looks**: the Hugging Face Hub cache and LM Studio's folder
(both above) plus `huggingface.model_dirs`, a list of your OWN folders
(docs/CONFIG.md) Halo scans recursively (a symlinked subfolder is never
followed, matching every other scanner in this codebase) for three
shapes: a bare `.gguf` file anywhere, a folder holding `config.json`
beside one or more `*.safetensors` files (an ordinary Hugging Face
"transformers" model folder), and the same safetensors shape again when
it looks like an MLX-quantized model (its folder name mentions "mlx", or
its `config.json` carries mlx-lm's own `quantization` key -- a best-
effort guess, not a confirmed marker). Manage the list from a running
session with `/local add <path>`/`/local forget <path>` (persisted to
`huggingface.model_dirs` right away), or from `halo init`'s own "Local
models" step, which also shows the same detection summary the Ollama/
Hugging Face tabs show (round 5b part 2, above) and lets you pick a
preferred runtime (below) before you've served anything at all.

**`halo local`** (the merged view above) lists every file it finds this
way with its format, its on-disk size, and -- read directly from the
file's own header, never by loading it -- its trained context length and
quantization where the file says so: a `.gguf` file's own metadata block
(magic, version, then key-value pairs that already include the context
length, layer count, attention head counts and the quantization name) or
a safetensors folder's `config.json` (`max_position_embeddings`,
`num_hidden_layers`, `num_key_value_heads`, `hidden_size`,
`num_attention_heads`). The same arithmetic the Ollama panel uses
(`/ollama`, above) turns those numbers into a fitted context size for
this machine's free GPU/unified memory -- nothing new, no model ever
opened to learn any of this. The capability column also says whether
anything on this machine can actually run the file right now, and names
the exact command.

**Option A -- serve it.** `halo local serve <path-or-name> [--runtime
llama-server|mlx_lm] [--port N] [--keep]` (or, in the TUI, the `s` key on
`/local`'s own view) starts a small background program on your own
machine, listening on a free port on `127.0.0.1` only, that answers the
same OpenAI-compatible shape every other local server in this doc does --
`llama-server` for a `.gguf` file, `mlx_lm` for a safetensors/MLX folder
on an Apple Silicon Mac (nothing else serves that shape today; option B
is the answer for it elsewhere). Halo picks the context size itself, from
the fit arithmetic above, and once it's running you can use it for the
rest of the session as `hf:local/<name>` -- no config edit needed. It
keeps running only as long as the Halo process that started it does,
unless you pass `--keep`; `halo local stop <name>` stops it by hand
either way.

If neither runtime is anywhere Halo can find it (on your `PATH`, or
already fetched into `~/.halo/runtimes/`), `llama-server` is the one Halo
offers to fetch for you: it names the file(s), their size, and where they
will go, and does nothing until you say yes (`--yes`, or type it when
asked). A live run found llama.cpp's actual releases page a little
different from the first-pass assumption: `GET /releases/latest` points
at the project's own most recent NON-binary release, not a compiled
build, so Halo instead lists recent releases and walks them newest-first
looking for one tagged `b<number>` that actually carries what this OS/GPU
needs. For CUDA specifically: it reads your NVIDIA driver's own reported
CUDA version and picks the newest build with the SAME major version whose
minor doesn't exceed the driver's (a driver reporting CUDA 13.2 skips a
13.4 build -- its minor is too new -- and falls back to the newest
available 12.x build instead); with no matching major AND no 12.x build
either, or with no NVIDIA driver at all, it falls back to a cross-vendor
Vulkan build; Metal is always the pick on a Mac. `--backend cuda|vulkan|
cpu|metal` overrides this choice outright. A CUDA pick also downloads the
paired `cudart-*` redistributable runtime UNLESS a CUDA toolkit is already
on your machine (detected by a `cudart64_*.dll` on `PATH` on Windows, or
`libcudart.so*` on Linux) -- the consent sentence names both downloads,
their combined size, and mentions the smaller, slower `--backend vulkan`
build as an alternative. Every downloaded file is checked against the
exact byte-for-byte digest GitHub's own API reports for it (llama.cpp
doesn't publish a checksum file of its own) before being unpacked into
`~/.halo/runtimes/<tag>/` -- never onto your `PATH`. Say no and Halo just
tells you the one-line install command for your OS instead (Homebrew,
winget, or the release page) and stops there. `halo local runtime remove
[VERSION]` deletes a fetched copy. `mlx_lm` is never fetched this way --
it's a small Python package (`pip install mlx-lm`); Halo tells you that
one line too, if it's missing.

**Option B -- import it into Ollama.** If you already run Ollama, `halo
local import <path-or-name> [--name NAME]` is the other way to use a
`.gguf` file: Halo tells you the file's size and that it's about to be
copied into Ollama's own model store, and once you say yes, it does
exactly that -- the result is an ordinary `ol:<name>`, with every one of
this doc's own Ollama rules (context sizing, roles, calibration) applying
to it automatically. Under the hood (a live run corrected the first-pass
assumption here too: Ollama's OLDER "write a Modelfile, `FROM <path>`"
approach now answers `HTTP 400`, "neither 'from' or 'files' was
specified"): Halo computes the file's own sha256, asks Ollama whether it
already has a blob by that digest, uploads the raw bytes only if it
doesn't (streamed from disk, never held fully in memory -- these files
are commonly hundreds of MB to tens of GB, with a plain progress line
while it happens), and then creates the model by naming that blob. This
round only imports `.gguf` files: Ollama's own documentation of which
other model shapes (safetensors folders) it can import directly wasn't
found this round, so Halo doesn't guess -- option A is the answer for
those.

**Roles**: either way, a model that becomes usable this way defaults to
the `small` role, the same as any other local model -- never picked as
the session's main model without you asking for it (see "Roles" above/
docs/ROLES.md).

**Apple Silicon (`hf:mlx/*`, round 5f, experimental)**

`hf:mlx/<org>/<repo>` names a Hugging Face Hub repo directly (for
example `hf:mlx/mlx-community/Qwen2.5-7B-Instruct-4bit`) rather than a
file already on disk -- the difference from `hf:local/*`/option A above:
nothing needs to be downloaded or discovered first. The FIRST use starts
a Halo-managed `mlx_lm.server` on a free loopback port with `--model
<repo>` (mlx-lm itself downloads the weights into the Hugging Face Hub
cache, or reuses them if already there, the first time it runs -- Halo
never downloads anything itself here); a plain notice names the repo,
its approximate size when the Hub cache already knows it, and the cache
destination. Every later use of the SAME repo id reuses that already-
running server -- no second download, no second notice. Recorded in the
exact same `~/.halo/run/local-servers.json` registry option A's managed
servers use, so `halo local stop <repo>` stops it, and it is stopped when
the `halo` process that started it exits unless kept.

Off by default -- `mlx-lm` is an optional extra, never installed unless
you ask for it:

```sh
uv tool install "halo-harness[mlx]"
```

(`pyproject.toml`'s own environment marker restricts this to macOS on
arm64 -- `uv`/`pip` never even attempt it on any other platform.) `halo
doctor` names whether the extra is present on Apple Silicon; on every
other platform, resolving an `hf:mlx/*` ref gives exactly one plain
sentence, **"MLX runs on Apple Silicon only."**, and nothing else about
the install, the doctor output, or any other route changes.

Because the ref rides the SAME `hf:local/*` tiers everywhere else in this
codebase (`ref.local=True` alongside the new `ref.mlx=True`), everything
else about using it is identical to any other local model: tools, the
repair loop and constrained decoding (behind the `huggingface` profile,
same as `hf:local/*`), the `small`-by-default role, the fit arithmetic
(the Apple unified-memory share above, calibrated against whatever
context `mlx_lm.server` itself reports, or the repo's own cached
`config.json` when it doesn't), tokens/second on the status bar, `halo
doctor --local --model hf:mlx/<repo>` (the 60-second acceptance check),
and `halo gym --models hf:mlx/<repo>,ol:<same model>` (a side-by-side
card, including both engines' version strings, so a stale comparison is
visibly stale). `halo local` lists an `mlx-community/*` repo already in
your Hub cache with this exact ref and a `halo local serve <repo-or-
folder> --runtime mlx_lm` hint -- the explicit, non-ref form of the same
thing.

`mlx_lm.server`'s own flags beyond `--model`/`--port` (a host default, a
context-length-at-launch flag) were not confirmed from its README this
round (`docs/harness/GPU-RESEARCH.md` section 7) -- see
[MAC.md](MAC.md), the live Mac quick-start that resolves this and the
Apple memory-share fraction in practice.

## Browsing the hub (3.3.5.0)

Studio's **Local -> Library** (its Hugging Face or Both source) and `halo models browse --source hf` search the hub's
documented API for GGUF and MLX repos (`GET https://huggingface.co/api/models?filter=gguf|mlx&search=<q>&sort=downloads&limit=50`,
with `expand[]` asking for the gated flag, the last change, the downloads, the tags and the pipeline tag), one row per
repo with its downloads, licence (`cardData.license` or the `license:` tag) and a **gated** mark; its size is an
estimate (the parameters in its name at a typical quantization) until it is opened. Opening a repo
(`GET /api/models/<repo>?blobs=true`) lists its files with their sizes -- a GGUF repo one row per quant (a split file's
shards summed; the vision projector `mmproj-*`, the importance matrix and a separate draft model left out, the
projector's bytes added to each row), an MLX repo its safetensors as one -- with `gguf.context_length` as the window,
and its `config.json` (layers, KV heads, head size, vocabulary, a hybrid model's `full_attention_interval`) as the
exact shape for the fit badge. A gated repo's files and config are read with `HF_TOKEN` from the env file; the token
goes with no other request. Each row's pull line is `ollama pull hf.co/<repo>:<quant>` for a GGUF file (Ollama pulls
from the hub itself) and `halo local download <repo>` for an MLX repo (3.3.5.0 R4 builds the download). A search is
cached an hour and a repo's files a day in `<state>/cache/models-library.json`. See [STUDIO-local.md](STUDIO-local.md).

