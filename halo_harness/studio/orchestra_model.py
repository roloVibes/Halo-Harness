"""halo_harness.studio.orchestra_model -- what the Orchestra view reads off a
run folder (Halo 3.0.3.0 round R4): the run rows, the whole run payload, and
the live "one file" view composed by code.

The file view: `base` is the file on the run's finished branch
(`orchestra/<run-id>`, which grows one merge at a time), else at the split's
base commit, else at HEAD, else on disk. Every lane that claims a unit of the
file gets a region: the unit's lines in `base` (located by its key through
`orchestra.index`), the lane's current text of that unit (its worktree copy,
else its `written` snapshot) and a state: the live claim's own state
(claimed / writing / written) when one is held, else `merged` once the lane
merged, else `written` when the lane holds a snapshot, else `claimed`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import gitops, jsonl
from halo_harness.orchestra.goal import Goal, list_runs, repo_root_of, run_meta
from halo_harness.orchestra.index import index_text, split_key
from halo_harness.orchestra.lanes import lane_rows, unit_text
from halo_harness.orchestra.report import load_report


def repo_of(cwd) -> Path:
    """The git repo Studio's folder belongs to (the folder itself when it is none)."""
    try:
        from halo_harness.worktree import repo_root
        return repo_root(Path(cwd)) or Path(cwd)
    except Exception:
        return Path(cwd)


def find_run(repo, run_id: str) -> Optional[Path]:
    """A run of `repo` by exact id or unique id prefix (never a path)."""
    runs = list_runs(repo)
    exact = [p for p in runs if p.name == run_id]
    if exact:
        return exact[0]
    matches = [p for p in runs if p.name.startswith(run_id)]
    return matches[0] if len(matches) == 1 else None


def goal_of(run_dir) -> dict:
    data = jsonl.read_json(Path(run_dir) / "goal.json", {}) or {}
    return Goal.from_dict(data).to_dict() if isinstance(data, dict) else {}


def _lead_cost(run_dir) -> float:
    split = jsonl.read_json(Path(run_dir) / "split.json", {}) or {}
    return float(split.get("lead_cost_usd") or 0.0) if isinstance(split, dict) else 0.0


def run_cost(run_dir, report: Optional[dict] = None, lanes: Optional[list] = None) -> float:
    """The report's cost once written, else the lead's split plus every lane so far."""
    if report and isinstance(report.get("cost_usd"), (int, float)):
        return float(report["cost_usd"])
    rows = lane_rows(run_dir) if lanes is None else lanes
    return round(_lead_cost(run_dir) + sum(float(r.get("cost_usd") or 0.0) for r in rows), 6)


def run_state(run_dir, live: bool, report: Optional[dict] = None) -> str:
    """running | planned | finished | stopped | dry run | new | interrupted (3.0.9.0 R2: planned =
    the split waits for the reviewed plan, live or not)."""
    graph = jsonl.read_json(Path(run_dir) / "workflow.json", {}) or {}
    planned = any(s.get("id") == "split" and s.get("state") == "planned" for s in graph.get("steps") or [])
    if live:
        return "planned" if planned else "running"
    if report:
        return str(report.get("status") or "finished")
    if planned:
        return "planned"
    if (Path(run_dir) / "dry_run.json").is_file():
        return "dry run"
    started = any(s.get("state") != "pending" for s in graph.get("steps") or [] if s.get("kind") != "goal")
    if started:
        # 3.1.8.0 R1: a run another process drives right now (the supervisor, a `halo orchestra run`
        # elsewhere) is running, not interrupted (supervise/heartbeat.py).
        from halo_harness.supervise.heartbeat import live as runner_live
        return "running" if runner_live(run_dir) is not None else "interrupted"
    return "new"


def run_row(run_dir, live_id: Optional[str]) -> dict:
    report = load_report(run_dir)
    goal = goal_of(run_dir)
    return {"run_id": Path(run_dir).name, "created": run_meta(run_dir).get("created"),
            "state": run_state(run_dir, Path(run_dir).name == live_id, report), "workers": goal.get("workers"),
            "goal_what": goal.get("what") or "", "cost_usd": run_cost(run_dir, report)}


