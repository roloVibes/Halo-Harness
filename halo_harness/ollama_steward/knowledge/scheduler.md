# Ollama's scheduler and loader

Read this when you need to know how an Ollama server decides what to load, where, for how long, and what it does to a prompt that is too long.

Ollama 0.40.x runs every GGUF model in llama.cpp's own `llama-server`, started as a child process per loaded model; its log says "using llama-server for model" and then "starting llama-server" with the whole command line. [S4][S30]

## The server settings

Each setting is an environment variable of the server process, read once at start. The startup line
`msg="server config" env="map[...]"` prints every one of them. [S2][S5][S30]

| Setting | Default | What it does |
|---------|---------|--------------|
| `OLLAMA_MAX_LOADED_MODELS` | 0 = automatic: 3 per GPU, 3 on a CPU-only box | the most models kept loaded at once, when they fit [S1][S2][S3] |
| `OLLAMA_NUM_PARALLEL` | 1 | slots per model; the runner is started with `-c num_ctx x parallel`, so the KV cache grows by the same factor [S1][S2][S4] |
| `OLLAMA_KEEP_ALIVE` | 5m | how long an idle model stays loaded; a request's `keep_alive` wins over it; a negative value keeps it forever, 0 unloads after the reply [S1][S2] |
| `OLLAMA_KV_CACHE_TYPE` | f16 (prints empty when unset) | one cache type for every model: `q8_0` is about half of f16, `q4_0` about a quarter; Ollama passes it as `--cache-type-k` and `--cache-type-v` [S1][S2][S4] |
| `OLLAMA_FLASH_ATTENTION` | automatic where the backend supports it | `1` forces it on, `0` off; the env dump prints `false` both when unset and when off, the `--flash-attn on/off/auto` on the llama-server command line is the real mode [S1][S2][S4] |
| `OLLAMA_GPU_OVERHEAD` | 0 | bytes set aside on every GPU before a load is placed [S2][S3] |
| `OLLAMA_SCHED_SPREAD` | false | spread every model across all GPUs instead of one when it fits on one [S1][S2] |
| `OLLAMA_MAX_QUEUE` | 512 | requests waiting beyond this get HTTP 503 [S1][S2] |
| `OLLAMA_CONTEXT_LENGTH` | 0 = by total VRAM: 4,096 under 23 GiB, 32,768 from 23 GiB, 262,144 from 47 GiB | the window when a request sends no `num_ctx` [S2][S5] |
| `OLLAMA_LOAD_TIMEOUT` | 5m | how long a load may stall before it is given up [S2] |
| `LLAMA_ARG_FIT`, `LLAMA_ARG_FIT_TARGET` | on; a 1,024 MiB margin per device | llama.cpp's own fitting of unset options to free memory, passed through by Ollama [S2][S12] |
| `num_gpu` (a request or Modelfile option) | -1 = llama-server decides | a positive value is passed as `-ngl N`, 0 means CPU only; there is no `OLLAMA_NUM_GPU` server variable [S2][S4] |

The FAQ still says the default window is 4,096 tokens flat; the settings code and the routes say it depends on total VRAM. Both are of v0.40.6; the code is what runs. [S1][S2][S5]

A 24 GB card on Windows reports 22.5 GiB total to Ollama ("vram-based default context" total_vram="22.5 GiB" default_num_ctx=4096), under the 23 GiB line, so such a box gets the 4,096 default unless `OLLAMA_CONTEXT_LENGTH` is set. [S5][S30][S31]

Some architectures always run one slot whatever `OLLAMA_NUM_PARALLEL` says: mllama, qwen3vl, qwen3vlmoe, qwen35, qwen35moe, qwen3next, lfm2, lfm2moe and the nemotron_h family; the log then warns "model architecture does not currently support parallel requests". [S3]

## How a load decides what goes on the GPU

