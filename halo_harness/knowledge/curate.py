"""halo_harness.knowledge.curate -- the owner keeps the store useful (Halo 3.3.16.2, "from a session's own review":
"the knowledge base is already getting noisy").

    select(kind=, project=, older_than_s=, cwd=, state_dir=)  the current entries that match: `kind` finding |
                                                              decision | gate (a gate's record, either kind);
                                                              `project` "." (the folder's), "all", or a name
    parse_age("7d")                                           seconds (m, h, d, w); KnowledgeError on a bad one
    prune(rows, state_dir=)                                   forget each; the ids removed
    gate_keep()                                               config `knowledge.gate_keep` (default 50)
    cap_passed_gates(project, state_dir=, keep=)              keep the newest `keep` passed-gate records of a
                                                              project, forget the rest (called when one is written)
"""

from __future__ import annotations

import re
import time
from typing import Optional

from halo_harness.knowledge import rank as R

GATE_KEEP_KEY = "knowledge.gate_keep"
DEFAULT_GATE_KEEP = 50
KINDS = ("finding", "decision", "gate")
_AGE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([mhdw])\s*$", re.IGNORECASE)
_UNIT = {"m": 60, "h": 3600, "d": 86400, "w": 7 * 86400}


def parse_age(text: str) -> float:
    from halo_harness.knowledge.store import KnowledgeError
    m = _AGE.match(str(text or ""))
    if not m:
        raise KnowledgeError(f"--older-than takes a number and a unit (30m, 12h, 7d, 2w), got {text!r}")
    return float(m.group(1)) * _UNIT[m.group(2).lower()]


def kind_matches(e: dict, kind: Optional[str]) -> bool:
    if not kind:
        return True
    return R.is_gate(e) if kind == "gate" else e.get("kind") == kind


def project_matches(e: dict, project: Optional[str], here: str) -> bool:
    if project in (None, "", "all"):
        return True
    return R.project_of(e) == (here if project == "." else project)


def select(*, kind: Optional[str] = None, project: Optional[str] = None, older_than_s: Optional[float] = None,
           cwd=None, state_dir=None, now: Optional[float] = None, everything: bool = False) -> list:
    from halo_harness.knowledge.store import current, entries
    now = time.time() if now is None else now
    here = R.project_here(cwd) if project == "." else ""
    rows = entries(state_dir) if everything else current(state_dir)
    out = []
    for e in rows:
        if not kind_matches(e, kind) or not project_matches(e, project, here):
            continue
        if older_than_s is not None:
            age = R.age_s(e, now)
            if age is None or age < older_than_s:
                continue
        out.append(e)
    return out


def prune(rows: list, *, state_dir=None) -> list:
    from halo_harness.knowledge.store import forget
    return [e["id"] for e in rows if forget(e["id"], state_dir)]


def gate_keep() -> int:
    try:
        from halo_harness.theme import get_config_value
        value = int(get_config_value(GATE_KEEP_KEY, DEFAULT_GATE_KEEP))
    except Exception:
        return DEFAULT_GATE_KEEP
    return max(0, value)


def cap_passed_gates(project: str, *, state_dir=None, keep: Optional[int] = None) -> list:
    """Forget a project's passed-gate records past the newest `keep` (config `knowledge.gate_keep`); the ids
    forgotten. 0 keeps none; a negative or unreadable setting keeps the default."""
    from halo_harness.knowledge.store import forget, current
    keep = gate_keep() if keep is None else max(0, int(keep))
    mine = [e for e in current(state_dir, kind="finding") if R.is_routine_gate(e) and R.project_of(e) == project]
    gone = []
    for e in mine[keep:]:  # current() is newest first
        if forget(e["id"], state_dir):
            gone.append(e["id"])
    return gone


def row_line(e: dict) -> str:
    """`halo knowledge list`'s line: id, kind, who, day, confidence, project, title."""
    project = R.project_of(e) or "-"
    gone = f"  (superseded by {e['superseded_by']})" if e.get("superseded_by") else ""
    sample = "  (sample)" if R.SAMPLE_TAG in (e.get("tags") or []) else ""
    return (f"  {e['id']}  {e['kind']:<8}  {e['by'][:18]:<18}  {e['when'][:10]}  {(e.get('confidence') or '-'):<7}  "
            f"{project[:16]:<16}  {e['title']}{sample}{gone}")
