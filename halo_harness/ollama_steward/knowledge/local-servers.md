# The other local servers: llama-server, mlx_lm.server, LM Studio, vLLM

Read this when a local model is served by something other than Ollama, or you need the llama-server behaviour underneath Ollama.

## llama.cpp's llama-server

| Flag | Default | What it does |
|------|---------|--------------|
| `-c, --ctx-size N` | 0 = the model's trained context | the whole KV cache in tokens, shared by the slots [S12] |
| `-np, --parallel N` | -1 = automatic | the number of slots (requests served at once) [S12] |
| `-ngl, --gpu-layers N` | auto | layers kept on the GPU: a number, `auto` or `all` [S12] |
| `-fit, --fit on/off` | on | adjusts options left unset (layers, window) to the free device memory [S12] |
| `-fitt, --fit-target MiB` | 1024 | the margin `--fit` keeps free per device [S12] |
| `-fitc, --fit-ctx N` | 4096 | the smallest window `--fit` may choose [S12] |
| `-ctk, --cache-type-k` / `-ctv, --cache-type-v` | f16 | the KV cache type: f32, f16, bf16, q8_0, q4_0, q4_1, iq4_nl, q5_0, q5_1 [S12] |
| `-fa, --flash-attn on/off/auto` | auto | flash attention [S12] |
| `--context-shift` | off | when the window fills during a reply, drop old tokens and keep writing [S12] |
| `--keep N` | 0 | tokens of the prompt's start that a context shift keeps [S12] |
| `-cram, --cache-ram N` | 8192 MiB | the prompt cache kept in system RAM between requests [S12] |
| `--metrics` | off | turns on `/metrics` [S12] |
| `--slots` | on | turns on `/slots` [S12] |

- `GET /health` answers 503 with "Loading model" while the model loads and 200 `{"status": "ok"}` once it is ready. [S12]
- `GET /slots` lists each slot's state and its `n_ctx`; `GET /metrics` (with `--metrics`) gives Prometheus counters: prompt and generated tokens, their speeds, requests processing and deferred, and the high-water mark of the context. [S12]
- A prompt as long as the slot's window or longer is refused: "request (N tokens) exceeds the available context size (M tokens), try increasing it". [S13]
- When the window fills during a reply with context shift off, the reply stops, the slot logs "truncated = 1" and the finish reason is "length"; with context shift on, half of the remaining old tokens are dropped ("slot context shift, n_keep = ..., n_discard = ...") and the reply goes on. [S13][S15]
- Context shift is turned off by the server itself for a multimodal model and for a model whose memory cannot shift (the hybrid models' recurrent state). [S13]
- When the KV cache has no free cell for a batch, decoding logs "failed to find a memory slot for batch of size N" and the request ends with "Context size has been exceeded.". [S13][S14]
- The result of a `/completion` call carries `truncated`, true when the prompt plus the reply ran past `n_ctx`. [S12]
- Ollama 0.40.x is a manager over this same server: it picks `-c`, `-np`, the cache type and flash attention, and leaves `-ngl` and the rest to `--fit` unless `num_gpu` is set. [S4]

## mlx-lm's `mlx_lm.server` (a Mac)

- `mlx_lm.server --model <path or Hugging Face repo>` serves an OpenAI-like API on 127.0.0.1:8080; its own doc says it is not meant for production. [S17][S18]
- Its flags include `--max-tokens` (default 512, the reply length when a request sends none), `--decode-concurrency` (32), `--prompt-concurrency` (8), `--prefill-step-size` (2048), `--prompt-cache-size` (10 caches), `--prompt-cache-bytes`, `--kv-bits` (quantized KV cache; turns batching off), `--kv-group-size` (64), `--draft-model` and `--num-draft-tokens`. [S18]
- It has no window flag: a request's cache is made with `make_prompt_cache(model)` and no size, so it grows with the conversation, and the prompt cache keeps up to 10 caches unless `--prompt-cache-bytes` caps their bytes. [S18]
- A reply's `finish_reason` is "stop" or "length", and `usage` carries `prompt_tokens`, `completion_tokens` and `total_tokens`; `GET /v1/models` lists the models. [S17]
- At start it raises the wired memory limit to the recommended size; a model close to that size is slow and the fix is `sudo sysctl iogpu.wired_limit_mb=N`. [S19][S20]

## LM Studio's server

- It answers on port 1234 in its own examples, with the OpenAI paths and its own REST API under `/api/v0` (LM Studio 0.3.6 or newer). [S22][S23]
- `GET /api/v0/models` lists each model with `state` ("not-loaded" or loaded), `max_context_length`, `quantization` and `arch`; a chat answer adds `stats` with `tokens_per_second`, `time_to_first_token`, `generation_time` and `stop_reason`. [S23]
- JIT loading loads a model on its first request; a JIT-loaded model unloads after 60 idle minutes by default (a request's `ttl` field changes it), and Auto-Evict (on by default) unloads the previous JIT model before loading a new one. [S22]

## vLLM (the basics)

- `--gpu-memory-utilization` (default 0.92) is the share of the GPU one vLLM instance takes for weights and cache, whatever else runs on the card. [S24]
- `--max-model-len` is the window (prompt and reply); `auto` or -1 picks the largest that fits. `--kv-cache-dtype` defaults to the model's own type. [S24]

## What Halo already reads from these servers

- On the OpenAI path each reply carries `usage` (prompt and completion tokens) and a `finish_reason`; "length" means the reply was cut by the reply limit or the window, the same as Ollama's `done_reason: length`. [S9][S17][S15]
- Ollama's native reply carries `prompt_eval_count`, `eval_count`, `done_reason` and the durations, the fields the traffic ledger records. [S9]
