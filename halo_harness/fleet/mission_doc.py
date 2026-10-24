"""halo_harness.fleet.mission_doc -- the readable side of a mission (Halo
3.0.6.0 "Fleet Missions" round R7): `MISSION.md` (the goal, the plan as a
table, who does what and why), each part's `brief.md`, and the plain-text
plan table `halo fleet mission` prints. Text in, text out; no model.
"""

from __future__ import annotations

import time

GUIDE = ("Every part sees this file and its own brief. A part edits only what it claims: the claims of two parts "
         "never overlap (two that would are run one after the other), and an edit outside a part's claims is "
         "refused on its harness and raised to the owner. Repo parts work on their own branch "
         "`mission/<id>/<part>` and are merged one at a time in the merge order; files parts leave their "
         "outputs in `artifacts/<part>/`. Every tool call runs under the owner's permission rules of the "
         "harness it runs on.")


def _cell(text, n: int = 80) -> str:
    one = " ".join(str(text or "").split()).replace("|", "/")
    return one if len(one) <= n else one[:n - 3] + "..."


def _who(p: dict) -> str:
    if p.get("unassignable"):
        return "(unassignable)"
    name = str(p.get("harness_name") or p.get("harness") or "?")
    return name + (" (pinned)" if p.get("pinned") else "")


def mission_md(doc: dict, plan: dict) -> str:
    parts = (plan or {}).get("parts") or []
    est = sum(float(p.get("est_cost_usd") or 0) for p in parts)
    budget = doc.get("budget_usd")
    head = [f"# Mission {doc['id']}", "", f"**Goal:** {doc.get('goal')}", ""]
    if doc.get("constraints"):
        head += [f"**Constraints:** {doc['constraints']}", ""]
    head += [f"**State:** {doc.get('state')} | hub {(doc.get('hub') or {}).get('name') or '?'} | "
             f"{len(parts)} part(s) | est. ${est:.2f}" + (f" of a ${float(budget):.2f} budget" if budget else ""), ""]
    if doc.get("lineup"):  # 3.2.1.0 R1: the lineup the mission was started with
        head += [f"**Lineup:** {doc['lineup']}", ""]
    if doc.get("metadata"):  # 3.2.0.0 R4: what the pack whose lineup started it says
        head += ["**Metadata:** " + ", ".join(f"{k}={v}" for k, v in doc["metadata"].items()), ""]
    if doc.get("repo"):
        head += [f"**Repo:** {doc['repo'].get('name')} from {str(doc['repo'].get('base') or '')[:12]}; merged branch "
                 f"`mission/{doc['id']}/merged`", ""]
    rows = ["## Plan", "", "| Part | Title | Harness | Why | Needs | Claims | Depends on | Est. $ |",
            "|---|---|---|---|---|---|---|---|"]
    for p in parts:
        rows.append(f"| {p['id']} ({p.get('kind')}) | {_cell(p.get('title'), 60)} | {_cell(_who(p), 40)} | "
                    f"{_cell(p.get('reason'), 90)} | {_cell(', '.join(p.get('needs') or []) or '-', 40)} | "
                    f"{_cell(', '.join(p.get('claims') or []) or '-', 60)} | {', '.join(p.get('depends_on') or []) or '-'} | "
                    f"{float(p.get('est_cost_usd') or 0):.2f} |")
    order = (plan or {}).get("merge_order") or []
    rows += ["", f"Merge order (repo parts): {', '.join(order) if order else 'none (no repo part)'}", ""]
    notes = list((plan or {}).get("notes") or [])
    if notes:
        rows += ["## Notes", ""] + [f"- {n}" for n in notes] + [""]
    rows += ["## Who does what", ""]
    for p in parts:
        rows.append(f"- **Part {p['id']} on {_who(p)}**: {p.get('title')}. {p.get('reason') or ''}".rstrip())
    rows += ["", "## How the parts work together", "", GUIDE, ""]
    return "\n".join(head + rows)


