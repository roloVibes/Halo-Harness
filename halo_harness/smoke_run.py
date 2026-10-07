"""halo_harness.smoke_run -- Halo 2.0.6 round 14: "Try it" on a bio and a
lineup smoke run from the forms, COST SHOWN FIRST (the item deferred from
2.0.5 round 2: "'Try it' on a bio and a lineup smoke run from the forms
(cost shown first)").

The cost estimate is honest about being an estimate: a fixed smoke
prompt's token footprint (DEFAULT_SMOKE_IN/OUT) times the model's real
per-million prices from the catalog, "price unknown" when the model
isn't in the catalog -- never a fake $0.00. The RUN reuses the proven
subprocess path `agents_doctor._default_call` already uses (`halo -p
--max-turns 1`), so a smoke run exercises exactly what a real call
would, credentials and all.
"""

from __future__ import annotations

from typing import Optional

DEFAULT_SMOKE_IN = 600     # tokens: the smoke prompt + the bio's own body
DEFAULT_SMOKE_OUT = 300    # tokens: a short reply


def smoke_cost_line(model_ref_raw: "Optional[str]", *, state_dir=None) -> str:
    """One sentence, shown BEFORE the run: the estimated worst-case cost
    of a smoke call against `model_ref_raw`, from the catalog's real
    per-million prices. `~$0.0004 (600 in / 300 out tokens at $0.60/$2.40
    per 1M)`; `price not in the catalog -- cost unknown` when the model
    has no prices; `no model picked yet` when the ref is empty. Never a
    fake $0.00 and never a raise."""
    if not isinstance(model_ref_raw, str) or not model_ref_raw.strip():
        return "no model picked yet -- pick a preference first"
    from halo_harness.providers.databricks import load_models_json
    from halo_harness.config.paths import bridge_home
    try:
        base = state_dir if state_dir is not None else bridge_home()
        catalog = load_models_json(base) or {}
    except Exception:
        catalog = {}
    entry = catalog.get(model_ref_raw) if isinstance(catalog, dict) else None
    if not isinstance(entry, dict):
        # a bare name (no route prefix) may still key the catalog
        entry = catalog.get(model_ref_raw.split(":", 1)[-1]) if isinstance(catalog, dict) else None
    price_in = entry.get("price_in_per_m") if isinstance(entry, dict) else None
    price_out = entry.get("price_out_per_m") if isinstance(entry, dict) else None
    if not isinstance(price_in, (int, float)) or not isinstance(price_out, (int, float)):
        return f"{model_ref_raw}: price not in the catalog -- cost unknown (a smoke run spends real tokens)"
    est = (DEFAULT_SMOKE_IN * price_in + DEFAULT_SMOKE_OUT * price_out) / 1_000_000
    return (f"{model_ref_raw}: ~${est:.4f} estimated ({DEFAULT_SMOKE_IN} in / {DEFAULT_SMOKE_OUT} out "
            f"tokens at ${price_in:g}/${price_out:g} per 1M) -- real spend, real credentials")


def run_bio_smoke(model_ref_raw: str, prompt: "Optional[str]" = None, *,
                  timeout: float = 60.0) -> str:
    """ONE smoke call against `model_ref_raw` through the real print-mode
    subprocess path. `prompt` defaults to a fixed 'reply in one short
    sentence' probe; the bio's own acceptance prompt is the caller's
    choice (the editor passes it when the bio has one). Never raises;
    the return is the call's stdout (empty on any failure -- the caller's
    note says so plainly)."""
    from halo_harness.agents_doctor import _default_call
    text = (prompt or "Reply with one short sentence confirming you can see this "
                      "smoke prompt, then stop.").strip()
    return _default_call(model_ref_raw, text, timeout=timeout)
