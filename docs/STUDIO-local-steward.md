# Studio: Local -> Steward

Read this when you talk to the steward from Studio, choose the model it runs on, or press a button its answer left.

Part of [Halo Studio](STUDIO.md), which lists every part. The other Local pages are in
[STUDIO-local.md](STUDIO-local.md); what the chat reads and does is in
[MODELS-ollama-steward-chat.md](MODELS-ollama-steward-chat.md).

## The Steward page (3.3.7.0 R5)

Local's eighth page, built in 3.3.7.0 R5 from the frame it had since 3.3.5.0, holds four blocks:

- **The steward now**: the steward job's status line and its last note (the Ollama panel's steward block, read the
  same way: `GET ollama/steward`).
- **Talk to the steward**: the chat box (below).
- **The steward's model**: the candidates (below), open while none is chosen.
- **The off-hours refresh** (3.3.7.0 R4): tonight's plan, the last run, the last roster review.

## The chat box

Its head names the model the steward runs on and why ("ol:qwen3.5:9b@pc: ollama.steward.model"). Type a question --
"Why is the card busy?", "What does the refresh do tonight?", "Make the 27B fit" -- and press **Ask** (or Enter).
The conversation shows each question, each tool the model used as one muted line (`[card] Hardware of 'pc' ...`,
amber when the tool refused), each button an answer left, and each answer with its cost chip ("local, 4 s", or the
dollars of a cloud model). A button names its one thing and its cost -- "Retire qwen3.6:27b from pc", "Download and
verify nomic-embed-text (0.3 GB, ~1 min)", "Bench qwen3.8:27b on pc", "Probe ... on pc" -- with its terminal line
beside it, and posts to the route that already does that one thing; nothing runs until it is pressed.

**Ask a bigger model...** first reads what the call costs (`GET local/steward/bigger-cost`: "ask or:vendor/model
once: ~3,412 tokens in -- about $0.0104 at or:vendor/model's catalog price") and shows it with **Ask it** and
**Cancel**; Ask it sends the same context once to the session's main model, whose answer is marked "main model".
The conversation is the steward's own session log, `<state>/ollama/steward-chat.jsonl`; `halo ollama steward chat`
writes to the same log.

## The model picker

One row per candidate, best first, each with why (fits beside the main model, its size, tool calls verified, its
measured speed); "in use" marks the steward's model; **Use** on an installed one writes `ollama.steward.model`. With
nothing installed that fits, the rows are known-good small models to download, each with its pull line.
`halo ollama steward candidates` prints the same list.

## The routes

| Route | What it does |
|---|---|
| `GET local/steward/chat` | the log's last rows, the steward's model and why |
| `POST local/steward/chat {question, bigger?}` | one turn: `{answer, model, cost, seconds, tools, buttons, left_out, context_tokens, usage}` (409 when no model can answer) |
| `GET local/steward/bigger-cost?question=` | `{model, tokens, line}`: what "ask a bigger model" costs |
| `GET local/steward/candidates` | `{candidates, line, chosen, why}` |
| `POST local/steward/model {model}` | the picker: `ollama.steward.model` |

The routes are `halo_harness/studio/local_steward_chat_api.py`; the page is `ui/src/routes/local/StewardPage.tsx`,
`StewardChat.tsx`, `StewardModel.tsx` and the slice `chatstore.ts`.
