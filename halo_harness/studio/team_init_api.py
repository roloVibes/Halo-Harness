"""halo_harness.studio.team_init_api -- `POST /api/team/init` (Halo 3.0.8.0
round R2): the Team tab's Start view button "Make my first team". It writes
the repo's team file from the shipped template (and a starter brief) through
the same code as `halo team init` (team/cli.py `init_files`), in the repo
that holds Studio's folder.

    POST team/init   200 {ok, written: [paths], path}
                     409 {error, path} when the repo already has a team file
"""

from __future__ import annotations

from halo_harness.team import spec as S


def post_init(req):
    from halo_harness.team.cli import init_files
    root = S.team_root(req.cwd)
    path = S.repo_team_path(root)
    if path.exists():
        return 409, {"error": f"{path} exists: open it, or edit it in your editor", "path": str(path)}
    try:
        written = init_files(root)
    except OSError as e:
        return 500, {"error": f"could not write {path}: {e}", "path": str(path)}
    return 200, {"ok": True, "written": written, "path": str(path)}
