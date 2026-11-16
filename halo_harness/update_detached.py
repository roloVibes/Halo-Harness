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
from halo_harness import subprocess_safe as subprocess
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
                   halo: str = "halo", restore_cmd: Optional[str] = None, restore_cwd: Optional[str] = None,
                   stop_starts=None) -> str:
    """The `update.cmd` text: wait, stop, reinstall, `halo --version` (3.6.0.0 R13: when the reinstall or that
    fails, `restore_cmd` puts back what was installed), restart, all into `log`. jb10: a stop pid is ended only when
    `stop_starts` records its start time and the live one (read just before) equals it."""
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
        start = str((stop_starts or {}).get(pid) or "")
        if not start.isdigit():  # Halo's Windows start time is the creation FILETIME, digits only
            out += [f'echo pid {pid} was not stopped: its start time was not recorded >> "%LOG%"']
            continue
        out += [f'powershell -NoProfile -NonInteractive -Command "$p = Get-Process -Id {pid} -ErrorAction Stop; '
                f'if ($p.StartTime.ToFileTimeUtc() -eq {start}) {{ exit 0 }} else {{ exit 1 }}" >nul 2>&1',
                f"if errorlevel 1 goto keep_{pid}",
                f'echo stopping pid {pid} >> "%LOG%"', f'taskkill /PID {pid} /T /F >> "%LOG%" 2>&1',
                f"goto stopped_{pid}", f":keep_{pid}",
                f'echo pid {pid} was not stopped: it is gone or another program now >> "%LOG%"', f":stopped_{pid}"]
    out += ['echo running the reinstall >> "%LOG%"', 'call :reinstall >> "%LOG%" 2>&1', "set RC=%ERRORLEVEL%",
            'echo reinstall exit code %RC% >> "%LOG%"', f'"{_bat(halo)}" --version >> "%LOG%" 2>&1',
            "if errorlevel 1 set RC=1"]
    if restore_cmd:
        out += ['if "%RC%"=="0" goto verified',
                'echo halo update: the update failed; putting back what was installed >> "%LOG%"',
                'call :restore >> "%LOG%" 2>&1', f'"{_bat(halo)}" --version >> "%LOG%" 2>&1',
                f'if errorlevel 1 echo halo update: halo does not answer; run by hand: {_bat(restore_cmd)} >> "%LOG%"',
                ":verified"]
    if restart_supervisor:
        out += [f'"{_bat(halo)}" supervise --daemon >> "%LOG%" 2>&1']
    out += ['echo === done >> "%LOG%"', "goto :eof", "", ":reinstall"]
    if cwd:
        out.append(f'cd /d "{_bat(cwd)}"')
    out += [_bat(reinstall_cmd), "exit /b %ERRORLEVEL%", ""]
    if restore_cmd:
        out += [":restore"] + ([f'cd /d "{_bat(restore_cwd)}"'] if restore_cwd else [])
        out += [_bat(restore_cmd), "exit /b %ERRORLEVEL%", ""]
    return "\r\n".join(out)


