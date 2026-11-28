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

def _stop_entry(entry: dict, *, state_dir=None, timeout: float = 5.0) -> dict:
    """CS.stop_entry, but the LAN host is first asked through its own stop file: a clean exit, which its service unit
    (Restart=on-failure, KeepAlive SuccessfulExit=false, RestartOnFailure) does not start again mid-install. A host
    of another home, or one that does not answer, is then ended as before."""
    if entry.get("what") == "host" and C.same_process(entry.get("pid"), entry.get("start_time")):
        try:
            from halo_harness.host import state as HS
            HS.request_stop(C._state(state_dir))
            CS._wait_gone(entry["pid"], timeout, entry.get("start_time"))
        except Exception:
            pass
    return CS.stop_entry(entry, state_dir=state_dir, timeout=timeout)


_stop = _stop_entry  # the seam a test replaces


def _supervisor_entry(state_dir=None) -> Optional[dict]:
    try:
        from halo_harness.supervise import pulse
        row = pulse.read(C._state(state_dir))
    except Exception:
        return None
    pid = row.get("pid")
    if not row.get("running") or not isinstance(pid, int) or pid == os.getpid():
        return None
    # 3.6.0.1: the start time is the one that proves the pid is still the process that wrote the pulse (`pstart`),
    # read once; a pid that vanished or now runs another program is dropped, never given that program's start time
    try:
        from halo_harness.bg_run import start_matches
        from halo_harness.remote.proc_ident import start_token
        want = (pulse.read_row(C._state(state_dir)) or {}).get("pstart")
        have = start_token(pid)
    except Exception:
        return None
    if have is None:
        if not C.pid_running(pid):
            return None
        start = None  # runs, unreadable: named (`halo supervise stop`), never ended by number
    elif want and start_matches(pid, want, have):
        start = have.split(":")[-1] if have.startswith(("win:", "linux:")) else have  # process_start_time's text
    elif want:
        return None
    else:
        start = None  # a pulse with no pstart cannot prove the pid is still the supervisor
    return {"pid": pid, "start_time": start, "what": "supervisor", "cmd": ["halo", "supervise"], "source": "pulse"}


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
    # 3.6.0.1: the start times are read BETWEEN the two looks, so the second one confirms them (two lists, as before):
    # a pid it no longer shows as Halo's vanished or was reused: dropped. A second look that reads nothing never
    # fails open: a pid that still runs is kept with no start time (named, never ended by number)
    starts = {p: C.start_time(p) for p in pids}
    rows = {r["pid"]: r for r in upd.other_halo_processes()}
    if rows:
        found = [dict(rows[p], start_time=starts[p]) for p in pids if p in rows]
    else:
        found = [{"pid": p, "ppid": None, "what": "halo", "cmd": "", "start_time": None} for p in pids
                 if C.pid_running(p)]
    skip = set(known)
    changed = True
    while changed:
        changed = False
        for r in found:
            if r["pid"] not in skip and r.get("ppid") in skip:
                skip.add(r["pid"])
                changed = True
    return [{"pid": r["pid"], "ppid": r.get("ppid"), "start_time": r["start_time"], "what": r.get("what") or "halo",
             "cmd": str(r.get("cmd") or "").split(), "source": "scan"} for r in found if r["pid"] not in skip]


# 3.6.0.25 G (the coordinator's ruling): the update ends Claude Code's guest bridge as it ends Halo's other processes
# (it is Halo's own program and holds the install on Windows), and says so first, once per bridge
BRIDGE_LINE = ("a Claude Code session is shown in Studio through Halo's bridge (pid {pid}); the update {ends} the "
               "bridge; the Claude Code session itself keeps running; its view in Studio comes back when that session "
               "reconnects its tool servers or at its next start")


def bridges(rows) -> list:
    """The guest bridges among `rows` (`what` "guest", update.halo_what: by the command line), one row each: a row
    under another bridge row is that bridge's own interpreter (Windows' venv launcher starts it as its child)."""
    found = [r for r in rows if r.get("what") == "guest"]
    pids = {r.get("pid") for r in found}
    return [r for r in found if r.get("ppid") not in pids]


