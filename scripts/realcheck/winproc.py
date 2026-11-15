"""scripts/realcheck/winproc.py -- Windows: every process with its parent, command line, environment, start time and
CPU time (the process list plus each process's PEB, read with ctypes), and the end of one process by pid.

The PEB offsets are the 64-bit ones (ProcessParameters at +0x20; CommandLine at +0x70, Environment at +0x80,
EnvironmentSize at +0x3F0 in RTL_USER_PROCESS_PARAMETERS); a 32-bit Python reads names and parents only. A process
this user may not open is listed without them (it is not one of ours)."""
from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
ntdll = ctypes.WinDLL("ntdll")

TH32CS_SNAPPROCESS = 0x2
QUERY_LIMITED, VM_READ, TERMINATE, SYNCHRONIZE = 0x1000, 0x0010, 0x0001, 0x00100000
STILL_ACTIVE = 259
EPOCH_AS_FILETIME = 116444736000000000
HANDLE = wintypes.HANDLE


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


class PBI(ctypes.Structure):
    _fields_ = [("ExitStatus", ctypes.c_void_p), ("PebBaseAddress", ctypes.c_void_p), ("AffinityMask", ctypes.c_void_p),
                ("BasePriority", ctypes.c_void_p), ("UniqueProcessId", ctypes.c_void_p),
                ("InheritedFromUniqueProcessId", ctypes.c_void_p)]


k32.CreateToolhelp32Snapshot.restype = HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
k32.Process32FirstW.argtypes = [HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
k32.Process32NextW.argtypes = [HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
k32.OpenProcess.restype = HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.CloseHandle.argtypes = [HANDLE]
k32.ReadProcessMemory.argtypes = [HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
k32.GetProcessTimes.argtypes = [HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
k32.GetExitCodeProcess.argtypes = [HANDLE, ctypes.POINTER(wintypes.DWORD)]
k32.TerminateProcess.argtypes = [HANDLE, wintypes.UINT]
ntdll.NtQueryInformationProcess.argtypes = [HANDLE, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
                                            ctypes.POINTER(ctypes.c_ulong)]
ntdll.NtQueryInformationProcess.restype = ctypes.c_long

WIDE = struct.calcsize("P") == 8


def _read(h, addr: int, size: int):
    if not addr or size <= 0:
        return None
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)) or got.value != size:
        return None
    return buf.raw


def _ptr(h, addr: int) -> int:
    raw = _read(h, addr, 8)
    return struct.unpack("<Q", raw)[0] if raw else 0


def _peb_strings(h) -> "tuple[str, dict]":
    """(command line, environment) from the process's PEB; ('', {}) when it cannot be read."""
    if not WIDE:
        return "", {}
    pbi = PBI()
    if ntdll.NtQueryInformationProcess(h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None) != 0 or not pbi.PebBaseAddress:
        return "", {}
    params = _ptr(h, pbi.PebBaseAddress + 0x20)
    if not params:
        return "", {}
    cmd = ""
    us = _read(h, params + 0x70, 16)
    if us:
        length, _max, _pad, buf = struct.unpack("<HHIQ", us)
        raw = _read(h, buf, min(length, 65534))
        cmd = raw.decode("utf-16-le", "replace") if raw else ""
    env: dict = {}
    where, size = _ptr(h, params + 0x80), _ptr(h, params + 0x3F0)
    raw = _read(h, where, min(size, 1 << 20)) if where and size else None
    if raw:
        for item in raw.decode("utf-16-le", "replace").split("\0"):
            k, eq, v = item.partition("=")
            if eq and k:  # "=C:=C:\\..." entries have an empty name
                env[k] = v
    return cmd, env


def _times(h) -> "tuple[float, float]":
    c, e, k, u = (wintypes.FILETIME() for _ in range(4))
    if not k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
        return 0.0, -1.0
    ft = lambda t: (t.dwHighDateTime << 32) | t.dwLowDateTime  # noqa: E731
    return (ft(c) - EPOCH_AS_FILETIME) / 1e7, (ft(k) + ft(u)) / 1e7


def snapshot() -> list:
    """[{pid, ppid, name, cmdline, env, started, cpu}] for every process (rows the Proc dataclass takes)."""
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == HANDLE(-1).value:
        return []
    rows = []
    try:
        e = PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(e)
        ok = k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            rows.append({"pid": int(e.th32ProcessID), "ppid": int(e.th32ParentProcessID), "name": e.szExeFile})
            ok = k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        k32.CloseHandle(snap)
    for row in rows:
        row.update(cmdline="", env={}, started=0.0, cpu=-1.0)
        if row["pid"] in (0, 4):
            continue
        h = k32.OpenProcess(QUERY_LIMITED | VM_READ, False, row["pid"]) or k32.OpenProcess(QUERY_LIMITED, False, row["pid"])
        if not h:
            continue
        try:
            row["started"], row["cpu"] = _times(h)
            row["cmdline"], row["env"] = _peb_strings(h)
        except OSError:
            pass
        finally:
            k32.CloseHandle(h)
    return rows


def started(pid: int) -> float:
    h = k32.OpenProcess(QUERY_LIMITED, False, int(pid))
    if not h:
        return 0.0
    try:
        return _times(h)[0] if alive_handle(h) else 0.0
    finally:
        k32.CloseHandle(h)


def alive_handle(h) -> bool:
    code = wintypes.DWORD(0)
    return bool(k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == STILL_ACTIVE


def alive(pid: int) -> bool:
    h = k32.OpenProcess(QUERY_LIMITED, False, int(pid))
    if not h:
        return False
    try:
        return alive_handle(h)
    finally:
        k32.CloseHandle(h)


def kill(pid: int) -> bool:
    h = k32.OpenProcess(TERMINATE | QUERY_LIMITED, False, int(pid))
    if not h:
        return False
    try:
        return bool(k32.TerminateProcess(h, 1))
    finally:
        k32.CloseHandle(h)
