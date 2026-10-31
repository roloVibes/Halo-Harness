# Benchmarks: what the bench measures and why

Read this when you need to know why the bench never times the first call, which windows it tries, and what `reserve_floor` means.

The bench (`halo local bench`) measures one model on one host with a fixed prompt, so its numbers say what this card does at a window, where the measured card says what real sessions happened to do. [S48][S42]

## The first call after a load is never timed

The first request after a model loads pays for graph capture: on the measured host it ran at 5.7 tok/s, then 199 tok/s steady. A speed that counted it would say the card is slow when only the load was. [S42]

So the bench sends one small untimed call right after each load and labels it "warming"; the battery does the same with its first probe, and the traffic ledger marks such calls `warming` so no speed counts them. [S48][S44]

A change of `num_ctx` makes Ollama load the model again, so every window the bench tries starts with its own warm-up. [S3][S48]

## The three windows

| Window | Why it is tried |
|--------|-----------------|
| 8,192 | the floor every model must serve; its speed is the model's best case on this card [S48] |
| 32,768 | the window a main agent needs; most of a session's calls run near it [S45][S48] |
| the planner's ceiling | the largest window the fit arithmetic says fits on this card, capped at the trained window and 128k [S39][S48] |

Each timed call is a prompt of about 60 % of the window and a 256-token reply, so the prompt rate and the reply rate are both measured where the cache is mostly full. [S48]

`/api/ps` after each timed call says whether every byte stayed on the GPU (`size_vram == size`); the largest window that did is `max_gpu_window`. When the planner's ceiling spills, the planner's number and the bench's disagree, and the bench's wins: placement and the tuning report read it. [S9][S48]

## The reply reserve

`reserve_floor` is the smallest `num_predict` (128, 256 or 512) at which a reply of about 150 words ended on its own instead of being cut at the limit (`done_reason: length`). A thinking model spends part of the budget on its thinking, so it needs more room than its answer alone. [S9][S44][S48]

When no budget of the three was enough the card says so, and the reserve should be raised past 512 for that model. [S48]
