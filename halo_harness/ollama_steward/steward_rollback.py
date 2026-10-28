"""halo_harness.ollama_steward.steward_rollback -- Halo 3.3.4.0 R3's rollback
judge, moved out of steward.py in R5 (the 250-line cap): a change in place
whose next JUDGE_CALLS calls of that host and model went worse (more trims,
cut replies and errors) than the JUDGE_CALLS before it is reverted, and the
revert says so.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.ollama_steward.steward import JUDGE_CALLS, _in_place, _revert, read_journal


def _bad(line: dict) -> int:
    return int(bool(line.get("trimmed")) or line.get("done_reason") == "length" or line.get("status") != 200)


def rollbacks(state_dir, *, lines: Optional[list] = None, now: Optional[float] = None) -> list:
    """Each change in place whose next 10 calls went worse than the 10 before it, reverted."""
    from halo_harness.ollama_steward.ledger import parse_at, read_calls
    from halo_harness.ollama_steward.profiles import key_for
    from halo_harness.ollama_steward.traffic import canonical_host
    from halo_harness.providers.ollama import resolve_ollama_hosts
    lines = read_calls(state_dir) if lines is None else lines
    hosts = resolve_ollama_hosts()
    out = []
    for row in _in_place(read_journal(state_dir)):
        t = parse_at(row.get("at")) or 0
        mine = [x for x in lines if x.get("kind") != "calibrate"
                and key_for(canonical_host(x.get("host") or {}, hosts)[0], x.get("model")) == row["key"]]
        before = [x for x in mine if (parse_at(x.get("at")) or 0) < t][-JUDGE_CALLS:]
        after = [x for x in mine if (parse_at(x.get("at")) or 0) >= t][:JUDGE_CALLS]
        if len(after) < JUDGE_CALLS:
            continue
        b, a = sum(map(_bad, before)), sum(map(_bad, after))
        if a > b:
            out.append(_revert(state_dir, row, "rollback", f"{a} bad calls of the next {len(after)} against {b} of "
                               f"the {len(before)} before", now=now))
    return out
