"""halo_harness.ext.yamlio -- Halo's YAML reader and writer (extension API 1.0).

    read_yaml(path)                          # a dict; {} for an empty file; None when missing or not a mapping
    write_yaml("doc-review", "reports/last.yaml", {"ok": True})   # [] when written, else one line

The same reader and writer the bio and lineup files go through
(`agents_yaml._read_yaml_file` / `_write_yaml_file`: safe loading, an atomic
write). A write lands where `write_private` would put it (the pack's data
folder; elsewhere with the `home-write` permission).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def read_yaml(path) -> Optional[dict]:
    from halo_harness.agents_yaml import _read_yaml_file
    return _read_yaml_file(Path(path))


def write_yaml(pack_id: str, path, data: dict) -> "list[str]":
    from halo_harness.agents_yaml import _write_yaml_file
    from halo_harness.ext.files import target
    if not isinstance(data, dict):
        return ["write_yaml takes a mapping"]
    dest, problem = target(pack_id, path)
    if dest is None:
        return [problem]
    dest.parent.mkdir(parents=True, exist_ok=True)
    return _write_yaml_file(dest, data)


__all__ = ["read_yaml", "write_yaml"]
