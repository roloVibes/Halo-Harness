"""halo_harness.fleet.control_probes -- Halo 3.3.6.0 R1: a member's battery
profiles reach the hub with the member's ledger push (fleet/ollama_share.py),
the way its pull jobs do (fleet/control_pulls.py).

    read_probes(home, now=None)         the member's side: the profiles it made in the last RECENT_S
                                        (the capability cache), without the raw evidence
    take_probes(home, member, rows)     the hub's side: each kept in the hub's own capability cache
                                        (`from` = the member, `host` = the hub's name for that host when a
                                        probe job of the hub asked for it) and onto that job
"""

from __future__ import annotations

import time
from typing import Optional

RECENT_S = 600.0
MAX_ROWS = 10


def read_probes(home, now: Optional[float] = None) -> list:
    from halo_harness.providers.ollama_capability import all_profiles
    from halo_harness.studio.local_probe_job import compact
    now = time.time() if now is None else now
    rows = [p for p in all_profiles(home) if not p.get("from") and now - float(p.get("probed_at") or 0) < RECENT_S]
    return [compact(p) for p in rows[:MAX_ROWS]]


def take_probes(home, member: str, rows) -> int:
    from halo_harness.providers.ollama_capability import save_profile
    from halo_harness.studio.local_probe_job import take_remote
    if not isinstance(rows, list) or not member:
        return 0
    n = 0
    for p in rows[:MAX_ROWS]:
        if not isinstance(p, dict) or not p.get("digest") or not p.get("model"):
            continue
        hub_host = take_remote(member, p)
        keep = {**p, "from": member, "member_host": p.get("host"),
                "host": hub_host if isinstance(hub_host, str) and hub_host else f"{member}:{p.get('host')}"}
        save_profile(home, keep)
        n += 1
    return n


def read_crashes(home) -> list:
    """3.3.6.0 R2: the member's crash fingerprints of the last RECENT_S (ollama_steward/fingerprints.py)."""
    from halo_harness.ollama_steward.fingerprints import read_recent
    return read_recent(home, RECENT_S)


def take_crashes(home, member: str, rows) -> int:
    from halo_harness.ollama_steward.fingerprints import take
    return take(home, member, rows)


__all__ = ["read_crashes", "read_probes", "take_crashes", "take_probes"]
