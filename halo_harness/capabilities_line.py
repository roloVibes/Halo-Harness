"""halo_harness.capabilities_line -- "best at": one honest line per model
and the kinds it is good at (Halo 3.1.9.0 R1).

`kind_scores(row)` scores every `capabilities.KINDS` kind once;
`best_at_kinds` keeps the kinds a model is good at (any positive score for
a yes/no capability -- visual, audio, video, image, pdf -- and a floor per
ranked kind: `FLOORS`), strongest first; `best_at_line` says in plain words
what the row states and what this host measured, the gaps after a `;`:

    "vision+pdf in, tools, reasoning, long context (1M), premium; no audio"
    "tools, cheap, fast, gym 0.81; text in only"
    "unknown: no catalog data"

Nothing here is guessed: an unstated input list reads "inputs not stated",
an unstated tool flag "tools not stated".
"""

from __future__ import annotations

from typing import Optional

# the floor a RANKED kind's score must reach to count as "good at"; the
# yes/no capability kinds count at any positive score
FLOORS = {"design": 0.6, "code": 0.75, "research": 0.7, "bulk": 0.6, "fast": 0.6, "local": 0.6}
# kinds that drive tools count only when tool calls are stated or measured
NEEDS_TOOLS = ("design", "code")
PREMIUM_PRICE = 3.0  # $/M in: the top tier in capabilities._tier
_IN_WORDS = (("image", "vision"), ("audio", "audio"), ("video", "video"), ("pdf", "pdf"))


def kind_scores(row: dict, preflight: Optional[dict] = None) -> dict:
    """{kind: (score, reason)} for every kind."""
    from halo_harness.capabilities import KINDS, score
    out = {}
    for kind in KINDS:
        try:
            out[kind] = score(row, kind, preflight=preflight)
        except Exception:
            out[kind] = (0.0, "could not score")
    return out


def best_at_kinds(row: dict, preflight: Optional[dict] = None, *, scores: Optional[dict] = None) -> list:
    from halo_harness.capabilities_facts import tools_state
    scores = kind_scores(row, preflight) if scores is None else scores
    tools = tools_state(row)[0]
    good = [(s, k) for k, (s, _r) in scores.items()
            if s > 0 and s >= FLOORS.get(k, 0.0) and (k not in NEEDS_TOOLS or tools is True)]
    return [k for _s, k in sorted(good, key=lambda t: (-t[0], t[1]))]


def _known(row: dict) -> bool:
    from halo_harness.capabilities_facts import is_local, measured
    facts = ("modalities_in", "tools", "reasoning", "price_in_per_m", "context_tokens")
    return any(row.get(k) is not None for k in facts) or bool(measured(row)) or is_local(row)


def best_at_line(row: dict, preflight: Optional[dict] = None, *, scores: Optional[dict] = None) -> str:
    from halo_harness.capabilities import capability_profile
    from halo_harness.capabilities_facts import _ctx, _ctx_words, _price, is_local, preflight_for, tools_state
    from halo_harness.capabilities_strengths import blended_price, gym_entry
    if not _known(row):
        return "unknown: no catalog data"
    scores = kind_scores(row, preflight) if scores is None else scores
    pos: list = []
    neg: list = []
    mi = row.get("modalities_in") if isinstance(row.get("modalities_in"), (list, tuple)) else None
    if mi is not None:
        ins = [word for m, word in _IN_WORDS if m in mi or (m == "pdf" and "file" in mi)]
        if ins:
            pos.append("+".join(ins) + " in")
        if not ins:
            neg.append("text in only")
        else:
            neg += [f"no {word}" for m, word in _IN_WORDS[:2] if m not in mi]
    else:
        neg.append("inputs not stated")
    if capability_profile(row)["image_out"]:
        pos.append("makes images")
    tools, tools_words = tools_state(row)
    if tools:
        pos.append("tools (probed)" if "probed" in tools_words else "tools")
    elif tools is False:
        neg.append(tools_words)
    else:
        neg.append("tools not stated")
    r = row.get("reasoning")
    if isinstance(r, dict) and r.get("kind") in ("native", "openai"):
        pos.append("reasoning")
    ctx = _ctx(row)
    if ctx >= 400_000:
        pos.append(f"long context ({_ctx_words(ctx)})")
    blended, pin = blended_price(row), _price(row)
    if is_local(row):
        pos.append("local, free")
    elif blended is not None and blended <= 0:
        pos.append("free")
    elif scores.get("bulk", (0, ""))[0] >= FLOORS["bulk"]:
        pos.append("cheap")
    elif pin is not None and pin >= PREMIUM_PRICE:
        pos.append("premium")
    elif pin is None:
        neg.append("price unknown")
    if scores.get("fast", (0, ""))[0] >= FLOORS["fast"]:
        pos.append("fast")
    if row.get("open_weights") is True and not is_local(row):
        pos.append("open weights")
    g = gym_entry(row)
    if g and isinstance(g.get("score"), (int, float)):
        pos.append(f"gym {float(g['score']):.2f}")
    pf = preflight_for(row, preflight)
    if pf.get("vision") is False:
        neg.append("failed the image canary")
    if pf.get("tools") is False:
        neg.append("failed the tool canary")
    if pos and neg:
        return ", ".join(pos) + "; " + ", ".join(neg)
    return ", ".join(pos or neg)
