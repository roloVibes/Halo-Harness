"""halo_harness.fleet.journal -- what the hub saw, kept for the digest (Halo
3.0.5.0 "Fleet" round R4): one JSON line per thing, appended by Studio's
fleet watcher (studio/fleet_watch.py) and the Fleet routes, read by
digest.py (`GET /api/fleet/digest`, `halo fleet digest`).

    <home>/fleet/journal.jsonl     0600; past MAX_BYTES it rolls to journal.1.jsonl (one old file kept)

Every line is `{ts, kind, harness, harness_name, session_id?, agent_id?, ...}`
with kind one of:

    session_start {title, started}   a session showed up on a harness
    session_end   {title}            it left
    cost          {usd}              a member session's cost so far (at most once a minute per session)
    file          {file, agent}      an agent touched a file (Edit / Write, or an Orchestra claim)
    error         {text}             an error frame, or an agent that failed
    decision      {what, answer, by, row_kind}   a card answered from Studio, and who answered it
    handoff       {action, to?, issue?, path?, by}
    cap_pause     {scope, key, spent, cap}   a cap paused sessions; cap_ack {scope, key, day}: lifted for the day
    ack           {row}              an attention row set aside from Studio
    mission_planned {mission, parts, by}, mission_approved {mission, by}, mission_run {mission, by},
    mission_part {mission, part, state, cost_usd?, error?}, mission_claim {mission, part, file, tool},
    mission_end {mission, state, cost_usd, reason, parts}      a fleet mission (3.0.6.0 R7, fleet/mission_run.py)
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

MAX_BYTES = 4_000_000
KINDS = ("session_start", "session_end", "cost", "file", "error", "decision", "handoff", "cap_pause", "cap_ack", "ack",
         "mission_planned", "mission_approved", "mission_run", "mission_part", "mission_claim", "mission_end")  # R7
_lock = threading.Lock()


def path(home) -> Path:
    return Path(home) / "fleet" / "journal.jsonl"


def append(home, kind: str, **fields) -> Optional[dict]:
    if kind not in KINDS:
        raise ValueError(f"journal kind must be one of {', '.join(KINDS)}, got {kind!r}")
    entry = {"ts": round(time.time(), 3), "kind": kind, **{k: v for k, v in fields.items() if v is not None}}
    p = path(home)
    line = json.dumps(entry, ensure_ascii=False, default=str) + "\n"
    with _lock:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.is_file() and p.stat().st_size > MAX_BYTES:
                p.replace(p.with_name("journal.1.jsonl"))
            new = not p.exists()
            with open(p, "a", encoding="utf-8") as f:
                f.write(line)
            if new:
                try:
                    p.chmod(0o600)
                except OSError:
                    pass
        except OSError:
            return None
    return entry


def read(home, since: float = 0.0, kinds=None) -> list:
    """Every line at or after `since` (both files, oldest first)."""
    out = []
    want = set(kinds) if kinds else None
    p = path(home)
    for f in (p.with_name("journal.1.jsonl"), p):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and float(row.get("ts") or 0) >= since and (want is None or row.get("kind") in want):
                out.append(row)
    return out


def day() -> str:
    return time.strftime("%Y-%m-%d")