def posix_script(*, wait_pids, stop_pids, reinstall_cmd: str, log, cwd: Optional[str] = None,
                 supervisor_stop_file: Optional[str] = None, restart_supervisor: bool = False,
                 halo: str = "halo", restore_cmd: Optional[str] = None, restore_cwd: Optional[str] = None,
                 stop_starts=None) -> str:
    """The `update.sh` text, the same steps as `windows_script`."""
    q = shlex.quote
    out = ["#!/bin/sh", "# Halo /update: runs after halo exits (written by halo_harness.update_detached).",
           f"exec >>{q(str(log))} 2>&1", 'echo "=== halo update from /update $(date)"']
    for pid in wait_pids:
        out += ["n=0", f"while kill -0 {pid} 2>/dev/null && [ $n -lt {WAIT_LIMIT_S} ]; do sleep 1; n=$((n+1)); done",
                f'echo "halo (pid {pid}) has exited"']
    if supervisor_stop_file:
        out += [f"echo stop > {q(supervisor_stop_file)}", "sleep 5"]
    guards = []
    for pid in stop_pids:
        start = str((stop_starts or {}).get(pid) or "")
        if not start:
            out.append(f'echo "pid {pid} was not stopped: its start time was not recorded"')
        elif start.startswith("ps:"):  # where there is no /proc: `lstart` in UTC, the C locale, one space apart
            guards.append((pid, f'[ "$(LC_ALL=C LANG=C TZ=UTC0 ps -o lstart= -p {pid} 2>/dev/null | tr -s \' \' '
                                f'| sed \'s/^ //;s/ $//\')" = {q(start[3:])} ]'))
        else:  # /proc/<pid>/stat field 22, after the command name in parentheses
            guards.append((pid, f'[ "$(sed \'s/.*) //\' /proc/{pid}/stat 2>/dev/null | cut -d\' \' -f20)" = {q(start)} ]'))
    for pid, same in guards:  # jb10: ended only while the live start time is the recorded one
        out.append(f'if {same}; then echo "stopping pid {pid}"; kill {pid} 2>/dev/null; '
                   f'else echo "pid {pid} was not stopped: it is gone or another program now"; fi')
    if guards:
        out.append("sleep 2")
        out += [f"if {same}; then kill -9 {pid} 2>/dev/null; fi" for pid, same in guards]
    out += ['echo "running the reinstall"', f"( {'cd ' + q(cwd) + ' && ' if cwd else ''}{reinstall_cmd} )",
            "rc=$?", 'echo "reinstall exit code $rc"', f"{q(halo)} --version || rc=1"]
    if restore_cmd:
        out += ['if [ "$rc" -ne 0 ]; then', '  echo "halo update: the update failed; putting back what was installed"',
                f"  ( {'cd ' + q(restore_cwd) + ' && ' if restore_cwd else ''}{restore_cmd} )",
                f"  {q(halo)} --version || echo {q('halo update: halo does not answer; run by hand: ' + restore_cmd)}",
                "fi"]
    if restart_supervisor:
        out.append(f"{q(halo)} supervise --daemon")
    out += ['echo "=== done"', ""]
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
    if popen is subprocess.Popen:  # 3.6.0.0 R10: the updater outlives the halo it replaces on purpose (closing.py)
        from halo_harness.closing import kept_kwargs
        common["env"] = kept_kwargs()["env"]
    if windows:
        argv = [os.environ.get("COMSPEC") or "cmd.exe", "/c", str(path)]
        base = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        for flags in (base | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0), base):
            try:
                proc = popen(argv, creationflags=flags, **common)
                from halo_harness.closing import register_kept
                register_kept(proc, "update", argv)
                return proc.pid
            except OSError:
                continue
        return None
    try:
        proc = popen([shutil.which("sh") or "/bin/sh", str(path)], start_new_session=True, **common)
        from halo_harness.closing import register_kept
        register_kept(proc, "update", ["sh", str(path)])
        return proc.pid
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
    from pathlib import Path
    from halo_harness.update_cli import ahead_of_offer, older_release
    from halo_harness.update_plan import expectation
    checkout = Path(build["checkout"]) if build.get("checkout") else None
    kind = {**kind, "current_cmd": kind.get("reinstall_cmd"), "expect": expectation(new_ref, channel, avail, build),
            "older": None if to else (older_release(build, avail, channel)
                                      or ahead_of_offer(build, avail, channel, checkout))}
    if new_ref and cmd and kind.get("spec"):
        cmd = _retarget_cmd(cmd, kind["spec"], new_ref)
    return cmd, kind


launch = None  # 3.6.0.0 R13: the seam a test replaces -- launch(plan, **kw) -> exit code or None (update_plan.launch)


