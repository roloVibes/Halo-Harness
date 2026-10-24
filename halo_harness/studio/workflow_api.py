"""halo_harness.studio.workflow_api -- a workflow's typed artifacts for
Studio's viewer (Halo 3.2.0.0 R5; docs/WORKFLOWS.md "Artifacts").

    GET pack/<id>/artifact/<schema>        an artifact panel's `latest` source: the newest run of this repo whose
                                           report holds an artifact of that schema (packs_studio_api.py routes it)
    GET orchestra/<run>/artifact/<name>    one artifact of a run, for Orchestra's run view (orchestra_api.py)

Both answer `{name, schema, view, columns, data, run, path, ok, problems}`:
`view` is the schema's `x-halo-view` (table | markdown | keyvalue, default
keyvalue), `columns` a table's (the properties of the rows' schema, in
order), `data` the document (null with `why` when there is none yet).
"""

from __future__ import annotations

from pathlib import Path


def columns(schema) -> "list[str]":
    """The rows' columns of a table view: the items of the first array-of-objects property (or of the list)."""
    if not isinstance(schema, dict):
        return []
    if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        return list((schema["items"].get("properties") or {}).keys())
    for sub in (schema.get("properties") or {}).values():
        if isinstance(sub, dict) and sub.get("type") == "array" and isinstance(sub.get("items"), dict):
            return list((sub["items"].get("properties") or {}).keys())
    return []


def _schema(pack_id: str, name: str, cwd):
    from halo_harness.packs.discover import find
    from halo_harness.packs.typed import artifact_schema
    pack = find(str(pack_id or ""), cwd=cwd)
    return artifact_schema(pack.root, name) if pack is not None and name else None


def payload(run_dir, row: dict, cwd) -> dict:
    from halo_harness.orchestra import jsonl
    from halo_harness.orchestra.goal import Goal
    from halo_harness.packs.typed import view_of
    goal = Goal.from_dict(jsonl.read_json(Path(run_dir) / "goal.json", {}) or {})
    schema = _schema((goal.workflow or {}).get("pack"), str(row.get("schema") or ""), cwd)
    data = jsonl.read_json(Path(run_dir) / row["path"], None) if row.get("path") else None
    return {"name": row.get("name"), "schema": row.get("schema") or "", "view": view_of(schema) if schema else "keyvalue",
            "columns": columns(schema), "data": data, "run": Path(run_dir).name, "path": row.get("path") or "",
            "ok": row.get("ok", True), "problems": list(row.get("problems") or []), "state": row.get("state") or "",
            "workflow": (goal.workflow or {}).get("ref") or ""}


def pack_artifact(req, pack, schema_name: str):
    from halo_harness.orchestra.report import load_report
    from halo_harness.studio.orchestra_model import repo_of
    from halo_harness.orchestra.goal import list_runs
    repo = repo_of(req.cwd)
    for run_dir in reversed(list_runs(repo)):
        report = load_report(run_dir) or {}
        rows = [a for a in report.get("artifacts") or [] if a.get("schema") == schema_name and a.get("path")]
        if rows and report.get("status") == "finished":
            return 200, payload(run_dir, rows[-1], req.cwd)
    from halo_harness.packs.typed import artifact_schema, view_of
    schema = artifact_schema(pack.root, schema_name)
    return 200, {"name": "", "schema": schema_name, "view": view_of(schema) if schema else "keyvalue", "columns": columns(schema),
                 "data": None, "run": "", "path": "", "ok": True, "problems": [],
                 "why": f"no finished run in this repo wrote a {schema_name} yet (halo workflow run ... writes one)"}


def run_artifact(req):
    from halo_harness.orchestra.report import load_report
    from halo_harness.studio import orchestra_model as OM
    run_dir = OM.find_run(OM.repo_of(req.cwd), req.params["run"])
    if run_dir is None:
        return 404, {"error": f"no Orchestra run {req.params['run']!r} in this repo"}
    rows = [a for a in (load_report(run_dir) or {}).get("artifacts") or [] if a.get("name") == req.params["name"]]
    if not rows:
        return 404, {"error": f"run {run_dir.name} has no artifact {req.params['name']!r}"}
    return 200, payload(run_dir, next((r for r in rows if r.get("path")), rows[0]), req.cwd)
