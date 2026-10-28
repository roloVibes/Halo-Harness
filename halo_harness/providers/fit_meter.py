"""halo_harness.providers.fit_meter -- Halo 3.3.5.0 R0b: the fit meter, the
first of "Local"'s five ideas: will this model run here at this window?

    fit_meter(card, host_card, *, row=None) -> {level, at_window, gpu_window, why}

`level` is one of
    fits    every layer on the GPU with room to spare: Ollama's own fit
            (llama.cpp's margin kept) holds the window
    tight   it holds the window only with every layer forced onto the GPU
            (a tuned twin, `num_gpu` all): the margin is gone
    spill   part of it runs on the CPU at this window (slow)
    no      it does not fit this machine at this window (GPU and RAM)
    cloud   a cloud model: it runs on the provider's machines
    unknown nothing to work it out from (no hardware card read for the host
            yet, a catalog row without a size or a shape, a local server
            that reports no sizes)
`at_window` is the window the card would run (the card's `window.tokens`),
`gpu_window` the largest that stays on the GPU; `why` says it in one line.
The arithmetic is the fit planner's (ollama_steward/fit.py,
providers/ollama_fit_parts.py); a host card comes from the Ollama panel's
cache (`host_card_of`) and is read only when the caller says so.
"""

from __future__ import annotations

from typing import Optional

GIB = 2 ** 30
LEVELS = ("fits", "tight", "spill", "no", "cloud", "unknown")
RAM_SHARE = 0.8  # what of the system RAM a spilled load may take beside everything else


def _gib(n) -> str:
    return f"{n / GIB:.1f} GiB"


def _out(level: str, why: str, at=None, gpu=None) -> dict:
    return {"level": level, "at_window": at, "gpu_window": gpu, "why": why}


def _row_of(card: dict) -> Optional[dict]:
    """The cached catalog row behind an Ollama card (no request)."""
    try:
        from halo_harness.providers.local_models_cached import cached_catalog
        from halo_harness.providers.model_card import _ollama_host, _row_for, parse_ref
        ref = parse_ref(card.get("ref") or "")
        host = _ollama_host(ref, None)
        catalog = cached_catalog(host) if host is not None else None
        return _row_for(catalog, ref.model) if catalog else None
    except Exception:
        return None


def fit_meter(card: dict, host_card: Optional[dict], *, row: Optional[dict] = None, top: Optional[int] = None) -> dict:
    """See the module docstring. `top` caps the windows tried (3.3.5.0 R2: the Library rates hundreds of rows at the
    window picked; `gpu_window` then says "up to `top`" at most)."""
    kind = (card or {}).get("kind")
    w = (card or {}).get("window") or {}
    at = w.get("tokens") if isinstance(w.get("tokens"), int) else None
    if kind == "cloud":
        return _out("cloud", "a cloud model: it runs on the provider's machines", at)
    if kind != "ollama":
        if w.get("source") == "loaded window" and at:
            return _out("fits", f"the server runs it now at {at:,} tokens", at)
        return _out("unknown", "this server reports no sizes, so the fit cannot be worked out here", at)
    from halo_harness.ollama_steward.fit import _kw, card_budget
    from halo_harness.providers.ollama_fit_parts import fit_window, need_bytes
    b = card_budget(host_card or {})
    host = card.get("host") or "this host"
    if not b["budget"]:
        return _out("unknown", f"no hardware card read for {host} yet (the Ollama panel reads it)", at)
    row = row if row is not None else _row_of(card)
    info = (row or {}).get("model_info") if isinstance((row or {}).get("model_info"), dict) else {}
    size = (row or {}).get("size")
    if not isinstance(size, int) or not info:
        return _out("unknown", "the catalog row has no size or shape to work the fit out from", at)
    at = at or 4096
    kw = {**_kw(b, row), "metal": b["metal"], "cards": b["cards"]}
    if isinstance(top, int) and top > 0:
        kw["top"] = max(-(-top // 4096) * 4096, -(-at // 4096) * 4096)
    forced = fit_window(info, weight_bytes=size, free_bytes=b["budget"], forced=True, step=4096, **kw)
    loose = fit_window(info, weight_bytes=size, free_bytes=b["budget"], forced=False, step=4096, **kw)
    if forced is None:
        return _out("unknown", "the model's shape is not in its catalog row", at)
    gpu = forced if isinstance(forced, int) else None
    others = f" ({_gib(b['others'])} held by other programs)" if b["others"] else ""
    if isinstance(loose, int) and at <= loose:
        return _out("fits", f"on the GPU with room to spare: {at:,} of the {loose:,} it holds here{others}", at, gpu)
    if gpu and at <= gpu:
        return _out("tight", f"{at:,} stays on the GPU only with every layer forced on (up to {gpu:,}); Ollama's own "
                    f"fit moves layers to the CPU past {loose if isinstance(loose, int) else 0:,}{others}", at, gpu)
    need = need_bytes(info, weight_bytes=size, window=at, metal=b["metal"],
                      **{k: v for k, v in kw.items() if k not in ("metal", "cards", "top")}) or 0
    ram = (host_card or {}).get("ram_bytes")
    if isinstance(ram, int) and ram > 0 and need > b["budget"] + ram * RAM_SHARE:
        return _out("no", f"needs {_gib(need)} at {at:,}; the card has {_gib(b['budget'])} and the RAM "
                    f"{_gib(ram)}{others}", at, gpu)
    where = f"the GPU holds it up to {gpu:,}" if gpu else "not even its weights fit the GPU"
    return _out("spill", f"part runs on the CPU at {at:,} (slow): it needs {_gib(need)}, the card has "
                f"{_gib(b['budget'])}; {where}{others}", at, gpu)


def host_card_of(host, *, read: bool = False) -> Optional[dict]:
    """The hardware card of an Ollama host from the Ollama panel's cache (studio/ollama_hosts_view, any age);
    `read` reads it when none is cached (the 60 s cache, `/api/ps` and the local GPU tool; never under
    BRIDGE_TEST_NO_BACKGROUND_NET)."""
    if host is None:
        return None
    try:
        from halo_harness.studio import ollama_hosts_view as V
        with V._LOCK:
            hit = V._CACHE.get(("card", str(getattr(host, "url", ""))))
        if hit is not None:
            return hit[1]
        from halo_harness.config.paths import background_net_disabled
        return V.card_of(host) if read and not background_net_disabled() else None
    except Exception:
        return None


def meter_words(meter: Optional[dict]) -> str:
    return (meter or {}).get("level") or ""
