"""halo_harness.work.claims -- a unit's claims, the same calls for every kind
(Halo 3.1.2.0 R1, docs/WORK.md).

    {"keys": [...], "mode": "unit|path|block|none",
     "live": [{"key", "holder", "state", "expires"}]}

* lane: keys are file units (`basket.py#total`, mode `unit`); the live
  claims are the run's claims.jsonl (orchestra/claims.py ClaimLog).
* part: keys are repo paths or globs from the plan (mode `path`); a part's
  claims are fixed by its plan (claims.json), nothing is held live.
* stage: keys are the blocks it writes (mode `block`); the live claims are
  its members' (`<member>@<stage>`) in each block's ledger (team/blocks.py).
* step: no claims (mode `none`).

`claim(kind, run_dir, uid, key, holder)` records one: a lane's key in the
run's ClaimLog, a stage's `<block id>:<key>` in that block's ledger. It
returns the ClaimLog's answer (a Claim, or a Refusal naming the holder).
"""

from __future__ import annotations

from pathlib import Path


def _live(claims: dict, keep) -> list:
    return [{"key": c.key, "holder": c.holder, "state": c.state, "expires": round(c.expires, 3)}
            for c in claims.values() if keep(c)]


def _team(run_dir):
    from halo_harness.orchestra import jsonl
    from halo_harness.team import spec as S
    meta = jsonl.read_json(Path(run_dir) / "run.json", {}) or {}
    root = meta.get("root")
    if not root:
        return None
    try:
        return S.load_team(Path(root))
    except Exception:
        return None


def of(kind: str, run_dir, uid) -> dict:
    from halo_harness.work.store import UnitStore
    u = UnitStore(run_dir, kind).need(uid)
    out = dict(u.claims, live=[])
    if u.kind == "lane":
        from halo_harness.orchestra.claims import ClaimLog
        from halo_harness.orchestra.index import overlaps
        keys = u.claims.get("keys") or []
        out["live"] = _live(ClaimLog(run_dir).active(), lambda c: any(overlaps(c.key, k) for k in keys))
    elif u.kind == "stage":
        team = _team(run_dir)
        if team is not None:
            from halo_harness.team import blocks as B
            from halo_harness.team import spec as S
            for bid in u.claims.get("keys") or []:
                block = S.block_by_id(team, bid)
                if block:
                    out["live"] += _live(B.claim_log(team["root"], block).active(),
                                         lambda c: str(c.holder).endswith(f"@{u.id}"))
    return out


def claim(kind: str, run_dir, uid, key: str, holder: str):
    from halo_harness.work.store import kind_of
    k = kind_of(kind)
    if k == "lane":
        from halo_harness.orchestra.claims import ClaimLog
        return ClaimLog(run_dir).claim(holder, key)
    if k == "stage":
        bid, _, inner = str(key).partition(":")
        team = _team(run_dir)
        from halo_harness.team import blocks as B
        from halo_harness.team import spec as S
        block = S.block_by_id(team, bid) if team is not None else None
        if block is None or not inner:
            raise ValueError(f"a stage's claim is `<block id>:<key>` of a block of its team, got {key!r}")
        B.ensure_ledger(team["root"], block)
        return B.claim_log(team["root"], block).claim(holder, inner, note=f"stage {uid}")
    if k == "part":
        raise ValueError("a part's claims are its plan's (claims.json): plan the mission again to change them")
    raise ValueError("a flow step takes no claims")
