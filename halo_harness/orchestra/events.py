"""halo_harness.orchestra.events -- the run's timed log, `<run>/events.jsonl`.

One JSON object per line:

    {"ts": 1760300000.123, "elapsed_s": 12.5, "lane": 2 | null,
     "kind": "claim", "text": "s1/a2 claimed basket.py#total", "data": {...}}

Kinds: state, claim, merge, gate, report, note. `elapsed_s` counts from the
run's start (run.json `created`). `emit()` also publishes the matching
session-feed event (`orchestra_<kind>` in halo_harness/events.py) when a
session with an event sink is given; `note` lines stay in the file only.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl

KINDS = ("state", "claim", "merge", "gate", "report", "note")
FEED_KINDS = {k: f"orchestra_{k}" for k in ("state", "claim", "merge", "gate", "report")}


def events_path(run_dir) -> Path:
    return Path(run_dir) / "events.jsonl"


def log(run_dir, kind: str, text: str, lane: Optional[int] = None, **data) -> dict:
    """Append one timed line and return it. Raises ValueError for an unknown kind."""
    return append(run_dir, kind, text, lane, data)


def append(run_dir, kind: str, text: str, lane: Optional[int], data: dict) -> dict:
    """`log` with `data` as one dict (any keys)."""
    if kind not in KINDS:
        raise ValueError(f"event kind must be one of {', '.join(KINDS)}, got {kind!r}")
    path = events_path(run_dir)
    with jsonl.locked(path):
        ts = time.time()  # taken under the lock, so the file's times never go backwards
        entry = {"ts": round(ts, 3), "elapsed_s": jsonl.elapsed(run_dir, ts), "lane": lane,
                 "kind": kind, "text": str(text), "data": dict(data or {})}
        jsonl.append_line(path, entry)
    return entry


def read(run_dir, since: int = 0) -> list:
    """Every line from entry number `since` on (0 = all). A poller passes the
    count it has already seen and gets only the new ones."""
    entries = jsonl.read_lines(events_path(run_dir))
    return entries[max(0, int(since)):]


def _sink_of(session):
    if session is None:
        return None
    if callable(session) and not hasattr(session, "_event_sink"):
        return session
    return getattr(session, "_event_sink", None)


def emit(session_or_none, kind: str, data: Optional[dict] = None, *, run_dir=None) -> dict:
    """Log to the run file and, when `session_or_none` is a Session with an
    event sink (or a plain callable sink), publish `orchestra_<kind>` with
    the same entry as its data. `data["text"]` and `data["lane"]` become the
    line's text and lane; the rest stays in `data`. `run_dir` defaults to
    $HALO_ORCHESTRA_RUN. A sink failure never fails the log."""
    if run_dir is None:
        import os
        from halo_harness.orchestra import RUN_ENV
        run_dir = os.environ.get(RUN_ENV) or None
        if run_dir is None:
            raise ValueError("emit: no run_dir given and $HALO_ORCHESTRA_RUN is not set")
    rest = dict(data or {})
    text = str(rest.pop("text", "") or "")
    lane = rest.pop("lane", None)
    entry = append(run_dir, kind, text, lane, rest)
    sink = _sink_of(session_or_none)
    feed_kind = FEED_KINDS.get(kind)
    if sink is not None and feed_kind is not None:
        try:
            from halo_harness import events as feed
            sink(feed.Event(feed_kind, dict(entry, run=Path(run_dir).name)))
        except Exception:
            pass
    return entry


def format_line(entry: dict) -> str:
    """`+12.5s  lane 2  claim  s1/a2 claimed basket.py#total` -- the CLI's line."""
    lane = entry.get("lane")
    lane_txt = f"lane {lane}" if lane is not None else "      "
    return f"+{float(entry.get('elapsed_s') or 0):8.1f}s  {lane_txt:<7} {entry.get('kind', ''):<6} {entry.get('text', '')}"
