"""halo_harness.orchestra.coach_citations -- the coach cites its library
(Halo 3.1.6.0 R3; orchestra/coach_library.py keeps the entries).

The rule: an entry is cited for a run when it is not undone, it was not born
from this same run, and either its project is the run's (the same remote
path; with no remote on either side, the same folder name) or its
EXPERIENCE.md ranks for the run's goal words through recall (`recall.search`,
score >= MIN_SCORE); newest first, at most `limit` (3). `coach.library.cite:
false` turns every citation off.

`cite(result, run_dir, state_dir)` (coach.overlay) adds to the coach result

    "library": [{entry, title, when, ts, project, same_project, source, from, fields: [{target, name, field, value}]}],
    "library_line": "the library: 3 earlier runs like this adopted <field> -> <value> (e-..., e-..., e-...)"

and to each suggestion `library_hits: [entry ids]` (the entries that changed
the same target, name and field; a plan job's field matches whatever run it
was in). `lessons(run_dir)` is the probe draft's "What earlier runs like
this learned" (the cited entries' Lessons): reuse through proposals only.
`SEARCH(query, state_dir, k)` replaces recall.search (tests).
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

SEARCH: Optional[Callable] = None
MIN_SCORE = 0.35
_RECALL: dict = {}  # (state dir, query, entry ids) -> {entry id: score}: one recall per library change


def enabled() -> bool:
    from halo_harness.theme import get_config_value
    value = get_config_value("coach.library.cite", True)
    return str(value).strip().lower() not in ("false", "0", "no", "off") if value is not None else True


def same_project(a: dict, b: dict) -> bool:
    a, b = a or {}, b or {}
    if a.get("remote") and b.get("remote"):
        return a["remote"] == b["remote"]
    return bool(a.get("name")) and a.get("name") == b.get("name")


def goal_words(run_dir, kind: str) -> str:
    from halo_harness.orchestra.coach_experience import context_of
    g = context_of(run_dir, kind)["goal"]
    return " ".join(x for x in (g.get("what"), g.get("done_when")) if x).strip()


def _recall(query: str, pool: list, state_dir) -> dict:
    """{entry id: score} for the library hits of the run's goal words."""
    if not query or not pool:
        return {}
    from halo_harness.orchestra.coach_library import folder
    key = (str(state_dir), query, tuple(sorted(e["id"] for e in pool)), id(SEARCH))
    if key in _RECALL:
        return _RECALL[key]
    try:
        if SEARCH is not None:
            hits = list(SEARCH(query, state_dir, 50) or [])
        else:
            from halo_harness.recall import search
            hits = search(query, state_dir=state_dir, k=50)
    except Exception:  # a broken index never stops the coach
        hits = []
    base, out = str(folder(state_dir).resolve()), {}
    for h in hits:
        p = Path(str(h.get("id") or ""))
        if h.get("kind") == "coach_library" and str(p.parent.parent.resolve()) == base:
            out[p.parent.name] = max(out.get(p.parent.name, 0.0), float(h.get("score") or 0.0))
    if len(_RECALL) > 256:  # a long-lived Studio: keep the cache small
        _RECALL.clear()
    _RECALL[key] = out
    return out


def matches(run_dir, state_dir=None, limit: int = 3, *, cwd=None) -> list:
    """The entries cited for this run, newest first: [entry.json + same_project, score]."""
    if not enabled():
        return []
    from halo_harness.orchestra import coach_library as L
    from halo_harness.orchestra.coach import run_kind
    from halo_harness.orchestra.coach_experience import project_of
    here = str(Path(run_dir).resolve())
    pool = [e for e in L.entries(state_dir) if not e.get("undone") and e.get("run_dir") != here]
    if not pool:
        return []
    kind = run_kind(run_dir) or ""
    me = project_of(run_dir, kind, cwd)
    scores = _recall(goal_words(run_dir, kind), pool, state_dir)
    out = []
    for e in pool:
        same, score = same_project(me, e.get("project")), scores.get(e["id"])
        if same or (score is not None and score >= MIN_SCORE):
            out.append(dict(e, same_project=same, score=score))
    return out[:max(0, int(limit))]


