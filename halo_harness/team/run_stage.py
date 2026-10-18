"""halo_harness.team.run_stage -- running one stage of a team run.

* `agent`: every member that is not the lead runs at the same time
  (team/parallel.py: a thread pool bounded by the tightest `max_parallel` of
  their tiers), then the lead with their hand-backs to merge. A member with
  `harness: <fleet member>` goes out through DISPATCH and holds its slot
  until its result lands (`waiting` on the board says on what); the others
  run here through SPAWN, each with `$HALO_TEAM_SCOPE` pointing at its scope
  file so team/guard.py keeps its writes in the stage's blocks. The row's
  `members_state` carries each member's state. A failed member fails the
  stage once the others end (the lead does not run).
* `orchestra`: ORCHESTRA with the stage's goal (team/resolve.goal_for_stage).
* `flow`: FLOW on the named flow, the stage's `inputs` as its intake.
* an orchestra or flow stage with `harness: <fleet member>` runs on that
  member (team/remote_stage.py, 3.1.2.0 R2).

Before a stage starts, its budget is checked (team/budget.py, 3.1.2.0 R2):
over the team's or the stage's `budget_usd`, it does not start.

`finish()` writes result.json, handback.md and refs.json, releases the
stage's claims, runs the acceptance and then: a failed result -> failed; a
`required` gate -> gated (gate.json, the acceptance shown with it); a failed
acceptance without one -> failed; else done (an `optional` gate opens too
but does not hold the next stage) and every `stage_done:<it>` stage queues.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from halo_harness.team import blocks as B
from halo_harness.team import board as BD
from halo_harness.team import parallel as P
from halo_harness.team import spec as S
from halo_harness.team import stages as ST
from halo_harness.team.guard import write_scope


def _result(raw, default_error: str = "no result") -> dict:
    raw = raw if isinstance(raw, dict) else {}
    ok = bool(raw.get("ok"))
    return {"ok": ok, "text": str(raw.get("text") or ""), "cost_usd": float(raw.get("cost_usd") or 0.0),
            "error": "" if ok else str(raw.get("error") or default_error), "session_id": raw.get("session_id"),
            "run_id": raw.get("run_id"), "state": raw.get("state") or ("done" if ok else "failed")}


def run_queued(runner) -> None:
    while runner.queue and runner.board().get("state") == "open":
        sid, redo = runner.queue.pop(0)
        start(runner, sid, redo)


def start(runner, sid: str, redo: str = "") -> None:
    from halo_harness.team.budget import hold_if_over
    stage = runner.stage(sid)
    if hold_if_over(runner, sid):
        return None  # over a budget: the row says why, the Attention row offers raise / skip / stop
    row = runner.row(sid)
    rnd = int(row.get("round") or 0) + 1
    ST.close_gate(runner.run_dir, sid)
    members = row.get("members") or S.stage_members(runner.team, stage)
    lead = row.get("lead") or S.stage_lead(runner.team, stage, members)
    workers = [m for m in members if m != lead]
    extra = {"members_state": P.initial(workers, lead)} if stage["kind"] == "agent" else {}
    BD.set_stage(runner.run_dir, sid, "running", f"round {rnd}" + (f" (redo: {redo})" if redo else ""), round=rnd,
                 started=round(time.time(), 3), ended=None, error="", waiting="", gate_answer=None, **extra)
    try:
        if stage["kind"] in ("orchestra", "flow") and stage.get("harness"):
            from halo_harness.team.remote_stage import send
            return send(runner, sid, stage, redo)
        if stage["kind"] == "orchestra":
            return finish(runner, sid, _orchestra(runner, stage))
        if stage["kind"] == "flow":
            return finish(runner, sid, _flow(runner, stage))
        cap = P.limit(runner.team, workers or [lead], cwd=runner.cwd or runner.root, state_dir=runner.state_dir)
        runner.live[sid] = {"order": workers + ([lead] if lead else []), "lead": lead, "workers": workers,
                            "results": {}, "handles": {}, "redo": redo, "cap": cap}
        return step(runner, sid)
    except Exception as e:  # a seam that raises fails its stage, never the runner
        runner.live.pop(sid, None)
        return finish(runner, sid, {"ok": False, "error": f"{type(e).__name__}: {e}"})


def _orchestra(runner, stage: dict) -> dict:
    from halo_harness.team.resolve import goal_for_stage
    out = _result(runner.orchestra(goal_for_stage(runner.team, stage, runner.root), root=runner.root,
                                   stage=stage["id"], run_dir=runner.run_dir), "the orchestra run ended without a report")
    out["refs"] = {"orchestra_run": out.get("run_id")}
    return out


def _flow(runner, stage: dict) -> dict:
    out = _result(runner.flow(stage["flow"], intake=dict(stage.get("inputs") or {}), cwd=runner.root,
                              stage=stage["id"], run_dir=runner.run_dir), "the flow run ended without a report")
    out["refs"] = {"flow_run": out.get("run_id")}
    return out


def _member_env(runner, stage: dict, name: str) -> dict:
    path = BD.stage_dir(runner.run_dir, stage["id"]) / f"scope-{name}.json"
    write_scope(path, root=runner.root, run_dir=runner.run_dir, stage=stage["id"], member=name,
                writes=stage.get("writes") or [], blocks=runner.team["blocks"])
    from halo_harness.team import SCOPE_ENV
    return {**os.environ, SCOPE_ENV: str(path), "PYTHONIOENCODING": "utf-8"}


def _task(runner, stage: dict, member: dict, prompt: str) -> dict:
    return {"team": runner.team["name"], "run": runner.run_dir.name, "stage": stage["id"], "member": member["name"],
            "lineup": member["lineup"], "role": member["role"], "title": f"team {runner.team['name']} stage {stage['id']}",
            "brief": prompt, "writes": list(stage.get("writes") or [])}


def _launch(runner, sid: str, name: str):
    """The call that runs member `name` here, or None once it went out through DISPATCH."""
    live, stage = runner.live[sid], runner.stage(sid)
    member = S.member_by_name(runner.team, name) or {"name": name, "lineup": "", "role": "main", "harness": None}
    lead = name == live["lead"] and bool(live["workers"])
    others = {m: live["results"][m]["text"] for m in live["workers"] if m in live["results"]} if lead else None
    prompt = ST.stage_prompt(runner.team, stage, member, lead=live["lead"], handbacks=others or None, redo=live["redo"])
    if member.get("harness"):
        _send(runner, sid, member, prompt)
        return None
    env = _member_env(runner, stage, name)
    return lambda: runner.spawn(member, prompt, cwd=runner.root, env=env, stage=sid, run_dir=runner.run_dir)


def step(runner, sid: str) -> None:
    """Start every member that can start now (at once, under the cap); the lead once they are all in; finish
    the stage when the lead's result is in (or a member failed and the others ended)."""
    live = runner.live.get(sid)
    if live is None:
        return None
    if live.get("remote"):
        from halo_harness.team.remote_stage import step as remote_step
        return remote_step(runner, sid)
    def launch(name):
        return _launch(runner, sid, name)

    def result_of(raw):
        return _result(raw, "the member came back empty")
    P.run_members(runner, sid, live["workers"], launch, result_of)
    if any(m not in live["results"] for m in live["workers"]):
        return None  # a delegated member is still out (or waits for its slot): the stage waits on it
    failed = [m for m in live["workers"] if not live["results"][m].get("ok")]
    lead = live["lead"]
    if lead and not failed and lead not in live["results"]:
        P.run_members(runner, sid, [lead], launch, result_of)
    if lead and not failed and lead not in live["results"]:
        return None  # a delegated lead is still out
    if failed and lead and lead not in live["results"]:
        P.mark(runner, sid, lead, "skipped", "a member failed")
    runner.live.pop(sid, None)
    finish(runner, sid, _merge(live))
    return None