def run_after_exit(*, state_dir=None, windows: Optional[bool] = None, resume_hint: str = "") -> int:
    """`/update`'s hand-off once the TUI is gone. 3.6.0.0 R13: the standalone updater (update_runner.py, through
    update_plan.launch) with the same plan `halo update` writes -- it waits for this halo, stops what the plan names,
    installs, checks `halo --version` and puts back what was installed when that fails. Without a Python outside
    halo's environment, the shell script below does the same steps (`restore_cmd` on a failed check)."""
    from halo_harness import update as upd
    from halo_harness import update_plan as UP
    from halo_harness.providers.http import format_offline_refusal, offline_mode_enabled
    from halo_harness.update_stop import describe, lingering, unproven_line
    if offline_mode_enabled():
        print(f"halo update: {format_offline_refusal('the update server')}", file=sys.stderr)
        return 1
    cmd, kind = reinstall_cmd()
    if not cmd:
        print("halo update: could not determine how halo was installed -- nothing to run", file=sys.stderr)
        return 1
    if kind.get("older"):
        print(f"halo update: not moving back -- {kind['older']}", file=sys.stderr)
        return 1
    windows = os.name == "nt" if windows is None else windows
    if launch is None:  # 3.6.0.0 R13 (judge): why the updater cannot start, before anything is listed to stop
        why = UP.launch_refusal(need_python=False)  # no outside Python: the shell script below does it
        if why:
            print(why, file=sys.stderr)
            return 1
    openers = upd.halo_openers()  # a Studio that opened this halo: stopped by the updater, never waited on
    from halo_harness.children import start_time
    for o in openers:  # seen in the process table just now; 3.6.0.1: then one more look (upd.confirm_rows)
        o["start_time"] = start_time(o["pid"])
    openers = upd.confirm_rows(openers, upd.halo_openers)
    rows = lingering(state_dir)
    rows += [{"pid": o["pid"], "what": o["what"], "cmd": str(o.get("cmd") or "").split(),
              "start_time": o["start_time"], "source": "opener"} for o in openers
             if all(r["pid"] != o["pid"] for r in rows)]
    # jb10: a row with no recorded start time is never ended by number (its pid may be another program's now)
    unrecorded = [r for r in rows if not r.get("start_time")]
    rows = [r for r in rows if r.get("start_time")]
    for r in unrecorded:
        print(f"halo update: not stopped by the updater: {unproven_line(r)}",
              file=sys.stderr if windows else sys.stdout)
    if unrecorded and windows:  # files are never replaced under a Halo that may still run
        print("halo update: not installing while it may still run; once that is dealt with as above, run /update "
              "again", file=sys.stderr)
        return 1
    starts = {r["pid"]: r["start_time"] for r in rows}
    supervisor = any(r.get("what") == "supervisor" for r in rows)
    from halo_harness.supervise.pulse import stop_path
    spec = kind.get("spec")
    cwd = spec if spec and Path(spec).is_dir() else None
    log = log_path(state_dir)
    from halo_harness import update_install as UI
    cmd, note = UI.pin_locally(cmd)
    if note:
        print(note, file=sys.stderr if cmd is None else sys.stdout)
    if cmd is None:
        return 1
    before = upd.installed_build()
    lock = UP.freeze_lock(UP.run_dir(state_dir) / UP.LOCK_NAME)
    restore = UP.previous_install(kind, before, kind.get("current_cmd"), str(lock) if lock else None,
                                  direct_url=upd._direct_url())
    stop_file = str(stop_path(_state(state_dir))) if supervisor else None
    ancestors = upd.halo_ancestors()
    py = UP.outside_python()
    tail = (f"; `{resume_hint}` picks the session up again" if resume_hint else "")
    if py:
        plan = UP.build_plan(cmd=cmd, cwd=cwd, before=before, expect=kind.get("expect") or {"label": "the newest"},
                             restore=restore, state_dir=state_dir,
                             wait_pids=[os.getpid(), *ancestors] if windows else [],  # POSIX: exec, no wait
                             stop_pids=[r["pid"] for r in rows], supervisor_stop_file=stop_file,
                             restart_supervisor=supervisor, windows=windows, stop_starts=starts)
        for r in rows:
            print(f"halo update: the updater stops {describe(r)}")
        print(("halo update: the update runs in its own window after halo exits" if windows else
               "halo update: the update runs here now") + f"; its log: {log}; `halo --version` then" + tail)
        got = (launch or UP.launch)(plan, state_dir=state_dir, windows=windows, python=py, quiet=True)
        return 1 if got is None else got
    make = windows_script if windows else posix_script
    text = make(wait_pids=[os.getpid(), *ancestors], stop_pids=[r["pid"] for r in rows], stop_starts=starts,
                reinstall_cmd=cmd, log=str(log), cwd=cwd, supervisor_stop_file=stop_file,
                restart_supervisor=supervisor, halo=shutil.which("halo") or "halo",
                restore_cmd=(restore or {}).get("cmd"), restore_cwd=(restore or {}).get("cwd"))
    path = write_script(text, script_path(state_dir, windows=windows))
    if spawn(path, windows=windows, cwd=_state(state_dir)) is None:
        print(f"halo update: could not start the updater ({path}); run `halo update` from a shell", file=sys.stderr)
        return 1
    for r in rows:
        print(f"halo update: the updater stops {describe(r)}")
    print(f"halo update: the update runs after halo exits; its log: {log}; `halo --version` then" + tail)
    return 0
