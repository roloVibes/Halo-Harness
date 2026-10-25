"""halo_harness.update_detached -- the TUI's `/update` installs after halo
has exited (Halo 3.2.2.0 R3). On Windows the running `halo.exe` holds the
tool venv ("Scripts: Access is denied"), so the install never runs inside
the halo process: `/update` writes a small updater script and starts it
detached, and halo exits.

    windows_script(...) / posix_script(...)  the script text (pure; tested as text)
    spawn(path)                              starts it: `cmd.exe /c <path>` or `sh <path>`
    run_after_exit()                         `cli.py`'s `/update` hand-off

The script waits for this pid (and the `halo.exe` launcher above it) to
end, stops the processes named at write time (`taskkill /PID <pid> /T /F` /
`kill <pid>`, the supervisor's stop file first), runs the reinstall
command, starts the supervisor again when it ran, then `halo --version`,
all appended to `~/.halo/update.log`. Never the tool venv's python: it is
the thing being replaced.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

LOG_NAME = "update.log"
WAIT_LIMIT_S = 300


def _state(state_dir=None) -> Path:
    if state_dir is not None:
        return Path(state_dir)
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def log_path(state_dir=None) -> Path:
    return _state(state_dir) / LOG_NAME


def _bat(text: str) -> str:
    return str(text).replace("%", "%%")


def windows_script(*, wait_pids, stop_pids, reinstall_cmd: str, log, cwd: Optional[str] = None,
                   supervisor_stop_file: Optional[str] = None, restart_supervisor: bool = False,
                   halo: str = "halo") -> str:
    """The `update.cmd` text: wait, stop, reinstall, restart, `halo --version`, all into `log`."""
    out = ["@echo off", "rem Halo /update: runs after halo exits (written by halo_harness.update_detached).",
           f'set "LOG={_bat(log)}"', 'echo === halo update from /update %DATE% %TIME% >> "%LOG%" 2>&1']
    for pid in wait_pids:
        out += [f"set N=0", f":wait_{pid}",
                f'tasklist /FI "PID eq {pid}" /FO CSV /NH 2>nul | findstr /C:"\\"{pid}\\"" >nul',
                f"if errorlevel 1 goto gone_{pid}", "set /a N+=1", f"if %N% GEQ {WAIT_LIMIT_S} goto gone_{pid}",
                "ping -n 2 127.0.0.1 >nul", f"goto wait_{pid}", f":gone_{pid}",
                f'echo halo (pid {pid}) has exited >> "%LOG%"']
    if supervisor_stop_file:
        out += [f'echo stop> "{_bat(supervisor_stop_file)}"', "ping -n 6 127.0.0.1 >nul"]
    for pid in stop_pids:
        out += [f'echo stopping pid {pid} >> "%LOG%"', f'taskkill /PID {pid} /T /F >> "%LOG%" 2>&1']
    out += ['echo running the reinstall >> "%LOG%"', 'call :reinstall >> "%LOG%" 2>&1',
            'echo reinstall exit code %ERRORLEVEL% >> "%LOG%"']
    if restart_supervisor:
        out += [f'"{_bat(halo)}" supervise --daemon >> "%LOG%" 2>&1']
    out += [f'"{_bat(halo)}" --version >> "%LOG%" 2>&1', 'echo === done >> "%LOG%"', "goto :eof", "", ":reinstall"]
    if cwd:
        out.append(f'cd /d "{_bat(cwd)}"')
    out += [_bat(reinstall_cmd), "exit /b %ERRORLEVEL%", ""]
    return "\r\n".join(out)


def posix_script(*, wait_pids, stop_pids, reinstall_cmd: str, log, cwd: Optional[str] = None,
                 supervisor_stop_file: Optional[str] = None, restart_supervisor: bool = False,
                 halo: str = "halo") -> str:
    """The `update.sh` text, the same steps as `windows_script`."""
    q = shlex.quote
    out = ["#!/bin/sh", "# Halo /update: runs after halo exits (written by halo_harness.update_detached).",
           f"exec >>{q(str(log))} 2>&1", 'echo "=== halo update from /update $(date)"']
    for pid in wait_pids:
        out += ["n=0", f"while kill -0 {pid} 2>/dev/null && [ $n -lt {WAIT_LIMIT_S} ]; do sleep 1; n=$((n+1)); done",
                f'echo "halo (pid {pid}) has exited"']
    if supervisor_stop_file:
        out += [f"echo stop > {q(supervisor_stop_file)}", "sleep 5"]
    if stop_pids:
        pids = " ".join(str(p) for p in stop_pids)
        out += [f'echo "stopping pid(s) {pids}"', f"kill {pids} 2>/dev/null", "sleep 2", f"kill -9 {pids} 2>/dev/null"]
    out += ['echo "running the reinstall"', f"( {'cd ' + q(cwd) + ' && ' if cwd else ''}{reinstall_cmd} )",
            'echo "reinstall exit code $?"']
    if restart_supervisor:
        out.append(f"{q(halo)} supervise --daemon")
    out += [f"{q(halo)} --version", 'echo "=== done"', ""]
    return "\n".join(out)


def script_path(state_dir=None, *, windows: Optional[bool] = None) -> Path:
    windows = os.name == "nt" if windows is None else windows
    return _state(state_dir) / "run" / ("update.cmd" if windows else "update.sh")


def write_script(text: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return path


def spawn(path, *, windows: Optional[bool] = None, cwd=None, popen=subprocess.Popen) -> Optional[int]:
    """Start the script detached from this process and its console; its pid, or None."""
    windows = os.name == "nt" if windows is None else windows
    common = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
              "cwd": str(cwd or Path(path).parent), "close_fds": True}
    if windows:
        argv = [os.environ.get("COMSPEC") or "cmd.exe", "/c", str(path)]
        base = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for flags in (base | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0), base):
            try:
                return popen(argv, creationflags=flags, **common).pid
            except OSError:
                continue
        return None
    try:
        return popen([shutil.which("sh") or "/bin/sh", str(path)], start_new_session=True, **common).pid
    except OSError:
        return None


def reinstall_cmd(to: Optional[str] = None) -> "tuple[Optional[str], dict]":
    """The command `halo update` would run (the channel's newest, `--to` aside), and the install kind."""
    from halo_harness import update as upd
    from halo_harness.update_checkout import pick_target
    from halo_harness.update_cli import _retarget_cmd
    build = upd.installed_build()
    channel = upd.default_channel(build)
    avail = upd.latest_available(channel)  # the /update dialog has just refreshed it
    kind = upd.install_kind(target=pick_target(channel, avail, to), channel=channel)
    cmd = kind.get("reinstall_cmd")
    stable_tag = avail.get("ref") if channel == "stable" and upd._TAG_RE.match(avail.get("ref") or "") else None
    new_ref = to or stable_tag
    if new_ref and cmd and kind.get("spec"):
        cmd = _retarget_cmd(cmd, kind["spec"], new_ref)
    return cmd, kind


def run_after_exit(*, state_dir=None, windows: Optional[bool] = None, resume_hint: str = "") -> int:
    """`/update`'s hand-off once the TUI is gone: write the updater, start it, say where its log is."""
    from halo_harness import update as upd
    from halo_harness.providers.http import format_offline_refusal, offline_mode_enabled
    from halo_harness.update_stop import describe, lingering
    if offline_mode_enabled():
        print(f"halo update: {format_offline_refusal('the update server')}", file=sys.stderr)
        return 1
    cmd, kind = reinstall_cmd()
    if not cmd:
        print("halo update: could not determine how halo was installed -- nothing to run", file=sys.stderr)
        return 1
    windows = os.name == "nt" if windows is None else windows
    rows = lingering(state_dir)
    supervisor = any(r.get("what") == "supervisor" for r in rows)
    from halo_harness.supervise.pulse import stop_path
    spec = kind.get("spec")
    log = log_path(state_dir)
    make = windows_script if windows else posix_script
    text = make(wait_pids=[os.getpid(), *upd.halo_ancestors()], stop_pids=[r["pid"] for r in rows],
                reinstall_cmd=cmd, log=str(log), cwd=spec if spec and Path(spec).is_dir() else None,
                supervisor_stop_file=str(stop_path(_state(state_dir))) if supervisor else None,
                restart_supervisor=supervisor, halo=shutil.which("halo") or "halo")
    path = write_script(text, script_path(state_dir, windows=windows))
    if spawn(path, windows=windows, cwd=_state(state_dir)) is None:
        print(f"halo update: could not start the updater ({path}); run `halo update` from a shell", file=sys.stderr)
        return 1
    for r in rows:
        print(f"halo update: the updater stops {describe(r)}")
    print(f"halo update: the update runs after halo exits; its log: {log}; `halo --version` then"
          + (f"; `{resume_hint}` picks the session up again" if resume_hint else ""))
    return 0
