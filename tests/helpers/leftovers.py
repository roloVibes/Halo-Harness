"""tests/helpers/leftovers.py -- run_all's check that a test module leaves no process running (3.6.0.1).

`begin(module, folders)` before a module runs takes one look at every process (pid + start time) and puts a marker in
this process's environment, `RUNALL_MODULE=<run id>/<module>`, that every program a test starts inherits unless the
test builds the program's environment from nothing. `end(token)` after the module finds the processes that did not
exist at `begin` and are this run's by any of:
  (a) a descendant of this process (the parent chain is checked with start times: a child is never older than its
      parent, so a parent pid the OS reused breaks the chain);
  (b) this run's marker in its environment (Linux /proc/<pid>/environ, macOS `ps -E`, Windows the process's PEB);
  (c) a command line naming a folder of this module (its home, the run root, any tempfile.mkdtemp made while it ran).
A zombie or an exited process is not counted (it cannot run and cannot be signalled). The check waits while something
is still there, up to GRACE_S (Halo's own way-out budget plus a margin: a Halo that is closing correctly is not a
leftover), then names every process still there (the module is red) and ends by pid, the newest first (children
before their parents), each only after its start time was read again and matched, ONLY those the run provably started:
(a) and (b). One found by (c) alone is named, never ended (a developer's `tail -f <run folder>/x.log` from another
terminal looks the same), except on Windows when its parent is WmiPrvSE: a program Halo starts through WMI has that
parent and no inherited environment, so only (c) finds it. Nothing is ever ended by name, and nothing that existed
before the module began is touched. A report line shows the argv only, cut to 200 characters, never an environment
(macOS `ps -E` puts the environment after the command; the argv is read again without it).
"""
from __future__ import annotations

import calendar
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

MARK = "RUNALL_MODULE"
WIN = os.name == "nt"
HAVE_PROC = not WIN and os.path.exists("/proc/self/stat")


@dataclass
class Proc:
    pid: int
    ppid: int
    start: int  # comparable on one system: Linux clock ticks since boot, Windows FILETIME, macOS UTC epoch seconds
    cmd: str = ""   # what the folder rule reads (macOS: argv followed by the environment)
    mark: str = ""
    args: str = ""  # the argv alone, the only text a report line shows ("" until known)
    why: str = ""   # how find() knew it: "child", "marker" or "folder"
    parent_exe: str = ""  # Windows: the parent's program name from the snapshot ("" when the parent is younger)


# ---- one look at every process ------------------------------------------------------------------------------------

def _scan_linux(want) -> dict:
    out = {}
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        try:
            with open(f"/proc/{pid}/stat", "rb") as fh:
                after = fh.read().decode("utf-8", "replace").rsplit(")", 1)[-1].split()
            state, ppid, start = after[0], int(after[1]), int(after[19])
        except (OSError, IndexError, ValueError):
            continue
        if state in ("Z", "X", "x"):
            continue
        p = Proc(pid, ppid, start)
        if want(pid, start):
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as fh:
                    p.cmd = p.args = fh.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
            except OSError:
                pass
            try:
                with open(f"/proc/{pid}/environ", "rb") as fh:
                    for item in fh.read().split(b"\0"):
                        if item.startswith(MARK.encode() + b"="):
                            p.mark = item[len(MARK) + 1:].decode("utf-8", "replace")
            except OSError:
                pass
        out[pid] = p
    return out


PS_ARGS = ["ps", "-A", "-ww", "-E", "-o", "pid=", "-o", "ppid=", "-o", "stat=", "-o", "lstart=", "-o", "command="]


