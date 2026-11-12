"""halo_harness.where.yaml_files -- the YAML files for `halo config where`:
the active lineup and every lineup it extends, the three lineup and bio
folders (repo `.halo/`, `~/.halo/`, shipped). (3.4.0.0 B: the team file left the core.)

Precedence comes from the loaders: a name in two folders goes to the file
`find_team_template_path` / `find_agent_bio_path` picks, and a section the active lineup and its
parent both set to `resolve_team_template`'s merge (the child's own value
when the merge kept it whole, "merged" otherwise).
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.where.rows import make, scope_of, settle, yaml_keys

_IDENTITY = ("name", "description", "version", "tags", "about", "extends")


def _stems(folder: Path, suffix: str = ".yaml", skip: str = "") -> "tuple[list, list]":
    try:
        files = sorted(p for p in folder.glob("*" + suffix) if p.is_file() and not (skip and p.name.endswith(skip)))
    except OSError:
        files = []
    return [p.name[:-len(suffix)] for p in files], files


def _folder_rows(kind: str, dirs, cwd: Path, winner_of, *, skip: str = "", project: "Path | None" = None) -> list:
    """3.4.1.2 (ENGINE-1): the repo folder is listed even when it is not read (an untrusted folder), and says so."""
    from halo_harness.packs.contribute import folder_names, read_only_source
    from halo_harness.project_gate import trusted
    dirs = list(dirs)
    if project is not None and not any(src == "project" for _d, src in dirs):
        dirs.insert(0, (project, "project"))
    rows = []
    for rank, (folder, source) in enumerate(dirs, start=1):
        names, files = _stems(folder, skip=skip)
        if source.startswith("pack:"):  # 3.2.0.0 R1: a pack's folder lists its `<id>--<name>` names
            names = sorted(folder_names(folder, source, skip=skip))
        unread = source == "project" and names and not trusted(cwd)
        rows.append(make(kind, folder, scope_of(source), cwd=cwd, sets=names, rank=rank, files=files,
                         note=f"{len(names)} file(s)" + (", read-only (duplicate one to edit it)" if read_only_source(source) else "")
                         + (f", from pack {source[len('pack:'):]}" if source.startswith("pack:") else "")
                         + (", not read: this folder is not trusted" if unread else "")))
    return settle(rows, winner_of, cwd=cwd)


def lineup_folder_rows(cwd: Path, state_dir: Path) -> list:
    from halo_harness import teams_yaml as T

    def winner(name):
        found = T.find_team_template_path(name, cwd=cwd, state_dir=state_dir)
        return str(found[0]) if found else None
    return _folder_rows("lineups", T.team_search_dirs(cwd=cwd, state_dir=state_dir), cwd, winner, skip=".team.yaml",
                        project=T.project_teams_dir(cwd))


def bio_folder_rows(cwd: Path, state_dir: Path) -> list:
    from halo_harness import agents_yaml as A

    def winner(name):
        found = A.find_agent_bio_path(name, cwd=cwd, state_dir=state_dir)
        return str(found[0]) if found else None
    return _folder_rows("bios", A.agent_search_dirs(cwd=cwd, state_dir=state_dir), cwd, winner,
                        project=A.project_agents_dir(cwd))


def active_lineup_rows(cwd: Path, state_dir: Path, active: str) -> list:
    """The active lineup's file, then each lineup it extends, child first."""
    from halo_harness import teams_yaml as T
    if not active:
        return []
    rows, raws, chain, name = [], [], [], active
    while name and name not in chain:
        chain.append(name)
        found = T.find_team_template_path(name, cwd=cwd, state_dir=state_dir)
        if found is None:
            where = "config.json team" if name == active else f"extends: in {chain[-2]}"
            rows.append(make("lineup", T.user_teams_dir(state_dir) / f"{name}.yaml", "home", cwd=cwd, sets=[name],
                             rank=len(chain), note=f"{where} names {name!r}, and no lineup file has that name"))
            raws.append({})
            break
        path, source = found
        keys, problem = yaml_keys(path)
        note = problem or ("the active lineup (config.json team)" if name == active else f"extended by {chain[-2]}")
        rows.append(make("lineup", path, scope_of(source), cwd=cwd, sets=[k for k in keys if k not in _IDENTITY],
                         rank=len(chain), note=note))
        raw = T.load_team_template_raw(name, cwd=cwd, state_dir=state_dir) or {}
        raws.append(raw)
        parent = raw.get("extends")
        name = parent.strip() if isinstance(parent, str) else ""
    resolved = T.resolve_team_template(active, cwd=cwd, state_dir=state_dir) or {}

    def winner(section):
        key = "agents" if section in ("agents", "roles") else section
        for r, raw in zip(rows, raws):
            if section in r["sets"] and raw.get(key) == resolved.get(key):
                return r["path"]
        return "merged (the nearer file's keys win)"
    return settle(rows, winner, cwd=cwd)


def yaml_rows(cwd: Path, state_dir: Path, active: str) -> list:
    return (active_lineup_rows(cwd, state_dir, active) + lineup_folder_rows(cwd, state_dir)
            + bio_folder_rows(cwd, state_dir))
