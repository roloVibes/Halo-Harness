"""halo_harness.packs.update -- `halo pack update <id> [--dry-run]` (Halo
3.2.0.0 R1; staged, swapped and kept one back since R7; docs/PACKS.md
"Updating and rolling back").

1. The checks install makes, on the recorded source: the new manifest, the
   API and Halo ranges, the same id. A new version that fails one is refused
   with its lines; nothing is touched.
2. The plan, said first: the `migrations` notes between the two versions
   (packs/migrate.py), the files that change (one line each), the settings
   it renames. `--dry-run` stops here; in a terminal `halo pack update` shows
   these lines and asks before step 3 (`confirm`, 3.2.1.0 R4; packs/cli.py).
3. The new folder is staged beside the pack (`<packs>/.staging-<hex>/<id>/`):
   the new version's files, and every file of yours in the pack's folder (one
   you changed or added) carried over. A copy error removes the staging
   folder: the pack stays as it was.
4. The swap, two renames: `<id>/` becomes `<id>.previous/` (replacing the one
   kept by the update before) and the staged folder becomes `<id>/`. When the
   second fails the first is undone.
5. The journal records the new hashes (the pack owns the new version's
   files), the settings renames are made and journaled, and state.json gets
   the new version and `previous: {version, op_id, requested}` for
   `halo pack rollback` (packs/rollback.py).
"""

from __future__ import annotations

import os
import shutil
import time
import uuid
from pathlib import Path

from halo_harness.packs import journal as J
from halo_harness.packs import migrate as M

PREVIOUS = ".previous"


def previous_dir(root) -> Path:
    """`<packs>/<id>.previous/`: the version before the last update."""
    root = Path(root)
    return root.with_name(root.name + PREVIOUS)


def _copy_file(src: Path, dest: Path) -> None:  # one seam for the tests' copy error
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _rename(a: Path, b: Path) -> None:  # one seam for the tests' swap error
    os.rename(a, b)


def plan(root: Path, src: Path, owned: dict) -> dict:
    """What goes into the staged folder and what the journal records:
    {"stage": {rel: from}, "rows": [(path, before, after)], "kept": [line], "changed": n}."""
    from halo_harness.packs.fetch import files_of
    stage, rows, kept = {}, [], []
    incoming = {J.norm(root / rel): rel for rel in files_of(src)}
    for key, rel in incoming.items():
        target, new_sha = root / rel, J.sha(src / rel)
        have = J.sha(target)
        if have is None or owned.get(key) == have or have == new_sha:
            stage[rel] = src / rel
            if have != new_sha and (have is None or owned.get(key) == have):
                rows.append((target, have, new_sha))
        else:
            stage[rel] = target
            kept.append(f"kept your copy of {rel.as_posix()} (the new version's is not written)")
    for rel in files_of(root) if root.is_dir() else []:
        key = J.norm(root / rel)
        if key in incoming:
            continue
        have = J.sha(root / rel)
        if key in owned and owned[key] == have:
            rows.append((root / rel, have, None))  # the new version drops it
        else:
            stage[rel] = root / rel
            if key in owned:
                kept.append(f"kept {rel.as_posix()}: the new version drops it and you changed it")
    return {"stage": stage, "rows": rows, "kept": kept, "changed": len(rows)}


def file_lines(root: Path, rows, limit: int = 20) -> "list[str]":
    """The files an update changes, one line each (3.2.1.0 R4): `  <rel> (changed|new|dropped)`."""
    out = []
    for path, before, after in sorted(rows, key=lambda r: Path(r[0]).relative_to(root).as_posix()):
        what = "new" if before is None else "dropped" if after is None else "changed"
        out.append(f"  {Path(path).relative_to(root).as_posix()} ({what})")
    return out[:limit] + ([f"  ... and {len(out) - limit} more file(s)"] if len(out) > limit else [])


def _stage(p: dict, staged: Path) -> None:
    for rel, origin in sorted(p["stage"].items()):
        _copy_file(origin, staged / rel)


def _swap(root: Path, staged: Path, scratch: Path) -> None:
    """`root` -> `<id>.previous`, `staged` -> `root`; the old `.previous` waits in `scratch` until it worked."""
    prev, old_prev = previous_dir(root), scratch / "previous"
    if prev.exists():
        _rename(prev, old_prev)
    try:
        _rename(root, prev)
    except OSError:
        if old_prev.exists():
            _rename(old_prev, prev)
        raise
    try:
        _rename(staged, root)
    except OSError:
        _rename(prev, root)
        if old_prev.exists():
            _rename(old_prev, prev)
        raise


