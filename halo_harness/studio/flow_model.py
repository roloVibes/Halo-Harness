"""halo_harness.studio.flow_model -- what Studio's Flow routes read (Halo
3.0.4.0 round R5): the flow files a run can start from, the run rows, one
run's whole payload (flow.json, each steps/<n>.json, the open gate, the
report, the project's posts and metrics for this run, its artboards with
their `/design-files/` URLs) and the run folder lookup. Read-only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from halo_harness.flows import gates, spec as fspec, state
from halo_harness.orchestra import jsonl

RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
FLOW_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
METRICS_TAIL = 20


def _template_row(name: str, source: str, path: Path) -> dict:
    row = {"name": name, "source": source, "path": str(path), "steps": [], "form": {}}
    try:
        data = fspec.load_flow(path)
    except ValueError as e:
        return dict(row, error=str(e))
    steps = [s for s in data.get("steps") or [] if isinstance(s, dict)]
    row["steps"] = [{"id": s.get("id"), "kind": s.get("kind")} for s in steps]
    intake = next((s for s in steps if s.get("kind") == "intake"), None)
    row["form"] = dict(intake.get("form") or {}) if intake and isinstance(intake.get("form"), dict) else {}
    row["name"] = str(data.get("name") or name)
    row["budget_usd"] = data.get("budget_usd")
    row["version"] = data.get("version")
    return row


def template_rows(cwd, state_dir) -> list:
    """`[{name, source: template|user|project, steps: [{id, kind}], form, budget_usd, version, path}]`."""
    rows = [_template_row(n, "template", fspec.template_path(n)) for n in fspec.template_names()]
    d = fspec.flows_dir(state_dir)
    rows += [_template_row(n, "user", d / f"{n}{fspec.SUFFIX}") for n in fspec.list_flows(state_dir=state_dir)]
    project = Path(cwd) / ".halo" / "flow.yaml"
    if project.is_file():
        rows.append(_template_row("flow", "project", project))
    return rows


def find_flow_file(name: str, cwd, state_dir) -> Optional[Path]:
    """A flow by name: the project's, the user's, then a shipped template (never a path)."""
    if not FLOW_NAME.match(name or ""):
        return None
    path = fspec.find_flow(name, cwd=cwd, state_dir=state_dir)
    if path is None:
        return None
    shipped = fspec.template_path(name)
    user = fspec.flows_dir(state_dir) / f"{name}{fspec.SUFFIX}"
    project = Path(cwd) / ".halo" / "flow.yaml"
    return path if path in (shipped, user, project) else None


def run_dir_of(state_dir, run_id: str) -> Optional[Path]:
    """The run folder `<state>/flows/runs/<id>` (or `last`), or None."""
    if run_id == "last":
        return state.find_run("last", state_dir=state_dir)
    if not RUN_ID.match(run_id or ""):
        return None
    d = state.runs_dir(state_dir) / run_id
    return d if (d / "flow.json").is_file() else None


def waiting_step(run_dir) -> Optional[str]:
    gate = gates.open_gate(run_dir)
    if gate:
        return gate.get("step")
    flow = state.read_flow(run_dir)
    return next((s.get("id") for s in flow.get("steps") or [] if s.get("state") == "waiting"), None)


def run_row(run_dir: Path, live_id: Optional[str]) -> dict:
    flow = state.read_flow(run_dir)
    row = {"run": run_dir.name, "name": flow.get("name"), "status": flow.get("status"),
           "created": flow.get("created"), "cost_usd": flow.get("cost_usd") or 0.0, "project": flow.get("project"),
           "budget_usd": flow.get("budget_usd"), "live": live_id == run_dir.name}
    step = waiting_step(run_dir)
    if step:
        row["waiting_step"] = step
    return row


def run_rows(state_dir, live_id: Optional[str]) -> list:
    """Every flow run, newest first: by `created`, then by id (two runs made in the
    same second would otherwise sort by their random suffix)."""
    root = state.runs_dir(state_dir)
    dirs = sorted(d for d in root.iterdir() if (d / "flow.json").is_file()) if root.is_dir() else []
    rows = [run_row(d, live_id) for d in reversed(dirs)]
    when = lambda r: r.get("created") if isinstance(r.get("created"), (int, float)) else 0  # noqa: E731
    return sorted(rows, key=lambda r: (when(r), r["run"]), reverse=True)


def project_of(run_dir, state_dir):
    """The run's design project (None until the runner or an upload made it)."""
    from halo_harness.design.store import Project
    flow = state.read_flow(run_dir)
    path = str(flow.get("project_path") or "")
    if path and (Path(path) / "design.json").is_file():
        return Project(Path(path))
    slug = str(flow.get("project") or "")
    return Project.open(slug, state_dir=state_dir) if slug else None


def _for_run(rows: list, run: str) -> list:
    return [r for r in rows if isinstance(r, dict) and r.get("run") in (None, run)]


def posts_of(run_dir, state_dir, everything: bool = False) -> list:
    p = project_of(run_dir, state_dir)
    if p is None:
        return []
    try:
        rows = json.loads((p.path / "posts.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = rows if isinstance(rows, list) else []
    return rows if everything else [r for r in rows if isinstance(r, dict) and r.get("run") == Path(run_dir).name]


def metrics_of(run_dir, state_dir, limit: int = METRICS_TAIL) -> list:
    p = project_of(run_dir, state_dir)
    if p is None or limit <= 0:
        return []
    return _for_run(jsonl.read_lines(p.path / "metrics.jsonl"), Path(run_dir).name)[-limit:]


def _source(project, aid: str) -> dict:
    return jsonl.read_json(project.artboard_dir(aid) / "source.json", {}) or {}


def artboards_of(run_dir, state_dir) -> list:
    """`[{id, kind, step, url, version, file}]`: the artboards this run's renders wrote."""
    from halo_harness.flows.steps_media import RENDER_FILES
    p = project_of(run_dir, state_dir)
    if p is None:
        return []
    run = Path(run_dir).name
    out = []
    for a in p.artboards():
        src = _source(p, a["id"])
        if src.get("flow_run") != run:
            continue
        name = next((f for f in RENDER_FILES if f in a.get("files") or []), a.get("render") or "")
        out.append({"id": a["id"], "kind": a.get("kind"), "step": src.get("step"), "title": a.get("title"),
                    "file": name, "url": f"/design-files/{p.slug}/{a['id']}/{name}" if name else "",
                    "version": a.get("latest") or 0, "versions": a.get("versions") or [],
                    "prompt_id": src.get("prompt_id")})
    return out


def run_payload(run_dir: Path, state_dir, live: bool) -> dict:
    """`{flow, steps, gate, report, posts, metrics_tail, artboards, events, live, project}`."""
    data = state.read_run(run_dir)
    p = project_of(run_dir, state_dir)
    data.update(posts=posts_of(run_dir, state_dir), metrics_tail=metrics_of(run_dir, state_dir),
                artboards=artboards_of(run_dir, state_dir), live=bool(live),
                project={"slug": p.slug, "path": str(p.path)} if p is not None else None)
    return data
