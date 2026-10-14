"""halo_harness.flows.report -- `<run>/report.json` and its text form.

    {"run", "name", "project", "project_path", "status": "finished" | "stopped",
     "stop_reason", "created", "finished", "elapsed_s", "cost_usd", "budget_usd",
     "steps": [{"id", "kind", "state", "cost_usd", "elapsed_s", "rounds", "error"}],
     "artboards": [{"step", "id", "kind", "path", "prompt_id"}],
     "accepted": [paths],
     "posts": [{"platform", "dry_run", "chars", "media", "post_id", "scheduled_at", "error"}],
     "metrics": {"notes": n, "summary", "samples": n, "posts": n, "totals": {views, likes, comments, shares}}}
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from halo_harness.flows.metrics_pull import run_totals
from halo_harness.flows.postiz_parse import format_totals
from halo_harness.orchestra import jsonl


def _elapsed(rec: dict):
    s, f = rec.get("started"), rec.get("finished")
    return round(float(f) - float(s), 3) if isinstance(s, (int, float)) and isinstance(f, (int, float)) else None


def _samples(project_path: str, run: str) -> list:
    if not project_path or not Path(project_path).is_dir():
        return []
    from halo_harness.design.store import Project
    return [m for m in Project(Path(project_path)).metrics() if m.get("run") == run]


def build_report(run_dir, *, status: str, stop_reason: str = "", clock: Callable = time.time) -> dict:
    from halo_harness.flows.state import read_events, read_flow, read_step
    run_dir = Path(run_dir)
    flow = read_flow(run_dir)
    rows, arts, accepted, posts, cost = [], [], [], [], 0.0
    for i, s in enumerate(flow.get("steps") or []):
        rec = read_step(run_dir, i + 1)
        c = float(rec.get("cost_usd") or 0.0)
        cost += c
        rows.append({"id": s.get("id"), "kind": s.get("kind"), "state": s.get("state"), "cost_usd": round(c, 6),
                     "elapsed_s": _elapsed(rec), "rounds": rec.get("rounds") or 0, "error": rec.get("error")})
        out = rec.get("output") if isinstance(rec.get("output"), dict) else {}
        if s.get("kind") == "render":
            arts += [dict(a, step=s.get("id")) for a in out.get("artboards") or []]
        if s.get("kind") == "confirm":
            accepted += list(out.get("accepted") or [])
        if s.get("kind") == "post":
            posts += [{"platform": p.get("platform"), "dry_run": p.get("dry_run"), "chars": len(p.get("text") or ""),
                       "media": len(p.get("media") or []), "post_id": p.get("post_id"),
                       "scheduled_at": p.get("scheduled_at"), "error": p.get("error")} for p in out.get("posts") or []]
    notes = [e for e in read_events(run_dir) if e.get("kind") == "metric"]
    project_path = str(flow.get("project_path") or "")
    samples = _samples(project_path, run_dir.name)
    totals, n_posts = run_totals(samples)
    now = clock()
    created = float(flow.get("created") or now)
    return {"run": run_dir.name, "name": flow.get("name"), "project": flow.get("project"),
            "project_path": project_path, "status": status, "stop_reason": stop_reason or None,
            "created": created, "finished": round(now, 3), "elapsed_s": round(max(0.0, now - created), 3),
            "cost_usd": round(cost, 6), "budget_usd": flow.get("budget_usd"), "steps": rows, "artboards": arts,
            "accepted": accepted, "posts": posts,
            "metrics": {"notes": len(notes), "samples": len(samples), "posts": n_posts, "totals": totals,
                        "summary": format_totals(totals, n_posts) or (notes[-1].get("text") if notes else "")}}


def write_report(run_dir, *, status: str, stop_reason: str = "", clock: Callable = time.time) -> dict:
    report = build_report(run_dir, status=status, stop_reason=stop_reason, clock=clock)
    jsonl.write_json(Path(run_dir) / "report.json", report)
    return report


def format_report(report: dict) -> str:
    lines = [f"flow {report.get('name')} run {report.get('run')}: {report.get('status')}"
             + (f" -- {report['stop_reason']}" if report.get("stop_reason") else "")]
    for s in report.get("steps") or []:
        el = s.get("elapsed_s")
        extra = f"  rounds {s['rounds']}" if (s.get("rounds") or 0) > 1 else ""
        lines.append(f"  {str(s.get('id')):<12} {str(s.get('kind')):<8} {str(s.get('state')):<8} "
                     f"${float(s.get('cost_usd') or 0):.4f}  {'%.1fs' % el if el is not None else '-':>8}{extra}"
                     + (f"  error: {s['error']}" if s.get("error") else ""))
    for a in report.get("artboards") or []:
        lines.append(f"  artboard {a.get('id')} ({a.get('kind')}): {a.get('path')}")
    for p in report.get("posts") or []:
        what = ("dry run" if p.get("dry_run") else f"failed: {p['error']}" if p.get("error") else
                f"live, post {p.get('post_id')}" + (f" scheduled {p['scheduled_at']}" if p.get("scheduled_at") else ""))
        lines.append(f"  post {p.get('platform')}: {what}, {p.get('chars')} chars, {p.get('media')} media")
    if (report.get("metrics") or {}).get("summary"):
        lines.append(f"  metrics: {report['metrics']['summary']}")
    budget = report.get("budget_usd")
    lines.append(f"  total ${float(report.get('cost_usd') or 0):.4f}" + (f" of ${float(budget):.2f}" if budget is not None else "")
                 + f" in {float(report.get('elapsed_s') or 0):.1f}s; project {report.get('project_path') or report.get('project')}")
    return "\n".join(lines)
