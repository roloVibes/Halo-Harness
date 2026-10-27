"""halo_harness.providers.databricks_prices -- the dollar price of a Databricks
pay-per-token endpoint (Halo 3.3.3.1, "costs are always dollars").

Every cost Halo shows is in USD. Databricks publishes its foundation-model
rates in DBUs per 1M tokens (providers/databricks_price_table.py, the
shipped table with its sources and date); one DBU is worth
`databricks.dbu_price_usd` dollars, by default DEFAULT_DBU_PRICE_USD:

    $0.07 per DBU -- the example SKU price on Databricks' Foundation Model
    Serving pricing page ("if your SKU price is $0.07 / DBU (e.g. AWS, US
    East N. Virginia)"), https://www.databricks.com/product/pricing/
    foundation-model-serving, read 2026-10-27. The figure is AWS's; other
    clouds, regions and contracts differ, so a workspace sets its own with
    `halo config set databricks.dbu_price_usd <usd>`.

`usd_per_m(endpoint)` answers, in order:
  1. `databricks.prices.<endpoint>` = {"in": usd, "out": usd[, "cache_read",
     "cache_write"]} (USD per 1M tokens) -- the owner's own figure always wins;
  2. the shipped table, by endpoint name (`databricks-glm-5-3`, `glm-5-3`,
     `dbx:databricks-glm-5-3`, a dated or `-code` / `-instruct` suffix form),
     its DBU rate times the DBU price;
  3. None: the endpoint stays unpriced and the session's total carries a `+`.
model.resolve_model_profile puts the answer on a Databricks ref's
ModelProfile, so CostMeter prices the endpoint's calls from their tokens.
"""

from __future__ import annotations

import re
from typing import Optional

DEFAULT_DBU_PRICE_USD = 0.07
_SUFFIX = re.compile(r"^(\d{4,8}|code|instruct|a\d+b|preview|latest)$")


def normalize(name: str) -> str:
    n = str(name or "").strip().lower()
    if n.startswith("dbx:"):
        n = n[4:]
    if n.startswith("databricks-"):
        n = n[len("databricks-"):]
    return re.sub(r"[._]", "-", n)


def table_row(name: str) -> "Optional[tuple]":
    """The shipped DBU row for an endpoint name: an exact match, else the
    longest table name it extends by one known suffix (`-0813`, `-code`)."""
    from halo_harness.providers.databricks_price_table import DBU_PER_M
    n = normalize(name)
    if n in DBU_PER_M:
        return DBU_PER_M[n]
    for key in sorted(DBU_PER_M, key=len, reverse=True):
        if n.startswith(key + "-") and _SUFFIX.match(n[len(key) + 1:]):
            return DBU_PER_M[key]
    return None


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else None


def override(name: str) -> Optional[dict]:
    """`databricks.prices.<endpoint>` (USD per 1M tokens), matched on the raw
    or the normalized name; None when unset or without both `in` and `out`."""
    from halo_harness.theme import get_config_value
    prices = get_config_value("databricks.prices", default=None)
    if not isinstance(prices, dict):
        return None
    want = normalize(name)
    for key, val in prices.items():
        if isinstance(val, dict) and (key == name or normalize(key) == want):
            p_in, p_out = _num(val.get("in")), _num(val.get("out"))
            if p_in is None or p_out is None:
                return None
            return {"in": p_in, "out": p_out, "cache_read": _num(val.get("cache_read")),
                    "cache_write": _num(val.get("cache_write")), "source": "override"}
    return None


def usd_per_m(name: str) -> Optional[dict]:
    """{"in", "out", "cache_read", "cache_write", "source"} in USD per 1M
    tokens (cache rates None when unpublished), or None when unpriced."""
    got = override(name)
    if got is not None:
        return got
    row = table_row(name)
    if row is None:
        return None
    from halo_harness.providers.dbx_routing import dbu_price_usd
    rate = dbu_price_usd()
    conv = (lambda d: round(d * rate, 6) if d is not None else None)
    return {"in": conv(row[0]), "out": conv(row[1]), "cache_read": conv(row[2]), "cache_write": conv(row[3]),
            "source": "table"}


def apply_to_profile(profile, name: str, *, keep_explicit: bool = False):
    """`profile` with the endpoint's dollar price on it (per token, as
    ModelProfile holds prices). `keep_explicit`: a routes.json profile that
    set its own `price_in` keeps it unless the owner's override says otherwise."""
    got = usd_per_m(name)
    if got is None or (keep_explicit and got["source"] != "override"):
        return profile
    from dataclasses import replace
    per = (lambda v: v / 1_000_000 if v is not None else None)
    return replace(profile, price_in=per(got["in"]), price_out=per(got["out"]),
                   price_cache_read=per(got["cache_read"]), price_cache_write=per(got["cache_write"]))
