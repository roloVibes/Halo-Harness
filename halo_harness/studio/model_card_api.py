"""halo_harness.studio.model_card_api -- Halo 3.3.5.0 R0b: the model card in
Studio (providers/model_card.py builds it, providers/fit_meter.py rates it).

    view(card, meter)            what a picker row carries: {card: {chips, how,
                                 fit_for, fit_why, purpose, thinks, tools,
                                 vision, kind, window {tokens, source}}, fit:
                                 {level, at_window, gpu_window, why}}
    row_view(ref, row, ...)      the same for a catalog row (`model_rows`)

    GET  models/card?ref=        {card, fit, check: {line, offer, offer_line} | null}
    POST models/lane {ref}       the offer accepted: the lineup written and
                                 active (the `halo teams apply` path), `model`
                                 set to the orchestrator; answers the lines
    GET  models/effort?ref=      {kind, options, word, choice}: what effort does
                                 on THIS model (providers/effort_on.py)
    POST models/think {ref, value}  `models.think[ref]` (on / off / default;
                                 low / medium / high on gpt-oss); answers the
                                 new word. A value of "" clears it.

Reading a card opens no connection: the Ollama catalog is the one this
process cached and the host card the Ollama panel's cache (read only when
the caller is not the cached read, `read_hardware`).
"""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("bridge")


def view(card: dict, meter: Optional[dict]) -> dict:
    from halo_harness.providers.model_card_words import chips
    w = card.get("window") or {}
    return {"card": {"chips": chips(card), "how": list(card.get("how") or []), "fit_for": dict(card.get("fit_for") or {}),
                     "fit_why": dict(card.get("fit_why") or {}), "purpose": card.get("purpose"),
                     "thinks": card.get("thinks"), "tools": card.get("tools"), "vision": card.get("vision"),
                     "vision_truth": card.get("vision_truth"),  # 3.3.6.0 R6: True | False | None, its truth
                     "kind": card.get("kind"), "embedding_only": bool(card.get("embedding_only")),
                     "window": {"tokens": w.get("tokens"), "source": w.get("source")},
                     "quirks": list(card.get("quirks") or []), "blocks": card.get("blocks") or {},  # 3.3.6.0 R1
                     "fit_source": dict(card.get("fit_source") or {}), "system_role": card.get("system_role"),
                     "speed": card.get("speed"), "probe": _probe_view(card),
                     "sources": dict(card.get("sources") or {}), "params": card.get("params"),  # 3.3.6.0 R2: the truths
                     "speed_chip": _speed_chip(card), "kv_dial": card.get("kv_dial"),  # 3.3.6.0 R4: measured, the dial
                     "dialect": card.get("dialect"), "speed_card": card.get("speed_card")},  # 3.3.6.0 R5: the bench
            "fit": dict(meter or {"level": "unknown", "at_window": None, "gpu_window": None, "why": ""})}


def _speed_chip(card: dict) -> str:
    from halo_harness.providers.measured import speed_chip
    return speed_chip(card.get("measured"))


def _probe_view(card: dict):
    p = card.get("profile")
    if not p:
        return None
    from halo_harness.providers.battery_profile import date_of, summary_line
    return {"date": date_of(p), "at": p.get("probed_at"), "line": summary_line(p), "agentic_ready": p.get("agentic_ready"),
            "interactive": p.get("interactive"), "quirks": list(p.get("quirks") or []), "sits": p.get("sits"),
            "window": p.get("window"), "stale": p.get("probe_set") != _probe_set(),
            "tool_call_accuracy": p.get("tool_call_accuracy"), "tool_call_why": p.get("tool_call_why")}


def _probe_set() -> str:
    from halo_harness.providers.battery_probes import PROBE_SET
    return PROBE_SET


def _host_for(ref_raw: str):
    from halo_harness.providers.model_card import _ollama_host, parse_ref
    ref = parse_ref(ref_raw)
    return _ollama_host(ref, None) if ref.provider == "ollama" else None


def row_view(ref_raw: str, row: Optional[dict], state_dir, *, read_hardware: bool = False, host_cards=None) -> dict:
    """`view` for one catalog row; `host_cards` ({url: card}) is the caller's per-call memo."""
    from halo_harness.providers.fit_meter import fit_meter, host_card_of
    from halo_harness.providers.model_card import card_of
    try:
        host = _host_for(ref_raw) if ref_raw.startswith("ol:") else None
        host_card = None
        if host is not None:
            memo = host_cards if host_cards is not None else {}
            if host.url not in memo:
                memo[host.url] = host_card_of(host, read=read_hardware)
            host_card = memo[host.url]
        card = card_of(ref_raw, state_dir=state_dir, catalog=None if host is not None else row, host=host,
                       host_card=host_card)
        return view(card, fit_meter(card, host_card))
    except Exception:
        log.debug("model_card_api: no card for %s", ref_raw, exc_info=True)
        return {}


