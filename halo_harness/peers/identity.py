"""halo_harness.peers.identity -- who this harness is, and the config keys a host reads (Halo 3.0.5.0 R2).

`harness(home=None)` is `{id, name, host, user, version, os}` (the id in `~/.halo/harness-id`, the name
`harness.name`, default `user@host`). With `home` (a Halo state directory) the id and the name are read from that
directory instead of the process's own, so one process can serve one home while its sessions belong to another (the
tests do).

    host.allow_control   none | ask | all   what a paired peer may do on this host (default ask; host/grants.py)

A paired entry in `~/.halo/fleet.json` (the file keeps its name: hosts paired before 3.5.0.0 are in it) may carry its
own `allow_control`; a missing or null one follows the config key.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from halo_harness.remote import session_identity as FI

SHARE_LEVELS = ("status", "events", "full")
CONTROL_LEVELS = ("none", "ask", "all")
DEFAULT_SHARE = "events"
DEFAULT_CONTROL = "ask"
DEFAULT_PORT = 7430
_CACHE_S = 1.0
_cache: dict = {}


def home() -> Path:
    """This process's Halo state directory (`~/.halo`, or the test home)."""
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _read_config(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    from halo_harness.config.renamed_keys import migrate  # 3.5.0.0: an old key's value under its new name
    return migrate(data) if isinstance(data, dict) else {}


def config_value(key: str, default=None, home_dir: Optional[Path] = None):
    """A dotted config key from `<home>/config.json` (this process's home by
    default), cached for a second so a busy relay never rereads it per frame."""
    path = (Path(home_dir) if home_dir is not None else home()) / "config.json"
    now = time.monotonic()
    hit = _cache.get(str(path))
    if hit is None or now - hit[0] > _CACHE_S:
        hit = (now, _read_config(path))
        _cache[str(path)] = hit
    cursor = hit[1]
    for part in key.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return default
        cursor = cursor[part]
    return cursor


def forget_cache() -> None:
    _cache.clear()


def harness_name(home_dir: Optional[Path] = None) -> str:
    if home_dir is None:
        return FI.harness_name()
    name = str(config_value("harness.name", "", home_dir) or "").strip()
    return (name or f"{FI._user()}@{FI._host()}")[:64]


def harness(home_dir: Optional[Path] = None) -> dict:
    """`{id, name, host, user, version, os}` of this harness (or of `home_dir`'s)."""
    if home_dir is None:
        return FI.harness()
    import os
    import platform
    from halo_harness import __version__
    return {"id": FI.harness_id(home_dir), "name": harness_name(home_dir), "host": FI._host(), "user": FI._user(),
            "version": __version__, "os": (platform.system() or os.name).lower()}


def _level(value, allowed: tuple, default: str) -> str:
    v = str(value or "").strip().lower()
    return v if v in allowed else default


def allow_control(entry: Optional[dict] = None) -> str:
    own = (entry or {}).get("allow_control")
    if own in CONTROL_LEVELS:
        return own
    return _level(config_value("host.allow_control", DEFAULT_CONTROL), CONTROL_LEVELS, DEFAULT_CONTROL)


def offline() -> bool:
    """`network.offline` (`--offline`, `/offline on`): the relay stops and `halo host serve` refuses."""
    from halo_harness.providers.http import offline_mode_enabled
    return offline_mode_enabled()
