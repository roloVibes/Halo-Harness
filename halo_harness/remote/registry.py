"""halo_harness.remote.registry -- `~/.halo/run/sessions.json`, the list of
live sessions that opened a control socket (Halo 2.0.9 round 2).

Entries: `{session_id, cwd, pid, endpoint, token_env, started, title, mode}`
plus `kind` (tui | print | orchestra-worker | mission-worker) and, since
3.0.5.0 (Fleet), `harness` (`{id, name, host, user, version, os}`),
`project` (`{root, repo, branch, dirty}`) and `parent` (the session that
spawned it, or None); an entry written before those keys existed still
loads (`public_entry` fills them in). On Windows only, `token` (the loopback
socket's token; the file is 0600 and lives in the user's own state dir, so
it is exactly as private as the home directory). `token_env` is None this
round (reserved for a token handed over through the environment).

Written atomically (temp file + `os.replace` through
`privateio.write_private_atomic`) under the `filelock.py` best-effort lock,
so two halo processes registering at once keep both entries. `list_live`
drops (and removes from the file) entries whose pid is gone or whose socket
file is gone, so a crashed process never leaves a stale row behind; a
refused connect probe only marks the row `unreachable_since` (3.6.0.4) and
it leaves after UNREACHABLE_PRUNE_S of failures without one success.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from halo_harness.filelock import file_lock

# 3.3.8.1: file_lock yields unheld after its timeout instead of raising, and a register that went on unlocked lost a
# row under eight concurrent registers on the Windows runner (run 41387434690); 30 s is far past any real contention.
LOCK_S = 30.0
from halo_harness.privateio import write_private_atomic
from halo_harness.remote import client

FILENAME = "sessions.json"
FIELDS = ("session_id", "cwd", "pid", "endpoint", "token_env", "started", "title", "mode", "kind", "harness",
          "project", "parent", "mission", "part",  # mission, part: a mission-worker's (3.0.6.0 R7)
          "follows", "first_words")  # 3.6.0.2 P16: the id this row took over from; P70: its first prompt's words
PUBLIC = ("session_id", "title", "cwd", "mode", "kind", "started", "pid", "harness", "project", "parent",
          "mission", "part", "follows", "first_words")
UNREACHABLE = "unreachable_since"  # 3.6.0.4: the first failed probe's time (time.time) in a run of failures
UNREACHABLE_PRUNE_S = 30.0  # probes failing this long without one success: the row leaves
FIRST_WORDS = 6  # 3.6.0.2 P70: the first six words of the first user message,
FIRST_WORDS_CAP = 60  # at most 60 characters


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
               title: str = "", mode: str = "", kind: str = "tui", started: Optional[float] = None,
               harness: Optional[dict] = None, project: Optional[dict] = None, parent: Optional[str] = None) -> dict:
    entry = {"session_id": session_id, "cwd": str(cwd), "pid": pid if pid is not None else os.getpid(),
             "endpoint": endpoint, "token_env": None, "started": started if started is not None else time.time(),
             "title": title, "mode": mode, "kind": kind, "harness": dict(harness or {}),
             "project": dict(project or {"root": str(cwd), "repo": None, "branch": None, "dirty": None}),
             "parent": parent}
    if token:
        entry["token"] = token
    return entry


def first_words(text) -> str:
    """3.6.0.2 P70: the first six words of `text`, joined by single spaces, at most 60 characters."""
    return " ".join(str(text or "").split()[:FIRST_WORDS])[:FIRST_WORDS_CAP]


def public_entry(entry: dict) -> dict:
    """The fields a listing may show (never `endpoint`, `token` or `token_env`),
    with an old entry's missing keys filled in."""
    row = {k: entry.get(k) for k in PUBLIC}
    row["kind"] = row["kind"] or "tui"
    row["harness"] = row["harness"] if isinstance(row["harness"], dict) else {}
    if not isinstance(row["project"], dict):
        row["project"] = {"root": row.get("cwd"), "repo": None, "branch": None, "dirty": None}
    return row


def register(entry: dict) -> None:
    path = registry_path()
    with file_lock(path, timeout=LOCK_S):
        rows = [r for r in _load(path) if r.get("session_id") != entry["session_id"]]
        rows.append(entry)
        _write(path, rows)


def unregister(session_id: str) -> None:
    path = registry_path()
    with file_lock(path, timeout=LOCK_S):
        rows = _load(path)
        kept = [r for r in rows if r.get("session_id") != session_id]
        if len(kept) != len(rows):
            _write(path, kept)


