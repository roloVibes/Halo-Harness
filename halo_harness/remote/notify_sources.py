"""halo_harness.remote.notify_sources -- what the supervisor passes to the transports each tick (Halo 3.3.13.0 R3;
remote/notify.py is the seam). The supervisor's own goal notes are written where a goal changes state
(supervise/queue.set_state); the attention queue's cards by Studio's fleet watcher (fleet/push.spool). This module
adds the Ollama steward's notes that ask for attention (`attention: true`, the same ones the attention queue
shows), read from its journal -- the steward itself is never changed for it.

    Steward(state_dir).tick() -> int   new attention notes since the last tick, each one `notify("steward", ...)`;
                                       the first tick only remembers what is there (no flood of old notes)
"""

from __future__ import annotations

WITHIN_S = 3600.0


class Steward:
    def __init__(self, state_dir) -> None:
        self.state_dir = state_dir
        self.seen: "set[str] | None" = None

    def _marked(self) -> list:
        from halo_harness.ollama_steward import notes
        return [r for r in notes.read(self.state_dir, since_s=WITHIN_S) if r.get("attention")
                and r.get("stage") in ("note", "change", "finding")]

    def tick(self) -> int:
        try:
            rows = self._marked()
        except Exception:
            return 0
        ids = {str(r.get("id") or r.get("at")) for r in rows}
        if self.seen is None:
            self.seen = ids
            return 0
        from halo_harness.ollama_steward.notes import first_line
        from halo_harness.remote.notify import listening, notify
        if not listening(self.state_dir):
            self.seen |= ids
            return 0
        n = 0
        for r in rows:
            rid = str(r.get("id") or r.get("at"))
            if rid in self.seen:
                continue
            self.seen.add(rid)
            more = [str(x) for x in (r.get("lines") or [])[1:3]]
            if notify("steward", "\n".join(["Steward: " + first_line(r)] + more), source=rid, state_dir=self.state_dir):
                n += 1
        return n
