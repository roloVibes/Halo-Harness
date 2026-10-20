"""halo_harness.orchestra.coach -- the post-run coach (Halo 3.0.9.0 round R3).

`coach(run_dir) -> {run, kind, suggestions, evidence, model: false}` reads a
finished run's files (no model call) and turns what they show into
suggestions, one per finding:

    {id, kind: prompt|model|tools|structure|coordination, severity: high|medium|low,
     lane_or_part, bio, text, why: [evidence lines],
     apply: {target: bio|lineup|plan, name, field, value} | null}

`kind` of the run is read from the folder: an Orchestra run (goal.json), a
mission (mission.json) or a team run (board.json).
The rules live once in coach_rules.py (3.1.3.0 R1); one thin loader per run
kind, `coach_<kind>_rules.py`, turns that kind's files into the rules'
facts (the Orchestra loader reads coach_lane_facts.py and coach_prices.py);
docs/ORCHESTRA.md "The coach" lists the rules with their evidence.

3.1.3.0 R1 closes the loop: `overlay(result, run_dir)` adds to each
suggestion its `paragraph` (the run's lead's explanation, coach_ask.py,
null until asked) and its `applied` state ({state: applied|undone,
apply_id, file, ts} | null, coach_record.py); Apply writes the change after
one confirm (coach_apply.py) and Undo puts the file back.

3.1.6.0 R2, the probes (coach_probe.py, asked for, never on their own): once
a probe of an Orchestra run ended, its one card (`kind: probe`) leads the
overlay's suggestions, and the result's `probe` is the probe's status.

3.1.6.0 R3, the library (coach_library.py, coach_citations.py): every Apply
becomes an entry; the overlay adds `library` (the entries like this run),
`library_line` and each suggestion's `library_hits`, and `format_card` prints
the line under the head and `[lib e-...]` after a matching card's severity.

`cached(run_dir)` is the Studio routes' read: the result kept in
`<run>/coach.json`, computed again when a run file it reads is newer, with
the overlay. `format_card(result)` is the CLI's plain text.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl

KINDS = ("prompt", "model", "tools", "structure", "coordination")
SEVERITIES = ("high", "medium", "low")
RUN_KINDS = ("orchestra", "mission", "team")
CACHE = "coach.json"
_MARKERS = (("mission", "mission.json"), ("team", "board.json"), ("orchestra", "goal.json"))
_SOURCES = ("report.json", "events.jsonl", "log.jsonl", "merge.json", "board.json", "mission.json",
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
        raise ValueError(f"{run_dir} is not an Orchestra, mission or team run folder")
    import importlib
    rules = getattr(importlib.import_module(f"halo_harness.orchestra.coach_{kind}_rules"), kind)
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


def overlay(result: dict, run_dir, state_dir=None) -> dict:
    """The result with each suggestion's `paragraph` (and `paragraph_error`) and `applied` state. 3.1.6.0 R2: an
    Orchestra run's probe card first once a probe ended (coach_probe_card.py), and `probe`: the probe's status."""
    from halo_harness.orchestra.coach_ask import read_store
    from halo_harness.orchestra.coach_probe_card import card, status
    from halo_harness.orchestra.coach_record import note_run, states
    asked, done = read_store(run_dir), states(run_dir, state_dir)
    probe = card(run_dir) if result.get("kind") == "orchestra" else None
    found = [probe] * bool(probe) + [s for s in result.get("suggestions") or [] if s.get("kind") != "probe"]
    own = {probe["id"]: probe} if probe else {}  # the probe card's paragraph is the judge's why, unless asked
    rows = [dict(s, paragraph=(asked.get(s["id"]) or {}).get("paragraph") or (own.get(s["id"]) or {}).get("paragraph")
                 or None, paragraph_error=(asked.get(s["id"]) or {}).get("error")
                 or (own.get(s["id"]) or {}).get("paragraph_error") or "", applied=done.get(s["id"])) for s in found]
    result = dict(result, suggestions=rows, model=any(s["paragraph"] for s in rows),
                  probe=status(run_dir) if result.get("kind") == "orchestra" else None)
    note_run(result, run_dir, state_dir)
    from halo_harness.orchestra.coach_citations import cite  # 3.1.6.0 R3: the library's entries like this run
    return cite(result, run_dir, state_dir)


def cached(run_dir, **kw) -> dict:
    """`coach(run_dir)` kept in `<run>/coach.json`; computed again when a run file is newer than it."""
    run_dir = Path(run_dir)
    path = run_dir / CACHE
    newest = source_mtime(run_dir)
    data = jsonl.read_json(path, None)
    if isinstance(data, dict) and float(data.get("source_mtime") or -1) >= newest and data.get("suggestions") is not None:
        return overlay(dict(data, cached=True), run_dir, kw.get("state_dir"))
    result = coach(run_dir, **kw)
    result.update(computed=round(time.time(), 3), source_mtime=newest)
    try:
        jsonl.write_json(path, result)
    except OSError:
        pass
    return overlay(dict(result, cached=False), run_dir, kw.get("state_dir"))


def _apply_text(a: dict) -> str:
    if a.get("target") == "overlay":  # 3.1.6.0 R2: a probe card writes several fields, maybe in several files
        return f"the probe's {a.get('name')} overlay: " + "; ".join(
            f"{c['target']} {c.get('name')}: {c['field']}" for c in a.get("changes") or [])
    value = a.get("value")
    shown = ", ".join(str(v) for v in value) if isinstance(value, list) else str(value)
    where = {"bio": "bio", "lineup": "lineup", "plan": "the plan of run"}.get(a.get("target"), a.get("target"))
    return f"{where} {a.get('name')}: {a.get('field')} = {shown}"


def format_card(result: dict) -> str:
    """The card as plain text: one block per suggestion with its why lines."""
    rows = result.get("suggestions") or []
    head = f"coach: {result.get('kind')} run {result.get('run')}: "
    lib = [result["library_line"]] if result.get("library_line") else []  # 3.1.6.0 R3 (orchestra/coach_citations.py)
    if not rows:
        return "\n".join([head + "nothing to suggest (the run's files show no finding)"] + lib)
    lines = [head + f"{len(rows)} suggestion{'s' if len(rows) != 1 else ''}"] + lib
    for s in rows:
        where = f" · {s['lane_or_part']}" if s.get("lane_or_part") not in (None, "") else ""
        hits = f" [lib {', '.join(s['library_hits'])}]" if s.get("library_hits") else ""
        lines += ["", f"[{s['severity']}]{hits} {s['kind']}{where}" + (f" (bio {s['bio']})" if s.get("bio") else ""),
                  f"  {s['text']}", f"  id: {s['id']}", "  why:"]
        lines += [f"    - {w}" for w in s.get("why") or []]
        lines.append(f"  apply: {_apply_text(s['apply'])}" if s.get("apply") else "  apply: nothing to fill in; "
                     "change it by hand")
        if s.get("applied"):
            st = s["applied"]
            lines.append(f"  {st['state']}: {st['apply_id']} ({st.get('file')})")
        who = "the judge" if s.get("kind") == "probe" else "the lead"
        if s.get("paragraph"):
            lines.append(f"  {who}: {s['paragraph']}")
        elif s.get("paragraph_error"):
            lines.append(f"  {who} could not answer: {s['paragraph_error']}")
    return "\n".join(lines)
