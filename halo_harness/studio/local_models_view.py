"""halo_harness.studio.local_models_view -- Halo 3.3.5.0 R1: the Local tab's
Models page, every installed model per host with its card (providers/
model_card.py through studio/model_card_api.panel_view), the fit meter, the
roles it can hold, the steward profile, what is loaded, and its rank for each
intent (the third of Local's five ideas: intents, not model names).

    models(state_dir, host="") -> {hosts: [{name, kind, url, models: [row]}], intents [{id, title, why}], at}
    row {model, ref, card, fit, profile, loaded, size, intent {id: score | None}}

An intent's score orders the rows (higher first; None = not for that intent):
the card's purpose and `fit_for` decide the band, the fit meter the place in it.
"""

from __future__ import annotations

import time
from typing import Optional

INTENTS = (
    ("code", "Code", "coding models first, then instruct models that can call tools; each band by how well it fits here"),
    ("chat", "Chat", "instruct models first, then reasoning ones, then coders; each band by how well it fits here"),
    ("long", "Read long documents", "the largest window this card runs first; a tight fit after a clean one"),
    ("images", "Look at images", "only models that see (vision on the card); each by how well it fits here"),
    ("embed", "Embed", "only embedding models; each by how well it fits here"),
)
FIT_SCORE = {"fits": 4, "tight": 3, "unknown": 2, "spill": 1, "cloud": 2, "no": 0}
READERS: dict = {}  # "hf_models": fn(server) -> [model ids] (the tests' seam)
_HF: dict = {}
HF_TTL_S = 60.0


def intent_scores(card: dict, fit: dict) -> dict:
    c = card or {}
    purpose, emb = c.get("purpose") or "unknown", bool(c.get("embedding_only")) or c.get("purpose") == "embedding"
    tools = c.get("tools") not in ("none", "no", False)
    f = FIT_SCORE.get((fit or {}).get("level") or "unknown", 2)
    win = int(((c.get("window") or {}).get("tokens")) or 0)
    band = None if emb else {"coder": 3, "instruct": 2 if tools else 1, "reasoning": 1}.get(purpose, 1 if tools else 0)
    chat = None if emb else {"instruct": 3, "reasoning": 2, "coder": 1}.get(purpose, 1)
    return {"code": None if band is None else band * 10 + f, "chat": None if chat is None else chat * 10 + f,
            "long": None if emb else round(win / 1024) * 10 + f, "images": (10 + f) if c.get("vision") and not emb else None,
            "embed": (10 + f) if emb else None}


def _hf_models(server) -> list:
    if "hf_models" in READERS:
        return list(READERS["hf_models"](server) or [])
    from halo_harness.config.paths import background_net_disabled
    if background_net_disabled():
        return []
    hit = _HF.get(server.url)
    if hit and time.monotonic() - hit[0] < HF_TTL_S:
        return hit[1]
    try:
        from halo_harness.providers.huggingface_local_probe import probe_models_endpoint
        got = probe_models_endpoint(server.url, name=server.name, api_key=getattr(server, "api_key", None))
        ids = list(getattr(got, "model_ids", ()) or ())
    except Exception:
        ids = []
    _HF[server.url] = (time.monotonic(), ids)
    return ids


def _row(model: str, ref: str, view: dict, profile, loaded, size) -> dict:
    card, fit = view.get("card") or {}, view.get("fit") or {"level": "unknown"}
    keep = ("num_ctx", "num_predict", "keep_alive", "by", "note") if profile else ()
    return {"model": model, "ref": ref, "card": card, "fit": fit, "size": size,
            "profile": {k: profile.get(k) for k in keep} if profile else None, "loaded": loaded,
            "intent": intent_scores(card, fit)}


def _ollama_rows(h) -> list:
    from halo_harness.ollama_steward.profiles import all_profiles, key_for, short_model
    from halo_harness.studio.model_card_api import panel_view
    from halo_harness.studio.ollama_hosts_view import card_of, catalog_of
    card = card_of(h)
    loaded = {short_model(x.get("model")): x for x in (card or {}).get("loaded") or []}
    profiles = all_profiles()
    rows = []
    for r in catalog_of(h).get("models") or []:
        if not isinstance(r, dict):
            continue
        m = short_model(r.get("model") or r.get("name"))
        ld = loaded.get(m)
        rows.append(_row(m, f"ol:{m}@{h.name}", panel_view(m, h, r, card), profiles.get(key_for(h.name, m)),
                         {"size_vram": ld.get("size_vram"), "size": ld.get("size"), "expires": ld.get("expires"),
                          "context_length": ld.get("context_length")} if ld else None, r.get("size")))
    return rows


def _hf_rows(s, state_dir) -> list:
    from halo_harness.studio.model_card_api import row_view
    out = []
    for mid in _hf_models(s):
        ref = f"hf:local/{mid}@{s.name}"
        out.append(_row(mid, ref, row_view(ref, {"id": mid}, state_dir) or {}, None, None, None))
    return out


def models(state_dir, host: str = "", *, now: Optional[float] = None) -> dict:
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.studio.local_hosts_view import kind_of
    from halo_harness.studio.ollama_hosts_view import local_servers
    out = []
    for h in resolve_ollama_hosts():
        if host and h.name.lower() != host.lower():
            continue
        out.append({"name": h.name, "kind": kind_of(h), "url": h.url, "models": _ollama_rows(h)})
    for s in local_servers():
        if host and s.name.lower() != host.lower():
            continue
        out.append({"name": s.name, "kind": "local server (OpenAI dialect)", "url": s.url, "models": _hf_rows(s, state_dir)})
    return {"hosts": out, "intents": [{"id": i, "title": t, "why": w} for i, t, w in INTENTS],
            "at": time.time() if now is None else now}


def rank(rows: list, intent: str) -> list:
    """The rows for `intent`, best first (a row with no score for it left out)."""
    scored = [r for r in rows if (r.get("intent") or {}).get(intent) is not None]
    return sorted(scored, key=lambda r: (-r["intent"][intent], r["model"]))


from halo_harness.studio.local_uses import uses_of  # noqa: E402,F401  (3.3.5.0 R3: what uses a model, the delete card)
