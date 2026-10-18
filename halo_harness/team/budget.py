"""halo_harness.team.budget -- a team's budget line (Halo 3.1.2.0 R2,
docs/TEAM.md "Budgets"; team/run_stage.py checks it before a stage starts).

    budget_usd: 2.0                      # in the team file: the whole run
    workflow:
      stages:
        - {id: build, kind: orchestra, budget_usd: 1.0, ...}   # one stage, every round of it

Before a stage starts, its forecast (`stage_forecast`) is added to what was
spent and checked against both lines:

    the run    the run's cost so far + the stage's forecast   <= the team's budget_usd
    the stage  the stage's cost so far (its earlier rounds) + its forecast <= the stage's budget_usd

A stage's forecast (its high end is what is checked): an agent stage, each
member that runs at the member's model's catalog price for one stage turn
of TURN_IN input and TURN_OUT output tokens (a member whose model the
catalog does not price counts a fixed TURN_USD); an orchestra stage, the
Orchestra forecast of its goal (orchestra/forecast.for_goal); a flow stage,
its steps' `budget_usd` (else the flow's own `budget_usd`, else 0).

Over a line, the stage is not started: its row goes back to `pending` with
`waiting: "budget: ..."` and `budget: {scope, spent, forecast, budget,
text, ts}`, the same record is `stages/<id>/budget.json`, and Studio's
Attention queue shows a `team_budget` row (fleet/team_attention.py):
Raise (edit budget_usd in the team file, then run the stage again), Skip
(the stage is skipped) or Stop (the run stops). The budgets are read from
the team file each time, so a raised line counts at once. `summary` is
what `halo team status` shows: spent, the forecast of the stages still to
run, the budget and the holds. `ROWS` is the catalog seam (None: the model
catalog on disk, orchestra/coach_prices.catalog).
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from halo_harness.team import board as BD
from halo_harness.team import spec as S
from halo_harness.work import forecast as F

TURN_IN, TURN_OUT, TURN_USD = 60000, 6000, 0.10
ROWS: Optional[list] = None
FILE = "budget.json"


def _rows(state_dir=None) -> list:
    if ROWS is not None:
        return ROWS
    from halo_harness.orchestra.coach_prices import catalog
    return catalog(state_dir)


def budgets(team: dict) -> "tuple[Optional[float], dict]":
    """`(the team's budget_usd, {stage: budget_usd})`, read from the team file now (else the loaded team)."""
    doc = team
    try:
        if team.get("path"):
            doc = S.normalize(S.load_file(team["path"]))
    except ValueError:
        doc = team
    stages = {s["id"]: s.get("budget_usd") for s in doc["workflow"]["stages"] if s.get("budget_usd") is not None}
    return doc.get("budget_usd"), stages


def _member_model(member: dict, cwd, state_dir) -> str:
    from halo_harness.orchestra.coach_lane_facts import _bio_model
    from halo_harness.team.adapters import member_bio
    return _bio_model(member_bio(member, cwd=cwd, state_dir=state_dir) or "", cwd, state_dir)


def _flow_budget(stage: dict, cwd, state_dir) -> float:
    from halo_harness.flows import spec as fspec
    try:
        path = fspec.find_flow(stage.get("flow") or "", cwd=cwd, state_dir=state_dir)
        flow = fspec.load_flow(path) if path else {}
    except ValueError:
        flow = {}
    steps = [float(s["budget_usd"]) for s in flow.get("steps") or [] if isinstance(s.get("budget_usd"), (int, float))]
    own = flow.get("budget_usd")
    return sum(steps) if steps else (float(own) if isinstance(own, (int, float)) else 0.0)


def stage_forecast(team: dict, stage: dict, members: list, *, root, cwd=None, state_dir=None) -> dict:
    """`{usd, usd_low, usd_high, lines, how}` for one round of `stage`."""
    rows = _rows(state_dir)
    kind = stage.get("kind")
    if kind == "orchestra":
        from halo_harness.orchestra.forecast import for_goal
        from halo_harness.team.resolve import goal_for_stage
        got = for_goal(goal_for_stage(team, stage, root), root, rows=rows, state_dir=state_dir)
        lines, how = got["lanes"], "the Orchestra forecast of its goal"
    elif kind == "flow":
        lines, how = [F.fixed(stage["id"], _flow_budget(stage, cwd or root, state_dir))], "its flow's step budgets"
    else:
        lines = []
        for name in members:
            m = S.member_by_name(team, name) or {"name": name, "lineup": "", "role": "main"}
            x = F.line(name, _member_model(m, cwd or root, state_dir), TURN_IN, TURN_OUT, "turn", rows)
            lines.append(x if x["priced"] else F.fixed(name, TURN_USD, "fixed", x["model"]))
        how = f"{len(members)} member turn(s)"
    t = F.total(lines)
    return {"usd": t["usd"], "usd_low": t["usd_low"], "usd_high": t["usd_high"], "lines": lines, "how": how}


def hold_if_over(runner, sid: str) -> bool:
    """True when stage `sid` is held at a budget line (its row says why); False when it may start."""
    team_b, stage_b = budgets(runner.team)
    if team_b is None and stage_b.get(sid) is None:
        _clear(runner.run_dir, sid)
        return False
    stage, board = runner.stage(sid), runner.board()
    row = BD.row(board, sid) or {}
    members = row.get("members") or S.stage_members(runner.team, stage)
    f = stage_forecast(runner.team, stage, members, root=runner.root, cwd=runner.cwd, state_dir=runner.state_dir)
    spent, own, cost = BD.cost(board), float(row.get("cost_usd") or 0.0), f["usd_high"]
    over = []
    if team_b is not None and spent + cost > team_b + 1e-12:
        over.append(("run", spent, team_b, f"the run spent {F.money(spent)} and stage {sid}'s forecast is "
                                          f"{F.money(cost)}: over the team's budget_usd {F.money(team_b)}"))
    if stage_b.get(sid) is not None and own + cost > stage_b[sid] + 1e-12:
        over.append(("stage", own, stage_b[sid], f"stage {sid} spent {F.money(own)} and its forecast is "
                                                 f"{F.money(cost)}: over its budget_usd {F.money(stage_b[sid])}"))
    if not over:
        _clear(runner.run_dir, sid)
        return False
    scope, so_far, budget, text = over[0]
    hold = {"stage": sid, "scope": scope, "spent": round(so_far, 6), "forecast": round(cost, 6), "budget": budget,
            "how": f["how"], "text": text, "ts": round(time.time(), 3)}
    BD.write_stage_file(runner.run_dir, sid, FILE, hold)
    BD.set_stage(runner.run_dir, sid, "pending", f"budget: {text}", waiting=f"budget: {text}", budget=hold)
    BD.log(runner.run_dir, "note", f"{sid} not started: {text} (raise budget_usd in the team file and run it "
                                   "again, skip it or stop the run)", stage=sid, budget=hold)
    return True


def _clear(run_dir, sid: str) -> None:
    path = Path(run_dir) / "stages" / sid / FILE
    if path.exists():
        try:
            os.unlink(path)
        except OSError:
            pass
        BD.set_stage(run_dir, sid, budget=None, waiting="")


def held(run_dir) -> list:
    """Every stage held at a budget line: its budget.json records."""
    out = []
    for r in BD.read_board(run_dir).get("stages") or []:
        hold = BD.read_stage_file(run_dir, str(r.get("id")), FILE, None)
        if isinstance(hold, dict) and r.get("state") == "pending":
            out.append(hold)
    return out


def skip(run_dir, sid: str, by: str = "") -> "tuple[bool, str]":
    """Skip a held stage (the Attention row's Skip): it is not run in this run."""
    if not any(h.get("stage") == sid for h in held(run_dir)):
        return False, f"stage {sid} of run {Path(run_dir).name} is not held at a budget line"
    os.unlink(Path(run_dir) / "stages" / sid / FILE)
    BD.set_stage(run_dir, sid, "skipped", "skipped at its budget line" + (f" by {by}" if by else ""), waiting="", budget=None)
    return True, f"stage {sid} skipped"


def summary(team: dict, run_dir, *, cwd=None, state_dir=None) -> dict:
    """`{spent, forecast, budget_usd, stages: {sid: budget_usd}, holds}`: forecast = the stages still to run."""
    board = BD.read_board(run_dir)
    team_b, stage_b = budgets(team)
    todo = 0.0
    for r in board.get("stages") or []:
        stage = S.stage_by_id(team, str(r.get("id")))
        if stage is not None and r.get("state") in ("pending", "ready"):
            members = r.get("members") or S.stage_members(team, stage)
            todo += stage_forecast(team, stage, members, root=team["root"], cwd=cwd, state_dir=state_dir)["usd_high"]
    return {"spent": BD.cost(board), "forecast": round(todo, 6), "budget_usd": team_b, "stages": stage_b,
            "holds": held(run_dir)}
