"""halo_harness.live.replay_facts -- a run's figures, read from its own record (Halo 3.4.1.0 R2 "Time": compare).

A replay (live/replay_file.py) carries `facts`: what only the record knows -- the cost as the transcripts priced it
(each call once: a sub-agent's rolled-up total is skipped when its own transcript is read), the models nothing priced,
the tokens, each model's cost, the retries, the failed calls, the steers. `figures` turns a replay (a session's, a goal
run's, a saved file's, or a window of one) into the figures Compare's rows read and the report card will. Never a live
counter; nothing here calls a model.

    session_facts(path) -> facts           from a session's transcripts on disk (main and every sub-agent); `unknown_at`
                                           [[t, model]] is each unpriced call, so a window knows whether its cost is whole
    figures(payload, window=None) -> {how, ok, wall_s, cost_usd, cost_known, cost_unknown, tokens, models, agents,
                                      asks, failures, retries, window}
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

TOKEN_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
OK_STATUS = (None, "ok")


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def session_facts(path) -> dict:
    """The record's figures for the session at `path`: one walk over main's transcript and each sub-agent's."""
    from halo_harness.live import history
    path = Path(path)
    kids: list = []
    history._children(path.parent / path.stem, history.MAIN, kids)
    read_too = {str(k[0]) for k in kids}
    logs = [(path, None)] + [(k[3], k[2].get("model")) for k in kids]
    cost, unknown, unknown_at, model_cost = 0.0, [], [], {}
    tin = tout = 0
    seen_tokens, retries, failed, steers = False, 0, 0, []
    for log, model in logs:
        current = model
        for n in history.read_nodes(log):
            kind = n.get("type")
            if kind == "meta" and n.get("model") and log == path:
                current = n["model"]
            if kind == "user" and n.get("kind") == "steer" and log == path and _num(n.get("ts")) is not None:
                steers.append(float(n["ts"]))
            if kind != "usage" or str(n.get("agent_id") or "") in read_too:
                continue
            ref = str(n.get("model") or current or "?")
            usage = n.get("usage") if isinstance(n.get("usage"), dict) else {}
            if any(isinstance(usage.get(k), (int, float)) for k in TOKEN_KEYS + ("output_tokens",)):
                seen_tokens = True
                tin += int(sum(usage.get(k) or 0 for k in TOKEN_KEYS))
                tout += int(usage.get("output_tokens") or 0)
            retries += int(n.get("retries") or 0)
            if n.get("status") not in OK_STATUS:
                failed += 1
                continue
            usd = None if n.get("estimate") else _num(n.get("cost_usd"))
            if usd is None:
                if not n.get("estimate"):
                    unknown += [] if ref in unknown else [ref]
                    unknown_at.append([_num(n.get("ts")), ref])
                continue
            cost += usd
            model_cost[ref] = round(model_cost.get(ref, 0.0) + usd, 6)
    return {"cost_usd": round(cost, 6), "cost_unknown": unknown, "unknown_at": unknown_at, "tokens": {"in": tin, "out": tout} if seen_tokens else None,
            "model_cost": model_cost, "retries": retries, "failed_calls": failed, "steers": sorted(steers)}


def _at(points: list, t: float, key: str = "usd") -> float:
    hit = 0.0
    for p in points or []:
        if not isinstance(p.get("t"), (int, float)) or p["t"] > t + 1e-6:
            break
        hit = float(p.get(key) or 0.0)
    return hit


def _overlap(a0, a1, w0, w1) -> float:
    if a0 is None:
        return 0.0
    return max(0.0, min(a1 if a1 is not None else w1, w1) - max(a0, w0))


def _ended_how(p: dict, facts: dict, t1: float, window: bool) -> "tuple[str, Optional[bool]]":
    top = next((a for a in p.get("agents") or [] if not a.get("parent")), {}) or {}
    if window:
        live = [a for a in p.get("agents") or [] if (_num(a.get("since")) or 0) <= t1 and (_num(a.get("ended")) is None or a["ended"] > t1)]
        from halo_harness.live.compare_text import secs
        at = secs(t1 - (_num(p.get("started")) or t1))
        return (f"{len(live)} agent{'s' if len(live) != 1 else ''} at work at {at}" if live else f"nothing at work at {at}"), None
    if facts.get("how"):
        return str(facts["how"]), facts.get("ok")
    state = str(top.get("state") or "")
    if state in ("running", "waiting", "paused", "queued"):
        return "still running", None
    fails = [a for a in p.get("agents") or [] if a.get("state") == "failed" and a.get("parent")]
    if state == "failed":
        return "failed", False
    return ("finished" + (f", {len(fails)} sub-agent{'s' if len(fails) != 1 else ''} failed" if fails else "")), True