def run_rows(repo, live_id: Optional[str]) -> list:
    """Every run of the repo, newest first."""
    return [run_row(p, live_id) for p in reversed(list_runs(repo))]


def active_claims(run_dir) -> list:
    from halo_harness.orchestra.claims import ClaimLog
    rows = [c.to_dict() for c in ClaimLog(run_dir).active().values()]
    return sorted(rows, key=lambda c: c["key"])


def run_payload(run_dir, live: bool) -> dict:
    run_dir = Path(run_dir)
    report = load_report(run_dir)
    lanes = lane_rows(run_dir)
    for row in lanes:
        row.pop("reply", None)
    read = lambda name: jsonl.read_json(run_dir / name, None)  # noqa: E731
    return {"run": dict(run_meta(run_dir), state=run_state(run_dir, live, report),
                        cost_usd=run_cost(run_dir, report, lanes)),
            "goal": goal_of(run_dir), "workflow": read("workflow.json"), "split": read("split.json"),
            "lanes": lanes, "claims": active_claims(run_dir), "merge": read("merge.json"), "report": report,
            "dry_run": read("dry_run.json"), "events_count": len(run_events.read(run_dir)), "live": bool(live)}


# -- the one-file view ------------------------------------------------------------

def base_text(run_dir, rel: str) -> "tuple[str, str]":
    """`(text, where)` of the goal file the view draws under the lanes."""
    repo = repo_root_of(run_dir)
    split = jsonl.read_json(Path(run_dir) / "split.json", {}) or {}
    refs = [gitops.finished_branch(Path(run_dir).name), str(split.get("base") or ""), "HEAD"]
    for ref in [r for r in refs if r]:
        try:
            text = gitops.show(repo, ref, rel)
        except Exception:
            text = None
        if text is not None:
            return text, ref
    try:
        return (repo / rel).read_text(encoding="utf-8"), "disk"
    except OSError:
        return "", "missing"


def _lane_text(row: dict, rel: str, key: str) -> Optional[str]:
    tree = row.get("worktree")
    if tree:
        try:
            text = unit_text((Path(tree) / rel).read_text(encoding="utf-8"), rel, key)
        except OSError:
            text = None
        if text is not None:
            return text
    snap = (row.get("written") or {}).get(key)
    return snap if isinstance(snap, str) else None


def region_state(row: dict, claim: Optional[dict]) -> str:
    if claim is not None:
        return str(claim.get("state") or "claimed")
    if row.get("state") == "merged":
        return "merged"
    if row.get("state") in ("written", "in_review") or row.get("written"):
        return "written"
    return "writing" if row.get("state") == "writing" else "claimed"


def file_view(run_dir, rel: str) -> dict:
    text, where = base_text(run_dir, rel)
    lines = text.splitlines()
    units = {u.key: u for u in index_text(text, rel)}
    claims = {c["key"]: c for c in active_claims(run_dir)}
    regions = []
    for row in lane_rows(run_dir):
        for key in row.get("claims") or []:
            path, name = split_key(key)
            if path != rel:
                continue
            unit = units.get(key)
            if name and unit is None:
                continue
            start, end = (unit.start_line, unit.end_line) if unit else (1, max(1, len(lines)))
            current = _lane_text(row, rel, key)
            claim = claims.get(key)
            regions.append({"key": key, "lane": row.get("lane"), "holder": (claim or {}).get("holder") or row.get("holder") or "",
                            "state": region_state(row, claim), "lane_state": row.get("state") or "",
                            "start_line": start, "end_line": end,
                            "text": current.split("\n") if current is not None else lines[start - 1:end]})
    regions.sort(key=lambda r: (r["start_line"], r["lane"] or 0))
    return {"path": rel, "base_ref": where, "base": lines, "regions": regions}
