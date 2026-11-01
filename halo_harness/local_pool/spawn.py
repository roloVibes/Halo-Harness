"""halo_harness.local_pool.spawn -- the pool's llama-server process (Halo 3.3.8.0 R3; local_pool/launch.py drives it).

    spawn(cmd, log, shown) -> pid    a Popen with stdout + stderr in `log` (its first line is "--- halo starts: <shown>",
                                     the argv with the api key as ***), the environment from tool_child_env
    wait_ready(pid, url, get, cap_s) -> (ready, "ok" | "exited" | "still loading after N s")   /health polled
    halt(pid) -> how it ended (terminate, then kill after a grace)
The process is the pool's own (not a `halo local serve` registry row): local_pool/launch.stop is its one way out, and
the process that warmed it stops it when it exits (an atexit hook, not for `--keep`).
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

_PROCS: dict = {}
POLL_S = 0.25


def spawn(cmd: list, log: Path, shown: list) -> int:
    from halo_harness.providers.config import tool_child_env
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as out:
        out.write(f"--- halo starts: {' '.join(shown)}\n".encode("utf-8"))
        out.flush()
        proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                env=tool_child_env(dict(os.environ)))
    _PROCS[proc.pid] = proc
    return proc.pid


def _exited(pid: int) -> bool:
    proc = _PROCS.get(pid)
    if proc is not None:
        return proc.poll() is not None
    from halo_harness.bg_run import pid_alive
    return not pid_alive(pid)


def wait_ready(pid: int, url: str, get, cap_s: float) -> "tuple[bool, str]":
    end = time.monotonic() + max(0.5, float(cap_s))
    while True:
        code, _body = get(f"{url}/health", timeout=1.0)
        if code == 200:
            return True, "ok"
        if _exited(pid):
            return False, "exited"
        if time.monotonic() >= end:
            return False, f"still loading after {cap_s:.0f} s"
        time.sleep(POLL_S)


def halt(pid: int) -> str:
    proc = _PROCS.pop(pid, None)
    if proc is not None:
        if proc.poll() is not None:
            return "it had exited"
        proc.terminate()
        try:
            proc.wait(timeout=10)
            return "terminated"
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            return "killed after 10 s"
    from halo_harness.providers.local_server_cmd import halt as halt_pid
    return halt_pid(int(pid))
