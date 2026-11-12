"""halo_harness.live.compare_text -- the words of a comparison (Halo 3.4.1.0 R2 "Time"): one run's cells (a value and
its text per row; the report card will read the same) and "what differed" in three plain lines, derived from the rows
(live/compare.py). A cost Halo cannot price is "unknown" (or the priced part with a "+"), never $0. No model call.
"""

from __future__ import annotations

from typing import Optional


def money(v: Optional[float]) -> str:
    if v is None:
        return "unknown"
    return f"${v:.2f}" if v >= 1 else f"${v:.4f}"  # Studio's cost() (orchestra/format.ts)


def secs(v: Optional[float]) -> str:
    if v is None:
        return "unknown"
    s = int(round(v))
    return f"{s // 3600} h {s % 3600 // 60:02d} min" if s >= 3600 else f"{s // 60} min {s % 60:02d} s" if s >= 60 else f"{s} s"


def kilo(n: int) -> str:
    return f"{n / 1_000_000:.1f}M" if n >= 1_000_000 else f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def bare(ref: str) -> str:
    return str(ref).split(":", 1)[-1].split("/")[-1] or str(ref)


def _pct(x: Optional[float]) -> str:
    return "?" if x is None else f"{round(x * 100)} %"


def cells(f: dict) -> dict:
    """{key: {value, text, unknown?}} for one run's figures (live/replay_facts.figures)."""
    cost, known = f.get("cost_usd"), bool(f.get("cost_known"))
    if cost is None or (not known and not cost):
        cost_text = "unknown" + (f" (no price for {', '.join(bare(m) for m in f.get('cost_unknown') or [])})" if f.get("cost_unknown") else "")
    else:
        cost_text = money(cost) + ("+" if not known else "")
    tok = f.get("tokens")
    tok_text = (f"{kilo(tok['in'] + tok['out'])} ({kilo(tok['in'])} in, {kilo(tok['out'])} out)" if tok
                else "not counted for part of a run" if f.get("window") else "unknown")
    models = f.get("models") or []
    m_text = "; ".join(f"{bare(m['model'])}: {_pct(m.get('cost_share'))} of cost, {_pct(m.get('time_share'))} of time" for m in models) or "none recorded"
    retries = f.get("retries")
    return {"ended": {"value": f.get("ok"), "text": str(f.get("how") or "unknown")},
            "wall": {"value": f.get("wall_s"), "text": secs(f.get("wall_s"))},
            "cost": {"value": cost if known else None, "text": cost_text, **({"unknown": True} if not known else {})},
            "tokens": {"value": tok["in"] + tok["out"] if tok else None, "text": tok_text, **({} if tok else {"unknown": True})},
            "models": {"value": [m["model"] for m in models], "text": m_text},
            "agents": {"value": f.get("agents"), "text": str(f.get("agents") or 0)},
            "asks": {"value": f.get("asks"), "text": str(f.get("asks") or 0)},
            "failures": {"value": f.get("failures"), "text": str(f.get("failures") or 0)},
            "retries": {"value": retries, "text": "unknown" if retries is None else str(retries), **({"unknown": True} if retries is None else {})}}


def _rel(a: float, b: float) -> float:
    hi = max(abs(a), abs(b))
    return abs(a - b) / hi if hi else 0.0


def _count(n: int, one: str) -> str:
    return "none" if not n else f"{n} {one}{'' if n == 1 else 's'}"


def differed(rows: list, fa: dict, fb: dict) -> list:
    """Three plain lines: the biggest differences first, then what was the same."""
    by = {r["key"]: r for r in rows}
    found: list = []  # (weight, line)
    e = by["ended"]
    if e["better"] in ("a", "b"):
        found.append((100, f"A {e['a']['text']}; B {e['b']['text']}."))
    c = by["cost"]
    if c["better"] in ("a", "b"):
        lo, hi = sorted([c["a"]["value"], c["b"]["value"]])
        who = c["better"].upper()
        found.append((40 + 50 * _rel(lo, hi), f"{who} cost {round(100 * _rel(lo, hi))} % less ({money(lo)} against {money(hi)})."))
    elif c["word"] == "unknown":
        side = "A" if c["a"].get("unknown") else "B"
        found.append((30, f"{side}'s cost is not all known ({c['a' if side == 'A' else 'b']['text']}), so the costs are not compared."))
    w = by["wall"]
    if w["better"] in ("a", "b"):
        va, vb = w["a"]["value"], w["b"]["value"]
        slow, fast = ("A", "B") if va > vb else ("B", "A")
        found.append((35 + 50 * _rel(va, vb), f"{slow} took {secs(abs(va - vb))} longer than {fast} ({secs(max(va, vb))} against {secs(min(va, vb))})."))
    ma, mb = set(by["models"]["a"]["value"]), set(by["models"]["b"]["value"])
    for side, mine, other, f in (("B", mb, ma, fb), ("A", ma, mb, fa)):
        only = [x for x in f.get("models") or [] if x["model"] in mine - other]
        if only:
            said = ", ".join(bare(x["model"]) + (f" ({_pct(x['cost_share'])} of its cost)" if x.get("cost_share") else "") for x in only)
            found.append((45 + 30 * max(x.get("cost_share") or 0 for x in only), f"{side} used {said}; {'A' if side == 'B' else 'B'} did not."))
    for key, one in (("failures", "failure"), ("asks", "ask to you"), ("retries", "retry")):
        r = by[key]
        if r["better"] in ("a", "b"):
            va, vb = int(r["a"]["value"]), int(r["b"]["value"])
            found.append((30 + 4 * abs(va - vb), f"A had {_count(va, one)}; B had {_count(vb, one)}."))
    t = by["tokens"]
    if t["better"] in ("a", "b"):
        va, vb = t["a"]["value"], t["b"]["value"]
        found.append((15 + 30 * _rel(va, vb), f"A used {kilo(va)} tokens; B used {kilo(vb)}."))
    va, vb = by["agents"]["a"]["value"], by["agents"]["b"]["value"]
    if isinstance(va, int) and isinstance(vb, int) and va != vb:
        found.append((15 + 30 * _rel(va, vb), f"A spawned {_count(va, 'agent')}; B spawned {_count(vb, 'agent')}."))
    lines = [line for _w, line in sorted(found, key=lambda x: -x[0])][:3]
    same = [r["label"].lower() for r in rows if r["better"] == "same"]
    if len(lines) < 3 and same:
        lines.append("The same for both: " + ", ".join(same) + ".")
    if len(lines) < 3 and ma == mb and ma:
        lines.append("Both used the same models: " + ", ".join(sorted(bare(m) for m in ma)) + ".")
    while len(lines) < 3:
        lines.append(["Nothing else differed in the figures.", "No other figure was recorded for both."][len(lines) % 2])
    return lines[:3]
