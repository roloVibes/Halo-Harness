"""halo_harness.remote.pairing_files -- the locked read/modify/write of a small private JSON file (Halo 2.0.9 round 3,
written for the Signal bridge's peers.json and pending.json; 3.3.13.0 R3: the Signal pairing left with the signal pack,
and these two stay for the fleet's own files: fleet/store.py, fleet/pairing.py).

    _read(path, default) -> dict        the mapping, or `default`
    _edit(path, default)                a context manager: locked read, the dict to change, an atomic 0600 write
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

from halo_harness.filelock import file_lock
from halo_harness.privateio import write_private_atomic


def _read(path: Path, default: dict) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default
    return data if isinstance(data, dict) else default


@contextmanager
def _edit(path: Path, default: dict):
    with file_lock(path):
        data = _read(path, default)
        yield data
        write_private_atomic(path, json.dumps(data, indent=2, sort_keys=True))
