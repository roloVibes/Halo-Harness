"""halo_harness.capabilities -- which model for what (Halo 3.0.1.0 round D1).

A capability profile is derived from facts the catalog already carries
(`providers.model_enumeration.build_model_rows`: `modalities_in`,
`modalities_out`, `image_output`, context, prices, speed), never guessed:
a row with no modality data is "unknown", shown as `?`, and ranks below a
row that states the capability. `best_for(rows, kind)` ranks for one job:

* `visual`  -- reading screenshots, mockups, photos (vision + context + price)
* `audio`   -- listening (audio input)
* `video`   -- watching clips (video input)
* `image`   -- making pictures (image output)
* `design`  -- iterating a design with tools: vision, a large context, tool
               calls, speed and price together; a lane that failed the
               preflight image canary is demoted

Every ranked row carries a one-line `reason` in plain words.

`best_for_media(rows, kind)` ranks the ComfyUI media-model inventory
(`providers.media_models`) by what a model produces, one of `OUTPUT_KINDS`;
those rows never mix with the LLM catalog above.
"""

from __future__ import annotations

from typing import Iterable, Optional

KINDS = ("visual", "audio", "video", "image", "design")
OUTPUT_KINDS = ("image-gen", "video-gen", "audio-gen", "upscale")  # media models, by what they produce


def _mods(row: dict, key: str) -> Optional[set]:
    v = row.get(key)
    return set(v) if isinstance(v, (list, tuple, set)) else None


def capability_profile(row: dict) -> dict:
    """{vision, audio, video, files, image_out: bool|None, known: bool, chips: str}"""
    mi = _mods(row, "modalities_in")
    mo = _mods(row, "modalities_out")
    known = mi is not None
    prof = {
        "vision": ("image" in mi) if mi is not None else None,
        "audio": ("audio" in mi) if mi is not None else None,
        "video": ("video" in mi) if mi is not None else None,
        "files": ("file" in mi) if mi is not None else None,
        "image_out": bool(row.get("image_output")) or (("image" in mo) if mo is not None else None),
        "known": known,
    }
    chips = []
    if prof["vision"]:
        chips.append("vision")
    if prof["audio"]:
        chips.append("audio")
    if prof["video"]:
        chips.append("video")
    if prof["files"]:
        chips.append("files")
    if prof["image_out"]:
        chips.append("image-out")
    prof["chips"] = " ".join(chips) if chips else ("text" if known else "?")
    return prof


def _price(row: dict) -> Optional[float]:
    p = row.get("price_in_per_m")
    return float(p) if isinstance(p, (int, float)) and p >= 0 else None


def _ctx(row: dict) -> int:
    c = row.get("context_tokens")
    return int(c) if isinstance(c, (int, float)) else 0


def _speed(row: dict) -> Optional[float]:
    s = row.get("speed_tokens_per_second")
    return float(s) if isinstance(s, (int, float)) and s > 0 else None


def _price_score(price: Optional[float]) -> float:
    """Free or cheap scores high; unknown sits in the middle."""
    if price is None:
        return 0.5
    if price <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - (price / 15.0)))  # $15/M in is the floor of the scale


