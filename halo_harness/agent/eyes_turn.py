"""halo_harness.agent.eyes_turn -- Halo 3.3.6.0 R6: what the eyes choice does to the turn that carries an image
(agent/eyes_offer.py says the line and gathers the choice; agent/loop.py's user-turn construction calls `run`).

    run(session, turn_no, images) -> a generator of events; returns {choice, send_images, line}
        choice None: the model sees (or a cloud model the catalog does not deny), the images ride as images
        "lane"      this turn switched to the visual lane (agent/model_switch.run_switch, why "eyes"); the turn's end
                    switches back (agent/loop.py `_restore_primary_model_after_turn`): the images ride
        "describe"  one call on a model that sees (Session.call_small_model with the images); its words land as an
                    `eyes_vision` snapshot, the log's meta `eyes` names who saw which files; the images ride as paths
        "send"      the text alone, the images as their paths (the old notice)
    tool_lines(session, path) -> the Screenshot tool's note and the three choices as lines (a tool result cannot
        ask: the model reads what each would do)
Each choice is the ladder's "eyes" rung (agent/degrade.eyes_rung): one marker line, kept with the turn's rungs.
"""

from __future__ import annotations

import logging

from halo_harness import events
from halo_harness.agent import eyes_offer as O

log = logging.getLogger("bridge")
WORDS = {"lane": "this turn on {ref} (the visual lane)", "describe": "{ref} describes the image into the turn",
         "send": "the text alone, the image as its path"}


def _routes(session) -> dict:
    return getattr(getattr(session, "agent_runtime", None), "routes", None) or {}


def _lane(session, raw: str):
    from halo_harness.agent.model_switch import run_switch
    from halo_harness.headless import _resolve_creds
    from halo_harness.model import parse_model_ref, resolve_model_profile
    try:
        target = parse_model_ref(raw, _routes(session))
        profile = resolve_model_profile(target, session.state_dir, _routes(session))
        creds = _resolve_creds(target, session.settings) or session.creds
        yield from run_switch(session, target, profile, creds, why="eyes")
        return getattr(session.model_ref, "raw", None) == target.raw
    except Exception:
        log.debug("eyes: the switch to %s failed", raw, exc_info=True)
        return False


def describe(session, raw: str, images: list) -> str:
    from halo_harness.agent.image_attach import path_mention_text
    from halo_harness.headless import _resolve_creds
    from halo_harness.model import parse_model_ref
    try:
        ref = parse_model_ref(raw, _routes(session))
        if _resolve_creds(ref, getattr(session, "settings", None)) is None:  # never the blind main model instead
            return ""
        text = session.call_small_model(system_text=O.DESCRIBE_SYSTEM, user_text="Describe these images for the main agent.",
                                        model_ref=ref, timeout_s=60.0, images=images, see=True)
    except Exception:
        log.debug("eyes: the description on %s failed", raw, exc_info=True)
        return ""
    if not (text or "").strip():
        return ""
    labels = ", ".join(path_mention_text(i) for i in images)
    return (f"[the eyes: {raw} looked at the image(s) for this turn -- the active model cannot see them]\n"
            f"{text.strip()}\n(attached as files: {labels})")


def run(session, turn_no: int, images):
    images = [i for i in images or [] if isinstance(i, dict) and i.get("type") == "image"]
    f = O.needs_offer(session) if images else None
    if f is None:
        return {"choice": None, "send_images": True, "line": ""}
    line = O.model_line(session, f)
    opts = O.choices(session)
    by = {o["id"]: o for o in opts}
    preset = next((i.get("eyes_choice") for i in images if i.get("eyes_choice") in O.CHOICES), None)
    how = ""
    if preset and not by[preset]["disabled"]:
        choice, how = preset, " (chosen with the image)"
    elif getattr(session, "interactive", False) and getattr(session, "agent_id", None) is None:
        choice = yield from O.ask(session, line, opts, turn_no)
    else:
        choice, how = O.default_choice(opts), " (no one to ask: the default)"
    if by.get(choice, {}).get("disabled"):
        choice = "send"
    out = {"choice": choice, "send_images": False, "line": line}
    ref = by[choice].get("ref") or ""
    if choice == "lane":
        if (yield from _lane(session, ref)):
            out["send_images"] = True
        else:
            choice, how = "send", f" (the switch to {ref} did not happen)"
    elif choice == "describe":
        text = describe(session, ref, images)
        if text:
            kind = "concierge_vision" if by["describe"].get("concierge") else "eyes_vision"
            session.log.append_snapshot([{"type": "text", "text": text}], kind=kind)
            session.log.append_meta(eyes={"seen_by": ref, "images": [i.get("image_path") or i.get("path") for i in images]})
        else:
            choice, how = "send", f" ({ref} gave no description)"
    out["choice"] = choice
    full = f"{line}: {WORDS[choice].format(ref=ref)}{how}"
    from halo_harness.agent.degrade import eyes_rung
    yield from eyes_rung(session, turn_no, choice, full)
    if choice == "send":
        yield events.notification(f"{getattr(session.model_ref, 'raw', 'this model')} does not take images; attached as a path")
    elif choice == "describe":
        who = "the concierge" if by["describe"].get("concierge") else ref
        yield events.notification(f"{who} described the image(s) -- the active model cannot see them")
    return out


def tool_lines(session, path: str) -> list:
    """The Screenshot tool's answer to a model that cannot see: the note and what each of the three would do."""
    f = O.sees(session) if session is not None else {"value": False, "truth": None, "source": "no session"}
    raw = getattr(getattr(session, "model_ref", None), "raw", "this model")
    out = [f"{raw} cannot see images: the file is at {path}" if f.get("value") is False else
           f"nothing says whether {raw} can see images: the file is at {path}"]
    if session is None:
        return out
    for o in O.choices(session):
        if o["id"] == "send":
            continue
        out.append(f"- {o['label']}: {o['what']}" + (" (ask the user to switch with /model)" if o["id"] == "lane" and not o["disabled"] else
                                                      " (an Agent call with that model and the file's path)" if o["id"] == "describe"
                                                      and not o["disabled"] else ""))
    out.append("- or go on without looking at it")
    return out
