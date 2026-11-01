# Commands: the steward's chat and candidates

Read this when you ask the steward a question from a terminal, or want the list of models that could run it.

Part of [Commands](COMMANDS.md), which lists every part.
What the chat reads, what its tools do and how its candidates are ranked is in
[MODELS-ollama-steward-chat.md](MODELS-ollama-steward-chat.md). Exit codes: 0 done, 1 could not (the reason
printed), 2 usage.

## `halo ollama steward chat`

```sh
halo ollama steward chat "why is the card on pc busy?"
halo ollama steward chat "give the 27B's replies more room" --json
halo ollama steward chat "what should I do about the spill?" --bigger      # the session's main model, once
halo ollama steward chat "..." --bigger --yes                              # no question before the call
```

One turn of the steward's chat, the conversation Local -> Steward shows. The steward's own model
(`ollama.steward.model`, else the best candidate) reads the job's context and the hosts' findings, may use its tools,
and answers. The terminal prints each tool it used (`[card] Hardware of 'pc' ...`), the answer, each button's command
(a retire, a download, a bench or the battery: the line to run), then the model and the cost:

    The 27B on pc spills: ComfyUI holds 2.0 GiB of the card.
    (ol:qwen3.5:9b@pc: local, 4 s)

`--bigger` prints what the call costs first ("ask or:vendor/model once: ~3,412 tokens in -- about $0.0104 at
or:vendor/model's catalog price") and, in a terminal, asks before it sends; it is the one way the chat calls the
session's main model. `--json` prints the whole answer: `{answer, model, cost, seconds, tools, buttons, left_out,
context_tokens, usage}`. Every turn is a row of `<state>/ollama/steward-chat.jsonl`, the same log Studio shows.

## `halo ollama steward candidates`

```sh
halo ollama steward candidates
halo ollama steward candidates --host pc --json
```

The models that could run the steward here, best first, one row each with why; `*` marks the one the steward runs
on, and the last line says which and where that came from:

    candidates to run the steward on this machine: qwen3.5:9b (fits beside qwen3-coder:30b, 6.4 GB, tool calls verified, 95 tok/s), ...
      * ol:qwen3.5:9b@pc: fits beside qwen3-coder:30b, 6.4 GB, tool calls verified, 95 tok/s
      - ol:qwen2.5:1.5b@pc: fits beside qwen3-coder:30b, 1.1 GB, tool calls not probed
    the steward runs on: ol:qwen3.5:9b@pc (ollama.steward.model)

With nothing installed that fits, the rows are known-good small models to download, each with its size, its minutes
and its pull line; nothing downloads here. `--json`: `{candidates, chosen, why}`.
