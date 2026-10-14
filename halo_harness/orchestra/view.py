"""halo_harness.orchestra.view -- the run as text, for `/orchestra` (the TUI
panel and the headless command share it).

    run <id>: finished | stopped -- <reason> | running or not started
    steps: goal:done  lead:done  split:done  merge:running  test:pending  gate:pending  done:pending

    lane 1   merged    returned 0  $0.0021    <holder>                   write add_item
    ...
    last events:
    +    12.5s  lane 2  merge  lane 2 merged into orchestra/<id>
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional


def run_finder(cwd, name: Optional[str] = None) -> Callable[[], Optional[Path]]:
    """A zero-arg callable returning the run `name` (or the latest) of the
    git repo that holds `cwd` (the repo is looked up once)."""
    from halo_harness.orchestra.goal import resolve_run
    from halo_harness.worktree import repo_root
    root = repo_root(Path(cwd)) or Path(cwd)
    return lambda: resolve_run(root, name)


def lane_line(row: dict) -> str:
    cost = row.get("cost_usd")
    cost_txt = f"${cost:.4f}" if isinstance(cost, (int, float)) else "-"
    return (f"lane {row.get('lane', '?'):<3} {row.get('state') or '-':<9} returned {row.get('pieces_returned', 0)}  "
            f"{cost_txt:<9} {row.get('holder') or '-':<26} {row.get('title') or ''}")


def panel_text(run_dir: Optional[Path]) -> str:
    """The whole body for `run_dir`."""
    if run_dir is None:
        return "No Orchestra run in this folder's repo yet: halo orchestra new, then halo orchestra run."
    from halo_harness.orchestra import events as run_events
    from halo_harness.orchestra import jsonl
    from halo_harness.orchestra.lanes import lane_rows
    from halo_harness.orchestra.report import load_report
    graph = jsonl.read_json(Path(run_dir) / "workflow.json", {}) or {}
    steps = "  ".join(f"{s['id']}:{s.get('state')}" for s in graph.get("steps") or []
                      if s.get("kind") != "worker")
    report = load_report(run_dir)
    status = (f"{report['status']}" + (f" -- {report['stop_reason']}" if report.get("stop_reason") else "")
              if report else "running or not started")
    lines = [f"run {Path(run_dir).name}: {status}", f"steps: {steps or '(no workflow.json)'}", ""]
    rows = lane_rows(run_dir)
    lines += [lane_line(r) for r in rows] or ["no lanes yet"]
    tail = run_events.read(run_dir)[-8:]
    if tail:
        lines += ["", "last events:"] + [run_events.format_line(e) for e in tail]
    return "\n".join(lines)
