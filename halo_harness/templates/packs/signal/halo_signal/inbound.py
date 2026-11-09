"""halo_signal.inbound -- an envelope from signal-cli, from the top: whose it is, whether it is answered, and what it
carries (a text, a long text, pictures, a PDF, a voice note, a reaction).

Order: a group message is dropped first (never a command, never a pairing); with a linked account only the owner's
own Note to Self counts. An untrusted-identity notification from a new phone while a pairing phrase is open queues
the trust of its key (pairing.note_untrusted; signal-cli then hands over the held message); a paired phone's is a
changed safety number (blocked until /signal reverify). A sender that is not paired: its text may redeem the open
phrase; otherwise it is never answered. A paired phone: blocked check, files taken, the signature when the phone is
set to signed, the rate limit, the read receipt, then routing.py. Nothing of a message is logged; the audit line is a
hash.
"""

from __future__ import annotations

from halo_signal import answers, routing, signing
from halo_signal.ratelimit import DROP_NOTIFY, OK

SIGNED_HINT = "This phone is set to signed messages: end each with ' #<counter>:<mac>' (the pack's README, Signing)."
NO_SECRET = ("This phone is set to signed messages but has no usable signing secret. On the computer: "
             "/signal sign off, or /signal sign on to make a new one.")
PAIRED = "Paired. Text me anything -- \"hello\" starts a session. /help lists what else I take."
SIGN_ANSWERS = {"unsigned": SIGNED_HINT, "bad_mac": "That signature did not match. " + SIGNED_HINT,
                 "stale": "That message is outside the allowed time window and its counter is now used; sign it "
                          "again with a higher counter.",
                 "replay": "That counter was already used; use a higher one."}


def on_envelope(b, item: dict) -> None:
    env = item.get("envelope") or {}
    aci, number, ts = env.get("sourceUuid"), env.get("sourceNumber"), env.get("timestamp")
    msg, atts, reaction = None, [], None
    if b.linked:
        sent = (env.get("syncMessage") or {}).get("sentMessage")
        if not isinstance(sent, dict) or sent.get("destinationUuid") != b.own_aci or sent.get("groupInfo"):
            return
        aci, msg, atts, reaction = b.own_aci, sent.get("message"), sent.get("attachments") or [], sent.get("reaction")
    elif env.get("dataMessage") is not None:
        dm = env["dataMessage"]
        if isinstance(dm, dict) and dm.get("groupInfo"):
            return b.on_group(dm["groupInfo"])
        if isinstance(dm, dict):
            msg, atts, reaction = dm.get("message"), dm.get("attachments") or [], dm.get("reaction")
    if not aci:
        return
    if item.get("exception"):
        if b.pairing.is_paired(aci):
            b.pairing.block(aci, b.safe_safety_number(aci))
        elif not b.pairing.note_untrusted(aci, number, b.safe_safety_number(aci)):
            b.pairing.note_stranger(aci, number)
        return
    if msg is None and not atts and not isinstance(reaction, dict):
        return  # typing, receipts, other sync: dropped without a trace
    peer = b.pairing.peer(aci)
    if peer is None:
        on_stranger(b, aci, number, msg or "", atts)
    elif isinstance(reaction, dict) and msg is None:
        on_reaction(b, peer, reaction)
    else:
        on_peer(b, peer, ts, msg or "", atts)


def on_stranger(b, aci: str, number, text: str, atts: list) -> None:
    b.transport.take_attachments(atts, False)
    res = b.pairing.redeem(aci, text, number)
    if res.status == "paired":
        b.say(aci, PAIRED)
        b.phones.set(aci, home=b.phones.get(aci)["home"])
        b.audit.record(aci, 0, "pairing-phrase", "pair", "paired")
    elif res.status in ("wrong", "dropped", "expired"):
        b.audit.record(aci, 0, "pairing-phrase", "pair", res.status)
    else:
        b.pairing.note_stranger(aci, number)


def on_reaction(b, peer: dict, reaction: dict) -> None:
    aci = peer["aci"]
    if peer.get("blocked_until_reverified") or reaction.get("isRemove") or peer.get("signed"):
        return  # a signed phone's reactions carry no signature: they are not answers
    if b.limiter.allow(aci) != OK:
        return
    done = answers.react(b, b.rt(aci), str(reaction.get("emoji") or ""), reaction.get("targetSentTimestamp"))
    b.audit.record(aci, 0, "reaction", "reaction", done or "ignored")


def refuse_bad(b, aci: str, text: str, reason: str, notice: str, counter: int = 0) -> None:
    verdict = b.bad_limiter.allow(aci)
    if verdict != OK:
        if verdict == DROP_NOTIFY:
            b.audit.record(aci, counter, text, "refused", "bad_rate_limited")
            b.say(aci, "Too many invalid messages; slow down. Further ones this minute are dropped.")
        return
    b.audit.record(aci, counter, text, "refused", reason)
    b.say(aci, notice)


def on_peer(b, peer: dict, ts, msg: str, atts: list) -> None:
    aci = peer["aci"]
    ok_peer = not peer.get("blocked_until_reverified")
    long_text, got = b.transport.take_attachments(atts, ok_peer, b.inbox_dir if ok_peer else None)
    text = long_text or msg
    if not ok_peer:
        b.audit.record(aci, 0, text, "refused", "blocked")
        return
    counter, shown = 0, text
    if peer.get("signed"):
        try:
            key = signing.secret_from_hex((peer.get("signing") or {}).get("secret_hex"))
        except ValueError:
            refuse_bad(b, aci, text, "no_secret", NO_SECRET)
            return
        v = signing.verify(key, (peer.get("signing") or {}).get("counter", 0), text, ts, b.clock.time(), b.window)
        if not v.ok:
            if v.reason == "stale":
                b.pairing.advance_counter(aci, v.counter)
            refuse_bad(b, aci, text, v.reason, SIGN_ANSWERS.get(v.reason, SIGNED_HINT), v.counter)
            return
        counter, shown = v.counter, v.text
    verdict = b.limiter.allow(aci)
    if verdict != OK:
        b.audit.record(aci, counter, shown, "refused", "rate_limited")
        if verdict == DROP_NOTIFY:
            b.say(aci, "Too many messages; slow down. Further ones this minute are dropped.")
        return
    if counter:
        b.pairing.advance_counter(aci, counter)
    try:
        if ts:
            b.transport.send_receipt(aci, ts)
    except Exception:
        pass
    kind, outcome = routing.route(b, b.rt(aci), shown, got)
    b.audit.record(aci, counter, shown, kind, outcome)
