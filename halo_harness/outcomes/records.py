"""halo_harness.outcomes.records -- `~/.halo/coach/outcomes.jsonl`, one line per
agent task (Halo 3.1.8.0 R3, docs/OUTCOMES.md "outcomes.jsonl"):

    {"run": "<run id | session id>", "task": "lane 2 | agent 3f2a1b9c", "source": "orchestra | session",
     "run_dir": "<run folder>" | "", "bio": "auto-coder", "model": "or:vendor/model", "kind": "code",
     "outcome": "passed | returned | failed | stopped | done", "check": "gate | acceptance | stage | ",
     "returns": 0, "cost_usd": 0.0123, "tests_passed": 12, "tests_failed": 0, "sources": 0,
     "evidence": "<path of its evidence.json>", "ts": 1760800000.0,
     "picked": "auto | measured | none", "reason": "<the pick's one line> | "}     (3.1.9.0 R3)

An Orchestra lane's outcome is read from the run's report: the run finished
-> `passed` (no send-back) or `returned` (sent back at least once); the run
stopped -> `failed` for a lane that failed or reached the return cap, else
`stopped` (the run stopped for another reason). A session sub-agent's
outcome is its acceptance check's (`passed`, `returned` after the retry,
`failed`), else its stage gate's, else `failed` when it ended on an error and
`done` when nothing checked it. `check` names what gave the verdict; a rate
(outcomes/measured.py) counts only checked `passed | returned | failed` rows.

`record_orchestra(run_dir, report)` appends a finished or stopped run's lane
rows once per report (write_report and the coach's `note_run` both call it);
`read(...)` returns the rows, the newest per task when a task was recorded
again (a resumed run).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

OUTCOMES = "outcomes.jsonl"
WORDS = ("passed", "returned", "failed", "stopped", "done")
RATED = ("passed", "returned", "failed")
PICKS = ("auto", "measured", "none")  # 3.1.9.0 R3: a row's `picked`


def path(state_dir=None) -> Path:
    from halo_harness.orchestra.coach_record import folder
    return folder(state_dir) / OUTCOMES


def append(rows: list, state_dir=None) -> int:
    if not rows:
        return 0
    from halo_harness.orchestra import jsonl
    target = path(state_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    with jsonl.locked(target):
        with open(target, "a", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows))
    return len(rows)


def make_row(*, run: str, task: str, source: str, ev=None, bio: str = "", model: str = "", kind: str = "",
             outcome: str, check: str = "", returns: int = 0, cost_usd: float = 0.0, run_dir: str = "",
             evidence_path: str = "", ts: Optional[float] = None, picked: str = "none", reason: str = "",
             **extra) -> dict:
    """One row. 3.1.9.0 R3: `picked` -- `auto` / `measured` when the model was picked at spawn for the task
    (models_auto_spawn.record), else `none`; `reason` -- that pick's one line ("" without one)."""
    row = {"run": run, "task": task, "source": source, "run_dir": run_dir,
           "bio": bio or (ev.bio if ev else ""), "model": model or (ev.model if ev else ""),
           "kind": kind or (ev.kind if ev else "other"), "outcome": outcome, "check": check,
           "returns": int(returns or 0), "cost_usd": round(float(cost_usd or (ev.cost_usd if ev else 0.0) or 0.0), 6),
           "tests_passed": ev.tests_passed if ev else 0, "tests_failed": ev.tests_failed if ev else 0,
           "sources": len(ev.sources) if ev else 0, "evidence": evidence_path, "ts": round(ts or time.time(), 3),
           "picked": picked if picked in PICKS else "none", "reason": str(reason or "")}
    row.update({k: v for k, v in extra.items() if v not in (None, "")})
    return row


def _capped(reason: str) -> set:
    m = re.match(r"lane ([\d, ]+) reached the return cap", str(reason or ""))
    return {int(x) for x in re.findall(r"\d+", m.group(1))} if m else set()


def lane_outcome(lane: dict, report: dict) -> str:
    if report.get("status") == "finished":
        return "returned" if int(lane.get("pieces_returned") or 0) else "passed"
    if lane.get("state") == "failed" or int(lane.get("lane") or 0) in _capped(report.get("stop_reason")):
        return "failed"
    return "stopped"


def orchestra_rows(run_dir, report: dict) -> list:
    """One row per lane of the report."""
    from halo_harness.orchestra import events as run_events, jsonl
    from halo_harness.orchestra.coach_lane_facts import lane_facts
    from halo_harness.orchestra.lanes import lane_rows
    from halo_harness.outcomes.lane import evidence_path, load_lane
    run_dir = Path(run_dir)
    goal = jsonl.read_json(run_dir / "goal.json", {}) or {}
    facts = {f["lane"]: f for f in lane_facts(run_dir, goal, lane_rows(run_dir), run_events.read(run_dir))}
    out = []
    for lane in report.get("lanes") or []:
        n = int(lane.get("lane") or 0)
        ev, f = load_lane(run_dir, n), facts.get(n) or {}
        out.append(make_row(run=str(report.get("run_id") or run_dir.name), task=f"lane {n}", source="orchestra", ev=ev,
                            bio=f.get("bio") or "", model=f.get("model") or "", kind=ev.kind if ev else "code",
                            outcome=lane_outcome(lane, report), check="gate", returns=lane.get("pieces_returned"),
                            cost_usd=lane.get("cost_usd"), run_dir=str(run_dir.resolve()),
                            evidence_path=str(evidence_path(run_dir, n)) if ev else "", ts=report.get("ts"),
                            report_ts=report.get("ts")))
    return out


def record_orchestra(run_dir, report: Optional[dict] = None, state_dir=None) -> int:
    """Append the run's lane rows once per report; the number of rows the run has. Never raises."""
    try:
        if report is None:
            from halo_harness.orchestra.report import load_report
            report = load_report(run_dir)
        if not isinstance(report, dict) or report.get("status") not in ("finished", "stopped"):
            return 0
        key = str(Path(run_dir).resolve())
        mine = [r for r in read_all(state_dir) if r.get("run_dir") == key]
        if any(r.get("report_ts") == report.get("ts") for r in mine):
            return len({r.get("task") for r in mine})
        rows = orchestra_rows(run_dir, report)
        append(rows, state_dir)
        return len({r.get("task") for r in mine + rows})
    except Exception:
        return 0


def read_all(state_dir=None) -> list:
    from halo_harness.orchestra import jsonl
    return [r for r in jsonl.read_lines(path(state_dir)) if isinstance(r, dict) and r.get("outcome") in WORDS]


def since_ts(text) -> Optional[float]:
    """`7d`, `24h`, `30m`, `2026-10-20` or an epoch -> epoch seconds; None when it does not read."""
    raw = str(text or "").strip().lower()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([dhm])", raw)
    if m:
        return time.time() - float(m.group(1)) * {"d": 86400, "h": 3600, "m": 60}[m.group(2)]
    try:
        import datetime
        return datetime.datetime.strptime(raw, "%Y-%m-%d").timestamp()
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return None


def read(state_dir=None, *, since: Optional[float] = None, bio: str = "", model: str = "", kind: str = "") -> list:
    """The rows, oldest first, the newest row per task; filtered by any of the arguments."""
    latest: dict = {}
    for r in read_all(state_dir):
        latest[(r.get("run_dir") or r.get("run"), r.get("task"))] = r
    rows = sorted(latest.values(), key=lambda r: float(r.get("ts") or 0))
    return [r for r in rows if (since is None or float(r.get("ts") or 0) >= since) and (not bio or r.get("bio") == bio)
            and (not model or r.get("model") == model) and (not kind or r.get("kind") == kind)]
