"""halo_harness.orchestra.coach_orchestra_rules -- the thin per-kind evidence
loader for an Orchestra run (Halo 3.1.2.0 R1). It reads the run's lanes as
lane facts (coach_lane_facts.py) and the model catalog (coach_prices.py),
turns them into unit facts (noun `lane`), calls the shared rules
(coach_rules.py, the rules of every run kind once) and gathers the evidence.
coach.py dispatches to `orchestra(run_dir, ...)`.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.coach_lane_facts import lane_facts
from halo_harness.orchestra.coach_prices import catalog as load_catalog
from halo_harness.orchestra.coach_rules import (conflict_pairs, coordination_rules, model_rules, prompt_rules,
                                                structure_rules, tools_rules, wait_pairs)


def _held(r: dict) -> dict:
    by = f"lane {r['by_lane']}" if r.get("by_lane") is not None else str(r.get("by"))
    return dict(r, held=f"{by} held `{r.get('other')}`")


def unit_facts(lanes: list) -> list:
    """Lane facts as the shared rules' unit facts."""
    return [dict(f, unit=f["lane"], noun="lane", refused=[_held(r) for r in f["refused"]],
                 files={k.split("#")[0] for k in f["claims"]}) for f in lanes]


def _loops(events: list) -> list:
    fails = [e for e in events if e.get("kind") == "gate" and str(e.get("text") or "").startswith("tests fail")]
    why = [f"+{float(e.get('elapsed_s') or 0):.0f}s {e.get('text')}; sent back: "
           f"{', '.join(f'lane {n}' for n in (e.get('data') or {}).get('back') or []) or 'none'}" for e in fails]
    return [{"unit": None, "noun": "run", "n": len(fails), "limit": 2, "why": why}]


def orchestra(run_dir, *, catalog=None, cwd=None, state_dir=None) -> tuple:
    from halo_harness.orchestra.lanes import lane_rows
    run_dir = Path(run_dir)
    goal = jsonl.read_json(run_dir / "goal.json", {}) or {}
    report = jsonl.read_json(run_dir / "report.json", {}) or {}
    events = jsonl.read_lines(run_dir / "events.jsonl")
    merge = jsonl.read_json(run_dir / "merge.json", {}) or {}
    if cwd is None:
        from halo_harness.orchestra.goal import repo_root_of
        cwd = repo_root_of(run_dir)
    cat = catalog if catalog is not None else load_catalog(state_dir)
    lanes = lane_facts(run_dir, goal, lane_rows(run_dir), events, cwd=cwd, state_dir=state_dir)
    units = unit_facts(lanes)
    cap = int(goal.get("return_cap") or 2)
    order = [int(n) for n in merge.get("order") or [] if str(n).isdigit()]
    conflicts = [{"unit": c.get("lane"), "file": c.get("file")} for c in merge.get("conflicts") or []]
    pairs = conflict_pairs(units, conflicts, order, wait_pairs(units))
    loops = _loops(events)
    found = (prompt_rules(units, goal, cap) + model_rules(units, goal, cap, cat) + tools_rules(units, cwd, state_dir)
             + structure_rules(units, pairs, run_dir.name) + coordination_rules(loops))
    keep = ("lane", "job", "bio", "model", "state", "pieces_returned", "cost_usd", "duration_s", "written", "lines",
            "returned", "waited_s")
    evidence = {"status": report.get("status"), "cost_usd": report.get("cost_usd"), "return_cap": cap,
                "lanes": [{k: f[k] for k in keep} | {"denied": len(f["denied"]), "refused": len(f["refused"])}
                          for f in lanes],
                "gate_loops": loops[0]["n"], "conflicts": len(merge.get("conflicts") or [])}
    return found, evidence
