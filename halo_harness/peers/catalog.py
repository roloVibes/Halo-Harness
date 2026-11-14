"""halo_harness.peers.catalog -- the capability catalog's cache on disk (Halo 3.0.6.0 R6; out of fleet/capabilities.py
in 3.4.0.0 C, when the fleet left the core for the shipped `fleet` pack).

The fleet pack gathers the catalog (what this harness can do: its MCP servers, skills, models, hardware) and a hub
reads it; the core only keeps the cache honest: `halo mcp add/remove`, a pack's grants and Studio's pack live-reload
mark it stale (`invalidate`), so the next announce gathers afresh. `config` and `scrub` are the owner's switches
(`fleet.tags`, `fleet.capabilities.hide`) and the path scrubber every catalog string goes through.

    cache_path(home)   <home>/fleet/capabilities.json
    load(home) / save(cat, home) / invalidate(home)
    scrub(obj, homes)  every absolute path cut to its last component (`~` for a home)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

FILE = "capabilities.json"
_loaded: dict = {}
_DRIVE = re.compile(r"(?<![\w/])[A-Za-z]:[\\/][^\s\"'<>|,;]*")
_POSIX = re.compile(r"(?<![\w.~])/(?:home|Users|root|mnt|media|opt|srv|tmp|var|private)/[^\s\"'<>|,;]*")


def _home(home=None) -> Path:
    if home is not None:
        return Path(home)
    from halo_harness.peers.identity import home as h
    return h()


def cache_path(home=None) -> Path:
    return _home(home) / "fleet" / FILE




def _base(m) -> str:
    text = m.group(0).rstrip("\\/.")
    return re.split(r"[\\/]", text)[-1] or "~"


def scrub(obj, homes: tuple = ()):
    """Every string with its absolute paths cut to their last component (`~` for a home)."""
    if isinstance(obj, dict):
        return {k: scrub(v, homes) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v, homes) for v in obj]
    if not isinstance(obj, str):
        return obj
    obj = _POSIX.sub(_base, _DRIVE.sub(_base, obj))
    for h in homes:
        if h and len(h) > 3:
            obj = obj.replace(h, "~")
    return obj


def load(home=None) -> Optional[dict]:
    """The cached catalog (re-read only when the file changed: a relay asks every announce)."""
    path = cache_path(home)
    try:
        mt = path.stat().st_mtime_ns
        hit = _loaded.get(str(path))
        if hit is not None and hit[0] == mt:
            return hit[1]
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    data = data if isinstance(data, dict) and data.get("hash") else None
    _loaded[str(path)] = (mt, data)
    return data


def save(cat: dict, home=None) -> None:
    from halo_harness.privateio import write_private_atomic
    path = cache_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_private_atomic(path, json.dumps(cat, indent=1, ensure_ascii=False))
    _loaded.pop(str(path), None)  # a rewrite inside one mtime tick (Windows) must not read back the old catalog


def invalidate(home=None) -> None:
    """`halo mcp add/remove`: the next announce or read gathers afresh."""
    cat = load(home)
    if cat:
        try:
            save({**cat, "at": 0}, home)
        except OSError:
            pass
