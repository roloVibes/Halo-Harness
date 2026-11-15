"""halo_harness.yamlfile -- the YAML reader and writer agent, pack and workflow files go through (Halo 3.6.0.0 R5b:
moved from agents_yaml.py, which went with bios): safe loading, one parse per change of a file, an atomic write.

    read_yaml_file(path) -> dict | None      write_yaml_file(path, data) -> [problem]
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml


# 3.6.0.0 R14: libyaml's scanner and parser when PyYAML was built with it (every PyPI wheel is), PyYAML's own otherwise:
# the same SafeConstructor and resolver either way, so the same mapping -- a pack's 50 bios parse in a tenth of the time
_LOADER = getattr(yaml, "CSafeLoader", None) or yaml.SafeLoader
_STOCK_SAFE_LOAD = yaml.safe_load


def safe_load(text: str):
    """`yaml.safe_load`, through libyaml when it is there (_LOADER). A `yaml.safe_load` replaced in this process (a
    test that counts the parses) is called as it is."""
    if yaml.safe_load is not _STOCK_SAFE_LOAD:
        return yaml.safe_load(text)
    return yaml.load(text, Loader=_LOADER)  # noqa: S506  (a safe loader: SafeConstructor)


_YAML_READS: dict = {}  # the file's full path -> (stamp, parsed): one parse per file per change (3.5.0.1)
_YAML_READS_MAX = 4096
_YAML_SETTLED_NS = 3_000_000_000  # a file changed in the last 3 s is read every time, never kept


def _yaml_key(path) -> str:
    import os
    return os.path.normcase(os.path.abspath(str(path)))


def _read_yaml_file(path: Path) -> "Optional[dict]":
    """The file's mapping, None when it cannot be read or parsed. 3.5.0.1: parsed once per change of the file, and
    each caller gets its own copy. Before, a pack's check read every bio of the pack again for every stage of every
    workflow (48 bios x 58 stages = 2,500 parses, seconds on every command and every Studio read that builds the
    pack list).

    What "unchanged" means: the same time, size, file id and change time. And a file whose time is within the last
    three seconds is never kept (the rule git uses for its index): a second write of the same size inside one tick
    of the file system's clock (two seconds on some volumes) would otherwise be answered from the copy made before
    it. So the first reads after any write, by Halo or by anything else, come from the disk."""
    import copy
    import time
    try:
        st = path.stat()
    except OSError:
        return None
    key = _yaml_key(path)
    stamp = (st.st_mtime_ns, st.st_size, getattr(st, "st_ino", 0), getattr(st, "st_ctime_ns", 0))
    hit = _YAML_READS.get(key)
    if hit is not None and hit[0] == stamp:
        return copy.deepcopy(hit[1])
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = safe_load(text)
    except yaml.YAMLError:
        return None
    data = data if isinstance(data, dict) else (None if data is not None else {})
    settled = abs(time.time_ns() - st.st_mtime_ns) > _YAML_SETTLED_NS
    if data is not None and settled:
        if len(_YAML_READS) >= _YAML_READS_MAX:
            _YAML_READS.clear()
        _YAML_READS[key] = (stamp, copy.deepcopy(data))
    elif not settled:
        _YAML_READS.pop(key, None)
    return data


def _write_yaml_file(path: Path, data: dict) -> "list[str]":
    """Atomic YAML write (temp file + replace, the old file's mode kept);
    `[]` on success, else one problem line -- never raises an OSError."""
    from halo_harness.privateio import write_atomic_keep_mode
    text = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)
    try:
        write_atomic_keep_mode(path, text)
    except OSError as e:
        return [f"cannot write {path}: {e}"]
    finally:
        _YAML_READS.pop(_yaml_key(path), None)  # 3.5.0.1: Halo's own write is never answered from the read cache
    return []



read_yaml_file = _read_yaml_file
write_yaml_file = _write_yaml_file
