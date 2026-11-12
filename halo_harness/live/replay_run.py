"""halo_harness.live.replay_run -- a goal run's replay as the same one file a session's is (Halo 3.4.1.0 R2 "Time").

A goal run (an Orchestra run, `<repo>/.halo/orchestra/<run-id>/`) has no transcript of its own: its record is the run
folder. The lead and each lane become the replay's agents (`lead`, `lane-<n>` under it), each lane's state history
(`lanes/<n>.json` `history`: joined, writing, written, in review, sent back, merged, failed) its states, marks and
bands through the same live/timeline.py a session's go through, the plan review (`plan.json`) an ask, and its `facts`
the run's own figures: the report's cost (else the lead's split plus every lane), each model's share, the pieces sent
back (retries), the tokens of the lead's and the lanes' sessions when every one of them is on this disk.

    build_run(state_dir, run_dir) -> payload    kind "run", format halo-replay version 1 (live/replay_file.py)
    find(cwd, run_id) -> run folder | None      a goal run of the repo that holds `cwd`
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

# a lane's word -> (an entry for timeline.py, the replay's state); None = no entry (the lane only waits its turn)
ENTRY = {"writing": "text", "waiting": "text", "written": "handback", "in_review": "tool_call"}
END = {"merged": "done", "failed": "failed"}


def find(cwd, run_id: str) -> Optional[Path]:
    if not run_id or any(c in run_id for c in "/\\*?["):
        return None
    try:
        from halo_harness.studio import orchestra_model as OM
        return OM.find_run(OM.repo_of(cwd), run_id)
    except Exception:
        return None


def _ref(word) -> Optional[str]:
    """A model ref (`or:...`), else None: `subagent`, `main` are role words (3.4.1.1, defect 59)."""
    return str(word) if word and ":" in str(word) else None


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _tokens(state_dir, sids: list) -> Optional[dict]:
    """The tokens of these sessions, when every one is on this disk; None otherwise (unknown, never 0)."""
    from halo_harness.live import history, replay_facts
    tin = tout = 0
    for sid in sids:
        path = history.find(state_dir, sid)
        t = replay_facts.session_facts(path).get("tokens") if path else None
        if not t:
            return None
        tin, tout = tin + t["in"], tout + t["out"]
    return {"in": tin, "out": tout} if sids else None


def _hist(meta: dict, goal: dict, lanes: list, report: Optional[dict], state: str) -> dict:
    """The run as live/history.read's shape (agents, entries, asks), so timeline.of makes its marks and bands."""
    t0 = _num(meta.get("created"))
    ends = [_num(r.get("ended")) for r in lanes] + [_num((report or {}).get("ts"))]
    t1 = max([t for t in ends + [t0] if t is not None], default=None)
    lead_state = "done" if state == "finished" else "failed" if state in ("stopped", "failed") else "running"
    agents = [{"agent_id": "lead", "parent": None, "name": "lead", "role": "orchestra", "bio": None, "lineup": goal.get("lineup") or None,
               "model": None, "state": lead_state, "since": t0, "ended": t1 if report else None,
               "cost_usd": None, "task": goal.get("what") or ""}]
    first = min([t for t in (_num(r.get("started")) for r in lanes) if t is not None], default=None)
    entries: dict = {"lead": ([{"kind": "thinking", "text": "the split", "ts": t0}] if t0 else [])  # the split, until the first lane
                     + ([{"kind": "note", "text": "the lanes run", "ts": first}] if first is not None else [])}
    for r in lanes:
        aid = f"lane-{r.get('lane')}"
        rows = [h for h in r.get("history") or [] if isinstance(h, dict) and _num(h.get("ts")) is not None]
        claims = ", ".join(str(c) for c in r.get("claims") or [])
        lane_state = END.get(str(r.get("state") or ""), "running" if r.get("state") else "queued")
        # 3.4.1.1 (60): a lane ends when it last merged (or failed), from its own history -- `ended` is when its last piece
        # was written, before the review, so the replay drew it merged half a run early
        last = [float(h["ts"]) for h in rows if h.get("state") == str(r.get("state"))]
        end = (last[-1] if last else _num(r.get("ended"))) if lane_state in ("done", "failed") else None
        agents.append({"agent_id": aid, "parent": "lead", "name": f"lane {r.get('lane')}", "role": "lane", "bio": r.get("bio") or None,
                       "lineup": goal.get("lineup") or None, "model": r.get("model") or _ref(goal.get("worker")), "state": lane_state,
                       "since": _num(r.get("started")), "ended": end, "cost_usd": _num(r.get("cost_usd")), "task": str(r.get("title") or claims)})
        entries[aid] = [{"kind": ENTRY[h["state"]], "ts": float(h["ts"]), "name": "review",
                         "text": f"wrote {claims}" if h["state"] == "written" else str(h["state"])}
                        for h in rows if h.get("state") in ENTRY]
    return {"agents": agents, "entries": entries, "asks": [], "started": t0, "ended": t1}


