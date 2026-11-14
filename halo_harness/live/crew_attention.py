"""halo_harness.live.crew_attention -- a Try it run that ended while nobody looked at it, as a row of the attention
queue (Halo 3.6.0.0 R1; the 3.4.1.3 rule: finished background work shows without a prompt).

    crew_try   a Try it run of the last day that ended (done, stopped or failed) and that the Agents tab has not
               shown yet (crew/trial.py `seen`)          a set aside | o open the agent in the Agents tab (a
               workflow's run, 3.6.0.0 R2: the workflow in the Workflows tab)

Setting it aside marks the run seen, so the row does not come back.
"""

from __future__ import annotations

KIND = "crew_try"


def rows(home, local: dict, seen: dict, now: float) -> list:
    try:
        return _rows(home, local, seen, now)
    except Exception:  # the queue never fails over a run's file
        return []


def _rows(home, local: dict, seen: dict, now: float) -> list:
    from halo_harness.crew import trial
    from halo_harness.live.attention import _row
    out = []
    for rec in trial.recent(home):
        if rec.get("seen") or rec.get("state") in ("running", "stopping"):
            continue
        state = rec.get("state")
        cost = rec.get("cost_usd")
        money = f" · ${cost:.4f}" if isinstance(cost, (int, float)) else ""
        flow = rec.get("kind") == "workflow"  # 3.6.0.0 R2: a workflow's run opens on the Workflows tab
        what = f"Try it {'finished' if state == 'done' else state}: {'workflow ' if flow else ''}{rec.get('agent')}{money}"
        detail = " ".join(str(rec.get("line") or rec.get("reply") or rec.get("error") or "").split())[:240]
        out.append(_row(KIND, str(rec.get("id")), local, None, "", what, detail, seen, now,
                        agent=rec.get("agent"), try_id=rec.get("id"), run="workflow" if flow else "agent"))
    return out


def open_target(row: dict) -> dict:
    t = row.get("target") or {}
    view = "flows" if t.get("run") == "workflow" else "crew"
    return {"section": "agents", "view": view, "agent": t.get("agent"), "try": t.get("try_id")}


def set_aside(home, row: dict) -> None:
    from halo_harness.crew import trial
    tid = (row.get("target") or {}).get("try_id")
    if tid:
        trial.seen(str(tid), home)
