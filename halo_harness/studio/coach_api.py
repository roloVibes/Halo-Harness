"""halo_harness.studio.coach_api -- the post-run coach's Studio routes (Halo
3.0.9.0 round R3; orchestra/coach.py). studio/api.py's `dispatch` sends
these four paths here before the section dispatchers:

    GET orchestra/<run>/coach        an Orchestra run of Studio's repo
    GET flow/runs/<id>/coach         a flow run
    GET fleet/missions/<id>/coach    a mission in this harness's missions folder
    GET team/coach?run=              a team run of Studio's repo (the latest when run is empty)

Each answers the coach's result `{run, kind, suggestions, evidence, model,
computed, source_mtime, cached}`, computed once and kept in
`<run>/coach.json` until a run file it reads is newer (coach.cached). 404
for an unknown run, 405 for another method.
"""

from __future__ import annotations

import re
from pathlib import Path

_RUN = r"[A-Za-z0-9_-]+"
PATTERNS = (("orchestra", rf"^orchestra/(?P<run>{_RUN})/coach$"), ("flow", rf"^flow/runs/(?P<run>{_RUN})/coach$"),
            ("mission", r"^fleet/missions/(?P<run>m-\d{8}-[0-9a-f]{4})/coach$"), ("team", r"^team/coach$"))


def _orchestra_dir(req, ref):
    from halo_harness.studio import orchestra_model as OM
    return OM.find_run(OM.repo_of(req.cwd), ref)


def _flow_dir(req, ref):
    from halo_harness.studio import flow_model as FM
    return FM.run_dir_of(req.state_dir, ref)


def _mission_dir(req, ref):
    from halo_harness.fleet import mission_store as S
    folder = S.folder(req.state_dir, ref)
    return folder if (folder / "mission.json").is_file() else None


def _team_dir(req, ref):
    from halo_harness.team import board as BD
    from halo_harness.team.spec import team_root
    return BD.find_run(team_root(req.cwd), ref or None)


FINDERS = {"orchestra": _orchestra_dir, "flow": _flow_dir, "mission": _mission_dir, "team": _team_dir}
WHAT = {"orchestra": "Orchestra run", "flow": "flow run", "mission": "mission", "team": "team run"}


def match(path: str):
    for kind, pattern in PATTERNS:
        m = re.match(pattern, path)
        if m:
            return kind, m.groupdict().get("run")
    return None


def dispatch_coach(req):
    """The coach's answer for `req`, or None when the path is not a coach route."""
    hit = match(req.path)
    if hit is None:
        return None
    if req.method != "GET":
        return 405, {"error": "method not allowed"}
    kind, ref = hit
    if kind == "team":
        ref = str(req.query.get("run") or "")
    run_dir = FINDERS[kind](req, ref)
    if run_dir is None or not Path(run_dir).is_dir():
        return 404, {"error": f"no {WHAT[kind]} {ref!r}" if ref else f"no {WHAT[kind]} yet"}
    from halo_harness.orchestra.coach import cached
    try:
        return 200, cached(run_dir, state_dir=req.state_dir)
    except ValueError as e:
        return 404, {"error": str(e)}
