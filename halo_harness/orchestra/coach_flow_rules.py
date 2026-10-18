"""halo_harness.orchestra.coach_flow_rules -- the thin evidence loader for a
flow run (orchestra/coach.py). 3.1.3.0 R1 moved its rules onto the shared
coach_rules.py: this module turns flow.json, steps/<n>.json and report.json
into unit facts (noun `step`) and loop facts, and calls the shared rules:

* a confirm gate that looped more than twice (coordination_rules);
* a render step drawn again two or more times (prompt_rules, class `redo`:
  the redo instructions are the evidence);
* a run stopped by its budget (coordination_rules, the cost per step).
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.coach_rules import coordination_rules, prompt_rules


def flow(run_dir, **_kw) -> tuple:
    run_dir = Path(run_dir)
    data = jsonl.read_json(run_dir / "flow.json", {}) or {}
    report = jsonl.read_json(run_dir / "report.json", {}) or {}
    spec = data.get("steps") or []
    steps = [jsonl.read_json(run_dir / "steps" / f"{i + 1}.json", {}) or {} for i in range(len(spec))]
    units, loops = [], []
    for i, s in enumerate(spec):
        rec, sid = steps[i], str(s.get("id"))
        redo = [str(t) for t in rec.get("instructions") or []]
        units.append({"unit": sid, "noun": "step", "title": str(s.get("kind") or ""), "bio": "", "who": f"step {sid}",
                      "state": s.get("state"), "returned": {"redo": len(redo)} if s.get("kind") == "render" else {},
                      "return_why": {"redo": [f"redo {k + 1}: {t}" for k, t in enumerate(redo)]}, "written": None})
        if s.get("kind") == "confirm":
            loops.append({"unit": sid, "noun": "step", "n": int(rec.get("rounds") or 0), "limit": 2,
                          "why": [f"step {sid}: {int(rec.get('rounds') or 0)} rounds"] + [f"redo: {t}" for t in redo]})
    reason = str(report.get("stop_reason") or "")
    spent = [f"step {r.get('id')}: ${float(r.get('cost_usd') or 0):.4f}" for r in report.get("steps") or []
             if float(r.get("cost_usd") or 0) > 0]
    out = prompt_rules(units, {}) + coordination_rules(loops, budget=reason if "budget" in reason else "",
                                                       budget_why=spent)
    evidence = {"status": report.get("status") or data.get("status"), "cost_usd": report.get("cost_usd"),
                "steps": [{"id": s.get("id"), "kind": s.get("kind"), "state": s.get("state"),
                           "rounds": int(steps[i].get("rounds") or 0), "cost_usd": steps[i].get("cost_usd")}
                          for i, s in enumerate(spec)]}
    return out, evidence
