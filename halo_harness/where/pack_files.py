"""halo_harness.where.pack_files -- the packs group of `halo config where`
(Halo 3.2.0.0 R1): the repo's `.halo/packs/` and the home's `~/.halo/packs/`
(each lists its pack ids, the pack.yaml files and how many run), then
`~/.halo/packs/state.json` (the installed ids). A pack id in both folders
goes to the repo's (packs/discover.py's own order).
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.where.rows import make, scope_of, settle


def pack_rows(cwd: Path, state_dir: Path) -> list:
    from halo_harness.packs import discover as D
    from halo_harness.packs import state as S
    from halo_harness.packs.registry import snapshot
    snap = snapshot(cwd=cwd, state_dir=state_dir)
    rows = []
    for rank, (folder, scope) in enumerate(D.search_dirs(cwd=cwd, state_dir=state_dir), start=1):
        winners = [p for p in snap.packs if D.same_path(p.root.parent, folder)]
        shadowed = [(p.id, Path(s)) for p in snap.packs for s in p.shadowed if D.same_path(Path(s).parent, folder)]
        ids = sorted([p.id for p in winners] + [pid for pid, _s in shadowed])
        running = sum(1 for p in winners if p.id in snap.order)
        files = [f for f in [p.root / "pack.yaml" for p in winners] + [s / "pack.yaml" for _pid, s in shadowed]
                 if f.is_file()]
        rows.append(make("packs", folder, scope_of(scope), cwd=cwd, sets=ids, rank=rank, files=files,
                         note=f"{len(ids)} pack(s), {running} running (halo pack list)"))
    installed = sorted((S.load(state_dir).get("installed") or {}))
    rows.append(make("packs", S.state_path(state_dir), "home", cwd=cwd, sets=[], rank=len(rows) + 1,
                     note=f"installed: {', '.join(installed) if installed else 'none'}; enabled and granted "
                          "per pack (halo pack enable)"))

    def winner(pack_id):
        pack = snap.pack(pack_id)
        return str(pack.root / "pack.yaml") if pack is not None else None
    return settle(rows, winner, cwd=cwd)
