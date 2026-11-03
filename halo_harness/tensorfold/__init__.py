"""halo_harness.tensorfold -- Halo 3.3.9.3 "TensorFold": TensorFold (github.com/ashhart/TensorFold, Apache-2.0), an
inference engine in one Zig binary that serves Hugging Face checkpoints on Metal (Apple Silicon) and CUDA (Linux, and a
native Windows build from source) with no Python or MLX installed, as one more local runtime (docs/MODELS-tensorfold.md).
On the Mac it is the second native engine beside mlx_lm.server. To Halo it is an OpenAI-compatible local server of
runtime `tensorfold`: `hf:local/<model>@tensorfold` here, `hf:local/<model>@<host>` from a peer.

    requirements.py  the binary (`huggingface.tensorfold_bin`, PATH, or the fetched Linux archive under
                     `~/.halo/runtimes/tensorfold-<tag>/`), `--version`, `capabilities --json`, the per-OS install line
    catalog.py       the qualified models TensorFold's README names, their sizes and the machines they are checked on
    peer.py          the host side's offer and a peer's `hf:local/<model>@<host>` entry
    route.py         the TensorFold server as a placement option (place.solve, the adviser's loading tax)
The launcher is providers/local_runtime_tensorfold.py (the managed-runtime path, like llama-server); the release
table for the fetched Linux binary is providers/local_runtime_fetch_tf.py.

Every fact taken from TensorFold's README, docs and source (main at 532589e4, read 2026-11-02) is marked "from the
source, unverified against a live run" where it is used: no TensorFold has run against this code yet (the owner's live
check is the Mac).
"""

from __future__ import annotations

RUNTIME = "tensorfold"
NAME = "tensorfold"  # the registry id and the huggingface.local_servers entry Halo writes
DEFAULT_PORT = 8080  # README "Serve flags": `--host HOST`, `--port PORT` default 127.0.0.1:8080 (from the source, unverified)
OWNED_BY = "tensorfold"  # /v1/models rows (zig/src/server/status_routes.zig modelValue), from the source, unverified
KEY_ENV = "HALO_SECRET_TENSORFOLD_API_KEY"  # Halo's generated key (the env file, never config.json)
REPO = "ashhart/TensorFold"
# The install routes (README "Quick start", docs/WINDOWS.md), from the source, unverified against a live run:
BREW = "brew install ashhart/tensorfold/tensorfold"
WINDOWS = ("TensorFold on Windows is built from source (docs/WINDOWS.md in its repo: Zig 0.17.0, the CUDA toolkit and "
           "MSVC's C++ build tools, then zig build native install -Dsm=89 -Dstrip=true); set huggingface.tensorfold_bin "
           "to its zig-out\\native\\bin\\tensorfold-native.exe")
LINUX_NEEDS = "glibc 2.28 or newer and an NVIDIA driver R580 or newer (CUDA 13.0)"
ARCHES = {"x86_64": "linux-x86_64", "amd64": "linux-x86_64", "aarch64": "linux-aarch64", "arm64": "linux-aarch64"}
GIB = 2 ** 30


def is_tf(word) -> bool:
    """A `huggingface.local_servers` entry, a registry row or a roster row that is a TensorFold server."""
    return str(word or "").strip().lower() == RUNTIME


def platform_word(os_name: str, machine: str) -> str:
    """The release archive's platform for this OS and CPU ("linux-x86_64", "linux-aarch64"), or "" when TensorFold
    ships no archive for it (the Mac takes Homebrew; Windows builds from source)."""
    return ARCHES.get(str(machine or "").lower(), "") if str(os_name or "").lower() == "linux" else ""


def install_line(os_name: str, machine: str = "") -> str:
    """The one install route for THIS OS: Homebrew on the Mac, the release archive Halo fetches on Linux x86_64 /
    aarch64, the native build guide on Windows."""
    os_name = str(os_name or "").lower()
    if os_name == "macos":
        return f"{BREW} (Apple Silicon, macOS 13 or newer)"
    if os_name == "windows":
        return WINDOWS
    plat = platform_word(os_name, machine)
    if plat:
        return (f"halo local serve --runtime tensorfold --yes fetches the {plat} release archive (about 41 MB, its "
                f".sha256 checked) into ~/.halo/runtimes/; it needs {LINUX_NEEDS}")
    return f"TensorFold ships release archives for Linux x86_64 and aarch64 only ({machine or 'this CPU'} has none)"