def _record(pack_id: str, op_id: str, p: dict, state_dir, old: str, new: str) -> None:
    for path, before, after in p["rows"]:
        J._append({"ts": round(time.time(), 3), "op": "update", "op_id": op_id, "pack": pack_id, "path": str(path),
                   "existed": before is not None, "before": before, "after": after}, state_dir)
    J._append({"ts": round(time.time(), 3), "op": "update", "op_id": op_id, "pack": pack_id,
               "swap": f"{pack_id}{PREVIOUS}", "from": old, "to": new}, state_dir)


def _source_line(pack_id: str, source: str) -> str:
    from halo_harness.packs.names import is_url
    if not source or source.endswith("(found in place)"):
        return f"{pack_id} was found in place, not installed from a source; there is nothing to update from"
    if not is_url(source) and not Path(source).expanduser().is_dir():
        return (f"{pack_id}'s source {source} is not there any more; nothing is changed "
                f"(install it from its new place, or see halo pack sources)")
    return ""


def update(pack_id: str, *, dry_run: bool = False, cwd=None, state_dir=None, confirm=None) -> "tuple[bool, list[str]]":
    """`confirm(lines) -> bool` (3.2.1.0 R4, the CLI in a terminal): called with the dry run's lines before the
    swap, from the same fetched source; False leaves the pack as it is (`<id> <version> stays as it is`)."""
    from halo_harness.packs import manifest as MF
    from halo_harness.packs import state as S
    from halo_harness.packs.discover import find
    from halo_harness.packs.fetch import fetched, rmtree
    from halo_harness.packs.install import _checks
    rec = S.entry(pack_id, state_dir)
    current = find(pack_id, cwd=cwd, state_dir=state_dir)
    if rec is None or current is None or rec.get("removed"):
        return False, [f"no pack {pack_id!r} is installed here (halo pack list)"]
    source = str(rec.get("source") or "")
    gone = _source_line(pack_id, source)
    if gone:
        return False, [gone]
    with fetched(source, state_dir=state_dir) as (src, problem):
        if src is None:
            return False, [problem]
        new, problems = _checks(src)
        if not problems and new.id != pack_id:
            problems = [f"{source} now holds pack {new.id!r}, not {pack_id!r}; nothing is changed"]
        if problems:
            return False, problems + [f"{pack_id} {current.version} stays as it is"]
        root, old_v, new_v = Path(current.root), current.version, new.version
        entries = M.between(new.manifest, old_v, new_v)
        said = M.note_lines(pack_id, entries) or [f"no migration notes between {old_v} and {new_v}"]
        p = plan(root, src, J.owned(pack_id, state_dir))
        if p["changed"] == 0 and old_v == new_v:
            return True, [f"{pack_id} {old_v} is up to date: its source holds the same files (0 file(s) changed)"] + said
        look = (said + [f"would update {pack_id} {old_v} -> {new_v} ({p['changed']} file(s) changed; "
                        f"{old_v} kept as {pack_id}{PREVIOUS})"] + file_lines(root, p["rows"])
                + M.plan_lines(pack_id, entries) + p["kept"])
        if dry_run:
            return True, look + ["dry run: nothing is changed (halo pack update " + pack_id + " makes these changes)"]
        if confirm is not None and not confirm(look):
            return False, [f"{pack_id} {old_v} stays as it is"]
        op_id = f"update-{uuid.uuid4().hex[:8]}"
        scratch = root.parent / f".staging-{uuid.uuid4().hex[:8]}"
        J._append({"ts": round(time.time(), 3), "op": "update", "op_id": op_id, "pack": pack_id, "mark": "start",
                   "from": old_v, "to": new_v}, state_dir)
        try:
            _stage(p, scratch / pack_id)
            _swap(root, scratch / pack_id, scratch)
        except OSError as e:
            rmtree(scratch)
            return False, [f"update of {pack_id} stopped: {e}; {old_v} stays as it was (nothing was replaced)"] + said
        rmtree(scratch)
    _record(pack_id, op_id, p, state_dir, old_v, new_v)
    moved = M.apply(pack_id, entries, op_id=op_id, state_dir=state_dir)
    S.put(pack_id, {"version": new_v, "previous": {"version": old_v, "op_id": op_id, "at": S.now(),
                                                   "requested": MF.requested(current.manifest)}}, state_dir)
    from halo_harness.packs.grants import changed
    changed(state_dir)  # what an enabled pack offers may have changed: Fleet's catalog gathers afresh
    lines = said + [f"updated {pack_id} {old_v} -> {new_v} ({p['changed']} file(s) changed); {old_v} is kept as "
                    f"{pack_id}{PREVIOUS} (halo pack rollback {pack_id})"] + moved + p["kept"]
    asked = [g for g in MF.requested(new.manifest) if g not in set(rec.get("granted") or [])
             and g not in set(MF.requested(current.manifest))]
    if asked and rec.get("enabled"):
        lines.append(f"{new_v} also requests {', '.join(asked)}, not granted: halo pack grant {pack_id} {' '.join(asked)}")
    return True, lines