def score(row: dict, kind: str, *, preflight: Optional[dict] = None) -> tuple:
    """(score 0..1, reason). preflight: {ref: {"vision": True|False|None}} from
    halo preflight, used to demote a lane whose image canary failed."""
    prof = capability_profile(row)
    reasons = []
    ref = row.get("ref", "")
    pf = (preflight or {}).get(ref) or {}
    if kind == "audio":
        if not prof["audio"]:
            return (0.0, "no audio input in the catalog" if prof["known"] else "modalities unknown")
        t, words = _tier(row)
        return (0.6 + 0.4 * t, "accepts audio; " + words)
    if kind == "video":
        if not prof["video"]:
            return (0.0, "no video input in the catalog" if prof["known"] else "modalities unknown")
        t, words = _tier(row)
        return (0.6 + 0.4 * t, "accepts video; " + words)
    if kind == "image":
        if not prof["image_out"]:
            return (0.0, "does not output images")
        t, words = _tier(row)
        return (0.7 + 0.3 * t, "makes images; " + words)
    # visual and design both start from vision and a text reply
    if not prof["vision"]:
        return (0.0, "no image input in the catalog" if prof["known"] else "modalities unknown")
    mo = _mods(row, "modalities_out")
    if mo is not None and "text" not in mo:
        return (0.0, "does not answer in text (" + ",".join(sorted(mo)) + " only)")
    if pf.get("vision") is False:
        return (0.05, "accepts images on paper but failed the preflight image canary")
    reasons.append("reads images")
    ctx = _ctx(row)
    ctx_s = min(1.0, ctx / 200_000) if ctx else 0.3
    reasons.append(f"{_ctx_words(ctx)} context" if ctx else "context unknown")
    tier_s, tier_words = _tier(row)
    reasons.append(tier_words)
    if kind == "visual":
        s = 0.45 * 1.0 + 0.25 * ctx_s + 0.30 * tier_s
    else:  # design: tool calls are required; speed and output length count
        tools = row.get("tools")
        if tools is False:
            return (0.0, "no tool calls, so it cannot drive the craft apps")
        speed = _speed(row)
        speed_s = min(1.0, speed / 80.0) if speed else 0.5
        if speed:
            reasons.append(f"{speed:.0f} tok/s")
        out_tokens = row.get("max_output_tokens")
        out_s = min(1.0, float(out_tokens) / 32_000) if isinstance(out_tokens, (int, float)) and out_tokens else 0.5
        reasons.append("tool calls" if tools else "tool calls not stated")
        s = 0.3 * 1.0 + 0.15 * ctx_s + 0.3 * tier_s + 0.1 * speed_s + 0.05 * out_s + (0.1 if tools else 0.03)
        if pf.get("tools") is False:
            s *= 0.5
            reasons.append("failed the preflight tool-call canary")
        elif pf.get("vision") is True:
            s = min(1.0, s + 0.05)
            reasons.append("passed the preflight image canary")
    return (round(s, 3), "; ".join(reasons))


def _tier(row: dict) -> tuple:
    """Price as a stated capability proxy for picture-reading work: free
    rows are usually small or preview models, the mid range is where the
    workhorses sit, the top end buys the most careful eyes. Local models
    (price 0 by definition) are scored by context instead."""
    price = _price(row)
    if row.get("provider") in ("ollama", "huggingface"):
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


def best_for(rows: Iterable[dict], kind: str, *, limit: int = 10, preflight: Optional[dict] = None) -> list:
    """The top `limit` rows for `kind`, each `{ref, score, reason, chips}`."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; one of {', '.join(KINDS)}")
    ranked = []
    for row in rows:
        if not row.get("ref") or row.get("provider") == "alias":
            continue
        s, reason = score(row, kind, preflight=preflight)
        if s > 0:
            ranked.append({"ref": row["ref"], "score": s, "reason": reason, "chips": capability_profile(row)["chips"],
                           "provider": row.get("provider", "")})
    ranked.sort(key=lambda r: (-r["score"], r["ref"]))
    return ranked[:limit]


def capability_lines(rows: Iterable[dict]) -> list:
    """`ref  in: text,image  out: image` lines for `halo models --capabilities`."""
    out = []
    for row in rows:
        if not row.get("ref") or row.get("provider") == "alias":
            continue
        mi, mo = _mods(row, "modalities_in"), _mods(row, "modalities_out")
        ins = ",".join(sorted(mi)) if mi else "?"
        outs = ",".join(sorted(mo)) if mo else ("image" if row.get("image_output") else "text")
        out.append(f"{row['ref']:<40} in: {ins:<24} out: {outs}")
    return out


def best_for_media(rows: Iterable[dict], kind: str, *, limit: int = 10) -> list:
    """Rank media-model rows for one of `OUTPUT_KINDS` (size, quant, a 4-step LoRA)."""
    from halo_harness.capabilities_media import best_for_media as rank
    return rank(rows, kind, limit=limit)