def update(session_id: str, **fields) -> bool:
    """Patch one live entry (`title`, `mode`, ...); False when it is not there."""
    path = registry_path()
    with file_lock(path, timeout=LOCK_S):
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
    """3.4.1.0 R6: this process at once, and on Windows the process's own exit code (children.pid_running:
    OpenProcess + GetExitCodeProcess), never a `tasklist` spawn: one tasklist slower than its 5 s timeout on a loaded
    box read a live session as dead, list_live pruned its row for good, and Studio lost the session (its mode word
    never moved again: the 3.4.1.0 candidate's Windows runner)."""
    if pid == os.getpid():
        return True
    from halo_harness.children import pid_running
    return pid_running(pid)


def _socket_file_gone(endpoint: str) -> bool:
    """3.6.0.4: a `unix:` endpoint whose socket file is not there any more can never answer again."""
    return endpoint.startswith("unix:") and bool(endpoint[5:]) and not os.path.lexists(endpoint[5:])


def _entry_alive(entry: dict, now: float) -> bool:
    """3.6.0.4: a refused connect means "not answering now", never "dead" (one refused probe while the session's
    accept queue was full pruned its row for good: Studio lost a running terminal session). A row leaves only when its
    pid is not running, its socket file is gone, or its probes have failed for UNREACHABLE_PRUNE_S without one success;
    the first failure's time rides in the row (UNREACHABLE) so every process reading the file counts from it."""
    pid = entry.get("pid")
    if isinstance(pid, int) and not pid_alive(pid):
        return False
    endpoint = str(entry.get("endpoint") or "")
    if client.probe(endpoint):
        entry.pop(UNREACHABLE, None)
        return True
    if _socket_file_gone(endpoint):
        return False
    since = entry.get(UNREACHABLE)
    if not isinstance(since, (int, float)) or isinstance(since, bool):
        entry[UNREACHABLE] = now
        return True
    return now - since < UNREACHABLE_PRUNE_S


def list_live(now: Optional[float] = None) -> list:
    """Every registered session not known dead; dead ones are pruned from the file, and a row whose probe failed
    carries `unreachable_since` (the first failure's time) until a probe succeeds. Entries are returned whole (a
    `token` included -- callers that print must leave it out). `now` is the tests' clock (time.time by default)."""
    path = registry_path()
    if not path.exists():
        return []
    now = time.time() if now is None else now
    with file_lock(path, timeout=LOCK_S):
        rows = _load(path)
        before = json.dumps(rows, sort_keys=True)
        live = [r for r in rows if _entry_alive(r, now)]
        if json.dumps(live, sort_keys=True) != before:
            _write(path, live)
    return live


def listed(session_id: str) -> bool:
    """3.6.0.4: is this id's row in the file? One plain read, no lock, no probe (a session asks it of itself)."""
    return any(r.get("session_id") == session_id for r in _load(registry_path()))


def entry_for(session_id: str) -> Optional[dict]:
    return next((r for r in list_live() if r.get("session_id") == session_id), None)


def endpoint_for(session_id: str) -> Optional[str]:
    entry = entry_for(session_id)
    return entry.get("endpoint") if entry else None


CTL_GRACE_S = 10.0  # a socket this young may be bound but not listening yet


def _is_socket(path: Path) -> bool:
    import stat
    try:
        return stat.S_ISSOCK(os.lstat(path).st_mode)
    except OSError:
        return False


def sweep_stale_ctl(directory: Optional[Path] = None, now: Optional[float] = None) -> None:
    """Delete `<id>.ctl` Unix sockets whose listener is gone (POSIX). A file
    younger than CTL_GRACE_S, or one whose session's registry entry has a
    live pid, is a sibling that is still starting (or running) and is kept."""
    from halo_harness.remote.control_socket import pointer_target, run_dir
    d = directory or run_dir()
    try:
        files = list(d.glob("*.ctl"))
    except OSError:
        return
    if not files:
        return
    owners = {r.get("session_id"): r.get("pid") for r in _load(d / FILENAME)}
    now = time.time() if now is None else now
    for f in files:
        try:
            if now - f.stat().st_mtime < CTL_GRACE_S:
                continue
        except OSError:
            continue
        pid = owners.get(f.stem)
        if isinstance(pid, int) and pid_alive(pid):
            continue
        target = pointer_target(f)  # R12: run/<id>.ctl may name a socket in the short folder
        if not client.probe(f"unix:{target or f}"):
            for p in (f, target if target is not None and _is_socket(target) else None):
                try:
                    if p is not None:
                        p.unlink()
                except OSError:
                    pass