def parse_ps(text: str, skip_pid: int = -1, with_env: bool = True) -> dict:
    """Rows of `ps -A -ww -E -o pid= -o ppid= -o stat= -o lstart= -o command=` read with TZ=UTC0 LC_ALL=C (macOS:
    `-E` appends the environment of this user's processes to the command). A zombie (stat Z) is left out.
    `with_env=False`: rows read without -E, whose command is the argv alone (Proc.args)."""
    out = {}
    for line in text.splitlines():
        parts = line.split(None, 8)  # pid ppid stat + lstart's five fields + the command (and its environment)
        if len(parts) < 8:
            continue
        try:
            pid, ppid = int(parts[0]), int(parts[1])
            start = calendar.timegm(time.strptime(" ".join(parts[3:8]), "%a %b %d %H:%M:%S %Y"))
        except ValueError:
            continue
        if pid == skip_pid or parts[2].startswith("Z"):
            continue
        cmd = parts[8] if len(parts) > 8 else ""
        mark = ""
        at = cmd.find(f" {MARK}=")
        if at >= 0:
            mark = cmd[at + len(MARK) + 2:].split(" ", 1)[0]
        out[pid] = Proc(pid, ppid, start, cmd, mark, args="" if with_env else cmd)
    return out


def _scan_ps(_want) -> dict:
    env = {**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC0"}
    proc = subprocess.Popen(PS_ARGS, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, errors="replace", env=env)
    try:
        text, _ = proc.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise OSError("ps did not answer in 20 s")
    return parse_ps(text, skip_pid=proc.pid)  # the scan's own ps is new since begin and a child of this process


if WIN:
    import ctypes
    import struct
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _ntdll = ctypes.WinDLL("ntdll")
    _QUERY_LIMITED, _VM_READ, _TERMINATE, _SYNCHRONIZE, _STILL_ACTIVE = 0x1000, 0x0010, 0x0001, 0x00100000, 259

    class _ENTRY(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    class _PBI(ctypes.Structure):
        _fields_ = [("ExitStatus", ctypes.c_void_p), ("PebBaseAddress", ctypes.c_void_p),
                    ("AffinityMask", ctypes.c_void_p), ("BasePriority", ctypes.c_void_p),
                    ("UniqueProcessId", ctypes.c_void_p), ("InheritedFromUniqueProcessId", ctypes.c_void_p)]

    _H = wintypes.HANDLE
    _k32.CreateToolhelp32Snapshot.restype = _H
    _k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _k32.Process32FirstW.argtypes = [_H, ctypes.POINTER(_ENTRY)]
    _k32.Process32NextW.argtypes = [_H, ctypes.POINTER(_ENTRY)]
    _k32.OpenProcess.restype = _H
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.CloseHandle.argtypes = [_H]
    _k32.GetProcessTimes.argtypes = [_H] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    _k32.GetExitCodeProcess.argtypes = [_H, ctypes.POINTER(wintypes.DWORD)]
    _k32.TerminateProcess.argtypes = [_H, wintypes.UINT]
    _k32.WaitForSingleObject.argtypes = [_H, wintypes.DWORD]
    _k32.ReadProcessMemory.argtypes = [_H, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                       ctypes.POINTER(ctypes.c_size_t)]
    _ntdll.NtQueryInformationProcess.argtypes = [_H, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong,
                                                 ctypes.POINTER(ctypes.c_ulong)]
    _ntdll.NtQueryInformationProcess.restype = ctypes.c_long

    def _win_start(h) -> "int | None":
        """The creation FILETIME of a process that still runs, else None."""
        code = wintypes.DWORD()
        if not _k32.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != _STILL_ACTIVE:
            return None
        c, e, k, u = (wintypes.FILETIME() for _ in range(4))
        if not _k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e), ctypes.byref(k), ctypes.byref(u)):
            return None
        return (c.dwHighDateTime << 32) | c.dwLowDateTime

    def _read(h, addr: int, size: int):
        if not addr or size <= 0:
            return None
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        if not _k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)) or got.value != size:
            return None
        return buf.raw

    def _ptr(h, addr: int) -> int:
        raw = _read(h, addr, 8)
        return struct.unpack("<Q", raw)[0] if raw else 0

    def _peb(h) -> "tuple[str, str]":
        """(command line, this run's marker) from the process's PEB (64-bit offsets); ('', '') when unreadable."""
        if struct.calcsize("P") != 8:
            return "", ""
        pbi = _PBI()
        if _ntdll.NtQueryInformationProcess(h, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None) != 0 \
                or not pbi.PebBaseAddress:
            return "", ""
        params = _ptr(h, pbi.PebBaseAddress + 0x20)
        if not params:
            return "", ""
        cmd, mark = "", ""
        us = _read(h, params + 0x70, 16)
        if us:
            length, _max, _pad, buf = struct.unpack("<HHIQ", us)
            raw = _read(h, buf, min(length, 65534))
            cmd = raw.decode("utf-16-le", "replace") if raw else ""
        where, size = _ptr(h, params + 0x80), _ptr(h, params + 0x3F0)
        raw = _read(h, where, min(size, 1 << 20)) if where and size else None
        if raw:
            for item in raw.decode("utf-16-le", "replace").split("\0"):
                if item.upper().startswith(MARK + "="):
                    mark = item[len(MARK) + 1:]
        return cmd, mark

    def _scan_win(want) -> dict:
        snap = _k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
        if not snap or snap == _H(-1).value:
            raise OSError("CreateToolhelp32Snapshot failed")
        rows = []
        try:
            e = _ENTRY()
            e.dwSize = ctypes.sizeof(e)
            ok = _k32.Process32FirstW(snap, ctypes.byref(e))
            while ok:
                rows.append((int(e.th32ProcessID), int(e.th32ParentProcessID), e.szExeFile))
                ok = _k32.Process32NextW(snap, ctypes.byref(e))
        finally:
            _k32.CloseHandle(snap)
        names = {pid: exe for pid, _ppid, exe in rows}
        out = {}
        for pid, ppid, _exe in rows:
            if pid in (0, 4):
                continue
            h = _k32.OpenProcess(_QUERY_LIMITED, False, pid)
            if not h:
                continue  # one this user may not open is not one of ours
            try:
                start = _win_start(h)
            finally:
                _k32.CloseHandle(h)
            if start is None:
                continue
            p = Proc(pid, ppid, start, parent_exe=names.get(ppid, ""))
            if want(pid, start):
                h = _k32.OpenProcess(_QUERY_LIMITED | _VM_READ, False, pid)
                if h:
                    try:
                        p.cmd, p.mark = _peb(h)
                        p.args = p.cmd
                    except OSError:
                        pass
                    finally:
                        _k32.CloseHandle(h)
            out[pid] = p
        for p in out.values():  # a parent pid now naming a younger process is not this one's parent
            parent = out.get(p.ppid)
            if parent is not None and parent.start > p.start:
                p.parent_exe = ""
        return out


