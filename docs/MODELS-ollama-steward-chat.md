# Models: the steward's chat and its candidates

Read this when you want to ask the steward about your local models in plain words, see what its answer cost, let it make a Halo-side change, or choose the small model it runs on.

Part of [Models](MODELS.md), which lists every part.

## The chat (3.3.7.0 R5)

Local -> Steward has a chat box to the steward's own small model (`ollama_steward/chat.py`; `halo ollama steward chat
"<question>"` from a terminal, [COMMANDS-ollama-chat.md](COMMANDS-ollama-chat.md)). It is the 3.3.4.0 steward agent run
as a conversation: it reads what the steward's job reads -- the hardware cards, the calls per model, the server
events, the findings (a paired halo host's own folded in, its ids kept), the fit plans -- plus the reservations, the
bundles' verdicts and the roster adviser's top suggestions with their ids, and the last few turns. It answers in
plain words, with only the numbers it was given or a tool returned.

Each round the model answers one JSON object: `{"tool": <name>, "args": {...}}` to use a tool, or `{"answer": ...}`;
at most four rounds a question. The tools (`ollama_steward/chat_tools.py`):

| Tool | What it does |
|---|---|
| `card`, `ledger`, `events`, `profiles`, `speed`, `findings` | read the host's card (with what is reserved), the calls per model, the server events, the profiles and battery profiles, the speed cards, the findings with their ids |
| `knowledge` | what an alert kind or a topic means (the steward's knowledge, `halo ollama explain`) |
| `bundles`, `advice` | each bundle's verdict; the adviser's suggestions with their `adv-...` ids |
| `busy`, `refresh` | why the card is busy (or since when it is idle; the clients that are not a halo); what the off-hours refresh does tonight |
| `propose` | one Halo-side profile change -- a field of `num_ctx`, `num_predict`, `keep_alive`, `tools_max`, `host_for`, `compact_at` -- citing a finding's id |
| `apply` | an adviser suggestion you named: `point` lands (the role write); `retire` and `add` become a button |
| `bench`, `battery` | a benchmark or the capability battery on a model: a button |

The chat acts within the duty steward's bounds: Halo-side fields only, one change per answer, a cited finding; the
change goes through the same guarded path as the job's (the measured cap, the card's fit, ten minutes per model,
`ollama.steward.apply`'s mode; a model a halo host serves lands through the host, which verifies it). A change the
chat lands is kept (you asked for it); `halo local changes` lists it and `halo local revert` puts it back. Retiring a
model, downloading one, a bench and the battery cost more, so the chat leaves a button that names the one thing it
does and what it costs (the shelf's uses card for a retire, the size and minutes for a download); the CLI prints the
command instead. Nothing runs until it is pressed.

Every row -- the question, each tool and what it answered, each button, the answer -- goes to the steward's own
session log, `<state>/ollama/steward-chat.jsonl`. Each answer carries its cost: "local, 4 s" for a local model (time,
no tokens leave the LAN), the dollars for a priced cloud model, the tokens when no price is known.

## The context and its budget

The context is held under `ollama.steward.chat_tokens` (6,000 by default: a 9 B steward at an 8 k window with room
for its answer). The findings, the reservations, the adviser, the cards, the calls and the events are added in that
order; when the budget is short the events go first, then the calls, then the cards, and the answer's row says what
was left out.

## Ask a bigger model

"Ask a bigger model..." says what it costs first -- "ask or:vendor/model once: ~3,412 tokens in -- about $0.0104 at
or:vendor/model's catalog price" (`halo ollama steward chat --bigger` prints the same and asks in a terminal) -- then
sends the same context once to the session's main model (the configured `model`): one call, no tools, its row
marked `bigger`. Nothing else in the chat ever calls the main model.

## The candidates

`ollama_steward/candidates.py` lists the models that could run the steward here, best first: tool calls verified by
the battery first, then fits beside the main model (the weights plus the KV at 8 k, beside main at its window, the
reservations counted), then the measured speed, then the smaller. Each says why:

    candidates to run the steward on this machine: qwen3.5:9b (fits beside qwen3-coder:30b, 6.4 GB, tool calls
    verified, 95 tok/s), qwen2.5:1.5b (fits beside qwen3-coder:30b, 1.1 GB, tool calls not probed), ...

With nothing installed that fits, the known-good small models of the library snapshot that would (qwen3.5:9b,
qwen3:8b, qwen3.5:4b, llama3.2:3b) are listed with their download size and minutes. The steward's model
(`agent.choose_model`) is `ollama.steward.model`, else a local `compactionModel`, else the best installed candidate
(its why said), else the smallest local model. `halo ollama steward candidates` prints the list; the Steward page's
picker has Use on each installed one (it writes `ollama.steward.model`); the first-run checklist has a "Steward
candidates" row -- on by default when an installed one fits and none is set, off when only a download would do (the
row names the download; ticked and run, it pulls that one, then sets it). A cloud model is never picked here.