def panel_view(model: str, host, row: Optional[dict], host_card) -> dict:
    """`view` for a model row of the Ollama panel (studio/ollama_hosts_view.py), its host card in hand."""
    if host is None or not row:
        return {}
    try:
        from halo_harness.providers.fit_meter import fit_meter
        from halo_harness.providers.model_card import card_of
        card = card_of(f"ol:{model}@{host.name}", catalog=row, host=host, host_card=host_card)
        return view(card, fit_meter(card, host_card, row=row))
    except Exception:
        log.debug("model_card_api: no card for %s", model, exc_info=True)
        return {}


def get_models_card(req):
    ref = str(req.query.get("ref") or "").strip()
    if not ref:
        return 422, {"error": "say which model: ?ref=ol:qwen3-coder:30b", "problems": ["ref is required"]}
    from halo_harness.agent.main_model_check import check
    from halo_harness.model_card_cli import card_and_meter
    from halo_harness.providers.model_card_words import card_lines
    card, meter = card_and_meter(ref, req.state_dir, read_hardware=False, cached=True)  # opens no connection
    try:
        got = check(ref, state_dir=req.state_dir, card=card)
    except Exception:
        log.debug("model_card_api: the main-model check failed", exc_info=True)
        got = None
    return 200, {**view(card, meter), "ref": ref, "lines": card_lines(card, meter),
                 "check": {k: got[k] for k in ("line", "offer", "offer_line")} if got else None}


def post_models_lane(req):
    ref = str((req.body or {}).get("ref") or "").strip()
    if not ref:
        return 422, {"error": 'say which model: {"ref": "ol:qwen3-coder:30b"}', "problems": ["ref is required"]}
    from halo_harness.agent.main_model_check import accept, check
    got = check(ref, state_dir=req.state_dir)
    if got is None:
        return 409, {"error": f"{ref} can orchestrate here: no lineup is needed", "problems": []}
    if not got.get("offer"):
        return 409, {"error": got["offer_line"], "problems": [got["line"]]}
    offer = got["offer"]
    ok, lines = accept(offer, cwd=req.cwd, state_dir=req.state_dir)
    if not ok:
        return 422, {"error": lines[0] if lines else "the lineup was not written", "problems": lines}
    from halo_harness.theme import set_config_value
    set_config_value("model", offer["orchestrator"])
    return 200, {"ok": True, "lineup": offer["lineup"], "orchestrator": offer["orchestrator"], "coder": offer["coder"],
                 "lines": [lines[0], f"model = {offer['orchestrator']} (the main agent); {ref} is the coder lane"]}


def _effort(ref: str) -> dict:
    from halo_harness.providers.effort_on import LEVELS, effort_on, think_choice_for
    from halo_harness.providers.model_card import parse_ref
    r = parse_ref(ref)
    row = None
    if r.provider == "ollama":
        from halo_harness.providers.model_card import card_of
        card = card_of(ref)
        row = {"capabilities": ["completion"] + (["thinking"] if card.get("thinks") != "no" else [])}
    choice = think_choice_for(ref)
    got = effort_on(r, row, think_choice=choice, explicit=False)
    if got["kind"] == "levels":
        return {**got, "options": list(LEVELS), "choice": None}
    return {**got, "choice": choice}


def get_models_effort(req):
    ref = str(req.query.get("ref") or "").strip()
    if not ref:
        return 422, {"error": "say which model: ?ref=...", "problems": ["ref is required"]}
    return 200, {"ref": ref, **_effort(ref)}


def post_models_think(req):
    body = req.body or {}
    ref, value = str(body.get("ref") or "").strip(), str(body.get("value") or "").strip().lower()
    if not ref:
        return 422, {"error": 'say which model: {"ref": ..., "value": "on"}', "problems": ["ref is required"]}
    now = _effort(ref)
    if value and value not in now["options"]:
        return 422, {"error": f"{ref} takes {', '.join(now['options']) or 'no think setting'}", "problems": [value]}
    from halo_harness.providers.effort_on import set_think_choice
    set_think_choice(ref, value or None)
    return 200, {"ref": ref, **_effort(ref)}


ROUTES: list = [
    ("GET", r"^models/card$", get_models_card),
    ("POST", r"^models/lane$", post_models_lane),
    ("GET", r"^models/effort$", get_models_effort),
    ("POST", r"^models/think$", post_models_think),
]
