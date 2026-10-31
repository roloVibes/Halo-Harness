# Models: what a local model can do

Read this when you pick a local model and want to know what it is (thinking, tools, vision, coding or embedding), how Halo will call it, whether it fits this machine, and what to do when it cannot run the main agent.

Part of [Models](MODELS.md), which lists every part.

## The model card (3.3.5.0)

Every model gets a card (`providers/model_card.py`): one record of what the
model IS and the exact way Halo talks to it. Each field names where it came
from, in this order: the Ollama `/api/show` row (`capabilities`,
`details.family`, `model_info`), the tool-call probe's cache
(`~/.halo/ollama-capabilities.json`), the family rules
([MODELS-families.md](MODELS-families.md#purpose-words-the-model-card)), the
name.

| Field | Values | From |
|---|---|---|
| kind | ollama, llama-server, lmstudio, mlx, openai-local, cloud | the ref, the local server's runtime |
| thinks | yes, no, default-on (thinks unless a call turns it off) | `capabilities` `thinking`, the family, the name |
| tools | declared, probed (a real tool call came back), none, unknown | the probe first, then `capabilities` |
| vision | yes / no | `capabilities` `vision`, the projector, the name |
| purpose | coder, instruct, reasoning, vision, embedding, unknown | the name's purpose word, then `capabilities` |
| family, params, quant | `qwen35`, 27B, Q4_K_M | `details`, `model_info`, the name |
| window | the tokens and their source | `agent/model_window.window_of` ([MODELS-switching.md](MODELS-switching.md)) |
| how | the exact way Halo calls it | below |
| fit_for | orchestrator, coder lane, reviewer, small, eyes; the reason for each it cannot hold | below |

A cloud model gets a card too, from the catalog's modalities: purpose
instruct unless its name says otherwise, the window from the cloud catalog.
The card is kept in the catalog row (`card`, `card_at`) and made again when
the row, the probe, the window or `models.think` changes; nothing in it sends
a request.

**How Halo calls it** -- one line each, what the next call does:

    think off (you set it: models.think)
    no tools: answers only (tool turns in the history go as text)
    images as captions (no vision)
    window 65,536 (the card's fit), reserve 16,384
    dialect: native (/api/chat)

**The roles it can hold**: the orchestrator needs tool calling (declared or
probed), a window of 32,768 or more and an instruct or reasoning purpose; the
coder lane a coder or instruct purpose (tools, or the flattened text
protocol: tool turns as text); a reviewer anything but an embedding model;
small 9B or less; eyes vision. A coder-only model is never the orchestrator.
An unknown fact (a local server that does not say) is not held against it.

Where it shows: every model picker's rows (chips: think, tools, vision, the
purpose word, the window; the picked row unfolds its `how` lines), Setup ->
Default model and Settings' `model` row (the selected model's card under the
list), the Ollama panel's model rows, the TUI `/model` picker's rows,
`/model <ref>` (the `how` lines before the switch line), `/model` with no
argument (the current model's card), `halo models show <ref>` and
`halo models --cards` ([COMMANDS-providers.md](COMMANDS-providers.md)).

## The fit meter

Beside every model row, a small bar says whether the model runs here at the
window its card names (`providers/fit_meter.py`, the fit planner's
arithmetic on the host's hardware card):

| Level | Means |
|---|---|
| fits | every layer on the GPU with room to spare (Ollama's own fit holds the window) |
| tight | it holds the window only with every layer forced on (a tuned twin): the margin is gone |
| spill | part of it runs on the CPU at this window (slow) |
| no | it does not fit this machine at this window, GPU and RAM together |
| cloud | a cloud model: the provider runs it |
| unknown | no hardware card read for the host yet (the Ollama panel reads it), or a local server that reports no sizes |

The bar's title (and the TUI row's word) says why: "on the GPU with room to
spare: 32,768 of the 61,440 it holds here (6.0 GiB held by other programs)".
The host card comes from the Ollama panel's cache; a picker never reads the
GPU for it.

## When the main model cannot orchestrate

When the model picked as the main one -- `/model`, `halo init --model`,
Setup -> Default model, Settings' `model` row, `halo config set model` --
cannot hold the orchestrator role, one plain line says what it is and what it
cannot do here (`agent/main_model_check.py`):

    qwen3-coder:30b is a coding model with no tool calling on this server: it can write and answer but
    cannot act; as the main agent it would not run tools

and offers the fix: **keep it as the coder lane under an orchestrator**. The
lineup `local-coder` (a cloud model: `<model>-coder`) pins the coder role to
this model, puts main on the best orchestrator among the configured models
(local first; then cloud, the model you were on or the Auto pool's pick) and
reviewer, researcher and small on the `auto` pool. It is written through the
`halo teams apply` path, made active, and the session moves to the
orchestrator; Roles shows the lineup. In the TUI the offer is one key (`y` or
Enter accepts, any other key goes ahead); in Studio one button
(`Keep it as the coder lane under ...`). `halo config set model` and
`halo init --model` print the line and the command instead (`halo teams apply
local-coder && halo config set model <orchestrator>`; the lineup file is
written, not made active). **Going ahead anyway always works**: the model
stays the main one and nothing is written.

Sub-agents the lineup spawns on a model with no tool calling get the
flattened text protocol: no tool catalog on their wire, tool turns as text
(the switch step's conversion, [MODELS-switching.md](MODELS-switching.md)).

## Effort on THIS model

The `/effort` card (TUI), `/effort` (print mode) and the effort word in
Studio's session header list what effort does on the session's model:
`think on` / `think off` / `default` on a thinking Ollama model (low /
medium / high on gpt-oss), "no adjustable effort" on one whose effort does
nothing; the cloud level is kept for when the session returns to a cloud
model. A pick writes `models.think[<ref>]`, which the next call sends, and the
status bar follows at once ([MODELS-switching.md](MODELS-switching.md#effort-on-a-local-model)).

## The steward knows the card

A ledger line now carries `body_flags` (`think`, `tools`, `images`: what the
body asked of the model). The steward's rule `called-wrong` holds each line
against the model's card -- a think value to a model that does not think, a
tool catalog to one with no tool calling, images to one without vision -- and
its finding says the fix in the card's own `how` words
([MODELS-ollama-steward.md](MODELS-ollama-steward.md#called-wrong)).

## Declared, expected, verified: the three truths (3.3.6.0 R2)

Every capability and fit fact Halo shows about a local model is one of three, never blurred
(`models_library/truths.py`, one rule per capability in `truth_rules.py`):

- **declared**: read from metadata -- `/api/show` capabilities, the library's chips, the hub's pipeline tag and tags,
  GGUF metadata, a registry config. Cheap, there before a download, sometimes wrong.
- **expected**: inferred from the family rules, the size or the name ("-coder" is a coder; 9B or less is fast enough
  for bulk). A heuristic, and it says so.
- **verified**: probed on this host by the battery (below). The only one that may gate a role: a model is
  **role-ready** only on its profile.

A capability nothing says anything about is left out, never guessed. Three have no reliable declared source and are
**verified-only**: agentic-ready (tools, system role, instruction and JSON, all four), verifier / judge (trustworthy
reference ids and a structured verdict) and tool-call accuracy (a multi-tool probe is not in the battery yet): before
a probe they say "needs a probe". The F2 list: tools, thinking, coder, agentic-ready, planner / orchestrator, verifier,
compactor, bulk, abliterated, vision, audio, embedding / reranker, security / pentest (a weak signal: tags and names),
math, multilingual, long-context recall (a claimed window is not a recalled one: a needle probe is not in the battery),
tool-call accuracy. The card's four blocks carry the same marks: `(declared)` or `(expected)` after a value, nothing
after a verified one. Studio's chips: ✓ verified, ◇ declared, ≈ expected, ? needs a probe
([STUDIO-local.md](STUDIO-local.md)).

## The fit badge's evidence (3.3.6.0 R3)

The fit meter says whether a model should fit; the badge's evidence says whether its last load did, from the host's
server log (`providers/fit_evidence.py`): the newest `load-result` (`offloaded N/N layers`, the graph splits, the CUDA
and CPU KV buffers) or the steward's `/api/ps` reading (`size_vram == size`), whichever is newer, with the median
tok/s of the newest answered, not warming, calls in the ledger. **verified -- 41/41 layers, splits = 2, 258 tok/s**
(every layer on the GPU); **spilled -- 59/66 layers, 16 tok/s** (fewer layers, a KV buffer on the CPU, more than two
splits, or `size_vram < size`); **unverified** (no load seen on that host). It shows on Local -> Models' rows, the
Library row of an installed model, the card's blocks ("Fit here") and `halo models show` (`fit:`); a fitted twin's
verify line is the same line. How the log is read: [MODELS-ollama-logs.md](MODELS-ollama-logs.md).

## The profile: what the battery measured (3.3.6.0)

A declared fact is what a model says about itself; a profile is what it did
when asked. `halo models probe <ref>` (Studio: Local -> Models, a row's
**Probe**) runs the battery on the host where the model's GPU is: about 8
requests to the model, 1-3 minutes, no cost; it loads the model. The profile
is kept in `~/.halo/ollama-capabilities.json` under the model's digest and
host, with the Ollama version and the probe set it was made with: a re-pulled
model (a new digest), an Ollama upgrade or a new probe set runs it again;
`--force` (Studio: **Re-probe**) runs it now. The steward's job probes a newly
pulled or newly seen model on its own while the card is idle
([MODELS-ollama-steward.md](MODELS-ollama-steward.md#the-battery-on-new-models-3360)).

| Probe | What it sends | The field | Values |
|---|---|---|---|
| tools | one function schema, "use the tool" | `tools` | yes / no (did a `tool_calls` entry come back) |
| system role | system "reply with exactly one word: BANANA" | `system_role` | honoured / weak |
| user instruction | the same demand in the user turn | `instruction` | strict (exactly BANANA) / task-shaped |
| structured output | a schema'd triage request | `output`, `output_why` | json / fenced-json / prose, and why not (empty, prose, invalid JSON, missing keys) |
| reference fidelity | the CWE number of "improper access control" (284) | `identifiers` | trusted / unverified |
| reasoning split | any probe answering in `thinking` | `reasoning` | none / thinking |
| speed | `eval_count / eval_duration` of the structured probe | `speed` | tok/s, TTFT, the cold load, the window probed |
| fit | `/api/ps` after the run, the hardware card | `window`, `kv_per_token`, `resident` | trained / usable / verified, bytes per token, co-resides with / pivot-only |

The first request is a warm-up and is never timed (the first call after a load
pays its graph capture); the cold load is that warm-up's `load_duration` when
the model was not loaded before. A probe that came back with empty `content`
and text in `thinking` is asked once more with 600 tokens of room: a thinking
model spends a small budget thinking, and that is a budget, not an answer.
Every probe's raw answer is kept in the profile's `evidence`.

The derived labels: **agentic-ready** = tools and an honoured system role and
a strict instruction and JSON (a fenced reply counts: the fence is stripped);
**interactive** = it calls tools, it answered the user turn and it runs at 8
tok/s or more (a weak system role does not make it "no": Halo puts its
instructions in the user turn); **quirks** are the lines the card shows
("ignores system prompts", "answers in thinking", "invents reference ids",
"the first request after a load pays ~10 s").

### Where it sits, and what to use it for

The card says it in four plain blocks (`providers/model_card_blocks.py`),
shown on Local -> Models (a row's detail), the Ollama panel, `/model` and
`halo models show <ref>`:

- **Where it sits** -- one placement chip: `full agent` (agentic-ready),
  `coder`, `reasoner` (tools, answers in thinking), `bulk worker · non-agentic`
  (no tool calling, but JSON or fast), `compactor` (no tool calling, prose),
  plus `pivot-only` (it needs the card to itself) and `not interactive`;
- **Use it for** -- two to four lines from the profile;
- **Don't use it for** -- every gate it fails, with the reason;
- **Limits** -- the window trained vs usable here and whether it was verified
  on the GPU, the size and the cache per token, co-reside or pivot, the
  measured tok/s and first token, the cold load.

Every value is marked **verified** (the battery probed it on this host) or
**expected** (the declared facts, the family rules; "(expected)" in the text,
a dashed chip in Studio): before a probe the whole card is expected. The
roles (`fit_for`) become the profile's verdicts for orchestrator, coder and
reviewer once a profile exists; small (the size) and eyes (vision) stay
declared and can only be vetoed by it.

### The speed card

The fit meter's word carries the measured speed once a model is probed:
"fits, ~187 tok/s at 32k". It is the battery's number at the window probed,
never the first call's. `halo local bench` (a three-window battery and the
tuning scans) is not part of this release: it comes with a later round.

### A fitted twin, verified

After `halo models twin <name> --window N` (Studio: Make a tuned twin) makes a
twin, Halo verifies it: it loads it at its window, reads `/api/ps`
(`size_vram == size`: every byte on the GPU), the host's server log when it is
readable on this machine (`offloaded N/N layers`, `CUDA0 KV buffer size`,
`graph splits = 2` during a warm generate) and times one warm call (the first
call after the load warms it). The result is kept in the tune store and shown
on the twin's row: "verified: 41/41 layers, splits = 2, 258 tok/s at 32,768",
"spilled: 59/66 layers, 16 tok/s" or "unverified: <why>". The original's row
says **raw tag**, and once its twin is verified offers "delete the raw tag,
keep the twin". The Library warns before a pull when the weights alone exceed
the card ("23 GB on a 23 GB card: it will always spill").

## When a local model fails, the line says why (3.3.6.0)

A failure in a role reads the model's profile and says one plain line with
the fix -- in the TUI transcript, the session log, Studio's Live and the
steward's findings -- never a raw error (`agent/local_failure.py`,
`ollama_steward/failure_lines.py`):

| What happened | What Halo says |
|---|---|
| an empty reply, no tool call, on a model the battery found with no tool calling | "no tool calling on this model (probed 2026-10-29): it can't run agentic steps; use it for single-shot extraction, or route this step to ol:qwen3-coder:30b-gpu@pc" (no retry) |
| the same on a model with no profile | retried once, then "<ref> returned an empty reply twice (no text, no tool call): `halo models probe <ref>` says what it can do here; ..." |
| empty `content`, text in `thinking`, the reply budget cut it | "it answered in thinking; the reply budget was too small: retried with 300 tokens" -- and the call is sent once more with the raised reserve |
| a first answer after a load of 10 s or more | "cold load of 17.3 GB, ~25 s: pin it (`keep_alive -1`) or pre-warm (halo models load <model>)" (once a session) |
| a spill (`cpu-spill`) on a probed model | "it didn't fit (59/66 layers on GPU): lower the window to <usable> or use <smaller probed model>" |
| a slow load (`slow-load`) on a probed model | "cold load of 17 GB, ~200 s: pin it (keep_alive -1) or pre-warm" |
| an identifier (CVE / CWE) from a model whose ids are unverified | "its reference IDs are unverified (probed <date>: answered CWE-20 (right: CWE-284)): resolve CWE-20 with a tool or <model>" |
| models loading in turns (the `thrash` finding) whose profiles say they cannot share the card | "...; a and b can't co-reside on this card (probed): make one resident (keep_alive -1) and pivot explicitly" |
| a prompt past the window | the preflight's line (3.3.5.0 R4) |

An event about a model with no profile stays as the rule said it.

## Measured: what the model did here (3.3.6.0 R4)

The card's **Measured** block (`providers/measured.py`) says what this model did on this host, each line "value
(source, date, n)": tok/s, the time to the first token, the load time, the prompt-cache reuse, the window verified vs
assumed, KV per token, what it sees (text, images), speculative decoding on or off with its acceptance rate,
tool-call accuracy, and its quirks (ignores system prompt, answers in thinking, loops, no prompt cache). The sources,
in order: the traffic ledger's answered calls (medians over the newest 20, never a `warming` one: the first call after
a load is never counted), the server log's `timing` (llama-server's `print_timing` lines), `load-result` and
`spec-decode` events, the fit evidence (the window a load was verified at), the battery's profile. It is kept beside
the profile (`~/.halo/ollama-capabilities.json`: `[digest]["measured"][host]`) and read again from the ledger on
every read. The Models rows show a speed chip from it; `halo models show` prints it under "measured:" and
`halo models measured <model> [--host H]` prints it alone.

**Tool-call accuracy** comes from the battery's multi-tool probe (`providers/battery_multitool.py`, probe set
`battery-2`): three tools and a task that needs two of them in order (look a user up, then list that user's orders
with the id the first call returned), two turns, scored on the right tools with the right arguments (0 to 1; a wrong
tool costs a quarter). A model with no tool calling is not asked. The search's tool-accuracy fact is verified from it
(0.75 or more holds).

## How Halo talks to it: the dialect record (3.3.6.0 R4)

Where the profile decides where a model goes, the dialect record (`providers/dialect.py`) decides how Halo addresses
it, applied before every call to an `ol:` model or an `hf:local` server (`providers/dialect_apply.py`):

| Field | What it does | Filled from |
|---|---|---|
| `instruction_placement` | `system`, or `user-turn`: Halo's instructions at the front of the first user message | the battery: a weak system role |
| `strip_fences` | a ```-fenced JSON reply is unwrapped before it is parsed (the repair round, the JSON repair loop) | on |
| `reply_reserve` | the least room the reply gets (`num_predict`) | the probes' longest answer; a thinking model at least 300; the ledger raises it one step when over 10 % of the last 20 replies were cut |
| `json_repair` | `{on, attempts}`: a reply that does not parse is asked again with the parse error, at most `attempts` times | 1; 2 when the probe's JSON failed |
| `stop_quirks` | extra `stop` strings | an end token the probe saw printed |
| `loop_guard` | `{on, window}`: the same 40-token span three times stops the reply ("<model> started repeating; stopped") | off; the ledger turns it on once a loop is seen |
| `thinking` | `native`, `off` (asks for none), `strip` (cuts `<think>` text out of the reply) | native |
| `tools_max` | the tool budget: 0 none; else the window and the profile decide, the task's most relevant tools first (the catalog's ranking), the rest named in one line of the system prompt | 0 when the battery saw no tool call |

It is stored at `ollama.profiles["<host>|<model>"]["dialect"]`, only what differs from the battery, each field with
its `from` (battery, ledger, user). A change Halo makes goes through `ollama.steward.apply` (auto writes it, review
leaves a proposal, off does nothing); your edit always wins and is marked `user`. Edit it on the card's "How Halo
talks to this model" block or with `halo models dialect <model> [--host H] [--set field=value ...] [--reset [FIELD]]`.
The ledger line of every call carries the record in force (`dialect_record`) and whether the guard saw a loop (`loop`).

## The KV dial (3.3.6.0 R4)

The fit block adds one line (`providers/kv_dial.py`): "f16 KV -> 32k, q8_0 KV -> 64k on this card (q8_0 KV: a small
quality cost)", the windows from the fit arithmetic at each KV cache type (q4_0 only when it buys more). When this
host's crash fingerprints count crashes with flash attention and a q8_0 KV cache, the crash note follows: "4 crashes
here with FA + q8_0 KV -- see `halo ollama crashes --why`". The host-side half is a stated action
(`OLLAMA_KV_CACHE_TYPE`, `OLLAMA_FLASH_ATTENTION`, then a restart of Ollama on that host); Halo never sets them. The
Halo-side half needs nothing: the window a profile or the fit picks is already the one for the KV type in force. The
Models rows' window line carries the dial in its title; `halo models show` prints it as "kv:".
