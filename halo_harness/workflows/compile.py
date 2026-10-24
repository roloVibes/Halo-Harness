"""halo_harness.workflows.compile -- a workflow and its inputs, compiled to
an Orchestra goal (Halo 3.2.0.0 R5, docs/WORKFLOWS.md "The compile").

    compiled = compile_workflow(wf, {"docs": "docs"}, repo=repo)
    compiled.problems   # [] -> compiled.goal is a valid orchestra Goal; new_run(repo, compiled.goal) runs it

The stages become jobs (one per stage, one per file for `for_each`), in the
file's order, `job-1..N`: `after` and `takes` become each job's `after` and
`handoff.needs`, `gives` its `handoff.gives` (an artifact give is saved as
`<name>.json`), a `files` give's paths its claims (the goal's `files`), the
role its `bio`. A `when` on an input is resolved here (a false one skips the
stage, and a stage after it runs after the skipped stage's own upstreams); a
`when` on an upstream output waits for the run (runtime.py). The Goal:

    what / done_when / stop_when   from the file (the description, done_when, stop_when)
    workers      the number of jobs          return_cap   the largest stage `retries` (default 2)
    test         every stage's verify.test, joined with &&       files   the claimed files
    lineup       the pack's lineup whose `workflows:` names this one (`<id>--<name>`)
    handoffs     {job id: {gives, needs, after}}                 plan    review when a stage has gate: human
    budget_usd   the file's budget_usd (else the stages' sum)    workflow  the pinned plan (below)

`goal.workflow` = {ref, pack, version, name, inputs, stages: [...], jobs: {job id: {stage, item, title,
brief, bio}}, outputs: {name: {type, from, schema}}, skipped: [{stage, why}], bounds: [...], checkpoint}.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from halo_harness.workflows import spec
from halo_harness.workflows.conditions import on_input

DEFAULT_STOP = "a stage cannot be done as its brief says (its worker says why in one line)"
_FIELD = re.compile(r"\{([A-Za-z0-9_-]+)\}")


@dataclass
class Compiled:
    workflow: object
    goal: Optional[object] = None
    jobs: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    problems: list = field(default_factory=list)


def fill(text: str, values: dict) -> str:
    """`{item}` and `{<input>}` filled from `values`; any other `{word}` stays as written."""
    return _FIELD.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), str(text or ""))


def _items(stage: dict, values: dict, repo: Path) -> "Optional[list]":
    """The files a `for_each` stage runs once per (sorted, repo-relative); None for a stage without one."""
    each = stage.get("for_each")
    if each is None:
        return None
    name, match = (each.get("input"), each.get("match") or "*") if isinstance(each, dict) else (each, "*")
    rel = values.get(name)
    if not rel:
        return []
    base = repo / rel
    if base.is_file():
        return [rel] if fnmatch.fnmatch(base.name, match) else []
    found = [p for p in base.rglob("*") if p.is_file() and fnmatch.fnmatch(p.name, match)
             and not ({".git", ".halo"} & set(p.relative_to(repo).parts))]
    return sorted(p.relative_to(repo).as_posix() for p in found)


def _ups(stage: dict) -> "list[str]":
    ups = [str(a) for a in stage.get("after") or []]
    return list(dict.fromkeys(ups + [str(t.get("from")) for t in stage.get("takes") or [] if isinstance(t, dict)]))


def _live_ups(sid: str, by_id: dict, ids_of: dict, seen=()) -> "list[str]":
    """The upstream stages that have jobs; a skipped upstream hands over its own."""
    out: list = []
    for u in _ups(by_id[sid]):
        if u in seen or u not in by_id:
            continue
        out += [u] if ids_of.get(u) else _live_ups(u, by_id, ids_of, seen + (sid,))
    return list(dict.fromkeys(out))


def _gives(stage: dict) -> list:
    out = []
    for g in stage.get("gives") or []:
        if isinstance(g, dict) and g.get("name"):
            row = {"name": str(g["name"]), "kind": str(g.get("kind") or "")}
            paths = [str(p) for p in g.get("paths") or []] or ([f"{g['name']}.json"] if row["kind"] == "artifact" else [])
            if paths:
                row["paths"] = paths
            out.append(row)
    return out


def _lineup(wf) -> str:
    from halo_harness.agents_yaml import _read_yaml_file
    from halo_harness.packs import names as N
    for rel in ((wf.pack.manifest.get("contributes") or {}).get("teams") or []):
        raw = _read_yaml_file(Path(wf.pack.root) / str(rel)) or {}
        if wf.name in (raw.get("workflows") or []):
            return N.qualify(wf.pack.id, Path(str(rel)).stem)
    return ""


def _jobs(wf, live: list, values: dict, repo: Path, skipped: list) -> "tuple[list, dict]":
    from halo_harness.packs.workflow_stages import role_bio
    jobs, ids_of = [], {}
    for s in live:
        sid, items = str(s["id"]), _items(s, values, repo)
        if items == []:
            skipped.append({"stage": sid, "why": f"for_each {s['for_each']!r} names no file"})
            continue
        ids_of[sid] = []
        for item in items if items is not None else [None]:
            n = len(jobs) + 1
            vals = dict(values, item=item) if item else dict(values)
            bio = role_bio(wf.pack.manifest, wf.pack.root, s.get("role")) if s.get("role") else ""
            jobs.append({"id": f"job-{n}", "stage": sid, "item": item or "", "worker": n, "order": n, "bio": bio,
                         "title": fill(s.get("title") or s["id"], vals) + (f" ({item})" if item and "{item}" not in str(s.get("title") or "") else ""),
                         "brief": fill(s.get("brief") or "", vals)})
            ids_of[sid].append(f"job-{n}")
    return jobs, ids_of


def _wire(jobs: list, by_id: dict, ids_of: dict) -> None:
    for job in jobs:
        s = by_id[job["stage"]]
        ups = _live_ups(job["stage"], by_id, ids_of)
        takes = [t for t in s.get("takes") or [] if isinstance(t, dict)]
        needs = [{"from": j, "take": str(t.get("take") or "summary")} for t in takes for j in ids_of.get(str(t.get("from")), [])]
        job["after"] = [j for u in ups for j in ids_of.get(u, []) if j not in {n["from"] for n in needs}]
        job["handoff"] = {k: v for k, v in (("gives", _gives(s)), ("needs", needs)) if v}
        files = [p for g in job["handoff"].get("gives") or [] if g["kind"] == "files" for p in g.get("paths") or []]
        job["claims"] = list(dict.fromkeys(files))


def compile_workflow(wf, raw_inputs: Optional[dict] = None, *, repo, cwd=None, state_dir=None) -> Compiled:
    from halo_harness.orchestra.goal import Goal, validate_goal
    from halo_harness.orchestra.workflow import MAX_WORKERS
    from halo_harness.workflows import bounds, inputs
    repo = Path(repo)
    out = Compiled(workflow=wf)
    values, out.problems = inputs.parse(wf, dict(raw_inputs or {}), repo=repo)
    out.problems += inputs.prerequisites(wf, repo=repo, cwd=cwd or repo, state_dir=state_dir)
    stages = spec.stages(wf)
    by_id = {str(s["id"]): s for s in stages}
    live = []
    for s in stages:
        out.problems += inputs.capability_problems(wf, s.get("needs"), cwd=cwd or repo, state_dir=state_dir,
                                                   where=f"stage {s['id']}: ")
        ok, why = on_input(s.get("when"), values)
        (live if ok else out.skipped).append(s if ok else {"stage": str(s["id"]), "why": why})
    out.jobs, ids_of = _jobs(wf, live, values, repo, out.skipped)
    _wire(out.jobs, by_id, ids_of)
    if not out.jobs:
        out.problems.append("every stage is skipped: " + "; ".join(f"{x['stage']}: {x['why']}" for x in out.skipped))
    elif len(out.jobs) > MAX_WORKERS:
        out.problems.append(f"{len(out.jobs)} jobs, but a run has at most {MAX_WORKERS} lanes (narrow the for_each match)")
    if out.problems:
        return out
    run_stages = [s for s in stages if str(s["id"]) in ids_of]
    caps = [int(s["retries"]) if isinstance(s.get("retries"), int) else 2 for s in run_stages]
    budgets = [float(s["budget_usd"]) for s in stages if isinstance(s.get("budget_usd"), (int, float))]
    tests = [str((s.get("verify") or {}).get("test") or "").strip() for s in run_stages if isinstance(s.get("verify"), dict)]
    files = sorted({c for j in out.jobs for c in j["claims"]})
    budget = wf.data.get("budget_usd") if isinstance(wf.data.get("budget_usd"), (int, float)) else (sum(budgets) if budgets else None)
    goal = Goal(what=f"Run the {wf.pack.id} workflow {wf.name}: {wf.description or wf.name}"
                     + "".join(f"\n  input {k} = {v}" for k, v in values.items()),
                done_when=str(wf.data.get("done_when") or f"every stage of {wf.ref} is done and its outputs pass their checks"),
                stop_when=str(wf.data.get("stop_when") or DEFAULT_STOP), workers=len(out.jobs),
                return_cap=max(caps) if caps else 2,
                test=" && ".join(t for t in tests if t), files=files, lineup=_lineup(wf),
                handoffs={j["id"]: dict(j["handoff"], after=j["after"]) for j in out.jobs if j["handoff"] or j["after"]},
                plan="review" if any(s.get("gate") == "human" for s in run_stages) else "auto",
                budget_usd=float(budget) if budget is not None else None)
    goal.workflow = bounds.block(wf, values, run_stages, out.jobs, ids_of, out.skipped)
    problems = validate_goal(goal)
    if problems:
        out.problems += problems
        return out
    out.goal = goal
    return out
