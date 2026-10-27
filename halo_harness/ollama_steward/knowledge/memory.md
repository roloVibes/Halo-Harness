# Memory arithmetic: what a model at a window needs

Read this when you work out whether a model fits a card at a window, or why Halo's estimate and the server disagree.

## The parts of a load

A loaded model takes, per device: its weights, the window's caches (the KV cache, plus a fixed state for hybrid models), a compute buffer, and on a GPU a margin the loader keeps free. llama.cpp prints exactly these columns at every load: `self = model + context + compute`. [S12][S30]

## Weights by quantization

| Type | Block layout | Bits per weight | Bytes per parameter |
|------|--------------|-----------------|---------------------|
| Q4_K | 144 bytes per 256 weights | 4.5 | 0.5625 [S16] |
| Q5_K | 176 bytes per 256 weights | 5.5 | 0.6875 [S16] |
| Q6_K | 210 bytes per 256 weights | 6.5625 | 0.8203 [S16] |
| Q8_0 | 34 bytes per 32 weights | 8.5 | 1.0625 [S16] |
| F16 | 2 bytes per weight | 16 | 2.0 [S16] |

- A `_M` file mixes types: the measured Q4_K_M files average 4.84 to 4.92 bits per weight, above Q4_K's 4.5, and a Q6_K file 6.56. [S16][S30]
- The file size is close to the weights' memory, but not all of it goes to the GPU: the measured 27B Q4_K_M file (15.65 GiB) put 15,339 MiB on the GPU and kept 682 MiB (the token embeddings) in system RAM. [S30]

## The KV cache

- Bytes per token = layers that hold a cache x KV heads x (key length + value length) x bytes per element. [S12][S33]
- Bytes per element by cache type: f16 2.0, q8_0 1.0625 (34 bytes per 32), q4_0 0.5625 (18 bytes per 32). [S16][S33]
- The cache is sized for the window times the slots: Ollama starts the runner with `-c num_ctx x OLLAMA_NUM_PARALLEL`. [S1][S4]
- Grouped-query attention is already in the formula: the KV head count (4 for every model below) is what is cached, not the query heads (24 to 32). [S26][S27][S29]
- Hybrid models (Qwen 3.5 and 3.8, `full_attention_interval` 4) have a KV cache only in every fourth layer; the other layers are linear attention with a fixed recurrent state that does not grow with the window. [S27][S28][S29][S30]
- The measured 27B shows both: "llama_kv_cache: size = 1088.00 MiB ( 32768 cells, 16 layers ...)" for 64 layers, and "llama_memory_recurrent: size = 748.13 MiB" at every window. [S30]
- Its draft layer (the multi-token-prediction head used for speculative decoding) keeps its own one-layer f16 cache: 128 MiB at 32,768. [S30]

## The compute buffer, the minimum and the margin

- The compute buffer grows with the window and the batch: the measured 27B used 180 MiB at 16,384 and 260 MiB at 32,768 (batch 512). [S30]
- Ollama keeps a fixed minimum free per device (457 MiB on CUDA, 512 MiB on Metal) plus `OLLAMA_GPU_OVERHEAD`. [S3][S11]
- When the layers are left to llama.cpp's `--fit`, it keeps a margin free on top (1,024 MiB by default; Ollama adds the vision projector's size, so the measured 27B kept 1,936 MiB). [S4][S12][S30]
- A model's vision projector can need up to its own size more ("estimated worst-case memory usage of mmproj is 1161.02 MiB" for the 27B). [S30]

## Windows and Apple

