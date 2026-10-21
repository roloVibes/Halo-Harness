"""halo_harness.capabilities_strengths -- the ranked strengths of a catalog
row (Halo 3.1.9.0 R1, "what each model is good at"), the kinds
`capabilities.score` hands over: `pdf` (a capability: document input) and
the five strengths `code`, `research`, `bulk`, `fast`, `local`.

Each scorer reads only what the row states or what this host measured
(`measured`: the gym, the tool-call probe, a learned tools rejection,
telemetry's speed, the canary census) and returns `(score 0..1, reason)`;
a fact nobody stated scores in the middle and says so, it is never
assumed:

* pdf      -- PDF input, then price as the tier proxy
* code     -- tool calls (required unless unstated), the tier, context,
              reasoning, the gym's tool-call accuracy and edit success; a
              failed tool canary halves it
* research -- 128k+ context, scaled to 500k, plus reasoning and the tier
* bulk     -- the blended price ((3 x in + out) / 4 per 1M): $0 = 1.0,
              $1 = 0; local compute is free
* fast     -- MEASURED tokens/s and time to first token only (telemetry's
              3+ calls, or the gym's own run); unmeasured = 0
* local    -- runs here (`is_local_model_ref`); the gym score, else context
"""

from __future__ import annotations

from typing import Optional

from halo_harness.capabilities import capability_profile
from halo_harness.capabilities_facts import _ctx, _ctx_words, _price, _tier, is_local, measured, tools_state


def price_out(row: dict) -> Optional[float]:
    p = row.get("price_out_per_m")
    return float(p) if isinstance(p, (int, float)) and not isinstance(p, bool) and p >= 0 else None


def blended_price(row: dict) -> Optional[float]:
    """USD per 1M tokens, (3 x in + out) / 4 -- a session reads far more
    than it writes; local compute is 0; None when the input price is unknown."""
    if is_local(row):
        return 0.0
    pin = _price(row)
    if pin is None:
        return None
    pout = price_out(row)
    return (3 * pin + (pout if pout is not None else pin)) / 4


def reasoning_score(row: dict) -> tuple:
    r = row.get("reasoning")
    if isinstance(r, dict):
        if r.get("kind") in ("native", "openai"):
            efforts = [e for e in (r.get("efforts") or []) if isinstance(e, str)]
            return 1.0, "reasoning" + (f" ({efforts[0]}..{efforts[-1]})" if len(efforts) > 1 else "")
        if r.get("kind") == "none":
            return 0.0, "no reasoning"
    return 0.4, "reasoning not stated"


def gym_entry(row: dict) -> Optional[dict]:
    g = measured(row).get("gym")
    return g if isinstance(g, dict) else None


def _gym_code_score(row: dict) -> tuple:
    g = gym_entry(row)
    if not g:
        return 0.5, ""
    parts = [g.get(k) for k in ("tool_call_accuracy", "edit_success") if isinstance(g.get(k), (int, float))]
    s = sum(parts) / len(parts) if parts else g.get("score")
    if not isinstance(s, (int, float)):
        return 0.5, ""
    return float(s), f"gym {float(s):.2f}"


def _text_out(row: dict) -> bool:
    mo = row.get("modalities_out")
    return not isinstance(mo, (list, tuple)) or "text" in mo


def score_strength(row: dict, kind: str, pf: dict) -> tuple:
    if kind == "pdf":
        prof = capability_profile(row)
        if not prof["files"]:
            return (0.0, "no PDF input in the catalog" if prof["known"] else "modalities unknown")
        t, words = _tier(row)
        return (round(0.6 + 0.4 * t, 3), "reads PDFs; " + words)
    if not _text_out(row):
        return (0.0, "does not answer in text")
    if kind == "code":
        return _code(row, pf)
    if kind == "research":
        return _research(row)
    if kind == "bulk":
        return _bulk(row)
    if kind == "fast":
        return _fast(row)
    if kind == "local":
        return _local(row)
    raise ValueError(f"unknown strength {kind!r}")


