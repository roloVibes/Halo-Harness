"""halo_harness.fleet.mission_report -- what a mission did, computed in code
(Halo 3.0.6.0 "Fleet Missions" round R7): who did what on which harness,
the cost per harness and per part, the decisions and who made them, the
files touched, the edits refused outside a part's claims, what failed and
why. `write` keeps `report.json` and `report.md` in the mission folder and
journals the end (`fleet/journal.py` kind `mission_end`).

    {mission, goal, state, stop_reason, created, ended, duration_s,
     cost: {total_usd, plan_usd, parts_usd, est_usd, budget_usd, over_budget},
     parts: [{id, title, kind, harness, harness_name, state, cost_usd, est_cost_usd, started, ended, duration_s,
              files, error, reason, pinned, merged, base, depends_on, take}],
     harnesses: [{harness, name, parts: [ids], cost_usd, done, failed}],
     decisions: [{ts, what, by}], files: [paths], refused: [{part, file, tool, harness, ts}],
     failed: [{part, state, error}], merge: {...} | null, artifacts: [paths], missing_outputs: [paths]}
"""

from __future__ import annotations

import json
import time

from halo_harness.fleet import mission as M
from halo_harness.fleet import mission_store as S


def _dur(a, b):
    return round(float(b) - float(a), 3) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None


def build(home, doc: dict, plan: dict) -> dict:
    mid = doc["id"]
    states = doc.get("parts") or {}
    merged = set(((doc.get("merge") or {}).get("merged")) or [])
    parts, harnesses = [], {}
    for p in (plan or {}).get("parts") or []:
        st = states.get(p["id"]) or {}
        row = {"id": p["id"], "title": p.get("title"), "kind": p.get("kind"), "harness": st.get("harness") or p.get("harness"),
               "harness_name": st.get("harness_name") or p.get("harness_name"), "state": st.get("state") or "pending",
               "cost_usd": round(float(st.get("cost_usd") or 0.0), 6), "est_cost_usd": float(p.get("est_cost_usd") or 0.0),
               "started": st.get("started"), "ended": st.get("ended"), "duration_s": _dur(st.get("started"), st.get("ended")),
               "files": list(st.get("files") or []), "error": st.get("error"), "reason": p.get("reason"),
               "pinned": bool(p.get("pinned")), "merged": p["id"] in merged, "base": st.get("base"),
               "depends_on": list(p.get("depends_on") or []), "take": p.get("take") or "outputs"}
        parts.append(row)
        h = harnesses.setdefault(str(row["harness"]), {"harness": row["harness"], "name": row["harness_name"], "parts": [],
                                                        "cost_usd": 0.0, "done": 0, "failed": 0})
        h["parts"].append(p["id"])
        h["cost_usd"] = round(h["cost_usd"] + row["cost_usd"], 6)
        h["done"] += row["state"] in ("done", "merged")
        h["failed"] += row["state"] in ("failed", "stopped", "skipped")
    parts_usd = round(sum(r["cost_usd"] for r in parts), 6)
    plan_usd = round(float(doc.get("plan_cost_usd") or 0.0), 6)
    budget = doc.get("budget_usd")
    try:
        refused = [{k: r.get(k) for k in ("part", "file", "tool", "harness", "ts")} for r in S.read_log(home, mid, ("claim_refused",))]
    except (OSError, M.MissionError):
        refused = []
    folder = S.folder(home, mid)
    return {"mission": mid, "goal": doc.get("goal"), "state": doc.get("state"), "stop_reason": doc.get("stop_reason"),
            "created": doc.get("created"), "ended": doc.get("ended"), "duration_s": _dur(doc.get("created"), doc.get("ended")),
            "cost": {"total_usd": round(plan_usd + parts_usd, 6), "plan_usd": plan_usd, "parts_usd": parts_usd,
                     "est_usd": round(sum(r["est_cost_usd"] for r in parts), 4), "budget_usd": budget,
                     "over_budget": bool(budget) and plan_usd + parts_usd > float(budget)},
            "parts": parts, "harnesses": sorted(harnesses.values(), key=lambda h: str(h["name"]).lower()),
            "decisions": list(doc.get("decisions") or []), "files": sorted({f for r in parts for f in r["files"]}),
            "refused": refused, "failed": [{"part": r["id"], "state": r["state"], "error": r["error"]} for r in parts
                                           if r["state"] in ("failed", "stopped", "skipped")],
            "merge": doc.get("merge"), "artifacts": [f["path"] for f in S.files(folder, "artifacts")],
            "missing_outputs": list((doc.get("merge") or {}).get("missing_outputs") or [])}


