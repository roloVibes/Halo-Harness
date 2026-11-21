"""halo_harness.children_stop -- stopping what children.py records (Halo
3.2.2.0 R3): the graceful path per kind first (Studio's shutdown route
through studio/launch.stop, a background run's `halo bg stop` tree kill, the
supervisor's stop file, `halo local stop` for a managed model server), then
terminate, then kill once `timeout` has passed. By pid only, never by name;
never this process.

    stop_all(owner=None, timeout=5.0) -> ["stopped: Studio (pid 4242)", ...]
    stop_for_quit()                    -> "stopped: Studio (pid 4242), 2 background runs" or ""

A quit (`stop_for_quit`) leaves the supervisor alone (started on purpose with
`halo supervise --daemon`), a `halo --bg` run started from a plain shell (no
owner), a Studio started on its own (`halo studio`: 3.4.1.1, defect 48), and
what another halo session still running in this home owns or uses: a Studio a
session started for itself and orphaned children end with the last session
that quits.
"""

from __future__ import annotations

import os
import signal
from halo_harness import subprocess_safe as subprocess
import time
from pathlib import Path
from typing import Optional

from halo_harness import children as C


def _reap(pid: int) -> None:
    try:
        os.waitpid(pid, os.WNOHANG)
    except (ChildProcessError, OSError):
        pass


def _wait_gone(pid: int, timeout: float, recorded: Optional[str] = None) -> bool:
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        if os.name != "nt":
            _reap(pid)
        if not C.same_process(pid, recorded):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