- Windows WDDM: a 24 GB card reports 23,028 MiB total (1.5 GiB under 24 GiB) and 420 MiB reserved; Ollama sees 22.5 GiB total, 21.0 GiB free at start. [S30][S31]
- Under WDDM the Windows kernel driver manages GPU memory, so `nvidia-smi` cannot say how much each process uses. [S25][S31]
- Apple Silicon has one memory for the CPU and GPU; Metal's `recommendedMaxWorkingSetSize` is "an approximation of how much memory ... this GPU device can allocate without affecting its runtime performance", and Apple publishes no fixed share of RAM for it. [S21]
- mlx-lm warns when a model needs more than 0.9 of that working set; raising `iogpu.wired_limit_mb` (`sudo sysctl iogpu.wired_limit_mb=N`, N above the model's size in MB and below the RAM) lets more stay wired. [S19][S20]
- Halo's own first guess for a Mac without a wired limit is 70 % of RAM, an estimate no source confirms. [S36]

## Worked examples on the measured host (24 GB card, server KV cache q8_0)

The blocks are checked by `tests/test_steward_knowledge.py`: it computes `halo_kv_bytes_per_token`, `halo_total_mib` and the two fits with Halo's own arithmetic (`providers/ollama_fit.py` and `providers/ollama_fit_parts.py`), the arithmetic from `kv_layers`, and fails when a figure is off by more than the block's `tolerance`: 0.05 since 3.3.4.0 R3 (it was 0.01 while the blocks recorded Halo's old, uncorrected figures), the fits compared exactly. `free_bytes` is the 21,506 MiB llama.cpp found free at load; `measured_total_mib` is the sum of the parts the log printed at that window; `halo_fit` is the window Halo's estimate allows with every layer on the GPU (Halo sends `num_gpu` then), `halo_fit_default` the one with the layers left to llama.cpp's `--fit`. [S30][S33][S39]

qwen3-coder:30b (mixture of experts, 48 layers, every one with a KV cache): the per-token figure is the real one at q8_0 and twice it when the host's cache type is left at f16; since 3.3.4.0 R3 the fit reads the server's own cache type from its log when the host entry has no hint. [S26][S30][S33][S39]

```example
model: qwen3-coder:30b
model_info: block_count=48 head_count_kv=4 key_length=128 value_length=128 embedding_length=2048 vocab_size=151936
kv_cache_type: q8_0
halo_kv_bytes_per_token: 52224
kv_layers: 48
real_kv_bytes_per_token: 52224
window: 65536
real_kv_mib: 3264
free_bytes: 22550675456
weight_bytes: 18554258719
projector_mib: 0
measured_total_mib: 21040
halo_fit: 65536
halo_fit_default: 32768
tolerance: 0.05
```

- At 65,536 with every layer on the GPU the log's budget is 17,524 MiB weights + 3,264 KV + 252 compute = 21,040 of 21,506 MiB free: it fits with 466 MiB left, just above Ollama's 457 MiB minimum and under `--fit`'s 1,024 MiB margin, so by default llama.cpp overflowed 3 layers' experts to RAM. [S12][S30]
- Halo's corrected sum is within a few MiB of that (the token embedding, 167 MiB at the 4.5 bits it is stored at, stays in RAM; the compute buffer grows by the attention mask and one layer's f16 K and V per token), so its forced fit is 65,536 and its default fit one power of two lower. [S30][S39]

qwen3.8:27b (the qwen35 architecture; Qwen3.5-27B has the same shape): `/api/show` reports 65 blocks (64 layers and the draft layer), only 16 layers hold a KV cache, and the other 48 carry a fixed recurrent state. [S27][S29][S30]

```example
model: qwen3.8:27b
model_info: block_count=65 head_count_kv=4 key_length=256 value_length=256 full_attention_interval=4 nextn_predict_layers=1 embedding_length=5120 vocab_size=248320 ssm.conv_kernel=4 ssm.state_size=128 ssm.group_count=16 ssm.inner_size=6144
kv_cache_type: q8_0
halo_kv_bytes_per_token: 34816
kv_layers: 16
real_kv_bytes_per_token: 34816
window: 65536
real_kv_mib: 2176
free_bytes: 22550675456
weight_bytes: 16804059546
projector_mib: 1161
measured_total_mib: 20230
halo_fit: 65536
halo_fit_default: 32768
tolerance: 0.05
```

| Part at 65,536 (q8_0, every layer on the GPU) | MiB |
|-----------------------------------------------|-----|
| weights on the GPU | 15,339 [S30] |
| KV cache, 16 layers | 2,176 [S30] |
| recurrent state (fixed; one sequence and the draft's four) | 748 [S30] |
| draft layer's f16 cache and its compute buffer | 256 + 130 [S30] |
| compute buffer (180 at 16,384, 260 at 32,768, 420 at 65,536) | 420 [S30] |
| vision projector, worst case | 1,161 [S30] |
| total | 20,230 of 21,506 free [S30] |

- So 65,536 fits with every layer forced on (the measured host used 20.7 GB there and called it safe), while `--fit`'s 1,936 MiB margin (1,024 and the 912 MiB projector file) leaves only 19,570 MiB, so the default spills; at 49,152 the same sum is about 19,550 MiB and loads whole, which is the measured "offloads past 49,152". [S30][S32]
- At 98,304 the sum with the projector's worst case is about 21,640 MiB (the draft's compute grew to 164), over the 21,506 free; the measured load still came up with every layer on, the projector's worst case not yet in use (the measured "works, too tight for daily use"), so Halo's estimate stops one step below it. [S30][S32]
- Before 3.3.4.0 R3 Halo counted all 65 blocks, 4 times too many per token (7.6 times with the host entry at f16), and said 32,768 (or 16,384) where 65,536 fits. [S30][S33]

qwen3.5:9b (32 layers, a KV cache in 8): the same one-in-four rule. [S28][S39]

```example
model: qwen3.5:9b
model_info: block_count=32 head_count_kv=4 key_length=256 value_length=256 full_attention_interval=4
kv_cache_type: f16
halo_kv_bytes_per_token: 32768
kv_layers: 8
real_kv_bytes_per_token: 32768
window: 65536
real_kv_mib: 2048
tolerance: 0.05
```

## What Halo's arithmetic counts (3.3.4.0 R3)

- The layers that hold a cache: one in `full_attention_interval` for a hybrid model, never the draft layer (`nextn_predict_layers`), the non-zero entries of a per-layer `head_count_kv` list (lfm2moe). [S30][S39]
- The cache type: the host entry's `kv_cache_type` hint, else the server's own from its startup env dump (`OLLAMA_KV_CACHE_TYPE:q8_0` on the measured host), else f16; the parallel slots the same way (`num_parallel_hint`, else `OLLAMA_NUM_PARALLEL`). [S1][S4][S30][S39]
- Beside the weights and the KV cache: the recurrent state, the draft layer's cache and compute, the compute buffer, the vision projector, Ollama's per-device minimum and, when the layers are left to `--fit`, its margin; the token embedding comes off the weights when `/api/show` gives the vocabulary size. [S3][S12][S30][S39]
- Still estimated, not read: the compute buffer is fitted to the two measured models, the projector's size is the measured 1,161 MiB worst case when `/api/show` gives only the vision capability, and the draft is counted whenever the model has a draft layer (a server that ignores it needs less). [S30][S39]
