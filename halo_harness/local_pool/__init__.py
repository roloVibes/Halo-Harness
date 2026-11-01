"""halo_harness.local_pool -- Halo 3.3.8.0 R1: the pool (docs/POOL.md; plans/pooled-inference-spec.md, the ROADMAP's
3.3.8.0 adaptation rules). A pool is a set of paired hosts whose GPU memory serves one model together over llama.cpp
RPC: each worker runs `rpc-server`, the controller runs `llama-server --rpc ... --tensor-split ...` and serves an
OpenAI-compatible API. Pooling buys capacity, not speed (measured -21 % to -55 % against a single node that could
hold the model); a mixture of experts with few active parameters is the pooled choice.

    members.py    `<state>/pool/pool.json`: the members {name, host, rpc_port, weight?, vram_gb?}, load / save / add /
                  remove and the validation lines
    link.py       the host card's `link` {type wired | wireless | unknown, speed_mbps}: the adapter that carries the
                  host's own address, read from the OS (a RUNNER seam per OS)
    budget.py     each member's free VRAM from its host card (usable with the helper, minus resident models, minus
                  claims; the source named) and the tensor split proportional to it
    catalog.py    the pool's model catalog (plans/pooled-inference-model-candidates.md), every estimate marked
    fit.py        one deterministic function: single node / fits the pool / does not fit, each number said
    recommend.py  what fits the pool by the lowest active parameters, then the single-node rows; the honest preview
    library.py    the Library's "Pool" preset rows with their fit badge
    scan.py       `halo pool scan` and Studio's Scan: the RPC-port probe (providers/rpc_probe.py) on explicit action

R1 knows the pool and tells the truth about it before anything runs. R3 (the controller) runs it:

    versions.py   the llama.cpp build of llama-server here and of each rpc-server, compared; min_build per node
    preflight.py  every check before a launch, one answer (`halo pool preflight`, the page before Warm)
    hosts.py      a member through its halo host: rpc_server, claim, renew, release, unload, warm
    claims.py     the pool's claim on every member with its lease; residents pivoted out first; the return pivots
    gguf.py       where the model's GGUF is on this machine (else the Download line)
    launch.py     the argv, start (claims, rpc-servers, llama-server, the entry), stop, <state>/pool/run.json
    spawn.py      the pool's llama-server process         entry.py  the `pool` local-server entry and its key
    degrade.py    running / degraded (worker2 down) / down; a failed pool request's line
    route.py      the pool's `route` answer and its pseudo-host for local_sched/place.solve
    peer.py       the pool offered through the host's catalog, resolved from a peer
The running pool is the `huggingface.local_servers` entry named `pool` (`hf:local/<model>@pool`, POOL_SERVER_NAME).
"""

POOL_SERVER_NAME = "pool"
DEFAULT_RPC_PORT = 50052
