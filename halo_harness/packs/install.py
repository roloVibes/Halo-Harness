"""halo_harness.packs.install -- `halo pack install` and `halo pack update`
(Halo 3.2.0.0 R1).

Install: fetch the source (a folder, or a git url cloned fresh), read and
validate its pack.yaml, check the pack against this Halo's extension API and
version, leave a folder already at `<packs>/<id>/` as it is -- all before writing
anything -- then copy every file through the journal (packs/journal.py) and
record the pack in state.json, disabled. A failed copy rolls every file back.

Update (packs/update.py since 3.2.0.0 R7): the same checks on the recorded
source, the migration notes said first, then the new version staged beside
the pack and swapped in by two renames, the old one kept as `<id>.previous/`
for `halo pack rollback`: a file the pack wrote and you have not changed is
replaced (or dropped when the new version drops it); a file you changed or
added is carried over and listed.

Both answer `(ok, lines)`; nothing raises for a problem the user can fix.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.packs import journal as J
from halo_harness.packs.discover import project_packs_dir, read_pack, user_packs_dir
from halo_harness.packs.fetch import fetched, files_of


def _checks(src: Path) -> "tuple[object, list[str]]":
    from halo_harness.packs.resolve import compat_lines
    pack = read_pack(src, "source", folder_is_id=False)
    if pack.problems:
        return pack, [f"{pack.id}: pack.yaml: {line}" for line in pack.problems]
    return pack, compat_lines(pack)


def _copy(op: "J.Op", src: Path, dest: Path, rels) -> None:
    for rel in rels:
        source = src / rel
        op.write(dest / rel, source.read_bytes(), mode=source.stat().st_mode & 0o777)


def install(source: str, *, project: bool = False, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    from halo_harness.packs import state as S
    from halo_harness.packs.fetch import source_for
    from halo_harness.packs.offers import offers, summary
    source = source_for(source)  # a bare id: found through config packs.sources
    with fetched(source, state_dir=state_dir) as (src, problem):
        if src is None:
            return False, [problem]
        pack, problems = _checks(src)
        if problems:
            return False, problems
        base = project_packs_dir(cwd) if project else user_packs_dir(state_dir)
        dest = base / pack.id
        if dest.exists():
            rec = S.entry(pack.id, state_dir)
            if rec and not rec.get("removed"):
                return False, [f"{pack.id} is already installed at {dest} (halo pack update {pack.id})"]
            return False, [f"{dest} is already there and Halo did not put it there; it is left as it is "
                           "(move it away, or enable it in place: halo pack enable " + pack.id + ")"]
        op = J.Op("install", pack.id, state_dir=state_dir)
        try:
            _copy(op, src, dest, files_of(src))
        except OSError as e:
            left = op.rollback()
            J.prune_empty_dirs(dest)
            return False, [f"install of {pack.id} stopped: {e}; every file it wrote is removed again"] + left
        op.commit()
    from halo_harness.packs.update import previous_dir  # 3.2.0.0 R7: a fresh install has no earlier version to go back to
    stale = previous_dir(dest)
    dropped = stale.is_dir()
    if dropped:
        from halo_harness.packs.fetch import rmtree
        rmtree(stale)
    previous = S.entry(pack.id, state_dir) or {}
    kept = list(previous.get("granted") or []) if previous.get("removed") else []
    S.replace(pack.id, {"version": pack.version, "source": str(source), "installed": S.now(), "enabled": False,
                        "granted": kept, "scope": "project" if project else "user", "root": str(dest)}, state_dir)
    installed = read_pack(dest, "project" if project else "user")
    from halo_harness.packs.grants import notify_studio  # 3.2.0.0 R3: Studio's pack list (it runs disabled)
    notify_studio("installed")
    lines = [f"installed {pack.id} {pack.version} at {dest} (disabled)",
             f"it offers: {summary(offers(installed))}"]
    asked = installed.manifest.get("permissions") or []
    lines.append(f"it requests: {', '.join(asked) if asked else 'no permissions'}")
    if kept:
        lines.append(f"grants kept from before (remove --keep-config): {', '.join(kept)}")
    if dropped:
        lines.append(f"removed {stale.name}: a fresh install starts with no earlier version to roll back to")
    grant = " --grant ".join([""] + list(asked)).strip() if asked else ""
    lines.append(f"enable it: halo pack enable {pack.id}" + (f" {grant}" if grant else ""))
    return True, lines


def update(pack_id: str, *, dry_run: bool = False, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """`halo pack update` (3.2.0.0 R7: staged and swapped, the old version kept as `<id>.previous`; packs/update.py)."""
    from halo_harness.packs.update import update as _update
    return _update(pack_id, dry_run=dry_run, cwd=cwd, state_dir=state_dir)
