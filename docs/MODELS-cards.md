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
