# The steward's sources

Read this when you check where a claim in the steward's knowledge comes from.

Every claim in the other files of this folder ends in one or more `[S<n>]` tags; each tag is a row
here. A row names the page or file, where it lives, the version or commit that was read, and the
date it was read. Ollama facts are of v0.40.6, the version the measured host's server ran when this
was written; the newest Ollama release on that date was v0.40.11 (S35). `local:` rows are reads of
the measured host itself (a Windows PC with one 24 GB NVIDIA card), done read-only: nothing was sent
to its Ollama server. `repo:` rows are files of this repository. A `tests/test_steward_knowledge.py`
check keeps the tags and the rows in step.

| ID | Source | URL | Version or commit | Read |
|----|--------|-----|-------------------|------|
| S1 | Ollama FAQ (`docs/faq.mdx`) | https://github.com/ollama/ollama/blob/v0.40.6/docs/faq.mdx | v0.40.6 (2476d5e) | 2026-10-27 |
| S2 | Ollama server settings (`envconfig/config.go`) | https://github.com/ollama/ollama/blob/v0.40.6/envconfig/config.go | v0.40.6 (2476d5e) | 2026-10-27 |
| S3 | Ollama scheduler (`server/sched.go`) | https://github.com/ollama/ollama/blob/v0.40.6/server/sched.go | v0.40.6 (2476d5e) | 2026-10-27 |
| S4 | Ollama's llama-server wrapper (`llm/llama_server.go`) | https://github.com/ollama/ollama/blob/v0.40.6/llm/llama_server.go | v0.40.6 (2476d5e) | 2026-10-27 |
| S5 | Ollama HTTP routes (`server/routes.go`) | https://github.com/ollama/ollama/blob/v0.40.6/server/routes.go | v0.40.6 (2476d5e) | 2026-10-27 |
| S6 | Ollama chat prompt truncation (`server/prompt.go`) | https://github.com/ollama/ollama/blob/v0.40.6/server/prompt.go | v0.40.6 (2476d5e) | 2026-10-27 |
| S7 | Ollama Qwen 3.5 renderer (`model/renderers/qwen35.go`) | https://github.com/ollama/ollama/blob/v0.40.6/model/renderers/qwen35.go | v0.40.6 (2476d5e) | 2026-10-27 |
| S8 | Ollama troubleshooting (`docs/troubleshooting.mdx`) | https://github.com/ollama/ollama/blob/v0.40.6/docs/troubleshooting.mdx | v0.40.6 (2476d5e) | 2026-10-27 |
| S9 | Ollama API reference (`docs/api.md`) | https://github.com/ollama/ollama/blob/v0.40.6/docs/api.md | v0.40.6 (2476d5e) | 2026-10-27 |
| S10 | Ollama device report (`discover/types.go`) | https://github.com/ollama/ollama/blob/v0.40.6/discover/types.go | v0.40.6 (2476d5e) | 2026-10-27 |
| S11 | Ollama device minimum memory (`ml/device.go`) | https://github.com/ollama/ollama/blob/v0.40.6/ml/device.go | v0.40.6 (2476d5e) | 2026-10-27 |
| S12 | llama.cpp server README (`tools/server/README.md`) | https://github.com/ggml-org/llama.cpp/blob/19ff817fb25e/tools/server/README.md | 19ff817fb25e (after v0.7.0) | 2026-10-27 |
| S13 | llama.cpp server slots (`tools/server/server-context.cpp`) | https://github.com/ggml-org/llama.cpp/blob/19ff817fb25e/tools/server/server-context.cpp | 19ff817fb25e | 2026-10-27 |
| S14 | llama.cpp decode (`src/llama-context.cpp`) | https://github.com/ggml-org/llama.cpp/blob/19ff817fb25e/src/llama-context.cpp | 19ff817fb25e | 2026-10-27 |
| S15 | llama.cpp server results (`tools/server/server-task.cpp`) | https://github.com/ggml-org/llama.cpp/blob/19ff817fb25e/tools/server/server-task.cpp | 19ff817fb25e | 2026-10-27 |
| S16 | GGML block layouts (`ggml/src/ggml-common.h`) | https://github.com/ggml-org/llama.cpp/blob/19ff817fb25e/ggml/src/ggml-common.h | 19ff817fb25e | 2026-10-27 |
| S17 | mlx-lm HTTP server doc (`mlx_lm/SERVER.md`) | https://github.com/ml-explore/mlx-lm/blob/4cfc6478473b/mlx_lm/SERVER.md | 4cfc6478473b (after v0.32.2) | 2026-10-27 |
| S18 | mlx-lm server flags (`mlx_lm/server.py`) | https://github.com/ml-explore/mlx-lm/blob/4cfc6478473b/mlx_lm/server.py | 4cfc6478473b | 2026-10-27 |
| S19 | mlx-lm README, large models (`README.md`) | https://github.com/ml-explore/mlx-lm/blob/4cfc6478473b/README.md | 4cfc6478473b | 2026-10-27 |
| S20 | mlx-lm wired limit (`mlx_lm/generate.py`) | https://github.com/ml-explore/mlx-lm/blob/4cfc6478473b/mlx_lm/generate.py | 4cfc6478473b | 2026-10-27 |
| S21 | Apple Metal `recommendedMaxWorkingSetSize` | https://developer.apple.com/documentation/metal/mtldevice/recommendedmaxworkingsetsize | unversioned page, as served | 2026-10-27 |
| S22 | LM Studio TTL and auto-evict | https://lmstudio.ai/docs/developer/core/ttl-and-auto-evict | unversioned page, as served | 2026-10-27 |
| S23 | LM Studio REST API endpoints | https://lmstudio.ai/docs/developer/rest/endpoints | page says LM Studio 0.3.6 or newer | 2026-10-27 |
| S24 | vLLM engine arguments | https://docs.vllm.ai/en/latest/configuration/engine_args.html | latest docs (names v0.33/v0.34 removals) | 2026-10-27 |
| S25 | NVIDIA nvidia-smi documentation | https://docs.nvidia.com/deploy/nvidia-smi/index.html | unversioned page; `--help-query-compute-apps` of driver 610.88 agrees | 2026-10-27 |
| S26 | Qwen3-Coder-30B-A3B-Instruct `config.json` | https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct/blob/main/config.json | b2cff646eb4b | 2026-10-27 |
| S27 | Qwen3.5-27B `config.json` | https://huggingface.co/Qwen/Qwen3.5-27B/blob/main/config.json | fc05daec18b0 | 2026-10-27 |
| S28 | Qwen3.5-9B `config.json` | https://huggingface.co/Qwen/Qwen3.5-9B/blob/main/config.json | c202236235762 | 2026-10-27 |
| S29 | Qwen3.8-27B `config.json` | https://huggingface.co/Qwen/Qwen3.8-27B/blob/main/config.json | 1d4bf0f2ff60 | 2026-10-27 |
| S30 | The measured host's Ollama server.log | local:%LOCALAPPDATA%\Ollama\server.log | Ollama 0.40.6, log of 2026-10-18 to 2026-10-27 | 2026-10-27 |
| S31 | The measured host's `nvidia-smi` | local:nvidia-smi --query-gpu / --query-compute-apps | driver 610.88, WDDM | 2026-10-27 |
| S32 | Halo's fit, calibration and tuned twin doc | repo:docs/MODELS-ollama-tuning.md | Halo 3.3.3.0 candidate (e3a98d2) | 2026-10-27 |
| S33 | Halo's fit arithmetic | repo:halo_harness/providers/ollama_fit.py | Halo 3.3.3.0 candidate (e3a98d2) | 2026-10-27 |
| S34 | The read-only watcher's alert rules and guide | local:ollama-watch/watch.ps1 | as of 2026-10-26 | 2026-10-27 |
| S35 | Ollama releases | https://github.com/ollama/ollama/releases | v0.40.11 newest (2026-10-24) | 2026-10-27 |
| S36 | Halo's per-host hardware reads | repo:halo_harness/providers/ollama_hw.py | Halo 3.3.3.0 candidate (e3a98d2) | 2026-10-27 |
| S37 | Halo's roadmap, 3.3.4.0 "The Ollama steward" (the three parked bugs) | repo:plans/ROADMAP.md | Halo 3.3.3.0 candidate (e3a98d2) | 2026-10-27 |
| S38 | llama.cpp server request queue (`tools/server/server-queue.cpp`) | https://github.com/ggml-org/llama.cpp/blob/19ff817fb25e/tools/server/server-queue.cpp | 19ff817fb25e | 2026-10-27 |
| S39 | Halo's corrected fit arithmetic | repo:halo_harness/providers/ollama_fit_parts.py | Halo 3.3.4.0 R3 | 2026-10-27 |
| S40 | Halo's roadmap, 3.3.5.0 R0 "the switch: a session fits the model it moves to" | repo:plans/ROADMAP.md | Halo 3.3.4.0 (8a14695) | 2026-10-27 |
