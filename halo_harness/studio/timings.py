"""halo_harness.studio.timings -- what Studio's first minute costs, from the user's own terminal (Halo 3.6.0.0 R14).

"It's still spinning" had no answer but a profiler on the user's machine. Every Studio server keeps a small record:

* the phases of its start (`phase`): the command's start (with the CPU the imports took), the server bound, the
  address printed -- each with the wall time since the command started and the process's CPU time (all threads);
* its first FIRST_REQUESTS requests (`request`): method, path, wall time and the CPU of the thread that answered;
* the process's CPU at 5, 10, 30 and 60 seconds (`watch`).

`halo studio --timings` (or HALO_STUDIO_TIMINGS=1) prints each as one `timings:` line on stdout as it happens;
HALO_STUDIO_TIMINGS=<file> appends the lines to that file instead (`halo init --timings` sets it for the Studio it
starts and prints the file's lines while it waits for Setup's Done). `GET /api/studio/timings` answers the record
at any time, flag or not: `{up_s, cpu_s, threads, phases, requests}` (`cpu_s` is the process's own user + system
time, the number tests/test_studio_first_minute.py holds to its budget).

Nothing here reads a file or opens a connection; a request costs two clock reads.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Callable, Optional

ENV = "HALO_STUDIO_TIMINGS"
FIRST_REQUESTS = 40
WATCH_AT = (5, 10, 30, 60)
_T0 = time.perf_counter()  # this module is imported as the studio command starts: the wall clock's zero


def _sink(flag: bool) -> "Optional[Callable[[str], None]]":
    """Where the lines go: a file named by HALO_STUDIO_TIMINGS, stdout with the flag or HALO_STUDIO_TIMINGS=1, else
    nowhere (the record is still kept for GET studio/timings)."""
    where = (os.environ.get(ENV) or "").strip()
    if where and where not in ("1", "true", "yes", "on"):
        def to_file(line: str) -> None:
            try:
                with open(where, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass
        return to_file
    if flag or where:
        def to_stdout(line: str) -> None:
            try:
                print(line, flush=True)
            except Exception:
                pass
        return to_stdout
    return None


class Timings:
    def __init__(self, flag: bool = False) -> None:
        self.out = _sink(flag)
        self.lock = threading.Lock()
        self.phases: list = []
        self.requests: list = []
        self._seen = 0

    @staticmethod
    def now() -> "tuple[float, float]":
        return time.perf_counter() - _T0, time.process_time()

    def _say(self, line: str) -> None:
        if self.out is not None:
            self.out("timings: " + line)

    def phase(self, name: str) -> None:
        wall, cpu = self.now()
        with self.lock:
            self.phases.append({"phase": name, "wall_s": round(wall, 3), "cpu_s": round(cpu, 3)})
        self._say(f"{name:<24} at {wall:7.3f} s wall, {cpu:7.3f} s cpu (the process, all threads)")

    def request(self, method: str, path: str, wall: float, cpu: float, status=None) -> None:
        with self.lock:
            self._seen += 1
            if self._seen > FIRST_REQUESTS:
                return
            at = round(time.perf_counter() - _T0, 3)
            self.requests.append({"method": method, "path": path, "at_s": at, "wall_s": round(wall, 3),
                                  "cpu_s": round(cpu, 3), "status": status})
        self._say(f"{method} {path} ({status}) {wall:7.3f} s wall, {cpu:7.3f} s cpu (its thread), done at {at:.2f} s")

    def snapshot(self) -> dict:
        wall, cpu = self.now()
        with self.lock:
            return {"up_s": round(wall, 3), "cpu_s": round(cpu, 3), "threads": threading.active_count(),
                    "phases": list(self.phases), "requests": list(self.requests)}

    def watch(self, alive: "Callable[[], bool]") -> None:
        """The process's CPU at WATCH_AT seconds (a daemon thread that ends after the last one or with the server)."""
        if self.out is None:
            return

        def run() -> None:
            last = 0.0
            for at in WATCH_AT:
                wait = at - (time.perf_counter() - _T0)
                if wait > 0:
                    time.sleep(wait)
                if not alive():
                    return
                _wall, cpu = self.now()
                self._say(f"up {at:>3} s: {cpu:7.3f} s cpu in all, {cpu - last:6.3f} s since the last line, "
                          f"{threading.active_count()} threads")
                last = cpu
        threading.Thread(target=run, name="halo-studio-timings", daemon=True).start()


def of(server) -> "Optional[Timings]":
    return getattr(server, "timings", None)


def timed(handler, method: str, fn) -> None:
    """Run one request's handler (`fn()`) and record it on the server's Timings."""
    t = of(handler.server)
    if t is None:
        return fn()
    w0, c0 = time.perf_counter(), time.thread_time()
    try:
        return fn()
    finally:
        try:
            path = handler.path.split("?", 1)[0].split("#", 1)[0]
            t.request(method, path, time.perf_counter() - w0, time.thread_time() - c0,
                      getattr(handler, "_last_status", None))
        except Exception:
            pass


def get_timings(req):
    t = of(req.server)
    if t is None:
        return 200, {"up_s": None, "cpu_s": round(time.process_time(), 3), "threads": threading.active_count(),
                     "phases": [], "requests": []}
    return 200, t.snapshot()


def dispatch_studio(req):
    if req.path == "studio/timings":
        return get_timings(req) if req.method == "GET" else (405, {"error": "method not allowed"})
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}


def write_line(line: str) -> None:  # pragma: no cover - a convenience for callers outside a server
    sys.stdout.write(line + "\n")


def init_file(state_dir) -> str:
    """`halo init --timings`: the file the Studio it starts writes its lines to (emptied first), named in
    HALO_STUDIO_TIMINGS for that child; '' when it cannot be written."""
    from pathlib import Path
    path = Path(state_dir) / "studio-timings.log"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    except OSError:
        return ""
    os.environ[ENV] = str(path)
    return str(path)


def tail(path: str, say: "Callable[[str], None]", *, every: float = 0.5, for_s: float = 600.0) -> None:
    """Print the lines a Studio appends to `path` (a daemon thread, for `for_s` seconds at most)."""
    def run() -> None:
        pos, end = 0, time.monotonic() + for_s
        while time.monotonic() < end:
            try:
                with open(path, encoding="utf-8") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
            except OSError:
                chunk = ""
            for line in chunk.splitlines():
                if line.strip():
                    say(line)
            time.sleep(every)
    threading.Thread(target=run, name="halo-init-timings", daemon=True).start()
