"""halo_harness.studio.flow_assets_api -- an upload into a flow run's
project assets/ (Halo 3.0.4.0 round R5; 3.1.0.0 R2 cut it out of
flow_api_io.py): `POST flow/runs/<id>/assets {name, data_base64}`; a run
that has not started yet also gets the file in its intake. Routed from
flow_api.py.
"""

from __future__ import annotations

from halo_harness.flows import state
from halo_harness.studio import flow_model as FM
from halo_harness.studio import flow_runs as live
from halo_harness.studio.flow_request import bad


def post_assets(req, run_dir):
    """Save an upload into the run's project assets/; a run not started yet also gets it in its intake."""
    from halo_harness.design import assets as A
    from halo_harness.design.store import Project
    if not str(req.body.get("name") or "").strip():
        return bad("an asset needs a name")
    flow = state.read_flow(run_dir)
    project = FM.project_of(run_dir, req.state_dir)
    if project is None:
        slug = str(flow.get("project") or flow.get("name") or "flow")
        project = Project.open(slug, state_dir=req.state_dir) or Project.create(slug, state_dir=req.state_dir)
    try:
        row = A.save_asset(project, str(req.body["name"]), req.body.get("data_base64"))
    except A.TooBig as e:
        return 413, {"error": str(e), "problems": [str(e)]}
    except ValueError as e:
        return bad(str(e))
    path = str(project.path / row["path"])
    pending = flow.get("status") == "pending" and live.live_id() != run_dir.name
    if pending:
        f = state.Flow(run_dir)
        with f.lock:
            intake = dict(f.data().get("intake") or {})
            intake["assets"] = list(intake.get("assets") or []) + [path]
            f.update(intake=intake)
    return 201, dict(row, rel=row["path"], path=path, project=project.slug, intake=pending)
