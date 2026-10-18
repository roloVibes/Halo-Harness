"""halo_harness.orchestra.coach_facts -- what the coach reads out of an
Orchestra run folder (orchestra/coach.py; the rules are coach_rules.py).

`lane_facts(run_dir, ...)` is one row per lane:

    {lane, job, title, bio, model, state, pieces_returned, cost_usd, duration_s,
     written: n units, lines: n lines written, returned: {gate: n, merge: n},
     denied: [{tool_name, reason}], refused: [{key, by_lane, other, ts}],
     waited_s: {other lane: seconds}, reply, after, claims, holder, ended}

The lane's bio and model are the lane file's (3.0.9.0 R3 records them),
else its job's in split.json, else the bio's `models.preference`, else the
model of the goal's worker role. `waited_s` adds up, per other lane, the
time from each refused claim (a `claim` event with op `refused`) to the
lane's next claim of that key (or its end). `catalog(state_dir)` is the
model catalog on disk (prices, best-for kinds), [] when it cannot be read.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl

TOP_PRICE = 3.0     # $/M input tokens: the top tier in capabilities._tier
CHEAP_PRICE = 0.5   # under it: the budget tier (free and local models count as cheap)


def _per_m(v) -> Optional[float]:
    try:
        return None if isinstance(v, bool) or v is None else float(v) * 1_000_000
    except (TypeError, ValueError):
        return None


def _openrouter_rows(base: Path) -> list:
    """models.json read as catalog rows whether or not OpenRouter is enabled here (a run's models still have prices)."""
    from halo_harness.providers.databricks import load_models_json
    rows = []
    for name, entry in sorted((load_models_json(base) or {}).items()):
        entry = entry if isinstance(entry, dict) else {}
        price = entry.get("price_in_per_m")
        params = entry.get("supported_parameters")
        rows.append({"ref": f"or:{name}", "provider": "openrouter",
                     "price_in_per_m": float(price) if isinstance(price, (int, float)) else
                     _per_m((entry.get("pricing") or {}).get("prompt")),
                     "modalities_in": list(entry.get("input_modalities") or []) or None,
                     "tools": ("tools" in params) if params else None})
    return rows


def catalog(state_dir=None) -> list:
    rows: list = []
    try:
        import os
        from halo_harness.providers.config import default_state_dir, load_routes
        from halo_harness.providers.model_enumeration import build_model_rows
        base = Path(state_dir or default_state_dir())
        try:
            routes = load_routes(base / "routes.json" if base.exists() else None)
            rows = [r for r in build_model_rows(base, env=dict(os.environ), routes=routes)
                    if r.get("ref") and r.get("provider") != "alias"]
        except Exception:
            rows = []
        seen = {r["ref"] for r in rows}
        rows += [r for r in _openrouter_rows(base) if r["ref"] not in seen]
    except Exception:
        pass
    return rows


def price_of(rows: list, ref: str) -> Optional[float]:
    for r in rows:
        if r.get("ref") == ref:
            p = r.get("price_in_per_m")
            if r.get("provider") in ("ollama", "huggingface"):
                return 0.0
            return float(p) if isinstance(p, (int, float)) and p >= 0 else None
    return None


def best_for(rows: list, ref: str) -> list:
    from halo_harness.capabilities import KINDS, score
    row = next((r for r in rows if r.get("ref") == ref), None)
    if row is None:
        return []
    out = []
    for kind in KINDS:
        try:
            if score(row, kind)[0] > 0:
                out.append(kind)
        except Exception:
            continue
    return out


def price_words(rows: list, ref: str) -> str:
    p = price_of(rows, ref)
    return "price unknown" if p is None else ("free or local" if p <= 0 else f"${p:.2f}/M in")


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
