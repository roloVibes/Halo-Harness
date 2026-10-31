"""halo_harness.models_library.nearest -- the nearest equivalent of a model that is gone (Halo 3.3.7.0 R4; plans/local-
model-fit-brief.md G14: "`qwen3.8:27b` was deleted -- nearest equivalent `qwen3.8:27b-gpu`").

    facts(name, row=None) -> {base, family, params_b, quant}     from the catalog row (details) and the name
    nearest(gone, rows, *, gone_row=None, card=None, window=None, profile=None, profiles=None) -> Near | None
    Near = {name, score, why [words], line ("same family, same quant, fits the same window")}

Each installed row is scored against what the gone model was (its last catalog row when Halo kept one -- the shelf's
retire line, the fit store's speed card -- else its name): the same family (the name's base before the tag, else the
details' family) +4, the same size (parameters within 15 %) +3, the same quant +2, fits the same window on this card
(the fit planner, when the card and the window are known) +1, the battery verified tool calls where the gone model
had them +1. No answer (None) when nothing shares its family or its size; then the closest spelling
(doctor_local_ids.nearest) is the caller's last resort, said as such. Arithmetic only: no request.
"""

from __future__ import annotations

import re
from typing import Optional

_PARAMS = re.compile(r"(\d+(?:\.\d+)?)\s*([bm])\b", re.IGNORECASE)


def _params(text) -> Optional[float]:
    m = _PARAMS.search(str(text or ""))
    if not m:
        return None
    v = float(m.group(1))
    return v / 1000.0 if m.group(2).lower() == "m" else v


def facts(name: str, row: Optional[dict] = None) -> dict:
    d = (row or {}).get("details") if isinstance((row or {}).get("details"), dict) else {}
    base = str(name or "").split(":", 1)[0].lower()
    tag = str(name or "").split(":", 1)[1] if ":" in str(name or "") else ""
    quant = str(d.get("quantization_level") or "").upper() or (re.search(r"(q\d(?:_k)?(?:_[msl])?|fp16|bf16|q8_0)", tag,
                                                                         re.IGNORECASE) or [""])[0].upper()
    return {"base": base, "family": str(d.get("family") or "").lower(), "params_b": _params(d.get("parameter_size"))
            or _params(tag) or _params(base), "quant": quant or None}


def _fits(card, row: dict, window: Optional[int]) -> Optional[bool]:
    if not card or not window or not isinstance(row.get("size"), int):
        return None
    try:
        from halo_harness.ollama_steward.fit import model_window_on_card
        most = model_window_on_card(card, row)
    except Exception:
        return None
    return None if most is None else most >= int(window)


def _tools(name: str, profiles) -> Optional[str]:
    from halo_harness.providers.ollama import ollama_names_match
    for p in profiles or []:
        if isinstance(p, dict) and ollama_names_match(p.get("model"), name):
            return p.get("tools")
    return None


def nearest(gone: str, rows: list, *, gone_row: Optional[dict] = None, card=None, window: Optional[int] = None,
            profile: Optional[dict] = None, profiles=None) -> Optional[dict]:
    from halo_harness.providers.ollama import ollama_names_match
    g = facts(gone, gone_row)
    best = None
    for r in rows or []:
        name = str((r or {}).get("model") or (r or {}).get("name") or "")
        if not name or ollama_names_match(name, gone):
            continue
        f = facts(name, r)
        score, why = 0, []
        family = (f["base"] == g["base"]) or bool(g["family"] and f["family"] == g["family"]
                                                 and f["base"].rstrip("0123456789.") == g["base"].rstrip("0123456789."))
        if family:
            score, why = score + 4, why + ["same family"]
        if g["params_b"] and f["params_b"] and abs(f["params_b"] - g["params_b"]) <= 0.15 * g["params_b"]:
            score, why = score + 3, why + ["same size"]
        if not family and "same size" not in why:
            continue
        if g["quant"] and f["quant"] and g["quant"] == f["quant"]:
            score, why = score + 2, why + ["same quant"]
        fits = _fits(card, {**r, "model": name}, window)
        if fits:
            score, why = score + 1, why + ["fits the same window"]
        if (profile or {}).get("tools") == "yes" and _tools(name, profiles) == "yes":
            score, why = score + 1, why + ["tool calls verified"]
        if best is None or score > best["score"] or (score == best["score"] and name < best["name"]):
            best = {"name": name, "score": score, "why": why, "line": ", ".join(why)}
    return best
