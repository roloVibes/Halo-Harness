"""halo_harness.packs.state -- `<state>/packs/state.json` (Halo 3.2.0.0 R1):
which packs are installed, from where, enabled or not, and what is granted.

    {"version": 1,
     "installed": {"<id>": {"version": "1.2.0", "source": "<folder or git url>",
                            "installed": "<UTC time>", "enabled": true,
                            "granted": ["mcp:<server>", "hooks", ...],
                            "scope": "user" | "project", "root": "<the pack's folder>"}}}

Written privately (`privateio.write_private_atomic`, 0600). A pack is
enabled only for the folder its record names (`root`): a same-id pack in
another repo is a different pack until you enable it there.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

VERSION = 1
FILE = "state.json"


def packs_home(state_dir=None) -> Path:
    from halo_harness.packs.discover import user_packs_dir
    return user_packs_dir(state_dir)


def state_path(state_dir=None) -> Path:
    return packs_home(state_dir) / FILE


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load(state_dir=None) -> dict:
    """The whole file; `{"version": 1, "installed": {}}` when missing or unreadable (never raises)."""
    try:
        data = json.loads(state_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("installed"), dict):
        return {"version": VERSION, "installed": {}}
    return data


def save(data: dict, state_dir=None) -> None:
    from halo_harness.packs import registry
    from halo_harness.privateio import write_private_atomic
    data = {"version": VERSION, "installed": dict(sorted((data.get("installed") or {}).items()))}
    write_private_atomic(state_path(state_dir), json.dumps(data, indent=2, sort_keys=False) + "\n")
    registry.invalidate()


def entry(pack_id: str, state_dir=None, *, data: Optional[dict] = None) -> Optional[dict]:
    rec = (data if data is not None else load(state_dir))["installed"].get(pack_id)
    return rec if isinstance(rec, dict) else None


def put(pack_id: str, record: dict, state_dir=None) -> dict:
    data = load(state_dir)
    rec = dict(data["installed"].get(pack_id) or {})
    rec.update(record)
    rec["granted"] = sorted(set(rec.get("granted") or []))
    rec.setdefault("enabled", False)
    data["installed"][pack_id] = rec
    save(data, state_dir)
    return rec


def replace(pack_id: str, record: dict, state_dir=None) -> dict:
    """The whole record for `pack_id`, nothing merged from before."""
    data = load(state_dir)
    rec = {**record, "granted": sorted(set(record.get("granted") or []))}
    rec.setdefault("enabled", False)
    data["installed"][pack_id] = rec
    save(data, state_dir)
    return rec


def drop(pack_id: str, state_dir=None) -> Optional[dict]:
    data = load(state_dir)
    rec = data["installed"].pop(pack_id, None)
    if rec is not None:
        save(data, state_dir)
    return rec


def enabled_for(pack, data: dict) -> bool:
    """True when the record for `pack.id` is enabled and names this pack's folder."""
    from halo_harness.packs.discover import same_path
    rec = entry(pack.id, data=data)
    return bool(rec and rec.get("enabled") and rec.get("root") and same_path(rec["root"], pack.root))


def granted(pack_id: str, data: dict) -> "list[str]":
    rec = entry(pack_id, data=data) or {}
    return [g for g in rec.get("granted") or [] if isinstance(g, str)]


def signature(state_dir=None) -> tuple:
    try:
        st = state_path(state_dir).stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return (None, None)
