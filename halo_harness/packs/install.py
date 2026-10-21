"""halo_harness.packs.install -- `halo pack install` and `halo pack update`
(Halo 3.2.0.0 R1).

Install: fetch the source (a folder, or a git url cloned fresh), read and
validate its pack.yaml, check the pack against this Halo's extension API and
version, leave a folder already at `<packs>/<id>/` as it is -- all before writing
anything -- then copy every file through the journal (packs/journal.py) and
record the pack in state.json, disabled. A failed copy rolls every file back.

Update: the same checks on the recorded source, then file by file: a file
the pack wrote and you have not changed is replaced (or removed when the new
version drops it); a file you changed or added stays and is listed. The
migration notes between the two versions are printed.

Both answer `(ok, lines)`; nothing raises for a problem the user can fix.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.packs import journal as J
from halo_harness.packs import semver as V
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
    previous = S.entry(pack.id, state_dir) or {}
    kept = list(previous.get("granted") or []) if previous.get("removed") else []
    S.replace(pack.id, {"version": pack.version, "source": str(source), "installed": S.now(), "enabled": False,
                        "granted": kept, "scope": "project" if project else "user", "root": str(dest)}, state_dir)
    installed = read_pack(dest, "project" if project else "user")
    lines = [f"installed {pack.id} {pack.version} at {dest} (disabled)",
             f"it offers: {summary(offers(installed))}"]
    asked = installed.manifest.get("permissions") or []
    lines.append(f"it requests: {', '.join(asked) if asked else 'no permissions'}")
    if kept:
        lines.append(f"grants kept from before (remove --keep-config): {', '.join(kept)}")
    grant = " --grant ".join([""] + list(asked)).strip() if asked else ""
    lines.append(f"enable it: halo pack enable {pack.id}" + (f" {grant}" if grant else ""))
    return True, lines


def migration_lines(manifest: dict, old: str, new: str) -> "list[str]":
    """The notes of every migration between the installed version `old` and the new version `new`."""
    out = []
    for m in manifest.get("migrations") or []:
        if not isinstance(m, dict) or V.release(m.get("from")) is None or V.release(m.get("to")) is None:
            continue
        try:
            after_old = V.release(old) is None or V.compare(m["from"], old) >= 0
            upto_new = V.compare(m["to"], new) <= 0
        except ValueError:
            continue
        if after_old and upto_new:
            out.append(f"migration {m['from']} -> {m['to']}: {m.get('note', '')}")
    return out


def update(pack_id: str, *, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    from halo_harness.packs import state as S
    from halo_harness.packs.discover import find
    rec = S.entry(pack_id, state_dir)
    current = find(pack_id, cwd=cwd, state_dir=state_dir)
    if rec is None or current is None:
        return False, [f"no pack {pack_id!r} is installed here (halo pack list)"]
    source = str(rec.get("source") or "")
    if not source or source.endswith("(found in place)"):
        return False, [f"{pack_id} was found in place, not installed from a source; there is nothing to update from"]
    with fetched(source, state_dir=state_dir) as (src, problem):
        if src is None:
            return False, [problem]
        new, problems = _checks(src)
        if not problems and new.id != pack_id:
            problems = [f"{source} now holds pack {new.id!r}, not {pack_id!r}; nothing is changed"]
        if problems:
            return False, problems
        root, owned = current.root, J.owned(pack_id, state_dir)
        incoming = {J.norm(root / rel): rel for rel in files_of(src)}
        op, kept = J.Op("update", pack_id, state_dir=state_dir), []
        try:
            for key, rel in incoming.items():
                target = root / rel
                data, have = (src / rel).read_bytes(), J.sha(target)
                if have is None or (owned.get(key) == have and have != J.sha_bytes(data)):
                    op.write(target, data, mode=(src / rel).stat().st_mode & 0o777)
                elif have != owned.get(key) and have != J.sha_bytes(data):
                    kept.append(f"kept your copy of {rel.as_posix()} (the new version's is not written)")
            for key, digest in owned.items():
                if key not in incoming and Path(key).exists():
                    if J.sha(key) == digest:
                        op.delete(key)
                    else:
                        kept.append(f"kept {Path(key).name}: the new version drops it and you changed it")
        except OSError as e:
            left = op.rollback()
            return False, [f"update of {pack_id} stopped: {e}; every file is back as it was"] + left
        op.commit()
    J.prune_empty_dirs(root, keep_root=True)
    S.put(pack_id, {"version": new.version}, state_dir)
    from halo_harness.packs.grants import changed
    changed(state_dir)  # what an enabled pack offers may have changed: Fleet's catalog gathers afresh
    lines = [f"updated {pack_id} {current.version} -> {new.version} ({len(op.done)} file(s) changed)"]
    lines += migration_lines(new.manifest, current.version, new.version) or ["no migration notes"]
    lines += kept
    asked = set(new.manifest.get("permissions") or []) - set(rec.get("granted") or [])
    if asked and rec.get("enabled"):
        lines.append(f"it now also requests: {', '.join(sorted(asked))} (halo pack enable {pack_id} --grant ...)")
    return True, lines
