"""halo_harness.models_library.rows -- Halo 3.3.5.0 R2: a library row, its card, its fit badge.

LibraryRow (row_builders.py makes them) = {source ("ollama" | "hf"), id (the library name or the repo),
tag_or_file, name, family, params (billions), quant, size_bytes (on disk: the weights and a projector),
weights_bytes, projector_bytes, capabilities [tools, vision, embedding, thinking, ...], context (the trained
window when the listing says it), downloads, updated, license, gated, description, pull_line ("ollama pull
qwen3.5:9b" | "ollama pull hf.co/<repo>:<quant>" | "halo local download <repo>"), kind ("ollama" | "gguf" |
"mlx"), key, shape (a model_info when known), sources {field: where it came from}}. 3.3.5.0 R3 hangs Pull on
`pull_line` and `key`.

    card_for_row(row) -> Card       R0b's card (providers/model_card.py's fields) from the row: purpose and
                                    thinking from the family rules, tools / vision from the chips, the window =
                                    the context with source "library", each `how` line marked "once pulled"
    fit_for_row(row, host_card, window, *, host_name="") -> fit_meter(...) + {numbers, estimate, shape_source}
                                    at the window picked; `why` carries the numbers: weights + KV at that window
                                    against the card's free memory, the newest resources sample included
    window_default(host) -> int     the host's max_ctx, else 32,768
"""

from __future__ import annotations

from typing import Optional

from halo_harness.models_library import shapes
from halo_harness.providers import model_card_purpose as P

DEFAULT_WINDOW = 32768
GIB = 2 ** 30
_SHOW = "/api/show capabilities"


def window_default(host) -> int:
    mc = getattr(host, "max_ctx", None)
    return mc if isinstance(mc, int) and mc > 0 else DEFAULT_WINDOW


def _src(text: str, source: str) -> str:
    return str(text or "").replace(_SHOW, source)


def card_for_row(row: dict) -> dict:
    from halo_harness.providers.model_card import fit_of
    from halo_harness.providers.model_card_words import how_lines
    name = row.get("name") or row.get("id") or ""
    caps = [str(c).lower() for c in row.get("capabilities") or []]
    from_chips = row.get("source") == "ollama"  # the library's chips are Ollama's own capability names
    rule_caps = (caps + ([] if "embedding" in caps else ["completion"])) if from_chips else None
    family = row.get("family") or ""
    chip_src = "the library's chips" if from_chips else "the hub's pipeline tag"
    purpose, psrc = P.purpose_of(name, rule_caps, family)
    if not from_chips and "embedding" in caps:
        purpose, psrc = "embedding", "the hub's pipeline tag (feature extraction)"
    elif not from_chips and purpose == "unknown":
        purpose, psrc = ("vision" if "vision" in caps and P.name_rule(name) == "vision" else "instruct",
                         "a chat model (no purpose word in its name)")
    thinks, tsrc = P.thinks_of(name, rule_caps if from_chips else (caps + ["completion"]) if "thinking" in caps else None, family)
    if from_chips:
        tools, tools_src = ("declared", "the library's chips: tools") if "tools" in caps else ("none", "the library's chips: no tools")
    else:
        tools, tools_src = "unknown", "the hub does not say (the chat template decides once pulled)"
    ctx = row.get("context")
    kind = "mlx" if row.get("kind") == "mlx" else "ollama"
    window = {"tokens": ctx if isinstance(ctx, int) and ctx > 0 else None, "source": "library",
              "ceiling": ctx, "ceiling_source": "the listing's context" if ctx else "", "kind": kind}
    card = {"ref": row.get("pull_line", "").split(" ")[-1] if row.get("pull_line") else name, "name": name,
            "host": None, "kind": kind, "thinks": thinks, "tools": tools, "vision": "vision" in caps,
            "embedding_only": purpose == "embedding", "purpose": purpose, "family": family,
            "params": row.get("params"), "quant": row.get("quant") or "", "window": window,
            "dialect": "native" if kind == "ollama" else "openai", "think_choice": None, "speed": None,
            "sources": {"thinks": _src(tsrc, chip_src), "tools": tools_src,
                        "vision": f"{chip_src}" if from_chips else "the hub's pipeline tag",
                        "purpose": _src(psrc, chip_src), "family": (row.get("sources") or {}).get("family", "the name"),
                        "params": (row.get("sources") or {}).get("params", "the name"),
                        "quant": (row.get("sources") or {}).get("quant", "unknown"), "window": "library", "row": "library"}}
    card["thinks_source"], card["purpose_source"] = card["sources"]["thinks"], card["sources"]["purpose"]
    from halo_harness.providers.vision_fact import apply as with_vision  # 3.3.6.0 R6: the row's metadata, the family
    with_vision(card, row, None)
    card["fit_for"], card["fit_why"] = fit_of(card)
    card["how"] = [f"{line} (once pulled)" for line in how_lines(card)]
    return card