LEAD_UNKNOWN = "the lead (model not recorded)"


def lead_model(state_dir, goal: dict, split: dict) -> Optional[str]:
    """3.4.1.1 (59): the model the lead ran on. `goal.lead` is a model ref (`or:...`) or a ROLE word (`main`), which is
    no model: then the model its own session's record names, else None ("the lead (model not recorded)")."""
    word = str(goal.get("lead") or "")
    if ":" in word:
        return word
    from halo_harness.live import history
    for sid in (split.get("lead_sessions") or []) if isinstance(split, dict) else []:
        path = history.find(state_dir, str(sid)) if sid else None
        got = history._meta(history.read_nodes(path), "model") if path else None
        if got:
            return str(got)
    return None


def _facts(state_dir, run_dir: Path, goal: dict, lanes: list, report: Optional[dict], state: str, cost: float) -> dict:
    from halo_harness.orchestra import jsonl
    split = jsonl.read_json(run_dir / "split.json", {}) or {}
    model_cost: dict = {}
    lead = float(split.get("lead_cost_usd") or 0.0) if isinstance(split, dict) else 0.0
    if lead:
        model_cost[lead_model(state_dir, goal, split) or LEAD_UNKNOWN] = round(lead, 6)
    for r in lanes:
        ref = str(r.get("model") or _ref(goal.get("worker")) or "a lane (model not recorded)")
        if _num(r.get("cost_usd")):
            model_cost[ref] = round(model_cost.get(ref, 0.0) + float(r["cost_usd"]), 6)
    sids = [str(s) for s in (split.get("lead_sessions") or []) if s] if isinstance(split, dict) else []
    sids += [str(s) for r in lanes for s in r.get("session_ids") or [] if s]
    reason = str((report or {}).get("stop_reason") or "")
    how = {"finished": "finished" + ("" if (report or {}).get("tests_ok", True) else ", the tests failed"),
           "stopped": f"stopped: {reason}" if reason else "stopped"}.get(state, state)
    wrote = [(str(c).split("#", 1)[0], f"lane {r.get('lane')}") for r in lanes if r.get("state") == "merged" for c in r.get("claims") or []]
    wrote += [(f".halo/orchestra/{run_dir.name}/{a['path']}", str(a.get("name") or "the workflow"))  # a workflow's saved outputs
              for a in (report or {}).get("artifacts") or [] if isinstance(a, dict) and a.get("state") == "saved" and a.get("path")]
    from halo_harness.live.replay_facts import artefacts
    return {"cost_usd": round(cost, 6), "cost_unknown": [], "tokens": _tokens(state_dir, sids), "model_cost": model_cost,
            "artefacts": artefacts(wrote, None), "answer": "",  # 3.4.1.0 R3: what merged (repo-relative) and the saved outputs
            "retries": sum(int(r.get("pieces_returned") or 0) for r in lanes), "failed_calls": 0, "steers": [],
            "how": how, "ok": True if state == "finished" and (report or {}).get("tests_ok", True) else False if state in ("stopped", "failed") else None}


