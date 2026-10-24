"""halo_harness.workflows.pinned -- the lead's split of a workflow run: a
PINNED plan (Halo 3.2.0.0 R5, docs/WORKFLOWS.md "The pinned plan").

orchestra/split.py `split_goal` hands a goal with a `workflow` here. The jobs
are the compiled ones (goal.workflow `jobs` + goal.handoffs): one call asks
the lead to refine each job's brief for this repo and answer

    {"jobs": [{"id": "job-1", "brief": "..."}, ...]}   the same jobs, in the same order

A missing brief keeps the workflow's; an answer that adds, drops, renames or
reorders a job is refused and asked once more with the problems, and a
second refusal runs the workflow's own briefs (a note says so). `{"stop":
reason}` stops the run as for any split. split.json is today's shape plus

    "workflow": {"pinned": true, "briefs": {job id: brief}, "refined": [job ids the lead changed]}

and the stages skipped at compile time are logged as `state` lines here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import jsonl


def pinned_jobs(goal) -> "list[dict]":
    """The compiled jobs in split.json's shape (+ bio), in order."""
    rows = (goal.workflow or {}).get("jobs") or {}
    out = []
    for i, (jid, row) in enumerate(sorted(rows.items(), key=lambda kv: int(kv[0].split("-")[-1])), 1):
        decl = dict((goal.handoffs or {}).get(jid) or {})
        job = {"id": jid, "title": row.get("title") or jid, "claims": list(row.get("claims") or []), "worker": i, "order": i}
        handoff = {k: decl[k] for k in ("gives", "needs") if decl.get(k)}
        job.update({k: v for k, v in (("handoff", handoff), ("after", list(decl.get("after") or [])),
                                      ("bio", row.get("bio") or "")) if v})
        out.append(job)
    return out


def pinned_prompt(goal, jobs: list, problems=None) -> str:
    rows = (goal.workflow or {}).get("jobs") or {}
    lines = []
    for j in jobs:
        r = rows.get(j["id"]) or {}
        after = ", ".join(j.get("after") or []) or "starts at once"
        lines.append(f"- {j['id']} (stage {r.get('stage')}, {r.get('bio') or 'the default worker'}; {after}): {j['title']}\n"
                     f"  brief: {r.get('brief') or '(none)'}")
    text = (f"You are the lead orchestrator of a run of the workflow {goal.workflow.get('ref')}. Its stages are "
            "pinned: these jobs run, in this order, with these hand-offs; you do not add, drop, merge or reorder them.\n\n"
            f"WHAT YOU WANT: {goal.what}\nDONE WHEN: {goal.done_when}\nSTOP WHEN: {goal.stop_when}\n\n"
            "The jobs:\n" + "\n".join(lines) + "\n\n"
            "Refine each job's brief for this repo (what to read, what to watch for); keep what the brief asks. "
            'Answer with JSON only: {"jobs": [{"id": "job-1", "brief": "..."}, ...]}, every job once, in this order. '
            'If STOP WHEN already applies, answer {"stop": "the reason"} instead.')
    if problems:
        text += "\n\nYour previous answer had these problems; fix every one:\n" + "\n".join(f"- {p}" for p in problems)
    return text


def check_answer(data, jobs: list) -> "list[str]":
    ids = [j["id"] for j in jobs]
    got = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(got, list):
        return ['the answer is not {"jobs": [{"id", "brief"}, ...]}']
    named = [str(j.get("id")) if isinstance(j, dict) else "?" for j in got]
    if named != ids:
        return [f"the stage set is pinned: answer with exactly {', '.join(ids)}, in that order (got {', '.join(named) or 'none'})"]
    return [f"{j['id']}: brief is text" for j in got if "brief" in j and not isinstance(j.get("brief"), str)]


