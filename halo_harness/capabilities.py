"""halo_harness.capabilities -- which model for what (Halo 3.0.1.0 round D1;
3.1.9.0 R1 "what each model is good at").

A capability profile is derived from facts the catalog already carries
(`providers.model_enumeration.build_model_rows`: `modalities_in`,
`modalities_out`, `image_output`, `tools`, `reasoning`, `local`, context,
prices, speed, and `measured` -- the gym, the probes, telemetry and the
preflight canary census), never guessed: a row with no modality data is
"unknown", shown as `?`, and ranks below a row that states the capability.
`best_for(rows, kind)` ranks for one job; `CAPABILITY_KINDS` say whether a
model can do a thing at all, `STRENGTH_KINDS` (capabilities_strengths.py)
rank how well or how cheaply:

* `visual`   -- reading screenshots, mockups, photos (vision + context + price)
* `audio`    -- listening (audio input)
* `video`    -- watching clips (video input)
* `image`    -- making pictures (image output)
* `design`   -- iterating a design with tools: vision, a large context, tool
                calls, speed and price together; a lane that failed the
                preflight image canary is demoted
* `pdf`      -- reading PDFs (document input)
* `code`     -- tool calls, a capable tier, context, reasoning, gym scores
* `research` -- long context plus reasoning
* `bulk`     -- cheap in and out
* `fast`     -- MEASURED speed only (telemetry, 3+ calls)
* `local`    -- runs on this machine or the LAN (offline, free)

Every ranked row carries a one-line `reason` in plain words;
`capabilities_line.best_at_line(row)` is the one honest line per model.

`best_for_media(rows, kind)` ranks the ComfyUI media-model inventory
(`providers.media_models`) by what a model produces, one of `OUTPUT_KINDS`;
those rows never mix with the LLM catalog above.
"""

from __future__ import annotations

from typing import Iterable, Optional

# the row readers live in capabilities_facts.py; the public ones are re-exported here
from halo_harness.capabilities_facts import (  # noqa: F401
    _ctx, _ctx_words, _price, _price_words, _speed, _tier, is_local, measured, preflight_for, tools_state,
)

CAPABILITY_KINDS = ("visual", "audio", "video", "image", "design", "pdf")
STRENGTH_KINDS = ("code", "research", "bulk", "fast", "local")
KINDS = CAPABILITY_KINDS + STRENGTH_KINDS
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
        "files": bool(mi & {"pdf", "file"}) if mi is not None else None,
        "image_out": bool(row.get("image_output")) or (("image" in mo) if mo is not None else None),
        "known": known,
    }
    chips = [name for name, key in (("vision", "vision"), ("audio", "audio"), ("video", "video"), ("files", "files"),
                                    ("image-out", "image_out")) if prof[key]]
    prof["chips"] = " ".join(chips) if chips else ("text" if known else "?")
    return prof


def score(row: dict, kind: str, *, preflight: Optional[dict] = None) -> tuple:
    """(score 0..1, reason). preflight: {ref: {"vision": True|False|None,
    "tools": ...}} from halo preflight (the row's own `measured.canary`
    applies without it), used to demote a lane whose canary failed."""
    if kind in STRENGTH_KINDS or kind == "pdf":
        from halo_harness.capabilities_strengths import score_strength
        return score_strength(row, kind, preflight_for(row, preflight))
    prof = capability_profile(row)
    reasons = []
    pf = preflight_for(row, preflight)
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
        tools, tools_words = tools_state(row)
        if tools is False:
            return (0.0, tools_words + ", so it cannot drive the craft apps")
        speed = _speed(row)
        speed_s = min(1.0, speed / 80.0) if speed else 0.5
        if speed:
            reasons.append(f"{speed:.0f} tok/s")
        out_tokens = row.get("max_output_tokens")
        out_s = min(1.0, float(out_tokens) / 32_000) if isinstance(out_tokens, (int, float)) and out_tokens else 0.5
        reasons.append(tools_words)
        s = 0.3 * 1.0 + 0.15 * ctx_s + 0.3 * tier_s + 0.1 * speed_s + 0.05 * out_s + (0.1 if tools else 0.03)
        if pf.get("tools") is False:
            s *= 0.5
            reasons.append("failed the preflight tool-call canary")
        elif pf.get("vision") is True:
            s = min(1.0, s + 0.05)
            reasons.append("passed the preflight image canary")
    return (round(s, 3), "; ".join(reasons))


def best_for(rows: Iterable[dict], kind: str, *, limit: int = 10, preflight: Optional[dict] = None,
             state_dir=None) -> list:
    """The top `limit` rows for `kind`, each `{ref, score, reason, chips}`.
    `state_dir`: read the preflight canary census there when no explicit
    `preflight` map is given (rows from `build_model_rows` already carry it
    as `measured.canary`)."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}; one of {', '.join(KINDS)}")
    if preflight is None and state_dir is not None:
        from halo_harness.providers.model_row_measured import canary_preflight
        preflight = canary_preflight(state_dir)
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
    """`ref  in: text,image  out: image  -- <best at>` lines for `halo models --capabilities`."""
    from halo_harness.capabilities_line import best_at_line
    out = []
    for row in rows:
        if not row.get("ref") or row.get("provider") == "alias":
            continue
        mi, mo = _mods(row, "modalities_in"), _mods(row, "modalities_out")
        ins = ",".join(sorted(mi)) if mi else "?"
        outs = ",".join(sorted(mo)) if mo else ("image" if row.get("image_output") else "text")
        out.append(f"{row['ref']:<40} in: {ins:<24} out: {outs:<11} -- {best_at_line(row)}")
    return out


def best_for_media(rows: Iterable[dict], kind: str, *, limit: int = 10) -> list:
    """Rank media-model rows for one of `OUTPUT_KINDS` (size, quant, a 4-step LoRA)."""
    from halo_harness.capabilities_media import best_for_media as rank
    return rank(rows, kind, limit=limit)
