"""scripts/realcheck/procs.py -- which processes on this machine belong to a scratch home, and the only kill there is.

A process belongs to a scratch home when the home's path is in its command line or anywhere in its environment
(Halo's children inherit HOME / USERPROFILE / BRIDGE_TEST_HOME), when it carries a `HALO_OWNER` marker that a
process of that home carries (Halo's own marker, 3.6.0.0 R10), or when its parent belongs (started after it). Nothing
else is ever matched: the owner's own Halo on the same machine, another worker's tests, a browser. `kill()` refuses a
pid whose start time is not the one the scan saw.

Linux reads /proc, macOS `ps -E`, Windows the process list and each process's PEB (command line, environment) with
ctypes. No psutil. A process this user cannot read is skipped (it is not ours)."""
from __future__ import annotations

import os
import signal
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field

OWNER_VAR = "HALO_OWNER"


@dataclass
class Proc:
    pid: int
    ppid: int
    name: str
    cmdline: str = ""
    env: dict = field(default_factory=dict)
    started: float = 0.0   # epoch seconds (0: unknown)
    cpu: float = -1.0      # CPU seconds used so far (-1: unknown)
    why: str = ""          # why it belongs (set by `belonging`)

    def short(self, width: int = 160) -> str:
        cmd = " ".join(self.cmdline.split())
        return f"pid {self.pid} ({self.name}) {cmd[:width]}"


def norm(text: str) -> str:
    """Paths compare with forward slashes and, on Windows and macOS, without case."""
    text = (text or "").replace("\\", "/")
    return text.lower() if sys.platform in ("win32", "darwin") else text


def needles_for(path) -> list:
    """The forms a scratch path takes in another process: as given and resolved (macOS /var -> /private/var)."""
    out = []
    for p in (str(path), os.path.realpath(str(path))):
        n = norm(p).rstrip("/")
        if n and n not in out:
            out.append(n)
    return out


# ---- Linux ---------------------------------------------------------------------------------------------------------
def _linux() -> dict:
    tck = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
    btime = 0.0
    try:
        for line in open("/proc/stat", encoding="ascii", errors="replace"):
            if line.startswith("btime "):
                btime = float(line.split()[1])
    except OSError:
        pass
    out = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        pid = int(d)
        try:
            stat = open(f"/proc/{d}/stat", encoding="utf-8", errors="replace").read()
            r = stat.rfind(")")
            name, f = stat[stat.find("(") + 1:r], stat[r + 2:].split()
            if f[0] == "Z":
                continue  # a zombie is gone; its parent has not read its status yet
            cmd = open(f"/proc/{d}/cmdline", "rb").read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except (OSError, IndexError, ValueError):
            continue
        env = {}
        try:
            for item in open(f"/proc/{d}/environ", "rb").read().split(b"\0"):
                k, _, v = item.decode("utf-8", "replace").partition("=")
                if k:
                    env[k] = v
        except OSError:
            pass
        out[pid] = Proc(pid, int(f[1]), name, cmd, env, btime + int(f[19]) / tck, (int(f[11]) + int(f[12])) / tck)
    return out


# ---- macOS ---------------------------------------------------------------------------------------------------------
def _cpu_text(t: str) -> float:
    days, _, t = t.rpartition("-")
    secs = 0.0
    for part in t.split(":"):
        secs = secs * 60 + float(part or 0)
    return secs + (int(days) * 86400 if days.isdigit() else 0)


