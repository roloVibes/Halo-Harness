"""halo_harness.studio.flow_api_io -- the body parsing and the assets upload
of Studio's Flow routes (Halo 3.0.4.0 round R5). Routed from flow_api.py.
"""

from __future__ import annotations

from halo_harness.flows import state
from halo_harness.studio import flow_model as FM
from halo_harness.studio import flow_runs as live


def bad(lines, status: int = 422):
    lines = [lines] if isinstance(lines, str) else list(lines)
    return status, {"error": lines[0] if lines else "invalid", "problems": lines}


def intake_of(body):
    """(intake, None) or (None, error): the intake mapping, `budget_usd` as a number."""
    intake = body.get("intake") if isinstance(body.get("intake"), dict) else {}
    intake = {str(k): v for k, v in intake.items() if v is not None}
    budget = intake.get("budget_usd")
    if isinstance(budget, str) and budget.strip():
        try:
            intake["budget_usd"] = float(budget)
        except ValueError:
            return None, bad(f"intake.budget_usd is a number, got {budget!r}")
    elif budget in ("", None):
        intake.pop("budget_usd", None)
    return intake, None


def overrides_of(raw):
    """`{step: {key: value}}` or `{"step.key": value}` -> ({step: {key: value}}, None) or (None, error)."""
    if raw in (None, ""):
        return {}, None
    if not isinstance(raw, dict):
        return None, bad("set is {\"<step>.<key>\": value} or {\"<step>\": {\"<key>\": value}}")
    out: dict = {}
    for key, val in raw.items():
        if isinstance(val, dict):
            out.setdefault(str(key), {}).update(val)
            continue
        step, dot, field = str(key).partition(".")
        if not dot or not step or not field:
            return None, bad(f"set takes <step>.<key>, got {key!r}")
        out.setdefault(step, {})[field] = val
    return out, None


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
