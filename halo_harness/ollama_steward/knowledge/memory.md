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

The blocks are checked by `tests/test_steward_knowledge.py`: it computes `halo_kv_bytes_per_token` and `halo_fit` with `providers/ollama_fit.py` itself and the arithmetic from `kv_layers`, and fails when a figure is off by more than the block's `tolerance` (a fraction; the fit is compared exactly). `free_bytes` is the 21,506 MiB llama.cpp found free at load. [S30][S33]

qwen3-coder:30b (mixture of experts, 48 layers, every one with a KV cache): Halo's per-token figure is right when the host entry says q8_0, and twice the real one when it is left at the f16 default. [S26][S30][S33]

```example
model: qwen3-coder:30b
model_info: block_count=48 head_count_kv=4 key_length=128 value_length=128
kv_cache_type: q8_0
halo_kv_bytes_per_token: 52224
kv_layers: 48
real_kv_bytes_per_token: 52224
window: 65536
real_kv_mib: 3264
free_bytes: 22550675456
weight_bytes: 18554258719
halo_fit: 65536
tolerance: 0.01
```

- At 65,536 with every layer on the GPU the log's budget is 17,524 MiB weights + 3,264 KV + 252 compute = 21,040 of 21,506 MiB free: it fits with 466 MiB left, under `--fit`'s 1,024 MiB margin, so by default llama.cpp overflowed 3 layers' experts to RAM. [S12][S30]
- Halo's estimate says 65,536 fits because it counts only weights and KV; the compute buffer and the minimum are the 0.7 GiB it leaves out. [S30][S33]

qwen3.8:27b (the qwen35 architecture; Qwen3.5-27B has the same shape): `/api/show` reports 65 blocks (64 layers and the draft layer), but only 16 layers hold a KV cache. [S27][S29][S30]

```example
model: qwen3.8:27b
model_info: block_count=65 head_count_kv=4 key_length=256 value_length=256
kv_cache_type: q8_0
halo_kv_bytes_per_token: 141440
kv_layers: 16
real_kv_bytes_per_token: 34816
window: 65536
real_kv_mib: 2176
free_bytes: 22550675456
weight_bytes: 16804059546
halo_fit: 32768
tolerance: 0.01
```

| Part at 65,536 (q8_0, every layer on the GPU) | MiB |
|-----------------------------------------------|-----|
| weights on the GPU | 15,339 [S30] |
| KV cache, 16 layers | 2,176 [S30] |
| recurrent state (fixed) | 748 [S30] |
| draft layer's f16 cache | 256 [S30] |
| compute buffer, estimated from 180 at 16,384 and 260 at 32,768 | about 420 [S30] |
| vision projector, worst case | 1,161 [S30] |
| total | about 20,100 of 21,506 free [S30] |

- So 65,536 fits with every layer forced on (the measured host used 20.7 GB there and called it safe), while `--fit`'s 1,936 MiB margin leaves only 19,570 MiB, so the default spills; at 49,152 the same sum is about 19,400 MiB and loads whole, which is the measured "offloads past 49,152". [S30][S32]
- At 98,304 the sum is about 21,480 MiB of 21,506: it loads, with almost nothing left (the measured "works, too tight for daily use"). [S30][S32]
- Halo's estimate is 4 times too big per token (65 blocks counted instead of 16) and, with the host entry at f16, 7.6 times; it says 32,768 (or 16,384) where 65,536 fits. [S30][S33]

qwen3.5:9b (32 layers, a KV cache in 8): the same factor of 4 when its GGUF reports 32 blocks; one more block for a draft layer raises Halo's figure by 1/32. [S28][S33]

```example
model: qwen3.5:9b
model_info: block_count=32 head_count_kv=4 key_length=256 value_length=256
kv_cache_type: f16
halo_kv_bytes_per_token: 131072
kv_layers: 8
real_kv_bytes_per_token: 32768
window: 65536
real_kv_mib: 2048
tolerance: 0.01
```

## Where Halo's arithmetic and the server differ

- Halo multiplies by every block; a hybrid model's KV cache is in one layer of four, so Halo over-counts Qwen 3.5 and 3.8 by 4 times. [S30][S33]
- Halo assumes f16 unless the host entry's `kv_cache_type` says otherwise; the server's own type is in its startup env dump (`OLLAMA_KV_CACHE_TYPE:q8_0` on the measured host). [S30][S33]
- Halo leaves out the compute buffer, the recurrent state, the draft layer's cache, the projector, Ollama's per-device minimum and llama.cpp's fit margin, and counts the whole file as GPU weights. [S3][S12][S30][S33]
- Halo does not multiply by the server's parallel slots (`num_parallel_hint` is read from config and never used in the fit). [S1][S4][S36]
- A model whose `head_count_kv` is a per-layer list (lfm2moe) gets no estimate at all, because Halo reads only a single number. [S30][S33]
