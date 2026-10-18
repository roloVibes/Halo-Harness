"""halo_harness.orchestra.coach_mission_rules -- the coach's rules for a fleet
mission (orchestra/coach.py; 3.1.0.0 R2 cut it out of coach_more.py). Same
suggestion shape, same evidence-in-`why` habit:

* a part `asked` (waiting for a harness owner to allow it) longer than the
  mission's median part took (coordination);
* an edit refused outside a part's claims (tools);
* a merge conflict judged between two parts (structure: `depends_on`);
* a repo part that changed no file (structure);
* outputs the plan named that are missing (prompt).
"""

from __future__ import annotations

from pathlib import Path
from statistics import median

from halo_harness.orchestra import jsonl
from halo_harness.orchestra.coach import suggestion


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
