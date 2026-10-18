"""halo_harness.work.forecast -- what a unit of work will cost before it runs
(Halo 3.1.2.0 R2, docs/ORCHESTRA.md "The forecast", docs/TEAM.md "Budgets").

One forecast line per unit, then a total against a budget:

    {"unit": "job-2", "model": "or:vendor/mid", "tokens_in": 21000, "tokens_out": 2400,
     "usd": 0.0306, "usd_low": 0.0153, "usd_high": 0.0612, "source": "lead|heuristic|turn|budget|fixed", "priced": true}
    {"usd", "usd_low", "usd_high", "budget_usd": 0.5 | null, "over": false, "unpriced": 0, "units": 3}

The price is the model catalog's (orchestra/coach_prices.py: the price per
million input tokens and per million output tokens of the model's row). A
row without an output price is priced at OUT_RATIO times its input price;
a free or local model (Ollama, Hugging Face, a price of 0) costs 0; a model
the catalog does not list leaves the line unpriced (`usd` null, `priced`
false) and the total counts it in `unpriced`. The band around `usd` says how
sure the estimate is (BAND): a lead's own token estimate x0.8 .. x1.5, a
heuristic or a team member's priced turn x0.5 .. x2, a `budget` (a flow
step's own budget) or a `fixed` amount (an unpriced member turn) x1. The
total is `over` when its high end passes the budget.
"""

from __future__ import annotations

from typing import Optional

BAND = {"lead": (0.8, 1.5), "heuristic": (0.5, 2.0), "turn": (0.5, 2.0), "budget": (1.0, 1.0), "fixed": (1.0, 1.0)}
OUT_RATIO = 4.0
FREE_PROVIDERS = ("ollama", "huggingface")


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else None


def prices(rows: list, ref: str) -> "Optional[tuple[float, float]]":
    """`(usd per M input tokens, usd per M output tokens)` of `ref` in the catalog, or None when unlisted."""
    if not ref:
        return None
    row = next((r for r in rows or [] if r.get("ref") == ref), None)
    if row is None:
        return None
    if row.get("provider") in FREE_PROVIDERS:
        return 0.0, 0.0
    p_in, p_out = _num(row.get("price_in_per_m")), _num(row.get("price_out_per_m"))
    if p_in is None and p_out is None:
        return None
    p_in = p_in if p_in is not None else (p_out or 0.0) / OUT_RATIO
    return p_in, (p_out if p_out is not None else p_in * OUT_RATIO)


def line(unit: str, model: str, tokens_in: int, tokens_out: int, source: str, rows: list) -> dict:
    """One unit's forecast: its tokens priced at its model's catalog price, with the source's band."""
    low, high = BAND.get(source, BAND["heuristic"])
    p = prices(rows, model)
    out = {"unit": str(unit), "model": model or "", "tokens_in": int(tokens_in), "tokens_out": int(tokens_out),
           "usd": None, "usd_low": None, "usd_high": None, "source": source, "priced": p is not None}
    if p is not None:
        usd = (tokens_in * p[0] + tokens_out * p[1]) / 1_000_000
        out.update(usd=round(usd, 6), usd_low=round(usd * low, 6), usd_high=round(usd * high, 6))
    return out


def fixed(unit: str, usd: float, source: str = "budget", model: str = "") -> dict:
    """A line whose cost is known up front (a flow step's budget, a fixed per-turn estimate)."""
    low, high = BAND.get(source, (1.0, 1.0))
    return {"unit": str(unit), "model": model, "tokens_in": 0, "tokens_out": 0, "usd": round(usd, 6),
            "usd_low": round(usd * low, 6), "usd_high": round(usd * high, 6), "source": source, "priced": True}


def total(lines: list, budget_usd=None) -> dict:
    """The lines added up, against `budget_usd` (None: no budget, never over)."""
    priced = [x for x in lines if x.get("priced")]
    budget = _num(budget_usd)
    out = {"usd": round(sum(x["usd"] for x in priced), 6), "usd_low": round(sum(x["usd_low"] for x in priced), 6),
           "usd_high": round(sum(x["usd_high"] for x in priced), 6), "budget_usd": budget,
           "over": False, "unpriced": len(lines) - len(priced), "units": len(lines)}
    out["over"] = budget is not None and out["usd_high"] > budget + 1e-12
    return out


def money(v) -> str:
    """Dollars: two decimals from a dollar up, else two to four (`$0.50`, `$0.105`, `$0.0306`), `$0` for
    nothing, `?` unknown."""
    if v is None:
        return "?"
    if not v:
        return "$0"
    if v >= 1:
        return f"${v:.2f}"
    whole, _, dec = f"{v:.4f}".partition(".")
    return f"${whole}.{dec.rstrip('0').ljust(2, '0')}"


def cell(x: dict) -> str:
    """A line's cost as the CLI's Cost column shows it."""
    if not x.get("priced"):
        return f"? ({x.get('model') or 'no model'})"
    if x.get("usd_low") == x.get("usd_high"):
        return money(x.get("usd"))
    return f"{money(x.get('usd_low'))}-{money(x.get('usd_high'))}"


def words(t: dict) -> str:
    """`forecast $0.12-$0.48 (3 lanes) against a budget of $0.30: over`."""
    text = f"forecast {money(t.get('usd_low'))}-{money(t.get('usd_high'))}"
    if t.get("unpriced"):
        text += f" (+{t['unpriced']} unpriced)"
    if t.get("budget_usd") is None:
        return text + ", no budget set"
    return text + f" against a budget of {money(t['budget_usd'])}" + (": over" if t.get("over") else ": within")