def _send(runner, sid: str, member: dict, prompt: str) -> None:
    live = runner.live[sid]
    status, body = runner.delegate().send(member, _task(runner, runner.stage(sid), member, prompt))
    body = body if isinstance(body, dict) else {}
    if status in (200, 202):
        live["handles"][member["name"]] = dict(body.get("handle") or body, member=member["name"], harness=member["harness"])
        what = "running on" if status == 200 else "asked; the owner's card is open on"
        P.mark(runner, sid, member["name"], "running" if status == 200 else "waiting")
        BD.set_stage(runner.run_dir, sid, waiting=f"{member['name']}: {what} {member['harness']}")
        BD.log(runner.run_dir, "note", f"{sid}: {member['name']} {what} {member['harness']}", stage=sid,
               status=status, harness=member["harness"])
        return
    reason = str(body.get("error") or f"status {status}")
    word = "refused" if status == 403 else "could not take the task"
    live["results"][member["name"]] = {"ok": False, "text": "", "cost_usd": 0.0,
                                       "error": f"{member['harness']} {word}: {reason}", "state": "failed"}
    P.mark(runner, sid, member["name"], "failed", word)


def poll_live(runner) -> None:
    for sid, live in list(runner.live.items()):
        for name, handle in list(live["handles"].items()):
            got = runner.delegate().poll(handle)
            if not got:
                continue
            if got.get("state") in ("asked", "running") and "ok" not in got:
                if live.get("remote"):
                    from halo_harness.team.remote_stage import waiting
                    waiting(runner, sid, handle, got["state"])
                    continue
                what = "running on" if got["state"] == "running" else "asked; the owner's card is open on"
                P.mark(runner, sid, name, "running" if got["state"] == "running" else "waiting")
                BD.set_stage(runner.run_dir, sid, waiting=f"{name}: {what} {handle.get('harness')}")
                continue
            live["handles"].pop(name, None)
            live["results"][name] = dict(_result(got, "the delegated member came back empty"),
                                         **{k: got[k] for k in ("report",) if k in got})
            if not live.get("remote"):
                P.mark(runner, sid, name, "done" if live["results"][name]["ok"] else "failed")
            BD.set_stage(runner.run_dir, sid, waiting="")
        if sid in runner.live:
            step(runner, sid)


