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

## The pool's findings

The pool's controller is a llama-server whose log carries llama.cpp's RPC lines. Three findings read them, one line
each, keyed `pool|<model>` [S50]; the RPC failure lines are the event kind `rpc-lost` (an error). pool-degraded: an RPC backend was lost mid-generation ("Remote RPC server crashed or
returned malformed response", "Failed to connect to <addr>"); the request failed once and is not retried; start the
worker's rpc-server again, then Warm the pool. pool-rtt: the replies run under three quarters of the pool's own speed
card and slower than the round trips explain; a pooled decode waits one round trip per RPC device per token, so a
Wi-Fi member, a shared card or a throttled worker shows here [S49]. pool-spill: a node holds less than its split's
share of the weights, or layers stayed on the controller's CPU; its free VRAM fell after the preflight, so Stop and
Warm again re-reads it [S50].

## Speech servers

Halo's own speech server (`halo local serve --stt` or `--tts`) is a local server of runtime `voice-stt` or `voice-tts`: its log holds one line per load and one per request, and four findings read them, keyed `stt|<model>` or `tts|<model>`, each with a stated fix that is never applied by itself [S51]. A fifth, `voice-slow`, reads the voice loop's own latency cards (`<state>/voice/turns.jsonl`), keyed `voice|<stage>` [S52].

| Kind | Symptom | Cause | Halo-side change | Server-side recommendation |
|------|---------|-------|------------------|----------------------------|
| `stt-slow` | "voice stt: audio 4.2 s -> text in 3.1 s (1.4x realtime)" | the transcription runs under 2x realtime: a large model on the CPU, or a GPU the chat model keeps busy | none: the turn waits on the transcript | `halo local serve --stt <model> --device cuda` when the GPU has the model's footprint free, else a smaller built model such as faster-whisper:small.en (costs: VRAM beside the chat model, or some accuracy) [S51] |
| `tts-slow` | "voice tts: ... first audio 650 ms" | the first sentence takes over 400 ms to speak: the CPU, or a model larger than Kokoro-82M | none: R2's sentence aggregator sends the first sentence alone | `halo local serve --tts <model> --device cuda` when the GPU has its footprint free, else kokoro-82m (costs: VRAM, or the cloned voice) [S51] |
| `voice-cpu` | "voice load: stt ... on cpu ...; the GPU had 22,000 MiB free" | the speech model loaded on the CPU while the GPU had its footprint free (asked, or auto saw no CUDA) | none: a bundle may keep speech on the CPU on purpose, so the chat model keeps the VRAM | `--device cuda` on the next serve moves it (costs: its GPU footprint, 0.3 to 1.5 GB) [S51] |
| `voice-load-failed` | "voice load failed: stt ... on cuda: ..." | the engine could not load the model: the extra not installed, a CUDA library missing, or files that are not the ones the engine loads | none | the install line (`uv tool install --reinstall "halo-harness[voice]"`), `--device cpu`, or `halo voice download <model>` again (costs: minutes, the download's GB) [S51] |
| `voice-slow` | "voice: 1.9 s, over the 1.5 s budget (heard 0.2 · text 0.9 · token 0.4 · audio 0.1) -- slow: text", three turns running | one stage of the voice loop ran over its share of the budget (heard 20 %, text 25 %, token 40 %, audio 15 %) three turns running: text is the STT, token the chat model (loading), audio the TTS, heard the VAD | none: the turn keeps its budget | text: `--device cuda` or `faster-whisper:small.en`; token: a voice bundle's reservation keeps the chat model resident (`halo pack on voice-local`); audio: Kokoro on the CPU is ~100 ms, check `tts-slow`; heard: `halo voice download silero-vad` (costs: VRAM beside the chat model, a restart in seconds, or ~1.2 GB held) [S52] |

## FreeToken

FreeToken (`ft serve`, Linux x86_64 with an NVIDIA driver r580+ and nvcc) serves a large Mixture-of-Experts model on one machine: with its default `offload` strategy the routed experts live in host RAM, an LRU cache of expert slots sits on the GPU, and each miss streams over PCIe (about 32-64 GB/s; NVLink-C2C about 450 GB/s); the first request after an install JIT-compiles its CUDA kernels; under WSL CUDA pinned memory is capped near half of RAM [S53]. Halo runs it as the runtime `freetoken` (`halo local serve --runtime freetoken`, entry `freetoken`), reads its log with these patterns unverified until a live log, and three findings read it, keyed `<server>|<model>`, each with a stated fix never applied by itself [S54].

| Kind | Symptom | Cause | Halo-side change | Server-side recommendation |
|------|---------|-------|------------------|----------------------------|
| `ft-expert-thrash` | "MoE decode, pinned 40 layers: hit 31.0%, per layer-step miss 5.52 ..." (with `--moe-collect-stats`, which Halo's launch passes) | the expert cache misses most experts a decode step asks for: each miss crosses the host link, so the link is the limit | none: the decode speed is the link's | a smaller model, a bigger cache share (`ft ctl cache --moe N` resizes the pool live; costs: VRAM from the KV cache), or NVLink-class hardware [S53][S54] |
| `ft-pinned-cap` | "--moe-cpu-layers auto: banks 60.00 GiB > pin budget 25.60 GiB; locking 22 head+tail MoE layers for CPU decode", or "expert banks need ... of pinned host RAM but the pin budget is ..." | under WSL the expert banks did not all pin (FreeToken budgets 40 % of RAM there): the rest decode on the CPU, slower, or the load stops | none | run FreeToken on native Linux, or a smaller checkpoint (costs: a reboot into Linux, or a smaller model's quality) [S53][S54] |
| `ft-kernel-jit` | "Prefill warmup complete for lengths [1, 8192] in 312.480 s", or the first call after a load running for minutes | the first use after an install compiles FreeToken's CUDA kernels; a toolchain that is not CUDA 13 fails to compile them | none: the session's wait for a FreeToken server allows it | nothing when it compiled; when it failed, install the CUDA 13 toolkit with nvcc on PATH (costs: a few GB, once) [S53][S54] |