- The scheduler first predicts the memory a load needs at `num_ctx x parallel` (capped at the model's trained context) plus its batch, then picks one GPU when the model fits on one, else every GPU. [S1][S3]
- The memory it may use per GPU is printed as `msg="gpu memory" available=... free=... minimum=... overhead=...`: available is free minus `OLLAMA_GPU_OVERHEAD` minus a fixed minimum, 457 MiB on CUDA and the like, 512 MiB on Metal. [S3][S11][S30]
- Ollama passes `-ngl` only when the request or Modelfile sets `num_gpu`. Otherwise llama-server's `--fit` (on by default) chooses: it changes only options left unset, keeps a free margin per device (1,024 MiB by default, which Ollama raises by the vision projector's size), and moves layers to system RAM until that margin holds. [S4][S12][S30]
- So with the window pinned by Ollama's `-c` and the layers left to `--fit`, a window that would fit with no margin loads part of the model on the CPU instead. This is the measured host's "offloads past 49,152" behaviour; forcing `num_gpu` to every layer takes the choice away from `--fit`, and the same model then loads whole at 65,536. [S4][S12][S32]
- For a mixture-of-experts model `--fit` overflows expert tensors of the last layers, so the log can say "offloaded 49/49 layers to GPU" while about 0.8 GiB of the model sits in system RAM ("49 layers ( 3 overflowing)"); `/api/ps` reporting `size_vram` under `size` is the reliable sign. [S9][S12][S30]
- On Windows with CUDA, Ollama turns mmap off for llama-server loads ("disabling mmap for llama-server load by default ... reason=windows_cuda"). [S3][S30]
- A load that runs out of memory is retried once: with a smaller automatic window when the request did not set `num_ctx`, else with every other model unloaded first. [S3]

## Eviction and a second model

- A request for a model already loaded reuses it unless its runner options differ: a different `num_ctx`, `num_gpu` or batch reloads the model (an automatic window does not count as a change). [S3]
- So two clients that send the same model different windows make the server reload it on every switch. [S3]
- When `OLLAMA_MAX_LOADED_MODELS` is reached, one model is unloaded to make room: an idle one first, else the one with the shortest keep-alive, after its running requests end. [S3]
- A second model loads beside the first only when it fits whole on the GPU; beside other models the scheduler unloads one when its prediction passes 80 % of the free memory, logging "llama-server model predicted to exceed available memory, evicting". [S1][S3][S30]
- After an unload the scheduler waits for the GPU's free memory to come back before the next load, because the drivers report it late. [S3]

## What a request does while another model loads

- While a model loads, new requests for a model that does not fit beside it wait in order; past `OLLAMA_MAX_QUEUE` they get HTTP 503. [S1]
- A client that closes its connection before the load ends aborts the load: "client connection closed before llama-server finished loading, aborting load", then `msg="Load failed" ... context canceled` and HTTP 499 for that request; the next request starts the load again from the beginning. [S3][S4][S30]

## What the server does to a prompt that is too long

- Chat requests first drop whole messages from the front, keeping every system message and always the last message, until the rendered prompt fits `num_ctx`; this step logs only at DEBUG level. [S6]
- If the messages left hold no real user message (only tool results), the Qwen 3.5 family's renderer fails with "no user query found in messages", which the chat route returns as HTTP 500 after logging "chat prompt error". [S5][S7][S30]
- A prompt still longer than the window is cut by the runner: it keeps the first `num_keep` tokens and only the newest tokens up to `num_ctx - (num_ctx - num_keep) / 2`, about half the window, and logs "truncating input prompt". [S4]
- With context shift off, a too-long prompt is refused with HTTP 400 instead. Ollama starts llama-server with `--context-shift` for every family except deepseek2. [S3][S4]
- llama-server turns context shift off for a multimodal model (one loaded with `--mmproj`) and for memory that cannot shift; a reply then stops when the window is full, the slot logs "truncated = 1", and the result's finish reason is "length". [S13][S15]

## The read-only views of a server

- `GET /api/version` answers `{"version": ...}`; `GET /api/ps` lists each loaded model with `size`, `size_vram`, `expires_at`, `digest`, `details` and the loaded `context_length`. [S5][S9]
- The server's own settings and its devices are not served over HTTP; they are in the server log's startup lines (see log-vocabulary.md). [S5][S10]

## Versions

- Every fact above is of Ollama v0.40.6, the version the measured host ran; the newest release on the day it was read was v0.40.11, not read here. [S30][S35]
