"""halo_harness.config.renamed_keys -- config keys that changed their name, and the ones that are no longer read
(Halo 3.5.0.0).

Halo 3.5.0.0 named the keys that serve this machine's sessions and its host by what they do. A config.json written
before still loads: `migrate(data)` copies an old key's value to its new name in memory, when the new one is not set
(the file is not rewritten; the next write of that key writes the new name), and every other `fleet.*` key is
ignored. `halo doctor` says once which of those it found (`unused(data)`).

    RENAMED       old dotted key -> new dotted key
    migrate(data) -> data with the new keys filled from the old ones (a copy; `data` is not changed)
    unused(data)  -> the `fleet.*` keys data holds that nothing reads any more, sorted
"""

from __future__ import annotations

import copy

RENAMED = {
    "fleet.enabled": "control.enabled",
    "fleet.private": "control.private",
    "fleet.name": "harness.name",
    "fleet.allow_control": "host.allow_control",
    "fleet.caps.per_harness_usd_per_day": "caps.per_harness_usd_per_day",
    "fleet.caps.per_project_usd_per_day": "caps.per_project_usd_per_day",
    "fleet.attention.signal": "attention.signal",
    "fleet.ollama.share": "ollama.share",
}
UNUSED_LINE = "fleet.* settings are no longer used: Fleet is a separate pack now"


def _get(data: dict, key: str):
    cursor = data
    for part in key.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return _MISSING
        cursor = cursor[part]
    return cursor


def _set(data: dict, key: str, value) -> None:
    cursor = data
    parts = key.split(".")
    for part in parts[:-1]:
        if not isinstance(cursor.get(part), dict):
            cursor[part] = {}
        cursor = cursor[part]
    cursor[parts[-1]] = value


_MISSING = object()


def migrate(data: dict) -> dict:
    """`data` with every renamed key's old value under its new name (when the new one is not set)."""
    if not isinstance(data, dict) or not isinstance(data.get("fleet"), dict):
        return data
    out = None
    for old, new in RENAMED.items():
        value = _get(data, old)
        if value is _MISSING or _get(data, new) is not _MISSING:
            continue
        if out is None:
            out = copy.deepcopy(data)
        _set(out, new, value)
    return out if out is not None else data


def _leaves(node, prefix: str) -> list:
    if isinstance(node, dict) and node:
        return [k for key, v in node.items() for k in _leaves(v, f"{prefix}.{key}")]
    return [prefix]


def unused(data: dict) -> list:
    """The `fleet.*` keys in `data` that nothing reads any more (a renamed one counts once its new name is set)."""
    if not isinstance(data, dict) or not isinstance(data.get("fleet"), dict):
        return []
    keys = _leaves(data["fleet"], "fleet")
    return sorted(k for k in keys if k not in RENAMED or _get(data, RENAMED[k]) is not _MISSING)


def doctor_line(data: dict) -> str:
    """'' or the one line `halo doctor` says: the unused keys, named."""
    keys = unused(data)
    return f"{UNUSED_LINE} ({', '.join(keys)})" if keys else ""