def _gib(n) -> str:
    return f"{n / GIB:.1f} GiB"


def _live_card(host_card: dict, host_name: str) -> dict:
    """The host card with the newest resources sample's other programs (when it is newer than the card)."""
    try:
        from halo_harness.ollama_steward.resources_share import others_for
        live = others_for(host_name, host_card) if host_name else None
    except Exception:
        live = None
    if live is None:
        return host_card
    return {**host_card, "other_users": [{"name": "the newest resources sample", "bytes": int(live)}], "_sample": True}


def _bench_speed(row: dict, host_name: str) -> Optional[dict]:
    """3.3.6.0 R5: an installed tag's speed card on this host (its ceiling row), for the badge's "~41 tok/s at 32k"."""
    if row.get("source") != "ollama" or not host_name or not row.get("tag_or_file"):
        return None
    try:
        from halo_harness.config.paths import bridge_home
        from halo_harness.providers.local_bench_runs import speed_index
        return speed_index(bridge_home(), host_name).get(str(row["tag_or_file"]))
    except Exception:
        return None


def fit_for_row(row: dict, host_card: Optional[dict], window: int, *, host_name: str = "") -> dict:
    from halo_harness.ollama_steward.fit import card_budget
    from halo_harness.providers.fit_meter import fit_meter
    from halo_harness.providers.ollama_fit_parts import load_parts, projector_for
    window = int(window or DEFAULT_WINDOW)
    info, shape_src = shapes.shape_for(row.get("id"), row.get("tag_or_file") if row.get("source") == "ollama" else "",
                                       row.get("params"), row.get("shape"))
    estimate = shape_src != "the repo's config.json" or not row.get("weights_bytes")
    proj = int(row.get("projector_bytes") or 0)
    weights = row.get("weights_bytes") or ((row.get("size_bytes") or 0) - proj) or None
    base = {"numbers": None, "estimate": estimate, "shape_source": shape_src, "host": host_name or None}
    if not host_card:
        return {"level": "unknown", "at_window": window, "gpu_window": None,
                "why": f"no hardware card read for {host_name or 'this host'} yet (the Hosts page reads it)", **base}
    if not info or not isinstance(weights, int) or weights <= 0:
        return {"level": "unknown", "at_window": window, "gpu_window": None,
                "why": "the listing has no size or shape to work the fit out from", **base}
    synth = {"size": weights, "model_info": info, "capabilities": row.get("capabilities") or [],
             "projector_info": {"general.parameter_count": proj / 2} if proj else {}}
    hc = _live_card(host_card, host_name)
    top = min(max(window * 2, 65536), row.get("context") or 262144, 262144)
    meter = fit_meter({"kind": "ollama", "host": host_name or "this host", "window": {"tokens": window},
                       "speed": _bench_speed(row, host_name)}, hc, row=synth, top=top)
    b = card_budget(hc)
    parts = load_parts(info, weight_bytes=weights, window=window, bytes_per_elem=b["bpe"], parallel=b["parallel"],
                       projector_bytes=projector_for(synth)) or {}
    nums = {"weights": int(weights), "kv": int(parts.get("kv") or 0), "projector": int(parts.get("projector") or 0),
            "total": int(parts.get("total") or 0), "budget": int(b["budget"]), "others": int(b["others"]),
            "others_from": "the newest resources sample" if hc.get("_sample") else "the hardware card",
            "window": window, "kv_cache": b["kv"]}
    if meter["level"] in ("fits", "tight", "spill", "no") and nums["total"]:
        line = (f"weights {_gib(nums['weights'])} + KV {_gib(nums['kv'])} at {window:,} ({b['kv']})"
                + (f" + projector {_gib(nums['projector'])}" if nums["projector"] else "")
                + f" = {_gib(nums['total'])} of {_gib(nums['budget'])} free"
                + (" (other programs from the newest resources sample)" if hc.get("_sample") else ""))
        meter = {**meter, "why": f"{line}: {meter['why']}" + ("; an estimate until pulled (shape: " + shape_src + ")" if estimate else "")}
    from halo_harness.providers.ollama_twin_verify import pull_warning  # 3.3.6.0 R1: weights past the card
    return {**meter, **base, "numbers": nums, "pull_warning": pull_warning(weights, b["budget"])}
