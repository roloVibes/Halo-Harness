"""halo_harness.engines -- Halo 3.3.13.0 R1: the local engines Halo knows beyond llama-server and mlx_lm.server, through
ONE OpenAI-compatible adapter whose per-engine knowledge is a short descriptor table (docs/MODELS-engines.md). To Halo
each is a local server of runtime `<id>`: `hf:local/<model>@<id>` here, `hf:local/<model>@<host>` from a peer.

    descriptors.py  THE table: one entry per engine (ports, routes, install lines, start, log patterns, fixes, fit)
    models.py       the models each engine names in its docs: the Library's download targets and the fit's sizes
    adapter.py      the program, the auto-detect, the `huggingface.local_servers` entry, the key, the stop, the wait
    launch.py       `halo local serve --runtime <id>`: the descriptor's managed start; a supervised engine settled
    steward.py      the log reader, the queue read, the findings with the descriptor's sentences and fixes
    fit.py          the two fit rules: `vram` and `paged-moe` (RAM and the disk link, not VRAM)
    doctor.py       `halo doctor --local`'s line per engine found here
    peer.py         an engine answers like a host: the peer offer, a peer's entry, the placement option
    bench.py        `halo local bench --host <id>` through the OpenAI-compatible route

Nothing runs unless a runtime word names an engine, its program is configured or on PATH, or its port answers; Halo
never downloads or installs an engine. Every entry says `verified: False` until an owner's live run.
"""
