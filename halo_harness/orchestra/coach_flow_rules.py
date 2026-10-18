"""halo_harness.orchestra.coach_flow_rules -- the coach's rules for a flow run
(orchestra/coach.py; 3.1.0.0 R2 cut it out of coach_more.py, which held the
flow, mission and team rules together). Same suggestion shape as the
Orchestra rules (coach_orchestra_rules.py), same evidence-in-`why` habit:

* a confirm gate that looped more than twice (coordination);
* a render step drawn again two or more times (prompt: the redo
  instructions are the evidence);
* a run stopped by its budget (coordination, the cost per step).
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.coach import suggestion


def flow(run_dir, **_kw) -> tuple:
    run_dir = Path(run_dir)
    data = jsonl.read_json(run_dir / "flow.json", {}) or {}
    report = jsonl.read_json(run_dir / "report.json", {}) or {}
    steps = [jsonl.read_json(run_dir / "steps" / f"{i + 1}.json", {}) or {} for i in range(len(data.get("steps") or []))]
    out = []
    for i, s in enumerate(data.get("steps") or []):
        rec, sid = steps[i], str(s.get("id"))
        rounds = int(rec.get("rounds") or 0)
        if s.get("kind") == "confirm" and rounds > 2:
            out.append(suggestion(f"coordination-{sid}-loops", "coordination", "medium",
                                  f"the gate at {sid} looped {rounds} times before an answer stuck",
                                  [f"step {sid}: {rounds} rounds"] + [f"redo: {t}" for t in rec.get("instructions") or []],
                                  lane_or_part=sid))
        redo = [str(t) for t in rec.get("instructions") or []]
        if s.get("kind") == "render" and len(redo) >= 2:
            out.append(suggestion(f"prompt-{sid}-redo", "prompt", "medium",
                                  f"tighten the prompt of step {sid}: it was drawn again {len(redo)} times",
                                  [f"redo {k + 1}: {t}" for k, t in enumerate(redo)], lane_or_part=sid,
                                  apply=None))
    reason = str(report.get("stop_reason") or "")
    if "budget" in reason:
        out.append(suggestion("coordination-budget", "coordination", "medium",
                              "the run stopped at its budget: raise budget_usd or give the dear step a cheaper model",
                              [reason] + [f"step {r.get('id')}: ${float(r.get('cost_usd') or 0):.4f}"
                                          for r in report.get("steps") or [] if float(r.get("cost_usd") or 0) > 0]))
    evidence = {"status": report.get("status") or data.get("status"), "cost_usd": report.get("cost_usd"),
                "steps": [{"id": s.get("id"), "kind": s.get("kind"), "state": s.get("state"),
                           "rounds": int(steps[i].get("rounds") or 0), "cost_usd": steps[i].get("cost_usd")}
                          for i, s in enumerate(data.get("steps") or [])]}
    return out, evidence
