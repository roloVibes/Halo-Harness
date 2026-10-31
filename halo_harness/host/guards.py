"""halo_harness.host.guards -- the mechanical guards on fixes (Halo 3.3.7.0 R2; plans/local-model-fit-brief.md H10.2 /
H10.3: "undo, not paternalism"). No model, no judgement: each guard is one line naming the mechanic and its number.

A request is a **fix** when it changes a profile field (`set_num_ctx`, `set_num_predict`, `set_keep_alive`,
`set_tools_max`) or cites a finding (`evidence`). A dry preview is never one. For a fix:

    evidence      a profile change names the finding it acts on: `evidence {finding: <id>}` or `{lines: [...]}`
                  -> 422 "a fix names the finding it acts on ..."
    one at a time one change in flight per host: while the host verifies one (host/verify.py) a second answers 409
                  "one change at a time: set_num_ctx landed 40 s ago on pc, verifying (2 of 5 calls, 560 s left)"
    cooldown      `host.cooldown_s` (120) between changes on the same host|model -> 409
    rate limit    `host.changes_per_hour` (10) per peer -> 429

A person's Load (a `warm` with no evidence) is not a fix: the invariants guard it (host/invariants.py).

    is_fix(op, body) / check(home, peer, op, body, *, host, key, now) -> (200, None) | (status, {error, guard})
"""

from __future__ import annotations

import time
from typing import Optional

COOLDOWN_S = 120.0
PER_HOUR = 10
HOUR = 3600.0


def _num(home, key: str, default, kind=float):
    from halo_harness.host.state import _cfg
    try:
        v = kind(_cfg(key, default, home))
    except (TypeError, ValueError):
        return default
    return v if v >= 0 else default


def cooldown_s(home) -> float:
    return _num(home, "host.cooldown_s", COOLDOWN_S)


def per_hour(home) -> int:
    return _num(home, "host.changes_per_hour", PER_HOUR, int)


def has_evidence(body: dict) -> bool:
    ev = body.get("evidence") if isinstance(body.get("evidence"), dict) else {}
    return bool(ev.get("finding") or (isinstance(ev.get("lines"), list) and ev["lines"]))


def is_fix(op, body: dict) -> bool:
    return body.get("dry") is not True and (op.profile or has_evidence(body))


def fixes_by(home, peer: str, since: float) -> list:
    """The fixes this peer landed since `since` (the audit's act lines: landed, not dry, a fix)."""
    from halo_harness.host.state import read_audit
    return [a for a in read_audit(home, limit=5000) if a.get("op") and a.get("fix") and a.get("landed") and not a.get("dry")
            and a.get("peer") == peer and float(a.get("at") or 0) >= since]


def check(home, peer: str, op, body: dict, *, host: str, key: Optional[str], now: Optional[float] = None) -> "tuple[int, Optional[dict]]":
    from halo_harness.host import verify
    now = time.time() if now is None else now
    if op.profile and body.get("dry") is not True and not has_evidence(body):
        return 422, {"error": f"a fix names the finding it acts on: send evidence {{finding: <id>}} (or {{lines: [...]}}) "
                              f"with {op.name}; a dry preview needs none", "guard": "evidence"}
    if not is_fix(op, body):
        return 200, None
    live = verify.open_on(home, host)
    if live is not None:
        from halo_harness.ollama_steward.ledger import parse_at
        ago, need = int(now - float(live.get("at") or now)), int(live.get("need_calls") or verify.VERIFY_CALLS)
        seen = sum(1 for x in verify._lines(home, live["host"], live["model"]) if (parse_at(x.get("at")) or 0) >= live["at"])
        left = max(0, int(float(live.get("ends_at") or now) - now))
        return 409, {"error": f"one change at a time: {live.get('op')} landed {ago} s ago on {host}, verifying "
                              f"({min(seen, need)} of {need} calls, at most {left} s more)", "guard": "in-flight",
                     "change": live.get("id")}
    last = verify.last_on(home, key) if key else None
    gap = cooldown_s(home)
    if last is not None and now - float(last.get("at") or 0) < gap:
        ago = int(now - float(last["at"]))
        return 409, {"error": f"cooldown: {last.get('op')} changed {key} {ago} s ago; host.cooldown_s is {int(gap)}, so "
                              f"the next change there opens in {int(gap) - ago} s", "guard": "cooldown"}
    cap = per_hour(home)
    mine = fixes_by(home, peer, now - HOUR)
    if len(mine) >= cap:
        first = min(float(a.get("at") or now) for a in mine)
        return 429, {"error": f"rate limit: {peer} landed {len(mine)} fixes in the last hour (host.changes_per_hour "
                              f"{cap}); the next one opens in {max(1, int(first + HOUR - now))} s", "guard": "rate"}
    return 200, None
