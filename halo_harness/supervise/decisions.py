"""halo_harness.supervise.decisions -- the decisions the supervisor parks for
its owner (Halo 3.1.8.0 R1). One file per decision, so a row survives Studio
starting later and the supervisor restarting:

    <state>/supervise/decisions/<rid>.json
      {id, kind, goal, what, detail, since, target: {...}, keys: {a|r|s|o: label}, text_for: "r" | None,
       deadline: ts | None, answer: {key, text, by, ts} | None, closed: ts | None, note}

    goal_plan    a plan review the goal asked for (plan: review)      a approve | r reject (text: why) | o open
    goal_gate    the gate sent a piece back past the return cap       a raise the cap by 1 and resume | r raise by N | s stop | o open
    goal_budget  a lane (or a job) would pass a cap                    a raise by the cap's size and resume | r raise by $N | s stop | o open
    goal_ask     a supervised job's permission card or question       a allow once | r deny (text: why) or answer | s stop the goal | o open
    goal_replan  a replan's new plan failed the check twice (R2)      a apply the new plan | r keep the old plan (text: why) | s stop | o open

A replan's review (R2, supervise/replan_ask.py) is a goal_plan row whose
target carries `replan: <n>`: a applies the new plan, r keeps the old one.

Studio's Attention queue lists the open ones (fleet/supervise_attention.py)
and writes an answer into the file; the supervisor polls the files and acts
on each answer once (`answered`), then closes it. A goal_ask waits until its
`deadline` (supervise.tick_s * 720) and is then denied by the supervisor.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

from halo_harness.filelock import file_lock
from halo_harness.privateio import write_private_atomic

KINDS = ("goal_plan", "goal_gate", "goal_budget", "goal_ask", "goal_replan")
KEYS = {
    "goal_plan": {"a": "approve", "r": "reject", "o": "open the plan"},
    "goal_gate": {"a": "raise the cap by 1 and resume", "r": "raise the cap by N", "s": "stop", "o": "open the run"},
    "goal_budget": {"a": "raise by its cap and resume", "r": "raise by $N", "s": "stop", "o": "open the goal"},
    "goal_ask": {"a": "allow once", "r": "deny", "s": "stop the goal", "o": "open the session"},
    "goal_replan": {"a": "apply the new plan", "r": "keep the old plan", "s": "stop the goal", "o": "open the plan"},
}
QUESTION_KEYS = {"r": "answer", "s": "stop the goal", "o": "open the session"}
TEXT_FOR = {"goal_plan": "r", "goal_gate": "r", "goal_budget": "r", "goal_ask": "r", "goal_replan": "r"}
NEEDS_TEXT = {("goal_gate", "r"), ("goal_budget", "r")}
_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


def folder(state_dir) -> Path:
    from halo_harness.supervise.queue import root
    return root(state_dir) / "decisions"


def row_id(kind: str, gid: str, ref: str) -> str:
    return _SAFE.sub("_", f"{kind}-{gid}-{ref}")[:120]


def _path(state_dir, rid: str) -> Path:
    return folder(state_dir) / f"{_SAFE.sub('_', rid)}.json"


def read(state_dir, rid: str) -> Optional[dict]:
    try:
        data = json.loads(_path(state_dir, rid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("id") else None


def _write(state_dir, row: dict) -> None:
    write_private_atomic(_path(state_dir, row["id"]), json.dumps(row, indent=2, sort_keys=True, default=str))


def park(state_dir, kind: str, goal_id: str, ref: str, what: str, detail: str = "", *, deadline: Optional[float] = None,
         keys: Optional[dict] = None, **target) -> dict:
    """The open row for this decision (written once: parking it again returns the same row)."""
    if kind not in KINDS:
        raise ValueError(f"a decision is one of {', '.join(KINDS)}, got {kind!r}")
    rid = row_id(kind, goal_id, ref)
    with file_lock(_path(state_dir, rid)):
        row = read(state_dir, rid)
        if row is not None and not row.get("closed"):
            return row
        row = {"id": rid, "kind": kind, "goal": goal_id, "what": what, "detail": detail[:400],
               "since": round(time.time(), 3), "target": {k: v for k, v in target.items() if v is not None},
               "keys": dict(keys or KEYS[kind]), "text_for": TEXT_FOR.get(kind), "deadline": deadline,
               "answer": None, "closed": None, "note": ""}
        _write(state_dir, row)
    return row


def all_rows(state_dir) -> list:
    d = folder(state_dir)
    if not d.is_dir():
        return []
    rows = [r for r in (read(state_dir, p.stem) for p in d.glob("*.json")) if r is not None]
    return sorted(rows, key=lambda r: (float(r.get("since") or 0), r["id"]))


def open_rows(state_dir) -> list:
    """The rows that wait on the owner: not answered, not closed."""
    return [r for r in all_rows(state_dir) if not r.get("answer") and not r.get("closed")]


def answered(state_dir) -> list:
    """The rows answered and not acted on yet (the supervisor's to do)."""
    return [r for r in all_rows(state_dir) if r.get("answer") and not r.get("closed")]


def answer(state_dir, rid: str, key: str, text: str = "", by: str = "") -> "tuple[Optional[dict], str]":
    """Write the owner's answer: `(row, '')`, or `(None, why)` when it cannot take it."""
    path = _path(state_dir, rid)
    with file_lock(path):
        row = read(state_dir, rid)
        if row is None:
            return None, f"no parked decision {rid!r}"
        if row.get("closed") or row.get("answer"):
            return None, f"{rid} is answered already"
        if key not in row.get("keys") or {}:
            return None, f"a {row['kind']} row takes {', '.join(row.get('keys') or {})}, got {key!r}"
        if (row["kind"], key) in NEEDS_TEXT and not str(text or "").strip():
            return None, f"{row['keys'][key]} needs the number"
        row["answer"] = {"key": key, "text": str(text or "").strip()[:2000], "by": by, "ts": round(time.time(), 3)}
        _write(state_dir, row)
    from halo_harness.supervise import history
    history.decision(state_dir, row.get("goal"), rid, key, by)
    from halo_harness.knowledge.writers import answered  # 3.1.8.0 R4: the answer and its why as a decision
    answered(state_dir, row)
    return row, ""


def close(state_dir, rid: str, note: str = "") -> None:
    path = _path(state_dir, rid)
    with file_lock(path):
        row = read(state_dir, rid)
        if row is None or row.get("closed"):
            return
        row["closed"], row["note"] = round(time.time(), 3), note
        _write(state_dir, row)


def reopen(state_dir, rid: str, detail: str) -> None:
    """An answer the supervisor could not apply (a plan that fails its check): the row waits again."""
    path = _path(state_dir, rid)
    with file_lock(path):
        row = read(state_dir, rid)
        if row is None:
            return
        row["answer"], row["closed"], row["detail"] = None, None, detail[:400]
        _write(state_dir, row)


def close_goal(state_dir, goal_id: str, note: str) -> int:
    """Close every row of a goal still open (the goal ended or was cancelled)."""
    n = 0
    for row in all_rows(state_dir):
        if row.get("goal") == goal_id and not row.get("closed"):
            close(state_dir, row["id"], note)
            n += 1
    return n


def number(text: str, default: float) -> float:
    """The N a raise answer typed ('2', '$1.50', '+3'), else `default`."""
    m = re.search(r"\d+(?:\.\d+)?", str(text or ""))
    return float(m.group(0)) if m else float(default)
