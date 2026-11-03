"""halo_harness.strata -- Halo 3.3.9.2 "Strata": Strata (github.com/Niko1221/Strata, MIT), an engine that runs one big
Mixture-of-Experts model on one consumer box -- the experts in host RAM, the rest streamed from the SSD -- natively on
Windows, Linux and the Mac, as one more local runtime (docs/MODELS-strata.md). It is FreeToken's family (expert paging
from RAM and disk) and the first of it that runs natively on Windows. To Halo it is an OpenAI-compatible local server of
runtime `strata`: `hf:local/<model>@strata` here, `hf:local/<model>@<host>` from a peer.

    requirements.py  the `strata` program (`huggingface.strata_bin`, else PATH), `strata --version`, the per-OS install
    catalog.py       the families and sets Strata names (its README and docs/MODELS.md), their download GB and memory
    launch.py        `halo local serve --runtime strata --model <family>/<set>` (or `--model-path DIR`): `strata launch
                     --plan` first, then `strata launch ... --yes --no-tui --access local --port P`, the registry row
                     and the `strata` entry of huggingface.local_servers
    control.py       `strata launch --status --output json` and `--stop` for a server Halo started; the server log path
    detect.py        a server on a probed port that is Strata (`/health` says `"service": "strata"`)
    bench.py         `halo local bench --host strata`: FreeToken's speed card (freetoken/bench.py) against Strata
    peer.py          the host side's offer and a peer's `hf:local/<model>@<host>` entry
    route.py         the Strata server as a placement option (place.solve, the adviser's loading tax)

Every fact taken from Strata's docs and source is marked "from the source, unverified against a live run" where it is
used: no Strata has run against this code yet (the owner's live check is on the PC). Halo never downloads a Strata set:
the first launch's tens to hundreds of GB are the user's download, said with the GB before anything starts.
"""

from __future__ import annotations

RUNTIME = "strata"
NAME = "strata"  # the registry id and the huggingface.local_servers entry Halo writes
DEFAULT_PORT = 8080  # strata_cli/launch/settings.DEFAULT_PORT, from the source, unverified against a live run
SERVICE = "strata"  # GET /health -> {"service": "strata", ...} (serve/server.py), from the source, unverified
KEY_ENV = "HALO_SECRET_STRATA_API_KEY"  # Halo's generated key (the env file, never config.json), passed by --api-key-env
REPO = "https://github.com/Niko1221/Strata"
# The install routes (README.md "Terminal app", docs/TERMINAL_LAUNCH.md "Install"), from the source, unverified:
INSTALL_WINDOWS = "irm https://github.com/Niko1221/Strata/releases/latest/download/install.ps1 | iex"
INSTALL_POSIX = ("curl -fsSL https://github.com/Niko1221/Strata/releases/latest/download/install.sh -o install.sh && "
                 "sh install.sh")
INSTALL_DIRS = {"windows": r"%LOCALAPPDATA%\Strata\install", "posix": "$XDG_DATA_HOME/strata/install"}
GB = 1e9  # Strata states its sizes in GB (decimal, as a download counts them)


def is_st(word) -> bool:
    """A `huggingface.local_servers` entry, a registry row or a roster row that is a Strata server."""
    return str(word or "").strip().lower() == RUNTIME


def install_line(os_name: str) -> str:
    """The one install route for THIS OS: install.ps1 on Windows, install.sh on Linux and the Mac."""
    if str(os_name or "").lower().startswith("win"):
        return f"in PowerShell: {INSTALL_WINDOWS} (then open a new terminal so strata is on PATH)"
    return f"{INSTALL_POSIX} (it puts strata in ~/.local/bin)"
