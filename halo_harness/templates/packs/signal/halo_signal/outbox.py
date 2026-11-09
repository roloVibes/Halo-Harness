"""halo_signal.outbox -- cards that could not be sent yet
(Halo 3.0.2.0). A permission, question, plan or approval card whose send
fails (signal-cli's link dropped with `-3`, the request timed out, or sending
is paused after a `-5`) is kept, in order, on the peer's `PeerRT.undelivered`
and sent again after the next `connected` notice or before the next message
to that phone. Plain relay text is not kept. The list is bounded; a card that
falls off it, or that the session stops waiting on (turn end, detach), leaves
an audit line (a hash, never the text)."""

from __future__ import annotations

MAX_UNDELIVERED = 12  # rendered messages kept per phone
CARD_TS = 40  # 3.3.13.1 (REMOTE-1): the sent timestamps kept per phone, the ones a reaction may answer


def sent_card(b, rt) -> None:
    """A card message went out: its sent timestamp (signal-cli's `send` answer) is one a reaction may answer."""
    ts = getattr(b, "last_ts", None)
    if isinstance(ts, int) and not isinstance(ts, bool):
        rt.card_ts = (rt.card_ts + [ts])[-CARD_TS:]


def send_card(b, aci: str, parts: list) -> None:
    """Send `parts` ((text, attachment, styles) tuples) in order; keep what fails."""
    rt = b.rt(aci)
    if not flush(b, rt):
        _keep(b, rt, parts)  # an older card is still stuck: keep the order
        return
    for i, part in enumerate(parts):
        if not b._send(aci, *part):
            _keep(b, rt, parts[i:])
            return
        sent_card(b, rt)


def flush(b, rt) -> bool:
    """Resend `rt`'s kept messages; True once none is left."""
    while rt.undelivered:
        if not b._send(rt.aci, *rt.undelivered[0]):
            return False
        sent_card(b, rt)
        rt.undelivered.pop(0)
        if not rt.undelivered:
            b.audit.record(rt.aci, 0, "card", "card", "redelivered")
    return True


def flush_all(b) -> None:
    for rt in list(b.rts.values()):
        if rt.undelivered:
            flush(b, rt)


def forget(b, rt, why: str) -> None:
    """The session no longer waits on the kept cards: drop them, with an audit line."""
    if rt.undelivered:
        rt.undelivered = []
        b.audit.record(rt.aci, 0, "card", "card", why)


def _keep(b, rt, parts: list) -> None:
    rt.undelivered.extend(parts)
    b.audit.record(rt.aci, 0, "card", "card", "undelivered")
    over = len(rt.undelivered) - MAX_UNDELIVERED
    if over > 0:
        del rt.undelivered[:over]
        b.audit.record(rt.aci, 0, "card", "card", "dropped_overflow")