def build_run(state_dir, run_dir) -> dict:
    """The replay of the goal run in `run_dir`. Raises ReplayError when it is not one."""
    from halo_harness import __version__
    from halo_harness.live import history, timeline
    from halo_harness.live.replay_file import AGENT_KEYS, FORMAT, VERSION, ReplayError, includes
    from halo_harness.privacy_redact import redact
    from halo_harness.studio import orchestra_model as OM
    run_dir = Path(run_dir)
    if not (run_dir / "goal.json").is_file():
        raise ReplayError(f"no goal run at {run_dir.name!r}")
    from halo_harness.orchestra.lanes import lane_rows
    from halo_harness.orchestra.report import load_report
    report, goal, lanes = load_report(run_dir), OM.goal_of(run_dir), lane_rows(run_dir)
    from halo_harness.orchestra.goal import run_meta
    meta = run_meta(run_dir)
    state = OM.run_state(run_dir, False, report)
    cost = OM.run_cost(run_dir, report, lanes)
    h = _hist(meta, goal, lanes, report, state)
    from halo_harness.orchestra import jsonl
    h["agents"][0]["model"] = lead_model(state_dir, goal, jsonl.read_json(run_dir / "split.json", {}) or {})  # 3.4.1.1 (59)
    h["agents"][0]["cost_usd"] = round(cost - sum(_num(r.get("cost_usd")) or 0.0 for r in lanes), 6)
    states = []
    for a in h["agents"]:
        end = a["state"] if a["state"] in ("done", "failed") else ""
        states += history.states_of(a["agent_id"], h["entries"].get(a["agent_id"]) or [], a["ended"], end)
    run_id = run_dir.name
    t_lead, costs, agent_costs, total = h["started"], [], [], 0.0
    for a in sorted(h["agents"], key=lambda a: (a["ended"] or t_lead or 0)):
        usd, t = _num(a["cost_usd"]), a["ended"] or (_num((report or {}).get("ts")) if a["agent_id"] == "lead" else None)
        if usd and t is not None:
            total += usd
            costs.append({"t": t, "usd": round(total, 6)})
            agent_costs.append({"t": t, "agent_id": a["agent_id"], "usd": usd})
    marks = timeline.marks(h)
    from halo_harness.orchestra import plan as plan_mod
    decision = plan_mod.read_decision(run_dir)
    if goal.get("plan") == "review" and isinstance(decision, dict) and _num(decision.get("ts")) is not None:
        said = "approved" if decision.get("approved") else f"rejected: {decision.get('reason') or ''}".rstrip(": ")
        marks.append({"t": float(decision["ts"]), "kind": "ask", "agent_id": "lead", "name": "lead", "text": f"the plan review ({said})"})
        marks.sort(key=lambda m: (m["t"], timeline.MARK_KINDS.index(m["kind"]), m["agent_id"]))
    saved = round(time.time(), 3)
    p = {"format": FORMAT, "version": VERSION, "kind": "run", "id": f"{run_id}-{time.strftime('%Y%m%d-%H%M%S', time.localtime(saved))}",
         "session_id": "", "run_id": run_id, "title": goal.get("what") or f"goal run {run_id}", "saved": saved, "halo": __version__,
         "started": h["started"], "ended": h["ended"], "cost_usd": round(cost, 6),
         "agents": [{k: a.get(k) for k in AGENT_KEYS} for a in h["agents"]],
         "states": sorted(states, key=lambda s: (s["t"], s["agent_id"])), "costs": costs, "agent_costs": agent_costs,
         "marks": marks, "bands": timeline.bands({**h, "asks": []}), "plan": None,
         "facts": _facts(state_dir, run_dir, goal, lanes, report, state, cost)}
    p = redact(p, root=run_dir.parents[2] if len(run_dir.parents) > 2 else None)  # 3.4.1.2: the one redaction
    if "_sanitize_error" in p:
        raise ReplayError("the redactor could not clean this run's record; nothing was written")
    p["includes"] = includes(p)
    return p