def _merge(live: dict) -> dict:
    results = live["results"]
    lead = results.get(live["lead"]) or {}
    failed = [f"{m}: {r['error']}" for m, r in results.items() if not r.get("ok")]
    return {"ok": not failed, "text": lead.get("text") or "", "error": "; ".join(failed),
            "cost_usd": round(sum(float(r.get("cost_usd") or 0) for r in results.values()), 6),
            "refs": {"sessions": {m: r.get("session_id") for m, r in results.items()}},
            "handbacks": {m: r.get("text") or r.get("error") for m, r in results.items()}}


def finish(runner, sid: str, result: dict) -> None:
    stage, run_dir = runner.stage(sid), runner.run_dir
    row = runner.row(sid)
    rnd = int(row.get("round") or 1)
    for name in row.get("members") or []:
        for bid in stage.get("writes") or []:
            block = S.block_by_id(runner.team, bid)
            if block:
                for key in B.release_holder(runner.root, block, B.holder_of(name, sid)):
                    BD.log(run_dir, "claim", f"{name}@{sid} released {key} in block {bid}", stage=sid, block=bid,
                           key=key, op="release")
    text = result.get("text") or ""
    acceptance = ST.evaluate(runner.team, stage, text, runner.accept) if result.get("ok") else None
    summary = (text.strip().splitlines() or [""])[0][:200] if result.get("ok") else result.get("error", "")[:200]
    hb = result.get("handbacks") or {}
    hand = text if not hb else "\n\n".join(f"## {m}\n\n{t}" for m, t in hb.items())
    BD.write_stage_file(run_dir, sid, "handback.md", hand or (result.get("error") or ""))
    BD.write_stage_file(run_dir, sid, "refs.json", result.get("refs") or {})
    state = "failed" if not result.get("ok") else ("gated" if stage["gate"] == "required" else
                                                    "failed" if acceptance and not acceptance["ok"] else "done")
    BD.write_stage_file(run_dir, sid, "result.json", {"ok": bool(result.get("ok")), "state": state, "round": rnd,
                                                     "summary": summary, "cost_usd": result.get("cost_usd") or 0.0,
                                                     "error": result.get("error") or "", "acceptance": acceptance,
                                                     "refs": result.get("refs") or {}, "ended": round(time.time(), 3)})
    cost = round(float(row.get("cost_usd") or 0) + float(result.get("cost_usd") or 0), 6)
    error = result.get("error") or ("" if not acceptance or acceptance["ok"] else acceptance["note"])
    BD.set_stage(run_dir, sid, state, summary, ended=round(time.time(), 3), cost_usd=cost, summary=summary,
                 error=error if state == "failed" else "", waiting="")
    BD.log(run_dir, "report", f"{sid} {state}: {summary}", stage=sid, state=state, cost_usd=result.get("cost_usd") or 0,
           acceptance=acceptance)
    if state == "gated" or (state == "done" and stage["gate"] == "optional"):
        ST.open_gate(run_dir, sid, rnd, summary=text or summary, acceptance=acceptance, gate=stage["gate"])
    if state == "done":
        runner.fire_done(sid)


def stage_text(run_dir, sid: str) -> Optional[str]:
    return BD.read_stage_file(run_dir, sid, "handback.md", None)
