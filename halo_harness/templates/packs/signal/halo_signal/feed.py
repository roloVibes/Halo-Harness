"""halo_signal.feed -- the attached session's events turned into the phone's side of the conversation.

A turn the phone started (its `user_message` says `via: signal` and this phone) is answered in full: the paragraphs
as they complete (relay.py), its cards, its errors, the closing line. A turn started elsewhere (the keyboard, Studio)
reaches the phone while it is `loud` (the default); while it is `quiet` only what `/notify` names arrives: `asks`
(its cards), `errors`, `turn_done` (one line when it ends). A sub-agent's text and turn_done belong to its parent's
tool call and are not relayed; a sub-agent's card is, tagged.
"""

from __future__ import annotations

from halo_harness.ext import remote as R

from halo_signal import outbox
from halo_signal.relay import Relay, closing_line
from halo_signal.session import call, label, one_line

CHILD_CARDS = ("permission_request", "question", "plan_review", "approval_request")


def _relaying(rt) -> bool:
    return rt.mine or rt.verbosity == "loud"


def _wants(b, rt, kind: str) -> bool:
    return _relaying(rt) or kind in b.phones.get(rt.aci)["notify"]


def _relay(b, rt) -> Relay:
    if rt.relay is None:
        rt.relay = Relay(clock=b.clock.monotonic)
    return rt.relay


def send_paragraphs(b, rt, paras: list) -> None:
    for p in paras:
        b.say(rt.aci, p, markdown=True)
    if paras:
        _relay(b, rt).touched()


def on_feed(b, rt, frame: dict) -> None:
    ev, data = frame.get("event"), frame.get("data") or {}
    aci, child = rt.aci, frame.get("agent_id")
    if child and ev not in CHILD_CARDS:
        return
    tag = f"[sub-agent {str(child)[:8]}] " if child else ""
    if ev == "user_message":
        rt.relay = Relay(clock=b.clock.monotonic)
        rt.mine = data.get("via") == "signal" and data.get("by") == aci[:8]
        if _relaying(rt):
            b.transport.typing.start(aci)
    elif ev == "message_start" and _relaying(rt):
        b.transport.typing.start(aci)
    elif ev == "text_chunk":
        paras = _relay(b, rt).feed(str(data.get("text") or ""))
        if _relaying(rt):
            send_paragraphs(b, rt, paras)
    elif ev == "tool_use_ready":
        _relay(b, rt).tool(str(data.get("name") or ""), data.get("input"))
    elif ev in CHILD_CARDS:
        _card(b, rt, ev, data, tag)
    elif ev == "error" and _wants(b, rt, "errors"):
        b.say(aci, "Error: " + one_line(data.get("message"), 600))
    elif ev == "turn_done":
        turn_done(b, rt)


def _card(b, rt, ev: str, data: dict, tag: str) -> None:
    cards = R.cards
    if not _wants(b, rt, "asks"):
        return
    if ev == "permission_request":
        rt.permission.append({"id": data.get("id")})
        for i, part in enumerate(cards.permission_messages(data)):
            b.say(rt.aci, (tag if i == 0 else "") + part, card=True)
    elif ev == "question":
        qs = cards.normalize_questions(data)
        if qs:
            rt.question = {"id": data.get("id"), "questions": qs, "idx": 0, "answers": {}}
            b.say(rt.aci, tag + cards.question_card(qs[0], 0, len(qs)), card=True)
    elif ev == "plan_review":
        rt.plan = {"id": data.get("id")}
        b.say(rt.aci, tag + cards.plan_card(data), markdown=True, card=True)
    elif ev == "approval_request":
        rt.approval = {"id": data.get("id")}
        b.say(rt.aci, tag + cards.approval_card(data), card=True)
    _relay(b, rt).touched()


def turn_done(b, rt) -> None:
    aci, relay = rt.aci, _relay(b, rt)
    b.transport.typing.stop(aci)
    rest = relay.flush()
    rt.permission, rt.question, rt.plan, rt.approval, rt.held = [], None, None, None, None
    outbox.forget(b, rt, "dropped_turn_done")
    if _relaying(rt):
        send_paragraphs(b, rt, rest)
        if relay.held:
            b.say(aci, f"The answer goes on for {len(relay.held)} more paragraph(s); the whole of it is attached as "
                       "reply.txt.", attachment_text="\n\n".join(relay.all))
        if relay.worked or not relay.all:
            st = call(b, rt, "status")
            b.say(aci, closing_line(relay, st.get("result") or {}) if relay.worked else "Done (no text in the reply).")
    elif "turn_done" in b.phones.get(aci)["notify"] and rt.entry is not None:
        first = one_line((relay.all or ["(no text)"])[0], 160)
        b.say(aci, f"Turn done in {label(rt.entry)}: {first}")
    rt.relay, rt.mine = None, False


def tick(b, now_rts) -> None:
    """The bridge's tick: a status line for each phone whose own turn has been silent for STATUS_S seconds."""
    for rt in now_rts:
        relay = rt.relay
        if relay is None or rt.client is None or not rt.mine or not relay.status_due():
            continue
        b.say(rt.aci, f"still working: {relay.doing()}")
        relay.touched()
