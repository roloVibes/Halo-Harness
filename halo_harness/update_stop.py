"""halo_harness.update_stop -- what `halo update` stops before it installs
(Halo 3.2.2.0 R3, docs/COMMANDS.md "halo update").

    lingering()          every process of this install still running: the
                         registry first (children.json, studio.json, the
                         supervisor's pulse, the local model servers that
                         run on this venv's python), then the process scan
                         (update.other_halo_pids / other_halo_processes)
    stop_lingering()     stops them in that order, one line each; returns
                         (lines, the supervisor was running)
    refusal_lines()      `--keep-running`: each one named with the command
                         that stops it
    restart_supervisor() `halo supervise --daemon` on the new version

The scan goes through `update.other_halo_pids` first (the seam every update
test fakes), so a test that fakes it never lists or stops a real process.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from halo_harness import children as C
from halo_harness import children_stop as CS
from halo_harness import update as upd

_stop = CS.stop_entry  # the seam a test replaces


def _supervisor_entry(state_dir=None) -> Optional[dict]:
    try:
        from halo_harness.supervise import pulse
        row = pulse.read(C._state(state_dir))
    except Exception:
        return None
    pid = row.get("pid")
    if not row.get("running") or not isinstance(pid, int) or pid == os.getpid():
        return None
    return {"pid": pid, "start_time": C.start_time(pid), "what": "supervisor", "cmd": ["halo", "supervise"],
            "source": "pulse"}


def registered(state_dir=None) -> list:
    """The registry half: children.json, the Studio, the supervisor, venv-held local servers."""
    out = [e for e in C.prune(state_dir) if e.get("pid") != os.getpid()]
    extra = [CS.studio_entry(state_dir), _supervisor_entry(state_dir)]
    extra += [e for e in C.local_servers(state_dir, venv_only=True) if C.alive(e)]
    for e in extra:
        if e and all(x.get("pid") != e["pid"] for x in out):
            out.append(e)
    return out


def scanned(known=()) -> list:
    """The scan half, minus `known` pids and anything below them (a listed
    background run's own `halo -p` child goes with it)."""
    pids = [p for p in upd.other_halo_pids() if p != os.getpid()]
    if not pids:
        return []
    rows = {r["pid"]: r for r in upd.other_halo_processes()}
    found = [rows.get(p) or {"pid": p, "ppid": None, "what": "halo", "cmd": ""} for p in pids]
    skip = set(known)
    changed = True
    while changed:
        changed = False
        for r in found:
            if r["pid"] not in skip and r.get("ppid") in skip:
                skip.add(r["pid"])
                changed = True
    return [{"pid": r["pid"], "start_time": C.start_time(r["pid"]), "what": r.get("what") or "halo",
             "cmd": str(r.get("cmd") or "").split(), "source": "scan"} for r in found if r["pid"] not in skip]


def lingering(state_dir=None) -> list:
    reg = registered(state_dir)
    return reg + scanned(e["pid"] for e in reg)


def first_words(entry: dict, n: int = 4) -> str:
    cmd = [str(c) for c in (entry.get("cmd") or [])]
    if not cmd:
        return ""
    head = os.path.basename(cmd[0].strip('"')) or cmd[0]
    return " ".join([head] + cmd[1:n])


def describe(entry: dict) -> str:
    words = first_words(entry)
    return f"{C.label(entry.get('what') or 'halo')} (pid {entry['pid']})" + (f": {words}" if words else "")


def _bg_id(pid: int) -> Optional[str]:
    try:
        from halo_harness.bg_run import list_runs
        return next((m.get("id") for m in list_runs() if m.get("pid") == pid), None)
    except Exception:
        return None


def stop_command(entry: dict) -> str:
    what, pid = entry.get("what"), entry.get("pid")
    if what == "studio":
        return "halo studio --stop"
    if what == "supervisor":
        return "halo supervise stop"
    if what == "bg":
        run_id = entry.get("bg_id") or _bg_id(pid)
        return f"halo bg stop {run_id}" if run_id else "halo bg list, then halo bg stop <id>"
    if what in ("mlx", "llama") and entry.get("model"):
        return f"halo local stop {entry['model']}"
    if what == "halo":
        return f"/quit in that session (or end pid {pid})"
    return f"taskkill /PID {pid}" if sys.platform == "win32" else f"kill {pid}"


def refusal_lines(state_dir=None) -> list:
    """`--keep-running`: one line per process with the command that stops it; [] when none run."""
    return [f"  {describe(e)} -- stop it with: {stop_command(e)}" for e in lingering(state_dir)]


def _stop_line(entry: dict, timeout: float, state_dir) -> str:
    result = _stop(entry, state_dir=state_dir, timeout=timeout)
    words = first_words(entry)
    return CS.line(result) + (f" -- {words}" if words else "")


def stop_lingering(state_dir=None, *, timeout: float = 5.0) -> "tuple[list, bool]":
    """Stop the registry's processes, then what the scan still finds. One line each."""
    sup = _supervisor_entry(state_dir) is not None
    lines = [_stop_line(e, timeout, state_dir) for e in registered(state_dir)]
    lines += [_stop_line(e, timeout, state_dir) for e in scanned()]
    return lines, sup


def restart_supervisor() -> str:
    """`halo supervise --daemon` through the freshly installed `halo`; the line to print."""
    try:
        r = upd.run(["halo", "supervise", "--daemon"], capture_output=True, text=True, timeout=60)
        ok = getattr(r, "returncode", 1) == 0
    except Exception:
        ok = False
    if ok:
        return "halo update: the supervisor is running again on the new version"
    return "halo update: the supervisor did not start again -- run: halo supervise --daemon"
