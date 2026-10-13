"""halo_harness.design.jsonio -- the design project's small JSON file helpers:
an atomic write (temp file in the same folder, then os.replace) so a reader
never sees a half-written file, and one re-entrant lock per project folder so
the read-modify-write of comments, knobs, design.json and system.json from
Studio's request threads and a running turn never drop each other's rows.
"""

from __future__ import annotations

import functools
import json
import os
import tempfile
import threading
import time
from pathlib import Path

_LOCKS: dict = {}
_GUARD = threading.Lock()


def project_lock(path) -> threading.RLock:
    """The one lock every writer of this project folder takes."""
    key = str(Path(path).resolve())
    with _GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


def locked(fn):
    """Run a Project method under the project's lock (re-entrant: a locked method may call another)."""
    @functools.wraps(fn)
    def run(self, *args, **kwargs):
        with project_lock(self.path):
            return fn(self, *args, **kwargs)
    return run


def read_json(p: Path, default):
    for attempt in range(3):  # Windows can refuse a read for a moment while a replace lands
        try:
            return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default
        except PermissionError:
            time.sleep(0.02 * (attempt + 1))
        except (OSError, ValueError):
            return default
    return default


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2, ensure_ascii=False))
        for attempt in range(5):
            try:
                os.replace(tmp, p)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02 * (attempt + 1))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
