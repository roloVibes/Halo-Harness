"""halo_harness.freetoken -- Halo 3.3.9.1 "FreeToken": FreeToken (github.com/FlashML-org/FreeToken, Apache-2.0), a
serving engine for big Mixture-of-Experts models on one consumer box, as one more local runtime (docs/MODELS-
freetoken.md). To Halo it is an OpenAI-compatible local server of runtime `freetoken`, like llama-server, LM Studio and
mlx_lm.server: `hf:local/<model>@freetoken` here, `hf:local/<model>@<host>` from a peer.

    requirements.py  the three requirements (Linux x86_64, NVIDIA driver r580+ with CUDA 13, `nvcc` on PATH) and `ft`
    launch.py        `halo local serve --runtime freetoken --model <checkpoint dir>`: `ft serve`, the registry row and
                     the `freetoken` entry of huggingface.local_servers
    catalog.py       the checkpoints FreeToken names as known-good (its docs/models.md), with their sizes
    shape.py         a checkpoint's dense bytes, expert bytes and KV per token (its config.json, or the catalog)
    link.py          `ft bench bw` through the bench seam: the host link's GB/s the fit reads
    bench.py         the speed card against a FreeToken server (the 3.3.6.0 battery's windows and reserve)
    peer.py          the host side's offer and a peer's `hf:local/<model>@<host>` entry
    route.py         the FreeToken server as a placement option (place.solve, the adviser's loading tax)
    waits.py         a FreeToken server's first request compiles its kernels for minutes: the wait allows it

Every fact taken from FreeToken's docs and source is marked "from the source, unverified against a live run" where it
is used: no FreeToken has run against this code yet (the owner's live check is on an Ubuntu box).
"""

from __future__ import annotations

RUNTIME = "freetoken"
NAME = "freetoken"  # the registry id and the huggingface.local_servers entry Halo writes
DEFAULT_PORT = 1919  # from the source (docs/cli.md `--port` default), unverified against a live run
OWNED_BY = "FreeToken"  # /v1/models rows' `owned_by` (server/api_models.ModelCard), from the source, unverified
API_KEY_ENV = "FREETOKEN_API_KEY"  # `ft serve --api-key` defaults to it (docs/cli.md), from the source, unverified
KEY_ENV = "HALO_SECRET_FREETOKEN_API_KEY"  # Halo's generated key for a `--lan` server (the env file, never config.json)
INSTALL_LINE = 'uv pip install "freetoken[accel]"'  # docs/install.md, from the source, unverified against a live run
CUDA_LINE = "the CUDA 13 toolkit with nvcc on PATH (sudo apt install cuda-toolkit-13-0 on Ubuntu, from NVIDIA's apt repo)"
DRIVER_LINE = "the NVIDIA driver r580 or newer (sudo ubuntu-drivers install, or nvidia-driver-580 from the apt repo)"
REQUIRES = "FreeToken needs Linux x86_64, an NVIDIA driver r580+ (CUDA 13) and nvcc on PATH"
WSL_CAVEAT = ("under WSL2 CUDA pinned memory is capped near half of RAM, so a large expert bank may not fully pin "
              "(FreeToken locks the rest for CPU decode: slower)")
GIB = 2 ** 30


def is_ft(word) -> bool:
    """A `huggingface.local_servers` entry, a registry row or a roster row that is a FreeToken server."""
    return str(word or "").strip().lower() == RUNTIME
