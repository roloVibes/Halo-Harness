"""halo_harness.orchestra.coach_orchestra_rules -- the thin per-kind evidence
loader for an Orchestra run (Halo 3.1.2.0 R1). It reads the run's units as
lane facts (coach_lane_facts.py) and the model catalog (coach_prices.py),
then calls the shared rules (coach_rules.py, which hold prompt / model /
tools / structure / coordination once over the unit model, docs/WORK.md)
and gathers the evidence. coach.py dispatches to `orchestra(run_dir, ...)`.
3.1.0.0 R2 renamed the rules module from coach_rules.py; 3.1.2.0 R1 moved
the rules there again (shared by every kind) and left this loader.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.coach_lane_facts import lane_facts
from halo_harness.orchestra.coach_prices import catalog as load_catalog
from halo_harness.orchestra.coach_rules import (coordination_rules, model_rules, prompt_rules, structure_rules,
                                                tools_rules)


def orchestra(run_dir, *, catalog=None, cwd=None, state_dir=None) -> tuple:
    from halo_harness.orchestra.lanes import lane_rows
    run_dir = Path(run_dir)
    goal = jsonl.read_json(run_dir / "goal.json", {}) or {}
    report = jsonl.read_json(run_dir / "report.json", {}) or {}
    events = jsonl.read_lines(run_dir / "events.jsonl")
    if cwd is None:
        from halo_harness.orchestra.goal import repo_root_of
        cwd = repo_root_of(run_dir)
    cat = catalog if catalog is not None else load_catalog(state_dir)
    lanes = lane_facts(run_dir, goal, lane_rows(run_dir), events, cwd=cwd, state_dir=state_dir)
    cap = int(goal.get("return_cap") or 2)
    found = (prompt_rules(lanes, goal, cap) + model_rules(lanes, goal, cap, cat, run_dir.name)
             + tools_rules(lanes, cwd, state_dir) + structure_rules(run_dir, lanes, run_dir.name)
             + coordination_rules(events))
    keep = ("lane", "job", "bio", "model", "state", "pieces_returned", "cost_usd", "duration_s", "written", "lines",
            "returned", "waited_s")
    evidence = {"status": report.get("status"), "cost_usd": report.get("cost_usd"), "return_cap": cap,
                "lanes": [{k: f[k] for k in keep} | {"denied": len(f["denied"]), "refused": len(f["refused"])}
                          for f in lanes],
                "gate_loops": sum(1 for e in events if e.get("kind") == "gate"
                                  and str(e.get("text") or "").startswith("tests fail")),
                "conflicts": len((jsonl.read_json(run_dir / "merge.json", {}) or {}).get("conflicts") or [])}
    return found, evidence
