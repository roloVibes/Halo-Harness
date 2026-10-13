"""halo_harness.remote.audit -- `<state>/remote/audit.jsonl`: one hashed line
per command the bridge acted on or refused, per pairing-code attempt and per
refused subscribeReceive (Halo 2.0.9 round 3).

A line is `{"ts", "peer", "h", "kind", "outcome"}` where `h` is the first 16
hex characters of `sha256("<aci>|<counter>|<text>")`. The text itself, the
reply, and every other byte of a conversation are never written anywhere by
the bridge; `peer` is the first 8 characters of the ACI.

The file rotates at `MAX_BYTES` (5 MB): `audit.jsonl` becomes `audit.jsonl.1`
(one previous file is kept, an older one is replaced) and a fresh file starts
(2.0.10 review finding 5).
"""

from __future__ import annotations

import json
import os
import threading
import time
from hashlib import sha256
from pathlib import Path

from halo_harness.privateio import write_private_atomic
from halo_harness.remote.signal_config import remote_dir

MAX_BYTES = 5 * 1024 * 1024
_LOCK = threading.Lock()


def command_hash(aci: str, counter: int, text: str) -> str:
    return sha256(f"{aci}|{counter}|{text}".encode("utf-8")).hexdigest()[:16]


class Audit:
    def __init__(self, path=None, clock=None) -> None:
        self.path = Path(path) if path else remote_dir() / "audit.jsonl"
        self._clock = clock

    def record(self, aci: str, counter: int, text: str, kind: str, outcome: str) -> None:
        row = {"ts": round(self._clock() if self._clock else time.time(), 3), "peer": aci[:8],
               "h": command_hash(aci, counter, text), "kind": kind, "outcome": outcome}
        line = json.dumps(row, sort_keys=True) + "\n"
        with _LOCK:
            self._rotate()
            if not self.path.exists():
                write_private_atomic(self.path, "")
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass

    def _rotate(self) -> None:
        try:
            if self.path.stat().st_size < MAX_BYTES:
                return
            os.replace(self.path, self.path.with_name(self.path.name + ".1"))
        except OSError:
            pass

    def lines(self) -> list:
        try:
            return [json.loads(x) for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]
        except (OSError, ValueError):
            return []
