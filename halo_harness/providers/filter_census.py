"""halo_harness.providers.filter_census -- Halo 2.0.7 cyber Pillar 1.2:
the MEASURED per-provider filter profile.

Census-style, not datasheets: every time a live response actually arrives
with a filter signal (`finish_reason: "content_filter"`, GLM's
`finish_reason: "sensitive"`, a native Anthropic `stop_reason:
"refusal"`), the observation is recorded here -- the full raw model ref,
the reason, the count, the last-seen time. Nothing is ever PROBED: the
profile is built purely from real traffic this harness already saw, so a
machine that never hits a filter never writes a file, and a provider
that never filters never appears.

Persisted at `<state_dir>/filter-census.json`:
`{"observations": {"<raw model ref>": {"<reason>": n, "last_seen": epoch}}}`.

The raw ref ("or:z-ai/glm-5.3", "ol:qwen3-coder:30b@lan") is the key on
purpose: it is unique, unambiguous, and exactly what a fallback-chain
entry or role table holds, so "is this lane filter-free" is a single
dict lookup with no ref parsing at all.

Consumers:
  * agent/loop.py `_step` records on every filter signal (Pillar 1.1);
  * the transparent reroute (Pillar 1.3) picks its lane from the
    session's fallback chain, and `filter_free_lanes` is the "which of
    these candidates has never filtered" view over this data (also the
    basis of the Pillar 2 canary/role-binding census display).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

_LOCK = threading.Lock()


def _census_path(state_dir) -> Optional[Path]:
    if state_dir is None:
        return None
    return Path(state_dir) / "filter-census.json"


def load_filter_census(state_dir) -> dict:
    """The whole census dict (never raises; a missing/corrupt file is an
    empty census -- the profile rebuilds from live traffic)."""
    path = _census_path(state_dir)
    if path is None or not path.exists():
        return {"observations": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"observations": {}}
    if not isinstance(data, dict):
        return {"observations": {}}
    data.setdefault("observations", {})
    return data


def record_filter_observation(state_dir, raw_ref: str, reason: str) -> None:
    """One live filter observation for the full raw model ref. Best-effort
    like every learned-rules write: a census that cannot persist
    (read-only state dir, a concurrent writer) is telemetry we lost,
    never a reason to fail a turn."""
    if not raw_ref or not reason:
        return
    path = _census_path(state_dir)
    if path is None:
        return
    with _LOCK:
        data = load_filter_census(state_dir)
        entry = data["observations"].setdefault(raw_ref, {})
        entry[reason] = int(entry.get(reason, 0)) + 1
        entry["last_seen"] = time.time()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        except Exception:
            pass


def model_filter_count(state_dir, raw_ref: str) -> int:
    """Total observed filter signals for one raw ref (0 = never filtered --
    a filter-free lane as far as the census knows)."""
    data = load_filter_census(state_dir)
    entry = (data.get("observations") or {}).get(raw_ref) or {}
    return sum(int(v) for k, v in entry.items() if k != "last_seen")


def filter_free_lanes(state_dir, candidates: "list[str]") -> "list[str]":
    """The subset of `candidates` (raw model refs) with ZERO census
    observations, in the original order. The reroute's "filter-free lane"
    view: a lane that has never filtered this machine's real traffic is
    the preferred next hop; a lane that HAS filtered is not forbidden
    (filters are per-prompt), it just ranks below the unobserved ones."""
    data = load_filter_census(state_dir)
    obs = data.get("observations") or {}
    return [raw for raw in candidates if raw not in obs]
