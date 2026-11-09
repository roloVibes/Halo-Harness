"""halo_harness.remote.notify -- one seam for the notes a transport carries to the owner (Halo 3.3.13.0 R3;
docs/REMOTE.md "Transports"). The core says that something happened; every transport that listens (the signal
pack's bridge, or any other pack's) picks it up and decides, per phone or per chat, what to pass on (`/notify`). The
core never knows which transport, or whether one is there.

    notify(kind, text, *, source="", session="", state_dir=None) -> bool
                       one row in <state>/remote/notify.jsonl, written only while a transport listens
    listen(name, state_dir=None)          a transport says it listens (its heartbeat: call it at least once a minute)
    listening(state_dir=None) -> [name]   the transports whose heartbeat is younger than LISTEN_S
    since(cursor, kinds=None, state_dir=None) -> (rows, cursor)
                       the rows after `cursor` (a row id; "" = only what comes after now), oldest first, none older
                       than KEEP_S; a cursor the log no longer holds reads from the oldest row kept

KINDS: `turn_done` (a session's turn ended), `asks` (a card or a decision waits on you: the attention queue),
`errors`, `supervisor` (a goal of the supervisor ended, parked or failed), `steward` (the Ollama steward's note that
asks for attention). A row: {id, ts, kind, text, source, session}. The log keeps the newest KEEP rows; 0600.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Optional

KINDS = ("turn_done", "asks", "errors", "supervisor", "steward")
LISTEN_S = 180.0
KEEP_S = 600.0
KEEP = 200
MAX_TEXT = 4000


def _dir(state_dir=None) -> Path:
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    return Path(state_dir) / "remote"


def log_path(state_dir=None) -> Path:
    return _dir(state_dir) / "notify.jsonl"


def _listeners(state_dir=None) -> Path:
    return _dir(state_dir) / "listeners"


def listen(name: str, state_dir=None) -> None:
    from halo_harness.privateio import write_private_atomic
    safe = "".join(c for c in str(name) if c.isalnum() or c in "-_.")[:40] or "transport"
    try:
        _listeners(state_dir).mkdir(parents=True, exist_ok=True)
        write_private_atomic(_listeners(state_dir) / f"{safe}.json", json.dumps({"name": safe, "ts": time.time()}))
    except OSError:
        pass


def listening(state_dir=None, now: Optional[float] = None) -> "list[str]":
    now = time.time() if now is None else now
    out = []
    folder = _listeners(state_dir)
    for p in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(row, dict) and now - float(row.get("ts") or 0) <= LISTEN_S:
            out.append(str(row.get("name") or p.stem))
    return out


def _rows(state_dir=None) -> "list[dict]":
    try:
        lines = log_path(state_dir).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            row = json.loads(ln)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("id"):
            out.append(row)
    return out


def notify(kind: str, text: str, *, source: str = "", session: str = "", state_dir=None) -> bool:
    """True when a row was written (a transport listens and `kind` is one of KINDS)."""
    if kind not in KINDS or not str(text or "").strip() or not listening(state_dir):
        return False
    from halo_harness.filelock import file_lock
    from halo_harness.privateio import write_private_atomic
    row = {"id": uuid.uuid4().hex[:12], "ts": round(time.time(), 3), "kind": kind, "text": str(text)[:MAX_TEXT],
           "source": str(source or "")[:80], "session": str(session or "")[:64]}
    path = log_path(state_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(path, timeout=5.0):
            rows = [r for r in _rows(state_dir) if time.time() - float(r.get("ts") or 0) <= KEEP_S][-(KEEP - 1):]
            rows.append(row)
            write_private_atomic(path, "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    except (OSError, TimeoutError):
        return False
    return True


def since(cursor: str, kinds=None, state_dir=None, now: Optional[float] = None) -> "tuple[list, str]":
    now = time.time() if now is None else now
    rows = [r for r in _rows(state_dir) if now - float(r.get("ts") or 0) <= KEEP_S]
    if not cursor:
        return [], (rows[-1]["id"] if rows else "-")
    ids = [r["id"] for r in rows]
    start = ids.index(cursor) + 1 if cursor in ids else 0
    new = [r for r in rows[start:] if kinds is None or r.get("kind") in kinds]
    return new, (rows[-1]["id"] if rows else cursor)
