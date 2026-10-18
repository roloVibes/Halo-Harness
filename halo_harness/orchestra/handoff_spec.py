"""halo_harness.orchestra.handoff_spec -- what a lane hands on and what it
takes (Halo 3.0.9.0 round R1), as the lead declares it in its job answer or
goal.json pre-declares it under `handoffs:`:

    {"title": "...", "claims": [...],
     "handoff": {"gives": [{"name": "notes", "kind": "files" | "summary" | "artifact", "paths": ["notes.md"]}],
                 "needs": [{"from": "job-1", "take": "all" | "summary" | "<a name job-1 gives>"}]},
     "after": ["job-1"]}

    goal.json  "handoffs": {"job-2": {"needs": [...], "gives": [...], "after": [...]}}

Every lane gives its summary (its final reply) and the units it wrote
whether it declares them or not, so `take: summary` and `take: all` always
name something; any other `take` names one of the upstream job's `gives`.
`from` and `after` name real jobs (`job-<n>`, the job's position in the
answer, or the lead's own `id` for it), never the job itself, and the
upstreams (`after` plus every `needs.from`) never form a cycle. A job with
upstreams sits one layer below its deepest upstream; with nothing declared
every job is in layer 0 and the run is today's all-at-once.
"""

from __future__ import annotations

from typing import Optional

GIVE_KINDS = ("files", "summary", "artifact")
BUILTIN_TAKES = ("all", "summary")


def _strs(value) -> list:
    if isinstance(value, str):
        value = [value]
    return [str(v).strip() for v in value if str(v).strip()] if isinstance(value, (list, tuple)) else []


def ref_map(raw_jobs: list) -> dict:
    """Every name a job may be called by -> its job id (`job-<n>`)."""
    out: dict = {}
    for i, job in enumerate(raw_jobs, 1):
        jid = f"job-{i}"
        for name in (jid, str(i)) + ((str(job.get("id")).strip(),) if isinstance(job, dict) and job.get("id") not in (None, "") else ()):
            out.setdefault(name, jid)
    return out


def shape_problems(decl, where: str) -> list:
    """Problems with the shape of one declaration (`{handoff?, after?}` or the
    goal's `{gives?, needs?, after?}`), before any job ids are known."""
    if decl in (None, {}):
        return []
    if not isinstance(decl, dict):
        return [f"{where}: a hand-off is an object with gives, needs and after"]
    body = decl.get("handoff") if isinstance(decl.get("handoff"), dict) else decl
    problems = []
    if "handoff" in decl and not isinstance(decl.get("handoff"), dict):
        problems.append(f"{where}: handoff must be an object {{gives: [...], needs: [...]}}")
    gives, needs = body.get("gives", []), body.get("needs", [])
    if not isinstance(gives, list):
        problems.append(f"{where}: gives must be a list")
        gives = []
    if not isinstance(needs, list):
        problems.append(f"{where}: needs must be a list")
        needs = []
    names = set()
    for k, g in enumerate(gives, 1):
        if not isinstance(g, dict) or not str(g.get("name") or "").strip():
            problems.append(f"{where}: gives[{k}] needs a name")
            continue
        name = str(g["name"]).strip()
        if name in names:
            problems.append(f"{where}: gives {name!r} twice")
        names.add(name)
        if str(g.get("kind") or "") not in GIVE_KINDS:
            problems.append(f"{where}: gives {name!r} has kind {g.get('kind')!r}; use files, summary or artifact")
        if "paths" in g and not isinstance(g.get("paths"), list):
            problems.append(f"{where}: gives {name!r}: paths must be a list")
    for k, n in enumerate(needs, 1):
        if not isinstance(n, dict) or not str(n.get("from") or "").strip():
            problems.append(f"{where}: needs[{k}] must say which job it is from: {{from: job-1, take: summary}}")
        elif not str(n.get("take") or "").strip():
            problems.append(f"{where}: needs[{k}] must say what it takes: all, summary or an artifact's name")
    after = decl.get("after", body.get("after", []))
    if not isinstance(after, (list, str)):
        problems.append(f"{where}: after must be a list of job ids")
    return problems


