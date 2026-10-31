"""halo_harness.providers.model_card_measured -- Halo 3.3.6.0 R4: what the card
says from measurement and how Halo acts on it (plans/local-model-fit-brief.md
D4 item 17, G1, G7): the Measured block (providers/measured.py), the dialect
block "How Halo talks to this model" (providers/dialect.py) and the KV dial's
line in the fit block (providers/kv_dial.py), added to a local card by
model_card_quirks.with_quirks on every read (so a kept card stays current).

    with_measured(card, state_dir) -> the card, with `measured`, `dialect`, `kv_dial`, and
        blocks.measured [{text, mark}], blocks.dialect {fields, from, lines}, blocks.kv_dial {text, crash, action}

Only an Ollama card (an `ol:` model on a host) gets them; nothing here sends a request.
"""

from __future__ import annotations

import logging

log = logging.getLogger("bridge")


def _host_of(card: dict):
    try:
        from halo_harness.providers.ollama import resolve_ollama_host
        return resolve_ollama_host(card.get("host"))
    except Exception:
        return None


def with_measured(card: dict, state_dir) -> dict:
    if not isinstance(card, dict) or card.get("kind") != "ollama" or not card.get("host") or not card.get("name"):
        return card
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    blocks = card["blocks"] if isinstance(card.get("blocks"), dict) else None
    try:
        from halo_harness.providers.measured import lines, measured_for
        m = measured_for(card["host"], card["name"], state_dir=state_dir)
        card["measured"] = m
        if blocks is not None:
            blocks["measured"] = [{"text": t, "mark": "verified"} for t in lines(m)]
    except Exception:
        log.debug("model card: the measured facts could not be read", exc_info=True)
    try:
        from halo_harness.providers.dialect import record, view
        d = record(card["host"], card["name"], state_dir=state_dir)
        card["dialect"] = d
        if blocks is not None:
            blocks["dialect"] = view(d)
    except Exception:
        log.debug("model card: the dialect record could not be read", exc_info=True)
    try:
        from halo_harness.providers.kv_dial import dial_for
        host = _host_of(card)
        k = dial_for(host, card["name"], state_dir=state_dir) if host is not None else None
        card["kv_dial"] = k
        if blocks is not None:
            blocks["kv_dial"] = {key: k.get(key) for key in ("text", "crash", "action", "in_force")} if k and k.get("text") \
                else None
    except Exception:
        log.debug("model card: the KV dial could not be read", exc_info=True)
    return card
