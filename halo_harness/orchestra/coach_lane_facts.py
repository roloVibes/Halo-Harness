"""halo_harness.orchestra.coach_lane_facts -- what the coach reads out of an
Orchestra run folder, one row per lane (orchestra/coach.py; the rules are
coach_orchestra_rules.py; 3.1.0.0 R2 renamed it from coach_facts.py and
moved the model catalog and its prices to coach_prices.py).

`lane_facts(run_dir, ...)` is one row per lane:

    {lane, job, title, bio, model, state, pieces_returned, cost_usd, duration_s,
     written: n units, lines: n lines written, returned: {gate: n, merge: n},
     denied: [{tool_name, reason}], refused: [{key, by_lane, other, ts}],
     waited_s: {other lane: seconds}, reply, after, claims, holder, ended}

The lane's bio and model are the lane file's (3.0.9.0 R3 records them),
else its job's in split.json, else the bio's `models.preference`, else the
model of the goal's worker role. `waited_s` adds up, per other lane, the
time from each refused claim (a `claim` event with op `refused`) to the
lane's next claim of that key (or its end).
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.orchestra import jsonl


def _bio_model(bio: str, cwd, state_dir) -> str:
    if not bio:
        return ""
    try:
        from halo_harness.agents_yaml import resolve_agent_bio
        data = resolve_agent_bio(bio, cwd=cwd, state_dir=state_dir) or {}
        return str((data.get("models") or {}).get("preference") or "")
    except Exception:
        return ""


def _role_model(role: str) -> str:
    try:
        from halo_harness.orchestra.adapters import role_model
        return str(role_model(role) or "")
    except Exception:
        return ""


def holders(events: list, rows: list) -> dict:
    """{holder: lane}: from each lane's `joined` lines, the lane files and the `lane:<n>` placeholders."""
    out = {}
    for e in events:
        data = e.get("data") or {}
        if e.get("kind") == "state" and data.get("holder") and e.get("lane") is not None:
            out[str(data["holder"])] = int(e["lane"])
    for row in rows:
        if row.get("holder"):
            out.setdefault(str(row["holder"]), int(row["lane"]))
        out[f"lane:{int(row['lane'])}"] = int(row["lane"])
    return out


def _refusals(events: list, who: dict) -> list:
    out = []
    for i, e in enumerate(events):
        data = e.get("data") or {}
        if e.get("kind") != "claim" or data.get("op") != "refused":
            continue
        lane = data.get("lane_n") if isinstance(data.get("lane_n"), int) else who.get(str(data.get("holder") or ""))
        if lane is None:
            continue
        got = next((float(x.get("ts") or 0) for x in events[i + 1:] if x.get("kind") == "claim"
                    and (x.get("data") or {}).get("op") in ("claim", "reassign")
                    and (x.get("data") or {}).get("key") == data.get("key")
                    and who.get(str((x.get("data") or {}).get("holder") or "")) == lane), None)
        out.append({"lane": int(lane), "key": data.get("key"), "by_lane": who.get(str(data.get("by") or "")),
                    "by": data.get("by"), "other": data.get("other"), "ts": float(e.get("ts") or 0), "until": got})
    return out


def _returned(history: list) -> dict:
    out = {"gate": 0, "merge": 0}
    for h in history or []:
        text = str(h.get("text") or "")
        if h.get("state") == "waiting" and text.startswith("the gate sent the piece back"):
            out["gate"] += 1
        elif h.get("state") == "waiting" and text.startswith("piece sent back"):
            out["merge"] += 1
    return out


def lane_facts(run_dir, goal: dict, rows: list, events: list, *, cwd=None, state_dir=None) -> list:
    run_dir = Path(run_dir)
    split = jsonl.read_json(run_dir / "split.json", {}) or {}
    jobs = {str(j.get("id")): j for j in split.get("jobs") or [] if isinstance(j, dict)}
    who = holders(events, rows)
    refused = _refusals(events, who)
    out = []
    for row in rows:
        n = int(row.get("lane") or 0)
        job = jobs.get(str(row.get("job"))) or {}
        bio = str(row.get("bio") or job.get("bio") or "")
        model = str(row.get("model") or job.get("model") or _bio_model(bio, cwd, state_dir)
                    or _role_model(str(goal.get("worker") or "subagent")))
        started, ended = row.get("started"), row.get("ended")
        duration = float(ended) - float(started) if isinstance(started, (int, float)) and isinstance(ended, (int, float)) else None
        mine = [r for r in refused if r["lane"] == n]
        waited: dict = {}
        for r in mine:
            if r["by_lane"] is None or r["by_lane"] == n:
                continue
            stop = r["until"] or (float(ended) if isinstance(ended, (int, float)) else r["ts"])
            waited[r["by_lane"]] = round(waited.get(r["by_lane"], 0.0) + max(0.0, stop - r["ts"]), 3)
        written = row.get("written") or {}
        out.append({"lane": n, "job": str(row.get("job") or f"job-{n}"), "title": str(row.get("title") or ""),
                    "bio": bio, "model": model, "state": str(row.get("state") or ""),
                    "pieces_returned": int(row.get("pieces_returned") or 0),
                    "cost_usd": float(row.get("cost_usd") or 0.0), "duration_s": duration,
                    "written": len(written), "lines": sum(len(str(t).splitlines()) for t in written.values()),
                    "returned": _returned(row.get("history") or []),
                    "denied": [d for d in row.get("denied") or [] if isinstance(d, dict)],
                    "refused": mine, "waited_s": waited, "reply": str(row.get("reply") or ""),
                    "after": list(row.get("after") or []), "claims": list(row.get("claims") or []),
                    "holder": str(row.get("holder") or ""), "ended": ended})
    return out
