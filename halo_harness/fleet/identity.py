"""halo_harness.fleet.identity -- who this harness is and the fleet's config
keys (Halo 3.0.5.0 "Fleet" round R2).

`harness(home=None)` is R1's `{id, name, host, user, version, os}` (the id in
`~/.halo/fleet-id`, the name `fleet.name`, default `user@host`). With `home`
(a Halo state directory such as a hub's) the id and the name are read from
that directory instead of the process's own, so one process can hold a hub
for one home while its sessions belong to another (the tests do).

Config keys (docs/CONFIG.md):

    fleet.share          status | events | full      (default events)
    fleet.allow_control  none | ask | all            (default ask)
    fleet.allow_answers  true | false                (default false)
    fleet.hub.port       the hub's LAN port          (default 7430)

A hub entry in `~/.halo/fleet.json` may carry its own `share` and
`allow_control`; a missing or null one follows the config key.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from halo_harness.remote import fleet_identity as FI

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
    return data if isinstance(data, dict) else {}


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


def fleet_name(home_dir: Optional[Path] = None) -> str:
    if home_dir is None:
        return FI.fleet_name()
    name = str(config_value("fleet.name", "", home_dir) or "").strip()
    return (name or f"{FI._user()}@{FI._host()}")[:64]


def harness(home_dir: Optional[Path] = None) -> dict:
    """`{id, name, host, user, version, os}` of this harness (or of `home_dir`'s)."""
    if home_dir is None:
        return FI.harness()
    import os
    import platform
    from halo_harness import __version__
    return {"id": FI.harness_id(home_dir), "name": fleet_name(home_dir), "host": FI._host(), "user": FI._user(),
            "version": __version__, "os": (platform.system() or os.name).lower()}


def _level(value, allowed: tuple, default: str) -> str:
    v = str(value or "").strip().lower()
    return v if v in allowed else default


def share(entry: Optional[dict] = None) -> str:
    """The share level for one hub: the entry's own, else `fleet.share`."""
    own = (entry or {}).get("share")
    if own in SHARE_LEVELS:
        return own
    return _level(config_value("fleet.share", DEFAULT_SHARE), SHARE_LEVELS, DEFAULT_SHARE)


def allow_control(entry: Optional[dict] = None) -> str:
    own = (entry or {}).get("allow_control")
    if own in CONTROL_LEVELS:
        return own
    return _level(config_value("fleet.allow_control", DEFAULT_CONTROL), CONTROL_LEVELS, DEFAULT_CONTROL)


def allow_answers() -> bool:
    return FI.truthy(config_value("fleet.allow_answers", False), False)


def hub_port(home_dir: Optional[Path] = None) -> int:
    raw = config_value("fleet.hub.port", DEFAULT_PORT, home_dir)
    try:
        port = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PORT
    return port if 0 <= port <= 65535 else DEFAULT_PORT


def offline() -> bool:
    """`network.offline` (`--offline`, `/offline on`): the relay stops and `serve` refuses."""
    from halo_harness.providers.http import offline_mode_enabled
    return offline_mode_enabled()
