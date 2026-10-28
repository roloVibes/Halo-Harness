"""halo_harness.ollama_steward.resources_system -- Halo 3.3.5.0 R1: the
machine's RAM and CPU for the Local tab's live strip (the GPU readers are
resources_readers.py; the seams are its `Seams`). Stdlib only, read-only.

    ram(seams)      {used, total, source}: /proc/meminfo (MemTotal - MemAvailable) on
                    Linux; GlobalMemoryStatusEx (ctypes) on Windows; on a Mac `sysctl -n
                    hw.memsize` and `memory_pressure`'s free percentage (no sudo)
    Cpu(seams)      `.read()` -> (percent | None, source or why): the whole machine
                    between two reads (the first answers None): /proc/stat on Linux,
                    GetSystemTimes (ctypes) on Windows, `ps -A -o %cpu=` over the core
                    count on a Mac
"""

from __future__ import annotations

import os
import re
from typing import Optional

from halo_harness.ollama_steward.resources_readers import TIMEOUT_S, Seams, _mac_total, _num, off


def parse_meminfo(text: str) -> Optional[dict]:
    vals = {m.group(1): int(m.group(2)) * 1024 for m in re.finditer(r"^(\w+):\s+(\d+) kB", text or "", re.M)}
    total, avail = vals.get("MemTotal"), vals.get("MemAvailable", vals.get("MemFree"))
    if not total or avail is None:
        return None
    return {"used": total - avail, "total": total, "source": "/proc/meminfo (MemTotal - MemAvailable)"}


def parse_memory_pressure(text: str) -> Optional[float]:
    """`System-wide memory free percentage: 63%` -> 0.63."""
    m = re.search(r"free percentage:\s*(\d+(?:\.\d+)?)%", text or "")
    return float(m.group(1)) / 100.0 if m else None


def _win_mem():
    import ctypes

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    st = MEMORYSTATUSEX()
    st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):  # type: ignore[attr-defined]
        return None
    return st.ullTotalPhys - st.ullAvailPhys, st.ullTotalPhys


def ram(seams: Seams):
    """The machine's RAM in use, or (None, why)."""
    if off(seams):
        return None, "background reads are off"
    if seams.platform.startswith("linux"):
        got = parse_meminfo(seams.read_file("/proc/meminfo") if seams.read_file else "")
        return (got, None) if got else (None, "no /proc/meminfo")
    if seams.platform.startswith("win"):
        try:
            pair = ((seams.win or {}).get("mem") or _win_mem)()
        except Exception:
            pair = None
        if not pair:
            return None, "no GlobalMemoryStatusEx answer"
        return {"used": int(pair[0]), "total": int(pair[1]), "source": "GlobalMemoryStatusEx"}, None
    total = _mac_total(seams)
    free = parse_memory_pressure(seams.runner(["memory_pressure"], TIMEOUT_S) or "") if seams.runner else None
    if total is None or free is None:
        return None, "no sysctl or memory_pressure answer"
    return {"used": int(total * (1 - free)), "total": total,
            "source": "memory_pressure's free percentage of sysctl hw.memsize"}, None


def _win_times():
    import ctypes

    class FILETIME(ctypes.Structure):
        _fields_ = [("lo", ctypes.c_ulong), ("hi", ctypes.c_ulong)]
    idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
    k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    if not k32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        return None
    v = lambda t: (t.hi << 32) | t.lo  # noqa: E731
    return v(idle), v(kernel), v(user)


def parse_proc_stat(text: str):
    """The `cpu` line -> (idle, total) jiffies (iowait counted idle)."""
    m = re.search(r"^cpu\s+(.+)$", text or "", re.M)
    if not m:
        return None
    nums = [int(x) for x in m.group(1).split() if x.isdigit()]
    if len(nums) < 4:
        return None
    return nums[3] + (nums[4] if len(nums) > 4 else 0), sum(nums)


class Cpu:
    """Whole-machine CPU % between two reads (the first read answers None)."""

    def __init__(self, seams: Seams) -> None:
        self.seams, self.last = seams, None

    def _mac(self):
        out = self.seams.runner(["ps", "-A", "-o", "%cpu="], TIMEOUT_S) if self.seams.runner else None
        if out is None:
            return None, "no ps answer"
        vals = [_num(x) for x in out.split()]
        total = sum(v for v in vals if v)
        return round(min(100.0, total / max(1, os.cpu_count() or 1)), 1), "ps -A -o %cpu over the core count"

    def read(self):
        s = self.seams
        if off(s):
            return None, "background reads are off"
        if s.platform.startswith("darwin"):
            return self._mac()
        if s.platform.startswith("win"):
            try:
                t = ((s.win or {}).get("times") or _win_times)()
            except Exception:
                t = None
            pair = (t[0], t[1] + t[2]) if t else None  # the kernel time holds the idle time
            src = "GetSystemTimes"
        else:
            pair = parse_proc_stat(s.read_file("/proc/stat") if s.read_file else "")
            src = "/proc/stat"
        if pair is None:
            return None, f"no {src} answer"
        prev, self.last = self.last, pair
        if prev is None or pair[1] <= prev[1]:
            return None, "the first read (the next one has a figure)"
        busy = 1.0 - (pair[0] - prev[0]) / (pair[1] - prev[1])
        return round(max(0.0, min(100.0, busy * 100.0)), 1), src
