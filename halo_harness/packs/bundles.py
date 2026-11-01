"""halo_harness.packs.bundles -- the bundles here: the ones Halo ships and every installed pack with a `bundle:` block
(Halo 3.3.7.0 R5; docs/PACKS.md "Bundles").

    shipped_dir() -> halo_harness/templates/bundles/   (one folder per bundle, each a pack: <id>/pack.yaml)
    listing(cwd=None, state_dir=None) -> [Entry]       installed bundles first (project, then user), then the shipped ones
                                                        not installed; one per id
    Entry = {id, name, description, block (manifest_bundle.block), root, scope (project | user | shipped), installed,
             enabled, problems}
    find(bundle_id, cwd=None, state_dir=None) -> Entry | None
    ensure_installed(entry, cwd=None, state_dir=None) -> (ok, lines, pack)   a shipped bundle installed (packs/install.py)
        and enabled; an installed one enabled; nothing else is written
A bundle requests no permissions, so enabling one grants nothing. Reads only, apart from ensure_installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from halo_harness.packs.manifest_bundle import block, is_bundle


def shipped_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "templates" / "bundles"


def _entry(pack, scope: str, enabled: bool, installed: bool) -> dict:
    return {"id": pack.id, "name": pack.name, "description": pack.description, "block": block(pack), "root": str(pack.root),
            "scope": scope, "installed": installed, "enabled": enabled, "problems": list(pack.problems)}


def _shipped() -> list:
    from halo_harness.packs.discover import read_pack
    base = shipped_dir()
    try:
        folders = sorted(d for d in base.iterdir() if d.is_dir() and (d / "pack.yaml").is_file())
    except OSError:
        return []
    return [read_pack(d, "source", folder_is_id=True) for d in folders]


def listing(cwd=None, state_dir=None) -> list:
    from halo_harness.packs import state as S
    from halo_harness.packs.discover import discover
    data = S.load(state_dir)
    out, seen = [], set()
    for pack in discover(cwd=cwd, state_dir=state_dir):
        if is_bundle(pack.manifest):
            out.append(_entry(pack, pack.scope, S.enabled_for(pack, data), True))
            seen.add(pack.id)
    for pack in _shipped():
        if pack.id not in seen and is_bundle(pack.manifest):
            out.append(_entry(pack, "shipped", False, False))
            seen.add(pack.id)
    return out


def find(bundle_id: str, cwd=None, state_dir=None) -> Optional[dict]:
    return next((e for e in listing(cwd=cwd, state_dir=state_dir) if e["id"] == bundle_id), None)


def ensure_installed(entry: dict, cwd=None, state_dir=None) -> "tuple[bool, list, object]":
    from halo_harness.packs import grants as G
    from halo_harness.packs.discover import find as find_pack
    lines: list = []
    if not entry["installed"]:
        from halo_harness.packs.install import install
        ok, got = install(entry["root"], cwd=cwd, state_dir=state_dir)
        if not ok:
            return False, got, None
        lines.append(got[0])
    pack = find_pack(entry["id"], cwd=cwd, state_dir=state_dir)
    if pack is None:
        return False, lines + [f"no pack {entry['id']!r} here after the install"], None
    if not entry.get("enabled"):
        ok, got = G.enable(pack, state_dir=state_dir)
        if not ok:
            return False, lines + got, None
        lines.append(got[0])
    return True, lines, pack
