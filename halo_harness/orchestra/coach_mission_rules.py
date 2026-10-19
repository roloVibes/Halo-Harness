"""halo_harness.orchestra.coach_mission_rules -- the thin evidence loader for a
fleet mission (orchestra/coach.py). 3.1.3.0 R1 moved its rules onto the
shared coach_rules.py: this module turns report.json and log.jsonl into
unit facts (noun `part`) and calls the shared rules:

* a part `asked` (waiting for a harness owner to allow it) longer than the
  mission's median part took (coordination_rules);
* an edit refused outside a part's claims (tools_rules);
* a merge conflict judged between two parts (structure_rules, `depends_on`);
* a repo part that changed no file (structure_rules: drop);
* outputs the plan named that are missing (outputs_rules).

A mission's changes go into its next plan, so its suggestions name no Apply.
"""

from __future__ import annotations

from pathlib import Path
from statistics import median

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.coach_rules import (conflict_pairs, coordination_rules, outputs_rules, structure_rules,
                                                tools_rules)

DEP_NOTE = "depends_on is the lead's: plan the mission again with this in its constraints"


def _asked(log: list) -> dict:
    """{part: seconds it sat `asked`} from the mission log's `part` lines."""
    out, since = {}, {}
    for e in log:
        if e.get("kind") != "part":
            continue
        pid, ts = str(e.get("part")), float(e.get("ts") or 0)
        if e.get("state") == "asked":
            since.setdefault(pid, ts)
        elif pid in since:
            out[pid] = round(out.get(pid, 0.0) + ts - since.pop(pid), 3)
    return out


def _refused(r: dict) -> dict:
    return {"key": str(r.get("file")), "held": "it is outside the part's claims",
            "why": [f"part {r.get('part')} on {r.get('harness')}: {r.get('tool')} {r.get('file')} refused",
                    "a part edits only what claims.json gives it: plan again with this file in its claims"]}


def mission(run_dir, **_kw) -> tuple:
    run_dir = Path(run_dir)
    report = jsonl.read_json(run_dir / "report.json", {}) or {}
    parts = {str(p.get("id")): p for p in report.get("parts") or []}
    asked = _asked(jsonl.read_lines(run_dir / "log.jsonl"))
    times = [float(p["duration_s"]) for p in parts.values() if isinstance(p.get("duration_s"), (int, float))]
    mid = median(times) if times else None
    refused: dict = {}
    for r in report.get("refused") or []:
        refused.setdefault(str(r.get("part")), []).append(_refused(r))
    units = []
    for pid, p in parts.items():
        drop = p.get("kind") == "repo" and p.get("state") in ("done", "merged") and not p.get("files")
        units.append({"unit": pid, "noun": "part", "title": str(p.get("title") or ""), "bio": "", "job": pid,
                      "state": p.get("state"), "files": set(p.get("files") or []), "refused": refused.pop(pid, []),
                      "written": 0 if drop else None, "asked_s": asked.get(pid), "where": p.get("harness_name")})
    for pid, rs in refused.items():  # a refusal of a part the report does not list
        units.append({"unit": pid, "noun": "part", "title": "", "bio": "", "job": pid, "files": set(), "refused": rs,
                      "written": None})
    merge = report.get("merge") or {}
    conflicts = [{"unit": str(c.get("part")), "file": c.get("file")} for c in merge.get("conflicts") or []]
    pairs = conflict_pairs(units, conflicts, [str(x) for x in merge.get("merged") or []])
    out = (coordination_rules([], units, mid) + tools_rules(units)
           + structure_rules(units, pairs, run_dir.name, dep="depends_on", note=DEP_NOTE, plan=False)
           + outputs_rules(list(report.get("missing_outputs") or [])))
    evidence = {"status": report.get("state"), "cost_usd": (report.get("cost") or {}).get("total_usd"),
                "median_part_s": mid, "asked_s": asked,
                "parts": [{k: p.get(k) for k in ("id", "state", "harness_name", "duration_s", "cost_usd")}
                          for p in parts.values()]}
    return out, evidence
