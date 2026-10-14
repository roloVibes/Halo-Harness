"""halo_harness.orchestra.jsonl -- small file helpers shared by the run's
logs: append one JSON line, read every line, write a JSON file whole, and
the run's start time (for `elapsed_s`).

Appends go through `halo_harness.filelock.file_lock` on `<file>.lock` plus a
process-wide lock per file: the file lock keeps two halo processes from
interleaving, the thread lock keeps two threads of one process ordered even
when the advisory file lock is unavailable.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from halo_harness.filelock import file_lock

_THREAD_LOCKS: dict = {}
_GUARD = threading.Lock()
_STARTED: dict = {}


def _thread_lock(path: Path) -> threading.RLock:
    key = os.path.normcase(str(Path(path).absolute()))
    with _GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def locked(path):
    """Hold the thread lock and the advisory file lock for `path`."""
    path = Path(path)
    with _thread_lock(path):
        with file_lock(path, timeout=10.0):
            yield


def append_line(path, obj: dict) -> None:
    """Append one JSON line. Callers that read-then-append hold `locked(path)`
    themselves (the lock is re-entrant per thread only through `locked`, so
    this function takes no lock of its own)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False, default=str) + "\n"
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)
        fh.flush()


def read_lines(path) -> list:
    """Every parsable JSON object line; a torn or blank line is skipped."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except ValueError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


class Tail:
    """Incremental reader of one append-only JSONL file: `lines()` parses
    only the bytes added since the last call (a shrunk file starts over),
    so folding a long log stays cheap. Only whole lines are consumed."""

    def __init__(self, path):
        self.path = Path(path)
        self._pos = 0
        self._entries: list = []

    def lines(self) -> list:
        try:
            with open(self.path, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                if size < self._pos:
                    self._pos, self._entries = 0, []
                fh.seek(self._pos)
                chunk = fh.read()
        except OSError:
            return list(self._entries)
        end = chunk.rfind(b"\n")
        if end >= 0:
            for raw in chunk[:end + 1].decode("utf-8", errors="replace").splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    self._entries.append(obj)
            self._pos += end + 1
        return list(self._entries)


def write_json(path, data) -> None:
    """Temp file beside `path`, then os.replace: a reader never sees half a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def read_json(path, default=None):
    """The parsed file, or `default` when it is missing or does not parse."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def run_started(run_dir) -> float:
    """The run's start time (run.json `created`), cached per run folder;
    the current time when run.json is missing."""
    key = os.path.normcase(str(Path(run_dir).absolute()))
    cached: Optional[float] = _STARTED.get(key)
    if cached is not None:
        return cached
    meta = read_json(Path(run_dir) / "run.json", {})
    created = meta.get("created") if isinstance(meta, dict) else None
    if isinstance(created, (int, float)) and not isinstance(created, bool):
        _STARTED[key] = float(created)
        return float(created)
    return time.time()


def elapsed(run_dir, ts: float) -> float:
    """Seconds since the run started, rounded to milliseconds."""
    return round(max(0.0, ts - run_started(run_dir)), 3)
