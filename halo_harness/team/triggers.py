"""halo_harness.team.triggers -- what starts a stage.

* `manual`              -- `halo team run <stage>` (or Studio's Run);
* `stage_done:<stage>`  -- that stage reached done and its gate (if any) was
  answered accept: the runner queues the stage right then;
* `block_change:<block>` -- a `BlockWatch` (agents_schedule.TeamScheduler with
  one more trigger kind) polls the block: its ledger's changes.jsonl and the
  files under it. A change opens a settle window of the stage's `settle_s`;
  every further change restarts it; when the block has been quiet that long
  the stage fires, once per window.

`BlockWatch.poll()` is one pass (the runner's tick calls it; the scheduler's
own thread calls it too when `start()`ed). The clock is injectable.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional

from halo_harness.agents_schedule import TeamScheduler
from halo_harness.team import LEDGER_DIR
from halo_harness.team import blocks as B

SKIP_DIRS = (LEDGER_DIR, ".git", "node_modules", "__pycache__")
WALK_CAP = 5000


def signature(root, block: dict) -> tuple:
    """What a block looks like now: its ledger's change count and its files' sizes and times."""
    path = (Path(root) / block["path"]).resolve()
    changes = B.ledger_dir(root, block) / "changes.jsonl"
    try:
        ch = (changes.stat().st_size, changes.stat().st_mtime_ns)
    except OSError:
        ch = (0, 0)
    if block["kind"] == "file":
        try:
            st = path.stat()
            return ch, ((st.st_size, st.st_mtime_ns),)
        except OSError:
            return ch, ()
    rows = []
    if path.is_dir():
        for i, p in enumerate(sorted(path.rglob("*"))):
            if i >= WALK_CAP:
                break
            rel = p.relative_to(path)
            if any(part in SKIP_DIRS or part.endswith(LEDGER_DIR) for part in rel.parts) or rel.parts[:2] == (".halo", "team"):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            if p.is_file():
                rows.append((rel.as_posix(), st.st_size, st.st_mtime_ns))
    return ch, tuple(rows)


class BlockWatch(TeamScheduler):
    """The team run's block watchers. `fire_fn(session, entry)` is called with the
    entry `{id, kind: "block_change", block, stage, settle_s, ...}`."""

    def __init__(self, team: dict, *, fire_fn: Callable, clock: Optional[Callable] = None, tick_s: float = 1.0):
        super().__init__(None, SimpleNamespace(name=team.get("name") or "team"), fire_fn=fire_fn, tick_s=tick_s,
                         clock=clock or time.time)
        self.team = SimpleNamespace(name=team.get("name") or "team")
        self.spec = team
        self.root = Path(team["root"])

    def arm_block(self, stage: dict) -> Optional[dict]:
        from halo_harness.team.spec import block_by_id, parse_trigger
        kind, bid = parse_trigger(stage["trigger"])
        block = block_by_id(self.spec, bid)
        if kind != "block_change" or block is None:
            return None
        settle = stage.get("settle_s")
        entry = {"id": f"{self.team.name}:{stage['id']}:block_change", "name": stage["id"], "kind": "trigger",
                 "on": "block_change", "on_value": bid, "block": bid, "stage": stage["id"],
                 "settle_s": float(settle) if isinstance(settle, (int, float)) and not isinstance(settle, bool) else 20.0,
                 "team": self.team.name, "enabled": True, "armed_at": self.clock(), "fired": False,
                 "last_note": "", "sig": signature(self.root, block), "changed_at": None, "fires": 0}
        with self._lock:
            self.triggers.append(entry)
        return entry

    def armed(self) -> list:
        with self._lock:
            return [dict(t, sig=None) for t in self.triggers if t.get("on") == "block_change"]

    def _poll_files(self) -> None:
        super()._poll_files()
        self.poll()

    def poll(self) -> list:
        """One pass: the stage ids that fired."""
        from halo_harness.team.spec import block_by_id
        now, due = self.clock(), []
        with self._lock:
            for t in self.triggers:
                if t.get("on") != "block_change" or not t.get("enabled", True):
                    continue
                block = block_by_id(self.spec, t["block"])
                if block is None:
                    continue
                sig = signature(self.root, block)
                if sig != t["sig"]:
                    t["sig"], t["changed_at"] = sig, now
                    continue
                if t["changed_at"] is not None and now - t["changed_at"] >= t["settle_s"]:
                    t["changed_at"] = None
                    t["fires"] += 1
                    due.append(t)
        for t in due:
            self._fire(t, f"block {t['block']} quiet for {t['settle_s']:g}s")
        return [t["stage"] for t in due]

    def _persist(self) -> None:
        return None
