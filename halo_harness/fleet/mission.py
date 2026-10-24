"""halo_harness.fleet.mission -- a fleet mission: one goal, split into parts,
each part run on the harness best placed for it (Halo 3.0.6.0 "Fleet
Missions" round R7). The model of the mission document and its states;
mission_store.py keeps it on disk, mission_plan.py writes its plan,
mission_run.py runs it.

States (a mission only moves forward along these edges):

    drafted -> planned -> approved -> running -> merging -> done
                                  \\-> failed | stopped (from any state before done)

`planned -> planned` is a re-plan or an owner edit; `approved -> planned`
an edit after approval (it needs approving again). Part states:

    pending -> asked -> running -> done | failed | stopped | skipped;  done -> merged
    pending -> waiting -> running   (3.2.1.0 R3: held until its pack capability has a free slot, mission_hold.py)

Ids are short and readable: `m-<yyyymmdd>-<4 hex>`.

Config (docs/CONFIG.md): `fleet.shared_dir` (a mount every machine sees: the
missions live there and nothing is mirrored), `fleet.mission.prefer` (an
ordered list of harness names that break a tie), `fleet.mission.max_parallel`
(default: the number of harnesses) and `fleet.mission.max_file_mb` (default
25, the cap on one file sent over the fleet protocol).
"""

from __future__ import annotations

import re
import secrets
import time
from pathlib import Path
from typing import Optional

from halo_harness.work.states import words

STATES = ("drafted", "planned", "approved", "running", "merging", "done", "failed", "stopped")
FINAL = ("done", "failed", "stopped")
EDGES = {"drafted": ("planned", "failed", "stopped"),
         "planned": ("planned", "approved", "failed", "stopped"),
         "approved": ("planned", "running", "failed", "stopped"),
         "running": ("merging", "failed", "stopped"),
         "merging": ("done", "failed", "stopped"),
         "done": (), "failed": (), "stopped": ()}
PART_STATES = words("part")  # pending waiting asked running done failed stopped skipped merged (work/states.py)
PART_LIVE = ("asked", "running")
PART_OVER = ("done", "failed", "stopped", "skipped", "merged")
ID_RE = re.compile(r"^m-\d{8}-[0-9a-f]{4}$")
DEFAULT_MAX_FILE_MB = 25.0


class MissionError(Exception):
    """A request the mission cannot take in its state; `status` is the HTTP status the routes answer."""

    def __init__(self, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.status = status


def new_id(now: Optional[float] = None) -> str:
    return f"m-{time.strftime('%Y%m%d', time.localtime(time.time() if now is None else now))}-{secrets.token_hex(2)}"


def valid_id(mid) -> bool:
    return isinstance(mid, str) and bool(ID_RE.match(mid))


def can(state: str, to: str) -> bool:
    return to in EDGES.get(state, ())


def move(doc: dict, to: str, why: str = "", by: str = "") -> dict:
    """`doc` moved to state `to` (history kept); MissionError when that edge does not exist."""
    cur = str(doc.get("state") or "drafted")
    if not can(cur, to):
        raise MissionError(f"mission {doc.get('id')} is {cur}; it cannot become {to}")
    now = time.time()
    doc["state"], doc["updated"] = to, now
    doc.setdefault("history", []).append({"ts": round(now, 3), "state": to, "why": why[:300], "by": by or None})
    if to in FINAL:
        doc["ended"] = now
    return doc


def new_doc(*, mid: str, goal: str, constraints: str = "", prefer=None, budget_usd=None, test: str = "",
            hub: Optional[dict] = None, repo: Optional[dict] = None, shared: bool = False, by: str = "") -> dict:
    now = time.time()
    return {"v": 1, "id": mid, "goal": goal, "constraints": constraints, "prefer": list(prefer or []),
            "budget_usd": budget_usd, "test": test, "state": "drafted", "created": now, "updated": now, "ended": None,
            "hub": dict(hub or {}), "repo": repo, "shared": bool(shared), "by": by or None, "plan_cost_usd": 0.0,
            "parts": {}, "history": [{"ts": round(now, 3), "state": "drafted", "why": "drafted", "by": by or None}],
            "decisions": [], "stop_reason": None, "merge": None, "approved_by": None}


def new_part_state(part: dict) -> dict:
    """A part's first state; its shape is the part adapter's (work/adapters/part.py, 3.1.2.0 R1)."""
    from halo_harness.work.adapters.part import new_state
    return new_state(part)


def decide(doc: dict, what: str, by: str = "") -> None:
    """A decision someone made (approve, reassign, drop, stop), for the report."""
    doc.setdefault("decisions", []).append({"ts": round(time.time(), 3), "what": what[:300], "by": by or None})


def summary(doc: dict) -> dict:
    """One row of `GET /api/fleet/missions`."""
    parts = doc.get("parts") or {}
    by_state: dict = {}
    for p in parts.values():
        by_state[p.get("state") or "pending"] = by_state.get(p.get("state") or "pending", 0) + 1
    harnesses = sorted({str(p.get("harness_name") or p.get("harness")) for p in parts.values() if p.get("harness")})
    return {"id": doc.get("id"), "goal": doc.get("goal"), "state": doc.get("state"), "created": doc.get("created"),
            "updated": doc.get("updated"), "ended": doc.get("ended"), "parts": len(parts), "part_states": by_state,
            "harnesses": harnesses, "cost_usd": cost(doc), "budget_usd": doc.get("budget_usd"),
            "stop_reason": doc.get("stop_reason"), "shared": bool(doc.get("shared"))}


def cost(doc: dict) -> float:
    return round(float(doc.get("plan_cost_usd") or 0.0)
                 + sum(float(p.get("cost_usd") or 0.0) for p in (doc.get("parts") or {}).values()), 6)


# ---- config ------------------------------------------------------------------------------

def _cfg(key: str, default, home=None):
    from halo_harness.fleet.identity import config_value
    return config_value(key, default, Path(home) if home is not None else None)


def names(value) -> list:
    """A list of names from a list or a comma-separated string."""
    if isinstance(value, str):
        value = value.split(",")
    return [str(v).strip() for v in (value or []) if str(v).strip()] if isinstance(value, (list, tuple)) else []


def prefer(home=None) -> list:
    return names(_cfg("fleet.mission.prefer", [], home))


def max_parallel(home=None, harnesses: int = 1) -> int:
    raw = _cfg("fleet.mission.max_parallel", None, home)
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 0
    return n if n > 0 else max(1, int(harnesses))


def max_file_bytes(home=None) -> int:
    raw = _cfg("fleet.mission.max_file_mb", DEFAULT_MAX_FILE_MB, home)
    try:
        mb = float(raw)
    except (TypeError, ValueError):
        mb = DEFAULT_MAX_FILE_MB
    return int(max(0.01, mb) * 1024 * 1024)


def shared_dir(home=None) -> Optional[Path]:
    """`fleet.shared_dir` when it names a folder that exists here, else None."""
    raw = str(_cfg("fleet.shared_dir", "", home) or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_dir() else None
