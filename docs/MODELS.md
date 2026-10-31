# Models

Read this when you need the exact behaviour of a model route: how a model name resolves, what each provider sends, the catalogs and the prices.

How a `--model`/`/model` string resolves to a real upstream call, per-family
request-shaping rules, the model catalogs and how they refresh, and pricing.
Verified against `halo_harness/model.py`, `providers/profiles.py`,
`providers/anthropic_aliases.py`, `providers/dbx_routing.py`, and
`providers/model_table.json`.

**New to local or cloud models?** [docs/LOCAL-MODELS.md](LOCAL-MODELS.md)
is the end-to-end walkthrough (commands, setup, known limits) for
Ollama, Hugging Face and the OpenAI API; this page's parts stay
the exhaustive reference for every route's exact wire behavior.

This page is the entry point; the content lives in the parts below, one per task.

## The parts

| Part | Read it when | What is in it |
|---|---|---|
| [Models: references, picks and provider enablement](MODELS-references.md) | you type a model name or prefix (`or:`, `dbx:`, `ant:`, `oai:`, `ol:`, `hf:` ...), choose a model for a job, or turn a provider on or off | Model reference forms · Which model for what (Halo 3.0.1.0) · Provider enablement |
| [Models: Ollama hosts, requests and the catalog](MODELS-ollama.md) | you point Halo at an Ollama host and want to know what it sends, how context is sized and how the host is checked | Ollama |
| [Models: Ollama fit, calibration and the gym](MODELS-ollama-tuning.md) | a local model does not fit, calls tools badly, or you want `halo gym` scores and role defaults for your GPU | Ollama: fit, calibration and the gym |
| [Models: switching models and effort on a local model](MODELS-switching.md) | you move a session from one model to another (`/model`, a lineup's per-task pick, a resumed session, a compaction model) or wonder what the effort level does on a local model | Switching models (3.3.5.0) · Effort on a local model |
| [Models: what a local model can do](MODELS-cards.md) | you pick a local model and want to know what it is (thinking, tools, vision, coding or embedding), how Halo will call it, whether it fits this machine, and what to do when it cannot run the main agent | The model card (3.3.5.0) · The fit meter · When the main model cannot orchestrate · Effort on THIS model · The steward knows the card · Measured · The dialect record · The KV dial · The speed card: the bench |
| [Models: which models can see](MODELS-vision.md) | you want to share a screenshot or an image with a model and need to know which models can see, how Halo knows, and what happens when the model in use cannot | Which models can see (3.3.6.0 R6) · The vision probe · What a turn with an image does |
| [Models: what Halo sends a local model](MODELS-prompt-budget.md) | a local model answers as if it never saw the task, you want to know what a request to a model is made of in tokens, or a request is larger than the model's window | What Halo sends a local model (3.3.5.0): the composition, the lean profile, the preflight, the prompt cache, warm-up truth |
| [Models: the Ollama steward](MODELS-ollama-steward.md) | you want to know what the Ollama steward knows, records, finds and changes across your halos and model servers | The steward (3.3.4.0) · Scopes: when a change goes back |
| [Models: the steward and the host](MODELS-ollama-steward-host.md) | the model you tune is served by a `halo host` and you want to know where the steward runs, how its fixes land on that host and what comes back | Three homes, one vocabulary (3.3.7.0 R2) · Landing through the host · What a peer's steward reads from the host |
| [Models: the Ollama server log](MODELS-ollama-logs.md) | you want to know how Halo reads an Ollama host's server log, whether that log is live, how the log drives a call's recovery, what a crash fingerprint holds and what Halo proposes when a crash repeats, how a failed local call walks the degradation ladder, what the answer post-mortem reads and how the model shelf retires a model | Logs (3.3.6.0 R3) · The degradation ladder · The post-mortem's sources · The model shelf |
| [Models: Hugging Face](MODELS-huggingface.md) | you use the Hugging Face router, a dedicated endpoint, or a local llama-server, LM Studio or MLX server (`hf:`) | Hugging Face |
| [Models: the OpenAI API](MODELS-openai-codex.md) | you use `oai:` with an OpenAI key | OpenAI API |
| [Models: Experiential Labs](MODELS-experiential.md) | you route models through the Experiential Labs gateway (`xp:`) | Experiential Labs · How to run the 2.0.4 "new labs" models |
| [Models: families, Qwen and reasoning effort](MODELS-families.md) | a model family behaves differently (DeepSeek, Kimi, GLM, Qwen) or you set the reasoning effort | Families and their rules · Purpose words (the model card) · Qwen at work · Reasoning effort |
| [Models: the catalog, prices and the picker](MODELS-catalog.md) | you refresh the model list, read a price or DBU cost, use the `/model` picker, or go offline | The model table, catalogs, and refresh · Pricing and DBUs · The `/model` picker · Enforced offline mode (Halo 2.0.3 round 5e) · Hybrid escalation (Halo 2.0.3 round 5e) · Saved versus cloud (Halo 2.0.3 round 5e) |
