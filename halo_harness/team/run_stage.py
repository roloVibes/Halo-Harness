"""halo_harness.team.run_stage -- running one stage of a team run.

* `agent`: every member that is not the lead runs first (in the order
  listed), then the lead with their hand-backs to merge. A member with
  `harness: <fleet member>` goes out through DISPATCH and the stage waits for
  its result (`waiting` on the board says on what); the others run here
  through SPAWN, each with `$HALO_TEAM_SCOPE` pointing at its scope file so
  team/guard.py keeps its writes in the stage's blocks.
* `orchestra`: ORCHESTRA with the stage's goal (team/spec_check.goal_for_stage).
* `flow`: FLOW on the named flow, the stage's `inputs` as its intake.

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
    stage = runner.stage(sid)
    row = runner.row(sid)
    rnd = int(row.get("round") or 0) + 1
    ST.close_gate(runner.run_dir, sid)
    BD.set_stage(runner.run_dir, sid, "running", f"round {rnd}" + (f" (redo: {redo})" if redo else ""), round=rnd,
                 started=round(time.time(), 3), ended=None, error="", waiting="", gate_answer=None)
    try:
        if stage["kind"] == "orchestra":
            return finish(runner, sid, _orchestra(runner, stage))
        if stage["kind"] == "flow":
            return finish(runner, sid, _flow(runner, stage))
        members = row.get("members") or S.stage_members(runner.team, stage)
        lead = row.get("lead") or S.stage_lead(runner.team, stage, members)
        order = [m for m in members if m != lead] + ([lead] if lead else [])
        runner.live[sid] = {"order": order, "lead": lead, "results": {}, "handles": {}, "redo": redo}
        return step(runner, sid)
    except Exception as e:  # a seam that raises fails its stage, never the runner
        runner.live.pop(sid, None)
        return finish(runner, sid, {"ok": False, "error": f"{type(e).__name__}: {e}"})


def _orchestra(runner, stage: dict) -> dict:
    from halo_harness.team.spec_check import goal_for_stage
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


def step(runner, sid: str) -> None:
    """Start whatever member can start now; finish the stage when the lead's result is in."""
    live = runner.live.get(sid)
    if live is None:
        return None
    stage = runner.stage(sid)
    for name in live["order"]:
        if name in live["results"] or name in live["handles"]:
            if name in live["handles"]:
                return None  # a delegated member is still out: the stage waits on it
            continue
        if name == live["lead"] and any(m not in live["results"] for m in live["order"] if m != name):
            return None
        member = S.member_by_name(runner.team, name) or {"name": name, "lineup": "", "role": "main", "harness": None}
        others = {m: r["text"] for m, r in live["results"].items()} if name == live["lead"] else None
        prompt = ST.stage_prompt(runner.team, stage, member, lead=live["lead"], handbacks=others or None,
                                 redo=live["redo"])
        if member.get("harness"):
            _send(runner, sid, member, prompt)
            continue
        live["results"][name] = _result(runner.spawn(member, prompt, cwd=runner.root, env=_member_env(runner, stage, name),
                                                     stage=sid, run_dir=runner.run_dir), "the member came back empty")
    lead = live["lead"]
    if lead in live["results"] and not live["handles"]:
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
        BD.set_stage(runner.run_dir, sid, waiting=f"{member['name']}: {what} {member['harness']}")
        BD.log(runner.run_dir, "note", f"{sid}: {member['name']} {what} {member['harness']}", stage=sid,
               status=status, harness=member["harness"])
        return
    reason = str(body.get("error") or f"status {status}")
    word = "refused" if status == 403 else "could not take the task"
    live["results"][member["name"]] = {"ok": False, "text": "", "cost_usd": 0.0,
                                       "error": f"{member['harness']} {word}: {reason}", "state": "failed"}


def poll_live(runner) -> None:
    for sid, live in list(runner.live.items()):
        for name, handle in list(live["handles"].items()):
            got = runner.delegate().poll(handle)
            if not got:
                continue
            if got.get("state") in ("asked", "running") and "ok" not in got:
                what = "running on" if got["state"] == "running" else "asked; the owner's card is open on"
                BD.set_stage(runner.run_dir, sid, waiting=f"{name}: {what} {handle.get('harness')}")
                continue
            live["handles"].pop(name, None)
            live["results"][name] = _result(got, "the delegated member came back empty")
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
