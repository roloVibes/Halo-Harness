"""halo_harness.orchestra.coach -- the post-run coach (Halo 3.0.9.0 round R3).

`coach(run_dir) -> {run, kind, suggestions, evidence, model: false}` reads a
finished run's files (no model call) and turns what they show into
suggestions, one per finding:

    {id, kind: prompt|model|tools|structure|coordination, severity: high|medium|low,
     lane_or_part, bio, text, why: [evidence lines],
     apply: {target: bio|lineup|plan, name, field, value} | null}

`kind` of the run is read from the folder: an Orchestra run (goal.json), a
flow run (flow.json), a mission (mission.json) or a team run (board.json).
The rules live in coach_rules.py (Orchestra) and coach_more.py (flow,
mission, team); docs/ORCHESTRA.md "The coach" lists them with their
evidence. `apply` names a change; nothing here writes it. Studio's Apply
opens the editor that owns the field with the value filled in (the bio
form, the Lineup tab, the plan editor) and the user saves there.

`cached(run_dir)` is the Studio routes' read: the result kept in
`<run>/coach.json`, computed again when a run file it reads is newer.
`format_card(result)` is the CLI's plain text.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl

KINDS = ("prompt", "model", "tools", "structure", "coordination")
SEVERITIES = ("high", "medium", "low")
RUN_KINDS = ("orchestra", "flow", "mission", "team")
CACHE = "coach.json"
_MARKERS = (("flow", "flow.json"), ("mission", "mission.json"), ("team", "board.json"), ("orchestra", "goal.json"))
_SOURCES = ("report.json", "events.jsonl", "log.jsonl", "merge.json", "board.json", "mission.json", "flow.json",
            "split.json", "plan.json")


def suggestion(sid: str, kind: str, severity: str, text: str, why: list, *, lane_or_part=None, bio: str = "",
               apply: Optional[dict] = None) -> dict:
    if kind not in KINDS or severity not in SEVERITIES:
        raise ValueError(f"suggestion {sid}: kind {kind!r} / severity {severity!r}")
    return {"id": sid, "kind": kind, "severity": severity, "lane_or_part": lane_or_part, "bio": bio or "",
            "text": text, "why": [str(w) for w in why], "apply": apply}


def apply_to(target: str, name: str, field: str, value) -> dict:
    return {"target": target, "name": name, "field": field, "value": value}


def run_kind(run_dir) -> Optional[str]:
    p = Path(run_dir)
    for kind, marker in _MARKERS:
        if (p / marker).is_file():
            return kind
    return None


def coach(run_dir, *, catalog: Optional[list] = None, cwd=None, state_dir=None) -> dict:
    """The coach's card for one run folder. ValueError when the folder is not a run."""
    run_dir = Path(run_dir)
    kind = run_kind(run_dir)
    if kind is None:
        raise ValueError(f"{run_dir} is not an Orchestra, flow, mission or team run folder")
    if kind == "orchestra":
        from halo_harness.orchestra.coach_rules import orchestra as rules
    else:
        from halo_harness.orchestra import coach_more
        rules = getattr(coach_more, kind)
    found, evidence = rules(run_dir, catalog=catalog, cwd=cwd, state_dir=state_dir)
    seen, out = set(), []
    for s in found:
        if s["id"] not in seen:
            seen.add(s["id"])
            out.append(s)
    out.sort(key=lambda s: (SEVERITIES.index(s["severity"]), KINDS.index(s["kind"])))
    return {"run": run_dir.name, "kind": kind, "suggestions": out, "evidence": evidence, "model": False}


def source_mtime(run_dir) -> float:
    """The newest of the run files the coach reads (lanes/*.json and parts/*/result.json too)."""
    run_dir = Path(run_dir)
    paths = [run_dir / n for n in _SOURCES] + list((run_dir / "lanes").glob("*.json")) \
        + list((run_dir / "parts").glob("*/result.json")) + list((run_dir / "steps").glob("*.json"))
    best = 0.0
    for p in paths:
        try:
            best = max(best, p.stat().st_mtime)
        except OSError:
            continue
    return best


def cached(run_dir, **kw) -> dict:
    """`coach(run_dir)` kept in `<run>/coach.json`; computed again when a run file is newer than it."""
    run_dir = Path(run_dir)
    path = run_dir / CACHE
    newest = source_mtime(run_dir)
    data = jsonl.read_json(path, None)
    if isinstance(data, dict) and float(data.get("source_mtime") or -1) >= newest and data.get("suggestions") is not None:
        return dict(data, cached=True)
    result = coach(run_dir, **kw)
    result.update(computed=round(time.time(), 3), source_mtime=newest)
    try:
        jsonl.write_json(path, result)
    except OSError:
        pass
    return dict(result, cached=False)


def _apply_text(a: dict) -> str:
    value = a.get("value")
    shown = ", ".join(str(v) for v in value) if isinstance(value, list) else str(value)
    where = {"bio": "bio", "lineup": "lineup", "plan": "the plan of run"}.get(a.get("target"), a.get("target"))
    return f"{where} {a.get('name')}: {a.get('field')} = {shown}"


def format_card(result: dict) -> str:
    """The card as plain text: one block per suggestion with its why lines."""
    rows = result.get("suggestions") or []
    head = f"coach: {result.get('kind')} run {result.get('run')}: "
    if not rows:
        return head + "nothing to suggest (the run's files show no finding)"
    lines = [head + f"{len(rows)} suggestion{'s' if len(rows) != 1 else ''}"]
    for s in rows:
        where = f" · {s['lane_or_part']}" if s.get("lane_or_part") not in (None, "") else ""
        lines += ["", f"[{s['severity']}] {s['kind']}{where}" + (f" (bio {s['bio']})" if s.get("bio") else ""),
                  f"  {s['text']}", "  why:"]
        lines += [f"    - {w}" for w in s.get("why") or []]
        lines.append(f"  apply: {_apply_text(s['apply'])}" if s.get("apply") else "  apply: nothing to fill in; "
                     "change it by hand")
    return "\n".join(lines)
