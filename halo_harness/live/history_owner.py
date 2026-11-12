"""halo_harness.live.history_owner -- which past sessions are a goal run's or a mission's own (Halo 3.4.0.1 "Found
live", defect 22: History listed a run's lead and worker sessions -- "You are the lead orchestrator ...", "You are
worker 1 of an Orchestra run ..." -- as rows of their own beside the run's row: 24 rows for 2 runs, 2 missions and
3 sessions).

    owners(cwd, state_dir, sessions=()) -> {session_id: {"kind": "run" | "mission", "id": <run or mission id>}}

Read from the records that already name them: a goal run's split.json (`lead_sessions`, kept for a failed split too),
split.lead.json and lanes/*.json (`session_ids`) in this repo's runs; a mission's plan.json (`lead_sessions`) and
mission.json (each part's `session_id`) under `<state>/fleet/missions/`. History folds those rows under their owner.
3.4.1.0 R5 (live re-check defect 35): "this repo" was only Studio's folder, so a goal run made in another repo had no
row while its lead and worker sessions did. Each listed session's own record names its folder (its meta line's
`cwd`): the runs of that repo are read too (a worker's folder is `<repo>/.halo/orchestra/<run>/wt/...`), whatever
Studio's folder is; and mission.json's `lead_sessions` (a plan that failed its check) counts like plan.json's.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_SID = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
MAX_ROOTS = 24


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _ids(values) -> list:
    return [str(v) for v in values or [] if isinstance(v, str) and v]


def _root_of(cwd: str) -> str:
    """The repo a session ran in: the part before `/.halo/orchestra/` for a goal run's worktree, else its folder."""
    posix = str(cwd).replace("\\", "/")
    cut = posix.find("/.halo/orchestra/")
    return str(cwd)[:cut] if cut > 0 else str(cwd)


def session_roots(state_dir, sessions) -> list:
    """The folders the listed sessions ran in (their records' meta `cwd`), as repo roots, at most MAX_ROOTS."""
    roots: list = []
    base = Path(state_dir) / "sessions" if state_dir is not None else None
    for sid in [str(s) for s in sessions or () if _SID.match(str(s or ""))]:
        for path in base.glob(f"*/{sid}.jsonl") if base is not None and base.is_dir() else []:
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    for _i, line in zip(range(5), f):
                        node = json.loads(line) if line.strip() else {}
                        if isinstance(node, dict) and node.get("type") == "meta" and isinstance(node.get("cwd"), str):
                            root = _root_of(node["cwd"])
                            roots += [root] if root not in roots else []
                            break
            except (OSError, ValueError):
                continue
        if len(roots) >= MAX_ROOTS:
            break
    return roots


def owners(cwd=None, state_dir=None, sessions=()) -> dict:
    out: dict = {}
    runs: list = []
    try:
        from halo_harness.orchestra.goal import list_runs
        for root in list(dict.fromkeys(([str(cwd)] if cwd is not None else []) + session_roots(state_dir, sessions))):
            runs += [r for r in list_runs(Path(root)) if r not in runs]
    except Exception:
        pass
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
        doc = _read(folder / "mission.json")
        for sid in _ids(_read(folder / "plan.json").get("lead_sessions")) + _ids(doc.get("lead_sessions")):
            out.setdefault(sid, own)
        parts = doc.get("parts")
        for p in (parts.values() if isinstance(parts, dict) else []):
            if isinstance(p, dict) and isinstance(p.get("session_id"), str) and p["session_id"]:
                out.setdefault(p["session_id"], own)
    return out