def _mac() -> dict:
    """`ps -E` appends the environment to the command (own processes only: the rest are not ours anyway)."""
    try:
        text = subprocess.run(["ps", "-axwwE", "-o", "pid=,ppid=,stat=,time=,command="], capture_output=True, text=True,
                              errors="replace", timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    out = {}
    for line in text.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5 or not parts[0].isdigit():
            continue
        if parts[2].startswith("Z") or parts[4].startswith("<defunct>"):
            continue  # a zombie is gone; its parent has not read its status yet
        pid, ppid, cpu, rest = int(parts[0]), int(parts[1]), parts[3], parts[4]
        env = {}
        for tok in rest.split(" "):  # the env words come last as KEY=VALUE; a value with spaces stays in `cmdline`
            k, eq, v = tok.partition("=")
            if eq and k.isidentifier() and k.upper() == k:
                env[k] = v
        try:
            cpu_s = _cpu_text(cpu)
        except ValueError:
            cpu_s = -1.0
        out[pid] = Proc(pid, ppid, rest.split(" ", 1)[0].rsplit("/", 1)[-1], rest, env, 0.0, cpu_s)
    return out


def _mac_started(pid: int) -> float:
    try:
        text = subprocess.run(["ps", "-o", "lstart=", "-p", str(pid)], capture_output=True, text=True,
                              timeout=10, env=dict(os.environ, LC_ALL="C")).stdout.strip()
        return time.mktime(time.strptime(text, "%a %b %d %H:%M:%S %Y")) if text else 0.0
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0


# ---- every platform ------------------------------------------------------------------------------------------------
def snapshot() -> dict:
    """{pid: Proc} for every process this user can read."""
    if sys.platform == "win32":
        from realcheck import winproc
        return {p.pid: p for p in (Proc(**row) for row in winproc.snapshot())}
    if sys.platform == "darwin":
        return _mac()
    return _linux()


def started_at(pid: int) -> float:
    """When `pid` started (epoch seconds; 0 when it is gone or unknown)."""
    if sys.platform == "win32":
        from realcheck import winproc
        return winproc.started(pid)
    if sys.platform == "darwin":
        return _mac_started(pid)
    p = _linux_one(pid)
    return p.started if p else 0.0


def _linux_one(pid: int):
    try:
        stat = open(f"/proc/{pid}/stat", encoding="utf-8", errors="replace").read()
        f = stat[stat.rfind(")") + 2:].split()
        if f[0] == "Z":
            return None
        tck = os.sysconf("SC_CLK_TCK")
        btime = next(float(x.split()[1]) for x in open("/proc/stat") if x.startswith("btime "))
        return Proc(pid, int(f[1]), "", "", {}, btime + int(f[19]) / tck, (int(f[11]) + int(f[12])) / tck)
    except (OSError, IndexError, ValueError, StopIteration):
        return None


def alive(pid: int) -> bool:
    if sys.platform == "win32":
        from realcheck import winproc
        return winproc.alive(pid)
    if sys.platform.startswith("linux"):
        return _linux_one(pid) is not None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:  # a zombie answers kill(0); ps says Z
        st = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, timeout=10).stdout
        return bool(st.strip()) and not st.strip().startswith("Z")
    except (OSError, subprocess.SubprocessError):
        return True


def belonging(snap: dict, needles: list, owners=(), roots=()) -> dict:
    """{pid: Proc} of the processes in `snap` that belong to the scratch home named by `needles` (normalized paths),
    each with `why`. `owners`: HALO_OWNER values known to be ours; `roots`: {pid: start time} of the processes this
    script started itself (a pid the system has since given to another program does not match: its start differs)."""
    roots = roots if isinstance(roots, dict) else {pid: 0.0 for pid in roots}
    found: dict = {}
    for p in snap.values():
        if p.pid == os.getpid():
            continue
        if p.pid in roots and _same_start(p, roots[p.pid]):
            p.why = "started by realcheck"
        elif any(n in norm(p.cmdline) for n in needles):
            p.why = "scratch path in its command line"
        elif any(n in norm(v) for v in p.env.values() for n in needles):
            p.why = "scratch path in its environment"
        else:
            continue
        found[p.pid] = p
    marks = set(owners) | {p.env[OWNER_VAR] for p in found.values() if p.env.get(OWNER_VAR)}
    grew = True
    while grew:  # the marker and the parent line pull in what a stripped environment would hide
        grew = False
        for p in snap.values():
            if p.pid in found or p.pid == os.getpid():
                continue
            parent = found.get(p.ppid)
            if marks and p.env.get(OWNER_VAR) in marks:
                p.why = f"{OWNER_VAR}={p.env[OWNER_VAR]}"
            elif parent is not None and (not p.started or not parent.started or p.started >= parent.started - 1):
                p.why = f"child of pid {parent.pid}"
            else:
                continue
            found[p.pid] = p
            grew = True
    for p in found.values():  # macOS lists no start times: read them for the few found, so kill() can check them
        if not p.started:
            p.started = started_at(p.pid)
    return found


def _same_start(p: Proc, recorded: float) -> bool:
    if not recorded:
        return True
    now = p.started or started_at(p.pid)
    return not now or abs(now - recorded) <= 2


def kill(p: Proc) -> bool:
    """End one process the scan said is ours, by pid, only while its start time is still the one the scan saw."""
    if p.started and abs(started_at(p.pid) - p.started) > 2:
        return False  # gone, or the pid now names another program
    try:
        if sys.platform == "win32":
            from realcheck import winproc
            return winproc.kill(p.pid)
        os.kill(p.pid, signal.SIGKILL)
        return True
    except OSError:
        return False


def pointer_size() -> int:
    return struct.calcsize("P")
