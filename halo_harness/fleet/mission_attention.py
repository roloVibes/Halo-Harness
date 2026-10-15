"""halo_harness.fleet.mission_attention -- a mission's rows in the Fleet
attention queue and their answers (Halo 3.0.6.0 "Fleet Missions" round R7;
fleet/attention.py builds the queue, studio/fleet_answer.py routes the keys).

    mission_plan   a planned mission waits for its owner: a approve and run | r edit (text: "part 2 to kali",
                   "drop 3") | s drop the mission (it ends `stopped`) | o open
    mission_claim  a part's worker tried to edit outside its claims and was refused: a set aside | o open
    mission_ask    (on the member) a hub asks to run a mission part here: the `fleet-ask:mission-` card,
                   a allow | r deny, answered like any fleet_ask (attention.session_rows)

`rows(home, local, seen, now)` reads the mission folders: planned missions,
and the `claim_refused` lines of missions that are not over or ended within
a day.
"""

from __future__ import annotations

import re

from halo_harness.fleet import mission as M
from halo_harness.fleet import mission_store as S

WITHIN_S = 86400.0
_EDIT = re.compile(r"^\s*(?:part\s+)?(\d{1,3})\s*(?:to|->|=>|on)\s*(\S.*?)\s*$", re.I)
_DROP = re.compile(r"^\s*drop\s+(?:part\s+)?(\d{1,3})\s*$", re.I)


def rows(home, local: dict, seen: dict, now: float) -> list:
    from halo_harness.fleet.attention import _row
    out = []
    for doc in S.all_docs(home):
        mid = doc["id"]
        if doc.get("state") == "planned":
            parts = doc.get("parts") or {}
            names = sorted({str(p.get("harness_name") or p.get("harness")) for p in parts.values() if p.get("harness")})
            out.append(_row("mission_plan", mid, local, None, "", f"Mission {mid} waits for your approval",
                            f"{doc.get('goal')} ({len(parts)} parts on {', '.join(names) or 'no harness'})"[:240],
                            seen, now, mission=mid))
        if doc.get("state") in M.FINAL and now - float(doc.get("ended") or 0) > WITHIN_S:
            continue
        try:
            refused = S.read_log(home, mid, ("claim_refused",))
        except (OSError, M.MissionError):
            refused = []
        for r in refused:
            rid = f"{mid}:{r.get('part')}:{r.get('file')}:{r.get('ts')}"
            out.append(_row("mission_claim", rid, local, None, "", f"Mission {mid} part {r.get('part')} was refused an edit "
                            f"outside its claims", f"{r.get('tool')} {r.get('file')}: {r.get('reason') or ''}"[:240],
                            seen, now, mission=mid, part=r.get("part"), file=r.get("file")))
    return out


def edit_from_text(text: str) -> dict:
    """`part 2 to kali` -> {part: 2, harness: kali}; `drop 3` -> {part: 3, drop: True}; {} when it is neither."""
    m = _DROP.match(text or "")
    if m:
        return {"part": m.group(1), "drop": True}
    m = _EDIT.match(text or "")
    return {"part": m.group(1), "harness": m.group(2)} if m else {}


def answer(req, row: dict, key: str, text: str):
    """`(status, body, label)` for a mission_plan row."""
    from halo_harness.studio.fleet_mission_api import _do
    mid, label = (row.get("target") or {}).get("mission"), row["keys"][key]
    if key == "a":
        status, got = _do(req, "run", id=mid)
        return status, got, label
    if key == "s":
        status, got = _do(req, "stop", id=mid, reason="dropped from the Fleet attention queue")
        return status, got, label
    edit = edit_from_text(text)
    if not edit:
        return 422, {"error": 'an edit is "part <n> to <harness>" or "drop <n>"'}, label
    status, got = _do(req, "edit", id=mid, **edit)
    return status, got, label


def open_target(row: dict) -> dict:
    t = row.get("target") or {}
    return {"section": "fleet", "panel": "fleet-mission", "mission": t.get("mission"), "part": t.get("part")}
