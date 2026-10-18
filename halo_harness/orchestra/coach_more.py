"""halo_harness.orchestra.coach_more -- the coach's rules for a flow run, a
mission and a team run (orchestra/coach.py; the Orchestra rules are
coach_rules.py). Same suggestion shape, same evidence-in-`why` habit:

* flow: a confirm gate that looped more than twice (coordination), a
  render step drawn again two or more times (prompt: the redo
  instructions are the evidence), a run stopped by its budget
  (coordination, the cost per step).
* mission: a part `asked` (waiting for a harness owner to allow it) longer
  than the mission's median part took (coordination); an edit refused
  outside a part's claims (tools); a merge conflict judged between two
  parts (structure: `depends_on`); a repo part that changed no file
  (structure); outputs the plan named that are missing (prompt).
* team: a stage gated two or more times (coordination: the redo answers);
  a write the team guard denied because another member held the block
  (tools).
"""

from __future__ import annotations

from pathlib import Path
from statistics import median

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


def mission(run_dir, **_kw) -> tuple:
    run_dir = Path(run_dir)
    report = jsonl.read_json(run_dir / "report.json", {}) or {}
    log = jsonl.read_lines(run_dir / "log.jsonl")
    parts = {str(p.get("id")): p for p in report.get("parts") or []}
    out = []
    asked = _asked(log)
    times = [float(p["duration_s"]) for p in parts.values() if isinstance(p.get("duration_s"), (int, float))]
    mid = median(times) if times else None
    for pid, secs in sorted(asked.items()):
        if mid is not None and secs > mid:
            p = parts.get(pid) or {}
            out.append(suggestion(f"coordination-{pid}-asked", "coordination", "medium",
                                  f"part {pid} waited {secs:.0f}s for {p.get('harness_name') or 'its harness'}'s owner "
                                  "to allow it: pin it to a harness that runs parts without asking, or answer sooner",
                                  [f"part {pid}: asked for {secs:.0f}s", f"the median part took {mid:.0f}s"],
                                  lane_or_part=pid))
    for r in report.get("refused") or []:
        out.append(suggestion(f"tools-{r.get('part')}-{r.get('file')}", "tools", "medium",
                              f"part {r.get('part')} could not write `{r.get('file')}`: it is outside the part's claims",
                              [f"part {r.get('part')} on {r.get('harness')}: {r.get('tool')} {r.get('file')} refused",
                               "a part edits only what claims.json gives it: plan again with this file in its claims"],
                              lane_or_part=str(r.get("part"))))
    merge = report.get("merge") or {}
    order = [str(x) for x in merge.get("merged") or []]
    for c in merge.get("conflicts") or []:
        pid, rel = str(c.get("part")), str(c.get("file") or "")
        others = [q for q in order[:order.index(pid)] if rel in (parts.get(q) or {}).get("files", [])] if pid in order else []
        if others:
            out.append(suggestion(f"structure-{pid}-after-{others[-1]}", "structure", "medium",
                                  f"give part {pid} `depends_on: [{others[-1]}]` so it starts from part {others[-1]}'s head",
                                  [f"merging part {pid} conflicted in {rel} with part {others[-1]}; a judge resolved it",
                                   "depends_on is the lead's: plan the mission again with this in its constraints"],
                                  lane_or_part=pid))
    for pid, p in parts.items():
        if p.get("kind") == "repo" and p.get("state") in ("done", "merged") and not p.get("files"):
            out.append(suggestion(f"structure-{pid}-drop", "structure", "low",
                                  f"drop part {pid} ({p.get('title')}) or fold it into another part",
                                  [f"part {pid} finished and changed no file"], lane_or_part=pid))
    missing = list(report.get("missing_outputs") or [])
    if missing:
        out.append(suggestion("prompt-missing-outputs", "prompt", "medium",
                              "say in the part's brief where each output goes: the plan named outputs nobody wrote",
                              [f"missing: {m}" for m in missing]))
    evidence = {"status": report.get("state"), "cost_usd": (report.get("cost") or {}).get("total_usd"),
                "median_part_s": mid, "asked_s": asked,
                "parts": [{k: p.get(k) for k in ("id", "state", "harness_name", "duration_s", "cost_usd")}
                          for p in parts.values()]}
    return out, evidence


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
