"""halo_harness.design.jsonio -- the JSON file I/O under a design project
(design.json, comments.json, controls.json, version.json, system.json).

Writes go through a temp file + os.replace, so a reader never sees a torn
file; a strict read tells a missing file (the default) from one that exists
but did not parse (UnreadableFile), so a read-modify-write never re-saves a
torn read over the project's real contents.
"""

from __future__ import annotations

import json
from pathlib import Path


class UnreadableFile(ValueError):
    """A project file exists but did not parse: a read-modify-write refuses to save over it."""


def _read_json(p: Path, default, *, strict: bool = False):
    """`default` for a missing file; for an unparsable one (or the wrong JSON type), `default`
    too -- or, with `strict`, UnreadableFile, so a torn read is never re-saved."""
    try:
        data = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else default
    except (OSError, ValueError):
        data = None
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
    from halo_harness.privateio import write_atomic_keep_mode  # temp file + os.replace: never torn
    write_atomic_keep_mode(p, json.dumps(data, indent=2, ensure_ascii=False))
