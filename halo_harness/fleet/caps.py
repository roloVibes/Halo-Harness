"""halo_harness.fleet.caps -- spend today and the caps on it (Halo 3.0.5.0
"Fleet" round R4, D6 budget guard). Pure: everything is computed from the
hub's view (`GET /api/fleet`); studio/fleet_watch.py acts on `reached`.

    fleet.caps.per_harness_usd_per_day   one harness's sessions started today
    fleet.caps.per_project_usd_per_day   every session on one repo started today, any harness
    fleet.caps.fleet_usd_per_day         every session the hub sees started today

A session counts toward today when it started today (local time), with the
cost its control socket reports, the same rule as a harness's `cost_today`.
A cap reached pauses the live sessions in its scope (the `pause` command,
reason "cap": every agent holds at its next tool boundary, so nothing new is
spawned) and raises an attention row; lifting it (the row's `a`) resumes
them and holds the cap off for the rest of the day.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

KEYS = ("per_harness_usd_per_day", "per_project_usd_per_day", "fleet_usd_per_day")
SCOPE = {"per_harness_usd_per_day": "harness", "per_project_usd_per_day": "project", "fleet_usd_per_day": "fleet"}


def _num(v) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def config(home=None) -> dict:
    from halo_harness.fleet import identity
    raw = identity.config_value("fleet.caps", {}, Path(home) if home is not None else None)
    raw = raw if isinstance(raw, dict) else {}
    return {k: _num(raw.get(k)) for k in KEYS}


def project_key(row: dict) -> str:
    p = row.get("project") if isinstance(row.get("project"), dict) else {}
    name = p.get("repo") or p.get("root") or row.get("cwd") or ""
    return str(name).replace("\\", "/").rstrip("/").split("/")[-1] or "no project"


def started_today(row: dict, now: Optional[float] = None) -> bool:
    st = row.get("started")
    day = time.strftime("%Y-%m-%d", time.localtime(now))
    return isinstance(st, (int, float)) and time.strftime("%Y-%m-%d", time.localtime(st)) == day


def spend(view: dict, now: Optional[float] = None) -> dict:
    sessions, per_h, per_p = [], {}, {}
    for h in view.get("harnesses") or []:
        hid, hname = str(h.get("id") or ""), str(h.get("name") or h.get("id") or "")[:64]
        per_h[hid] = {"id": hid, "name": hname, "local": bool(h.get("local")), "usd": 0.0, "sessions": 0}
        for s in h.get("sessions") or []:
            usd = float(s.get("cost_usd") or 0) if isinstance(s.get("cost_usd"), (int, float)) else 0.0
            today = started_today(s, now)
            pk = project_key(s)
            sessions.append({"harness": hid, "harness_name": hname, "session_id": s.get("session_id"),
                             "title": s.get("title") or "", "project": pk, "usd": round(usd, 6),
                             "started": s.get("started"), "today": today})
            if not today:
                continue
            per_h[hid]["usd"] += usd
            per_h[hid]["sessions"] += 1
            p = per_p.setdefault(pk, {"key": pk, "label": pk, "usd": 0.0, "sessions": 0, "harnesses": []})
            p["usd"] += usd
            p["sessions"] += 1
            if hname not in p["harnesses"]:
                p["harnesses"].append(hname)
    for d in list(per_h.values()) + list(per_p.values()):
        d["usd"] = round(d["usd"], 6)
    total = round(sum(h["usd"] for h in per_h.values()), 6)
    return {"fleet": total, "harnesses": list(per_h.values()),
            "projects": sorted(per_p.values(), key=lambda p: -p["usd"]), "sessions": sessions}


def reached(view: dict, caps: dict, now: Optional[float] = None) -> list:
    """`[{scope, key, label, spent, cap, sessions: [[harness, session_id], ...]}]` for every cap at or over."""
    sp = spend(view, now)
    live = [(str(h.get("id")), s) for h in view.get("harnesses") or [] for s in h.get("sessions") or []]
    out = []
    cap = caps.get("per_harness_usd_per_day")
    for h in sp["harnesses"] if cap else []:
        if h["usd"] >= cap:
            out.append({"scope": "harness", "key": h["id"], "label": h["name"], "spent": h["usd"], "cap": cap,
                        "sessions": [[hid, s.get("session_id")] for hid, s in live if hid == h["id"]]})
    cap = caps.get("per_project_usd_per_day")
    for p in sp["projects"] if cap else []:
        if p["usd"] >= cap:
            out.append({"scope": "project", "key": p["key"], "label": p["label"], "spent": p["usd"], "cap": cap,
                        "sessions": [[hid, s.get("session_id")] for hid, s in live if project_key(s) == p["key"]]})
    cap = caps.get("fleet_usd_per_day")
    if cap and sp["fleet"] >= cap:
        out.append({"scope": "fleet", "key": "fleet", "label": "the whole fleet", "spent": sp["fleet"], "cap": cap,
                    "sessions": [[hid, s.get("session_id")] for hid, s in live]})
    return out


def cap_id(scope: str, key: str) -> str:
    return f"{scope}:{key}"
