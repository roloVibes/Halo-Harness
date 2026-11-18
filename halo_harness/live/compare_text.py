"""halo_harness.live.compare_text -- the words of a comparison (Halo 3.4.1.0 R2 "Time"): one run's cells (a value and
its text per row; the report card will read the same) and "what differed" in three plain lines, derived from the rows
(live/compare.py). A cost Halo cannot price is "unknown" (or the priced part with a "+"), never $0. No model call.
3.6.0.3: the card's words (money, secs, kilo, bare, cells) moved to live/card_data.py, re-exported here.
"""

from __future__ import annotations

from halo_harness.live.card_data import (bare, cells, kilo, money, _pct, secs)  # noqa: F401 (moved in 3.6.0.3)


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
            times = lambda n: "never" if not n else "once" if n == 1 else f"{n} times"  # noqa: E731
            found.append((30 + 4 * abs(va - vb), f"A asked you {times(va)}; B {times(vb)}." if key == "asks"  # 3.4.1.1 (61)
                          else f"A had {_count(va, one)}; B had {_count(vb, one)}."))
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
