"""halo_harness.supervise.procgroup -- a pack service and its children as one group (Halo 3.3.14.0 R2, REVIEW #17:
CORE-3 / REMOTE-6 / PERMS-13 / PACKS-10; docs/SUPERVISE.md "Pack services").

    popen_kwargs() -> dict     what Popen needs so the service starts its own group: a new session on POSIX,
                               CREATE_NEW_PROCESS_GROUP on Windows (the caller adds its own flags)
    attach(proc) -> Group|None the group of a service just started: on POSIX its session (the pgid is its pid), on
                               Windows a Job object with KILL_ON_JOB_CLOSE the process is put in; None for anything that
                               is not a real subprocess.Popen (the tests' fake processes are never signalled)
    term(group)                SIGTERM to the whole group (POSIX); the Job object ended (Windows)
    kill(group)                SIGKILL to the whole group (POSIX); the Job object ended (Windows)
    finish(group)              the service has ended: whatever it left in its group goes too, and the Job is closed

On Windows a child the service starts after `attach` is in its Job, so TerminateJobObject ends signal-cli's JVM with
its wrapper. When the Job could not be made, the tree is ended by `taskkill /T /F` instead.
"""

from __future__ import annotations

import os
from halo_harness import subprocess_safe as subprocess
from typing import Optional

_KILL_ON_JOB_CLOSE, _EXTENDED_LIMITS = 0x2000, 9


class Group:
    def __init__(self, pid: int, job=None) -> None:
        self.pid, self.job = int(pid), job


def popen_kwargs() -> dict:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def attach(proc) -> Optional[Group]:
    if not isinstance(proc, subprocess.STDLIB_POPEN):  # 3.4.1.2: any Popen, the safe module's or the standard one
        return None
    if os.name != "nt":
        return Group(proc.pid)
    return Group(proc.pid, _job_for(proc))


def term(group: Optional[Group]) -> None:
    _end(group, "SIGTERM")


def kill(group: Optional[Group]) -> None:
    _end(group, "SIGKILL")


def finish(group: Optional[Group]) -> None:
    if group is None:
        return
    _end(group, "SIGTERM")
    if group.job is not None:
        _k32().CloseHandle(group.job)
        group.job = None


def _end(group: Optional[Group], sig: str) -> None:
    if group is None:
        return
    if os.name != "nt":
        import signal
        try:
            if group.pid != os.getpgid(0):  # never the supervisor's own group
                os.killpg(group.pid, getattr(signal, sig))
        except OSError:
            pass  # the group is empty: nothing left to end
        return
    if group.job is not None and _k32().TerminateJobObject(group.job, 1):
        return
    try:
        subprocess.run(["taskkill", "/PID", str(group.pid), "/T", "/F"], capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass


def _k32():
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    k32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
    k32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    k32.TerminateJobObject.argtypes = (wintypes.HANDLE, wintypes.UINT)
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    return k32


def _job_for(proc):
    """A Job object holding `proc`, ended when its last handle closes (the supervisor's own exit included)."""
    try:
        import ctypes
        from ctypes import wintypes

        class _Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class _Io(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ("Read", "Write", "Other", "ReadB", "WriteB", "OtherB")]

        class _Extended(ctypes.Structure):
            _fields_ = [("Basic", _Basic), ("Io", _Io), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        k32 = _k32()
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = _Extended()
        info.Basic.LimitFlags = _KILL_ON_JOB_CLOSE
        if not (k32.SetInformationJobObject(job, _EXTENDED_LIMITS, ctypes.byref(info), ctypes.sizeof(info))
                and k32.AssignProcessToJobObject(job, int(proc._handle))):
            k32.CloseHandle(job)
            return None
        return job
    except (OSError, AttributeError, ValueError):
        return None
