"""halo_harness.workflows.bounds -- the compiled workflow's block in goal.json
and its bounds, each with what holds it (Halo 3.2.0.0 R5, docs/WORKFLOWS.md
"Bounds").

    goal.workflow = block(wf, values, stages, jobs, ids_of, skipped)

Each bound row is `{stage, key, value, enforced, how}`: `enforced` true means
the run holds it (the line says where), false means the run records it and
says "not enforced yet" in the report:

    retries     enforced: the gate's return cap for that stage's lanes (workflows/gate.py)
    timeout_s   enforced: the worker's time limit (orchestra/adapters.py spawn_worker)
    budget_usd  enforced: before each pass of the stage's worker; at its budget the run stops
    gate human  enforced: the plan review (plan: review) before any stage starts
    after_event enforced: the lane waits for the pack event before its worker starts
    the workflow's budget_usd   the goal's budget_usd: the plan's forecast is shown against it;
                not enforced as a stop in a plain Orchestra run (the supervisor holds it: --as goal)
    checkpoint  enforced: an Orchestra run resumes at its first unfinished step (halo orchestra run <id>)
"""

from __future__ import annotations

STAGE_KEYS = ("role", "bio", "gate", "retries", "timeout_s", "budget_usd", "verify", "when", "after_event", "needs")
HOW = {
    "retries": "the gate's return cap for this stage's lanes",
    "timeout_s": "the worker's time limit (each pass of a real worker)",
    "budget_usd": "checked before each pass of the stage's worker; at its budget the run stops",
    "gate": "the plan review: the run waits for halo orchestra approve (or Studio's plan) before any stage",
    "after_event": "the stage's lane waits for the event before its worker starts",
}


def _stage_row(s: dict, ids: list, bio_of: dict) -> dict:
    row = {"id": str(s["id"]), "title": str(s.get("title") or s["id"]), "jobs": list(ids), "bio": bio_of.get(ids[0], "") if ids else ""}
    for k in STAGE_KEYS:
        if k != "bio" and s.get(k) is not None:
            row[k] = s[k]
    return row


def rows(wf, stages: list) -> "list[dict]":
    out = []
    for s in stages:
        for key in ("retries", "timeout_s", "budget_usd", "after_event"):
            if s.get(key) is not None:
                out.append({"stage": str(s["id"]), "key": key, "value": s[key], "enforced": True, "how": HOW[key]})
        if s.get("gate") == "human":
            out.append({"stage": str(s["id"]), "key": "gate", "value": "human", "enforced": True, "how": HOW["gate"]})
    if isinstance(wf.data.get("budget_usd"), (int, float)):
        out.append({"stage": "", "key": "budget_usd", "value": wf.data["budget_usd"], "enforced": False,
                    "how": "the goal's budget: the forecast is shown against it; not enforced yet as a stop in a plain "
                           "Orchestra run (under --as goal the supervisor stops at it)"})
    if wf.data.get("checkpoint") is not None:
        out.append({"stage": "", "key": "checkpoint", "value": bool(wf.data["checkpoint"]), "enforced": True,
                    "how": "the run resumes at its first unfinished step (halo orchestra run <run>; the supervisor's resume)"})
    return out


def block(wf, values: dict, stages: list, jobs: list, ids_of: dict, skipped: list) -> dict:
    from halo_harness.workflows import spec
    from halo_harness.packs.workflow_rules import schema_of
    bio_of = {j["id"]: j.get("bio") or "" for j in jobs}
    return {"ref": wf.ref, "pack": wf.pack.id, "name": wf.name, "version": wf.pack.version, "inputs": dict(values),
            "stages": [_stage_row(s, ids_of.get(str(s["id"]), []), bio_of) for s in stages],
            "jobs": {j["id"]: {k: j[k] for k in ("stage", "item", "title", "brief", "bio", "claims")} for j in jobs},
            "outputs": {k: {"type": str(v.get("type") or ""), "from": str(v.get("from") or ""),
                            **({"schema": schema_of(v.get("type"))} if schema_of(str(v.get("type") or "")) else {})}
                        for k, v in spec.outputs(wf).items()},
            "skipped": list(skipped), "bounds": rows(wf, stages), "checkpoint": bool(wf.data.get("checkpoint", True))}


def bound(goal, job_id: str, key: str):
    """A stage bound (`retries`, `timeout_s`, `budget_usd`, `after_event`, `gate`) for the job's stage, or None."""
    wf = getattr(goal, "workflow", None) or {}
    stage = ((wf.get("jobs") or {}).get(job_id) or {}).get("stage")
    row = next((s for s in wf.get("stages") or [] if s.get("id") == stage), {})
    return row.get(key)
