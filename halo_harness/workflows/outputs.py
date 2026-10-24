"""halo_harness.workflows.outputs -- a workflow run's outputs and its part
of report.json (Halo 3.2.0.0 R5; orchestra/report.py `write_report` adds
`part(...)` for a goal with a `workflow`).

On completion (`status: finished`) each output's files are copied from the
lane that gave them to `<run>/artifacts/<name>/` (the artifact JSON, and a
folder `lanes/<n>/artifacts/<name>/` beside it when the stage saved one), so
the run's results live in one place after its lanes are gone. The report:

    "workflow": {"ref", "version", "inputs", "stages": [{id, jobs, lanes: [{lane, state}], skipped}],
                 "skipped": [{stage, why}], "bounds": [{stage, key, value, enforced, how}]}
    "artifacts": [{"name", "type", "schema", "view", "stage", "lane", "path", "bytes", "ok", "problems",
                   "state": "saved" | "skipped" | "missing"}]

A `retention: run` memory entry of the run is removed when the run ends
(packs/memory_meta.py `end_run`).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from halo_harness.orchestra import jsonl


def artifacts_root(run_dir) -> Path:
    return Path(run_dir) / "artifacts"


def view(pack_id: str, schema: str, repo=None) -> str:
    """How Studio draws a document of `schema` (its x-halo-view; keyvalue by default)."""
    from halo_harness.packs.discover import find
    from halo_harness.packs.typed import artifact_schema, view_of
    pack = find(str(pack_id or ""), cwd=repo) if schema else None
    return view_of(artifact_schema(pack.root, schema)) if pack is not None else "keyvalue"


def _copy(run_dir: Path, lane_n: int, src: Path, name: str, many: bool) -> Path:
    dest_dir = artifacts_root(run_dir) / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (f"{src.stem}.{lane_n}{src.suffix}" if many else src.name)
    shutil.copyfile(src, dest)
    beside = src.parent / name
    if beside.is_dir():
        shutil.copytree(beside, dest_dir / (f"files.{lane_n}" if many else "files"), dirs_exist_ok=True)
    return dest


def _gate_rows(gate) -> dict:
    rows = getattr(gate, "record", None) or []
    return {(r.get("lane"), r.get("artifact")): r for r in rows if isinstance(r, dict) and r.get("artifact")}


def artifact_rows(run_dir, goal, lanes: list, gate, status: str) -> list:
    from halo_harness.orchestra.goal import repo_root_of
    run_dir = Path(run_dir)
    wf, out, repo = goal.workflow or {}, [], repo_root_of(run_dir)
    checked = _gate_rows(gate)
    for name, o in (wf.get("outputs") or {}).items():
        st = next((s for s in wf.get("stages") or [] if s.get("id") == o.get("from")), {})
        mine = [lane for lane in lanes if lane.job.id in set(st.get("jobs") or [])]
        schema = str(o.get("schema") or "")
        base = {"name": name, "type": o.get("type"), "schema": schema, "view": view(wf.get("pack"), schema, repo), "stage": o.get("from")}
        if not mine:
            why = next((x.get("why") for x in wf.get("skipped") or [] if x.get("stage") == o.get("from")), "no lane ran it")
            out.append(dict(base, state="skipped", why=why))
        for lane in mine:
            data = lane.data()
            if data.get("skipped"):
                out.append(dict(base, lane=lane.n, state="skipped", why=data["skipped"]))
                continue
            rows = [g for g in data.get("gave") or [] if g.get("name") == name and g.get("kind") != "files"]
            src = run_dir / rows[0]["path"] if rows else None
            if src is None or not src.is_file():
                out.append(dict(base, lane=lane.n, state="missing", ok=False))
                continue
            path = _copy(run_dir, lane.n, src, name, len(mine) > 1) if status == "finished" else src
            g = checked.get((lane.n, name)) or {}
            out.append(dict(base, lane=lane.n, state="saved", path=path.relative_to(run_dir).as_posix(),
                            bytes=path.stat().st_size, ok=g.get("equal", True), problems=list(g.get("problems") or [])))
    return out


def part(run_dir, goal, lanes: list, gate, status: str) -> dict:
    """The report's `workflow` and `artifacts` ({} for a goal without a workflow)."""
    wf = getattr(goal, "workflow", None) or {}
    if not wf:
        return {}
    by_job = {lane.job.id: lane for lane in lanes}
    stages = []
    for st in wf.get("stages") or []:
        mine = [by_job[j] for j in st.get("jobs") or [] if j in by_job]
        stages.append({"id": st.get("id"), "jobs": list(st.get("jobs") or []),
                       "lanes": [{"lane": l.n, "state": "skipped" if l.data().get("skipped") else l.state} for l in mine]})
    try:
        from halo_harness.packs.memory_meta import end_run
        end_run(Path(run_dir).name)
    except Exception:  # memory housekeeping never changes how a run ends
        pass
    return {"workflow": {"ref": wf.get("ref"), "version": wf.get("version"), "inputs": wf.get("inputs") or {},
                         "stages": stages, "skipped": list(wf.get("skipped") or []), "bounds": list(wf.get("bounds") or [])},
            "artifacts": artifact_rows(run_dir, goal, lanes, gate, status)}


def lines(report: dict) -> "list[str]":
    """The CLI report's workflow lines: each artifact, the workflow's budget with the spend (3.2.1.0 R2) and each
    bound not enforced yet."""
    out = []
    for a in report.get("artifacts") or []:
        where = a.get("path") or a.get("why") or ""
        mark = "ok" if a.get("ok", True) and a.get("state") == "saved" else a.get("state")
        out.append(f"  artifact {a['name']:<12} {mark:<8} {a.get('schema') or a.get('type')} ({a.get('view')}) {where}")
    for b in (report.get("workflow") or {}).get("bounds") or []:
        if b.get("key") == "budget_usd" and not b.get("stage") and b.get("enforced"):
            out.append(f"  budget: the run spent {float(report.get('cost_usd') or 0):.4f} of {float(b['value']):.4f} USD "
                       "(the workflow's budget_usd, a stop)")
        elif not b.get("enforced"):
            out.append(f"  not enforced yet: {(b.get('stage') + ' ') if b.get('stage') else ''}{b['key']} {b['value']} -- {b['how']}")
    return out


def load_artifact(run_dir, name: str) -> "tuple[object, dict]":
    """`(document, row)` of a run's artifact by name (the report's row), `(None, {})` when there is none."""
    report = jsonl.read_json(Path(run_dir) / "report.json", {}) or {}
    row = next((a for a in report.get("artifacts") or [] if a.get("name") == name and a.get("path")), None)
    if row is None:
        return None, {}
    return jsonl.read_json(Path(run_dir) / row["path"], None), row
