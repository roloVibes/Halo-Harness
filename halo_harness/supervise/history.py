"""halo_harness.supervise.history -- `<state>/supervise/history.jsonl` (Halo
3.1.8.0 R1): one line per goal state change and one per decision answered.

    {"ts", "goal", "from", "to", "why", "cost_usd", "run_dir" | "bg_id"}   a state change
    {"ts", "goal", "row", "key", "by"}                                    a decision answered

`halo goal show` prints a goal's lines; `summary` is the morning line
Studio's Session landing shows ("N goals done, M waiting on you, $X").
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from halo_harness.filelock import file_lock

FILE = "history.jsonl"
DAY_S = 86400.0


def path(state_dir) -> Path:
    from halo_harness.supervise.queue import root
    return root(state_dir) / FILE


def append(state_dir, row: dict) -> dict:
    """Add one line (best-effort); `ts` is filled in when missing."""
    line = {"ts": round(time.time(), 3), **{k: v for k, v in row.items() if v is not None}}
    p = path(state_dir)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(p):
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, sort_keys=True, default=str) + "\n")
    except OSError:
        pass
    return line


def change(state_dir, goal: dict, before: str, after: str, why: str = "") -> dict:
    """The line for a goal moving from `before` to `after`."""
    row = {"goal": goal.get("id"), "from": before, "to": after, "why": why or goal.get("why") or "",
           "cost_usd": round(float(goal.get("cost_usd") or 0.0), 6)}
    if goal.get("run_dir"):
        row["run_dir"] = goal["run_dir"]
    if goal.get("bg_id"):
        row["bg_id"] = goal["bg_id"]
    return append(state_dir, row)


def decision(state_dir, goal_id: str, row_id: str, key: str, by: str) -> dict:
    return append(state_dir, {"goal": goal_id, "row": row_id, "key": key, "by": by})


def read(state_dir, goal: Optional[str] = None, since: Optional[float] = None) -> list:
    """Every line (of one goal, after `since`), oldest first; a bad line is skipped."""
    try:
        text = path(state_dir).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for raw in text.splitlines():
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        if goal is not None and row.get("goal") != goal:
            continue
        if since is not None and float(row.get("ts") or 0) < since:
            continue
        out.append(row)
    return out


def format_line(row: dict) -> str:
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(row.get("ts") or 0)))
    if row.get("row"):
        return f"  {when}  decision {row.get('key')} on {row.get('row')} by {row.get('by') or '?'}"
    why = f" ({row['why']})" if row.get("why") else ""
    where = row.get("run_dir") or row.get("bg_id") or ""
    return (f"  {when}  {row.get('from') or '-'} -> {row.get('to')}{why}  ${float(row.get('cost_usd') or 0):.4f}"
            + (f"  {Path(str(where)).name}" if where else ""))


def summary(state_dir, now: Optional[float] = None, within_s: float = DAY_S) -> dict:
    """`{done, waiting, cost_usd, since}` for the last day: goals that reached done, the decisions
    still open (decisions.py), what the goals that ended spent."""
    now = time.time() if now is None else now
    since = now - within_s
    done, cost = set(), {}
    for row in read(state_dir, since=since):
        if row.get("row"):
            continue
        if row.get("to") == "done":
            done.add(row.get("goal"))
        if row.get("to") in ("done", "stopped", "failed", "parked"):
            cost[row.get("goal")] = float(row.get("cost_usd") or 0.0)
    from halo_harness.supervise import decisions
    waiting = len(decisions.open_rows(state_dir))
    return {"done": len(done), "waiting": waiting, "cost_usd": round(sum(cost.values()), 6), "since": since}
