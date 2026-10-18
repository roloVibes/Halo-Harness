"""halo_harness.orchestra.plan_check -- the checks an edited plan passes
before a review run takes it (Halo 3.0.9.0 round R2; `workflow.validate_plan`
re-exports `validate_plan`).

A plan is a list of jobs in split.json's shape plus the hand-off fields
(orchestra/handoff_spec.py) and, optionally, the worker's `bio` and `model`:

    {"id": "job-2", "title": "write remove_item", "claims": ["basket.py#remove_item"],
     "after": ["job-1"], "handoff": {"gives": [...], "needs": [{"from": "job-1", "take": "summary"}]},
     "bio": "coder", "model": "or:vendor/model"}

`plan_problems(jobs, unit_keys=..., cwd=..., state_dir=...)` answers one row
per problem, `{"jobs": [the job ids it is about], "field", "text"}` (Studio
outlines those cards and prints the text); `validate_plan` answers the
texts. Checked: at least one and at most 50 jobs, unique ids, a title on
every job, at least one claim and every claim a key of the goal's files,
`after` and `needs.from` name real jobs (never the job itself), no cycle,
`take` names something the upstream gives (`all`, `summary` or one of its
`gives`), no two jobs claim the same or an overlapping key without an
`after` (or a need) between them, and every job's bio and model pass the
lineup preflight (the bio exists, its `tools.allow` is not empty, the model
is in its provider's catalog).
"""

from __future__ import annotations

import re
from typing import Optional

from halo_harness.orchestra.handoff_spec import BUILTIN_TAKES, reach, shape_problems, upstream_ids
from halo_harness.orchestra.index import overlaps

MAX_JOBS = 50
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def _row(jobs, field: str, text: str) -> dict:
    return {"jobs": [j for j in ([jobs] if isinstance(jobs, str) else list(jobs)) if j], "field": field, "text": text}


def _strs(value) -> list:
    return [str(v) for v in value] if isinstance(value, list) else []


def _handoff(job: dict) -> dict:
    h = job.get("handoff")
    return h if isinstance(h, dict) else {}


def _shape(job: dict, jid: str) -> list:
    decl = {k: job[k] for k in ("handoff", "after") if k in job}
    return [_row(jid, "handoff", p) for p in shape_problems(decl, jid)]


def plan_problems(jobs, *, unit_keys: Optional[list] = None, cwd=None, state_dir=None,
                  preflight: bool = True) -> list:
    """Every problem with an edited plan; [] means it may run."""
    if not isinstance(jobs, list) or not jobs:
        return [_row([], "", "the plan has no jobs: give it at least one lane")]
    out = []
    if len(jobs) > MAX_JOBS:
        out.append(_row([], "", f"{len(jobs)} jobs, but a run has at most {MAX_JOBS} lanes"))
    ids, seen = [], set()
    for i, job in enumerate(jobs, 1):
        jid = str(job.get("id") or "").strip() if isinstance(job, dict) else ""
        if not isinstance(job, dict):
            out.append(_row([], "", f"job #{i} is not an object with an id, a title and claims"))
        elif not jid:
            out.append(_row([], "id", f"job #{i} has no id"))
        elif not _ID.match(jid):
            out.append(_row(jid, "id", f"{jid!r} is not a job id (letters, digits, - and _)"))
        elif jid in seen:
            out.append(_row(jid, "id", f"two jobs are called {jid}: give each its own id"))
        seen.add(jid)
        ids.append(jid)
    good = [(jid, job) for jid, job in zip(ids, jobs) if jid and isinstance(job, dict)]
    known = set(unit_keys) if unit_keys is not None else None
    for jid, job in good:
        if not str(job.get("title") or "").strip():
            out.append(_row(jid, "title", f"{jid} has no title: say in one line what its worker does"))
        claims = job.get("claims")
        if not isinstance(claims, list) or not [c for c in claims if str(c).strip()]:
            out.append(_row(jid, "claims", f"{jid} claims nothing: give it at least one unit of the goal's files"))
        elif known is not None:
            for key in claims:
                if not isinstance(key, str) or key not in known:
                    out.append(_row(jid, "claims", f"{jid}: {key!r} is not a unit of the goal's files"))
        out += _shape(job, jid)
    out += _refs(good, set(seen))
    deps = {jid: [u for u in upstream_ids(_handoff(job), _strs(job.get("after"))) if u in seen] for jid, job in good}
    for jid in deps:
        if jid in reach(deps, jid):
            out.append(_row(jid, "after", f"{jid} waits for itself: its after and needs go round in a circle"))
    out += _overlaps(good, deps)
    if preflight:
        out += job_preflight(good, cwd=cwd, state_dir=state_dir)
    return out


