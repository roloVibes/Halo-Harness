"""halo_harness.local_sched.loads -- the loading tax: how many loads a session paid and the seconds they took (Halo
3.3.7.0 R3; plans/local-model-fit-brief.md G5).

    record(state_dir, *, session, host, model, seconds, why)   one line in <state>/local_sched/loads.jsonl
        (the scheduler's own loads: a pivot, `halo local warm`)
    tally(state_dir, session) -> {count, seconds, per_model {model: {count, seconds}}, line}
    recent(state_dir, host=None, since=86400) -> every load line on that host (3.3.7.0 R4: what idle reads)
    line_for(t) -> "loading: 7 loads, 3 m 02 s (qwen3.8:27b 4, qwen3-coder:30b 3)" | "loading: no loads"

A load is a ledger line of the session whose `load_ms` was over 2 s (the call that paid the load:
ollama_steward/ledger_prompt.WARM_LOAD_MS), plus each load the scheduler made for it (the call after a pivot finds
its model loaded, so nothing is counted twice). Local cost is time: the seconds are the measure, beside the
dollars ("saved vs cloud" on `/cost`). No request is sent.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("bridge")

FILE = "loads.jsonl"


def _path(state_dir) -> Path:
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    return Path(state_dir) / "local_sched" / FILE


def record(state_dir, *, session: Optional[str], host: str, model: str, seconds: float, why: str) -> None:
    try:
        p = _path(state_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        from halo_harness.ollama_steward.ledger import now_iso
        row = {"at": now_iso(), "session": session, "host": host, "model": model, "seconds": round(float(seconds), 1),
               "why": why}
        with p.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        log.debug("local_sched.loads: the load line could not be written", exc_info=True)


def _own(state_dir, session: str) -> list:
    out = []
    try:
        for raw in _path(state_dir).read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("session") == session:
                out.append(row)
    except OSError:
        pass
    return out


def recent(state_dir, *, host: Optional[str] = None, since: float = 86400.0) -> list:
    """3.3.7.0 R4: every load line on `host` (any session, the refresh's too) newer than `since` seconds."""
    from halo_harness.ollama_steward.ledger import parse_at
    cutoff, out = time.time() - since, []
    try:
        raw = _path(state_dir).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in raw:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and (not host or str(row.get("host") or "").lower() == host.lower())                 and (parse_at(row.get("at")) or 0) >= cutoff:
            out.append(row)
    return out


def _ledger(state_dir, session: str) -> list:
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.ledger_prompt import WARM_LOAD_MS
    try:
        lines = read_calls(state_dir if state_dir is not None else _path(None).parent.parent)
    except Exception:
        return []
    return [{"model": x.get("model"), "seconds": x["load_ms"] / 1000.0, "host": (x.get("host") or {}).get("name")}
            for x in lines if x.get("session") == session and isinstance(x.get("load_ms"), (int, float))
            and not isinstance(x.get("load_ms"), bool) and x["load_ms"] > WARM_LOAD_MS]


def tally(state_dir, session: Optional[str]) -> dict:
    if not session:
        return {"count": 0, "seconds": 0.0, "per_model": {}, "line": line_for({"count": 0})}
    from halo_harness.ollama_steward.profiles import short_model
    rows = _ledger(state_dir, session) + _own(state_dir, session)
    per: dict = {}
    for r in rows:
        m = per.setdefault(short_model(r.get("model") or "?"), {"count": 0, "seconds": 0.0})
        m["count"] += 1
        m["seconds"] = round(m["seconds"] + float(r.get("seconds") or 0), 1)
    t = {"count": len(rows), "seconds": round(sum(float(r.get("seconds") or 0) for r in rows), 1), "per_model": per,
         "at": time.time()}
    t["line"] = line_for(t)
    return t


def line_for(t: dict) -> str:
    from halo_harness.local_sched.swap_cost import secs
    n = int(t.get("count") or 0)
    if not n:
        return "loading: no loads"
    per = sorted((t.get("per_model") or {}).items(), key=lambda kv: (-kv[1]["count"], kv[0]))
    parts = ", ".join(f"{m} {v['count']}" for m, v in per[:4]) if len(per) > 1 else ""
    return f"loading: {n} load{'s' * (n != 1)}, {secs(t.get('seconds') or 0)}" + (f" ({parts})" if parts else "")
