"""halo_harness.crew.builder_cap -- the builder's model and its money cap (Halo 3.6.0.0 R1).

    studio.builder.model    the builder's model (Settings -> Studio -> Builder); unset: the strongest reasoning model
                            the model index names (models_best_at), else your main `model`
    studio.builder.cap_usd  what the builder may spend in a day, in dollars (default 1.00); the person sets it

The day's spend is kept in <state>/crew/.builder/spend.json ({day, usd}); every builder call adds what it cost (a call
with no catalog price counts at PRICE_IN / PRICE_OUT per million tokens, a local model at 0). `left()` is what is left
today; Studio's builder route checks it before every request and after every call, so the cap holds server side.
"""

from __future__ import annotations

import json
import time

from halo_harness.crew import store

CAP_KEY, MODEL_KEY = "studio.builder.cap_usd", "studio.builder.model"
DEFAULT_CAP = 1.0
PRICE_IN, PRICE_OUT = 3.0, 15.0  # $ per million tokens for a call whose model has no catalog price
TYPICAL = "about $0.01-0.03 a request"


def _get(key: str, default=None):
    try:
        from halo_harness.theme import get_config_value
        return get_config_value(key, default)
    except Exception:
        return default


def cap_usd() -> float:
    v = _get(CAP_KEY, DEFAULT_CAP)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else DEFAULT_CAP


def model(state_dir=None) -> "tuple[str, str]":
    """(model ref, where it came from)."""
    got = _get(MODEL_KEY, "")
    if isinstance(got, str) and got.strip():
        return got.strip(), "Settings -> Studio -> Builder"
    try:
        from halo_harness import models_best_at
        best = ((models_best_at.load(store.state_dir_of(state_dir)) or {}).get("best") or {}).get("reasoning") or {}
        if best.get("strongest"):
            return str(best["strongest"]), "your strongest reasoning model"
    except Exception:
        pass
    main = _get("model", "")
    return (str(main), "your main model") if main else ("", "no model: set one in Settings -> Studio -> Builder")


def _path(state_dir):
    return store.state_dir_of(state_dir) / "crew" / ".builder" / "spend.json"


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def spent(state_dir=None) -> float:
    try:
        rec = json.loads(_path(state_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0.0
    if not isinstance(rec, dict) or rec.get("day") != _today():
        return 0.0
    v = rec.get("usd")
    return float(v) if isinstance(v, (int, float)) else 0.0


def add(state_dir, usd: float) -> float:
    total = round(spent(state_dir) + max(0.0, float(usd or 0.0)), 6)
    store.write_text(_path(state_dir), json.dumps({"day": _today(), "usd": total}))
    return total


def left(state_dir=None) -> float:
    return cap_usd() - spent(state_dir)


def cost_of(reply: dict) -> float:
    """A call's dollars: its catalog price, 0 for a local model, else the tokens at PRICE_IN / PRICE_OUT."""
    if isinstance(reply.get("cost_usd"), (int, float)):
        return float(reply["cost_usd"])
    if reply.get("local"):
        return 0.0
    tin, tout = int(reply.get("input_tokens") or 0), int(reply.get("output_tokens") or 0)
    return (tin * PRICE_IN + tout * PRICE_OUT) / 1_000_000


def reached_line(state_dir=None) -> str:
    return (f"Today's builder cap (${cap_usd():.2f}) is reached (${spent(state_dir):.3f} spent). Raise it in Settings -> "
            f"Studio -> Builder ({CAP_KEY}), or it starts again tomorrow.")


def meta(state_dir=None) -> dict:
    ref, why = model(state_dir)
    return {"model": ref, "model_from": why, "typical": TYPICAL, "spent_usd": round(spent(state_dir), 4),
            "cap_usd": cap_usd(), "reached": left(state_dir) <= 0}