def _refs(good: list, ids: set) -> list:
    out = []
    gives = {jid: {str(g.get("name")) for g in _handoff(job).get("gives") or [] if isinstance(g, dict)} for jid, job in good}
    for jid, job in good:
        for a in _strs(job.get("after")):
            if a == jid:
                out.append(_row(jid, "after", f"{jid} runs after itself"))
            elif a not in ids:
                out.append(_row(jid, "after", f"{jid} runs after {a!r}, which is not one of the jobs"))
        for n in _handoff(job).get("needs") or []:
            if not isinstance(n, dict):
                continue
            src, take = str(n.get("from") or ""), str(n.get("take") or "")
            if src == jid:
                out.append(_row(jid, "needs", f"{jid} needs its own hand-off"))
            elif src not in ids:
                out.append(_row(jid, "needs", f"{jid} needs {src!r}, which is not one of the jobs"))
            elif take and take not in BUILTIN_TAKES and take not in gives.get(src, set()):
                offer = ", ".join(sorted(gives.get(src) or ())) or "only its summary and units"
                out.append(_row([jid, src], "needs", f"{jid} takes {take!r} from {src}, which gives {offer} (or use all / summary)"))
    return out


def _overlaps(good: list, deps: dict) -> list:
    out, told = [], set()
    for i, (a, ja) in enumerate(good):
        for b, jb in good[i + 1:]:
            if a in reach(deps, b) or b in reach(deps, a):
                continue
            for ka in _strs(ja.get("claims")):
                hit = next((kb for kb in _strs(jb.get("claims")) if overlaps(ka, kb)), None)
                if hit and (a, b) not in told:
                    told.add((a, b))
                    same = f"both claim {ka}" if ka == hit else f"claim {ka} and {hit}, which overlap"
                    out.append(_row([b, a], "claims", f"{a} and {b} {same} and would run at once: "
                                    f"give {b} an after on {a}, or move the claim"))
    return out


def job_preflight(good: list, *, cwd=None, state_dir=None) -> list:
    """The lineup preflight for each job's own bio and model."""
    from halo_harness.agents_doctor import missing_model_provider
    from halo_harness.agents_yaml import resolve_agent_bio
    out, catalogs, bios = [], {}, {}
    for jid, job in good:
        bio_name, model = str(job.get("bio") or "").strip(), str(job.get("model") or "").strip()
        bio = None
        if bio_name:
            if bio_name not in bios:
                try:
                    bios[bio_name] = resolve_agent_bio(bio_name, cwd=cwd, state_dir=state_dir)
                except Exception:
                    bios[bio_name] = None
            bio = bios[bio_name]
            if bio is None:
                out.append(_row(jid, "bio", f"{jid}'s bio `{bio_name}` does not exist: pick one from the list "
                                f"or make it (`halo agents new {bio_name}`)"))
            else:
                tools = bio.get("tools")
                if isinstance(tools, dict) and isinstance(tools.get("allow"), list) and not tools["allow"]:
                    out.append(_row(jid, "bio", f"{jid}'s bio `{bio_name}` has `tools.allow: []`: its worker may call "
                                    "no tool and cannot edit the files"))
        own = (bio or {}).get("models") if isinstance((bio or {}).get("models"), dict) else {}
        ref = model or own.get("preference")
        try:
            provider = missing_model_provider(ref, catalogs=catalogs, state_dir=state_dir)
        except Exception:
            provider = None
        if provider is not None:
            whose = "model" if model else f"bio `{bio_name}`'s model"
            out.append(_row(jid, "model", f"{jid}'s {whose} `{ref}` is not in the {provider} catalog: requests for "
                            "it 404 and the worker comes back empty (pick a live id, or `halo models --refresh`)"))
    return out


def validate_plan(jobs, **kw) -> list:
    """The problem texts of `plan_problems`; [] means the plan may run."""
    return [p["text"] for p in plan_problems(jobs, **kw)]
