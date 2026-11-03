"""halo_harness.strata.requirements -- the `strata` program and what it says about itself, read without changing anything
(Halo 3.3.9.2; docs/MODELS-strata.md "Install").

Strata's installer (README.md, docs/TERMINAL_LAUNCH.md "Install", docs/AI_SETUP.md: from the source, unverified against a
live run) needs no administrator rights and puts `strata` on PATH -- `install.ps1` on Windows (then a new terminal),
`install.sh` on Linux and the Mac. Its packages are x86-64 on Windows and Linux, Apple Silicon (macOS 15+) on the Mac;
the engine for the card comes with the first model (`strata launch` fetches it). `strata --version` prints one line,
"strata <version> (build <b>; python <v> at <exe>)" (strata_cli/cli.py).

    binary() -> (argv prefix | None, where from)   `huggingface.strata_bin` (a path, or the program and its first
        arguments: the tests' seam, tests/helpers/fake_strata.py), else `strata` on PATH. Halo does not search
        Strata's install folders (%LOCALAPPDATA%\\Strata\\install, $XDG_DATA_HOME/strata/install): the line names them.
    os_word() -> "windows" | "linux" | "macos" | ...
    version(prefix) -> "0.2.10" | None
    check() -> {ok, strata, strata_from, version, os, line}   `line`: one line with the install route for THIS OS when
        strata is missing or silent; "" when it answered
    SEAMS: {"run": fn(argv) -> (rc, text), "which": fn(name) -> path | None, "os": fn() -> word} for tests

Each probe is one short local command, never a model, never the network.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from typing import Optional

from halo_harness.strata import INSTALL_DIRS, install_line

SEAMS: dict = {}
_VERSION = re.compile(r"^strata (\S+)", re.M)  # strata_cli/cli.py's --version line (from the source, unverified)


def _run(argv: list, timeout: float = 20.0) -> "tuple[int, str]":
    if "run" in SEAMS:
        return SEAMS["run"](list(argv))
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def os_word() -> str:
    if "os" in SEAMS:
        return SEAMS["os"]()
    p = sys.platform
    return "linux" if p.startswith("linux") else "macos" if p == "darwin" else "windows" if p.startswith("win") else p


def binary() -> "tuple[Optional[list], str]":
    from halo_harness.theme import get_config_value
    raw = get_config_value("huggingface.strata_bin", default=None)
    if isinstance(raw, list) and raw and all(isinstance(x, str) for x in raw):
        return list(raw), "huggingface.strata_bin"
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()], "huggingface.strata_bin"
    found = SEAMS["which"]("strata") if "which" in SEAMS else shutil.which("strata")
    return ([found], "strata on PATH") if found else (None, "")


def version(prefix: Optional[list]) -> Optional[str]:
    if not prefix:
        return None
    rc, out = _run(list(prefix) + ["--version"])
    m = _VERSION.search(out) if rc == 0 else None
    return m.group(1) if m else None


def missing_line(os_name: str, *, found: bool) -> str:
    where = INSTALL_DIRS["windows" if os_name == "windows" else "posix"]
    head = "strata did not answer --version" if found else "strata is not on PATH"
    return (f"{head}: install it {install_line(os_name)}; an install the desktop app made lives in {where} "
            "(set huggingface.strata_bin to its strata program)")


def check() -> dict:
    os_name = os_word()
    prefix, src = binary()
    v = version(prefix) if prefix else None
    line = "" if v else missing_line(os_name, found=prefix is not None)
    return {"ok": bool(v), "strata": prefix, "strata_from": src, "version": v, "os": os_name, "line": line}
