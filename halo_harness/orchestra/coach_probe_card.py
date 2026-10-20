"""halo_harness.orchestra.coach_probe_card -- the probe's one coach card (Halo
3.1.6.0 R2): built from `<run>/probe.json` once a probe ended (coach.overlay
puts it first on the run's card), with Apply and Undo through the coach's
writers (orchestra/coach_apply.py, orchestra/coach_record.py).

    {"id": "probe-<ts>", "kind": "probe", "severity": "high" (adopted, merged) | "low" (kept),
     "lane_or_part": null, "bio": "", "text": "adopt the invariant candidate: ...",
     "why": [the compose line, one contrast line per candidate, what Apply cannot write],
     "apply": {"target": "overlay", "name": "<pick>", "field": "overlay", "value": "<n> change(s)",
               "changes": [{target, name, field, value}]} | null,
     "paragraph": "<the judge's why>", "table": [the run itself, then one row per candidate],
     "probe": {runs, k, cost_usd, pick, cap_usd, ended}}

Apply groups the changes by file (one bio, one lineup, the run's plan draft),
writes each file once through coach_apply's writer for its target with all
its fields, and records one row per file under one `group` id (`g-<hex>`, the
apply id the card shows); Undo puts the whole group back. `status(run_dir)`
is the coach result's `probe` field (the progress line while it runs).
`format_probe(data)` is the CLI's contrast table.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import coach_record as R
from halo_harness.orchestra.coach_compose import money, row_line

SEVERITY = {"invariant": "high", "domain": "high", "merged": "high", "kept": "low"}
VERB = {"invariant": "adopt the invariant candidate", "domain": "adopt the domain candidate",
        "merged": "adopt the merged candidate (invariant + domain)", "kept": "keep the run's harness"}
STATUS_KEYS = ("state", "step", "line", "k", "runs", "cap_usd", "estimate", "started", "ended", "card", "pick", "error")


def status(run_dir) -> Optional[dict]:
    from halo_harness.orchestra.coach_probe import read
    data = read(run_dir)
    if not data:
        return None
    return dict({k: data.get(k) for k in STATUS_KEYS}, cost_usd=(data.get("cost") or {}).get("total"))


def table(data: dict) -> list:
    ref = data.get("reference") or {}
    rank = {k: i + 1 for i, k in enumerate((data.get("judge") or {}).get("ranking") or [])}
    head = {"id": "reference", "kind": "the run", "status": ref.get("status"), "tests_ok": ref.get("tests_ok"),
            "passed": ref.get("passed"), "cost_usd": ref.get("cost_usd"), "steps": ref.get("steps"),
            "rank": rank.get("reference"), "wins": [], "picked": data.get("pick") == "kept"}
    return [head] + [dict(r, picked=r["id"] in (data.get("picked") or [])) for r in data.get("contrast") or []]


def _what(changes: list) -> str:
    seen = list(dict.fromkeys(f"{c['target']} {c.get('name') or ''}".strip() for c in changes))
    return f"{len(changes)} change(s) to " + ", ".join(seen) if changes else "nothing Apply can write"


def card(run_dir) -> Optional[dict]:
    """The probe's card once a probe ended with a pick; None before."""
    from halo_harness.orchestra.coach_probe import read
    data = read(run_dir)
    if not data or data.get("state") != "done" or data.get("pick") not in SEVERITY:
        return None
    pick, ref = data["pick"], data.get("reference") or {}
    changes, skipped = (data.get("apply") or {}).get("changes") or [], (data.get("apply") or {}).get("skipped") or []
    rows, judge = data.get("contrast") or [], data.get("judge") or {}
    text = VERB[pick] + ("" if pick == "kept" else f": {_what(changes)}")
    names = {c["id"]: f"{c['kind']} {c['id']}" for c in data.get("candidates") or []}
    labels = ", ".join(f"{L} = {names.get(k, 'the run itself' if k == 'reference' else k)}"
                       for L, k in sorted((judge.get("labels") or {}).items()))
    why = [str(data.get("why") or "")] + [row_line(r, ref, len(rows) + 1) for r in rows] + \
        [f"Apply leaves out {s}" for s in skipped if pick != "kept"] + \
        ([f"the judge saw the deliverables as {labels} (shuffled, nothing else named)"] if labels else [])
    apply = {"target": "overlay", "name": pick, "field": "overlay", "value": f"{len(changes)} change(s)",
             "changes": changes} if changes and pick != "kept" else None
    return {"id": data.get("card") or f"probe-{int(data.get('started') or 0)}", "kind": "probe",
            "severity": SEVERITY[pick], "lane_or_part": None, "bio": "", "text": text, "why": [w for w in why if w],
            "apply": apply, "paragraph": judge.get("why") or None, "paragraph_error": judge.get("error") or "",
            "table": table(data), "probe": {"runs": data.get("runs"), "k": data.get("k"), "pick": pick,
                                            "cost_usd": (data.get("cost") or {}).get("total"),
                                            "cap_usd": data.get("cap_usd"), "ended": data.get("ended")}}


def groups(changes: list) -> list:
    """The changes as one writer call per file: {target, name, field, value, fields: [[field, value], ...]}."""
    by: dict = {}
    for c in changes:
        g = by.setdefault((c["target"], c.get("name") or ""), {"target": c["target"], "name": c.get("name") or "",
                                                               "fields": []})
        g["fields"].append([c["field"], c["value"]])
    return [dict(g, field=g["fields"][0][0], value=g["fields"][0][1]) for g in by.values()]


