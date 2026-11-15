"""halo_harness.where.crew_files -- the agents, workflows and maps of `halo config where` (Halo 3.6.0.0 R5d, where the
lineup and bio folders were): per kind, this project's `.halo/crew/<kind>s/` (listed even when the folder is not
trusted, and saying so), yours `~/.halo/crew/<kind>s/`, the shipped starters, then one row per enabled pack whose
files read as that kind (a 2.0 pack's `crew/`, a 1.x pack's bios, lineups and plain workflows), read-only.

Precedence is crew/store.py's own: a name in two folders goes to the file `store.find` picks (the project's, then
yours, then a starter, then a pack's).
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.where.rows import make, settle

KINDS = (("agent", "agents", "Agent folders"), ("workflow", "workflows", "Workflow folders"), ("map", "maps", "Map folders"))
GROUPS = tuple((group, title) for _kind, group, title in KINDS)
_SCOPE = {"project": "repo", "yours": "home", "starter": "shipped"}


def _stems(folder: Path) -> "tuple[list, list]":
    try:
        files = sorted(p for p in folder.glob("*.yaml") if p.is_file())
    except OSError:
        files = []
    return [p.stem for p in files], files


def kind_rows(kind: str, group: str, cwd: Path, state_dir: Path) -> list:
    from halo_harness.crew import store
    from halo_harness.project_gate import trusted
    folders = store.folders(kind, cwd=cwd, state_dir=state_dir)
    if not any(sc == "project" for _f, sc in folders):  # an untrusted project's folder is listed, not read
        folders.insert(0, (store.own_folder(kind, cwd=cwd, project=True), "project"))
    rows = []
    for rank, (folder, scope) in enumerate(folders, start=1):
        names, files = _stems(folder)
        unread = scope == "project" and names and not trusted(cwd)
        note = f"{len(names)} file(s)" + (", read-only (halo " + group + " copy <name> makes yours)" if scope == "starter" else "")
        rows.append(make(group, folder, _SCOPE[scope], cwd=cwd, sets=names, rank=rank, files=files, read=not unread,
                         note=note + (", not read: this folder is not trusted" if unread else "")))
    by_pack: dict = {}
    for name, body in store.pack_items(kind, cwd=cwd, state_dir=state_dir).items():
        path = Path(str(body.get("_path") or ""))
        by_pack.setdefault((name.split("--", 1)[0], str(path.parent)), []).append((name, path))
    for (pack_id, folder), items in sorted(by_pack.items()):
        names = sorted(n for n, _p in items)
        rows.append(make(group, Path(folder), "pack", cwd=cwd, sets=names, rank=len(rows) + 1,
                         files=sorted({str(p) for _n, p in items}),
                         note=f"{len(names)} file(s), read-only (halo {group} copy <name> makes yours), from pack {pack_id}"))

    def winner(name):
        found = store.find(kind, name, cwd=cwd, state_dir=state_dir)
        return str(found[0]) if found else None
    return settle(rows, winner, cwd=cwd)


def crew_rows(cwd: Path, state_dir: Path) -> list:
    out: list = []
    for kind, group, _title in KINDS:
        out += kind_rows(kind, group, cwd, state_dir)
    return out
