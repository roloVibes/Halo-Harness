"""halo_harness.agent.eyes_offer -- Halo 3.3.6.0 R6: before an image reaches a model that cannot see it, the turn
says so in one line and offers the eyes (agent/loop.py's user-turn construction calls `run`; the Screenshot
tool's result carries `tool_lines`).

    sees(session) -> {value, truth, source}     the session model's vision fact (providers/vision_fact.py; a cloud
                                                model from its model profile), kept per model ref
    needs_offer(session) -> fact | None         False, or unknown on a local model; None: send the image
    visual_lane(session) -> {ref, role, cost} | None    the lineup's `visual` lane (roles.visual, else roles.eyes)
    describer(session) -> {ref, why} | None     a model that sees for the look-at-it sub-agent: the concierge when it
                                                sees, else models_auto.pick with the vision need
    choices(session) -> [{id, label, what, disabled?}]   lane / describe / send, each with what it does and costs
    ask(session, line, opts, turn_no) -> a generator of events (the card); returns the choice
    (agent/eyes_turn.py does what the choice says to the turn)

The choice: an image block's `eyes_choice` (Studio's buttons sent it with the steer), else the card (the TUI's
menu, Enter = the first; Studio's Live buttons: an `approval_request` with position "eyes"), else -- `-p`, no
UI, a sub-agent -- the visual lane when one is set, else the concierge's description when it sees, else the text
alone. "lane" switches this turn only (the turn's end switches back); "describe" asks the model that sees for a
description that lands in the turn as text (the log names who saw it); "send" sends the text, the image as its
path. Each is one rung of agent/degrade.py's ladder ("needs eyes"), logged like any other.
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Optional

from halo_harness import events

log = logging.getLogger("bridge")
CHOICES = ("lane", "describe", "send")
DESCRIBE_SYSTEM = ("You are the eyes for a coding session whose main model cannot see images. Describe each image "
                   "concretely and compactly: what it shows, every piece of text in it, anything actionable. These "
                   "words are all the main model will see of it.")


def _fact(value, truth, source) -> dict:
    return {"value": value, "truth": truth if value is not None else None, "source": source}


def is_local(ref) -> bool:
    from halo_harness.model import is_local_model_ref
    return bool(ref is not None and (is_local_model_ref(ref) or getattr(ref, "provider", "") == "local"))


def sees(session) -> dict:
    ref = getattr(session, "model_ref", None)
    raw = getattr(ref, "raw", "") or ""
    got = getattr(session, "_eyes_fact", None)
    if isinstance(got, tuple) and got[0] == raw:
        return got[1]
    profile_sees = bool(getattr(getattr(session, "model_profile", None), "vision", False))
    if is_local(ref):
        try:
            from halo_harness.agent.model_card_switch import card_for
            card = card_for(session, ref, getattr(session, "model_profile", None)) or {}
            f = _fact(card.get("vision"), card.get("vision_truth"), (card.get("sources") or {}).get("vision") or "")
        except Exception:
            f = _fact(None, None, "nothing says whether it reads images (no card)")
        if profile_sees and f["value"] is not True:
            f = _fact(True, "declared", "the model profile says it reads images")
    else:
        f = _fact(profile_sees, "declared", "the model profile (the catalog's modalities)")
    session._eyes_fact = (raw, f)
    return f


def needs_offer(session) -> Optional[dict]:
    f = sees(session)
    if f["value"] is True or (f["value"] is None and not is_local(getattr(session, "model_ref", None))):
        return None
    return f


def model_line(session, f: dict) -> str:
    raw = getattr(getattr(session, "model_ref", None), "raw", "this model")
    if f.get("value") is False:
        return f"{raw} cannot see images ({f.get('truth') or 'declared'}: {f.get('source')})"
    return f"nothing says whether {raw} can see images ({f.get('source') or 'no probe yet'})"


def _cost(session, raw: str) -> str:
    try:
        from halo_harness.model import parse_model_ref, resolve_model_profile
        ref = parse_model_ref(raw)
        if is_local(ref):
            from halo_harness.providers.placement import profile_for_ref
            p = profile_for_ref(ref, getattr(session, "state_dir", None)) or {}
            cold = (p.get("speed") or {}).get("cold_load_s")
            return f"local, no cost; loads {ref.model} if it is not loaded" + (f", ~{cold:.0f} s" if cold else "")
        from halo_harness.roles import _price_str
        price = _price_str(resolve_model_profile(ref, getattr(session, "state_dir", None), {}))
        return "price not known" if price == "n/a" else price
    except Exception:
        return "price not known"


def visual_lane(session) -> Optional[dict]:
    try:
        from halo_harness.roles import configured_role_table, role_value_parts
        table = configured_role_table()
    except Exception:
        return None
    me = getattr(getattr(session, "model_ref", None), "raw", "")
    for role in ("visual", "eyes"):
        raw = role_value_parts(table.get(role))[0] if table.get(role) is not None else None
        if raw and str(raw).strip().lower() not in ("inherit", "parent", "-") and raw != me:
            return {"ref": raw, "role": role, "cost": _cost(session, raw)}
    return None


def describer(session) -> Optional[dict]:
    try:
        from halo_harness.concierge import resolve_concierge
        got = resolve_concierge(session)
        if got is not None and getattr(got[1], "vision", False):
            return {"ref": got[0].raw, "why": "the concierge (roles.concierge) sees", "concierge": True}
    except Exception:
        pass
    try:
        from halo_harness.models_auto import pick
        p = pick(getattr(session, "state_dir", None), needs=["vision"], main_ref=getattr(session.model_ref, "raw", ""),
                 role="eyes")
        if not p.fallback and p.ref and p.ref != session.model_ref.raw:
            return {"ref": p.ref, "why": p.line()}
    except Exception:
        log.debug("eyes_offer: no pick", exc_info=True)
    return None


def choices(session) -> list:
    lane, eyes = visual_lane(session), describer(session)
    return [{"id": "lane", "label": f"this turn on the visual lane: {lane['ref']}" if lane else "no visual lane set",
             "what": (f"switches this turn to {lane['ref']} (roles.{lane['role']}), back after it; {lane['cost']}; writes "
                      "nothing" if lane else "set one with halo config set roles.visual <model that sees> (halo models --vision)"),
             "disabled": lane is None, "ref": (lane or {}).get("ref")},
            {"id": "describe", "label": f"let {eyes['ref']} describe it" if eyes else "no model that sees for a description",
             "what": (f"one call on {eyes['ref']} ({_cost(session, eyes['ref'])}) writes what the image shows into the turn "
                      "as text; the log names who saw it" if eyes else "the catalog has no model that sees"),
             "disabled": eyes is None, "ref": (eyes or {}).get("ref"), "concierge": bool((eyes or {}).get("concierge"))},
            {"id": "send", "label": "send the text without it", "what": "no extra call; the image rides as its path",
             "disabled": False}]


def default_choice(opts: list) -> str:
    """No one to ask: the visual lane when set, else the concierge's description when it sees, else the text."""
    by = {o["id"]: o for o in opts}
    if not by["lane"]["disabled"]:
        return "lane"
    return "describe" if not by["describe"]["disabled"] and by["describe"].get("concierge") else "send"


