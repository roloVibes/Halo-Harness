"""halo_harness.orchestra.coach_prices -- the model catalog the coach prices
lanes with (Halo 3.0.9.0 round R3; 3.1.0.0 R2 cut it out of
coach_facts.py). `catalog(state_dir)` is the model catalog on disk (every
provider's rows plus models.json's OpenRouter rows, whether or not
OpenRouter is enabled here: a run's models still have prices), [] when it
cannot be read; `price_of`, `price_words` and `best_for` read one model's
row. The model rules (coach_orchestra_rules.py) compare against
`TOP_PRICE` and `CHEAP_PRICE`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

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
