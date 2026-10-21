"""halo_harness.capabilities_facts -- what the "which model for what"
scorers read off a catalog row (Halo 3.1.9.0 R1): whether it runs here
(`is_local`: the row's `local` key, else `model.is_local_ref_string`), what
this host measured (`measured`), the preflight canaries that apply to it
(`preflight_for`: the census the row carries, overridden by an explicit
map), what is known about its tool calls (`tools_state`, measured facts
first), its input price, context and speed, and price as the stated tier
proxy (`_tier`) with the words the reasons use. capabilities.py,
capabilities_strengths.py and capabilities_line.py all read rows through
these, so a fact is read one way everywhere.
"""

from __future__ import annotations

from typing import Optional


def is_local(row: dict) -> bool:
    """The row's `local` key; a row built elsewhere (no key) is asked of its ref."""
    if isinstance(row.get("local"), bool):
        return row["local"]
    from halo_harness.model import is_local_ref_string
    return is_local_ref_string(row.get("ref"))


def measured(row: dict) -> dict:
    m = row.get("measured")
    return m if isinstance(m, dict) else {}


def preflight_for(row: dict, preflight: Optional[dict]) -> dict:
    """The canary checks for this row: the census the row carries
    (`measured.canary`), overridden by an explicit `preflight` map."""
    canary = measured(row).get("canary") if isinstance(measured(row).get("canary"), dict) else {}
    pf = {k: canary.get(k) for k in ("tools", "vision") if canary.get(k) is not None}
    pf.update({k: v for k, v in ((preflight or {}).get(row.get("ref", "")) or {}).items() if v is not None})
    return pf


def tools_state(row: dict) -> tuple:
    """(True | False | None, words): what is known about tool calls, the
    measured facts first (a learned rejection, the Ollama probe)."""
    m = measured(row)
    if m.get("tools_rejected"):
        return False, "rejects tool calls (learned from a live 400)"
    if m.get("tools_probe") is False:
        return False, "failed the tool-call probe"
    if m.get("tools_probe") is True:
        return True, "tool calls (probed)"
    t = row.get("tools")
    if t is True:
        return True, "tool calls"
    if t is False:
        return False, "no tool calls"
    return None, "tool calls not stated"


def _price(row: dict) -> Optional[float]:
    p = row.get("price_in_per_m")
    return float(p) if isinstance(p, (int, float)) and not isinstance(p, bool) and p >= 0 else None


def _ctx(row: dict) -> int:
    c = row.get("context_tokens")
    return int(c) if isinstance(c, (int, float)) and not isinstance(c, bool) else 0


def _speed(row: dict) -> Optional[float]:
    s = row.get("speed_tokens_per_second")
    return float(s) if isinstance(s, (int, float)) and s > 0 else None


def _tier(row: dict) -> tuple:
    """Price as a stated capability proxy: free rows are usually small or
    preview models, the mid range is where the workhorses sit, the top end
    buys the most careful eyes. Local models (price 0 by definition) are
    scored by context instead -- `local` is `is_local_model_ref` (a Hugging
    Face ROUTER row is remote and priced like any other)."""
    price = _price(row)
    if is_local(row):
        return (0.5, "local, " + _price_words(row))
    if price is None:
        return (0.6, "price unknown")
    if price <= 0:
        return (0.35, "free (usually a small or preview model)")
    if price < 0.5:
        return (0.6, f"${price:.2f}/M in, budget tier")
    if price < 3:
        return (0.9, f"${price:.2f}/M in, workhorse tier")
    return (1.0, f"${price:.2f}/M in, top tier")


def _price_words(row: dict) -> str:
    p = _price(row)
    if p is None:
        return "price unknown"
    if p <= 0:
        return "free"
    return f"${p:.2f}/M in"


def _ctx_words(ctx: int) -> str:
    if ctx >= 1_000_000:
        return f"{ctx / 1_000_000:.0f}M"
    return f"{ctx // 1000}k"
