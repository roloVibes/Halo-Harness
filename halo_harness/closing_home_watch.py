"""halo_harness.closing_home_watch -- a model server that "stops when the last Halo process on this home exits"
(Halo 3.6.0.0 R10, closing.py).

    python -I closing_home_watch.py <state dir> <server pid> <server start> <launcher pid> <launcher start> <pkg parent>

`halo local serve` (and the engine and voice servers) return at once; the server they start is someone else's binary
and watches nothing. This tiny Halo-owned process does: every half second it looks for a living Halo of this home --
the command that started the server (until it returns), a session (run/sessions.json), the Studio (studio.json), the
LAN host (host/serve.json) -- and when two looks in a row find none, it ends the server (its group, then hard) and
exits. It is the server's owner in run/local-servers.json, so if it is itself killed hard, the next launch's sweep
stops the server. Never a pid but the server's, checked by its start time.
"""

import json
import os
import signal
import sys
import time


def _alive(pid, start=None) -> bool:
    from halo_harness import children as C
    if not isinstance(pid, int) or pid <= 0 or pid == os.getpid():
        return False
    return C.same_process(pid, start) if start else C.pid_running(pid)


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _session_alive(row: dict) -> bool:
    """A session's row names a living session: its pid runs, and the process that has it did not begin after the row
    was written (3.6.0.9). A session that was killed hard leaves its row, and the system gives its pid to the next
    program (Windows at once): that program is not a Halo of this home, and the server would never be stopped while
    it runs. The row's `started` is written by the session itself once it runs, so a process that began more than a
    moment later cannot be it (children.newer_than_row: provable on Windows and macOS; on Linux, and for a row with
    no time, the pid is taken at its word as before)."""
    pid = row.get("pid")
    if not _alive(pid):
        return False
    from halo_harness import children as C
    return not C.newer_than_row({"pid": pid, "since": row.get("started")})


def halos_alive(state: str, launcher: "tuple[int, str]") -> bool:
    if _alive(launcher[0], launcher[1] or None):
        return True
    rows = (_read(os.path.join(state, "run", "sessions.json")) or {}).get("sessions") or []
    if isinstance(rows, list) and any(isinstance(r, dict) and _session_alive(r) for r in rows):
        return True
    studio = _read(os.path.join(state, "studio.json")) or {}
    if _alive(studio.get("pid"), studio.get("pstart")):
        return True
    host = _read(os.path.join(state, "host", "serve.json")) or {}
    return _alive(host.get("pid"), host.get("start_time"))  # 3.6.0.0 fx: serve.json records it now


def _end_server(pid: int, start: str) -> None:
    from halo_harness import children as C
    from halo_harness import closing
    # 3.6.0.0 fx: one unreadable start time (macOS: a `ps` past its limit) is read again, never taken as "gone": the
    # watch returns after this, so giving up here left the server running with no owner
    if not C.provably_same(pid, start, tries=5):
        return
    # 3.6.0.9: a soft stop the system refused outright (Windows: taskkill without /F on a console program, which a
    # model server is) is not waited for: the 2 s were spent on nothing, and the server outlived its last Halo by them.
    # (taskkill /T also answers no when only ONE process of the tree could not be asked: a windowed root that would
    # have closed politely is then stopped hard too. The servers this watch owns are console programs.)
    asked = closing._signal_tree(pid, hard=False)
    deadline = time.monotonic() + (0.0 if asked is False else 2.0)
    while time.monotonic() < deadline and C.same_process(pid, start):
        time.sleep(0.1)
    if C.provably_same(pid, start, tries=5):
        closing._signal_tree(pid, hard=True)


def main(argv: list) -> int:
    state, spid, sstart, lpid, lstart, parent = argv[0], int(argv[1]), argv[2], int(argv[3]), argv[4], argv[5]
    if parent and parent not in sys.path:
        sys.path.insert(0, parent)
    from halo_harness import children as C

    def on_term(*_a):
        _end_server(spid, sstart)
        sys.exit(0)
    for sig in ("SIGTERM", "SIGHUP", "SIGINT", "SIGBREAK"):
        if hasattr(signal, sig):
            try:
                signal.signal(getattr(signal, sig), on_term)
            except (OSError, ValueError):
                pass
    misses = 0
    while sstart and C.same_process(spid, sstart):  # a kept look (macOS: one `ps` per PS_TTL_S); _end_server proves afresh
        misses = 0 if halos_alive(state, (lpid, lstart)) else misses + 1
        if misses >= 2:
            _end_server(spid, sstart)
            return 0
        time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