def figures(p: dict, window: Optional["tuple[float, float]"] = None) -> dict:
    """The figures of replay `p`, whole or over `window` (epoch seconds, clipped to the run)."""
    facts = p.get("facts") if isinstance(p.get("facts"), dict) else {}
    s0, s1 = _num(p.get("started")), _num(p.get("ended"))
    t0, t1 = (s0 or 0.0), (s1 if s1 is not None else (s0 or 0.0))
    if window:
        t0, t1 = max(t0, window[0]), min(t1, window[1])
        t1 = max(t0, t1)
    agents = [a for a in p.get("agents") or [] if isinstance(a, dict)]
    marks = [m for m in p.get("marks") or [] if isinstance(m.get("t"), (int, float)) and (not window or t0 - 1e-6 <= m["t"] <= t1 + 1e-6)]
    unknown = list(facts.get("cost_unknown") or [])
    if window:  # an unpriced call counts against the window it fell in (one with no time: against every window)
        unknown = sorted({str(m) for t, m in facts.get("unknown_at") or [] if t is None or t0 - 1e-6 <= t <= t1 + 1e-6})
        cost = round(_at(p.get("costs"), t1) - _at(p.get("costs"), t0), 6)
        per: dict = {}
        for a in agents:
            pts = [c for c in p.get("agent_costs") or [] if str(c.get("agent_id")) == str(a.get("agent_id"))]
            usd = _at(pts, t1) - _at(pts, t0) if pts else 0.0
            if usd:
                per[str(a.get("model") or "?")] = per.get(str(a.get("model") or "?"), 0.0) + usd
        model_cost = {k: round(v, 6) for k, v in per.items()}
    else:
        cost = _num(facts.get("cost_usd")) if facts else _num(p.get("cost_usd"))
        model_cost = dict(facts.get("model_cost") or {})
        if not facts:  # a file saved before 3.4.1.0 R2: each agent's cost, by its model
            for a in agents:
                if _num(a.get("cost_usd")):
                    model_cost[str(a.get("model") or "?")] = round(model_cost.get(str(a.get("model") or "?"), 0.0) + a["cost_usd"], 6)
    secs: dict = {}
    for a in agents:
        span = _overlap(_num(a.get("since")), _num(a.get("ended")), t0, t1)
        if span > 0:
            secs[str(a.get("model") or "?")] = secs.get(str(a.get("model") or "?"), 0.0) + span
    total_s, total_c = sum(secs.values()), sum(v for v in model_cost.values() if v)
    names = sorted(set(secs) | set(model_cost), key=lambda m: (-(model_cost.get(m) or 0), -(secs.get(m) or 0), m))
    share = lambda m: None if m in unknown else round((model_cost.get(m) or 0.0) / total_c, 4) if total_c else 0.0  # noqa: E731
    models = [{"model": m, "cost_usd": model_cost.get(m), "cost_share": share(m),
               "secs": round(secs.get(m, 0.0), 1), "time_share": round(secs.get(m, 0.0) / total_s, 4) if total_s else None}
              for m in names if m != "?" or secs.get(m) or model_cost.get(m)]
    how, ok = _ended_how(p, facts, t1, bool(window))
    spawned = [a for a in agents if a.get("parent") and (not window or t0 - 1e-6 <= (_num(a.get("since")) or t0) <= t1 + 1e-6)]
    fails = sum(1 for m in marks if m.get("kind") == "fail") + (0 if window else int(facts.get("failed_calls") or 0))
    tokens = None if window else facts.get("tokens")
    return {"how": how, "ok": ok, "wall_s": round(t1 - t0, 1) if s0 is not None else None,
            "cost_usd": cost, "cost_known": cost is not None and not unknown, "cost_unknown": unknown,
            "tokens": tokens if isinstance(tokens, dict) else None, "models": models, "agents": len(spawned),
            "asks": sum(1 for m in marks if m.get("kind") == "ask"), "failures": fails,
            "retries": None if window or "retries" not in facts else int(facts.get("retries") or 0),
            "window": [round(t0 - (s0 or 0), 1), round(t1 - (s0 or 0), 1)] if window else None}
