"""halo_signal.notes -- the notes the core gives every transport (ext.remote.notify), passed to each phone that asked
for their kind (`/notify on|off <kind>`; phones.py keeps the choice).

The core writes them: the attention queue's cards from any session or harness (`asks`, Studio's fleet watcher), a
supervisor goal that ended, parked or failed (`supervisor`), the Ollama steward's note that asks for attention
(`steward`). The bridge says it listens (`listen("signal")`, every LISTEN_EVERY_S) so the core writes them at all, and
reads the new ones every POLL_S. An `asks` note about the session a phone is attached to is skipped: that card already
reached it. A blocked phone gets nothing.

    Notes(bridge).tick()
    default_fleet_lines() -> [line]   `/fleet`: this harness's sessions, the fleet's members, what waits on you
"""

from __future__ import annotations

from halo_harness.ext import remote as R

POLL_S = 2.0
LISTEN_EVERY_S = 30.0
NAME = "signal"


class Notes:
    def __init__(self, bridge, *, read=None, listen=None) -> None:
        self.b = bridge
        self.read = read or R.notes
        self.listen = listen or R.listen
        self.cursor = ""
        self.next_poll = 0.0
        self.next_listen = 0.0

    def tick(self) -> int:
        now = self.b.clock.monotonic()
        if now >= self.next_listen:
            self.next_listen = now + LISTEN_EVERY_S
            try:
                self.listen(NAME)
            except Exception:
                pass
        if now < self.next_poll:
            return 0
        self.next_poll = now + POLL_S
        self.requests()
        try:
            rows, self.cursor = self.read(self.cursor)
        except Exception:
            return 0
        sent = 0
        for row in rows:
            sent += self.deliver(row)
        return sent

    def requests(self) -> int:
        """`/signal test` (ctl.test) leaves a request in the data folder's requests/; the bridge sends it."""
        import platform
        from halo_signal import files
        folder, n = files.path("requests"), 0
        for p in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            try:
                p.unlink()
            except OSError:
                continue
            to = [a for a, peer in self.b.pairing.peers().items() if not (peer or {}).get("blocked_until_reverified")]
            if not to and self.b.linked and self.b.own_aci:
                to = [self.b.own_aci]
            for aci in to:
                self.b.say(aci, f"A test message from Halo on {platform.node() or 'this computer'}: the bridge "
                                "reads and writes here.")
                n += 1
        return n

    def deliver(self, row: dict) -> int:
        kind, text = str(row.get("kind") or ""), str(row.get("text") or "")
        if not text.strip():
            return 0
        n = 0
        for aci, peer in self.b.pairing.peers().items():
            if not isinstance(peer, dict) or peer.get("blocked_until_reverified"):
                continue
            if kind not in self.b.phones.get(aci)["notify"]:
                continue
            rt = self.b.rts.get(aci)
            attached = (rt.entry or {}).get("session_id") if rt is not None else None
            if kind == "asks" and attached and row.get("session") == attached:
                continue
            self.b.say(aci, text, card=(kind == "asks"))
            n += 1
        return n


def default_fleet_lines() -> list:
    try:
        return R.fleet_lines()
    except Exception as e:  # the fleet's own trouble, in one line
        return [f"The fleet view is not available here: {type(e).__name__}"]