def terminate(pid, *, timeout: float = 5.0, recorded: Optional[str] = None) -> bool:
    """End `pid` (and, on Windows, its tree): terminate, wait up to `timeout`,
    then kill. True when it is gone. `recorded` (its start time) keeps a pid
    the OS gave to another program from being touched."""
    if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
        return False
    if not C.same_process(pid, recorded):
        return True
    if not C.provably_same(pid, recorded):  # 3.6.0.0 fx: an unknown start time on either side is no proof
        return False
    if os.name == "nt":
        try:
            soft = subprocess.run(["taskkill", "/PID", str(pid), "/T"], capture_output=True, text=True, timeout=10)
            if soft.returncode == 0 and _wait_gone(pid, min(timeout, 2.0), recorded):
                return True
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            from halo_harness.tools._proc import _kill_process_tree_windows
            _kill_process_tree_windows(pid)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)  # TerminateProcess
            except OSError:
                pass
        return _wait_gone(pid, 2.0, recorded)
    try:
        os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError):
        return not C.pid_running(pid)
    if _wait_gone(pid, timeout, recorded):
        return True
    try:
        os.kill(pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
    return _wait_gone(pid, 2.0, recorded)


def _stop_studio(entry: dict, state_dir: Path, timeout: float) -> bool:
    from halo_harness.studio import launch
    info = launch.read_info(state_dir)
    if info and info.get("pid") == entry["pid"]:
        launch.stop(state_dir)  # the shutdown route, then the signal
    if not entry.get("start_time"):  # nothing proves the pid is still that Studio: never signal it
        return not C.pid_running(entry["pid"])
    return terminate(entry["pid"], timeout=timeout, recorded=entry.get("start_time"))


def _stop_supervisor(entry: dict, state_dir: Path, timeout: float) -> bool:
    from halo_harness.supervise import pulse
    pulse.request_stop(state_dir)
    if _wait_gone(entry["pid"], timeout, entry.get("start_time")):
        return True
    return terminate(entry["pid"], timeout=timeout, recorded=entry.get("start_time"))


def stop_entry(entry: dict, *, state_dir=None, timeout: float = 5.0) -> dict:
    """Stop one entry by its kind's path; `{what, pid, ok}`. The entry leaves children.json."""
    state = C._state(state_dir)
    pid, what = entry.get("pid"), entry.get("what") or "halo"
    ok = False
    try:
        if not C.same_process(pid, entry.get("start_time")):
            ok = True
        elif what == "studio":
            ok = _stop_studio(entry, state, timeout)
        elif what == "bg":
            from halo_harness.bg_run import kill_pid
            ok = ((C.provably_same(pid, entry.get("start_time")) and kill_pid(pid))
                  or terminate(pid, timeout=timeout, recorded=entry.get("start_time")))
        elif what == "supervisor":
            ok = _stop_supervisor(entry, state, timeout)
        elif entry.get("source") == "local-servers" and entry.get("model"):
            if not C.provably_same(pid, entry.get("start_time")):  # jb10: its stop signals by pid: proof first
                return {"what": what, "pid": pid, "ok": False, "cmd": entry.get("cmd") or []}
            from halo_harness.providers.local_runtime import stop_managed_server
            stop_managed_server(entry["model"], state_dir=state)
            ok = _wait_gone(pid, timeout, entry.get("start_time"))
        else:
            ok = terminate(pid, timeout=timeout, recorded=entry.get("start_time"))
    except Exception:
        ok = not C.alive(entry)
    C.unregister(pid, state_dir=state)
    return {"what": what, "pid": pid, "ok": bool(ok), "cmd": entry.get("cmd") or []}


def line(result: dict) -> str:
    head = "stopped" if result["ok"] else "still running"
    return f"{head}: {C.label(result['what'])} (pid {result['pid']})"


def summary(results: list) -> str:
    """One line: "stopped: Studio (pid 4242), 2 background runs"; '' for none."""
    def group(rows: list) -> str:
        order: list = []
        by: dict = {}
        for r in rows:
            key = C.label(r["what"])
            if key not in by:
                order.append(key)
                by[key] = []
            by[key].append(r)
        parts = []
        for key in order:
            rs = by[key]
            parts.append(f"{key} (pid {rs[0]['pid']})" if len(rs) == 1 else f"{len(rs)} {C.label(rs[0]['what'], 2)}")
        return ", ".join(parts)
    done = [r for r in results if r["ok"]]
    left = [r for r in results if not r["ok"]]
    out = f"stopped: {group(done)}" if done else ""
    if left:
        out = (out + "; " if out else "") + f"still running: {group(left)}"
    return out


def studio_entry(state_dir=None) -> Optional[dict]:
    """The Studio `studio.json` names, as an entry ('' when none runs)."""
    from halo_harness.studio import launch
    info = launch.read_info(C._state(state_dir))
    pid = info.get("pid") if info else None
    if not isinstance(pid, int) or pid == os.getpid() or not C.pid_running(pid):
        return None
    if not launch.pid_is_studio(pid, info):  # a pid the OS gave to another program is never a target
        return None
    return {"pid": pid, "start_time": info.get("pstart") or C.start_time(pid), "what": "studio",
            "cmd": ["halo", "studio"], "owner_pid": None, "source": "studio.json"}


def _with_studio(entries: list, state_dir) -> list:
    st = studio_entry(state_dir)
    if st and all(e.get("pid") != st["pid"] for e in entries):
        entries = entries + [st]
    return entries


def stop_all(owner: Optional[int] = None, timeout: float = 5.0, *, state_dir=None,
             keep=("supervisor", "host", "update", "terminal", "steward")) -> list:
    """Stop every registered child of this home (`owner`: only that pid's),
    except the kinds in `keep`; with no owner the Studio in studio.json too.
    One line per process."""
    entries = [e for e in C.prune(state_dir) if e.get("what") not in keep]
    if owner is not None:
        entries = [e for e in entries if e.get("owner_pid") == owner]
    else:
        entries = _with_studio(entries, state_dir)
    entries = [e for e in entries if e.get("pid") != os.getpid()]
    return [line(stop_entry(e, state_dir=state_dir, timeout=timeout)) for e in entries]


def other_live_sessions() -> list:
    """Pids of the other halo TUI (and 3.3.11.0 R2: headless) sessions of this home that still run (run/sessions.json)."""
    try:
        from halo_harness.remote import registry
        rows = registry._load(registry.registry_path())
    except Exception:
        return []
    me = os.getpid()
    return [r["pid"] for r in rows if isinstance(r.get("pid"), int) and r["pid"] != me
            and (r.get("kind") or "tui") in ("tui", "headless") and C.pid_running(r["pid"])]


def closes_itself(entry: dict) -> bool:
    """3.6.0.6 W: this process's own browser (the Browser tool's) is left to its own Browser.close, which the closing
    procedure runs (closing.on_close) before its own stops: a quit's stop of leftovers runs earlier and is a hard end
    on Windows, and Halo's kept profile would lose what the browser had not written yet (a sign-in)."""
    return entry.get("what") == "browser" and entry.get("owner_pid") == os.getpid()


def quit_targets(state_dir=None) -> list:
    """What a quit stops: only what a session started -- this session's own
    children and, when no other halo session of this home runs, orphans (a
    session started them and is gone) -- minus the supervisor. 3.4.1.1 (48):
    a Studio counts like any child; one started on its own (`halo studio`,
    above all with `--fleet`: members joined its hub) is in studio.json only,
    owned by no session, and no session's quit ever stops it."""
    me = os.getpid()
    others = bool(other_live_sessions())
    out = []
    for e in C.prune(state_dir):
        if e.get("what") == "supervisor" or e.get("pid") == me:
            continue
        if e.get("keep") or e.get("what") in ("host", "update", "terminal", "steward"):
            continue  # 3.6.0.0 R10: asked to keep running; the closing procedure names it
        mine = e.get("owner_pid") == me
        if closes_itself(e):
            continue
        # No owner: started from a plain shell (`halo --bg`, a Studio a shell
        # command opened), on purpose -- a quit leaves it; `halo update`,
        # `halo bg stop` and `halo studio --stop` end it.
        if mine or (e.get("owner_pid") is not None and not others and not C.owner_alive(e)):
            out.append(e)
    return out


def _stop_together(targets: list, state_dir, timeout: float) -> list:
    """fx jb8: every target told to stop at the same moment, each on its own thread, all inside one bound (`timeout`,
    never past a leaving halo's deadline): a polite stop waited out on one never holds up the next. A stop still
    under way at the bound is reported by its entry as still running."""
    import threading
    from halo_harness.closing import time_left
    bound = time_left(timeout)
    results: list = [None] * len(targets)

    def one(i: int, entry: dict) -> None:
        results[i] = stop_entry(entry, state_dir=state_dir, timeout=bound)

    threads = [threading.Thread(target=one, args=(i, e), name="halo-quit-stop", daemon=True)
               for i, e in enumerate(targets)]
    for th in threads:
        th.start()
    end = time.monotonic() + bound + 1.0  # a stop's own wait is `bound`; its last look gets a moment more
    for th in threads:
        th.join(max(0.0, end - time.monotonic()))
    return [r if r is not None else {"what": e.get("what") or "halo", "pid": e.get("pid"), "ok": not C.alive(e),
                                     "cmd": e.get("cmd") or []} for r, e in zip(results, targets)]


def stop_for_quit(state_dir=None, timeout: float = 5.0) -> str:
    """The exit path's stop: one line -- what it stopped, then what it left
    running of this home (children_left.py) -- or '' when neither. Never raises."""
    try:
        stopped = summary(_stop_together(quit_targets(state_dir), state_dir, timeout))
    except Exception:
        stopped = ""
    from halo_harness.children_left import quit_line
    return quit_line(stopped, state_dir)
