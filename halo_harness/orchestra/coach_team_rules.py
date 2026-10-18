"""halo_harness.orchestra.coach_team_rules -- the thin evidence loader for a
team run (orchestra/coach.py). 3.1.3.0 R1 moved its rules onto the shared
coach_rules.py: this module turns board.json and events.jsonl into unit
facts (noun `stage`) and loop facts, and calls the shared rules:

* a stage gated two or more times (coordination_rules: the redo answers);
* a write the team guard denied because another member held the block
  (tools_rules).
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.coach_rules import coordination_rules, tools_rules


def _gates(events: list, sid: str, key: str) -> list:
    return [e for e in events if e.get("kind") == "gate" and e.get("stage") == sid and (e.get("data") or {}).get(key)]


def team(run_dir, **_kw) -> tuple:
    run_dir = Path(run_dir)
    board = jsonl.read_json(run_dir / "board.json", {}) or {}
    events = jsonl.read_lines(run_dir / "events.jsonl")
    refused: dict = {}
    for e in events:
        data = e.get("data") or {}
        if e.get("kind") == "claim" and data.get("refused"):
            refused.setdefault(str(e.get("stage") or ""), []).append(
                {"key": str(data.get("key")), "held": f"{data.get('by')} held it", "why": [str(e.get("text") or "")],
                 "who": f"member {data.get('member')} (stage {e.get('stage')})"})
    loops, units = [], []
    for row in board.get("stages") or []:
        sid = str(row.get("id"))
        opened = _gates(events, sid, "gate")
        redo = [str(((e.get("data") or {}).get("answer") or {}).get("text") or "") for e in events
                if e.get("kind") == "gate" and e.get("stage") == sid and (e.get("data") or {}).get("action") == "redo"]
        loops.append({"unit": sid, "noun": "stage", "n": len(opened), "limit": 1,
                      "why": [f"stage {sid}: {len(opened)} gates, round {row.get('round')}"] + [f"redo: {t}" for t in redo if t]})
        units.append({"unit": sid, "noun": "stage", "title": sid, "bio": "", "state": row.get("state"),
                      "refused": refused.pop(sid, []), "written": None})
    units += [{"unit": sid, "noun": "stage", "title": sid, "bio": "", "refused": rs, "written": None}
              for sid, rs in refused.items()]
    out = coordination_rules(loops) + tools_rules(units)
    evidence = {"status": board.get("state"), "stages": [{k: r.get(k) for k in ("id", "state", "round", "cost_usd")}
                                                          for r in board.get("stages") or []]}
    return out, evidence