def brief_md(doc: dict, plan: dict, part: dict) -> str:
    n = part["id"]
    lines = [f"# Mission {doc['id']}, part {n}: {part.get('title')}", "",
             f"You run one part of a fleet mission on {_who(part).replace(' (pinned)', '')}. Other harnesses run the "
             "other parts at the same time; MISSION.md has the whole plan.", "",
             "## The mission", "", f"Goal: {doc.get('goal')}"]
    if doc.get("constraints"):
        lines.append(f"Constraints: {doc['constraints']}")
    lines += ["", "## Your part", "", str(part.get("brief") or "").strip(), "", "## What you may edit (your claims)", ""]
    lines += [f"- `{c}`" for c in part.get("claims") or []] or ["- nothing: this part only reads"]
    lines += ["", "An edit anywhere else is refused: another part owns it.", ""]
    if part.get("kind") == "repo":
        lines += [f"Work in your folder, a git worktree on branch `mission/{doc['id']}/{n}`. Do not commit: the mission "
                  "commits your worktree when you finish and merges it in the merge order.", ""]
    else:
        lines += [f"Your folder is the mission folder; leave your outputs in `artifacts/{n}/`.", ""]
    if part.get("outputs"):
        lines += ["## What to leave behind", ""] + [f"- `{o}`" for o in part["outputs"]] + [""]
    if part.get("depends_on"):
        lines += ["## Before you", "", "Parts " + ", ".join(part["depends_on"]) + " finished before you started; "
                  "their outputs are under `artifacts/<part>/` and their notes in `parts/<part>/handback.md`.", ""]
    lines += ["End your reply with a short hand-back: what you did, the files you changed or made, and anything the "
              "owner should know.", ""]
    return "\n".join(lines)


def _lineup_lines(doc: dict) -> "list[str]":
    """3.2.1.0 R1: `  lineup: <name>` (and the pack's metadata) for a mission started with a lineup."""
    name = doc.get("lineup") or (doc.get("metadata") or {}).get("lineup")  # named, or the active pack lineup's
    out = [f"  lineup: {name}"] if name else []
    meta = {k: v for k, v in (doc.get("metadata") or {}).items() if k != "lineup"}
    if meta:
        out.append("  metadata: " + ", ".join(f"{k}={v}" for k, v in meta.items()))
    return out


def plan_table(doc: dict, plan: dict) -> str:
    """The plan as `halo fleet mission new|plan` prints it."""
    parts = (plan or {}).get("parts") or []
    states = doc.get("parts") or {}
    out = [f"Mission {doc['id']} ({doc.get('state')}): {doc.get('goal')}"] + _lineup_lines(doc)
    if not parts:
        return "\n".join(out + ["  (no plan yet)"])
    width = max(8, *(len(_who(p)) for p in parts))
    for p in parts:
        st = (states.get(p["id"]) or {}).get("state") or "pending"
        dep = f"  after {','.join(p['depends_on'])}" if p.get("depends_on") else ""
        out.append(f"  {p['id']:>2}  {_who(p):<{width}}  {st:<8}  {_cell(p.get('title'), 60)}{dep}")
        out.append(f"      why: {_cell(p.get('reason'), 110)}")
        if p.get("claims"):
            out.append(f"      claims: {_cell(', '.join(p['claims']), 110)}")
    for note in (plan or {}).get("notes") or []:
        out.append(f"  note: {note}")
    if (plan or {}).get("merge_order"):
        out.append(f"  merge order: {', '.join(plan['merge_order'])}")
    return "\n".join(out)


def status_table(doc: dict) -> str:
    """Parts by harness with their state and cost (`halo fleet mission status <id>`, the run's live table)."""
    out = [f"Mission {doc['id']} {doc.get('state')}  ${float(doc.get('plan_cost_usd') or 0) + sum(float(p.get('cost_usd') or 0) for p in (doc.get('parts') or {}).values()):.4f}"
           f"  {time.strftime('%H:%M:%S', time.localtime(doc.get('updated') or time.time()))}"] + _lineup_lines(doc)
    by: dict = {}
    for pid, p in sorted((doc.get("parts") or {}).items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        by.setdefault(str(p.get("harness_name") or p.get("harness") or "?"), []).append((pid, p))
    for name, rows in sorted(by.items()):
        out.append(f"  {name}")
        for pid, p in rows:
            note = p.get("waiting") if p.get("state") == "waiting" else p.get("error")  # 3.2.1.0 R3: the waits line
            err = f"  {_cell(note, 70)}" if note else ""
            out.append(f"    part {pid:>2}  {p.get('state') or 'pending':<8}  ${float(p.get('cost_usd') or 0):.4f}{err}")
            out += [f"      {_cell(p['replanned'], 110)}"] if p.get("replanned") else []
    if doc.get("stop_reason"):
        out.append(f"  reason: {doc['stop_reason']}")
    return "\n".join(out)
