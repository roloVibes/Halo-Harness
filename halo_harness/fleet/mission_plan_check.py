"""halo_harness.fleet.mission_plan_check -- the lead's answer made into a plan,
checked in code (Halo 3.0.6.0 "Fleet Missions" round R7).

`normalize(answer, has_repo)` -> `(parts, merge_order, problems)`: parts are
renumbered "1".."N" (the lead's own ids are mapped, `depends_on` and
`merge_order` with them); every part needs a title and a brief; claims are
repo-relative; a part is `kind: repo` (it edits the mission's repo on its own
branch) or `kind: files` (it works in `artifacts/<n>/` of the mission folder,
which is then its claim); `take` (3.0.9.0) is `outputs` (the default: from each
dependency it reads that part's outputs and hand-back) or `all` (the
dependency's whole artifacts folder). `sequence(parts, order)` makes two repo parts whose
claims overlap run one after the other (the later waits for the earlier) and
says why; `cycles(parts)` finds a dependency loop. `ready(plan)` lists what
stops an approval (an unassignable part, a part with no harness).
"""

from __future__ import annotations

from typing import Optional

from halo_harness.fleet.mission_claims import bad_claim, norm_claim, overlap

MAX_PARTS = 20


def _strs(value) -> list:
    if isinstance(value, str):
        value = [value]
    return [str(v).strip() for v in value or [] if str(v).strip()] if isinstance(value, (list, tuple)) else []


def _cost(value) -> float:
    try:
        return max(0.0, round(float(value), 4))
    except (TypeError, ValueError):
        return 0.0


def normalize(data, has_repo: bool) -> "tuple[list, list, list]":
    if not isinstance(data, dict) or not isinstance(data.get("parts"), list) or not data["parts"]:
        return [], [], ['the answer must be a JSON object {"parts": [...], "merge_order": [...]} with at least one part']
    raw = [p for p in data["parts"] if isinstance(p, dict)]
    problems = [] if len(raw) == len(data["parts"]) else ["every part must be a JSON object"]
    if len(raw) > MAX_PARTS:
        problems.append(f"{len(raw)} parts; a mission has at most {MAX_PARTS}")
    ids = {}
    for i, p in enumerate(raw, 1):
        ids.setdefault(str(p.get("id") if p.get("id") not in (None, "") else i), str(i))
    parts = []
    for i, p in enumerate(raw, 1):
        n = str(i)
        title, brief = " ".join(str(p.get("title") or "").split())[:160], str(p.get("brief") or "").strip()
        if not title:
            problems.append(f"part {n} has no title")
        if not brief:
            problems.append(f"part {n} has no brief")
        deps = []
        for d in _strs(p.get("depends_on")):
            if d not in ids:
                problems.append(f"part {n} depends on {d!r}, which is not a part's id")
            elif ids[d] == n:
                problems.append(f"part {n} depends on itself")
            elif ids[d] not in deps:
                deps.append(ids[d])
        claims = [norm_claim(c) for c in _strs(p.get("claims"))]
        problems += [f"part {n}: {bad_claim(c)}" for c in claims if bad_claim(c)]
        kind = str(p.get("kind") or "").lower()
        kind = "repo" if has_repo and (kind == "repo" or (kind != "files" and claims)) else "files"
        outputs = [norm_claim(o) for o in _strs(p.get("outputs"))]
        if kind == "files":
            home = f"artifacts/{n}"
            outputs = [o if o.startswith(home + "/") else f"{home}/{o.split('/')[-1]}" for o in outputs]
            claims = [f"{home}/**"]
        parts.append({"id": n, "title": title, "brief": brief, "kind": kind, "harness": str(p.get("harness") or ""),
                      "reason": " ".join(str(p.get("reason") or "").split())[:300], "needs": _strs(p.get("needs")),
                      "depends_on": deps, "claims": claims, "outputs": outputs, "est_cost_usd": _cost(p.get("est_cost_usd")),
                      "sequenced": [], "take": "all" if str(p.get("take") or "").strip().lower() == "all" else "outputs"})
    order = [ids[str(x)] for x in data.get("merge_order") or [] if str(x) in ids] if isinstance(data.get("merge_order"), list) else []
    problems += cycles(parts)
    return parts, merge_order(parts, order), problems


def merge_order(parts: list, order: list) -> list:
    """The repo parts in merge order: the lead's order first (deduplicated), then the rest by id."""
    repo = [p["id"] for p in parts if p.get("kind") == "repo"]
    out = [x for i, x in enumerate(order) if x in repo and x not in order[:i]]
    return out + [x for x in repo if x not in out]


def _reach(parts: list, start: str) -> set:
    """Every part `start` waits for, directly or not."""
    deps = {p["id"]: set(p.get("depends_on") or []) for p in parts}
    seen, todo = set(), list(deps.get(start, ()))
    while todo:
        x = todo.pop()
        if x not in seen:
            seen.add(x)
            todo += list(deps.get(x, ()))
    return seen


def cycles(parts: list) -> list:
    return [f"part {p['id']} waits for itself through its depends_on" for p in parts if p["id"] in _reach(parts, p["id"])]


def sequence(parts: list, order: list) -> list:
    """Overlapping claims of two repo parts become a `depends_on` (the later waits); the notes say why."""
    pos = {x: i for i, x in enumerate(order)}
    repo = [p for p in parts if p.get("kind") == "repo"]
    notes = []
    for i, a in enumerate(repo):
        for b in repo[i + 1:]:
            hit = next(((x, y) for x in a["claims"] for y in b["claims"] if overlap(x, y)), None)
            if hit is None:
                continue
            first, later = (a, b) if pos.get(a["id"], 99) <= pos.get(b["id"], 99) else (b, a)
            if first["id"] in _reach(parts, later["id"]) or later["id"] in _reach(parts, first["id"]):
                continue
            later["depends_on"].append(first["id"])
            why = f"part {later['id']} waits for part {first['id']}: both claim {hit[0]!r} / {hit[1]!r}"
            later.setdefault("sequenced", []).append({"after": first["id"], "because": why})
            notes.append(why)
    return notes


def ready(plan: Optional[dict]) -> list:
    if not isinstance(plan, dict) or not plan.get("parts"):
        return ["the mission has no plan yet"]
    out = [f"part {p['id']} is unassignable: {p['unassignable']}" for p in plan["parts"] if p.get("unassignable")]
    out += [f"part {p['id']} has no harness" for p in plan["parts"] if not p.get("harness") and not p.get("unassignable")]
    return out
