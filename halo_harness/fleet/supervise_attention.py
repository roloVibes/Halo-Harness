"""halo_harness.fleet.supervise_attention -- the supervisor's parked decisions
as rows of the Fleet attention queue (Halo 3.1.8.0 R1; fleet/attention.py
builds the queue, studio/fleet_answer.py routes the keys).

    goal_plan    a plan review the goal asked for       a approve | r reject (text: why) | o open the plan
    goal_gate    a gate past the return cap              a raise the cap by 1 and resume | r raise by N | s stop | o open
    goal_budget  a lane (or a job) would pass a cap      a raise by its cap and resume | r raise by $N | s stop | o open
    goal_ask     a supervised job's ask                  a allow / approve / accept | r deny / answer / edit | s stop | o open

The rows come from `<state>/supervise/decisions/<rid>.json` (supervise/
decisions.py), so they survive Studio starting later and the supervisor
restarting. `rows(home, ...)` turns the open ones into attention rows;
`answer(req, row, key, text)` writes the owner's answer into the decision
file; the supervisor polls it and acts (loop.py). `open_target(row)` opens
the goal's run in the Orchestra section.
"""

from __future__ import annotations

from pathlib import Path

GATE_KEYS = {"goal_gate", "goal_budget"}


def rows(home, local: dict, seen: dict, now: float) -> list:
    from halo_harness.fleet.attention import _row
    from halo_harness.remote.bridge_cards import one_line
    from halo_harness.supervise import decisions
    out = []
    for d in decisions.open_rows(home):
        target = dict(d.get("target") or {}, decision=d["id"], goal=d.get("goal"))
        out.append(_row(d["kind"], d["id"], local, None, "", one_line(d.get("what"), 240),
                        one_line(d.get("detail"), 240), seen, now, **target))
        out[-1]["keys"] = dict(d.get("keys") or {})
        out[-1]["text_for"] = d.get("text_for")
    return out


def answer(req, row: dict, key: str, text: str):
    """`(status, body, label)` for a goal_* row: write the owner's answer into the decision file."""
    from halo_harness.supervise import decisions
    t = row.get("target") or {}
    rid, label = str(t.get("decision") or row["id"]), row["keys"][key]
    home = req.state_dir
    saved, why = decisions.answer(home, rid, key, text, by=_by(home))
    if saved is None:
        return 409, {"error": why}, label
    return 200, {"ok": True, "decision": rid, "key": key}, label


def open_target(row: dict) -> dict:
    t = row.get("target") or {}
    run_dir = t.get("run_dir")
    run = Path(run_dir).name if run_dir else None
    return {"section": "orchestra", "panel": "orchestra-run", "run": run, "goal": t.get("goal")}


def _by(home) -> str:
    try:
        from halo_harness.fleet.identity import fleet_name
        return fleet_name(Path(home) if home is not None else None)
    except Exception:
        return ""
