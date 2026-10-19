"""halo_harness.fleet.push -- the attention queue on the phone (Halo 3.0.5.0
"Fleet" round R4). When the Signal bridge is ENABLED (`remote.enabled`),
RUNNING and PAIRED with at least one phone, every new attention row (any
harness, any session) goes to the phone as the same card the bridge already
sends for the session it is attached to (remote/bridge_cards.py), prefixed
with the harness name: `[kali@lab] Permission needed: Bash ...`. Otherwise
nothing is written and nothing is sent.

The hub (Studio's fleet watcher) writes one small file per card into
`<home>/remote/fleet-push/` (0600); the bridge process drains it on its own
loop (`drain`, called from remote/bridge.py) and sends each card to every
paired phone that is not blocked. A card older than KEEP_S is dropped
unsent, so a bridge that starts late never floods the phone. A local session
a phone is attached to is skipped: the bridge already sent that card.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

SPOOL = "fleet-push"
KEEP_S = 600.0
MAX_FILES = 200
PUSH_KINDS = ("permission", "question", "plan", "approval", "fleet_ask", "waiting", "cap", "conflict")


def _remote(home) -> Path:
    if home is not None:
        return Path(home) / "remote"
    from halo_harness.config.paths import bridge_home
    return bridge_home() / "remote"


def paired(home=None) -> bool:
    try:
        data = json.loads((_remote(home) / "peers.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    peers = data.get("peers") if isinstance(data, dict) else None
    return isinstance(peers, dict) and any(isinstance(p, dict) and not p.get("blocked_until_reverified") for p in peers.values())


def ready(home=None) -> bool:
    """Enabled, running and paired: only then does a card leave the hub."""
    from halo_harness.remote import bridge_state
    from halo_harness.remote.fleet_identity import remote_enabled
    if not remote_enabled() or not paired(home):
        return False
    return bool(bridge_state.read(_remote(home) / "bridge.json").get("running"))


def card(row: dict, ask: Optional[dict] = None) -> str:
    from halo_harness.remote import bridge_cards as cards
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
    """Write the cards for `rows` (the NEW attention rows); the number written."""
    from halo_harness.privateio import write_private_atomic
    folder = _remote(home) / SPOOL
    n = 0
    now = now or time.time()
    for row in rows:
        if row.get("kind") not in PUSH_KINDS or (row.get("local") and row.get("remote_attached")):
            continue
        ask = (asks or {}).get((str(row.get("harness")), str(row.get("session_id")), str((row.get("target") or {}).get("request_id"))))
        try:
            folder.mkdir(parents=True, exist_ok=True)
            name = f"{int(now * 1000)}-{n:03d}.json"
            write_private_atomic(folder / name, json.dumps({"id": row["id"], "created": now, "text": card(row, ask)}))
            n += 1
        except OSError:
            break
    return n


def drain(bridge, folder: Optional[Path] = None, now: Optional[float] = None) -> int:
    """The bridge's side: send every waiting card to every paired phone; the number of cards sent."""
    folder = Path(folder) if folder is not None else Path(bridge.pairing.dir) / SPOOL
    if not folder.is_dir():
        return 0
    now = now or time.time()
    sent = 0
    for f in sorted(folder.glob("*.json"))[:MAX_FILES]:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            doc = {}
        try:
            f.unlink()
        except OSError:
            continue
        if not isinstance(doc, dict) or not doc.get("text") or now - float(doc.get("created") or 0) > KEEP_S:
            continue
        for aci, peer in bridge.pairing.peers().items():
            if isinstance(peer, dict) and not peer.get("blocked_until_reverified"):
                bridge.say(aci, str(doc["text"]), card=True)
        sent += 1
    return sent
