"""tests.helpers.hanging_git -- a stand-in `git` for what a hanging network looks like (3.6.0.17 Z1).

`make(folder)` writes a `git` (an executable script on POSIX, a `git.cmd` on Windows) into `folder`; put `folder` first
on PATH. For `ls-remote` it starts a helper that inherits its stdout and stderr (as git's own `git-remote-https`
does), appends both pids to `folder/git-pids.txt`, and both sleep HOLD_S. Any other git command fails at once and
prints nothing. `make(folder, hang=False)` (3.6.0.17 Z2): `ls-remote` fails at once too (a git that answers at once). `seen(folder)` reads the pids with each one's start time, `alive(rows)` names those still the same
process, and `end(rows)` ends them by pid (a test's `finally`): never a pid alone, its start time must still match."""
from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

HOLD_S = 120
PIDS = "git-pids.txt"

_SCRIPT = '''import os, subprocess, sys, time
here = os.path.dirname(os.path.abspath(__file__))
if sys.argv[1:2] == ["--hold"]:
    time.sleep(%(hold)d)
    sys.exit(0)
if "ls-remote" not in sys.argv[1:] or not %(hang)s:
    sys.exit(1)
helper = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--hold"],
                          stdin=subprocess.DEVNULL, stdout=1, stderr=2)
with open(os.path.join(here, "%(pids)s"), "a") as fh:
    fh.write("%%d %%d\\n" %% (os.getpid(), helper.pid))
time.sleep(%(hold)d)
'''


def make(folder: Path, hang: bool = True) -> Path:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "git_standin.py"
    script.write_text(_SCRIPT % {"hold": HOLD_S, "pids": PIDS, "hang": bool(hang)}, encoding="utf-8")
    if os.name == "nt":
        (folder / "git.cmd").write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        git = folder / "git"
        git.write_text(f"#!{sys.executable}\n" + script.read_text(encoding="utf-8"), encoding="utf-8")
        git.chmod(0o755)
    return folder


def _start(pid: int) -> Optional[str]:
    from halo_harness.bg_run import process_start_time, ps_forget
    try:
        ps_forget(pid)  # a fresh look each time: where there is no /proc one `ps` answers for a moment
        return process_start_time(pid)
    except Exception:
        return None


def seen(folder: Path) -> list:
    """[(pid, start time)] of every stand-in process an `ls-remote` started (git's own and its helper), in order."""
    rows: list = []
    try:
        text = (Path(folder) / PIDS).read_text(encoding="utf-8")
    except OSError:
        return rows
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            rows += [(int(p), _start(int(p))) for p in parts]
    return rows


def wait_seen(folder: Path, seconds: float) -> list:
    end = time.monotonic() + seconds
    while True:
        rows = seen(folder)
        if rows or time.monotonic() >= end:
            return rows
        time.sleep(0.05)


def alive(rows: list) -> list:
    """The pids of `rows` still running as the same process (same start time)."""
    return [pid for pid, start in rows if start and _start(pid) == start]


def wait_gone(rows: list, seconds: float) -> list:
    end = time.monotonic() + seconds
    while True:
        left = alive(rows)
        if not left or time.monotonic() >= end:
            return left
        time.sleep(0.1)


def end(rows: list) -> None:
    for pid in alive(rows):
        try:
            os.kill(pid, signal.SIGTERM if os.name == "nt" else signal.SIGKILL)
        except OSError:
            pass
