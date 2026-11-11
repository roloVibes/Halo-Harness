"""halo_harness.studio.work_api -- the shared unit view's route (Halo 3.1.2.0
R1, docs/WORK.md). studio/api.py dispatches `work/` here.

    GET work/<kind>/<run>    the units of one run as the shared rows (work/report.py)

`<kind>` is `orchestra` or `mission` (or a unit kind: lane, part;
3.4.0.0 B: `team` / `stage` left with the team file). `<run>` is a run id or a unique prefix, found the way
each section's own routes find it (orchestra_model, the missions folder). The answer is `{run, kind, units}`; 404 for an
unknown run, 405 for another method. The Studio panels keep their own
routes this round -- this one serves every kind through one shape.
"""

from __future__ import annotations

import re
from pathlib import Path

PATTERN = re.compile(r"^work/(?P<kind>orchestra|mission|lane|part)/(?P<run>[A-Za-z0-9_-]+)$")
_UNIT_RUN = {"lane": "orchestra", "part": "mission"}


def _orchestra(req, ref):
    from halo_harness.studio import orchestra_model as OM
    return OM.find_run(OM.repo_of(req.cwd), ref)


def _mission(req, ref):
    from halo_harness.packs import fleet_door  # 3.4.0.0 C: missions are the fleet pack's (none when it is off)
    S = fleet_door.module("fleet/mission_store.py", cwd=req.cwd, state_dir=req.state_dir)
    if S is None:
        return None
    folder = S.folder(req.state_dir, ref)
    return folder if (folder / "mission.json").is_file() else None


FINDERS = {"orchestra": _orchestra, "mission": _mission}
WHAT = {"orchestra": "Orchestra run", "mission": "mission"}


def dispatch_work(req):
    """The unit rows for `req`, or None when the path is not a work route."""
    m = PATTERN.match(req.path)
    if m is None:
        return None
    if req.method != "GET":
        return 405, {"error": "method not allowed"}
    kind = m.group("kind")
    run_kind = _UNIT_RUN.get(kind, kind)
    ref = m.group("run")
    run_dir = FINDERS[run_kind](req, ref)
    if run_dir is None or not Path(run_dir).is_dir():
        return 404, {"error": f"no {WHAT[run_kind]} {ref!r}"}
    from halo_harness.work.report import rows
    from halo_harness.work.store import UnitStore
    try:
        store = UnitStore(run_dir)
    except ValueError as e:
        return 404, {"error": str(e)}
    return 200, {"run": Path(run_dir).name, "kind": store.run_kind, "units": rows(run_dir)}
