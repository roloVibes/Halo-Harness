"""halo_harness.live.history_owner -- which past sessions are a goal run's or a mission's own (Halo 3.4.0.1 "Found
live", defect 22: History listed a run's lead and worker sessions -- "You are the lead orchestrator ...", "You are
worker 1 of an Orchestra run ..." -- as rows of their own beside the run's row: 24 rows for 2 runs, 2 missions and
3 sessions).

    owners(cwd, state_dir) -> {session_id: {"kind": "run" | "mission", "id": <run or mission id>}}

Read from the records that already name them: a goal run's split.json (`lead_sessions`, kept for a failed split too),
split.lead.json and lanes/*.json (`session_ids`) in this repo's runs; a mission's plan.json (`lead_sessions`) and
mission.json (each part's `session_id`) under `<state>/fleet/missions/`. History folds those rows under their owner.
"""

from __future__ import annotations

import json
from pathlib import Path


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _ids(values) -> list:
    return [str(v) for v in values or [] if isinstance(v, str) and v]


def owners(cwd=None, state_dir=None) -> dict:
    out: dict = {}
    try:
        from halo_harness.orchestra.goal import list_runs
        runs = list_runs(Path(cwd)) if cwd is not None else []
    except Exception:
        runs = []
    for run in runs:
        own = {"kind": "run", "id": run.name}
        for name in ("split.json", "split.lead.json"):
            for sid in _ids(_read(run / name).get("lead_sessions")):
                out.setdefault(sid, own)
        for lane in sorted((run / "lanes").glob("*.json")) if (run / "lanes").is_dir() else []:
            for sid in _ids(_read(lane).get("session_ids")):
                out.setdefault(sid, own)
    root = Path(state_dir) / "fleet" / "missions" if state_dir is not None else None
    for folder in sorted(root.iterdir()) if root is not None and root.is_dir() else []:
        own = {"kind": "mission", "id": folder.name}
        for sid in _ids(_read(folder / "plan.json").get("lead_sessions")):
            out.setdefault(sid, own)
        parts = _read(folder / "mission.json").get("parts")
        for p in (parts.values() if isinstance(parts, dict) else []):
            if isinstance(p, dict) and isinstance(p.get("session_id"), str) and p["session_id"]:
                out.setdefault(p["session_id"], own)
    return out