def _parts(s: dict, run_dir, cwd, state_dir) -> "tuple[list, list]":
    from halo_harness.orchestra import coach_apply as CA
    parts, skipped = [], []
    for a in groups((s.get("apply") or {}).get("changes") or []):
        try:
            ch = CA._change({"id": s["id"], "apply": a}, run_dir, cwd, state_dir)
        except CA.ApplyError as e:
            skipped.append(f"{a['target']} {a['name']}: {e}")
            continue
        parts.append((a, ch))
    return parts, skipped


def preview(result: dict, s: dict, run_dir, *, cwd=None, state_dir=None) -> dict:
    """The confirm card of a probe card: every file Apply writes, with its diff; nothing is written."""
    from halo_harness.orchestra import coach_apply as CA
    parts, skipped = _parts(s, run_dir, cwd, state_dir)
    if not parts:
        raise CA.ApplyError("nothing of the probe's overlay can be written here: " + ("; ".join(skipped) or "no change"))
    files = []
    for a, ch in parts:
        before = R.text_of(ch["file"])
        files.append({"target": a["target"], "name": ch.get("name") or a["name"], "fields": a["fields"],
                      "file": str(ch["file"]), "exists": before is not None,
                      "diff": CA.diff(before or "", ch["render"], ch["file"])})
    n = sum(len(f["fields"]) for f in files)
    return {"id": s["id"], "target": "overlay", "name": s["apply"].get("name"), "field": "overlay",
            "value": f"{n} change(s) in {len(files)} file(s)", "file": files[0]["file"], "files": [f["file"] for f in files],
            "exists": all(f["exists"] for f in files), "before": "", "after": "",
            "diff": [line for f in files for line in f["diff"]], "parts": files, "skipped": skipped}


def apply(result: dict, s: dict, run_dir, *, cwd=None, state_dir=None) -> dict:
    """Write every file of the probe card's overlay; one record row per file under one group id."""
    from halo_harness.orchestra import coach_apply as CA
    parts, skipped = _parts(s, run_dir, cwd, state_dir)
    if not parts:
        raise CA.ApplyError("nothing of the probe's overlay can be written here: " + ("; ".join(skipped) or "no change"))
    group, rows, diff = "g-" + uuid.uuid4().hex[:10], [], []
    for a, ch in parts:
        before = R.text_of(ch["file"])
        ok, problems = ch["write"]()
        if not ok:
            if rows:
                R.undo(group, state_dir)
            raise CA.ApplyError(problems[0] if problems else f"could not write {ch['file']}")
        after = R.text_of(ch["file"]) or ""
        rows.append(R.append({"op": "apply", "apply_id": R.new_id(), "group": group, "id": s["id"],
                              "run": result.get("run"), "run_dir": str(Path(run_dir).resolve()), "kind": result.get("kind"),
                              "target": a["target"], "name": ch.get("name") or a["name"],
                              "field": ", ".join(f for f, _ in a["fields"]), "value": a["fields"], "file": str(ch["file"]),
                              "existed": before is not None, "before": before or "", "after": after,
                              "ts": round(time.time(), 3)}, state_dir))
        diff += CA.diff(before or "", after, ch["file"])
    return {"apply_id": group, "group": group, "file": ", ".join(r["file"] for r in rows),
            "files": [r["file"] for r in rows], "rows": [r["apply_id"] for r in rows], "skipped": skipped, "diff": diff}


def format_probe(data: dict, run: str = "") -> str:
    """The probe as the CLI prints it: the contrast table, the pick and its why, the judge's paragraph."""
    if data.get("state") != "done":
        return f"probe {data.get('state')}: {data.get('error') or data.get('line') or ''}".rstrip(": ")
    rows = table(data)
    names = [("* " if r.get("picked") else "  ") + ("the run itself" if r["id"] == "reference" else f"{r['kind']} {r['id']}")
             for r in rows]
    w = max(len(n) for n in names) + 2
    lines = [f"probe of run {run or '?'}: picked {data.get('pick')}", "",
             f"  {'':<{w}}{'tests':<14} {'cost':<10} {'steps':<8} {'rank':<5} won"]
    for r, name in zip(rows, names):
        tests = "-" if r.get("tests_ok") is None else ("pass" if r["tests_ok"] else "fail") + \
            (f" {r['passed']}" if r.get("passed") is not None else "") + \
            (f" ({r['tests_delta']:+d})" if r.get("tests_delta") is not None else "")
        steps = "-" if r.get("steps") is None else f"{r['steps']}" + (f" ({r['steps_delta']:+d})" if "steps_delta" in r else "")
        won = ", ".join(r.get("wins") or []) or ("" if r["id"] == "reference" or r.get("status") == "finished"
                                                 else f"{r.get('status')}: {r.get('stop_reason') or r.get('error') or ''}")
        lines.append(f"  {name:<{w}}{tests:<14} {money(r.get('cost_usd')) if r.get('cost_usd') is not None else '-':<10} "
                     f"{steps:<8} {str(r.get('rank') or '-'):<5} {won}".rstrip())
    lines += ["", f"  why: {data.get('why')}"]
    judge = data.get("judge") or {}
    if judge.get("why"):
        lines.append(f"  the judge{' (' + judge['model'] + ')' if judge.get('model') else ''}: {judge['why']}")
    changes = (data.get("apply") or {}).get("changes") or []
    if data.get("pick") != "kept" and changes:
        lines.append(f"  apply: halo coach {run or '<run>'} --apply {data.get('card')} ({_what(changes)}; Undo puts it back)")
    for s in (data.get("apply") or {}).get("skipped") or []:
        lines.append(f"  Apply leaves out {s}")
    from halo_harness.orchestra.coach_probe import probe_line
    return "\n".join(lines + [f"  {probe_line(data)}"])
