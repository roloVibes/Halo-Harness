"""halo_harness.providers.kv_dial -- Halo 3.3.6.0 R4: the KV-quantisation dial
(plans/local-model-fit-brief.md Part G7): the window this model gets on this card
at each KV cache type, the quality caveat, and the crash note when this host's
crash fingerprints implicate flash attention with a q8_0 KV cache.

    dial_for(host, model, *, state_dir=None, card=None, row=None) -> None | {
        rows: [{kv, window}], in_force, window_in_force, text, crash, crashes, action}
    text   "f16 KV -> 32k, q8_0 KV -> 64k on this card (q8_0 KV: a small quality cost)"
    crash  "4 crashes here with FA + q8_0 KV -- see `halo ollama crashes --why`" | ""
    action the host-side half, stated: "OLLAMA_KV_CACHE_TYPE=q8_0 (with OLLAMA_FLASH_ATTENTION=1), then restart
           Ollama on <host>" -- Halo never sets them

The windows are ollama_steward/fit.py's `model_window_on_card` with the card's
`server.kv_cache_type` set to each type (fit.card_budget's `bpe`: f16 2.0, q8_0
1.0625, q4_0 0.5625 bytes per element, knowledge/memory.md); q4_0 is listed only
when it buys a larger window than q8_0. The Halo-side half needs nothing new: the
window a profile or the fit picks is already the one for the KV type in force
(card_budget reads it), which `window_in_force` shows. `card` is the host's
hardware card (the Ollama panel's cache) and `row` the model's catalog row with
its `model_info`; both are read from the caches when not given. No request.
"""

from __future__ import annotations

from typing import Optional

TYPES = ("f16", "q8_0", "q4_0")
CAVEAT = {"q8_0": "q8_0 KV: a small quality cost", "q4_0": "q4_0 KV: a larger quality cost"}
STEP = 4096


def _k(n: int) -> str:
    return f"{n // 1024}k" if n >= 1024 else str(n)


def _card_and_row(host, model: str, card, row):
    if card is None:
        from halo_harness.providers.fit_meter import host_card_of
        card = host_card_of(host, read=False)
    if row is None:
        from halo_harness.providers.local_models_cached import cached_catalog
        from halo_harness.providers.model_card import _row_for
        row = _row_for(cached_catalog(host), model) if host is not None else None
    return card, row


def crashes_with_fa_q8(state_dir, host_name: str) -> int:
    """How many crashes this host's fingerprints count with flash attention on and a q8_0 KV cache."""
    if state_dir is None or not host_name:
        return 0
    from halo_harness.ollama_steward.fingerprints import read
    n = 0
    for fp in read(state_dir, host=host_name):
        fa = str(fp.get("flash_attention")).lower() in ("true", "1", "on", "enabled")
        if fa and str(fp.get("kv_cache_type") or "").lower() == "q8_0":
            n += int(fp.get("count") or 1)
    return n


def dial_for(host, model: str, *, state_dir=None, card=None, row=None) -> Optional[dict]:
    from halo_harness.ollama_steward.fit import model_window_on_card
    card, row = _card_and_row(host, model, card, row)
    if not card or not isinstance((row or {}).get("size"), int) or not (row or {}).get("model_info"):
        return None
    server = dict(card.get("server") or {})
    in_force = str(server.get("kv_cache_type") or "f16").lower()
    rows = []
    for kv in TYPES:
        w = model_window_on_card({**card, "server": {**server, "kv_cache_type": kv}}, row, step=STEP)
        if isinstance(w, int) and w > 0:
            rows.append({"kv": kv, "window": w})
    if not rows:
        return None
    by = {r["kv"]: r["window"] for r in rows}
    if "q4_0" in by and by["q4_0"] <= by.get("q8_0", 0):
        rows = [r for r in rows if r["kv"] != "q4_0"]
    shown = [r for r in rows if r["kv"] in ("f16", "q8_0")] + [r for r in rows if r["kv"] == "q4_0"]
    caveats = [CAVEAT[r["kv"]] for r in shown if r["kv"] in CAVEAT]
    text = ", ".join(f"{r['kv']} KV -> {_k(r['window'])}" for r in shown) + " on this card"
    text += f" ({'; '.join(caveats)})" if caveats else ""
    name = getattr(host, "name", host) or "the host"
    n = crashes_with_fa_q8(state_dir, str(name))
    crash = f"{n} crash{'es' if n != 1 else ''} here with FA + q8_0 KV -- see `halo ollama crashes --why`" if n else ""
    fa = str(server.get("flash_attention")).lower() in ("true", "1", "on", "enabled")
    if n and in_force == "q8_0":
        action = (f"OLLAMA_KV_CACHE_TYPE=f16 (or OLLAMA_FLASH_ATTENTION=0), then restart Ollama on {name}: "
                  "Halo never sets them")
    elif in_force == "f16" and by.get("q8_0", 0) > by.get("f16", 0):
        action = (f"OLLAMA_KV_CACHE_TYPE=q8_0" + ("" if fa else " with OLLAMA_FLASH_ATTENTION=1 (q8_0 needs it)")
                  + f", then restart Ollama on {name}: Halo never sets them")
    else:
        action = ""
    return {"rows": shown, "in_force": in_force, "window_in_force": model_window_on_card(card, row, step=STEP),
            "text": text, "crash": crash, "crashes": n, "action": action, "flash_attention": fa}
