"""halo_harness.schemas -- one schema set for the files `halo config where`
lists: `config.json` and a pack's `pack.yaml` (3.6.0.0 R5d: the lineup and bio shapes went with them).

    from halo_harness.schemas import schema_for, check_file_shape
    check_file_shape("pack", data)   # -> [{"check", "key", "text", "closest"}, ...]

`halo doctor --config` (halo_harness/doctor_config.py) runs these for shape
and the existing validators for meaning.
"""

from __future__ import annotations

from halo_harness.schemas.check import check, closest_key
from halo_harness.schemas.config_json import schema as config_json_schema

KINDS = ("config", "pack")  # "pack": a pack's pack.yaml (3.2.0.0 R1)


def schema_for(kind: str) -> dict:
    if kind == "config":
        return config_json_schema()
    from halo_harness.schemas.pack_yaml import pack
    if kind == "pack":
        return pack()
    raise KeyError(kind)


def check_file_shape(kind: str, data) -> list:
    """Every shape finding for one parsed file of `kind` (see KINDS)."""
    return check(data, schema_for(kind))


__all__ = ["KINDS", "schema_for", "check_file_shape", "check", "closest_key"]
