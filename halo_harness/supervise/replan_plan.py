"""halo_harness.supervise.replan_plan -- the lead's new plan for the lanes left,
checked against the run (Halo 3.1.8.0 R2, docs/SUPERVISE.md "Replanning").

The lead answers (replan_prompt.py) for the lanes LEFT only:

    {"jobs": [{"id": "job-2", "title", "claims", "model": "<ref>", "retry": true},     keep job-2: a model, a retry
              {"id": "job-3a", "from": "job-3", "title", "claims": [part of job-3's]},  a split: two or more parts
              {"id": "job-3b", "from": "job-3", "title", "claims": [the rest]},
              {"id": "job-9", "assist": "job-4", "title", "claims": [job-4's], "bio": "<specialist>"}],
     "why": "one line"}

`check(run_dir, answer)` makes the run's whole plan from it: the merged lanes
pinned as split.json has them; each lane left kept (its own id and claims,
maybe a new `model` / `bio`, maybe `retry`) or split (two or more parts whose
claims divide its claims; a later job that ran after it runs after every
part); a specialist is a new lane with the same claims marked `assist`, which
the lane it assists runs after, taking its summary. New lanes take the next
free lane numbers. The whole plan then passes plan_check.plan_problems (ids,
titles, claims, references, cycles, overlaps, the bio/model preflight).
`moves` say what changed lane by lane; `diff_lines(moves)` is the goal_plan
row's detail (replan_moves.py). A kept lane whose worker runs again (`requeue`): a retry, a
lane it assists, a model or bio change on a lane already written.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from halo_harness.orchestra.index import covers, overlaps
from halo_harness.supervise.drift import lanes_left, plan_lanes

MAX_LANE = 50


@dataclass
class Checked:
    problems: list = field(default_factory=list)
    jobs: list = field(default_factory=list)       # the whole plan, split.json's shape, by lane number
    moves: list = field(default_factory=list)
    retired: list = field(default_factory=list)    # lane numbers a split replaced
    requeue: list = field(default_factory=list)    # kept lane numbers whose worker runs again
    assists: dict = field(default_factory=dict)    # new lane number -> the job id it assists
    added: list = field(default_factory=list)      # new lane numbers
    notes: dict = field(default_factory=dict)      # lane number -> the context its hand-off carries
    before: list = field(default_factory=list)     # the old jobs of the lanes that changed
    proposal: list = field(default_factory=list)   # the lead's jobs as given (replan.plan.json)


def _keys(job: dict) -> list:
    claims = job.get("claims") if isinstance(job, dict) else None
    return [str(c) for c in claims if str(c).strip()] if isinstance(claims, list) else []


def _set(job: dict, p: dict) -> dict:
    from halo_harness.orchestra.forecast import est_dict
    for k in ("title", "model", "bio"):
        if str(p.get(k) or "").strip():
            job[k] = str(p[k]).strip()
    if est_dict(p.get("est_tokens")):
        job["est_tokens"] = est_dict(p.get("est_tokens"))
    for k in ("after", "handoff"):
        if k in p:
            job[k] = p[k]
    return job


def _remap(job: dict, parts: dict) -> None:
    """References to a split lane point at every one of its parts."""
    after = [x for a in job.get("after") or [] for x in parts.get(str(a), [str(a)])]
    job["after"] = list(dict.fromkeys(after))
    h = dict(job.get("handoff") or {})
    if h.get("needs"):
        h["needs"] = [dict(nd, **{"from": x}) for nd in h["needs"] if isinstance(nd, dict)
                      for x in parts.get(str(nd.get("from")), [str(nd.get("from"))])]
    job["handoff"] = {k: v for k, v in h.items() if v}
    for k in ("after", "handoff"):
        if not job[k]:
            job.pop(k)


def check(run_dir, answer, *, state_dir=None) -> Checked:
    out = Checked()
    jobs, files = plan_lanes(run_dir)
    left = lanes_left(jobs, files)
    left_ids = {str(jobs[n].get("id")): n for n in left}
    pinned = {str(j.get("id")) for n, j in jobs.items() if n not in left}
    given = answer.get("jobs") if isinstance(answer, dict) else None
    if not isinstance(given, list) or not given:
        out.problems = ['answer with {"jobs": [...]}: one entry per lane left, by its own id or as the parts of its split']
        return out
    out.proposal = [p for p in given if isinstance(p, dict)]
    kept, parts, assists, seen, bad = {}, {}, [], set(), out.problems
    for i, p in enumerate(given, 1):
        pid = str(p.get("id") or "").strip() if isinstance(p, dict) else ""
        if not pid:
            bad.append(f"job #{i} has no id")
            continue
        if pid in seen:
            bad.append(f"two jobs are called {pid}: give each its own id")
            continue
        seen.add(pid)
        src, helps = str(p.get("from") or "").strip(), str(p.get("assist") or "").strip()
        if p.get("retry") and (pid not in left_ids or src or helps):
            bad.append(f"{pid} retries, but only a lane left kept by its own id retries")
        if pid in pinned:
            bad.append(f"{pid} is merged: it is pinned, leave it out of the plan")
        elif pid in left_ids:
            if src or helps:
                bad.append(f"{pid} keeps its own lane: a split part or a specialist takes a new id")
            elif "claims" in p and set(_keys(p)) != set(_keys(jobs[left_ids[pid]])):  # no claims: the same ones
                bad.append(f"{pid} keeps its id but changes its claims: to move units, split it "
                           f"(new ids with \"from\": \"{pid}\")")
            else:
                kept[pid] = p
        elif src:
            if src not in left_ids:
                bad.append(f"{pid} splits {src!r}, which is " + ("merged" if src in pinned else "not a lane left"))
                continue
            parts.setdefault(src, []).append(p)
            outside = [k for k in _keys(p) if not any(covers(s, k) for s in _keys(jobs[left_ids[src]]))]
            if outside or not _keys(p):
                bad.append(f"{pid} is a part of {src} but claims " + (", ".join(outside) or "nothing")
                           + f": a part claims some of {src}'s units")
        elif helps:
            if helps not in left_ids:
                bad.append(f"{pid} assists {helps!r}, which is " + ("merged" if helps in pinned else "not a lane left"))
                continue
            own = _keys(jobs[left_ids[helps]])
            if any(not any(overlaps(k, o) for o in own) for k in _keys(p)):
                bad.append(f"{pid} assists {helps} but claims units outside {helps}'s: it takes the same claims")
            assists.append(p)
        else:
            bad.append(f"{pid} is not a lane left: keep a lane by its id, split one (\"from\") or add a specialist "
                       f"(\"assist\")")
    for jid, n in left_ids.items():
        if jid in parts and jid in kept:
            bad.append(f"{jid} is kept and split at once: one or the other")
        elif jid in parts:
            got = [k for p in parts[jid] for k in _keys(p)]
            if len(parts[jid]) < 2:
                bad.append(f"{jid} is split into one part: a split gives two or more (or keep {jid} by its id)")
            missing = [k for k in _keys(jobs[n]) if not any(overlaps(k, g) for g in got)]
            if missing:
                bad.append(f"the split of {jid} leaves {', '.join(missing)} unclaimed")
        elif jid not in kept:
            bad.append(f"{jid} is a lane left and the plan drops it: keep it by its id or split it (\"from\": \"{jid}\")")
    bad += [f"{a['id']} assists {a['assist']}, which the plan splits: a specialist assists a kept lane"
            for a in assists if a["assist"] in parts]
    if not bad:
        _build(out, run_dir, jobs, files, left_ids, kept, parts, assists, state_dir)
    return out


def _build(out: Checked, run_dir, jobs: dict, files: dict, left_ids: dict, kept: dict, parts: dict, assists: list,
           state_dir) -> None:
    from halo_harness.orchestra import plan as P
    nxt = max(list(jobs) + list(files) + [0]) + 1
    plan, by_id, ids_of = {}, {}, {}
    for n, job in jobs.items():
        if str(job.get("id")) not in left_ids:
            plan[n] = dict(job)                                  # pinned: exactly as split.json has it
        elif str(job.get("id")) in kept:
            plan[n] = _set({k: v for k, v in job.items() if k != "replan_note"}, kept[str(job["id"])])
    for src, ps in parts.items():
        old = jobs[left_ids[src]]
        for p in ps:
            base = {k: old[k] for k in ("after", "handoff") if old.get(k)}
            plan[nxt] = _set(dict(base, id=str(p["id"]), title="", claims=_keys(p)), p)
            ids_of.setdefault(src, []).append(plan[nxt]["id"])
            nxt += 1
        out.retired.append(left_ids[src])
        out.before.append(dict(old))
    for a in assists:
        target = left_ids[a["assist"]]
        plan[nxt] = _set({"id": str(a["id"]), "title": "", "claims": _keys(a) or _keys(jobs[target]),
                          "assist": a["assist"]}, {k: v for k, v in a.items() if k not in ("after", "handoff")})
        t = plan[target]
        t["after"] = list(dict.fromkeys(list(t.get("after") or []) + [plan[nxt]["id"]]))
        h = dict(t.get("handoff") or {})
        h["needs"] = list(h.get("needs") or []) + [{"from": plan[nxt]["id"], "take": "summary"}]
        t["handoff"] = h
        out.assists[nxt] = a["assist"]
        nxt += 1
    for n, job in plan.items():
        if n in jobs and str(job.get("id")) not in left_ids:  # pinned: never rewritten
            if pinned_refs(job, ids_of):
                out.problems.append(f"{job['id']} is merged and runs after {', '.join(pinned_refs(job, ids_of))}, "
                                    "which the plan splits: a merged lane stays as it is")
        else:
            job.update(worker=n, order=int(job.get("order") or n) if n in jobs else n)
            _remap(job, ids_of)
        by_id[str(job["id"])] = n
    out.jobs = [plan[n] for n in sorted(plan)]
    out.added = sorted(n for n in plan if n not in jobs)
    if max(list(plan) + [0]) > MAX_LANE:
        out.problems.append(f"the plan would need lane {max(plan)}, but a run has at most {MAX_LANE} lanes")
    out.problems += [p["text"] for p in P.check(run_dir, out.jobs, state_dir=state_dir)]
    from halo_harness.supervise.replan_moves import moves_of
    moves_of(out, run_dir, jobs, files, left_ids, kept, parts, plan, by_id)


def pinned_refs(job: dict, ids_of: dict) -> list:
    """The split lanes a job refers to (after or needs)."""
    refs = [str(a) for a in job.get("after") or []] + [str(nd.get("from")) for nd in (job.get("handoff") or {}).get("needs") or []
                                                       if isinstance(nd, dict)]
    return [r for r in dict.fromkeys(refs) if r in ids_of]
