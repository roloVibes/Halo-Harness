"""halo_harness.packs.remove -- `halo pack remove <id> [--keep-config]`
(Halo 3.2.0.0 R1).

Removes the pack's own files only: the ones its install or update wrote
(packs/journal.py) that still hold what was written. A file in the pack's
folder you changed or added stays, and so does everything of yours outside
it, each listed: your bios and lineups named `<id>--*`, your lineups that
name the pack's bios, the lineups' memory folders (`~/.halo/teams/<id>--*/`),
your settings under `packs.settings.<id>` and a `team:` that names the
pack's lineup. A pack found in place (never installed by Halo) has no files
of its own: nothing in its folder is removed. The state.json record goes;
`--keep-config` keeps it (disabled, with its grants), so installing the pack
again later starts with the same grants.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.packs import journal as J
from halo_harness.packs import names as N


def _rel(path: str, root: Path) -> str:
    """`path` relative to `root` (both in journal spelling, J.norm), or '' when it is not under it."""
    try:
        return Path(J.norm(path)).relative_to(Path(J.norm(root))).as_posix()
    except ValueError:
        return ""


def _named_by_pack(folder: Path, pack_id: str) -> "list[Path]":
    try:
        return sorted(p for p in folder.glob(f"{pack_id}{N.SEP}*.yaml") if p.is_file())
    except OSError:
        return []


def yours(pack_id: str, *, cwd=None, state_dir=None) -> "list[str]":
    """One line per thing of yours that concerns the pack and stays."""
    from halo_harness import agents_yaml as A
    from halo_harness import teams_yaml as T
    from halo_harness.packs.discover import user_packs_dir
    from halo_harness.where.rows import display
    out = []
    for folder in (A.project_agents_dir(cwd), A.user_agents_dir(state_dir)):
        out += [f"your bio {p.stem} stays ({display(p, cwd=cwd)})" for p in _named_by_pack(folder, pack_id)]
    for folder in (T.project_teams_dir(cwd), T.user_teams_dir(state_dir)):
        out += [f"your lineup {p.stem} stays ({display(p, cwd=cwd)})" for p in _named_by_pack(folder, pack_id)]
        for p in sorted(folder.glob("*.yaml")) if folder.is_dir() else []:
            raw = A._read_yaml_file(p) or {}
            used = [e.get("agent") for e in raw.get("agents") or [] if isinstance(e, dict)]
            used += [v for v in (raw.get("roles") or {}).values() if isinstance(v, str)] if isinstance(raw.get("roles"), dict) else []
            hits = sorted({u for u in used if isinstance(u, str) and N.unqualify(u)[0] == pack_id})
            if hits and not p.stem.startswith(pack_id + N.SEP):
                out.append(f"your lineup {p.stem} names {', '.join(hits)}; it stays (those names no longer resolve)")
    teams_state = user_packs_dir(state_dir).parent / "teams"  # <state>/teams/<lineup>/: memory, layouts
    for d in sorted(teams_state.glob(f"{pack_id}{N.SEP}*")) if teams_state.is_dir() else []:
        if d.is_dir():
            out.append(f"the memory and layout folder {display(d, cwd=cwd)} stays")
    from halo_harness.packs.settings import user_values
    if user_values(pack_id):
        out.append(f"your settings packs.settings.{pack_id} stay in ~/.halo/config.json")
    from halo_harness.theme import get_config_value
    team = get_config_value("team", default=None)
    if isinstance(team, str) and N.unqualify(team)[0] == pack_id:
        out.append(f"config.json team: {team} stays; it names the pack's lineup (halo teams use <name>)")
    return out


def remove(pack_id: str, *, keep_config: bool = False, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    from halo_harness.packs import state as S
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import changed
    rec = S.entry(pack_id, state_dir)
    pack = find(pack_id, cwd=cwd, state_dir=state_dir)
    if rec is None and pack is None:
        return False, [f"no pack {pack_id!r} is installed here (halo pack list)"]
    root = Path(pack.root if pack is not None else rec.get("root") or "")
    owned = {p: d for p, d in J.owned(pack_id, state_dir).items() if _rel(p, root)}
    op, lines, kept = J.Op("remove", pack_id, state_dir=state_dir), [], []
    try:
        for path, digest in sorted(owned.items()):
            if not Path(path).exists():
                continue
            if J.sha(path) == digest:
                op.delete(path)
            else:
                kept.append(f"kept {_rel(path, root)} in {root}: you changed it")
    except OSError as e:
        left = op.rollback()
        return False, [f"remove of {pack_id} stopped: {e}; every file is back as it was"] + left
    op.commit()
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.is_file() and J.norm(p) not in owned:
                kept.append(f"kept {p.relative_to(root).as_posix()} in {root}: Halo did not write it")
    J.prune_empty_dirs(root)
    if keep_config and rec is not None:
        S.put(pack_id, {"enabled": False, "removed": S.now()}, state_dir)
    elif rec is not None:
        S.drop(pack_id, state_dir)
    changed(state_dir)
    gone = "its folder is gone" if not root.exists() else f"{root} stays (it holds files that are not the pack's)"
    lines.append(f"removed {pack_id}: {len(op.done)} file(s) of its own deleted; {gone}")
    if not owned and pack is not None:
        lines.append(f"{pack_id} was found in place, not installed by Halo: none of its files are removed")
    lines += kept + yours(pack_id, cwd=cwd, state_dir=state_dir)
    if keep_config and rec is not None:
        lines.append(f"kept its record (grants: {', '.join(rec.get('granted') or []) or 'none'}) for a later install")
    return True, lines
