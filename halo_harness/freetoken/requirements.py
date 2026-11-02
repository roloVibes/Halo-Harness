"""halo_harness.freetoken.requirements -- what FreeToken needs on the machine that serves it, read without changing
anything (Halo 3.3.9.1; docs/MODELS-freetoken.md "Install").

FreeToken's docs/install.md (from the source, unverified against a live run): Linux x86_64, an NVIDIA GPU with driver
r580+ (CUDA 13), Python >= 3.10, and for the CUDA kernels it JIT-compiles on first use a CUDA 13 toolkit with `nvcc` on
PATH. Under WSL2 it runs, with CUDA pinned memory capped near half of RAM (docs/models.md "Hosts that cap pinned
memory"). No macOS; AMD is "WIP" (docs/install_amd.md).

    binary() -> (argv prefix | None, where from)   `huggingface.freetoken_bin` (a path, or the program and its first
        arguments: the tests' seam, tests/helpers/fake_ft_server.py), else `ft` on PATH
    platform_facts() -> {os, arch, linux, x86, wsl}
    check(*, binary_too=True) -> {ok, facts, ft, ft_version, driver, driver_ok, nvcc, nvcc_ok, missing [line], line}
        `line`: one line -- the three requirements and what to install for each one missing; "" when all are there
    SEAMS: {"run": fn(argv) -> (rc, text), "platform": fn() -> facts, "which": fn(name) -> path | None} for tests

Each probe is one short local command (`ft --version`, `nvidia-smi --query-gpu=driver_version`, `nvcc --version`),
never a model, never the network.
"""

from __future__ import annotations

import platform as _platform
import re
import shutil
import subprocess
import sys
from typing import Optional

from halo_harness.freetoken import CUDA_LINE, DRIVER_LINE, INSTALL_LINE, REQUIRES, WSL_CAVEAT

SEAMS: dict = {}
DRIVER_MIN = 580
CUDA_MAJOR = 13
_DRIVER = re.compile(r"(\d+)\.(\d+)")
_NVCC = re.compile(r"release (\d+)\.(\d+)")
_FT = re.compile(r"freetoken version (\S+)")  # cli.py prints "freetoken version <v>" (from the source, unverified)


def _run(argv: list) -> "tuple[int, str]":
    if "run" in SEAMS:
        return SEAMS["run"](list(argv))
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _which(name: str) -> Optional[str]:
    return SEAMS["which"](name) if "which" in SEAMS else shutil.which(name)


def binary() -> "tuple[Optional[list], str]":
    from halo_harness.theme import get_config_value
    raw = get_config_value("huggingface.freetoken_bin", default=None)
    if isinstance(raw, list) and raw and all(isinstance(x, str) for x in raw):
        return list(raw), "huggingface.freetoken_bin"
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()], "huggingface.freetoken_bin"
    found = _which("ft")
    return ([found], "ft on PATH") if found else (None, "")


def platform_facts() -> dict:
    if "platform" in SEAMS:
        return dict(SEAMS["platform"]())
    os_name = "linux" if sys.platform.startswith("linux") else "macos" if sys.platform == "darwin" else (
        "windows" if sys.platform.startswith("win") else sys.platform)
    arch = _platform.machine().lower()
    wsl = os_name == "linux" and "microsoft" in _platform.release().lower()  # FreeToken's own WSL test (engine.py)
    return {"os": os_name, "arch": arch, "linux": os_name == "linux", "x86": arch in ("x86_64", "amd64"), "wsl": wsl}


def _driver() -> "tuple[Optional[str], bool]":
    rc, out = _run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])
    m = _DRIVER.search(out) if rc == 0 else None
    return (m.group(0), int(m.group(1)) >= DRIVER_MIN) if m else (None, False)


def _nvcc() -> "tuple[Optional[str], bool]":
    if _which("nvcc") is None and "run" not in SEAMS:
        return None, False
    rc, out = _run(["nvcc", "--version"])
    m = _NVCC.search(out) if rc == 0 else None
    return (f"{m.group(1)}.{m.group(2)}", int(m.group(1)) >= CUDA_MAJOR) if m else (None, False)


def ft_version(prefix: Optional[list]) -> Optional[str]:
    if not prefix:
        return None
    rc, out = _run(list(prefix) + ["--version"])
    m = _FT.search(out) if rc == 0 else None
    return m.group(1) if m else (out.strip().splitlines()[-1][:60] if rc == 0 and out.strip() else None)


def check(*, binary_too: bool = True) -> dict:
    facts = platform_facts()
    prefix, src = binary() if binary_too else (None, "")
    driver, driver_ok = _driver()
    nvcc, nvcc_ok = _nvcc()
    version = ft_version(prefix) if prefix else None
    missing = []
    if not (facts["linux"] and facts["x86"]):
        missing.append(f"Linux x86_64 (this machine: {facts['os']} {facts['arch']}; on Windows, WSL2 with Ubuntu)")
    if not driver_ok:
        missing.append(f"the driver ({'found ' + driver if driver else 'nvidia-smi answered no driver'}): {DRIVER_LINE}")
    if not nvcc_ok:
        missing.append(f"nvcc ({'found CUDA ' + nvcc if nvcc else 'not on PATH'}): {CUDA_LINE}")
    if binary_too and (prefix is None or version is None):
        missing.append(f"ft ({'not on PATH' if prefix is None else 'it did not answer --version'}): {INSTALL_LINE}")
    line = (f"{REQUIRES}; missing here: " + "; ".join(missing)) if missing else ""
    if facts.get("wsl") and not missing:
        line = f"WSL2: {WSL_CAVEAT}"
    return {"ok": not missing, "facts": facts, "ft": prefix, "ft_from": src, "ft_version": version, "driver": driver,
            "driver_ok": driver_ok, "nvcc": nvcc, "nvcc_ok": nvcc_ok, "missing": missing, "line": line}