def clean(decl) -> "tuple[dict, list]":
    """`(handoff, after)` from one declaration, refs still as written; ({}, []) for none."""
    if not isinstance(decl, dict):
        return {}, []
    body = decl.get("handoff") if isinstance(decl.get("handoff"), dict) else decl
    gives = []
    for g in body.get("gives") or [] if isinstance(body.get("gives"), list) else []:
        if isinstance(g, dict) and str(g.get("name") or "").strip():
            row = {"name": str(g["name"]).strip(), "kind": str(g.get("kind") or "")}
            if _strs(g.get("paths")):
                row["paths"] = _strs(g.get("paths"))
            gives.append(row)
    needs = [{"from": str(n.get("from")).strip(), "take": str(n.get("take") or "").strip()}
             for n in (body.get("needs") or [] if isinstance(body.get("needs"), list) else [])
             if isinstance(n, dict) and str(n.get("from") or "").strip()]
    handoff = {k: v for k, v in (("gives", gives), ("needs", needs)) if v}
    return handoff, _strs(decl.get("after", body.get("after")))


def merge_decl(lead: tuple, goal: tuple) -> tuple:
    """The goal's pre-declaration wins field by field over the lead's."""
    (lh, la), (gh, ga) = lead, goal
    handoff = dict(lh)
    handoff.update({k: v for k, v in gh.items() if v})
    return handoff, (ga or la)


def resolve(decls: list, refs: dict) -> "tuple[list, list]":
    """`decls` = [(handoff, after)] per job in order; every ref made a job id.
    Returns `(resolved, problems)`."""
    out, problems = [], []
    for i, (handoff, after) in enumerate(decls, 1):
        me = f"job-{i}"
        needs, ups = [], []
        for n in handoff.get("needs") or []:
            jid = refs.get(n["from"])
            if jid is None:
                problems.append(f"job {i} needs {n['from']!r}, which is not one of the jobs")
            elif jid == me:
                problems.append(f"job {i} needs its own hand-off")
            else:
                needs.append({"from": jid, "take": n["take"]})
        for a in after:
            jid = refs.get(a)
            if jid is None:
                problems.append(f"job {i} runs after {a!r}, which is not one of the jobs")
            elif jid == me:
                problems.append(f"job {i} runs after itself")
            elif jid not in ups:
                ups.append(jid)
        h = {k: v for k, v in (("gives", handoff.get("gives") or []), ("needs", needs)) if v}
        out.append((h, ups))
    gives = {f"job-{i}": {g["name"] for g in h.get("gives") or []} for i, (h, _a) in enumerate(out, 1)}
    for i, (h, _a) in enumerate(out, 1):
        for n in h.get("needs") or []:
            if n["take"] not in BUILTIN_TAKES and n["take"] not in gives.get(n["from"], set()):
                problems.append(f"job {i} takes {n['take']!r} from {n['from']}, which gives "
                                + (", ".join(sorted(gives[n['from']])) or "only its summary and units") + " (or use all / summary)")
    deps = {f"job-{i}": upstream_ids(h, a) for i, (h, a) in enumerate(out, 1)}
    problems += [f"{jid} waits for itself through its hand-offs" for jid in deps if jid in reach(deps, jid)]
    return out, problems


def upstream_ids(handoff: dict, after: list) -> list:
    """`after` plus every `needs.from`, in order, each once."""
    out = list(after or [])
    for n in (handoff or {}).get("needs") or []:
        if n.get("from") and n["from"] not in out:
            out.append(n["from"])
    return out


def reach(deps: dict, start: str) -> set:
    seen, todo = set(), list(deps.get(start, ()))
    while todo:
        x = todo.pop()
        if x not in seen:
            seen.add(x)
            todo += list(deps.get(x, ()))
    return seen


def layers(deps: dict) -> dict:
    """`{job id: layer}`: 0 without upstreams, else one below the deepest (a cycle counts as 0)."""
    memo: dict = {}

    def depth(jid: str, path: tuple) -> int:
        if jid in memo:
            return memo[jid]
        if jid in path:
            return 0
        ups = [u for u in deps.get(jid) or [] if u in deps]
        memo[jid] = 0 if not ups else 1 + max(depth(u, path + (jid,)) for u in ups)
        return memo[jid]
    return {jid: depth(jid, ()) for jid in deps}


def edge_label(handoff: Optional[dict], upstream: str) -> str:
    """What the edge upstream -> this job carries: the takes from it, else `after`."""
    takes = [n["take"] for n in (handoff or {}).get("needs") or [] if n.get("from") == upstream]
    return " + ".join(dict.fromkeys(takes)) if takes else "after"
