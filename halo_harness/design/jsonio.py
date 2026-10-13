"""halo_harness.design.jsonio -- the JSON file I/O under a design project
(design.json, comments.json, controls.json, version.json, system.json).

Three guarantees, from the 3.0.2.0 fix pass:

* a write goes through a temp file in the same folder and `os.replace`, so a
  reader never sees a half-written file (Windows may refuse the replace or a
  read for a moment while another one lands, so both retry briefly);
* a strict read tells a missing file (the default) from one that exists but
  did not parse (`UnreadableFile`), so a read-modify-write never re-saves a
  torn read over the project's real contents;
* one re-entrant lock per project folder, so the read-modify-write of
  comments, knobs, design.json and system.json from Studio's request threads
  and a running turn never drop each other's rows.
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


class UnreadableFile(ValueError):
    """A project file exists but did not parse: a read-modify-write refuses to save over it."""


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


def _read_json(p: Path, default, *, strict: bool = False):
    """`default` for a missing file; for an unparsable one (or the wrong JSON
    type), `default` too -- or, with `strict`, UnreadableFile, so a torn read
    is never re-saved."""
    data = None
    for attempt in range(3):  # Windows can refuse a read for a moment while a replace lands
        try:
            data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default
            break
        except PermissionError:
            time.sleep(0.02 * (attempt + 1))
        except (OSError, ValueError):
            break
    if type(data) is type(default):
        return data
    if strict:
        raise UnreadableFile(f"{p} exists but did not parse; leaving it as it is")
    return default


def _read_jsonl_line(line: str):
    try:
        return json.loads(line) if line.strip() else None
    except ValueError:
        return None


def _write_json(p: Path, data) -> None:
    """Temp file beside `p`, then os.replace: never torn. An existing file keeps its mode."""
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = os.stat(p).st_mode & 0o777
    except OSError:
        mode = None
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(data, indent=2, ensure_ascii=False))
        if mode is not None:
            try:
                os.chmod(tmp, mode)
            except OSError:
                pass
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


# The public spellings the Studio side imports.
read_json = _read_json
write_json = _write_json
