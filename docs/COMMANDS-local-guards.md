# Commands: refresh, advise and the guards

Read this when you re-measure stale local models by hand, ask Halo what to add or retire, or point a role at the nearest equivalent of a deleted tag.

Part of [Commands](COMMANDS.md), which lists every part.
Exit codes: 0 done, 1 could not (the reason on stderr), 2 usage. What the guards are is in
[MODELS-ollama-steward-guards.md](MODELS-ollama-steward-guards.md); the adviser in [MODELS-adviser.md](MODELS-adviser.md).

## `halo local refresh`

```sh
halo local refresh [--dry] [--host H] [--json]
```

Halo 3.3.7.0 R4. For a machine with no `halo host` (on one, the host does it off-hours: `halo host refresh`): the
plan -- drifted tags first, then never probed, then the profiles older than `host.refresh.max_age_days` -- then each
model in turn, the capability battery and the quick bench, stopping the moment a call arrives (a ledger call, a
session on the card, a foreign model), each line saying what it measured and what it stamped. `--dry` prints the plan
and the minutes and runs nothing; `--host` takes one Ollama host.

## `halo local advise`

```sh
halo local advise [--host H] [--lineup L] [--json]
```

Halo 3.3.7.0 R4: the roster adviser's lines, ranked by value per gigabyte, each `[gap|overlap|mismatch|freshness]`
with what it unlocks or frees, what it costs and the one command that does it (`ollama pull ...`, `halo models retire
...`, `halo roles point ...`). It runs nothing. `--lineup` reads that lineup's roles instead of the active one.

3.3.8.0 R4: a fifth kind, `[placement]` -- a lane a cheaper candidate across the fleet would serve, both scores and
what each costs to place ("compactor (qwen3.5:9b) on pc scores 75 (evicts qwen3-coder:30b, pivots beside
qwen3-coder:30b); sagan scores 116 (18 s to load)"; `halo local place --apply` moves it) -- and under the lines the
**placement scores**: each lane's score on every candidate (every paired host's card, the pool), the chosen host
first, each with its loading tax (the load seconds, what it evicts or pivots beside, not pulled there, the pool's
decode penalty). When a far card changes (a paired host's residency: a model loaded or unloaded there), the steward's
job places the lanes it carries again and says each move in one line; nothing moves until `--apply`.

## `halo roles point`

```sh
halo roles point <role> <model> [--json]
```

Halo 3.3.7.0 R4: `roles.<role>` in config.json becomes `<model>` (a role written as `{model, effort}` keeps its
effort) -- the dead-tag line's "point the role at it" and the adviser's point suggestion. Halo-side only: nothing is
pulled and nothing loads. Studio's button sends `POST roles/<role>/point {to}`.

## `halo models probe hf:local/<model>`

```sh
halo models probe hf:local/<model>[@server] [--json]
```

Halo 3.3.7.0 R4: the battery's vision probe on a Hugging Face local server -- one 1 px image as an `image_url` to
`/v1/chat/completions` where the endpoint takes one (llama-server started with `--mmproj`, LM Studio's vlm models,
MLX-VLM), "not asked" with the reason elsewhere (mlx-lm, vLLM, TGI, a server that says nothing about images). The
answer is kept where the model card reads its vision ("reads images (verified: the battery's image probe ...)").
