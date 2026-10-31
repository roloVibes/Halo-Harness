"""halo_harness.providers.model_card_quirks -- Halo 3.3.5.0 R4: what a model's
server log said about it, as card quirks (providers/model_card.py adds them).

    quirks_for(state_dir, model) -> [{kind, say}]
    with_quirks(card, state_dir) -> a copy of `card` with `quirks` and one `how` line per quirk, and (3.3.6.0 R3)
        `fit_evidence` (providers/fit_evidence.py: the model's last load on its host, as the log says it)

A model whose server logs "forcing full prompt re-processing due to lack of
cache data" (the steward's `no-prompt-cache` event: sliding-window or
hybrid/recurrent memory) re-reads the whole prompt every turn; the card says
it in one line and the Local tab's model row shows it.
"""

from __future__ import annotations

import logging

log = logging.getLogger("bridge")

QUIRKS = {"no-prompt-cache": "re-reads the whole prompt every turn (no prompt cache: the server log says so)"}
SINCE_S = 30 * 86400


_CACHE: dict = {}
CACHE_S = 10.0


def _events(state_dir) -> list:
    import time
    from halo_harness.ollama_steward.server_events import read_events
    key, now = str(state_dir), time.monotonic()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < CACHE_S:
        return hit[1]
    evs = [e for e in read_events(state_dir, since=SINCE_S) if e.get("kind") in QUIRKS]
    _CACHE[key] = (now, evs)
    return evs


def quirks_for(state_dir, model) -> list:
    if state_dir is None or not model:
        return []
    try:
        from halo_harness.ollama_steward.profiles import short_model
        want = short_model(model)
        seen = set()
        for ev in _events(state_dir):
            kind = ev.get("kind")
            if kind in QUIRKS and short_model(ev.get("model")) in (want, want.split(":")[0]):
                seen.add(kind)
        return [{"kind": k, "say": QUIRKS[k]} for k in QUIRKS if k in seen]
    except Exception:
        log.debug("model_card_quirks: the server events could not be read", exc_info=True)
        return []


def with_quirks(card: dict, state_dir) -> dict:
    if not isinstance(card, dict) or card.get("kind") == "cloud":
        return card
    from halo_harness.providers.fit_evidence import for_card  # 3.3.6.0 R3: the fit badge cites the log
    card["fit_evidence"] = for_card(card, state_dir)  # in place: read again on every call, so the kept card stays it
    if isinstance(card.get("blocks"), dict):
        from halo_harness.providers.model_card_blocks import fit_block
        card["blocks"]["fit"] = fit_block(card["fit_evidence"])
    quirks = quirks_for(state_dir, card.get("name"))
    if not quirks and not card.get("quirks"):
        return card
    how = [line for line in card.get("how") or [] if line not in QUIRKS.values()]
    return {**card, "quirks": quirks, "how": how + [q["say"] for q in quirks]}
