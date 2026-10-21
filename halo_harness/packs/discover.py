"""halo_harness.packs.discover -- the packs on disk (Halo 3.2.0.0 R1).

Two folders, nearest first: `<repo>/.halo/packs/<id>/` (project: the
untrusted layer -- its lineups drop `permissions.mode` and allow rules the
way `teams_yaml._drop_untrusted_raise` does) and `~/.halo/packs/<id>/`
(user). A folder whose name starts with `.` is Halo's own (`.data`,
`.backup`, `.staging-*`), never a pack; `state.json` and `journal.jsonl`
beside the packs are files. A pack id found in both folders: the project
one is used and the user one is listed in its `shadowed`.

    discover(cwd=..., state_dir=...)   # [Pack, ...] by id, project first
    find(pack_id, cwd=..., state_dir=...)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from halo_harness.packs import manifest as MF


@dataclass
class Pack:
    id: str
    root: Path
    scope: str  # "project" | "user" | "source" (a folder being inspected or installed)
    manifest: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)
    shadowed: list = field(default_factory=list)

    @property
    def version(self) -> str:
        return str(self.manifest.get("version") or "")

    @property
    def name(self) -> str:
        return str(self.manifest.get("name") or self.id)

    @property
    def description(self) -> str:
        return str(self.manifest.get("description") or "")


def user_packs_dir(state_dir=None) -> Path:
    from halo_harness.config.paths import bridge_home
    return Path(state_dir if state_dir is not None else bridge_home()) / "packs"


def project_packs_dir(cwd=None) -> Path:
    return Path(cwd if cwd is not None else Path.cwd()) / ".halo" / "packs"


def search_dirs(*, cwd=None, state_dir=None) -> "list[tuple[Path, str]]":
    return [(project_packs_dir(cwd), "project"), (user_packs_dir(state_dir), "user")]


def read_pack(root, scope: str, *, folder_is_id: bool = True) -> Pack:
    """One folder as a Pack: its manifest and every problem validate_manifest finds."""
    root = Path(root)
    data, problems = MF.load_manifest(root)
    if data is None:
        return Pack(id=root.name, root=root, scope=scope, manifest={}, problems=problems)
    problems = MF.validate_manifest(data, root=root, folder_is_id=folder_is_id)
    pack_id = data.get("id") if isinstance(data.get("id"), str) and data.get("id") else root.name
    return Pack(id=pack_id, root=root, scope=scope, manifest=data, problems=problems)


def _folders(d: Path) -> "list[Path]":
    try:
        with os.scandir(d) as it:
            return sorted(Path(e.path) for e in it if e.is_dir() and not e.name.startswith("."))
    except OSError:
        return []


def signature(*, cwd=None, state_dir=None) -> tuple:
    """What discovery depends on: each packs folder and each pack.yaml (mtime and size)."""
    out = []
    for d, _scope in search_dirs(cwd=cwd, state_dir=state_dir):
        try:
            st = d.stat()
        except OSError:
            out.append((str(d), None))
            continue
        out.append((str(d), st.st_mtime_ns))
        for folder in _folders(d):
            try:
                mst = (folder / MF.MANIFEST).stat()
                out.append((str(folder), mst.st_mtime_ns, mst.st_size))
            except OSError:
                out.append((str(folder), None, None))
    return tuple(out)


def discover(*, cwd=None, state_dir=None) -> "list[Pack]":
    """Every pack folder, one Pack per id (the project's wins), sorted by id."""
    by_id: "dict[str, Pack]" = {}
    for d, scope in search_dirs(cwd=cwd, state_dir=state_dir):
        for folder in _folders(d):
            pack = read_pack(folder, scope)
            if pack.id in by_id:
                by_id[pack.id].shadowed.append(str(folder))
            else:
                by_id[pack.id] = pack
    return [by_id[k] for k in sorted(by_id)]


def find(pack_id: str, *, cwd=None, state_dir=None) -> Optional[Pack]:
    for pack in discover(cwd=cwd, state_dir=state_dir):
        if pack.id == pack_id:
            return pack
    return None


def same_path(a, b) -> bool:
    try:
        return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))
    except (OSError, ValueError):
        return str(a) == str(b)
