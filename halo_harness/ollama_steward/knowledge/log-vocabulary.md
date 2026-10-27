# Ollama's server log, line by line

Read this when you read an Ollama server.log and want to know what a line means and what to do about it.

Examples are real lines of the measured host's log (Ollama 0.40.6 on Windows) with the client address replaced by a 192.0.2.x placeholder and the user folder by `example`; where a line never appeared there, the example is built from the source line that prints it. [S30]

## Where the log is

- Windows: `%LOCALAPPDATA%\Ollama\server.log`, the newest; older runs are `server-1.log`, `server-2.log` and so on beside it. [S8]
- macOS (the app): `~/.ollama/logs/server.log`. [S8]
- Linux with systemd: the journal, `journalctl -u ollama --no-pager`; every line then carries the journal's own date and `ollama[pid]:` prefix. [S8]
- A container: its stdout and stderr (`docker logs <name>`); `ollama serve` in a terminal: that terminal. [S8]
- A new server process starts a new block in the same file; only the newest block describes the server that runs now. [S5][S30]

## The startup block (the server's settings and its devices)

| Line | What it means | Example |
|------|---------------|---------|
| `msg="server config" env="map[...]"` | every server setting, `NAME:value` pairs; an empty value means unset (the default applies) [S2][S5] | `OLLAMA_FLASH_ATTENTION:true ... OLLAMA_KEEP_ALIVE:30m0s OLLAMA_KV_CACHE_TYPE:q8_0 ... OLLAMA_MAX_LOADED_MODELS:0 ... OLLAMA_NUM_PARALLEL:1` [S30] |
| `msg="Listening on [::]:11434 (version 0.40.6)"` | the address and the server's version [S5] | `Listening on [::]:11434 (version 0.40.6)` [S30] |
| `msg="inference compute" id=0 library=CUDA ... description="..." ... total="22.5 GiB" available="21.0 GiB"` | one line per usable device: its id, library (CUDA, ROCm, Vulkan, Metal, cpu), name, driver, type (discrete or iGPU), total and free memory at start [S10] | `id=0 filter_id=0 library=CUDA compute=8.9 name=CUDA0 description="NVIDIA GeForce RTX 4090" ... type=discrete total="22.5 GiB" available="21.0 GiB"` [S30] |
| `msg="inference compute" id=cpu library=cpu` | no usable GPU: the server runs on the CPU [S10] | built from the source line [S10] |
| `msg="dropping integrated GPU; to enable, set OLLAMA_IGPU_ENABLE=1"` | an integrated GPU was found and left out [S2][S30] | `description="AMD Radeon(TM) Graphics"` [S30] |
| `msg="vram-based default context" total_vram=... default_num_ctx=...` | the window used when a request sends no `num_ctx` and `OLLAMA_CONTEXT_LENGTH` is unset [S5] | `total_vram="22.5 GiB" default_num_ctx=4096` [S30] |

## A load

