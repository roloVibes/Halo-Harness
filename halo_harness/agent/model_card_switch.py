"""halo_harness.agent.model_card_switch -- Halo 3.3.5.0 R0b: the model card in
a `/model` switch (`agent/loop.py`'s `set_model` command).

    card_marker(session, ref, profile) -> (card, event | None)
        the card's `how` lines, before the switch step's line (a `turn_marker`
        of state "card", which the TUI, print mode and Studio's Live show)
    check_marker(session, card, prev_raw) -> event | None
        after the switch: the main-model line and the coder-lane offer
        (agent/main_model_check.py), a `turn_marker` of state "model-check"
        with `line`, `offer` and `offer_line`; the main session only

Nothing here sends a request: the catalog row is the one the switch step
reads (`model_switch._ollama_facts`, the short-TTL catalog), a cloud model's
card is built from its model profile.
"""

from __future__ import annotations

import logging
from typing import Optional

from halo_harness import events

log = logging.getLogger("bridge")


def _cloud_row(profile) -> dict:
    vision = bool(getattr(profile, "vision", False))
    return {"modalities_in": ["text", "image"] if vision else ["text"], "tools": True,
            "context_tokens": getattr(profile, "context_tokens", None)}


def card_for(session, ref, profile=None) -> Optional[dict]:
    from halo_harness.agent.model_switch import _ollama_facts
    from halo_harness.providers.model_card import card_of
    state_dir = getattr(session, "state_dir", None)
    provider = getattr(ref, "provider", "")
    if provider == "ollama":
        row, _profile, probe = _ollama_facts(session, ref)
        return card_of(ref, state_dir=state_dir, catalog=row, probe=probe)
    if provider in ("huggingface", "local") and (getattr(ref, "local", False) or getattr(ref, "mlx", False)
                                                 or provider == "local"):
        return card_of(ref, state_dir=state_dir)
    return card_of(ref, state_dir=state_dir, catalog=_cloud_row(profile))


def card_text(card: dict) -> str:
    from halo_harness.providers.model_card_words import what_words
    return f"{card.get('ref')}, {what_words(card)} -- how Halo calls it:\n" + "\n".join(
        f"  {line}" for line in card.get("how") or [])


def card_marker(session, ref, profile=None) -> "tuple[Optional[dict], object]":
    try:
        card = card_for(session, ref, profile)
    except Exception:
        log.debug("model_card_switch: no card for %s", getattr(ref, "raw", ref), exc_info=True)
        return None, None
    turn = getattr(session, "turn_count", 0) or 0
    return card, events.turn_marker("card", card_text(card), turn=turn, how=list(card.get("how") or []),
                                    ref=card.get("ref"))


def is_main(session) -> bool:
    return getattr(session, "role_name", None) in (None, "", "main") and not getattr(session, "_parent_model_raw", None)


def check_marker(session, card: Optional[dict], prev_raw: Optional[str] = None):
    if card is None or not is_main(session):
        return None
    if getattr(getattr(session, "model_ref", None), "raw", None) != card.get("ref"):
        return None  # the switch did not land
    try:
        from halo_harness.agent.main_model_check import check
        got = check(card["ref"], state_dir=getattr(session, "state_dir", None), card=card,
                    prefer=[prev_raw] if prev_raw else ())
    except Exception:
        log.debug("model_card_switch: the main-model check failed", exc_info=True)
        return None
    if got is None:
        return None
    session._main_model_check = got
    turn = getattr(session, "turn_count", 0) or 0
    return events.turn_marker("model-check", f"{got['line']}\n{got['offer_line']}", turn=turn, line=got["line"],
                              offer=got["offer"], offer_line=got["offer_line"])
