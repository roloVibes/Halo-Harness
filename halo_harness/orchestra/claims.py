"""halo_harness.orchestra.claims -- who holds which part of which file.

The log `<run>/claims.jsonl` is append-only, one JSON object per line:

    {"ts", "elapsed_s", "op", "holder", "key", "ttl_s", "note"}

with `op` one of claim | writing | written | release | expire | steal.
`active(now)` folds it: the LAST line per key wins; release/expire clear the
key; claim/steal/writing/written make `holder` hold it (state claimed /
claimed / writing / written) until that line's `ts + ttl_s`. Every op reads,
checks and appends under the run's lock (`<run>/claims.jsonl.lock` plus a
thread lock), so two sessions on one machine never interleave and two agents
racing for one key get exactly one winner.

Holders are `"<session_id>/<agent_id>"` (`agent_id` "main" for the top
session); `holder_for(session_dir)` builds one from a session folder. Every
op also writes a `claim` line to the run's events.jsonl.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional, Union

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import jsonl
from halo_harness.orchestra.index import covers, overlaps

OPS = ("claim", "writing", "written", "release", "expire", "steal")
STATE_OF_OP = {"claim": "claimed", "steal": "claimed", "writing": "writing", "written": "written"}
DEFAULT_TTL_S = 900


@dataclass
class Claim:
    key: str
    holder: str
    state: str          # claimed | writing | written | released
    ts: float           # the last line's time
    ttl_s: int
    note: str = ""
    ok = True

    @property
    def expires(self) -> float:
        return self.ts + self.ttl_s

    def to_dict(self) -> dict:
        return dict(asdict(self), expires=self.expires)


@dataclass
class Refusal:
    key: str
    text: str
    holder: str = ""          # who holds the conflicting claim ("" when none)
    conflict_key: str = ""
    expires: float = 0.0
    ok = False

    def __str__(self) -> str:
        return self.text


Result = Union[Claim, Refusal]


def clock_text(ts: float) -> str:
    """Local wall-clock time of `ts`, e.g. 14:05:09."""
    return time.strftime("%H:%M:%S", time.localtime(ts))


def holder_for(session_dir, agent_id: Optional[str] = None) -> str:
    """`<session_id>/<agent_id>` for a session folder: the top session's id
    (the folder before the first `subagents` hop) and the agent id (the
    given one, else the last `agent-<id>` folder, else "main")."""
    parts = Path(session_dir).parts if session_dir else ()
    if "subagents" in parts:
        idx = parts.index("subagents")
        top = parts[idx - 1] if idx > 0 else "session"
    else:
        top = parts[-1] if parts else "session"
    if not agent_id:
        last = parts[-1] if parts else ""
        agent_id = last[len("agent-"):] if last.startswith("agent-") and "subagents" in parts else "main"
    return f"{top}/{agent_id}"


def fold(entries: list, now: float) -> dict:
    """`{key: Claim}` for every key whose last line holds it and has not expired."""
    last: dict = {}
    for e in entries:
        if e.get("op") in OPS and isinstance(e.get("key"), str):
            last[e["key"]] = e
    out = {}
    for key, e in last.items():
        state = STATE_OF_OP.get(e["op"])
        if state is None:
            continue
        claim = Claim(key, str(e.get("holder") or ""), state, float(e.get("ts") or 0),
                      int(e.get("ttl_s") or DEFAULT_TTL_S), str(e.get("note") or ""))
        if claim.expires > now:
            out[key] = claim
    return out


class ClaimLog:
    """The claim log of one run. `clock` is injectable for tests."""

    def __init__(self, run_dir, *, clock: Callable[[], float] = time.time):
        self.run_dir = Path(run_dir)
        self.path = self.run_dir / "claims.jsonl"
        self.clock = clock
        self._tail = jsonl.Tail(self.path)

    # ---- reading ---------------------------------------------------------
    def entries(self) -> list:
        """Every line of claims.jsonl, oldest first (read incrementally)."""
        return self._tail.lines()

    def active(self, now: Optional[float] = None) -> dict:
        """`{key: Claim}` of every live claim at `now` (default: the clock)."""
        return fold(self.entries(), self.clock() if now is None else now)

    def conflicts(self, holder: str, key: str, now: Optional[float] = None) -> list:
        """Live claims by OTHER holders whose key overlaps `key`."""
        return [c for c in self.active(now).values() if c.holder != holder and overlaps(c.key, key)]

    def held_by(self, holder: str, key: str, now: Optional[float] = None) -> Optional[Claim]:
        """`holder`'s live claim that covers `key` (the key itself or a parent), if any."""
        mine = [c for c in self.active(now).values() if c.holder == holder and covers(c.key, key)]
        return max(mine, key=lambda c: len(c.key), default=None)

    def lead_holder(self) -> Optional[str]:
        from halo_harness.orchestra.goal import run_meta
        value = run_meta(self.run_dir).get("lead_holder")
        return value if isinstance(value, str) and value else None

    def is_lead(self, holder: str) -> bool:
        """The recorded lead (run.json `lead_holder`); with none recorded, any
        `<session>/main` holder (the top session that runs the workers)."""
        lead = self.lead_holder()
        return holder == lead if lead else str(holder).endswith("/main")

    # ---- writing ---------------------------------------------------------
    def _append(self, op: str, holder: str, key: str, ttl_s: int, note: str = "") -> Claim:
        ts = self.clock()
        jsonl.append_line(self.path, {"ts": round(ts, 3), "elapsed_s": jsonl.elapsed(self.run_dir, ts),
                                      "op": op, "holder": holder, "key": key, "ttl_s": int(ttl_s),
                                      "note": note})
        state = STATE_OF_OP.get(op, "released")
        return Claim(key, holder, state, ts, int(ttl_s), note)

    def _event(self, text: str, **data) -> None:
        try:
            run_events.log(self.run_dir, "claim", text, **data)
        except OSError:
            pass

    def claim(self, holder: str, key: str, ttl_s: int = DEFAULT_TTL_S, note: str = "") -> Result:
        """Take `key` for `ttl_s` seconds, or a Refusal naming the holder of an
        overlapping live claim and when it expires. Re-claiming your own key renews it."""
        with jsonl.locked(self.path):
            now = self.clock()
            others = self.conflicts(holder, key, now)
            if others:
                c = min(others, key=lambda c: c.expires)
                return Refusal(key, f"`{key}` overlaps `{c.key}`, held by {c.holder} until "
                                    f"{clock_text(c.expires)} ({c.state}): wait for the release, claim "
                                    f"another unit, or ask the lead", c.holder, c.key, c.expires)
            result = self._append("claim", holder, key, ttl_s, note)
        self._event(f"{holder} claimed {key}", op="claim", holder=holder, key=key, ttl_s=int(ttl_s))
        return result

    def _own_step(self, op: str, holder: str, key: str, note: str = "") -> Result:
        with jsonl.locked(self.path):
            current = self.active().get(key)
            if current is None or current.holder != holder:
                who = f"held by {current.holder}" if current else "not claimed by anyone"
                return Refusal(key, f"you do not hold `{key}` ({who}): claim it first",
                               current.holder if current else "", key, current.expires if current else 0.0)
            result = self._append(op, holder, key, current.ttl_s, note)
        self._event(f"{holder} {op if op != 'release' else 'released'} {key}", op=op, holder=holder, key=key)
        return result

    def mark_writing(self, holder: str, key: str, note: str = "") -> Result:
        """`holder` started writing its claimed `key` (renews the TTL)."""
        return self._own_step("writing", holder, key, note)

    def mark_written(self, holder: str, key: str, note: str = "") -> Result:
        """`holder` finished writing `key`; the claim stays until released."""
        return self._own_step("written", holder, key, note)

    def release(self, holder: str, key: str, note: str = "") -> Result:
        """`holder` lets `key` go. Returns the Claim in state `released`."""
        return self._own_step("release", holder, key, note)

    def steal(self, key: str, by: str, reason: str, ttl_s: int = DEFAULT_TTL_S) -> Result:
        """The run's lead takes `key` (and clears every overlapping claim) for `by`."""
        if not self.is_lead(by):
            lead = self.lead_holder() or "the run's <session>/main holder"
            return Refusal(key, f"only the lead ({lead}) can steal `{key}`: ask the lead")
        with jsonl.locked(self.path):
            now = self.clock()
            for c in self.conflicts(by, key, now):
                if c.key != key:
                    self._append("release", c.holder, c.key, c.ttl_s, f"stolen by {by}: {reason}")
            result = self._append("steal", by, key, ttl_s, reason)
        self._event(f"{by} stole {key}: {reason}", op="steal", holder=by, key=key)
        return result

    def reassign(self, key: str, new_holder: str, by_lead: str, ttl_s: int = DEFAULT_TTL_S) -> Result:
        """The lead hands `key` to `new_holder` (a `steal` line in the new
        holder's name): how a worker takes over the `lane:<n>` placeholder
        claims the split made for its lane."""
        if not self.is_lead(by_lead):
            return Refusal(key, f"only the lead ({self.lead_holder() or 'none recorded'}) can reassign `{key}`")
        with jsonl.locked(self.path):
            result = self._append("steal", new_holder, key, ttl_s, f"reassigned by {by_lead}")
        self._event(f"{key} reassigned to {new_holder}", op="reassign", holder=new_holder, key=key)
        return result

    def expire_stale(self, now: Optional[float] = None) -> list:
        """Append an `expire` line for every claim past its TTL; returns their keys."""
        expired = []
        with jsonl.locked(self.path):
            now = self.clock() if now is None else now
            live = fold(self.entries(), now)
            last: dict = {}
            for e in self.entries():
                if e.get("op") in OPS and isinstance(e.get("key"), str):
                    last[e["key"]] = e
            for key, e in last.items():
                if e["op"] in STATE_OF_OP and key not in live:
                    self._append("expire", str(e.get("holder") or ""), key, int(e.get("ttl_s") or 0), "ttl passed")
                    expired.append(key)
        for key in expired:
            self._event(f"claim on {key} expired", op="expire", key=key)
        return expired
