# Models: Ollama fit, calibration and the gym

Read this when a local model does not fit, calls tools badly, or you want `halo gym` scores and role defaults for your GPU.

Part of [Models](MODELS.md), which lists every part.

## Ollama: fit, calibration and the gym

**Fit calibration (round 5b; Halo 3.2.3.0 R1)**: `halo ollama calibrate <model> [--host
NAME] [--start N] [--timeout S]` loads `model` at a candidate `num_ctx` (the GPU-based
estimate when a local or `ssh:`-configured read exists, else 32768),
reads `/api/ps` back (`size` vs `size_vram`), and steps DOWN by powers of
two until it is fully resident in GPU memory -- or stops at 4096 and
reports "does not fit." A step is a measurement only when the load
finished within its budget (local 20 s + 4 s per GB, remote 40 s + 6 s
per GB, 60 s for an unknown size, or `--timeout`) and `/api/ps` lists the
model at that very `context_length`; otherwise it is unknown, tried once
more with twice the budget, then the run ends inconclusive and records
no cap. The result -- `{host url, model, digest, max_full_gpu_ctx,
measured_at, ollama_version}` plus, when one was seen, `tight_ctx`/
`tight_vram`/`gpu_total` -- is recorded in `~/.halo/ollama-fit.json` and
is ONE candidate of the `min()` below, not a winner over everything: the
prompt floor (the request's own estimate, LOCAL-MODELS.md) sits under
the whole `min()` and raises the window over a smaller saved cap. It never expires on its
own; it is re-measured only by an explicit re-run of the command, or
automatically the moment the model's own `digest` (re-pulled weights) or
the host's `ollama_version` (a server upgrade) changes. The FIRST time a
model is used on a host with no learned cap at all, Halo runs the same
procedure automatically before the first request, with one plain notice
line ("qwen3-coder:30b on pc: 32k fits, 65k does not (1 min 50 s)"; the
turn waits up to 20 s, the measurement finishes in the background and its
line appears on a later turn) -- opt out
with `ollama.auto_calibrate: false` (docs/CONFIG.md). `/ollama`/`halo
ollama` show every catalog model's learned cap (or "not calibrated") next
to a "what fits" column and the one-phrase source of that decision
("learned cap" / "host max_ctx" / "fit estimate" / "remote default" /
"trained context" / "hard cap" / "fallback").

**Calibration also steps UP (round 5b part 2)**: once the DOWN-stepping
loop above finds a candidate that fits fully resident, calibration keeps
DOUBLING from there -- `halo ollama calibrate`'s own first guess on a
roomy card is often not the model's true ceiling, and settling for it
would under-use real headroom. Bounded by the model's own trained context
and the hard cap (131072) either way, and stopping at the FIRST candidate
that does NOT fit (never stepping back down to search for a smaller gap)
-- the recorded `max_full_gpu_ctx` is the LAST value that was still fully
resident. `halo ollama calibrate --no-up` skips this phase and keeps the
first fitting guess, for a faster (but possibly smaller) measurement. The
automatic first-use trigger steps up too, bounded by that model's own
catalog-reported trained context.

**All layers on the GPU (Halo 3.2.3.0)**: by default Ollama moves part
of a model to the CPU once the window passes a size it judges risky, even
when the GPU has room left. Measured on one host (placeholders: a 23 GB
card, a 17 GB model): offloading started past a 49,152 window by default;
with every layer forced onto the GPU the same model at 65,536 used 20.7
of 23 GB and read prompts at about 2,500 tokens/s (safe), at 98,304 it
used 22.1 GB (works, too tight for daily use); a smaller coder model at
65,536 used 21.6 GB at about 4,800 tokens/s. So when Halo's memory
estimate (weights + KV bytes per token x the window) or a calibration
says the model fits the GPU at the window sent, the request carries
`options.num_gpu` = the model's layer count (`<family>.block_count` + 1
from `/api/show`, 999 when unknown -- Ollama caps it); otherwise
`num_gpu` is left to Ollama. Calibration loads with the same option and
reads a load with `size_vram < size` as offloaded (it steps down), a
fully resident one as safe or tight by the headroom rule (at least 8 % of
the card or 1.5 GB free); the saved window is the largest safe one, with
the midpoint between a safe size and the next (x 1.5) tried once. A
derived model whose Modelfile keeps every layer on the GPU with its own
default window (it shares the blobs) works the same way (a tuned twin,
below). Prompt reading
speed (`prompt_eval_count` / `prompt_eval_duration` of each real turn) is
kept per host and model as a rolling average (`prompt_speed` in
`~/.halo/ollama-fit.json`, beside the calibration entries) and `halo
ollama` shows it ("reads ~2,500 tok/s").

