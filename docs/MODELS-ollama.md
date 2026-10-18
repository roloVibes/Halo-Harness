# Models: Ollama hosts, requests and the catalog

Read this when you point Halo at an Ollama host and want to know what it sends, how context is sized and how the host is checked.

Part of [Models](MODELS.md), which lists every part.

## Ollama

Halo 2.0.3 rounds 2-3 (`plans/2.0.3-ollama-round2-brief.md`, design doc
`docs/harness/LOCAL-MODELS-RESEARCH.md`). `ol:<model>` (the default host)
or `ol:<model>@<hostname>` (a named entry in `~/.halo/config.json`'s
`ollama.hosts`) -- local, LAN, or Ollama Cloud, all through the SAME
request shape. An Ollama model tag may itself contain a `:` (`qwen3:30b`);
the `@<hostname>` split is always on the first (and only) `@`, never on a
colon. Not yet covered by the fixed provider-enablement table above (that
table assumes one on/off flag per provider; Ollama is multi-host
reachability instead) -- an explicit `providers.ollama.enabled: false`
override still refuses an `ol:` ref the same way it would for any other
provider name, but nothing auto-detects "enabled" the way a single API key
would.

**Why the native API, never the OpenAI-compatible shim**: Ollama's
`/v1/chat/completions` endpoint has no equivalent of `options.num_ctx` --
its own docs state plainly that context size requires a custom model via
`Modelfile`, not per-request configuration. `ol:` always uses `/api/chat`
instead, so Halo can size the context window itself, every request,
without the user ever having to find a server knob.

**Host config** (`ollama.hosts`, `halo config set ollama.hosts '[...]'`,
or hand-edited): a list of `{name, url, default, keep_alive, max_ctx,
num_parallel_hint, api_key}`. With no entries configured at all, Halo
synthesizes exactly one default host from `OLLAMA_HOST` (Ollama's own env
var; a bare `host:port` is normalized to a full URL) falling back to
`127.0.0.1:11434`, picking up an ambient `OLLAMA_API_KEY` for that one
host's `api_key` too (Ollama Cloud). Every non-loopback host is treated as
unauthenticated by definition unless its own `api_key` is set -- Ollama
itself has no auth mechanism at all; a reverse-proxy/bearer setup on a LAN
host is the user's own responsibility, never assumed.