def key_of(target, name, field) -> tuple:
    return (target, "" if target == "plan" else str(name or ""), str(field or ""))


def touched(s: dict) -> set:
    a = s.get("apply") or {}
    rows = (a.get("changes") or []) if a.get("target") == "overlay" else ([a] if a else [])
    return {key_of(c.get("target"), c.get("name"), c.get("field")) for c in rows}


def shown(c: dict) -> str:
    from halo_harness.orchestra.coach_experience import shown as value
    where = "the plan" if c.get("target") == "plan" else f"{c.get('target')} {c.get('name')}".strip()
    return f"{where} {c.get('field')} -> {value(c.get('value'))}"


def line(rows: list) -> str:
    """"the library: N earlier run(s) like this adopted <field> -> <value> (ids)" ('' with no entry)."""
    if not rows:
        return ""
    counts: Counter = Counter()
    first: dict = {}
    for r in rows:
        for c in r.get("fields") or []:
            k = (key_of(c.get("target"), c.get("name"), c.get("field")), shown(c))
            if r["entry"] not in first.setdefault(k, []):
                first[k].append(r["entry"])
                counts[k] += 1
    if not counts:
        return f"the library: {len(rows)} earlier run(s) like this ({', '.join(r['entry'] for r in rows)})"
    best = max(counts, key=lambda k: counts[k])  # ties: the newest entry's first change
    ids, n = first[best], counts[best]
    rest = [r["entry"] for r in rows if r["entry"] not in ids]
    return (f"the library: {n} earlier run{'s' if n != 1 else ''} like this adopted {best[1]} ({', '.join(ids)})"
            + (f"; {', '.join(rest)} adopted other changes" if rest else ""))


def row_of(e: dict) -> dict:
    return {"entry": e["id"], "title": e.get("title") or "", "ts": e.get("ts"),
            "when": time.strftime("%Y-%m-%d %H:%M", time.localtime(float(e.get("ts") or 0))),
            "project": e.get("project") or {}, "same_project": bool(e.get("same_project")), "source": e.get("source"),
            "from": e.get("from"), "fields": list(e.get("changes") or [])}


def cite(result: dict, run_dir, state_dir=None) -> dict:
    """The coach result with `library`, `library_line` and each suggestion's `library_hits`; never raises."""
    try:
        rows = [row_of(e) for e in matches(run_dir, state_dir)]
    except Exception:
        rows = []
    keys = {r["entry"]: {key_of(c.get("target"), c.get("name"), c.get("field")) for c in r["fields"]} for r in rows}
    out = []
    for s in result.get("suggestions") or []:
        mine = touched(s)
        out.append(dict(s, library_hits=[r["entry"] for r in rows if mine & keys[r["entry"]]]))
    return dict(result, suggestions=out, library=rows, library_line=line(rows))


def lessons(run_dir, state_dir=None, *, cwd=None) -> str:
    """The cited entries' Lessons as the probe draft's prompt part ('' with none)."""
    from halo_harness.orchestra import coach_library as L
    from halo_harness.orchestra.coach_experience import flat, section, when_line
    try:
        rows = matches(run_dir, state_dir, cwd=cwd)
    except Exception:
        rows = []
    parts = []
    for e in rows:
        text = section(L.text_of(e["id"], L.EXPERIENCE, state_dir), "Lessons")
        if text:
            parts.append(f"  - {e['id']} ({when_line(e.get('project') or {}, e.get('lineup') or '', e.get('goal') or {})}): "
                         f"{flat(text, 300)}; it changed: " + "; ".join(shown(c) for c in e.get("changes") or []))
    return ("What earlier runs like this learned (the coach's library; propose what fits this run, nothing is "
            "inherited):\n" + "\n".join(parts) + "\n\n") if parts else ""
