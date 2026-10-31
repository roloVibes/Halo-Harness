"""halo_harness.ollama_steward.steward_review -- the steward's review-mode half (moved out of steward.py in 3.3.7.0 R2
for the 250-line cap): `propose` writes a proposal line, `apply_by_id` applies a finding or a proposal by its id
(`halo ollama steward apply <id>`, Studio's Apply).
"""

from __future__ import annotations

from typing import Optional


def propose(state_dir, f: dict, change: dict, *, now: Optional[float] = None) -> dict:
    """A review-mode proposal line (its id is the finding's: `halo ollama steward apply <id>`)."""
    from halo_harness.ollama_steward.steward import _append
    return _append(state_dir, {"_now": now, "id": f["id"], "kind": "proposal", "key": f["key"], "field": change["field"],
                               "from": change.get("from"), "to": change["to"], "why": change["why"],
                               "finding": f["id"], "rule": f["rule"], "evidence": f.get("evidence"),
                               "plan": f.get("plan")})


def apply_by_id(state_dir, fid: str, *, now: Optional[float] = None, **gather_kw) -> "tuple[Optional[dict], str]":
    """`halo ollama steward apply <id>`: a finding of the current run (or a proposal in the journal) applied."""
    import time
    from halo_harness.ollama_steward.rules import findings as get_findings
    from halo_harness.ollama_steward.steward import apply_change, check, profile_lock, read_journal
    from halo_harness.providers.ollama import resolve_ollama_hosts
    now = now or time.time()
    f = None
    row = next((r for r in reversed(read_journal(state_dir)) if r.get("kind") == "proposal" and r.get("id") == fid),
               None)
    if row is None:
        f = next((x for x in get_findings(state_dir, **gather_kw) if x["id"] == fid), None)
        if f is None:
            return None, f"no finding or proposal with the id {fid}"
    else:
        from halo_harness.ollama_steward.profiles import split_key
        host, model = split_key(row["key"])
        f = {"id": fid, "rule": row.get("rule"), "key": row["key"], "host": host, "model": model,
             "evidence": row.get("evidence"), "plan": row.get("plan"),
             "proposal": {k: row.get(k) for k in ("field", "from", "to", "why")}}
    with profile_lock(state_dir):
        change, why = check(state_dir, f, hosts=resolve_ollama_hosts(), now=now)
        return (None, why) if change is None else (apply_change(state_dir, f, change, mode_name="review", now=now), "")
