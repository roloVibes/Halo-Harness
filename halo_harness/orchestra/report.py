"""halo_harness.orchestra.report -- `<run>/report.json`, the run's checks.

    {"run_id", "status": "finished" | "stopped", "stop_reason": "",
     "branch": "orchestra/<run>", "finished": "<sha>" | null, "tests_ok": true,
     "tests_tail": "...", "cost_usd": 0.0123, "elapsed_s": 81.2, "ts": ...,
     "goal_done_when": "...",
     "lanes": [{"lane", "title", "state", "pieces_returned", "cost_usd"}],
     "checks": [{"id", "ok", "detail"}]}

Check ids (the reel's list): reviewer_fresh, reviewer_applied_by_code_tests_pass,
no_piece_over_cap, all_branches_merged, record_equals_disk,
every_edit_streamed, tests_pass_finished_branch, and goal_done_when (the
DONE WHEN text, echoed; `ok` is null).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import gitops, jsonl
from halo_harness.orchestra.goal import repo_root_of

CHECK_IDS = ("reviewer_fresh", "reviewer_applied_by_code_tests_pass", "no_piece_over_cap",
             "all_branches_merged", "record_equals_disk", "every_edit_streamed",
             "tests_pass_finished_branch", "goal_done_when")


def report_path(run_dir) -> Path:
    return Path(run_dir) / "report.json"


def load_report(run_dir) -> Optional[dict]:
    data = jsonl.read_json(report_path(run_dir), None)
    return data if isinstance(data, dict) else None


def _check(cid: str, ok, detail: str) -> dict:
    return {"id": cid, "ok": ok, "detail": detail}


def _reviewer_checks(conflicts: list, lanes: list, lead_sessions: set) -> list:
    if not conflicts:
        none = "no merge conflicts: no reviewer was needed"
        return [_check("reviewer_fresh", True, none), _check("reviewer_applied_by_code_tests_pass", True, none)]
    worker_sessions = {s for lane in lanes for s in (lane.data().get("session_ids") or [])}
    ids = [c.get("judge_session") for c in conflicts]
    reused = len(set(ids)) != len(ids)
    shared = [i for i in ids if i in worker_sessions or i in lead_sessions]
    stale = [c for c in conflicts if not c.get("fresh") or int(c.get("messages_before") or 0) != 0]
    fresh_ok = not reused and not shared and not stale
    fresh = _check("reviewer_fresh", fresh_ok,
                   f"{len(ids)} judge call(s), each a new session with no earlier messages" if fresh_ok else
                   f"reused={reused} shared_with_workers={shared} with_history={len(stale)}")
    last: dict = {}
    for c in conflicts:
        last[(c.get("lane"), c.get("file"))] = c
    bad = [k for k, c in last.items() if not (c.get("applied_by") == "code" and c.get("applied") and c.get("tests_ok"))]
    applied = _check("reviewer_applied_by_code_tests_pass", not bad,
                     f"{len(last)} conflict(s) resolved: answer applied by code, tests ok" if not bad else
                     "not resolved: " + ", ".join(f"lane {l} {f}" for l, f in bad))
    return [fresh, applied]


def _streamed(run_dir, lanes: list) -> dict:
    entries = jsonl.read_lines(Path(run_dir) / "claims.jsonl")
    missing = []
    for lane in lanes:
        for key in lane.job.claims:
            ops = [e.get("op") for e in entries if e.get("key") == key]
            try:
                w = ops.index("writing")
                wr = ops.index("written", w)
                ops.index("release", wr)
            except ValueError:
                missing.append(key)
    total = sum(len(lane.job.claims) for lane in lanes)
    return _check("every_edit_streamed", not missing,
                  f"{total} unit(s) went claimed -> writing -> written -> released" if not missing else
                  "no full claim/writing/written/release trail for: " + ", ".join(missing))


def build_checks(run_dir, goal, lanes: list, merge: dict, gate) -> list:
    run_dir = Path(run_dir)
    split = jsonl.read_json(run_dir / "split.json", {}) or {}
    checks = _reviewer_checks(merge.get("conflicts") or [], lanes, set(split.get("lead_sessions") or []))
    over = [lane.n for lane in lanes if lane.pieces_returned > goal.return_cap]
    returned = {lane.n: lane.pieces_returned for lane in lanes if lane.pieces_returned}
    checks.append(_check("no_piece_over_cap", not over,
                         f"return cap {goal.return_cap}; returned: {returned or 'none'}" if not over else
                         f"over the cap: lane {over}"))
    repo, branch = repo_root_of(run_dir), merge.get("branch") or gitops.finished_branch(run_dir.name)
    unmerged = [lane.n for lane in lanes if lane.n not in (merge.get("merged") or [])
                or not gitops.is_ancestor(repo, lane.branch, branch)]
    checks.append(_check("all_branches_merged", bool(lanes) and not unmerged,
                         f"{len(lanes)} worker branch(es) merged into {branch}" if not unmerged else
                         f"not merged: lane {unmerged}"))
    if gate is not None:
        rows = gate.record
        diff = [r["key"] for r in rows if not r["equal"] and not r["judge"]]
        judged = [r["key"] for r in rows if r["judge"]]
        checks.append(_check("record_equals_disk", gate.record_ok,
                             (f"{len(rows)} unit(s) on {branch} equal their written snapshots"
                              + (f" ({len(judged)} resolved by the judge)" if judged else ""))
                             if gate.record_ok else "differs from the record: " + ", ".join(diff)))
        checks.append(_check("tests_pass_finished_branch", gate.tests.ok,
                             f"`{gate.tests.command}` exit {gate.tests.returncode}" if gate.tests.command else
                             "no test command"))
    else:
        checks.append(_check("record_equals_disk", False, "the gate did not run"))
        checks.append(_check("tests_pass_finished_branch", False, "the gate did not run"))
    checks.insert(5, _streamed(run_dir, lanes))
    checks.append(_check("goal_done_when", None, goal.done_when))
    return checks


def write_report(run_dir, *, goal, lanes: list, merge: Optional[dict] = None, gate=None,
                 status: str = "finished", stop_reason: str = "", clock=time.time) -> dict:
    run_dir = Path(run_dir)
    merge = merge or jsonl.read_json(run_dir / "merge.json", {}) or {}
    split = jsonl.read_json(run_dir / "split.json", {}) or {}
    cost = float(split.get("lead_cost_usd") or 0.0) + sum(lane.cost_usd for lane in lanes)
    cost += sum(float(c.get("cost_usd") or 0.0) for c in merge.get("conflicts") or [])
    ts = clock()
    report = {
        "run_id": run_dir.name, "status": status, "stop_reason": stop_reason,
        "branch": merge.get("branch") or gitops.finished_branch(run_dir.name),
        "finished": merge.get("finished") if status == "finished" else None,
        "tests_ok": bool(gate is not None and gate.tests.ok),
        "tests_tail": gate.tests.tail if gate is not None else "",
        "cost_usd": round(cost, 6), "ts": round(ts, 3), "elapsed_s": jsonl.elapsed(run_dir, ts),
        "goal_done_when": goal.done_when,
        "lanes": [{"lane": lane.n, "title": lane.job.title, "state": lane.state,
                   "pieces_returned": lane.pieces_returned, "cost_usd": round(lane.cost_usd, 6)} for lane in lanes],
        "checks": build_checks(run_dir, goal, lanes, merge, gate),
        "units": _unit_rows(run_dir),  # 3.1.2.0 R1: one UnitRow per lane (docs/WORK.md), beside `lanes`
    }
    jsonl.write_json(report_path(run_dir), report)
    return report


def _unit_rows(run_dir) -> list:
    """The run's lanes as the shared report rows (work/report.py); [] if it cannot be read."""
    from halo_harness.work.report import rows
    return rows(run_dir, "lane")


def format_report(report: dict) -> str:
    """The report as the CLI prints it."""
    mark = {True: "PASS", False: "FAIL", None: "    "}
    lines = [f"run {report.get('run_id')}: {report.get('status')}"
             + (f" -- {report['stop_reason']}" if report.get("stop_reason") else "")]
    if report.get("finished"):
        lines.append(f"  finished branch {report.get('branch')} at {str(report['finished'])[:12]}")
    lines.append(f"  tests {'pass' if report.get('tests_ok') else 'do not pass'}; cost "
                 f"${float(report.get('cost_usd') or 0):.4f}; {float(report.get('elapsed_s') or 0):.1f}s")
    for lane in report.get("lanes") or []:
        lines.append(f"  lane {lane['lane']:<3} {lane['state']:<9} returned {lane['pieces_returned']}  "
                     f"${float(lane.get('cost_usd') or 0):.4f}  {lane['title']}")
    lines.append("  checks:")
    for c in report.get("checks") or []:
        lines.append(f"    {mark.get(c.get('ok'), '????')}  {c['id']:<36} {c.get('detail') or ''}")
    return "\n".join(lines)
