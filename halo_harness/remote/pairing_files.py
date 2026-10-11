"""halo_harness.remote.pairing_files -- the small pieces under pairing.py:
constants, the result tuples, and the locked read/modify/write of the two
JSON state files (`peers.json`, `pending.json`, both 0600)."""

from __future__ import annotations

import json
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from typing import NamedTuple, Optional

from halo_harness.filelock import file_lock
from halo_harness.privateio import write_private_atomic


CODE_TTL_S = 600
CODE_DIGITS = 6
MAX_ATTEMPTS = 3
MAX_PENDING = 32  # contact requests; the oldest unapproved one is dropped for a new one
MAX_NOTICES = 20


class Approval(NamedTuple):
    code: str
    expires: float
    trusted: bool


class Redeem(NamedTuple):
    status: str            # ignored | wrong | dropped | expired | paired
    peer: Optional[dict]
    secret: bytes


class PairingError(Exception):
    pass


def _digits(sn: str) -> str:
    return "".join(str(sn).split())


def _hash(code: str, salt: str) -> str:
    return sha256(f"{salt}|{code}".encode("utf-8")).hexdigest()


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