| Line | What it means | Example |
|------|---------------|---------|
| `msg="starting llama-server" cmd="... -c 32768 -np 1 ... --cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on ..."` | the runner's real options: `-c` is the window times the slots, `-np` the slots, `-ngl` appears only when `num_gpu` was set [S4] | `-c 32768 -np 1 ... --cache-type-k q8_0 --cache-type-v q8_0 --flash-attn on -b 512 -ub 512 --context-shift --keep 4` [S30] |
| `msg="system memory" total=... free=...` and `msg="gpu memory" ... available=... minimum=... overhead=...` | the memory the scheduler places this load against [S3] | `available="20.6 GiB" free="21.0 GiB" minimum="457.0 MiB" overhead="0 B"` [S30] |
| `common_memory_breakdown_print: ... total = free + (self = model + context + compute)` | llama.cpp's table, in MiB: the weights, the window's caches and the compute buffer one device needs [S12][S30] | `23027 = 20756 + (17435 = 15339 + 1836 + 260)` [S30] |
| `common_params_fit_impl: ... 49 layers ( 3 overflowing), 20442 MiB used, 1063 MiB free` | `--fit` moved part of 3 layers to system RAM to keep its margin [S12][S30] | as quoted [S30] |
| `load_tensors: offloaded 49/49 layers to GPU` | how many layers have their main tensors on the GPU; with overflowing experts it can read a/a while some weights are in RAM [S12][S30] | `offloaded 66/66 layers to GPU` [S30] |
| `llama_kv_cache: size = 1088.00 MiB ( 32768 cells, 16 layers, ...)` | the KV cache: the window, the layers that hold one, the type [S30] | `K (q8_0): 544.00 MiB, V (q8_0): 544.00 MiB` [S30] |
| `llama_memory_recurrent: size = 748.13 MiB` | the fixed state of a hybrid model's linear-attention layers; it does not grow with the window [S30] | `( 1 cells, 64 layers, 1 seqs 4 rs_seq)` [S30] |
| `msg="llama-server started in 4.27 seconds"`, `msg="loaded runners" count=1` | the load finished; how many models are loaded now [S3][S4] | as quoted [S30] |
| `msg="llama-server model predicted to exceed available memory, evicting"` | a second model does not fit beside the loaded ones; one is unloaded first [S3] | `predicted="22.4 GiB" predicted_num_ctx=32768 ... available="2.0 GiB"` [S30] |
| `msg="llama-server model fits alongside existing models"` | the second model loads beside the first [S3] | built from the source line [S3] |
| `msg="client connection closed before llama-server finished loading, aborting load"` | the client gave up while the model loaded; the load is thrown away [S4] | as quoted [S30] |
| `msg="Load failed" model=... error="timed out waiting for llama-server to start: context canceled"` | the load did not finish: `context canceled` is the client's abort, other errors are the runner's own [S3][S4] | as quoted, after the abort line [S30] |
| `msg="llama-server load failed; reducing automatic context and retrying once"` | an out-of-memory load is tried again with a smaller automatic window [S3] | built from the source line [S3] |
| `msg="runtime OOM detected; expiring loaded models to clear memory before next request"` | the GPU ran out of memory while serving; loaded models are unloaded [S3] | built from the source line [S3] |

## A request

| Line | What it means | Example |
|------|---------------|---------|
| `[GIN] ... \| 200 \| 7.0006466s \| 192.0.2.x \| POST "/api/chat"` | one HTTP request: status, time taken, client, route [S30] | as quoted [S30] |
| status `499` | the client closed the connection before the answer; during a load this aborts the load [S4][S30] | `\| 499 \| 4.2862269s \| 192.0.2.x \| POST "/api/chat"` [S30] |
| status `500` | the request failed; on the measured host 16 of 21 followed a "chat prompt error", and 4 of the other 5 sit next to "srv stop: cancel task" (a stopped reader cancels its unfinished task): requests ended while their prompt (up to 44,000 tokens) was still being read or the slot was busy, logged as 500, not 499 [S5][S30][S38] | `\| 500 \| 251.1156ms \| 192.0.2.x \| POST "/api/chat"` [S30] |
| status `503` | the queue (`OLLAMA_MAX_QUEUE`) is full [S1] | built from the FAQ [S1] |
| `msg="chat prompt error" error="no user query found in messages"` | the front-drop of old messages left no user message (Qwen 3.5 family renderer); the request ends in 500 [S5][S6][S7] | as quoted [S30] |
| `msg="truncating input prompt" limit=2050 prompt=23536 keep=4 new=2050` | the runner cut the prompt to about half the window: `limit = num_ctx - (num_ctx - keep) / 2`, so this window was 4,096 [S4] | as quoted [S30] |
| `slot release: ... stop processing: n_tokens = 65535, truncated = 1` | the reply stopped because the window filled (or a context shift dropped old tokens); the finish reason is "length" [S13][S15] | as quoted [S30] |
| `slot context shift, n_keep = 4, n_left = 32763, n_discard = 16381` | context shift on: half of the window's old tokens were dropped to keep writing [S13] | as quoted [S30] |
| `decode: failed to find a memory slot for batch of size 1` | the KV cache had no free cell for the next token: the window is full mid-reply [S14] | as quoted, at 64,825 tokens of a 65,536 window [S30] |
| `slot print_timing: ... prompt eval time = ... tokens per second` | the request's prompt and reply speeds [S13][S30] | `prompt eval time = 171.66 ms / 8 tokens` [S30] |

## What the log does not say

- The messages dropped from the front of a chat (the first truncation step) are logged only at DEBUG level, so a normal log shows no line for them. [S6]
- An idle model's unload is logged only at DEBUG level too; at the default level the next load's lines are the only sign. [S3]
