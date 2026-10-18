"""halo_harness.studio.flow_api_edit -- `PUT flow/templates/<name>`, the
one write route for a flow file (Halo 3.0.9.0 round R2: the Flow graph's
reorder-by-drag of independent steps):

    PUT flow/templates/<name> {yaml}     the whole file
    PUT flow/templates/<name> {order}    the same file with its steps in this order (flows/graph.py `reorder`)
        -> 200 {ok, name, source, path, steps, warnings} | 422 {error, problems} | 404

The file written is the project's `.halo/flow.yaml` or the user's
`~/.halo/flows/<name>.flow.yaml` when the flow is one of those; a shipped
template is copied to the user's folder first (as `halo flow new` does), so
Halo's own files never change. `flows.spec.validate_flow` checks the new
text: a problem the edit brings in (a step that now reads a later one, a
bad YAML) is a 422 and nothing is written; the problems the file already had
(an org this home does not have) do not block an order change.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.flows import spec as fspec
from halo_harness.studio import flow_model as FM


def _problems(text: str, cwd, state_dir) -> "tuple[dict | None, list]":
    import yaml
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        return None, [f"the flow is not valid YAML: {e}"]
    if not isinstance(data, dict):
        return None, ["a flow file is a mapping with name, steps, ..."]
    return data, fspec.errors(fspec.validate_flow(data, cwd=cwd, state_dir=state_dir))


def put_template(req):
    name = req.params["name"]
    source_path = FM.find_flow_file(name, req.cwd, req.state_dir)
    if source_path is None:
        return 404, {"error": f"no flow {name!r} (halo flow list names them)"}
    shipped = fspec.template_path(name)
    target = fspec.flows_dir(req.state_dir) / f"{name}{fspec.SUFFIX}" if source_path == shipped else Path(source_path)
    before = source_path.read_text(encoding="utf-8")
    body = req.body if isinstance(req.body, dict) else {}
    if isinstance(body.get("order"), list):
        from halo_harness.flows.graph import reorder
        try:
            text = reorder(before, body["order"])
        except (ValueError, TypeError) as e:
            return 422, {"error": str(e), "problems": [str(e)]}
    elif isinstance(body.get("yaml"), str) and body["yaml"].strip():
        text = body["yaml"]
    else:
        return 422, {"error": 'send {"yaml": "<the flow file>"} or {"order": [step ids]}', "problems": []}
    data, after = _problems(text, req.cwd, req.state_dir)
    _old, had = _problems(before, req.cwd, req.state_dir)
    new = [p for p in after if p not in had]
    if data is not None and str(data.get("name") or "") != str(_old.get("name") if _old else name):
        new.append(f"name: keep the flow's name ({name}); save it under another name with halo flow new")
    if new:
        return 422, {"error": new[0], "problems": new}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="")
    from halo_harness.flows.graph import graph_rows
    source = "user" if target != Path(req.cwd) / ".halo" / "flow.yaml" else "project"
    warnings = [line for line in fspec.validate_flow(data, cwd=req.cwd, state_dir=req.state_dir) if line not in after]
    return 200, {"ok": True, "name": name, "source": source, "path": str(target), "steps": graph_rows(data),
                 "warnings": warnings}


ROUTES = [("PUT", r"^flow/templates/(?P<name>[A-Za-z0-9][A-Za-z0-9_.-]*)$", put_template)]
