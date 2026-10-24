"""halo_harness.packs.deprecations -- the doctor's rows for a pack whose code
uses an extension API name announced for removal, and for a grant an update
asked for (Halo 3.2.0.0 R7; docs/EXTENSION_API.md "Compatibility and migration").

    used_names(pack)          [(rel, line, name)]: every `halo_harness.ext` name its Python uses
    deprecated_rows(pack)     one doctor row per use of a name in ext.deprecations()
    update_request_rows(pack, rec, granted)
                              one row per permission the installed version requests, its version before the last
                              update did not, and you have not granted

A use is an import (`from halo_harness.ext import read_yaml`) or an attribute
of the module (`ext.read_yaml`, `halo_harness.ext.read_yaml`), found by
walking each `.py` file of the pack (the walk tests/test_ext_api.py makes).
"""

from __future__ import annotations

import ast
from pathlib import Path

EXT = "halo_harness.ext"


def _row(pack_id, check, text, fix, path) -> dict:
    return {"pack": pack_id, "severity": "warns", "check": check, "text": text, "fix": fix, "path": str(path)}


def _uses(tree) -> "list[tuple[int, str]]":
    aliases, out = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == EXT:
            out += [(node.lineno, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module == "halo_harness":
            aliases |= {a.asname or a.name for a in node.names if a.name == "ext"}
        elif isinstance(node, ast.Import):
            aliases |= {a.asname for a in node.names if a.name == EXT and a.asname}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        base = node.value
        if isinstance(base, ast.Name) and base.id in aliases:
            out.append((node.lineno, node.attr))
        elif isinstance(base, ast.Attribute) and base.attr == "ext" and isinstance(base.value, ast.Name) \
                and base.value.id == "halo_harness":
            out.append((node.lineno, node.attr))
    return sorted(set(out))


def used_names(pack) -> "list[tuple[str, int, str]]":
    root, out = Path(pack.root), []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError, ValueError):
            continue
        out += [(path.relative_to(root).as_posix(), line, name) for line, name in _uses(tree)]
    return out


def deprecated_rows(pack) -> "list[dict]":
    from halo_harness.ext.compat import deprecations
    gone = {d["name"]: d for d in deprecations()}
    if not gone:
        return []
    out = []
    for rel, line, name in used_names(pack):
        d = gone.get(name)
        if d is None:
            continue
        use = f" (use ext.{d['use']})" if d["use"] else ""
        out.append(_row(pack.id, "deprecated", f"{pack.id}: {rel} line {line} uses ext.{name}, deprecated since API "
                        f"{d['since']}; it goes away in API {d['removed_in']}{use}",
                        f"use ext.{d['use']}" if d["use"] else f"stop using ext.{name} before API {d['removed_in']}",
                        Path(pack.root) / rel))
    return out


def update_request_rows(pack, rec: dict, granted) -> "list[dict]":
    from halo_harness.packs.manifest import requested
    prev = rec.get("previous") if isinstance(rec, dict) and isinstance(rec.get("previous"), dict) else None
    if not prev or not isinstance(prev.get("requested"), list):
        return []
    have, before = set(granted or []), set(prev["requested"])
    return [_row(pack.id, "update-request", f"{pack.id} {pack.version} requests {perm}, which {prev.get('version')} did "
                 f"not; it is not granted, so what needs it does not run", f"halo pack grant {pack.id} {perm}",
                 Path(pack.root) / "pack.yaml")
            for perm in requested(pack.manifest) if perm not in before and perm not in have]
