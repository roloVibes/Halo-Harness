"""halo_harness.process_alive -- whether a pid runs, on Windows, from the process's own exit code (Halo 3.4.1.1, the
3.4.1.0 R6 open item): OpenProcess + GetExitCodeProcess, no process spawned. One `tasklist` slower than its timeout on a
loaded box read a live session as dead (the 3.4.1.0 candidate's runner); bg_run.pid_alive and children.pid_running ask
here first.

    win_alive(pid) -> True | False | None     None: the API could not tell (the caller's fallback decides)
"""

from __future__ import annotations

from typing import Optional

STILL_ACTIVE = 259
ACCESS_DENIED, INVALID_PARAMETER = 5, 87


def win_alive(pid: int) -> Optional[bool]:
    """True while `pid` runs (its exit code is STILL_ACTIVE; a process of another user, whose handle is refused, runs
    too), False when it exited or no process has that pid, None when the API cannot tell."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            err = ctypes.get_last_error()
            return True if err == ACCESS_DENIED else False if err == INVALID_PARAMETER else None
        try:
            code = wintypes.DWORD()
            return code.value == STILL_ACTIVE if k32.GetExitCodeProcess(handle, ctypes.byref(code)) else None
        finally:
            k32.CloseHandle(handle)
    except Exception:
        return None
