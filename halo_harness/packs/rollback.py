"""halo_harness.packs.rollback -- `halo pack rollback <id>` (Halo 3.2.0.0 R7;
docs/PACKS.md "Updating and rolling back").

An update keeps the version it replaced as `<packs>/<id>.previous/` (one
back, until the next update; packs/update.py) and records it in state.json
(`previous: {version, op_id, requested}`). Rollback swaps it back:

1. A file of yours in the pack's folder that is not in `<id>.previous/` as
   it is now (one you changed or added since the update) is copied into it,
   so it stays.
2. Two renames: `<id>/` moves into a staging folder and `<id>.previous/`
   becomes `<id>/`; when the second fails the first is undone. The version
   rolled back from is then deleted (`halo pack update <id>` installs it again).
3. The journal gets the files' ownership back as it was before that update;
   the settings that update renamed move back (packs/migrate.py `undo`); the
   record gets the old version, keeps its grants, and loses `previous`.

A pack removed with `--keep-config` keeps its `<id>.previous/` with its
record: rollback installs that version again (disabled, with the grants).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from halo_harness.packs import journal as J


def _carry(root: Path, prev: Path, owned: dict) -> "list[str]":
    """Copy each file of yours in `root` (not the pack's per the journal) into `prev` when it differs there."""
    from halo_harness.packs.fetch import files_of
    from halo_harness.packs.update import _copy_file
    out = []
    for rel in files_of(root) if root.is_dir() else []:
        path = root / rel
        have = J.sha(path)
        if owned.get(J.norm(path)) == have or J.sha(prev / rel) == have:
            continue
        _copy_file(path, prev / rel)
        out.append(f"kept your copy of {rel.as_posix()}")
    return out


def _restore_ownership(pack_id: str, op_id: str, state_dir) -> None:
    """Journal rows that put `owned()` back to what it was before the update `op_id`."""
    import time
    now, then = J.owned(pack_id, state_dir), J.owned(pack_id, state_dir, before_op=op_id)
    for key in sorted(set(now) | set(then)):
        if now.get(key) != then.get(key):
            J._append({"ts": round(time.time(), 3), "op": "rollback", "op_id": f"rollback-{op_id}", "pack": pack_id,
                       "path": key, "existed": key in now, "before": now.get(key), "after": then.get(key)}, state_dir)


def rollback(pack_id: str, *, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    from halo_harness.packs import migrate as M
    from halo_harness.packs import state as S
    from halo_harness.packs.fetch import rmtree
    from halo_harness.packs.grants import changed, no_pack_line
    from halo_harness.packs.update import _rename, previous_dir
    rec = S.entry(pack_id, state_dir)
    if rec is None:
        return False, [no_pack_line(pack_id)]
    root = Path(str(rec.get("root") or ""))
    prev, info = previous_dir(root), rec.get("previous") if isinstance(rec.get("previous"), dict) else {}
    if not info or not prev.is_dir():
        return False, [f"{pack_id} has no earlier version to go back to: an update keeps the version it replaces as "
                       f"{pack_id}.previous until the next update"]
    old_v, op_id, cur_v = str(info.get("version") or "?"), str(info.get("op_id") or ""), str(rec.get("version") or "?")
    carried = _carry(root, prev, J.owned(pack_id, state_dir))
    scratch = root.parent / f".staging-{uuid.uuid4().hex[:8]}"
    away = scratch / pack_id
    try:
        if root.is_dir():
            scratch.mkdir(parents=True, exist_ok=True)
            _rename(root, away)
        try:
            _rename(prev, root)
        except OSError:
            if away.is_dir():
                _rename(away, root)
            raise
    except OSError as e:
        rmtree(scratch)
        return False, [f"rollback of {pack_id} stopped: {e}; {cur_v} stays as it is"]
    rmtree(scratch)
    _restore_ownership(pack_id, op_id, state_dir)
    moved = M.undo(pack_id, op_id, state_dir=state_dir)
    new_rec = {k: v for k, v in rec.items() if k not in ("previous", "removed")}
    new_rec["version"] = old_v
    S.replace(pack_id, new_rec, state_dir)
    changed(state_dir)
    back = "installed again, disabled" if rec.get("removed") else ("enabled" if rec.get("enabled") else "disabled")
    lines = [f"rolled back {pack_id} {cur_v} -> {old_v}: {prev.name} is {pack_id}/ again ({back}); "
             f"{cur_v} is gone (halo pack update {pack_id} brings it back)",
             f"grants kept: {', '.join(rec.get('granted') or []) or 'none'}"]
    return True, lines + moved + carried
