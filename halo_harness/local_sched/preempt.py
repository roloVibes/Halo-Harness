"""halo_harness.local_sched.preempt -- when two claims collide, the lower priority is pre-empted and told (Halo 3.3.8.0
R4; docs/MODELS-bundles.md "Priority and pre-emption").

    rank(priority) -> 0 low | 1 normal | 2 high
    plan(claims, *, need_gb, free_gb, priority, bundle) -> {ok, take [claim], frees_gb, held_by [claim]}
        the fewest lower-priority claims (the lowest first, then the largest) whose GB make `need_gb` fit in `free_gb`;
        a claim of equal or higher priority is never taken (`held_by` names them when nothing lower is enough)
    line(winner, priority, c) -> "pre-empted verifier (low) on pc: big-reasoner (high) needs its 6.0 GB -- halo pack on
        verifier claims it again once there is room" ("needs the pool" for a claim on the pool: one resource)
    held_line(bundle, priority, held_by) -> "verifier holds 6.0 GB there at priority high: big-reasoner's normal does not
        pre-empt it"
    take(c, *, winner, priority, state_dir=None) -> [line]   the claim released (here: reserve_act.release; on a halo
        host: its `release` op), and the notice written where its owner reads it (claims_file.notice, both files)
Never silent: every pre-emption is one line in the winner's output and one notice in the loser's verdict.
"""

from __future__ import annotations

from typing import Optional

RANK = {"low": 0, "normal": 1, "high": 2}


def rank(priority: Optional[str]) -> int:
    return RANK.get(str(priority or "normal"), 1)


def plan(claims: list, *, need_gb: float, free_gb: float, priority: str, bundle: str) -> dict:
    others = [c for c in claims if c.get("bundle") != bundle and float(c.get("gb") or 0) > 0]
    lower = sorted((c for c in others if rank(c.get("priority")) < rank(priority)),
                   key=lambda c: (rank(c.get("priority")), -float(c.get("gb") or 0), str(c.get("bundle"))))
    take, room = [], float(free_gb)
    for c in lower:
        if room >= need_gb:
            break
        take.append(c)
        room += float(c.get("gb") or 0)
    ok = room >= need_gb
    return {"ok": ok and bool(take), "take": take if ok else [], "frees_gb": round(room - float(free_gb), 1),
            "held_by": [c for c in others if rank(c.get("priority")) >= rank(priority)]}


def line(winner: str, priority: str, c: dict) -> str:
    what = ("the pool" if str(c.get("host") or "").lower() == "pool" else  # the pool is one resource, held whole
            f"its {float(c.get('gb') or 0):.1f} GB")
    return (f"pre-empted {c.get('bundle')} ({c.get('priority') or 'normal'}) on {c.get('host')}: {winner} ({priority}) "
            f"needs {what} -- halo pack on {c.get('bundle')} claims it again once there is room")


def held_line(bundle: str, priority: str, held_by: list) -> str:
    if not held_by:
        return ""
    who = ", ".join(sorted({str(c.get("bundle")) for c in held_by}))
    gb = sum(float(c.get("gb") or 0) for c in held_by)
    top = max((c.get("priority") or "normal" for c in held_by), key=rank)
    return f"{who} holds {gb:.1f} GB there at priority {top}: {bundle}'s {priority} does not pre-empt it"


def take(c: dict, *, winner: str, priority: str, state_dir=None) -> list:
    from halo_harness.local_sched import claims_file as CF
    from halo_harness.local_sched.reserve import _state, forget
    state = _state(state_dir)
    said = line(winner, priority, c)
    out = []
    if c.get("via") == "host":
        from halo_harness.local_sched.facts import host_named
        from halo_harness.local_sched.reserve_act import _host_act
        ok, got = _host_act(host_named(c.get("host")), "release", {"bundle": c["bundle"]})
        out.append(said if ok else f"{said} (the halo host did not answer the release: {got or 'no answer'})")
    mine = [r for r in CF.read(CF.local_file(state), expired=True) if r.get("bundle") == c.get("bundle")]
    if mine:
        from halo_harness.local_sched.reserve_act import release
        release(str(c["bundle"]), state_dir=state, disable=False)
    if not out:
        out.append(said)
    row = {"bundle": c.get("bundle"), "by": winner, "priority": priority, "host": c.get("host"), "gb": c.get("gb"),
           "line": said}
    CF.notice(CF.local_file(state), row)
    forget()
    return out
