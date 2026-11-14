"""halo_harness.live.session_cost -- what a session cost, read from its record (Halo 3.4.0.1 "Found live", defects
10, 17, 21, 26): the one source of truth for a session's spend, open or finished.

A session's record is its transcript `<state>/sessions/<project>/<sid>.jsonl`; every model call appends one `usage`
line with its `cost_usd` (a sub-agent's spend is rolled up into its parent's record the same way). A call Halo could
not price has `cost_usd: null` and names its model: that spend is unknown, never $0.

    of_record(path)             {usd, complete, unknown: [models], started, calls}   (cached by size and mtime)
    today(state_dir=None, now=) {usd, sessions, complete, unknown, projects}   every session STARTED today (local
                                                                     time), finished or open (docs/FLEET.md "Caps");
                                                                     3.4.1.0 R5: `projects` {key: {usd, sessions}}
                                                                     by the project key the caps use (live/caps.py)
    started(path)               the first `ts` the record names (its meta line), else None

Readers: the harness's own `cost_today` (peers/local_view.py, so the hub's machine and every member say the same),
the fleet caps (live/caps.py), History's session rows (studio/live_agents_api.py) and a goal run's lead calls.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

_cache: dict = {}  # path -> ((size, mtime), result)
_lock = threading.Lock()


def _head(path, key: str, kind=(int, float)):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for _i, line in zip(range(5), f):
                got = (json.loads(line) if line.strip() else {}).get(key)
                if isinstance(got, kind) and not isinstance(got, bool):
                    return got
    except (OSError, ValueError, AttributeError):
        pass
    return None


def started(path) -> Optional[float]:
    got = _head(path, "ts")
    return float(got) if got is not None else None


def _read(path: Path) -> dict:
    usd, unknown, calls = 0.0, [], 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"usage"' not in line:
                continue
            try:
                node = json.loads(line)
            except ValueError:
                continue
            if not isinstance(node, dict) or node.get("type") != "usage":
                continue
            calls += 1
            cost = node.get("cost_usd")
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                usd += float(cost)
            elif node.get("status") not in (None, "ok"):
                continue  # 3.4.1.0 R5: a failed call (429, 5xx, ...) spent nothing; its line is not an unpriced one
            elif node.get("model") and str(node["model"]) not in unknown:
                unknown.append(str(node["model"]))
    return {"usd": round(usd, 6), "complete": not unknown, "unknown": unknown, "started": started(path), "calls": calls,
            "cwd": _head(path, "cwd", str)}  # 3.4.1.0 R5: the folder it ran in (its project, for the per-project cap)


def of_record(path) -> Optional[dict]:
    """The session's spend from its record, or None when it cannot be read."""
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return None
    key = (st.st_size, st.st_mtime)
    with _lock:
        hit = _cache.get(str(p))
    if hit is not None and hit[0] == key:
        return hit[1]
    try:
        got = _read(p)
    except OSError:
        return None
    with _lock:
        if len(_cache) > 4000:
            _cache.clear()
        _cache[str(p)] = (key, got)
    return got


def _midnight(now: Optional[float] = None) -> float:
    t = time.localtime(now if now is not None else time.time())
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1))


def today(state_dir=None, now: Optional[float] = None) -> dict:
    """Every session of this harness started today, finished or open: the priced sum, how many, and what is unknown."""
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    root = Path(state_dir) / "sessions"
    out = {"usd": 0.0, "sessions": 0, "complete": True, "unknown": [], "projects": {}}
    if not root.is_dir():
        return out
    start = _midnight(now)
    end = _midnight(start + 86400 + 7200)  # the next midnight, a DST day too
    for p in root.glob("*/*.jsonl"):
        try:
            if p.stat().st_mtime < start:  # untouched since before today: it did not start today
                continue
        except OSError:
            continue
        got = of_record(p)
        when = (got or {}).get("started")
        if got is None or not isinstance(when, (int, float)) or not start <= when < end:
            continue
        out["usd"] += got["usd"]
        out["sessions"] += 1
        row = out["projects"].setdefault(project_of(got.get("cwd")), {"usd": 0.0, "sessions": 0})
        row["usd"], row["sessions"] = round(row["usd"] + got["usd"], 6), row["sessions"] + 1
        out["unknown"] += [m for m in got["unknown"] if m not in out["unknown"]]
    out["usd"] = round(out["usd"], 6)
    out["complete"] = not out["unknown"]
    return out


def project_of(cwd) -> str:
    """The project key of a folder, as a live session's row names it (its git repo, else the folder): live/caps.py's
    `project_key` over remote/session_identity.project, so a finished session counts toward the same project's cap."""
    if not cwd:
        return "no project"
    from halo_harness.live.history_owner import _root_of  # 3.4.1.1 (66): a goal run's worker counts to its run's repo
    cwd = _root_of(str(cwd))
    from halo_harness.live.caps import project_key
    try:
        from halo_harness.remote.session_identity import project
        return project_key({"project": project(cwd)})
    except Exception:
        return project_key({"cwd": cwd})
