"""halo_harness.fleet.push -- the attention queue on the owner's phone or chat (Halo 3.0.5.0 "Fleet" round R4; 3.3.13.0
R3: through the transports' seam, remote/notify.py, instead of the Signal bridge's own spool). While a transport
listens (a pack's bridge, the signal pack's for one) and `remote.enabled` is not false, every new attention row (any
harness, any session) becomes one `asks` note, the same card text the bridge sends for the session it is attached to
(remote/cards.py), prefixed with the harness name: `[kali@lab] Permission needed: Bash ...`. Otherwise nothing is
written.

Studio's fleet watcher (the hub) calls `spool` with the new rows; a local session a phone is attached to is skipped
(the transport already carries that card). The note's `session` is the row's session id, so a transport can skip a
session it is attached to as well.
"""

from __future__ import annotations

from typing import Optional

PUSH_KINDS = ("permission", "question", "plan", "approval", "fleet_ask", "waiting", "cap", "conflict",
              "goal_plan", "goal_gate", "goal_budget", "goal_ask", "goal_replan")  # 3.1.8.0 R1/R2: the supervisor's decisions


def _state(home):
    if home is not None:
        return home
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def listening(home=None) -> "list[str]":
    from halo_harness.remote.notify import listening as names
    return names(_state(home))


def ready(home=None) -> bool:
    """`remote.enabled` is not off and a transport listens: only then does a card leave the hub."""
    from halo_harness.remote.fleet_identity import remote_enabled
    return remote_enabled() and bool(listening(home))


def card(row: dict, ask: Optional[dict] = None) -> str:
    from halo_harness.remote import cards
    data = (ask or {}).get("data") if isinstance((ask or {}).get("data"), dict) else None
    who = row.get("harness_name") or "a harness"
    if row.get("agent") and row.get("agent") not in ("main", ""):
        who += f" · {row['agent']}"
    kind = row.get("kind")
    text = ""
    if data and kind == "permission":
        text = cards.permission_card(data)
    elif data and kind == "question":
        qs = cards.normalize_questions(data)
        text = cards.question_card(qs[0], 0, len(qs)) if qs else ""
    elif data and kind == "plan":
        text = cards.plan_card(data)
    elif data and kind == "approval":
        text = cards.approval_card(data)
    if not text:
        text = "\n".join(x for x in (row.get("what"), row.get("detail")) if x) + "\n(answer it in Studio: Fleet, Attention)"
    return f"[{who}] {text}"


def spool(home, rows: list, asks: Optional[dict] = None, now: Optional[float] = None) -> int:
    """One `asks` note per NEW attention row a transport should carry; the number written."""
    from halo_harness.remote.notify import notify
    n = 0
    for row in rows:
        if row.get("kind") not in PUSH_KINDS or (row.get("local") and row.get("remote_attached")):
            continue
        ask = (asks or {}).get((str(row.get("harness")), str(row.get("session_id")), str((row.get("target") or {}).get("request_id"))))
        if notify("asks", card(row, ask), source=str(row.get("id") or ""), session=str(row.get("session_id") or ""),
                  state_dir=_state(home)):
            n += 1
    return n