def scan(want=None) -> dict:
    """{pid: Proc} of every running process this user can see; `want(pid, start)` says whose command line and
    marker are read (None: nobody's; macOS reads them all in its one `ps`)."""
    want = want or (lambda _pid, _start: False)
    if WIN:
        return _scan_win(want)
    if HAVE_PROC:
        return _scan_linux(want)
    return _scan_ps(want)


# ---- ending one process by pid ------------------------------------------------------------------------------------

def _row_now(pid: int) -> "Proc | None":
    """`pid` read now on POSIX (None: gone, a zombie, or unreadable); without `ps -E`, so its command is the argv."""
    if HAVE_PROC:
        return _scan_one_linux(pid)
    env = {**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC0"}
    try:
        got = subprocess.run(["ps", "-ww", "-o", "pid=", "-o", "ppid=", "-o", "stat=", "-o", "lstart=", "-o",
                              "command=", "-p", str(pid)], capture_output=True, text=True, timeout=10, env=env)
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_ps(got.stdout or "", with_env=False).get(pid)


def _start_now(pid: int) -> "int | None":
    """`pid`'s start time read now on POSIX (None: gone, a zombie, or unreadable)."""
    row = _row_now(pid)
    return row.start if row else None


def _fill_args(procs) -> None:
    """macOS: the scan's `ps -E` command holds the environment after the argv; the argv alone is read again, without
    -E, for each process the report names, and kept only when the pid still has the same start time."""
    if WIN or HAVE_PROC:
        return  # the argv was read alone already (PEB command line, /proc/<pid>/cmdline)
    for p in procs:
        if not p.args:
            row = _row_now(p.pid)
            if row is not None and row.start == p.start:
                p.args = row.cmd


def _scan_one_linux(pid: int) -> "Proc | None":
    try:
        with open(f"/proc/{pid}/stat", "rb") as fh:
            after = fh.read().decode("utf-8", "replace").rsplit(")", 1)[-1].split()
        if after[0] in ("Z", "X", "x"):
            return None
        return Proc(pid, int(after[1]), int(after[19]))
    except (OSError, IndexError, ValueError):
        return None


def end_one(p: Proc, wait_s: float = 5.0) -> bool:
    """End `p` by its pid, only when the pid still names the process with `p`'s start time. True when it is gone."""
    if WIN:
        h = _k32.OpenProcess(_TERMINATE | _QUERY_LIMITED | _SYNCHRONIZE, False, p.pid)
        if not h:
            return not _alive(p)
        try:
            if _win_start(h) != p.start:  # read on the same handle that is then terminated: no pid-reuse race
                return not _alive(p)
            _k32.TerminateProcess(h, 1)
            _k32.WaitForSingleObject(h, int(wait_s * 1000))
        finally:
            _k32.CloseHandle(h)
        return not _alive(p)
    if _start_now(p.pid) != p.start:
        return True
    try:
        os.kill(p.pid, signal.SIGKILL)
    except OSError:
        pass
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        try:
            os.waitpid(p.pid, os.WNOHANG)  # reaps it when it is this process's own child; elsewhere no-op
        except (ChildProcessError, OSError):
            pass
        if not _alive(p):
            return True
        time.sleep(0.05)
    return not _alive(p)


def _alive(p: Proc) -> bool:
    if WIN:
        h = _k32.OpenProcess(_QUERY_LIMITED, False, p.pid)
        if not h:
            return False
        try:
            return _win_start(h) == p.start
        finally:
            _k32.CloseHandle(h)
    return _start_now(p.pid) == p.start


# ---- the check around one module ----------------------------------------------------------------------------------

_RUN_ID: "str | None" = None


def run_id() -> str:
    """This process's pid and start time: two runs on one machine never match each other's processes."""
    global _RUN_ID
    if _RUN_ID is None:
        me = scan().get(os.getpid())
        _RUN_ID = f"{os.getpid()}-{me.start if me else int(time.time())}"
    return _RUN_ID


def _tracked() -> list:
    from tests.helpers import runner
    return runner._tracked_temp_dirs


def _norm(text: str) -> str:
    return os.path.normcase(text.replace("/", os.sep)) if WIN else text


def begin(module: str, folders=()) -> dict:
    known = {(p.pid, p.start) for p in scan().values()}
    value = f"{run_id()}/{module}"
    token = {"module": module, "known": known, "prev": os.environ.get(MARK), "value": value,
             "folders": [str(f) for f in folders], "tracked_from": len(_tracked())}
    os.environ[MARK] = value
    return token


#: 3.6.0.1 (the first CI run with the check on, macOS legs): a browser's own helpers are the browser's, not the run's
#: and not Halo's. Its crash handler outlives it for a moment; its updater is the machine's own service, woken by any
#: start of that browser. They are neither counted nor ended. A browser a test leaves running still is counted.
BROWSER_HELPERS = ("chrome_crashpad_handler", "crashpad_handler", "googleupdater", "googlesoftwareupdate", "ksfetch",
                   "microsoftedgeupdate")


def _browser_helper(p: Proc) -> bool:
    """Whether `p`'s program (its path up to the first ` --` option, by its last segment) is one of BROWSER_HELPERS."""
    head = (p.cmd or "").split(" --", 1)[0].replace("\\", "/").rstrip("/").rsplit("/", 1)[-1].lower()
    return any(head.startswith(h) for h in BROWSER_HELPERS)


def find(token: dict) -> list:
    """The processes this module started that still run (see the module's docstring)."""
    known, me = token["known"], os.getpid()
    procs = scan(lambda pid, start: (pid, start) not in known)
    folders = [_norm(os.path.normpath(f)) for f in token["folders"] + list(_tracked()[token["tracked_from"]:])
               if f and len(str(f)) > 4]
    ours_mark = token["value"].split("/", 1)[0] + "/"

    def descends(p: Proc) -> bool:
        seen, cur = set(), p
        while cur.pid not in seen:
            seen.add(cur.pid)
            parent = procs.get(cur.ppid)
            if parent is None or parent.start > cur.start:
                return False
            if parent.pid == me:
                return True
            cur = parent
        return False

    found = []
    for pid, p in procs.items():
        if pid == me or (pid, p.start) in known or _browser_helper(p):
            continue
        if descends(p):
            p.why = "child"
        elif p.mark.startswith(ours_mark):
            p.why = "marker"
        elif any(f in _norm(p.cmd) for f in folders):
            p.why = "folder"
        else:
            continue
        found.append(p)
    return found


def _may_end(p: Proc, win: bool = WIN) -> bool:
    """Only what the run provably started is ended: a child of it or a carrier of its marker. A command line naming a
    run folder proves nothing (anyone may open that folder), except on Windows under WmiPrvSE, how Halo starts its kept
    programs there (they inherit neither the parent chain nor the environment)."""
    if p.why in ("child", "marker"):
        return True
    return win and p.why == "folder" and p.parent_exe.lower() == "wmiprvse.exe"


def _grace_s() -> float:
    """How long a module's processes may take to go: Halo's own way-out budget plus a margin, at least 8 s."""
    try:
        from halo_harness.closing import QUIT_BUDGET_S
    except Exception:  # noqa: BLE001 -- the rig must run even when the product does not import
        QUIT_BUDGET_S = 4.0
    return max(8.0, float(QUIT_BUDGET_S) + 4.0)


def end(token: dict, grace_s: "float | None" = None) -> dict:
    """{"left": [(Proc, True ended / False could not be / None not ended: not proven the run's)], "seconds": the
    check's cost}. Waits only while something is still there. Puts this process's marker back as it was."""
    t0 = time.monotonic()
    try:
        found = find(token)
        if found:
            deadline = time.monotonic() + (_grace_s() if grace_s is None else grace_s)
            while found and time.monotonic() < deadline:
                time.sleep(0.25)
                found = find(token)
        _fill_args(found)
        left = [(p, end_one(p) if _may_end(p) else None)
                for p in sorted(found, key=lambda p: p.start, reverse=True)]
    finally:
        if token["prev"] is None:
            os.environ.pop(MARK, None)
        else:
            os.environ[MARK] = token["prev"]
    return {"left": left, "seconds": time.monotonic() - t0}


def report_lines(module: str, result: dict) -> list:
    """One line per process left: its pid and its argv only (never `cmd`, which on macOS carries the environment)."""
    def how(ok) -> str:
        if ok is None:
            return ("NOT ENDED: found only because its command line names a folder of this run, which does not prove "
                    "the run started it; end it yourself if it is the test's")
        return "ended by pid" if ok else "COULD NOT BE ENDED"
    return [f"[LEFTOVER] {module}: pid {p.pid} {(p.args or '').strip()[:200] or '(command line unreadable)'} -- "
            + how(ok) for p, ok in result["left"]]


if __name__ == "__main__":  # a manual cost look: python -m tests.helpers.leftovers
    t = time.monotonic()
    tok = begin("cost-probe")
    mid = time.monotonic()
    res = end(tok)
    print(f"begin {mid - t:.3f}s, end {res['seconds']:.3f}s, {len(tok['known'])} processes, left {len(res['left'])}",
          file=sys.stdout)