def base_cell(p: dict) -> str:
    """3.0.9.0: where a repo part started (its dependencies' head, or the mission's base)."""
    if not p.get("base"):
        return "-"
    return f"`{str(p['base'])[:7]}`" + (f" (after {', '.join(p['depends_on'])})" if p.get("depends_on") else "")


def markdown(r: dict) -> str:
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(r.get("ended") or time.time()))
    c = r["cost"]
    lines = [f"# Mission {r['mission']}: {r['state']}", "", f"**Goal:** {r.get('goal')}", "",
             f"Ended {when}; ${c['total_usd']:.4f} in all (lead ${c['plan_usd']:.4f}, parts ${c['parts_usd']:.4f}; "
             f"estimated ${c['est_usd']:.2f}" + (f", budget ${float(c['budget_usd']):.2f}" if c.get("budget_usd") else "") + ")."]
    if r.get("stop_reason"):
        lines += ["", f"**Why it ended:** {r['stop_reason']}"]
    lines += ["", "## Who did what", "", "| Part | Harness | State | Cost $ | Time | Base | Title |", "|---|---|---|---|---|---|---|"]
    for p in r["parts"]:
        t = f"{p['duration_s']:.0f}s" if p.get("duration_s") is not None else "-"
        lines.append(f"| {p['id']}{' (merged)' if p['merged'] else ''} | {p.get('harness_name') or p.get('harness')} | "
                     f"{p['state']} | {p['cost_usd']:.4f} | {t} | {base_cell(p)} | {str(p.get('title') or '').replace('|', '/')} |")
    lines += ["", "## Cost per harness", ""] + [f"- {h['name']}: ${h['cost_usd']:.4f} (parts {', '.join(h['parts'])}; "
                                                 f"{h['done']} done, {h['failed']} not)" for h in r["harnesses"]]
    if r["decisions"]:
        lines += ["", "## Decisions", ""] + [f"- {d.get('what')} (by {d.get('by') or 'the hub'})" for d in r["decisions"]]
    if r["failed"]:
        lines += ["", "## What failed", ""] + [f"- part {f['part']} {f['state']}: {f.get('error') or ''}" for f in r["failed"]]
    if r["refused"]:
        lines += ["", "## Edits refused outside a part's claims", ""] + [f"- part {x['part']}: {x['tool']} {x['file']}"
                                                                        for x in r["refused"]]
    m = r.get("merge") or {}
    if m.get("branch"):
        lines += ["", "## Merge", "", f"Branch `{m['branch']}` at {str(m.get('finished') or '')[:12]}; merged parts "
                  f"{', '.join(m.get('merged') or []) or 'none'}" + (f"; {len(m.get('conflicts') or [])} conflict(s) judged"
                                                                      if m.get("conflicts") else "") + "."]
    if m.get("error"):
        lines += ["", f"Merge stopped: {m['error']}"]
    if r["files"]:
        lines += ["", "## Files touched", ""] + [f"- `{f}`" for f in r["files"][:200]]
    if r["artifacts"]:
        lines += ["", "## Artifacts", ""] + [f"- `{a}`" for a in r["artifacts"][:200]]
    if r["missing_outputs"]:
        lines += ["", "## Outputs the plan named that are missing", ""] + [f"- `{a}`" for a in r["missing_outputs"]]
    return "\n".join(lines) + "\n"


def write(home, mid: str) -> dict:
    from halo_harness.fleet import journal
    from halo_harness.fleet.mission_plan import load_plan
    doc = S.need(home, mid)
    report = build(home, doc, load_plan(home, mid) or {})
    folder = S.folder(home, mid)
    S.write_text(folder, "report.json", json.dumps(report, indent=2, default=str))
    S.write_text(folder, "report.md", markdown(report))
    hub = doc.get("hub") or {}
    journal.append(home, "mission_end", harness=hub.get("id"), harness_name=hub.get("name"), mission=mid,
                   state=doc.get("state"), cost_usd=report["cost"]["total_usd"], reason=doc.get("stop_reason"),
                   parts=len(report["parts"]))
    return report
