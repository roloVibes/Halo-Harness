"""halo_harness.orchestra.coach_team_rules -- the coach's rules for a team run
(orchestra/coach.py; 3.1.0.0 R2 cut it out of coach_more.py). Same
suggestion shape, same evidence-in-`why` habit:

* a stage gated two or more times (coordination: the redo answers);
* a write the team guard denied because another member held the block
  (tools).
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.coach import suggestion


def team(run_dir, **_kw) -> tuple:
    run_dir = Path(run_dir)
    board = jsonl.read_json(run_dir / "board.json", {}) or {}
    events = jsonl.read_lines(run_dir / "events.jsonl")
    out = []
    for row in board.get("stages") or []:
        sid = str(row.get("id"))
        opened = [e for e in events if e.get("kind") == "gate" and e.get("stage") == sid and (e.get("data") or {}).get("gate")]
        redo = [str(((e.get("data") or {}).get("answer") or {}).get("text") or "") for e in events
                if e.get("kind") == "gate" and e.get("stage") == sid and (e.get("data") or {}).get("action") == "redo"]
        if len(opened) >= 2:
            out.append(suggestion(f"coordination-{sid}-gated", "coordination", "medium",
                                  f"stage {sid} was gated {len(opened)} times: put what the redo asked for in its brief "
                                  "or its acceptance",
                                  [f"stage {sid}: {len(opened)} gates, round {row.get('round')}"]
                                  + [f"redo: {t}" for t in redo if t], lane_or_part=sid))
    seen = set()
    for e in events:
        data = e.get("data") or {}
        if e.get("kind") != "claim" or not data.get("refused"):
            continue
        key = (e.get("stage"), data.get("member"), data.get("key"))
        if key in seen:
            continue
        seen.add(key)
        out.append(suggestion(f"tools-{e.get('stage')}-{data.get('member')}-{data.get('key')}", "tools", "medium",
                              f"member {data.get('member')} (stage {e.get('stage')}) could not write `{data.get('key')}`: "
                              f"{data.get('by')} held it",
                              [str(e.get("text") or "")], lane_or_part=str(e.get("stage") or "")))
    evidence = {"status": board.get("state"), "stages": [{k: r.get(k) for k in ("id", "state", "round", "cost_usd")}
                                                          for r in board.get("stages") or []]}
    return out, evidence
