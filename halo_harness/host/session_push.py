"""halo_harness.host.session_push -- Halo 3.3.8.0 R2: a session with no Studio or hub on its machine (a terminal-only
`halo`) pushes its own ledger lines to the `halo host` that serves its model, so the host's verify, the busy wait and
the offline promise see that peer's calls (before, only the steward job of a Studio or a hub forwarded them, and a
TUI-only peer looked like a client that is not a halo).

`after_call(state_dir, line)` (ollama_steward/ledger.record_call, after the line is written) hands the line to the
existing forwarder (host/ledger_push.push_all: the cursor per host, its lock, the host's profiles in the answer) on a
daemon thread, when the line is this machine's own (no `from`), a paired host serves its url, and no steward job runs
in this process (that job pushes on its tick). One worker per home: it sends what waits, then once more after the
forwarder's cadence (FLUSH_S), so the calls of a busy minute go as one batch. It never blocks a turn and never raises.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Optional

_WORKERS: dict = {}
_LOCK = threading.Lock()
SEAMS: dict = {}  # "wait_s": the pause before the second push (the tests shorten it)


def wanted(state_dir, line: dict) -> bool:
    if not isinstance(line, dict) or line.get("from") or state_dir is None:
        return False
    from halo_harness.ollama_steward.host_client import any_paired, for_host
    if not any_paired(state_dir):
        return False
    from halo_harness.ollama_steward import job
    if str(state_dir) in job._JOBS:
        return False
    url = str((line.get("host") or {}).get("url") or "")
    return bool(url) and for_host(SimpleNamespace(url=url, name=(line.get("host") or {}).get("name") or ""),
                                  state_dir) is not None


def _work(state_dir) -> None:
    from halo_harness.peers.ollama_share import FLUSH_S
    from halo_harness.host.ledger_push import push_all
    stop = threading.Event()
    try:
        push_all(state_dir)
        stop.wait(SEAMS.get("wait_s", FLUSH_S + 1.0))
        push_all(state_dir, force=True)  # the lines that arrived during the wait go now: the cached pusher's cadence
        # gate would hold them until another call (Linux run 41368923557: the second of two lines never left the peer)
    except Exception:
        pass
    finally:
        with _LOCK:
            if _WORKERS.get(str(state_dir)) is threading.current_thread():
                _WORKERS.pop(str(state_dir), None)


def after_call(state_dir, line: dict) -> Optional[threading.Thread]:
    try:
        if not wanted(state_dir, line):
            return None
    except Exception:
        return None
    with _LOCK:
        t = _WORKERS.get(str(state_dir))
        if t is not None and t.is_alive():
            return t
        t = threading.Thread(target=_work, args=(state_dir,), name="halo-session-push", daemon=True)
        _WORKERS[str(state_dir)] = t
    t.start()
    return t