def split_pinned(run_dir, goal, units: list, *, call_model: Callable, base: str = "", lead_holder: str = "") -> list:
    from halo_harness.orchestra.claims import ClaimLog
    from halo_harness.orchestra.split import PLACEHOLDER_TTL_S, Job, StopRun, _call, parse_answer, placeholder
    run_dir = Path(run_dir)
    wf = goal.workflow or {}
    for row in wf.get("skipped") or []:
        run_events.log(run_dir, "state", f"stage {row.get('stage')} skipped: {row.get('why')}", step="split",
                       stage=row.get("stage"), state="skipped")
    jobs = pinned_jobs(goal)
    briefs = {jid: str(r.get("brief") or "") for jid, r in (wf.get("jobs") or {}).items()}
    cost, sessions, problems, refined = 0.0, [], [], []
    for attempt in (1, 2):
        text, spent, sid = _call(call_model, pinned_prompt(goal, jobs, problems if attempt == 2 else None))
        cost += spent
        sessions += [sid] if sid else []
        data = parse_answer(text)
        if isinstance(data, dict) and str(data.get("stop") or "").strip():
            raise StopRun(f"the lead stopped the run: {str(data['stop']).strip()}")
        problems = check_answer(data, jobs)
        if not problems:
            for j in data["jobs"]:
                if str(j.get("brief") or "").strip() and j["brief"].strip() != briefs.get(j["id"]):
                    briefs[j["id"]] = j["brief"].strip()
                    refined.append(j["id"])
            break
        run_events.log(run_dir, "state", f"split answer {attempt} rejected: " + "; ".join(problems),
                       step="split", attempt=attempt, problems=problems)
    if problems:
        run_events.log(run_dir, "note", "the lead's answer did not keep the pinned stages twice; the run uses the "
                       "workflow's own briefs", step="split")
    jsonl.write_json(run_dir / "split.json", {"base": base, "lead_cost_usd": round(cost, 6), "lead_sessions": sessions,
                                             "jobs": jobs, "workflow": {"pinned": True, "briefs": briefs, "refined": refined}})
    log = ClaimLog(run_dir)
    for job in jobs:
        for key in job.get("claims") or []:
            log.claim(placeholder(job["worker"]), key, ttl_s=PLACEHOLDER_TTL_S, note=f"{job['id']}: {job['title']}")
    run_events.log(run_dir, "state", f"split into {len(jobs)} job(s): the pinned plan of {wf.get('ref')}"
                   + (f" ({len(refined)} brief(s) refined by the lead)" if refined else ""), step="split", jobs=len(jobs),
                   lead=lead_holder or None)
    return [Job.from_dict(j) for j in jobs]


def plan_rules(run_dir, jobs) -> "tuple[list, tuple]":
    """For a reviewed plan (orchestra/plan.py `check`): `(problems, claim_free)`. A workflow run's plan keeps
    its jobs (same ids, same order: you may edit titles, bios, models, claims, never the stage set), and a
    job whose stage claims no file may claim nothing. ([], ()) for a run without a workflow."""
    from halo_harness.orchestra.goal import load_goal
    try:
        goal = load_goal(Path(run_dir) / "goal.json")
    except (OSError, ValueError):
        return [], ()
    if not goal.workflow:
        return [], ()
    pinned = pinned_jobs(goal)
    ids = [str(j.get("id")) for j in jobs if isinstance(j, dict)] if isinstance(jobs, list) else []
    want = [j["id"] for j in pinned]
    problems = [] if ids == want else [{"jobs": [], "field": "id", "text": f"the workflow {goal.workflow.get('ref')} pins "
                                        f"its stages: the plan keeps {', '.join(want)}, in that order"}]
    return problems, tuple(j["id"] for j in pinned if not j.get("claims"))


def brief_of(run_dir, goal, job_id: str) -> str:
    """The job's brief: the lead's refinement (split.json), else the workflow's."""
    split = jsonl.read_json(Path(run_dir) / "split.json", {}) or {}
    briefs = (split.get("workflow") or {}).get("briefs") or {}
    return str(briefs.get(job_id) or (((goal.workflow or {}).get("jobs") or {}).get(job_id) or {}).get("brief") or "")
