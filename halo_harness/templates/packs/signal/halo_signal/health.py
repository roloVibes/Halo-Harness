"""halo_signal.health -- the service's health file and stop file.

The supervisor starts the service with HALO_SERVICE_HEALTH (the file pack.yaml's `health.file` names, in the data
folder) and HALO_SERVICE_STOP (the file whose existence asks it to end). Run by hand (`bin/signal.py service` in a
terminal) both default to the data folder: health.json and service.stop.

    Health(path=None, stop=None, clock=time.time)
      .write(state, line)     {pid, state, line, updated, phones} -- starting | connected | rate-limited | stopped | off
      .beat(phones)           the same row again at most every BEAT_S (the supervisor reads its age)
      .stop_asked() -> bool
    read(path=None) -> row     what /signal status and Setup show
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from halo_signal import files

BEAT_S = 15.0


def health_path() -> Path:
    return Path(os.environ.get("HALO_SERVICE_HEALTH") or files.path("health.json"))


def stop_path() -> Path:
    return Path(os.environ.get("HALO_SERVICE_STOP") or files.path("service.stop"))


class Health:
    def __init__(self, path: Optional[Path] = None, stop: Optional[Path] = None, clock=time.time) -> None:
        self.path = Path(path) if path else health_path()
        self.stop_file = Path(stop) if stop else stop_path()
        self.clock = clock
        self.state, self.line, self.phones, self.last = "starting", "", 0, 0.0

    def write(self, state: Optional[str] = None, line: Optional[str] = None, phones: Optional[int] = None) -> None:
        self.state = state or self.state
        self.line = line if line is not None else self.line
        self.phones = phones if phones is not None else self.phones
        self.last = self.clock()
        row = {"pid": os.getpid(), "state": self.state, "line": self.line, "updated": self.last, "phones": self.phones}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps(row, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass

    def beat(self, phones: int) -> None:
        if self.clock() - self.last >= BEAT_S or phones != self.phones:
            self.write(phones=phones)

    def stop_asked(self) -> bool:
        return self.stop_file.exists()


def read(path: Optional[Path] = None) -> dict:
    row = files.read_json(path or health_path())
    if not row:
        return {"state": "off", "line": "the bridge has not run yet", "updated": None}
    return row
