"""halo_signal.phones -- what each paired phone keeps across bridge restarts (phones.json, 0600):

    {aci: {session_id, home, notify: [kind, ...], verbosity}}

`session_id` is the session the phone is attached to (re-attached when it is still live); `home` the folder a new
session starts in (`/cd`, `/new <folder>`; default the pack's `home_dir`, else your home folder); `notify` what
arrives unprompted (`/notify on|off <kind>`; default the pack's `notify`); `verbosity` loud | quiet (`/loud`,
`/quiet`).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from halo_harness.ext import remote as R

from halo_signal import files, settings

KINDS = ("turn_done", "asks", "errors", "supervisor", "steward")


def default_home() -> str:
    raw = str(settings.get("home_dir") or "").strip()
    return str(Path(os.path.expanduser(raw)) if raw else R.user_home())


class Phones:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else files.path("phones.json")

    def _all(self) -> dict:
        return dict(files.read_json(self.path).get("phones", {}))

    def get(self, aci: str) -> dict:
        row = dict(self._all().get(aci) or {})
        row.setdefault("home", default_home())
        notify = row.get("notify")
        row["notify"] = [k for k in notify if k in KINDS] if isinstance(notify, list) else \
            [k for k in settings.get("notify") if k in KINDS]
        if row.get("verbosity") not in ("loud", "quiet"):
            row["verbosity"] = settings.get("verbosity")
        return row

    def set(self, aci: str, **fields) -> dict:
        with files.edit_json(self.path, {"version": 1, "phones": {}}) as d:
            row = d.setdefault("phones", {}).setdefault(aci, {})
            for k, v in fields.items():
                if v is None:
                    row.pop(k, None)
                else:
                    row[k] = v
            return dict(row)

    def forget(self, aci: str) -> None:
        with files.edit_json(self.path, {"version": 1, "phones": {}}) as d:
            d.setdefault("phones", {}).pop(aci, None)

    def notify_set(self, aci: str, kind: str, on: bool) -> "list[str]":
        now = self.get(aci)["notify"]
        want = [k for k in KINDS if (k in now and not (k == kind and not on)) or (k == kind and on)]
        self.set(aci, notify=want)
        return want


def resolve_home(raw: str, base: str) -> "tuple[Optional[str], str]":
    """A folder the phone named (`~/x`, an absolute path, or relative to `base`) -> (its path, '') or (None, why)."""
    text = (raw or "").strip()
    if not text:
        return None, "name a folder: /cd ~/work"
    p = Path(os.path.expanduser(text))
    if not p.is_absolute():
        p = Path(base) / p
    if not p.is_dir():
        return None, f"{text} is not a folder on this computer"
    return str(p.resolve()), ""


def short(path: str) -> str:
    """`~/work` for a folder under your home folder."""
    try:
        rel = Path(path).resolve().relative_to(R.user_home().resolve())
        return "~" if str(rel) == "." else "~/" + rel.as_posix()
    except (ValueError, OSError):
        return str(path)
