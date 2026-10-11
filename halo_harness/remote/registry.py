"""halo_harness.remote.registry -- `~/.halo/run/sessions.json`, the list of
live sessions that opened a control socket (Halo 2.0.9 round 2).

Entries: `{session_id, cwd, pid, endpoint, token_env, started, title, mode}`
plus `kind` ("tui"/"print") and, on Windows only, `token` (the loopback
socket's token; the file is 0600 and lives in the user's own state dir, so
it is exactly as private as the home directory). `token_env` is None this
round (reserved for a token handed over through the environment).

Written atomically (temp file + `os.replace` through
`privateio.write_private_atomic`) under the `filelock.py` best-effort lock,
so two halo processes registering at once keep both entries. `list_live`
drops (and removes from the file) entries whose pid is gone or whose
endpoint refuses a connect probe -- the same self-healing idea as the `cc:`
bridge's stale `*.sock` sweep, which this module never touches.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from halo_harness.filelock import file_lock
from halo_harness.privateio import write_private_atomic
from halo_harness.remote import client

FILENAME = "sessions.json"
FIELDS = ("session_id", "cwd", "pid", "endpoint", "token_env", "started", "title", "mode")


def registry_path() -> Path:
    from halo_harness.remote.control_socket import run_dir
    return run_dir() / FILENAME


def _load(path: Path) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = data.get("sessions") if isinstance(data, dict) else None
    return [r for r in rows if isinstance(r, dict) and r.get("session_id")] if isinstance(rows, list) else []


def _write(path: Path, rows: list) -> None:
    write_private_atomic(path, json.dumps({"version": 1, "sessions": rows}, indent=2, sort_keys=True))


def make_entry(*, session_id: str, cwd, endpoint: str, pid: Optional[int] = None, token: Optional[str] = None,
               title: str = "", mode: str = "", kind: str = "tui", started: Optional[float] = None) -> dict:
    entry = {"session_id": session_id, "cwd": str(cwd), "pid": pid if pid is not None else os.getpid(),
             "endpoint": endpoint, "token_env": None, "started": started if started is not None else time.time(),
             "title": title, "mode": mode, "kind": kind}
    if token:
        entry["token"] = token
    return entry


def register(entry: dict) -> None:
    path = registry_path()
    with file_lock(path):
        rows = [r for r in _load(path) if r.get("session_id") != entry["session_id"]]
        rows.append(entry)
        _write(path, rows)


def unregister(session_id: str) -> None:
    path = registry_path()
    with file_lock(path):
        rows = _load(path)
        kept = [r for r in rows if r.get("session_id") != session_id]
        if len(kept) != len(rows):
            _write(path, kept)


def update(session_id: str, **fields) -> bool:
    """Patch one live entry (`title`, `mode`, ...); False when it is not there."""
    path = registry_path()
    with file_lock(path):
        rows = _load(path)
        for r in rows:
            if r.get("session_id") == session_id:
                if all(r.get(k) == v for k, v in fields.items()):
                    return True
                r.update(fields)
                _write(path, rows)
                return True
    return False


def pid_alive(pid) -> bool:
    from halo_harness.bg_run import pid_alive as _alive
    return _alive(pid)


def _entry_alive(entry: dict) -> bool:
    pid = entry.get("pid")
    if isinstance(pid, int) and not pid_alive(pid):
        return False
    return client.probe(str(entry.get("endpoint") or ""))


def list_live() -> list:
    """Every registered session still reachable; dead ones are pruned from
    the file. Entries are returned whole (a `token` included -- callers that
    print must leave it out)."""
    path = registry_path()
    if not path.exists():
        return []
    with file_lock(path):
        rows = _load(path)
        live = [r for r in rows if _entry_alive(r)]
        if len(live) != len(rows):
            _write(path, live)
    return live


def entry_for(session_id: str) -> Optional[dict]:
    return next((r for r in list_live() if r.get("session_id") == session_id), None)


def endpoint_for(session_id: str) -> Optional[str]:
    entry = entry_for(session_id)
    return entry.get("endpoint") if entry else None


def sweep_stale_ctl(directory: Optional[Path] = None) -> None:
    """Delete `<id>.ctl` Unix sockets whose listener is gone (POSIX)."""
    from halo_harness.remote.control_socket import run_dir
    d = directory or run_dir()
    try:
        files = list(d.glob("*.ctl"))
    except OSError:
        return
    for f in files:
        if not client.probe(f"unix:{f}"):
            try:
                f.unlink()
            except OSError:
                pass
