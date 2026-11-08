"""halo_harness.packs.link -- `halo pack install <folder> --link`: the installed pack is the folder itself, read in
place, so an edit shows at the next read with no reinstall (Halo 3.3.12.0 R4; docs/PACK-AUTHORING.md "The loop").

A link is one small file beside the installed packs, `<packs>/<id>.link` (`~/.halo/packs/`, or the repo's
`.halo/packs/` with `--project`), holding `{"folder": "<the pack's folder>"}`, written through the journal (its row's
`op` is `link`); state.json records the pack with `link: true` and its `root` the folder. Discovery reads a link as a
pack folder of that scope (packs/discover.py), so `list`, `inspect`, `enable`, the doctor, Studio and every session see
it as they see a copied pack; the registry's signature stats the linked folder's pack.yaml and its watched files, so
an edit there shows at once. Halo never writes in a linked folder: `halo pack remove <id>` (or `unlink`) deletes the
link file only (journal `op` `unlink`) and the folder stays; `update` and `rollback` have nothing to do for a link.

    SUFFIX = ".link"
    read_link(path) -> Path | None          the folder a link file names
    links(packs_dir) -> [(link file, folder)]
    link(source, project=False, cwd=None, state_dir=None) -> (ok, lines)
    unlink(pack_id, rec, keep_config=False, cwd=None, state_dir=None) -> (ok, lines)
    linked_line(pack_id, rec) -> str        the one line update / rollback answer for a linked pack ('' otherwise)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

SUFFIX = ".link"


def read_link(path) -> Optional[Path]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    folder = data.get("folder") if isinstance(data, dict) else None
    return Path(folder) if isinstance(folder, str) and folder.strip() else None


def links(packs_dir) -> "list[tuple[Path, Path]]":
    """Every `<id>.link` in a packs folder whose folder is there, by name."""
    out = []
    try:
        with os.scandir(packs_dir) as it:
            names = sorted(e.path for e in it if e.name.endswith(SUFFIX) and not e.name.startswith(".") and e.is_file())
    except OSError:
        return []
    for path in names:
        folder = read_link(path)
        if folder is not None and folder.is_dir():
            out.append((Path(path), folder))
    return out


def linked_line(pack_id: str, rec) -> str:
    if isinstance(rec, dict) and rec.get("link"):
        return (f"{pack_id} is linked to {rec.get('root')}: the installed pack is that folder as it is now, so there "
                "is nothing to update or roll back (edit the folder; halo pack test checks it)")
    return ""


def link(source: str, *, project: bool = False, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    from halo_harness.packs import journal as J
    from halo_harness.packs import state as S
    from halo_harness.packs.discover import project_packs_dir, read_pack, user_packs_dir
    from halo_harness.packs.install import _checks
    from halo_harness.packs.offers import offers, summary
    folder = Path(source).expanduser()
    if not folder.is_dir():
        return False, [f"{source}: --link takes a pack folder on this machine (not a git url or an id)"]
    folder = folder.resolve()
    pack, problems = _checks(folder)
    if problems:
        return False, problems
    base = project_packs_dir(cwd) if project else user_packs_dir(state_dir)
    copy, link_file = base / pack.id, base / f"{pack.id}{SUFFIX}"
    if copy.exists():
        return False, [f"{pack.id} is already installed at {copy}; remove it first (halo pack remove {pack.id})"]
    if link_file.exists():
        return False, [f"{pack.id} is already linked to {read_link(link_file)} (halo pack unlink {pack.id})"]
    op = J.Op("link", pack.id, state_dir=state_dir)
    try:
        op.write(link_file, (json.dumps({"folder": str(folder)}) + "\n").encode("utf-8"))
    except OSError as e:
        op.rollback()
        return False, [f"link of {pack.id} stopped: {e}"]
    op.commit()
    previous = S.entry(pack.id, state_dir) or {}
    kept = list(previous.get("granted") or []) if previous.get("removed") else []
    S.replace(pack.id, {"version": pack.version, "source": str(folder), "installed": S.now(), "enabled": False,
                        "granted": kept, "scope": "project" if project else "user", "root": str(folder), "link": True},
              state_dir)
    from halo_harness.packs.grants import notify_studio
    notify_studio("installed")
    linked = read_pack(folder, "project" if project else "user", folder_is_id=False)
    asked = linked.manifest.get("permissions") or []
    grant = " --grant ".join([""] + list(asked)).strip() if asked else ""
    return True, [f"linked {pack.id} {pack.version}: {folder} is the installed pack, read in place (disabled); "
                  "an edit there shows at the next read, no reinstall",
                  f"it offers: {summary(offers(linked))}",
                  f"it requests: {', '.join(asked) if asked else 'no permissions'}",
                  f"enable it: halo pack enable {pack.id}" + (f" {grant}" if grant else ""),
                  f"halo pack unlink {pack.id} takes the link away; the folder stays"]


def unlink(pack_id: str, rec: dict, *, keep_config: bool = False, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    from halo_harness.packs import journal as J
    from halo_harness.packs import state as S
    from halo_harness.packs.discover import project_packs_dir, user_packs_dir
    from halo_harness.packs.grants import changed
    base = project_packs_dir(cwd) if rec.get("scope") == "project" else user_packs_dir(state_dir)
    link_file = base / f"{pack_id}{SUFFIX}"
    op = J.Op("unlink", pack_id, state_dir=state_dir)
    try:
        op.delete(link_file)
    except OSError as e:
        op.rollback()
        return False, [f"unlink of {pack_id} stopped: {e}; the link is as it was"]
    op.commit()
    if keep_config:
        S.put(pack_id, {"enabled": False, "removed": S.now()}, state_dir)
    else:
        S.drop(pack_id, state_dir)
    changed(state_dir)
    from halo_harness.packs.remove import yours
    lines = [f"unlinked {pack_id}: {rec.get('root')} stays as it is (Halo never wrote in it)"]
    if keep_config:
        lines.append(f"kept its record (grants: {', '.join(rec.get('granted') or []) or 'none'}) for a later install")
    return True, lines + yours(pack_id, cwd=cwd, state_dir=state_dir)
