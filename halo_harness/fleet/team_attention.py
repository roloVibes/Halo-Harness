"""halo_harness.fleet.team_attention -- a team stage held at its gate, as a
row of the Fleet attention queue (Halo 3.0.8.0 round R2; fleet/attention.py
builds the queue, studio/fleet_answer.py routes the keys).

    team_gate   a stage of this repo's team run waits at a required gate:
                a accept | r redo (text: the instruction) | s stop the run | o open the Team section on it
    team_budget a stage was not started: over the team's or its own budget_usd (3.1.2.0 R2, team/budget.py):
                a raise (opens the team file: edit budget_usd, then run it again) | r skip it | s stop the run

`gated(cwd, state_dir)` reads the team of Studio's folder (docs/TEAM.md) and
its latest run: one entry per stage whose gate is open, and (`kind: budget`)
per stage held at a budget line. `rows(...)` makes them attention rows;
`answer(...)` goes through `POST team/answer` (a gate, the Team tab's gate
card's route) or `POST team/budget` (a hold).
"""

from __future__ import annotations

import time
from pathlib import Path

ACTION = {"a": "accept", "r": "redo", "s": "stop"}
ROOT_TTL_S = 60.0
_roots: dict = {}   # cwd -> (when, the repo root): the watcher ticks every 3 s, git answers once a minute


def _root(cwd) -> Path:
    from halo_harness.team import spec as S
    key = str(cwd)
    hit = _roots.get(key)
    if hit is None or time.monotonic() - hit[0] > ROOT_TTL_S:
        hit = _roots[key] = (time.monotonic(), S.team_root(cwd))
    return hit[1]


def gated(cwd, state_dir) -> list:
    """`[{team, run, stage, round, summary, acceptance, root}]` for each open gate of the team's latest open run."""
    from halo_harness.team import board as BD
    from halo_harness.team import spec as S
    from halo_harness.team.stages import read_gate
    if cwd is None:
        return []
    root = _root(cwd)
    if not (S.repo_team_path(root).is_file() or S.user_team_path(root, state_dir).is_file()):
        return []
    run_dir = BD.latest_run(root, open_only=True)
    if run_dir is None:
        return []
    try:
        team = S.load_team(root, state_dir)
    except ValueError:
        return []
    if team is None:
        return []
    from halo_harness.team.budget import held
    out = [{"kind": "budget", "team": team["name"], "run": run_dir.name, "stage": h.get("stage"), "root": team["root"],
            "text": h.get("text") or "", "ts": h.get("ts")} for h in held(run_dir)]
    for r in BD.read_board(run_dir).get("stages") or []:
        if r.get("state") != "gated":
            continue
        gate = read_gate(run_dir, str(r.get("id"))) or {}
        out.append({"team": team["name"], "run": run_dir.name, "stage": r.get("id"), "round": gate.get("round", r.get("round")),
                    "summary": str(gate.get("summary") or r.get("summary") or ""), "root": team["root"],
                    "acceptance": gate.get("acceptance")})
    return out


def rows(gates: list, local: dict, seen: dict, now: float) -> list:
    from halo_harness.fleet.attention import _row
    from halo_harness.remote.bridge_cards import one_line
    out = []
    for g in gates:
        if g.get("kind") == "budget":
            out.append(_row("team_budget", f"{g['run']}:{g['stage']}:{g.get('ts')}", local, None, "",
                            f"Team {g['team']}: stage {g['stage']} is held at its budget line",
                            one_line(g.get("text") or "raise the budget, skip the stage or stop the run", 240),
                            seen, now, run=g["run"], stage=g["stage"]))
            continue
        acc = g.get("acceptance") if isinstance(g.get("acceptance"), dict) else None
        note = f" (acceptance {'ok' if acc.get('ok') else 'failed'}: {acc.get('note')})" if acc and acc.get("note") else ""
        out.append(_row("team_gate", f"{g['run']}:{g['stage']}:{g.get('round')}", local, None, "",
                        f"Team {g['team']}: stage {g['stage']} waits at its gate",
                        one_line((g.get("summary") or "accept it, redo it with an instruction, or stop the run") + note, 240),
                        seen, now, run=g["run"], stage=g["stage"]))
    return out


def answer(req, row: dict, key: str, text: str):
    """`(status, body, label)` for a team_gate row (the gate card's own route) or a team_budget row."""
    from halo_harness.studio.fleet_answer import _sub
    from halo_harness.studio.team_api import post_answer
    t, label = row.get("target") or {}, row["keys"][key]
    if row.get("kind") == "team_budget":
        if key == "a":  # the budget lives in the team file: Raise opens it
            return 200, {"open": dict(open_target(row), panel="team-file")}, label
        from halo_harness.studio.team_budget_api import post_budget
        status, got = post_budget(_sub(req, "team/budget", {"stage": t.get("stage"), "run": t.get("run"),
                                                            "action": "skip" if key == "r" else "stop"}, {}))
        return status, got, label
    body = {"stage": t.get("stage"), "run": t.get("run"), "action": ACTION[key], "text": text if key == "r" else ""}
    status, got = post_answer(_sub(req, "team/answer", body, {}))
    return status, got, label


def open_target(row: dict) -> dict:
    t = row.get("target") or {}
    return {"section": "team", "panel": "team-inspector", "run": t.get("run"), "stage": t.get("stage")}
