"""halo_harness.ollama_steward.server_events -- Halo 3.3.4.0 R2: where the
server's events go and how they read.

    record_events(state_dir, events, host=..., quiet=...)
        every event appended to `<state>/ollama/events.jsonl` with its host
        and an ISO `at`; `notify` says whether it passed the quiet period
        (QUIET_S per kind: the notification side -- R4's job, the TUI, Studio
        -- shows only those; the file keeps every event)
    read_events(state_dir, since=None, kind=None, host=None)
    ps_delta(before, now, at)  `/api/ps` rows before and now -> loaded /
        unloaded / reloaded (the same model at another window: R1 found two
        windows for one model reload it every call) and cpu-spill (size_vram
        under size on a fresh load)
    format_event(e)            the line `halo ollama events` prints
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

from halo_harness.ollama_steward import ledger
from halo_harness.ollama_steward.server_rules import event

EVENTS_FILE = "events.jsonl"
QUIET_S = 600.0


def events_path(state_dir) -> Path:
    return ledger.ledger_dir(state_dir) / EVENTS_FILE


def passes_quiet(ev: dict, quiet: dict, now: float) -> bool:
    """True when this kind has not been notified in the last QUIET_S (and marks it notified)."""
    kind = ev.get("kind")
    last = quiet.get(kind)
    if isinstance(last, (int, float)) and now - last < QUIET_S:
        return False
    quiet[kind] = now
    return True


def record_events(state_dir, events: list, *, host: Optional[str] = None, quiet: Optional[dict] = None,
                  now: Optional[float] = None) -> list:
    """Append `events` (each gets `host`, an ISO `at`, `notify`); returns them as written."""
    if not events or state_dir is None:
        return []
    from halo_harness.filelock import file_lock
    now = time.time() if now is None else now
    quiet = quiet if quiet is not None else {}
    rows = []
    from halo_harness.ollama_steward.failure_lines import explain  # 3.3.6.0 R1: the fix, read off the profile
    for ev in events:
        ev = explain(ev, state_dir)
        at = ev.get("at")
        row = {**ev, "host": host, "at": ledger.now_iso(at if isinstance(at, (int, float)) else now)}
        row["notify"] = passes_quiet(row, quiet, at if isinstance(at, (int, float)) else now)
        rows.append(row)
    path = events_path(state_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(path, timeout=2.0):
            with open(path, "a", encoding="utf-8", newline="\n") as f:
                for row in rows:
                    f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except OSError:
        return []
    from halo_harness.ollama_steward import ledger_tap  # 3.3.5.0 R1: the Local tab's traffic shows them inline
    ledger_tap.events(state_dir, rows)
    return rows


def read_events(state_dir, since=None, kind: Optional[str] = None, host: Optional[str] = None) -> list:
    """Every event, oldest first; `since` seconds back or a span such as "24h"."""
    if isinstance(since, str):
        since = ledger.parse_since(since)
    cutoff = time.time() - since if isinstance(since, (int, float)) else None
    out = []
    try:
        with open(events_path(state_dir), "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                try:
                    row = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                t = ledger.parse_at(row.get("at"))
                if cutoff is not None and (t is None or t < cutoff):
                    continue
                if kind and row.get("kind") != kind:
                    continue
                if host and str(row.get("host") or "").lower() != host.lower():
                    continue
                out.append(row)
    except OSError:
        return []
    return out


def _gib(n) -> str:
    return f"{n / 2 ** 30:.1f} GiB" if isinstance(n, (int, float)) else "?"


def ps_delta(before: Optional[list], now: list, at: float) -> list:
    """Two `/api/ps` readings (hardware_sources.parse_ps rows) -> events; the
    first reading (`before` None) only sets the baseline."""
    if before is None:
        return []
    old = {r.get("model"): r for r in before if r.get("model")}
    new = {r.get("model"): r for r in now if r.get("model")}
    out = []
    for name, row in new.items():
        size, vram, ctx = row.get("size"), row.get("size_vram"), row.get("context_length")
        data = {"size": size, "size_vram": vram, "expires": row.get("expires"), "context_length": ctx}
        prev = old.get(name)
        if prev is None:
            out.append(event("loaded", f"{name} loaded ({_gib(size)}, {_gib(vram)} on the GPU, window {ctx or '?'})",
                             f"/api/ps {name}", at=at, model=name, **data))
        elif ctx and prev.get("context_length") and ctx != prev.get("context_length"):
            out.append(event("reloaded", f"{name} reloaded at another window ({prev.get('context_length')} -> {ctx}): "
                             "two windows for one model reload it every call; one window per host and model fixes "
                             "it", f"/api/ps {name}", at=at, model=name, previous_context_length=prev.get("context_length"),
                             **data))
        else:
            continue
        if isinstance(size, int) and isinstance(vram, int) and vram < size:
            out.append(event("cpu-spill", f"{name} holds {_gib(size - vram)} in system RAM ({_gib(vram)} of "
                             f"{_gib(size)} on the GPU)", f"/api/ps {name}", at=at, model=name, **data))
    for name in old:
        if name not in new:
            out.append(event("unloaded", f"{name} unloaded", f"/api/ps {name}", at=at, model=name))
    return out


def format_event(e: dict) -> str:
    t = ledger.parse_at(e.get("at"))
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) if t is not None else "?"
    model = f" [{e['model']}]" if e.get("model") else ""
    return f"{when} {e.get('severity', 'info'):<5} {e.get('kind')}{model}: {e.get('say')}"