**A tuned twin (Halo 3.2.3.0)**: Ollama's own rule offloads part of a
model to the CPU past a 49,152 window on the host measured above, even
with room left on the card, for any client that does not ask otherwise.
A tuned twin carries the fix as the model's own defaults: `halo ollama
tune <model> --host <name>` creates, through `/api/create` on that host,
a derived model `FROM <model>` with `PARAMETER num_ctx <the safe window
calibration recorded>` (or `--window N`, held at the trained context)
and `PARAMETER num_gpu <every layer>` (`<family>.block_count` + 1, 999
when unknown). It shares the original's blobs, so it costs no extra disk,
and every client of that server (Halo, `ollama run`, another tool) gets
the whole model on the GPU at that window. The name rule: `-halo` is
added to the model's name and the tag is kept (`qwen3.8:27b` ->
`qwen3.8-halo:27b`; `qwen3` -> `qwen3-halo:latest`). With the facts
above as placeholders (a 23 GB card, a 17 GB model: 65,536 safe, 98,304
tight) the twin's default window is 65,536 -- the tight 98,304 is never
a twin's default. Ollama keeps no comment of a Modelfile, so Halo knows a
twin by what `/api/show` keeps: `details.parent_model` (the `from`
model), both parameters, and the name rule; it also records each twin it
made (`twins` in `~/.halo/ollama-fit.json`) for a server that leaves
`parent_model` empty. The twin starts calibrated (it carries its
original's measured window), `halo ollama` and `halo local` list it under
its original ("tuned twin of qwen3.8:27b (65k window, all layers on the
GPU)"), the `/model` picker and Studio's Models rows show it first for
that host, and `--remove` deletes it (never an original). `halo ollama
discover --calibrate` and the wizard's calibrate offer end with "make
tuned twins of the models that fit? (Enter / n)". See
[COMMANDS-ollama.md](COMMANDS-ollama.md)'s `halo ollama tune`. From a
row (3.3.5.0 R3): Studio's Local -> Models, a model's `...` menu, **Make a
tuned twin** -- pick the window, read the twin's name and what it costs (a
manifest, no new blobs), then Make it -- or `halo models twin <name>
--window N [--host H]` ([STUDIO-local.md](STUDIO-local.md)).

**Context-ownership precedence (round 5b, corrected)**: `num_ctx` is the
SMALLEST of every candidate that is actually known -- the hard cap
(131072) always included -- where the "fit" candidate is the learned
calibration cap when one exists, else the live fit estimate; `host.
max_ctx`, when configured, is an ordinary candidate in that same
minimum, not a separate override tier. The one MUST-FIX from a live
LAN-host run: a REMOTE host (no `ssh:` configured, nothing loaded yet)
with no `host.max_ctx` and no fit signal at all now gets a conservative
32768 default instead of silently falling through to the 131072 hard
cap -- `ollama.hosts[].max_ctx` is the documented explicit override for
this exact case. A LOCAL host never hits this path (it always has an OS
GPU probe to fall back on).

**The memory arithmetic (3.3.4.0 R3, corrected)**: the fit estimate is the
largest window whose parts fit the card's free memory (every loaded
model's share counted back in) after Ollama's per-card minimum (457 MiB on
CUDA, 512 on Metal, plus `OLLAMA_GPU_OVERHEAD`): the weights (less the
token embedding llama.cpp keeps in RAM, when `/api/show` gives the
vocabulary), the KV cache of only the layers that hold one (one in
`full_attention_interval` for a hybrid model such as Qwen 3.5 / 3.8, never
the draft layer, the non-zero entries of a per-layer `head_count_kv` list)
times the window times the server's parallel slots, a hybrid model's
recurrent state, the draft layer's f16 cache and compute, the compute
buffer (the attention mask and one layer's f16 K and V per token), and a
vision model's projector. The cache type and the slots come from the host
entry's `kv_cache_type` / `num_parallel_hint`, else from the server's own
startup log on this machine, else f16 and one. Halo sends `num_gpu` (every
layer) at a window it knows fits, so its estimate is the one with every
layer forced; the steward's planner also works out the default, where
llama.cpp's `--fit` keeps 1,024 MiB plus the projector free. On the
measured 24 GB card this says 65,536 for qwen3.8:27b (it said 32,768 before)
and qwen3-coder:30b forced, 49,152 and 53,248 by default, within 5 % of the
log's own sums (`ollama_steward/knowledge/memory.md`).

**Multi-GPU**: when the local probe (or an `ssh:` read) sees more than
one card, the fit estimate SUMS every card's free memory -- never the
minimum, which would waste every card past the smallest -- minus a
per-card overhead (`OLLAMA_GPU_OVERHEAD`'s own documented meaning,
"set aside VRAM per GPU," taken out once PER CARD). This matches Ollama's
own documented spread rule: a model that fits on one card loads there;
one that doesn't is spread across every configured card, never a partial
subset.

**Optional ssh GPU read for a remote host**: `ollama.hosts[].ssh:
"user@host"` runs the exact same vendor probes (NVIDIA/AMD/Apple) over
`ssh -o BatchMode=yes -o ConnectTimeout=3 user@host '<command>'` instead
of a local subprocess -- read-only, never prompted for a password (
`BatchMode` refuses outright rather than hanging). Entirely optional:
calibration already works without it (it needs no GPU read at all, only
Ollama's own `/api/ps`). Not covered: the sysfs AMD branch (it reads a
local file path directly, with no ssh-shaped equivalent) -- a documented
gap, not a silent one.

**KV cache type per host**: `ollama.hosts[].kv_cache_type` ("f16"
default, "q8_0", or "q4_0" -- Ollama's own `OLLAMA_KV_CACHE_TYPE` values)
is a HINT the operator sets to match their server's own flag; Ollama
exposes no per-model readback of what's actually running, so this is
never auto-detected. The exact bytes/element the fit arithmetic now uses,
hand-summed from llama.cpp's own `ggml-common.h` block structs: f16/bf16
2.0 (unchanged), q8_0 1.0625 (was approximated as 1.0, 6% too low), q4_0
0.5625 (was approximated as 0.5, 12% too low) -- both old approximations
under-counted memory, the wrong direction for a budget estimate.

**Apple Silicon memory model**: unified memory, no discrete VRAM to
query. The local probe reads total RAM (`sysctl hw.memsize`) and, when
set, `sysctl iogpu.wired_limit_mb` (confirmed from mlx-lm's own README --
"wires the memory occupied by the model and cache," `sudo sysctl
iogpu.wired_limit_mb=<N>` is the documented way to raise it); with the
limit unset, the GPU-usable share is estimated as roughly two-thirds to
three-quarters of total RAM (the exact fraction is UNCONFIRMED against
any Apple/mlx-lm primary source -- a wizard/panel FIRST GUESS only,
always labelled an estimate). `halo ollama calibrate` is the ground
truth on a Mac exactly as it is everywhere else; the fraction never
overrides an actual calibration result.

**Stable request prefix**: Ollama/llama.cpp reuse the cached prompt
prefix when a request is byte-identical up to the first change, so the
system message, the tools array, and `options` must never carry per-turn
volatile content (a live timestamp, a context percentage, a counter) on
an `ol:` session. Pinned directly (`tests/test_ollama_precedence_5b.py`):
building two consecutive request bodies for the same session produces a
byte-identical leading system message, tools array, and `options`, even
when the caller's own tool list happens to arrive in a different order
each time (`convert_tools`'s own alphabetical sort absorbs that). What
remains volatile BY DESIGN, never claimed stable: the full messages list
legitimately GROWS turn to turn (each new turn's own content is new, and
context pruning may reshape an OLDER tool result's text once the
transcript grows past a threshold -- a deliberate context-management
trade-off, not a bug); and `num_ctx` may change exactly ONCE, from
before a brand-new model's first load to after it, on a host with no
learned cap yet (round 3's own fix already makes it stable from the
SECOND turn onward, since a loaded model's context is then read back
from `/api/ps` as ground truth rather than recomputed).

**Throughput in the UI**: for an `ol:` turn, the status bar's model chip
shows a compact segment next to the model name -- `"41 tok/s · prefill
1.2 s"` -- computed from the final NDJSON line's `eval_count`/`eval_
duration`/`prompt_eval_duration` (Ollama's own documented nanosecond
timing fields), plus `"· offloaded"` when the last `/api/ps` read (a side
effect of the SAME read the fit estimate already makes, never a second
probe) found the model partially in system RAM. `halo ollama` prints the
last turn's own numbers per host/model, persisted in the same `~/.halo/
ollama-fit.json` file as the learned caps.

**Reliable tool calls from small models (round 5b part 2, corrected by a
fix pass the same day)**: local models fail mostly by emitting malformed
or half-formed tool calls, not by choosing the wrong tool. **Constrained
decoding is used ONLY to repair a malformed call, never to force one** --
an ordinary turn, including one right after a tool result, is ALWAYS
decoded free: the model must always be able to answer in prose. The first
version of this round instead sent the tool-call schema as an output
CONSTRAINT on every turn it judged "expected to call a tool" (right after
a tool result) -- a real run on a local box showed why that is wrong: once
the model had nothing useful left to call, it could no longer just say so
in prose, so it emitted one meaningless call (`TaskStop` on a task that
didn't exist) every time, Halo dispatched it, and the NEXT turn was ALSO
"right after a tool result" and ALSO constrained -- the session looped for
25 minutes (175 requests) until killed by hand. That gate (`providers.
tool_call_schema.expected_to_call_tool`) is deleted outright. Three
measures remain, all behind the `ollama` dialect (local hosts only -- never
Ollama Cloud, which the research confirms rejects structured output) and
`hf:local/*` servers, every other dialect completely untouched:

1. **One local repair round, constrained.** A tool call that fails to
   parse (bad JSON arguments, or a resolved tool whose arguments fail
   schema validation -- covering "missing required argument") gets ONE
   isolated, tools-less, history-less completion: Halo sends the tool's
   own exact `input_schema` as the output constraint (`format` on `ol:`,
   the OpenAI `response_format` json_schema shape on `hf:local/*`) plus
   the parse/validation error, and uses whatever comes back (re-validated
   against that same schema) as the repaired call -- before anything
   reaches the user. A second failure (or the repair reply itself not
   validating) surfaces the ordinary plain error, exactly as it always
   has. This is the ONLY place either dialect ever puts a structured-
   output constraint on the wire now -- a real tool call was already
   ATTEMPTED and failed, so constraining the fix to that one tool's own
   schema is correct; constraining an attempt that hasn't happened yet is
   what caused the live-run loop. An UNRESOLVED tool name is never offered
   this repair round at all -- there is no single schema to constrain
   against until a name is known, and the existing alias-table/difflib
   name resolution already recovers the overwhelming majority of near-miss
   names locally, with no network round trip either.
2. **Leak-parser promotion stays on regardless.** The generic bare-JSON/
   fenced-JSON leak extractors (`tool_leak_patterns=("python_repr_args",
   "json_text_call")`) are enabled for the `ollama`/`huggingface` profiles
   -- harmless now that nothing forces a model into that shape: if a model
   spills a `{"name": ..., "arguments": {...}}`-shaped attempt into plain
   text on its OWN initiative (unprompted), it still gets promoted to a
   real tool_use via the existing, dialect-agnostic leak_parser call.
3. **A stricter identical-call loop guard.** Independent of the generic,
   all-dialect loop breaker (5 denies, 8 ends the turn, counted per turn
   but NOT required to be consecutive), `ollama`/`huggingface` sessions
   also track an unbroken run of the IDENTICAL (tool, arguments) pair --
   three in a row stops the turn immediately with one plain sentence
   ("... the model repeated the same tool call three times in a row --
   stopping this turn so you can steer it"), reset every turn, with the
   same `BashOutput`-polling exemption the generic breaker already has.
   This is the backstop against a model stuck repeating one call for ANY
   reason, not just the specific constraint-driven loop above.

**VRAM-aware role defaults (round 5b part 2)**: when the session's main
model is `ol:` on a host where a SECOND model's own on-disk weight size
plus the main model's CURRENTLY RESIDENT size (`/api/ps`'s `size_vram` --
a measured fact, main must actually be loaded) would exceed that host's
total GPU memory, the `small`/`researcher`/`judge`/`subagent_default`
roles' TABLE value (never an explicit `--role`/`/roles set` override for
this run -- that is never second-guessed) is redirected to the main model
itself instead of evicting it -- `providers.ollama_hw.fits_beside_main`
is the measurement, `roles.vram_aware_override` the redirection; unknown
(no GPU read, main not loaded, candidate not in the catalog, different
hosts) always means "leave it alone," never a guess. `/local <question>`
applies the SAME redirection at call time to whatever `roles.small`
resolved to. `halo roles`/`/roles` and the model picker's `u` action show
`(same as main: fits beside it: no)` as the reason when this fired.

**The model gym (`halo gym`, round 5d; `hf:local/*`/`hf:mlx/*` added round
5i)**: a fixed task battery run against each local model on THIS
machine's own hardware, through the real request/decode path (never a
second, parallel wire format) -- `halo gym [--models ol:a,hf:local/b,...]
[--roles small,judge,...] [--quick]`. `ol:`, `hf:local/*`, and `hf:mlx/*`
all count as "local"; every OTHER ref (the router, a dedicated endpoint,
any cloud provider) may still be NAMED explicitly for comparison but is
never run by default. `gym_send.send_turn_for` picks the sender -- the
native Ollama path (round 5d) or `providers.huggingface_send.send_hf_turn`
(round 5f's shared openai-chat sender, reused as-is here too) -- so the
same four measurements, each a plain ratio (never a vendor claim), apply
either way:
  - **tool-call accuracy**: out of N real attempts to call a Read tool, how
    many came back schema-valid on the FIRST try. A malformed/missing call
    gets exactly ONE local repair round (the SAME constrained-decoding/
    free-decode choice `supports_constrained_tool_calls` makes for the
    repair loop below) before counting as failed -- repaired calls and
    repair rounds are reported SEPARATELY, never blended into the headline
    number, so a model that leans on the repair loop a lot never looks as
    good as one that doesn't.
  - **edit success**: out of N attempts, how many produced a real Edit
    call that -- actually applied to a scratch fixture file -- left it
    reading exactly as expected.
  - **context recall**: out of N attempts, how many answers contained a
    short needle fact planted at about 12% depth of a prompt sized to this
    model's own FITTED context -- `providers.ollama_hw.resolve_context_
    decision`'s own `num_ctx` for an `ol:` ref, or (round 5i) `model.
    resolve_model_profile`'s `context_tokens` for an `hf:` one (the local
    server's own reported context, else the bare 128000 profile default)
    -- this tests the context size Halo actually grants the model on this
    host, not the advertised trained one.
  - **instruction adherence**: out of N attempts at the plain-sentence
    reply rules (one word when asked for one word, no preamble when asked
    for none), how many were followed exactly.
  - **tokens/second and prefill seconds**, averaged across every real
    battery turn, from the identical `eval_count`/`eval_duration`/
    `prompt_eval_duration` fields the status bar already reads -- for an
    `ol:` model. The shared openai-chat sender exposes no server-side
    usage/per-phase timing to a caller outside it, so an `hf:` card's
    `tokens_per_second` is a wall-clock estimate instead (reply length
    over call duration, never the server's own figure) and its
    `prefill_seconds` is honestly `None` rather than a guessed number.
`--quick` halves N (and context recall's own smaller base count) for a
faster, noisier read. `--show-replies` prints each reply-only task's
actual reply excerpt (first 200 characters) alongside its score; the same
excerpts are ALWAYS saved in the result JSON under each metric's own
`samples` key, so a 0% is diagnosable from the file alone even without the
flag. Fix pass (2026-10-04 live run, a thinking-by-default model):
context recall and instruction adherence used to request only 16-32
output tokens -- too small for a model that spends its OWN tokens
reasoning before emitting the real answer, so the reply came back
genuinely empty (never thinking text mistaken for the answer -- the
decoder never turns `message.thinking` into checked text in the first
place) and scored a flat, unexplained 0%. Both now request a flat,
generous 160-token budget; the needle check is also now case-insensitive
(already tolerant of surrounding punctuation/quotes as a plain substring
check). Results persist at `~/.halo/gym/<host-slug>/<id>.json` with the
model name, a stable id, fitted context, and timestamps measured AT THAT
TIME -- `halo gym show [model]` prints a per-model card from the saved
file, never a fresh probe. For an `ol:` ref, `<host-slug>` is the Ollama
host's own configured name and `<id>` is the model's real digest
(quantization and the Ollama version are recorded too). For `hf:local/*`/
`hf:mlx/*` (round 5i), every result groups under the single shared
`huggingface` host-slug instead (there is no multi-model "host" concept
for an arbitrary local server the way an Ollama daemon is one), keyed by
a stable id of its own -- the bare Hugging Face Hub repo id for `hf:mlx/
*` (`ensure_mlx_server` already names its managed server by that exact
id), or the resolved server's own configured/auto-detected name for a
generic `hf:local/*` ref (no per-model digest concept exists for an
arbitrary OpenAI-compatible server, so the SERVER is the measured unit
there); neither quantization nor an engine version string is recorded
for this branch. A cloud/router/endpoint ref may be named explicitly for
comparison; the battery never runs against one by default (cost).

**From scores to a role table (`halo gym propose`)**: turns saved gym
scores into a role-table proposal in the EXISTING roles v2 shape (nothing
new) -- the best LOCAL (`ol:`/`hf:local/*`/`hf:mlx/*`) model per supporting
role (`small`/`researcher`/`judge`/`subagent_default`), each role weighting
the four raw ratios (plus normalized tok/s) by what that role's own job
leans on most (documented in `gym_propose.py`'s own `ROLE_WEIGHTS`), with
the round 5b VRAM-aware rule (`roles.vram_aware_override`) applied to the
winner exactly as a live session would -- that rule already no-ops on its
own whenever either the winner or `main` isn't an `ollama` ref (its own
existing guard clauses), so an `hf:` winner, or `--main` pointed at an
`hf:`/cloud ref, simply skips it with no separate branch needed. `main` is
never touched -- "left as configured" means
propose never writes an `orchestrator` entry at all; `--main REF` only
supplies the reference point the VRAM rule compares candidates against,
same reason. One plain sentence per role names the composite score and the
measurements behind it, or says plainly that no local model has a usable
score for that role yet. `--apply` saves the proposal as an ordinary role
template through the EXISTING `halo roles template import` path
(`~/.halo/roles/gym-proposed.json` by default) -- `halo roles template
load gym-proposed` (or the picker) is the separate, explicit step that
makes it the live table. The `/model` picker shows a model's gym score
(and tok/s) beside it, read straight from the saved file, whenever one
exists.

**The 60-second acceptance check (`halo doctor --local [--model ol:x]`)**:
the "works out of the box" proof per machine, and the first thing the docs
below point a new local-model user at. Four steps, always run in this
order and each printed as `[PASS]`/`[FAIL]` with a plain reason and the
elapsed time, even when an earlier one failed: load the model (one plain
turn), one real tool call (Read on a scratch file, dispatched and
diffed), one structured output (the SAME constrained-decoding path the
repair loop uses), and one summary of a small fixture transcript (a
compaction-shaped call, never the full `agent/loop.py` compaction
machinery itself -- that has its own dedicated tests). Exit 0 iff all four
passed.
