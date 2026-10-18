"""halo_harness.fleet.mission_plan -- the hub's lead split for a mission (Halo
3.0.6.0 "Fleet Missions" round R7), modelled on Orchestra's split.py: ONE
model call (`call_model(prompt)` -> str | (str, cost) | {text, cost_usd,
session_id}), through the same provider path as Orchestra's lead
(orchestra/adapters.model_call); tests pass a fake. The prompt carries the
fleet's capability catalog, one compact block per harness, and what only
one harness has (mission_assign.unique_lines). The answer:

    {"parts": [{"id", "title", "brief", "harness", "reason", "needs": [capability names],
                "depends_on": [ids], "claims": [repo-relative paths or globs], "outputs": [files],
                "est_cost_usd", "kind"?: "repo" | "files"}],
     "merge_order": [ids]}

Code checks it (mission_plan_check.normalize; a failed check retries once
with the problems listed), then assigns harnesses by the rules
(mission_assign.assign: pinned, prefer, load, unassignable) and
sequences overlapping claims. `plan.json` keeps the result; MISSION.md and
every `parts/<n>/brief.md` are written from it. `edit` (reassign or drop a
part) re-validates in code only.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from halo_harness.fleet import mission as M
from halo_harness.fleet import mission_store as S
from halo_harness.fleet.mission_doc import brief_md, mission_md
from halo_harness.fleet.mission_plan_check import merge_order, normalize, sequence
from halo_harness.fleet.mission_assign import able, assign, norm_need, unique_lines
from halo_harness.orchestra import jsonl
from halo_harness.orchestra.split import _call, parse_answer

MAX_TOOLS_SHOWN = 30


def make_lead(cwd) -> Callable:
    """The real lead: a fresh bare session through the provider layer (Orchestra's adapters)."""
    from halo_harness.orchestra.adapters import model_call
    return model_call(None, "main", cwd=cwd)


def _hw(cat: dict) -> str:
    hw = cat.get("hardware") or {}
    gpus = ", ".join(f"{g.get('name')} {g.get('vram_gb') or '?'} GB" for g in hw.get("gpu") or [])
    return (f"{hw.get('distro') or hw.get('os') or '?'} {hw.get('release') or ''}, {hw.get('cpu') or '?'} "
            f"({hw.get('cores') or '?'} cores), {hw.get('ram_gb') or '?'} GB RAM" + (f", GPU {gpus}" if gpus else ", no GPU"))


def catalog_block(entries: list, load: dict) -> str:
    out = []
    for e in entries:
        cat = e.get("catalog") or {}
        lines = [f"### {e.get('name')}" + (" (the hub's own harness)" if e.get("local") else "")]
        if cat.get("tags"):
            lines.append("tags: " + ", ".join(map(str, cat["tags"])))
        lines.append("hardware: " + _hw(cat))
        if cat.get("craft_apps"):
            lines.append("craft apps: " + ", ".join(map(str, cat["craft_apps"])))
        for s in cat.get("mcp") or []:
            tools = [str(t.get("name")) for t in s.get("tools") or []] if isinstance(s.get("tools"), list) else []
            more = f" +{len(tools) - MAX_TOOLS_SHOWN} more" if len(tools) > MAX_TOOLS_SHOWN else ""
            lines.append(f"mcp {s.get('name')}: " + (", ".join(tools[:MAX_TOOLS_SHOWN]) + more if tools else "(tools unknown)"))
        if cat.get("skills"):
            lines.append("skills: " + ", ".join(map(str, cat["skills"][:40])))
        models = [str(m.get("id")) for m in cat.get("models") or []][:8]
        if models:
            lines.append("models: " + ", ".join(models))
        clis = [k for k, v in (cat.get("clis") or {}).items() if v]
        if clis:
            lines.append("clis: " + ", ".join(clis))
        if (cat.get("media") or {}).get("comfyui"):
            lines.append("media: ComfyUI")
        lines.append(f"load: {int(load.get(str(e.get('harness')), 0))} live agents")
        out.append("\n".join(lines))
    return "\n\n".join(out)


def prompt(doc: dict, entries: list, load: dict, problems: Optional[list] = None) -> str:
    repo = doc.get("repo")
    where = (f"The mission's repo is `{repo.get('name')}`: a part that changes it is kind \"repo\" (it runs on its own "
             "branch; claims are paths or globs relative to the repo root). A part that only makes files (a report, "
             "a spreadsheet, a scan) is kind \"files\" and leaves its outputs in its own folder."
             if repo else "There is no repo: every part is kind \"files\" and leaves its outputs in its own folder.")
    text = (
        "You are the lead of a fleet mission. Split the goal into parts and give each part to the harness best "
        "placed for it, by what each harness can do.\n\n"
        f"GOAL: {doc.get('goal')}\n" + (f"CONSTRAINTS: {doc['constraints']}\n" if doc.get("constraints") else "")
        + (f"BUDGET: ${float(doc['budget_usd']):.2f} for the whole mission\n" if doc.get("budget_usd") else "")
        + f"\n{where}\n\nTHE FLEET (one block per harness):\n\n{catalog_block(entries, load)}\n\n"
        + ("WHAT ONLY ONE HARNESS HAS (a part that needs it goes there):\n" + "\n".join(unique_lines(entries)) + "\n\n"
           if unique_lines(entries) else "")
        + "Rules: name in `needs` the capabilities a part cannot do without (an MCP server or tool, a craft app, "
        "a CLI such as nmap, a skill, `gpu`, an OS); two parts never claim the same file (parts that must touch "
        "one file run one after the other through depends_on); keep parts independent so they run at the same "
        "time; a part that uses another's output depends on it, reads that part's outputs (or everything it "
        'left, with "take": "all") and, for a repo part, starts from its finished branch. Answer with JSON only:\n'
        '{"parts": [{"id": "1", "title": "one line", "brief": "what to do, in full", "kind": "repo|files", '
        '"harness": "<name>", "reason": "why this harness", "needs": ["gridcraft"], "depends_on": [], '
        '"claims": ["src/report/**"], "outputs": ["report.xlsx"], "take": "outputs", "est_cost_usd": 0.2}], '
        '"merge_order": ["1"]}'
    )
    if problems:
        text += "\n\nYour previous answer had these problems; fix every one:\n" + "\n".join(f"- {p}" for p in problems)
    return text


def finalize(parts: list, order: list, entries: list, prefer: list, load: dict) -> "tuple[list, list]":
    for p in parts:
        assign(p, entries, prefer, load)
    notes = sequence(parts, order)
    for p in parts:
        if p.get("pinned"):
            notes.append(f"part {p['id']} is pinned to {p.get('harness_name')}: {p.get('reason')}")
        elif p.get("unassignable"):
            notes.append(f"part {p['id']} is unassignable: {p['unassignable']}")
    return parts, notes


def write_plan(home, doc: dict, plan: dict) -> None:
    d = S.folder(home, doc["id"])
    jsonl.write_json(d / "plan.json", plan)
    jsonl.write_json(d / "claims.json", {p["id"]: p.get("claims") or [] for p in plan.get("parts") or []})
    for p in plan.get("parts") or []:
        S.write_text(d, f"parts/{p['id']}/brief.md", brief_md(doc, plan, p))
    S.write_text(d, "MISSION.md", mission_md(doc, plan))


def load_plan(home, mid: str) -> Optional[dict]:
    data = jsonl.read_json(S.folder(home, mid) / "plan.json", None)
    return data if isinstance(data, dict) else None


def _commit(home, mid: str, plan: dict, by: str, why: str, cost: float = 0.0) -> dict:
    def apply(doc: dict) -> None:
        if doc["state"] != "planned":
            M.move(doc, "planned", why, by)
        doc["plan_cost_usd"] = round(float(doc.get("plan_cost_usd") or 0.0) + cost, 6)
        doc["parts"] = {p["id"]: M.new_part_state(p) for p in plan["parts"]}
        doc["approved_by"] = None
    doc = S.update(home, mid, apply)
    write_plan(home, doc, plan)
    S.log(home, mid, "planned", parts=len(plan["parts"]), why=why, by=by or None)
    return doc


def plan(home, mid: str, entries: list, *, call_model: Optional[Callable] = None, load: Optional[dict] = None,
         prefer: Optional[list] = None, by: str = "") -> dict:
    """Ask the lead (retry once), check, assign, write. Returns the plan; MissionError (422) when both answers fail."""
    doc = S.need(home, mid)
    if doc["state"] not in ("drafted", "planned", "approved"):
        raise M.MissionError(f"mission {mid} is {doc['state']}; only a mission not yet running is planned again")
    if not entries:
        raise M.MissionError("no harness with a capability catalog to plan for", 409)
    load = dict(load or {})
    prefer = list(prefer if prefer is not None else (doc.get("prefer") or M.prefer(home)))
    call_model = call_model or make_lead(S.folder(home, mid))
    cost, sessions, problems, parts, order = 0.0, [], [], [], []
    for attempt in (1, 2):
        text, spent, sid = _call(call_model, prompt(doc, entries, load, problems if attempt == 2 else None))
        cost += spent
        sessions += [sid] if sid else []
        parts, order, problems = normalize(parse_answer(text), bool(doc.get("repo")))
        if not problems:
            break
        S.log(home, mid, "plan_rejected", attempt=attempt, problems=problems)
    if problems:
        S.update(home, mid, lambda d: d.update(plan_cost_usd=round(float(d.get("plan_cost_usd") or 0) + cost, 6),
                                               plan_problems=problems))
        raise M.MissionError("the lead's plan failed the check twice: " + "; ".join(problems), 422)
    parts, notes = finalize(parts, order, entries, prefer, load)
    result = {"v": 1, "mission": mid, "created": time.time(), "attempts": attempt, "lead_cost_usd": round(cost, 6),
              "lead_sessions": sessions, "parts": parts, "merge_order": merge_order(parts, order), "notes": notes,
              "harnesses": [{"harness": e.get("harness"), "name": e.get("name"), "local": bool(e.get("local"))}
                            for e in entries], "prefer": prefer}
    _commit(home, mid, result, by, "planned by the lead" if doc["state"] == "drafted" else "planned again", cost)
    return result


def edit(home, mid: str, pid: str, entries: list, *, harness: Optional[str] = None, drop: bool = False,
         load: Optional[dict] = None, by: str = "") -> dict:
    """Reassign or drop one part, then re-check in code (no model call). MissionError on a bad edit."""
    doc, old = S.need(home, mid), load_plan(home, mid)
    if doc["state"] not in ("planned", "approved") or not old:
        raise M.MissionError(f"mission {mid} is {doc['state']}; parts are edited before it runs")
    parts = [dict(p, depends_on=list(p.get("depends_on") or []), sequenced=[]) for p in old["parts"]]
    part = next((p for p in parts if p["id"] == str(pid)), None)
    if part is None:
        raise M.MissionError(f"mission {mid} has no part {pid!r}", 404)
    if drop:
        parts = [p for p in parts if p["id"] != part["id"]]
        for p in parts:
            p["depends_on"] = [d for d in p["depends_on"] if d != part["id"]]
        what = f"dropped part {part['id']} ({part.get('title')})"
    elif harness:
        low = harness.strip().lower()
        target = next((e for e in entries if low in (str(e.get("harness")).lower(), str(e.get("name") or "").lower())), None)
        if target is None:
            raise M.MissionError(f"no harness {harness!r} in this fleet", 404)
        missing = [n for n in part.get("needs") or [] if not able([target], [norm_need(n)])]
        if missing:
            raise M.MissionError(f"{target.get('name')} does not have {', '.join(missing)}", 422)
        part.update(harness=str(target.get("harness")), reason=f"{target.get('name')}: the owner's choice")
        what = f"part {part['id']} to {target.get('name')}"
    else:
        raise M.MissionError("an edit needs a harness or drop: true", 422)
    seq = {o["id"]: {x.get("after") for x in o.get("sequenced") or []} for o in old["parts"]}
    for p in parts:  # the code's own sequencing is recomputed below
        p["depends_on"] = [d for d in p["depends_on"] if d not in seq.get(p["id"], set())]
    fixed = {p["id"]: (p.get("harness"), p.get("reason")) for p in parts if p["id"] == part["id"] and not drop}
    parts, notes = finalize(parts, [x for x in old.get("merge_order") or [] if any(p["id"] == x for p in parts)],
                            entries, old.get("prefer") or [], load or {})
    for p in parts:
        if p["id"] in fixed:
            p["harness"], p["reason"] = fixed[p["id"]]
            p["harness_name"] = next((e.get("name") for e in entries if str(e.get("harness")) == p["harness"]), p["harness"])
            p["pinned"] = False
    plan_ = {**old, "parts": parts, "merge_order": merge_order(parts, old.get("merge_order") or []), "notes": notes,
             "edited": time.time()}
    def note(d: dict) -> None:
        M.decide(d, what, by)
    S.update(home, mid, note)
    _commit(home, mid, plan_, by, what)
    return plan_
