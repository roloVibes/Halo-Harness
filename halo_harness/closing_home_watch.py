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


def halos_alive(state: str, launcher: "tuple[int, str]") -> bool:
    if _alive(launcher[0], launcher[1] or None):
        return True
    rows = (_read(os.path.join(state, "run", "sessions.json")) or {}).get("sessions") or []
    if isinstance(rows, list) and any(isinstance(r, dict) and _alive(r.get("pid")) for r in rows):
        return True
    studio = _read(os.path.join(state, "studio.json")) or {}
    if _alive(studio.get("pid"), studio.get("pstart")):
        return True
    host = _read(os.path.join(state, "host", "serve.json")) or {}
    return _alive(host.get("pid"), host.get("start_time"))  # 3.6.0.0 fx: serve.json records it now


def _end_server(pid: int, start: str) -> None:
    from halo_harness import children as C
    from halo_harness import closing
    if not C.provably_same(pid, start):
        return
    closing._signal_tree(pid, hard=False)
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and C.provably_same(pid, start):
        time.sleep(0.1)
    if C.provably_same(pid, start):
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
