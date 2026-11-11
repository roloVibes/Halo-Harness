"""halo_harness.work.claims -- a unit's claims, the same calls for every kind
(Halo 3.1.2.0 R1, docs/WORK.md).

    {"keys": [...], "mode": "unit|path|none",
     "live": [{"key", "holder", "state", "expires"}]}

* lane: keys are file units (`basket.py#total`, mode `unit`); the live
  claims are the run's claims.jsonl (orchestra/claims.py ClaimLog).
* part: keys are repo paths or globs from the plan (mode `path`); a part's
  claims are fixed by its plan (claims.json), nothing is held live.

(3.4.0.0 B: a team stage's block claims left with the team file.)

`claim(kind, run_dir, uid, key, holder)` records one: a lane's key in the
run's ClaimLog. It returns the ClaimLog's answer (a Claim, or a Refusal
naming the holder).
"""

from __future__ import annotations


def _live(claims: dict, keep) -> list:
    return [{"key": c.key, "holder": c.holder, "state": c.state, "expires": round(c.expires, 3)}
            for c in claims.values() if keep(c)]


def of(kind: str, run_dir, uid) -> dict:
    from halo_harness.work.store import UnitStore
    u = UnitStore(run_dir, kind).need(uid)
    out = dict(u.claims, live=[])
    if u.kind == "lane":
        from halo_harness.orchestra.claims import ClaimLog
        from halo_harness.orchestra.index import overlaps
        keys = u.claims.get("keys") or []
        out["live"] = _live(ClaimLog(run_dir).active(), lambda c: any(overlaps(c.key, k) for k in keys))
    return out


def claim(kind: str, run_dir, uid, key: str, holder: str):
    from halo_harness.work.store import kind_of
    k = kind_of(kind)
    if k == "lane":
        from halo_harness.orchestra.claims import ClaimLog
        return ClaimLog(run_dir).claim(holder, key)
    raise ValueError("a part's claims are its plan's (claims.json): plan the mission again to change them")
