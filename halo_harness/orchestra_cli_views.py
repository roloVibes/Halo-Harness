"""halo_harness.orchestra_cli_views -- the read-only views of `halo
orchestra` (Halo 3.0.3.0 rounds R1 / R2; 3.1.0.0 R2 gathered them here
from orchestra_cli.py and orchestra_cli_run.py). Nothing here writes.

    halo orchestra status [RUN]          the goal, the workflow's steps, live claims, the last events
    halo orchestra claims [RUN]          every live claim: key, holder, state, expiry
    halo orchestra log [RUN] [--since N] the timed run log
    halo orchestra runs                  every run of this repo, oldest first
    halo orchestra lanes [RUN]           every lane: state, holder, returns, cost
    halo orchestra report [RUN]          the run's report and its checks

The parsers are orchestra_cli.py's; RUN resolves through its `_open`.
"""

from __future__ import annotations

import sys
from pathlib import Path

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import goal as G
from halo_harness.orchestra import jsonl
from halo_harness.orchestra.claims import ClaimLog, clock_text
from halo_harness.orchestra.workflow import summary


def _open(args, repo: Path):
    from halo_harness.orchestra_cli import _open as open_run
    return open_run(args, repo)


def _status(args, repo: Path) -> int:
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    try:
        goal = G.load_goal(run_dir / "goal.json")
    except ValueError as e:
        print(f"halo orchestra status: {e}", file=sys.stderr)
        return 1
    print(f"run {run_dir.name}  ({run_dir})")
    print(f"  WHAT YOU WANT  {goal.what}")
    print(f"  DONE WHEN      {goal.done_when}")
    print(f"  STOP WHEN      {goal.stop_when}")
    print(f"  {goal.workers} worker(s), return cap {goal.return_cap}, test {goal.test or '(none)'}, "
          f"lead {goal.lead}, worker {goal.worker}" + (f", lineup {goal.lineup}" if goal.lineup else ""))
    print(f"  files: {', '.join(goal.files) or '(none)'}")
    graph = jsonl.read_json(run_dir / "workflow.json", {}) or {}
    counts = summary(graph)
    print("  steps: " + (", ".join(f"{v} {k}" for k, v in sorted(counts.items())) or "(no workflow.json)"))
    running = [s["id"] for s in graph.get("steps") or [] if s.get("state") == "running"]
    if running:
        print("  running: " + ", ".join(running))
    active = ClaimLog(run_dir).active()
    print(f"  live claims: {len(active)}")
    tail = run_events.read(run_dir)[-5:]
    if tail:
        print("  last events:")
        for e in tail:
            print("    " + run_events.format_line(e))
    return 0


def _claims(args, repo: Path) -> int:
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    active = ClaimLog(run_dir).active()
    if not active:
        print(f"run {run_dir.name}: no live claims")
        return 0
    print(f"run {run_dir.name}: {len(active)} live claim(s)")
    for c in sorted(active.values(), key=lambda c: c.key):
        print(f"  {c.key:<40} {c.holder:<30} {c.state:<8} until {clock_text(c.expires)}")
    return 0


def _log(args, repo: Path) -> int:
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    entries = run_events.read(run_dir, since=args.since)
    if not entries:
        print(f"run {run_dir.name}: no events" + (f" after entry {args.since}" if args.since else ""))
        return 0
    for e in entries:
        print(run_events.format_line(e))
    return 0


def _runs(args, repo: Path) -> int:
    runs = G.list_runs(repo)
    if not runs:
        print("no runs in this repo yet: halo orchestra new")
        return 0
    for run_dir in runs:
        data = jsonl.read_json(run_dir / "goal.json", {}) or {}
        what = str(data.get("what") or "")
        print(f"{run_dir.name}  {int(data.get('workers') or 0):>2} worker(s)  {what[:60]}")
    return 0


def cmd_lanes(args, repo: Path) -> int:
    from halo_harness.orchestra.lanes import lane_rows
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    rows = lane_rows(run_dir)
    if not rows:
        print(f"run {run_dir.name}: no lanes yet (halo orchestra run {run_dir.name})")
        return 0
    print(f"run {run_dir.name}: {len(rows)} lane(s)")
    for row in rows:
        print(f"  lane {row.get('lane'):<3} {row.get('state') or '-':<9} returned {row.get('pieces_returned', 0)}  "
              f"${float(row.get('cost_usd') or 0):.4f}  {row.get('holder') or '-':<28} {row.get('title') or ''}")
        print(f"           {', '.join(row.get('claims') or [])}")
    return 0


def cmd_report(args, repo: Path) -> int:
    from halo_harness.orchestra.report import format_report, load_report
    run_dir = _open(args, repo)
    if run_dir is None:
        return 1
    report = load_report(run_dir)
    if report is None:
        print(f"run {run_dir.name}: no report yet (halo orchestra run {run_dir.name})")
        return 1
    print(format_report(report, run_dir))
    return 0


HANDLERS = {"status": _status, "claims": _claims, "log": _log, "runs": _runs, "lanes": cmd_lanes, "report": cmd_report}
