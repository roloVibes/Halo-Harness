"""halo_harness.ollama_steward.ledger_tap -- Halo 3.3.5.0 R1: the ledger
writer publishes each line as it lands, so the Local tab's traffic view is
live (studio/local_traffic.py turns a line into a row).

    listen(state_dir, fn)        a Studio server of this process takes the lines,
                                 events and frames written for `state_dir`:
                                 fn(kind, payload) with kind "lines" | "events" |
                                 "frames"; returns the function that stops it
    lines(state_dir, rows)       ledger.append_lines calls it (the session's own
                                 lines and the ones a hub takes from its members)
    events(state_dir, rows)      server_events.record_events calls it
    frames(state_dir, frames)    ready frames (a member's resources samples)

With no listener in this process, lines and events go to the Studio running for
this home, if one is (`<state>/studio.json`: its port and token), as one
`POST /api/local/traffic {lines, events}` (studio/launch.api_call) on a daemon thread (a short timeout,
and a missing Studio remembered for NO_STUDIO_S): a TUI session's calls reach
the tab the moment they end. A failure is silent; the ledger file is the record.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from typing import Callable

NO_STUDIO_S = 10.0
POST_TIMEOUT_S = 1.5
_LOCK = threading.Lock()
_LISTENERS: "dict[str, list]" = {}
_NO_STUDIO: dict = {}


def _key(state_dir) -> str:
    return os.path.normcase(os.path.abspath(str(state_dir))) if state_dir is not None else ""


def line_id(row: dict) -> str:
    """The id a line keeps on the wire, in the file and in the page (the text it is written as)."""
    text = json.dumps(row, ensure_ascii=False, default=str)
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def listen(state_dir, fn: Callable) -> Callable:
    key = _key(state_dir)
    with _LOCK:
        _LISTENERS.setdefault(key, []).append(fn)

    def stop() -> None:
        with _LOCK:
            fns = _LISTENERS.get(key) or []
            if fn in fns:
                fns.remove(fn)
            if not fns:
                _LISTENERS.pop(key, None)
    return stop


def _deliver(state_dir, kind: str, payload: list) -> bool:
    with _LOCK:
        fns = list(_LISTENERS.get(_key(state_dir)) or [])
    for fn in fns:
        try:
            fn(kind, payload)
        except Exception:
            pass
    return bool(fns)


def _post(state_dir, body: dict) -> None:
    """One call on the running Studio's loopback API with its stored token (studio/launch.api_call)."""
    from pathlib import Path
    from halo_harness.studio.launch import api_call
    try:
        got = api_call(Path(state_dir), "POST", "local/traffic", body, timeout=POST_TIMEOUT_S)
    except Exception:
        got = None
    if got is None:
        _NO_STUDIO[_key(state_dir)] = time.monotonic() + NO_STUDIO_S


def _send(state_dir, kind: str, rows: list) -> None:
    if not rows or state_dir is None:
        return
    if _deliver(state_dir, kind, rows) or kind == "frames":
        return
    if time.monotonic() < _NO_STUDIO.get(_key(state_dir), 0.0):
        return
    if not os.path.isfile(os.path.join(str(state_dir), "studio.json")):
        _NO_STUDIO[_key(state_dir)] = time.monotonic() + NO_STUDIO_S
        return
    threading.Thread(target=_post, args=(state_dir, {kind: rows}), name="halo-ledger-tap", daemon=True).start()


def lines(state_dir, rows: list) -> None:
    _send(state_dir, "lines", rows)


def events(state_dir, rows: list) -> None:
    _send(state_dir, "events", rows)


def frames(state_dir, rows: list) -> None:
    _send(state_dir, "frames", rows)


def reset() -> None:
    """The tests' fresh start."""
    with _LOCK:
        _LISTENERS.clear()
    _NO_STUDIO.clear()
