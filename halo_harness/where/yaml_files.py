"""halo_harness.where.yaml_files -- the YAML files for `halo config where`:
the active lineup and every lineup it extends, the three lineup and bio
folders (repo `.halo/`, `~/.halo/`, shipped), the team file, and the flows.

Precedence comes from the loaders: a name in two folders goes to the file
`find_team_template_path` / `find_agent_bio_path` / `find_flow` picks, the
team file to `find_team_file`, and a section the active lineup and its
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


def _folder_rows(kind: str, dirs, cwd: Path, winner_of, *, skip: str = "") -> list:
    rows = []
    for rank, (folder, source) in enumerate(dirs, start=1):
        names, files = _stems(folder, skip=skip)
        rows.append(make(kind, folder, scope_of(source), cwd=cwd, sets=names, rank=rank, files=files,
                         note=f"{len(names)} file(s)" + (", read-only (duplicate one to edit it)" if source == "template" else "")))
    return settle(rows, winner_of, cwd=cwd)


def lineup_folder_rows(cwd: Path, state_dir: Path) -> list:
    from halo_harness import teams_yaml as T

    def winner(name):
        found = T.find_team_template_path(name, cwd=cwd, state_dir=state_dir)
        return str(found[0]) if found else None
    return _folder_rows("lineups", T.team_search_dirs(cwd=cwd, state_dir=state_dir), cwd, winner, skip=".team.yaml")


def bio_folder_rows(cwd: Path, state_dir: Path) -> list:
    from halo_harness import agents_yaml as A

    def winner(name):
        found = A.find_agent_bio_path(name, cwd=cwd, state_dir=state_dir)
        return str(found[0]) if found else None
    return _folder_rows("bios", A.agent_search_dirs(cwd=cwd, state_dir=state_dir), cwd, winner)


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


def team_file_rows(cwd: Path, state_dir: Path) -> list:
    from halo_harness.team import spec as S
    from halo_harness.where.rows import display
    root = S.team_root(cwd)
    found = S.find_team_file(cwd, state_dir)
    rows = []
    for rank, (path, source) in enumerate(((S.repo_team_path(root), "repo"), (S.user_team_path(root, state_dir), "user")), 1):
        names, note = [], "no file here"
        if path.is_file():
            note = "the team for this repo (halo team)"
            try:
                names = [str(S.load_file(path).get("name") or root.name)]
            except ValueError as e:
                note = str(e)
        row = make("team", path, scope_of(source), cwd=cwd, sets=names, rank=rank, note=note)
        if found is not None and path.is_file() and path.resolve() != Path(found[0]).resolve():
            row["loses"] = [{"key": "team file", "to": display(found[0], cwd=cwd), "to_path": str(found[0])}]
            row["note"] = "not used: the repo's own .halo/team.yaml wins"
        rows.append(row)
    teams_dir = Path(state_dir) / "teams"
    for path in sorted(teams_dir.glob("*" + S.SUFFIX)) if teams_dir.is_dir() else []:
        if path.resolve() == S.user_team_path(root, state_dir).resolve():
            continue
        rows.append(make("team", path, "home", cwd=cwd, sets=[path.name[:-len(S.SUFFIX)]], rank=3,
                         note=f"for a repo folder named {path.name[:-len(S.SUFFIX)]}, not this one"))
    return rows


def flow_rows(cwd: Path, state_dir: Path) -> list:
    from halo_harness.flows import spec as F
    rows = []
    project = Path(cwd) / ".halo" / "flow.yaml"
    name = ""
    if project.is_file():
        try:
            name = str(F.load_flow(project).get("name") or "")
        except ValueError:
            name = ""
    rows.append(make("flows", project, "repo", cwd=cwd, sets=[name] if name else [], rank=1,
                     note="this repo's flow" if project.is_file() else "no file here"))
    names, files = _stems(F.flows_dir(state_dir), F.SUFFIX)
    rows.append(make("flows", F.flows_dir(state_dir), "home", cwd=cwd, sets=names, rank=2, files=files,
                     note=f"{len(names)} flow(s) (halo flow new)"))
    shipped, shipped_files = _stems(F.TEMPLATES_DIR, F.SUFFIX)
    rows.append(make("flows", F.TEMPLATES_DIR, "shipped", cwd=cwd, sets=shipped, rank=3, files=shipped_files,
                     note="templates; halo flow new copies one"))

    def winner(flow_name):
        hit = F.find_flow(flow_name, cwd=cwd, state_dir=state_dir)
        return str(hit) if hit else None
    return settle(rows, winner, cwd=cwd)


def yaml_rows(cwd: Path, state_dir: Path, active: str) -> list:
    return (active_lineup_rows(cwd, state_dir, active) + lineup_folder_rows(cwd, state_dir)
            + bio_folder_rows(cwd, state_dir) + team_file_rows(cwd, state_dir) + flow_rows(cwd, state_dir))