def ask(session, line: str, opts: list, turn_no: int):
    rid = f"eyes-{uuid.uuid4().hex[:8]}"
    session._approval_waiters[rid] = {"event": threading.Event(), "decision": None}
    first = next(o["id"] for o in opts if not o.get("disabled"))
    session._eyes_pending = {"id": rid, "line": line, "choices": opts, "default": first}
    yield events.Event("approval_request", {"id": rid, "position": "eyes", "text": line, "is_error": False,
                                            "choices": opts, "default": first}, turn=turn_no)
    try:
        answer = session._await_reply(session._approval_waiters, rid)
    finally:
        session._eyes_pending = None
    got = str((answer or {}).get("action") or "")
    return got if got in CHOICES else ("send" if answer is None else first)


def offer_for(raw: str, state_dir=None) -> dict:
    """What Studio's chip shows before the send, for a model ref (no Session: the caches only, no request).
    {sees, offer, line, choices}; `offer` False: the image rides as an image."""
    from types import SimpleNamespace
    from halo_harness.model import parse_model_ref, resolve_model_profile
    if state_dir is None:
        from halo_harness.config.paths import bridge_home
        state_dir = bridge_home()
    try:
        ref = parse_model_ref(raw)
        profile = resolve_model_profile(ref, state_dir, {})
    except Exception as e:
        return {"sees": _fact(None, None, f"no such model ({e})"), "offer": False, "line": "", "choices": []}
    s = SimpleNamespace(model_ref=ref, model_profile=profile, state_dir=state_dir, settings=None, agent_runtime=None,
                        interactive=False, agent_id=None)
    f = needs_offer(s)
    return {"sees": sees(s), "offer": f is not None, "line": model_line(s, f) if f else "",
            "choices": choices(s) if f else []}
