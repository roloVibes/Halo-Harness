"""halo_harness.ext.config -- a pack's settings (extension API 1.0).

    get_config("doc-review")                     # every setting: pack.yaml's defaults, yours on top
    get_config("doc-review", "style", "short")   # one (a dotted key reaches inside a mapping)
    set_config("doc-review", "style", "long")    # [] when written; one line per schema problem

Keys are the pack's own: they live under `packs.settings.<id>` in
`~/.halo/config.json` and are checked against pack.yaml's `config.schema`
before anything is written. A pack reads and writes no other key.
"""

from __future__ import annotations

_MISSING = object()


def _pack(pack_id: str):
    from halo_harness.packs.discover import find
    from halo_harness.packs.names import pack_id_problem
    line = pack_id_problem(pack_id)
    if line:
        raise ValueError(line)
    return find(pack_id)


def get_config(pack_id: str, key=None, default=None):
    from halo_harness.packs import settings as ST
    pack = _pack(pack_id)
    values = ST.values(pack) if pack is not None else ST.user_values(pack_id)
    if key is None:
        return values
    cursor = values
    for part in str(key).split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return default
        cursor = cursor[part]
    return cursor


def set_config(pack_id: str, key: str, value) -> "list[str]":
    from halo_harness.packs import settings as ST
    pack = _pack(pack_id)
    if pack is None:
        return [f"no pack {pack_id!r} is installed here (halo pack list)"]
    return ST.set_value(pack, key, value)


__all__ = ["get_config", "set_config"]