def _code(row: dict, pf: dict) -> tuple:
    tools, tools_words = tools_state(row)
    if tools is False:
        return (0.0, tools_words)
    tier_s, tier_words = _tier(row)
    ctx = _ctx(row)
    ctx_s = min(1.0, ctx / 200_000) if ctx else 0.3
    rs, r_words = reasoning_score(row)
    gs, g_words = _gym_code_score(row)
    s = 0.25 * (1.0 if tools else 0.4) + 0.35 * tier_s + 0.15 * ctx_s + 0.1 * rs + 0.15 * gs
    reasons = [tools_words, tier_words, f"{_ctx_words(ctx)} context" if ctx else "context unknown", r_words]
    if g_words:
        reasons.append(g_words)
    if pf.get("tools") is False:
        s *= 0.5
        reasons.append("failed the preflight tool-call canary")
    return (round(s, 3), "; ".join(reasons))


def _research(row: dict) -> tuple:
    ctx = _ctx(row)
    if not ctx:
        return (0.0, "context unknown")
    if ctx < 128_000:
        return (0.0, f"{_ctx_words(ctx)} context (research wants 128k or more)")
    rs, r_words = reasoning_score(row)
    tier_s, tier_words = _tier(row)
    s = 0.5 * min(1.0, ctx / 500_000) + 0.35 * rs + 0.15 * tier_s
    return (round(s, 3), f"{_ctx_words(ctx)} context; {r_words}; {tier_words}")


def _bulk(row: dict) -> tuple:
    b = blended_price(row)
    if b is None:
        return (0.0, "price unknown")
    s = max(0.0, 1.0 - b / 1.0)
    if is_local(row):
        words = "local, free"
    elif b <= 0:
        words = "free"
    else:
        pin, pout = _price(row), price_out(row)
        words = f"${pin:.2f} in / ${pout if pout is not None else pin:.2f} out per 1M"
    if s <= 0:
        return (0.0, words + ": not a cheap model")
    tools, tools_words = tools_state(row)
    if tools is False:
        s *= 0.6
        words += "; " + tools_words
    return (round(s, 3), words)


def _fast(row: dict) -> tuple:
    m = measured(row)
    tps, ttft = m.get("tokens_per_second"), m.get("ttft_s")
    g = gym_entry(row) or {}
    source = "measured here"
    if not isinstance(tps, (int, float)) and isinstance(g.get("tokens_per_second"), (int, float)):
        tps, source = g["tokens_per_second"], "the gym's run"
    if not isinstance(tps, (int, float)) and not isinstance(ttft, (int, float)):
        return (0.0, "speed not measured yet (3+ calls)")
    tps_s = min(1.0, tps / 120.0) if isinstance(tps, (int, float)) and tps > 0 else 0.4
    ttft_s = 1.0 - min(float(ttft), 4.0) / 4.0 if isinstance(ttft, (int, float)) else 0.5
    words = [f"{tps:.0f} tok/s" if isinstance(tps, (int, float)) else "", f"{ttft:.1f}s to first token"
             if isinstance(ttft, (int, float)) else ""]
    return (round(0.6 * tps_s + 0.4 * ttft_s, 3), ", ".join(w for w in words if w) + f" ({source})")


def _local(row: dict) -> tuple:
    if not is_local(row):
        return (0.0, "a remote model")
    g = gym_entry(row)
    ctx = _ctx(row)
    if g and isinstance(g.get("score"), (int, float)):
        return (round(0.6 + 0.4 * float(g["score"]), 3), f"runs here, free; gym {float(g['score']):.2f}")
    ctx_s = min(1.0, ctx / 128_000) if ctx else 0.3
    return (round(0.6 + 0.2 * ctx_s, 3), "runs here, free" + (f"; {_ctx_words(ctx)} context" if ctx else ""))
