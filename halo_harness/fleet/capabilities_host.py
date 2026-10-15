"""halo_harness.fleet.capabilities_host -- this machine in a harness's
capability catalog (Halo 3.0.6.0 "Fleet Missions" round R6): the hardware
(os, distro, cpu, cores, RAM, GPUs and their VRAM, free disk) and the
command-line tools on PATH with their versions. Computed in code; with
`spawn=False` (BRIDGE_TEST_NO_BACKGROUND_NET) no process starts: no
`--version`, no `nvidia-smi`, the tools only say whether they are on PATH.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

CLI_TIMEOUT_S = 3.0
CLIS = ("git", "gh", "python", "uv", "node", "npm", "docker", "ffmpeg", "rg", "claude", "codex", "ollama",
        "go", "cargo", "java", "kubectl", "terraform", "nmap")


# ---- hardware ------------------------------------------------------------------------------
def _ram_gb() -> Optional[float]:
    try:
        if os.name == "nt":
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = _MS()
            ms.dwLength = ctypes.sizeof(_MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms)):
                return round(ms.ullTotalPhys / 2 ** 30, 1)
            return None
        if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:
            return round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2 ** 30, 1)
    except (OSError, ValueError, AttributeError):
        return None
    return None


def _cpu() -> str:
    try:
        if os.name == "nt":
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return " ".join(str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).split())
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^model name\s*:\s*(.+)$", text, re.M)
        if m:
            return " ".join(m.group(1).split())
    except (OSError, ImportError):
        pass
    return platform.processor() or platform.machine() or ""


def _distro() -> str:
    if platform.system() != "Linux":
        return (platform.system() or os.name).lower()
    try:
        return str(platform.freedesktop_os_release().get("ID") or "linux").lower()
    except (OSError, AttributeError):
        return "linux"


def _gpus(spawn: bool) -> list:
    exe = shutil.which("nvidia-smi") if spawn else None
    if not exe:
        return []
    try:
        r = subprocess.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=CLI_TIMEOUT_S, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return []
    out = []
    for line in (r.stdout or "").splitlines():
        name, _, mem = line.rpartition(",")
        if name.strip():
            out.append({"name": name.strip(), "vram_gb": round(float(mem) / 1024, 1) if mem.strip().isdigit() else None})
    return out


def hardware(home: Path, *, spawn: bool) -> dict:
    try:
        free = round(shutil.disk_usage(str(home)).free / 1e9, 1)
    except OSError:
        free = None
    return {"os": (platform.system() or os.name).lower(), "distro": _distro(), "release": platform.release(),
            "cpu": _cpu(), "cores": os.cpu_count(), "ram_gb": _ram_gb(), "gpu": _gpus(spawn), "disk_free_gb": free}


# ---- command-line tools --------------------------------------------------------------------------
def _version(exe: str) -> str:
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=CLI_TIMEOUT_S, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return "installed"
    m = re.search(r"\d+(?:\.\d+)+[\w.+-]*", (r.stdout or "") + " " + (r.stderr or ""))
    return m.group(0) if m else "installed"


def clis(*, spawn: bool) -> dict:
    """`{name: version | "installed" | None}`; versions only when `spawn`."""
    found = {n: shutil.which(n) for n in CLIS}
    out: dict = {n: (None if not p else "installed") for n, p in found.items()}
    if not spawn:
        return out
    threads = [threading.Thread(target=lambda n=n, p=p: out.__setitem__(n, _version(p)), daemon=True, name="halo-caps-cli")
               for n, p in found.items() if p]
    for t in threads:
        t.start()
    deadline = time.monotonic() + CLI_TIMEOUT_S + 1
    for t in threads:
        t.join(max(0.0, deadline - time.monotonic()))
    return out