**Request shape**: `options.num_ctx` on every request (never a Modelfile
default -- see above), `keep_alive` only when the host entry configures
one (a request-level `keep_alive` overrides the server's own
`OLLAMA_KEEP_ALIVE`, so an unconfigured host leaves the field out and the
server's setting stands), `think` mapped from the session's
effort level (off for `low` on a bool-only thinking model, graded
low/medium/high for the gpt-oss family specifically, on for medium and
above everywhere else; omitted entirely when no effort is configured,
letting the model's own default apply), and tools in the same OpenAI
function shape (`{"type": "function", "function": {name, description,
parameters}}`) the native API already expects -- no second tool-shape
conversion needed. No `tool_choice` field exists on this dialect.

**Context ownership**: `num_ctx = min(trained context from
model_info["<family>.context_length"], host.max_ctx override, a fit
estimate, 131072)`, falling back to a conservative 8192 when the trained
context isn't known yet (before the catalog has loaded for that model
once). Compaction triggers at 75% of whatever `num_ctx` that request
actually sent. The fit estimate (Halo 2.0.3 round 3) is the largest
power-of-two context whose KV cache fits in free memory after the
model's own weights: on the LOCAL host, free/total VRAM comes from the OS
GPU tool for the detected vendor (`nvidia-smi` on Windows/Linux, verified
live; `rocm-smi`/sysfs on AMD and `system_profiler` on Apple stay
UNCONFIRMED -- no such hardware available this round), cached for about a
minute so a turn never shells out more than once in that window; on a
REMOTE host, there is no OS-level read at all, so the fit estimate is
just that model's OWN already-loaded `context_length` from `/api/ps`
when it happens to be loaded there already, else unknown. Either way
`None` (unknown) simply drops out of the `min(...)` -- never a crash,
never a guessed number.

**An untagged name IS its own `:latest`** (fix pass after a live run
surfaced the gap): Ollama stores a model created/imported with no
explicit tag (`ollama create foo`, `halo local import ... --name foo`)
as `foo:latest`, and reports it that way from `/api/tags`/`/api/ps` --
every name comparison Halo makes (the catalog lookup, the trained-
context lookup, the fit estimate's `/api/ps` matching, calibration,
panel rows, `/local`) normalizes both sides through ONE helper
(`providers.ollama.ollama_names_match`) before comparing, so `ol:foo`
and `ol:foo:latest` are always treated as the same model. Before this
fix, an untagged model's own catalog row went unmatched, `trained_
context` silently came back `None`, and `num_ctx` fell all the way to
the conservative 8192 fallback -- discovered live when a model imported
without `--name`'s tag then overflowed on an ordinary prompt.

**Ollama DOES answer a 400 on overflow** (the SAME live run corrected a
second wrong assumption): a prompt longer than `num_ctx` is NOT silently
truncated server-side -- build 0.34.2 answers `HTTP 400 {"error":
{"code":400,"message":"...","type":"exceed_context_size_error",
"n_prompt_tokens":N,"n_ctx":M}}`. Halo now handles it in two tiers: if a
BIGGER `num_ctx` is actually allowed (the smallest of whichever of the
learned cap, `host.max_ctx`, and the live fit estimate are known, never
exceeding the usual 131072 hard cap) covers `n_prompt_tokens` plus the
turn's own output budget, Halo retries that ONE request once more at the
smallest power-of-two context that holds both -- no compaction, the
model never even sees a shorter prompt. Only when no bigger window is
available (or the retry overflows too) does this become an ordinary
context-overflow event, triggering the existing compaction-and-retry
path exactly like every other dialect.

**Three outcomes, not two** (fix pass after a live run surfaced the gap):
`/api/ps` is checked FIRST, local hosts included. (1) **Already loaded**
-- that model's own loaded `context_length` IS the fit estimate, full
stop; the GPU-memory arithmetic is never repeated for it, because two
slightly different free-VRAM readings (e.g. two concurrent `halo -p`
processes) used to compute two different `num_ctx` values for the SAME
loaded model and force Ollama to reload it, with partial offload, just
to change its context size. (2) **Not loaded, fits** -- the usual
headroom math, except free memory is first topped up with every OTHER
currently-loaded model's own `size_vram` (Ollama can evict any of them
to make room), since that VRAM is reclaimable, not actually unavailable.
(3) **Not loaded, does not fit** even after reclaiming -- a distinct,
POSITIVELY-known outcome from plain "unknown": `num_ctx` falls back to
the conservative 8192 (never the 131072 hard cap, which is only correct
when nothing at all is known) -- a model already spilling to system RAM
must not also be handed the largest possible KV-cache budget.

**Streaming and tool-call ids**: the response is NDJSON (one complete
JSON object per line, never SSE) -- `message.content`/`message.thinking`/
`message.tool_calls` accumulate per line; `message.thinking` is captured
for display only and never replayed on a later request (undocumented
whether Ollama expects it back at all). Ollama sends no id for a tool
call, only a 0-based `index` -- Halo synthesizes its own stable `toolu_`
id the moment an index is first seen, so the rest of the tool-result/
replay machinery never needs a second code path for this provider; a
tool-result message replays as `{"role": "tool", "tool_name": "<name>",
"content": "<result>"}` (no id at all, keyed by name). `done_reason:
"length"` maps onto the ordinary `max_tokens` stop reason; `done_reason:
"load"` (semantics UNCONFIRMED against a live server) retries the turn
ONCE, silently, but only while nothing has been shown to the user yet for
that turn -- real output alongside a "load" reason is never discarded.

**Catalog and capability probe**: `/api/tags` + `/api/show` per model are
merged into one per-host catalog, cached in memory with a short TTL (never
written to disk) -- `details.quantization_level`/`family` and
`model_info`'s trained context come from here. Separately, a background
`/api/version` probe (honouring the same `BRIDGE_TEST_NO_BACKGROUND_NET`
test seam every other background probe does) reports whether a host is
reachable at all. What `/api/show`'s `capabilities` list CLAIMS and what a
model actually DOES when asked are kept deliberately separate: the first
time Halo sees a given model digest, it sends one cheap, real tool-call
turn and records whether `tool_calls` actually came back non-empty --
cached durably per digest (`~/.halo/ollama-capabilities.json`), so the
cost (one real inference call) is paid at most once per distinct model
digest, never once per catalog read. A model re-pulled under the same
name/tag with different weights (a new digest) is probed again exactly
once. This is surfaced later as a measured badge, never a vendor claim.

**Host analysis (`/ollama`, `halo ollama`, `halo doctor`)**: Halo 2.0.3
round 3. One panel/CLI page per configured host: reachable, version, and
every currently-loaded model's `size` vs `size_vram` as ONE plain
sentence ("fully loaded in GPU memory" or "partially offloaded: X of Y
in GPU memory (N%), the rest in system RAM (slower)") -- never a block,
never gated on; a partially-offloaded model still runs, just slower.
Per model: trained context (the catalog's `model_info`) next to the
EFFECTIVE context it's actually loaded at (`/api/ps`'s own
`context_length` -- ground truth for a loaded model, not a guess), and
the KV-cache bytes/token figure -- standard GGML/llama.cpp accounting
(`2 x layers x kv_heads x head_dim x bytes_per_elem`, f16 `bytes_per_elem`
assumed since Ollama exposes no per-model KV-quant field), not
independently re-derived this round; the panel's own help text repeats
this origin note. `halo doctor` gains a lightweight one-line-per-host
Ollama section (reachable, version, loaded count only -- never the full
per-model `/api/show` fan-out the richer panel does).

**Host setup checklist (`halo ollama doctor [--host NAME]`, round 5b part
2)**: the SAME per-host analysis above, plus the documented host-tuning
recommendations Halo cannot read back from any API, as plain sentences,
never a block: `OLLAMA_FLASH_ATTENTION=1`, `OLLAMA_KV_CACHE_TYPE=q8_0`,
`OLLAMA_NUM_PARALLEL=1` on a single-user box, `OLLAMA_KEEP_ALIVE`,
`OLLAMA_CONTEXT_LENGTH` -- and WHERE each one actually lives, per OS of
the HOST (a local host: the OS Halo itself is running on; a remote host:
unknown, so all three print briefly): **Windows** -- the tray app's own
"Expose Ollama to the network" switch (its Settings screen) overrides
`OLLAMA_HOST` outright; setting it yourself is a user-scope environment
variable plus quitting and relaunching the tray app. **macOS** -- the
menu-bar app's own "Expose to network" switch, same override relationship;
setting it yourself is `launchctl setenv OLLAMA_HOST 0.0.0.0:11434` plus
relaunching the app -- from the research doc's own community-knowledge
note, NOT independently confirmed live (rolo's own Mac, when available, is
the live check). **Linux** -- `sudo systemctl edit ollama`, one
`Environment="VAR=value"` line per variable under `[Service]`, then
`sudo systemctl daemon-reload` and a restart. A loopback-only host (its
own configured URL is `127.0.0.1`/`localhost`) gets one extra plain line:
"this daemon is reachable from this machine only; to share it on the LAN
flip <the per-OS switch above>." `halo doctor`'s own Ollama section prints
the identical checklist text per host, one `[OK]`-prefixed line per
sentence, never a WARN just for this.

**Tool-catalog sizing by context class**: Halo 2.0.3 round 3. The `ol:`
ProviderProfile's `tools_max` now follows the EFFECTIVE `num_ctx` instead
of round 2's permanently-unbounded `None`: under 16k tokens -> 16 tools,
16k-32k -> 32, 32k-64k -> 64, 64k and above -> 128 -- overridable with the
`ollama.tools_max` config key (`docs/CONFIG.md`), and never below however
many built-in tools this platform actually ships (they're frozen into
every session before any cap is computed, so a smaller number would be
unreachable). The SessionCatalog -- not a second mechanism -- is what
actually shrinks the live tool list to fit (the same cap-shrink/LRU-evict
dance `/model` already runs on a provider switch); the panel shows the
resulting catalog's rough per-request prompt-token cost next to each
loaded model's `tools_max`.

**Roles**: a local `ol:` model defaults to a SUPPORTING role (the model
picker's `u` action pre-selects `small`, never `orchestrator`/main) when
assigning it a role -- `roles.<name>` is the exact same config-table
mechanism `/roles`/`halo roles` already read, no second one. Choosing a
local model as the session's main model anyway is never blocked; when
its catalog row doesn't declare tool-calling support, the plain
consequence sentence prints ("... can answer questions as the main
model, but cannot edit files, run commands, or call any other tool") and
the choice proceeds regardless.

**`/local`** (round 5 widens this from Ollama-only): `/local <question>`
is a one-shot call to `roles.small`'s model -- an `ol:` OR `hf:` ref --
answered inline and NEVER logged into the session's own transcript, the
exact same `call_small_model` path title generation/`/improve` already
use, which builds its body directly rather than through `derive_request`.
Bare `/local` (or `/local refresh`) instead opens the shared local-model
discovery view described under "Hugging Face" below.

**Not yet in this round**: images (`images`, a user message's base64
array), `format` (structured output) -- see `plans/2.0.3-ollama-round2-
brief.md` and the rounds after it.