def bridge_lines(rows=None, *, would: bool = False) -> list:
    """One line per bridge in `rows` (the scan when None); `would`: the dry forms' words, nothing is ended."""
    rows = scanned() if rows is None else rows
    return [BRIDGE_LINE.format(pid=r.get("pid"), ends="would end" if would else "ends") for r in bridges(rows)]


def lingering(state_dir=None, *, skip=()) -> list:
    """3.6.0.0 R13: `skip` -- pids not to list here (a Studio that opened this very halo: stopping it from inside
    its own tree would end this halo too; the updater stops it once this halo has exited)."""
    reg = [e for e in registered(state_dir) if e.get("pid") not in set(skip)]
    return reg + [e for e in scanned(e["pid"] for e in reg) if e.get("pid") not in set(skip)]


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
    if what == "host":
        return "halo host stop"
    if what == "bg":
        run_id = entry.get("bg_id") or _bg_id(pid)
        return f"halo bg stop {run_id}" if run_id else "halo bg list, then halo bg stop <id>"
    if what in ("mlx", "llama") and entry.get("model"):
        return f"halo local stop {entry['model']}"
    if what == "halo":
        return f"/quit in that session (or end pid {pid})"
    return f"taskkill /PID {pid}" if sys.platform == "win32" else f"kill {pid}"


def unproven_line(entry: dict) -> str:
    """3.6.0.1: what to do about a process Halo cannot prove is its own (no start time recorded): never a signal by
    pid number. A ledger row (children.json, the model servers' registry) can be forgotten by `halo ps --forget`; a
    Halo command that stops its kind is named; a bare `taskkill` / `kill` is not."""
    pid = entry.get("pid")
    cmd = stop_command(entry)
    own = None if cmd.startswith(("taskkill ", "kill ")) else cmd.split(" (or end pid")[0]
    text = f"{describe(entry)} may still run and cannot be proven to be Halo's own (its start time was not recorded)"
    if entry.get("source") in (None, "local-servers"):
        text += (f"; if it is not Halo's (Task Manager or ps shows another program), `halo ps --forget {pid}` removes "
                 f"its record")
        return text + (f"; if it is Halo's, stop it with: {own}" if own else "")
    return text + (f"; if it is Halo's, stop it with: {own}" if own else "; if it is Halo's, end it where it runs")


def refusal_lines(state_dir=None) -> list:
    """`--keep-running`: one line per process with the command that stops it; [] when none run. 3.6.0.1 (jf-update):
    a row with no recorded start time gets `unproven_line` (as /update does), never a `taskkill` / `kill` by number."""
    rows = lingering(state_dir)
    said = {r["pid"]: f"  {line}" for r, line in zip(bridges(rows), bridge_lines(rows, would=True))}
    out = []
    for e in rows:
        out += [said[e["pid"]]] if e["pid"] in said else []
        out.append(f"  {describe(e)} -- stop it with: {stop_command(e)}" if e.get("start_time")
                   else f"  {unproven_line(e)}")
    return out


def _stop_line(entry: dict, timeout: float, state_dir) -> str:
    result = _stop(entry, state_dir=state_dir, timeout=timeout)
    words = first_words(entry)
    return CS.line(result) + (f" -- {words}" if words else "")


def stop_lingering(state_dir=None, *, timeout: float = 5.0, skip=(), say=None) -> "tuple[list, bool]":
    """Stop the registry's processes, then what the scan still finds. One line each. `skip`: pids left for the
    updater (see `lingering`). `say(line)`: each line as it is made, so a bridge's line comes before it is ended."""
    skip = set(skip)
    sup = _supervisor_entry(state_dir) is not None
    lines: list = []

    def add(line: str) -> None:
        lines.append(line)
        if say:
            say(line)
    for e in registered(state_dir):
        if e.get("pid") not in skip:
            add(_stop_line(e, timeout, state_dir))
    found = [e for e in scanned() if e.get("pid") not in skip]
    said = {r["pid"]: line for r, line in zip(bridges(found), bridge_lines(found))}
    for e in found:
        if e["pid"] in said:
            add(said[e["pid"]])
        add(_stop_line(e, timeout, state_dir))
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
