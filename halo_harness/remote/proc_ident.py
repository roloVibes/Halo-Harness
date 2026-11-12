"""halo_harness.remote.proc_ident -- tell a process apart from a later one
that was given the same PID (3.0.2.0), for the pulse files (the supervisor's, its services').

    start_token(pid) -> str | None   a value fixed for the life of `pid`
    boot_time()      -> float | None the unix time the machine booted

`start_token` is the kernel's own record of when the process started:
Linux `/proc/<pid>/stat` field 22 qualified by the boot id, Windows
`GetProcessTimes` creation time, other POSIX `ps -o lstart=`. None means
"cannot tell here"; callers then fall back to `boot_time()`.
"""

from __future__ import annotations

import os
import re
from halo_harness import subprocess_safe as subprocess
import time
from typing import Optional


def _linux_token(pid: int) -> Optional[str]:
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8", errors="replace") as fh:
            stat = fh.read()
    except OSError:
        return None
    fields = stat[stat.rfind(")") + 2:].split()  # after "pid (comm) "; field 3 is fields[0]
    if len(fields) < 20:
        return None
    try:
        with open("/proc/sys/kernel/random/boot_id", "r", encoding="utf-8") as fh:
            boot = fh.read().strip()
    except OSError:
        boot = ""
    return f"linux:{boot}:{fields[19]}"


def _windows_token(pid: int) -> Optional[str]:
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            if not k32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                return None
            created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            return f"win:{created}"
        finally:
            k32.CloseHandle(handle)
    except Exception:
        return None


def _ps_token(pid: int) -> Optional[str]:
    try:
        out = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    text = " ".join((out.stdout or "").split())
    return f"ps:{text}" if out.returncode == 0 and text else None


def start_token(pid) -> Optional[str]:
    if not isinstance(pid, int) or pid <= 0:
        return None
    if os.name == "nt":
        return _windows_token(pid)
    if os.path.isdir("/proc/self") and os.path.exists(f"/proc/{os.getpid()}/stat"):
        return _linux_token(pid)
    return _ps_token(pid)


def boot_time() -> Optional[float]:
    if os.name == "nt":
        try:
            import ctypes
            k32 = ctypes.WinDLL("kernel32")
            k32.GetTickCount64.restype = ctypes.c_ulonglong
            return time.time() - k32.GetTickCount64() / 1000.0
        except Exception:
            return None
    try:
        with open("/proc/stat", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("btime "):
                    return float(line.split()[1])
    except (OSError, ValueError, IndexError):
        pass
    try:
        out = subprocess.run(["sysctl", "-n", "kern.boottime"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"sec\s*=\s*(\d+)", out.stdout or "")
    return float(m.group(1)) if m else None


BOOT_SLACK_S = 5.0


def pulse_alive(row: dict) -> bool:
    """A pulse row's process ({pid, pstart, started}) is running AND is the process that wrote it: the start token
    matches, or (no token here) it was written after this boot. 3.3.13.0 R3: moved here from the Signal bridge's
    pulse (remote/bridge_state.py, now the signal pack's); the supervisor's pulse and its services read it."""
    pid = row.get("pid") if isinstance(row, dict) else None
    if not isinstance(pid, int) or pid <= 0:
        return False
    from halo_harness.remote.registry import pid_alive
    if not pid_alive(pid):
        return False
    want = row.get("pstart")
    if want:
        have = start_token(pid)
        if have is not None:
            return have == want
    started, boot = row.get("started"), boot_time()
    if isinstance(started, (int, float)) and boot is not None and started < boot - BOOT_SLACK_S:
        return False  # written before this boot: the PID now belongs to something else
    return True
