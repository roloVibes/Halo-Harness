"""halo_harness.fleet.local_view -- this harness's own sessions and agent
trees, the direct path (Halo 3.0.5.0 "Fleet" round R2).

`snapshot()` is the local harness as `GET /api/fleet` lists it (and as the
terminal table shows it when no Studio runs): the live registry
(`~/.halo/run/sessions.json`, never a private session) plus, for each
session, `status` and `agents` over its control socket (every call times
out after TIMEOUT_S; the probes run side by side and the whole snapshot
waits at most WAIT_S, a slow session keeping its row without the extras).
`session_row` is the row shape both this and the relay's announce use:

    {...registry public fields, status: waiting|busy|idle|unknown, busy, pending, model, cost_usd,
     agents_live, agents: [agent row, ...]}
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from halo_harness.fleet import identity

TIMEOUT_S = 1.0
WAIT_S = 1.5
CACHE_S = 1.0
_cache: dict = {}
_lock = threading.Lock()


def _state(data) -> str:
    if not isinstance(data, dict):
        return "unknown"
    pending = data.get("pending") if isinstance(data.get("pending"), dict) else {}
    if any(pending.get(k) for k in ("permission", "question", "plan", "approval")):
        return "waiting"
    return "busy" if data.get("busy") else "idle"


def session_row(entry: dict, status: Optional[dict], agents: Optional[list]) -> dict:
    from halo_harness.remote.registry import public_entry
    row = public_entry(entry)
    data = status if isinstance(status, dict) else {}
    live = data.get("agents")
    row.update(status=_state(status), busy=bool(data.get("busy")), pending=data.get("pending"),
               model=data.get("model"), cost_usd=data.get("cost_usd"),
               agents_live=live if isinstance(live, int) and not isinstance(live, bool) else 0,
               agents=[a for a in (agents or []) if isinstance(a, dict)])
    return row


def _probe(entry: dict, out: dict) -> None:
    from halo_harness.remote.client import ControlClient, default_token_for
    client = None
    try:
        client = ControlClient(str(entry.get("endpoint") or ""), default_token_for(entry), timeout=TIMEOUT_S)
        st = client.call("status")
        ag = client.call("agents")
        out[entry["session_id"]] = (st.get("result") if st.get("ok") else None,
                                    (ag.get("result") or {}).get("agents") if ag.get("ok") else None)
    except Exception:
        pass
    finally:
        if client is not None:
            client.close()


def sessions(list_live: Optional[Callable] = None) -> list:
    if list_live is None:
        from halo_harness.remote.registry import list_live
    try:
        entries = [e for e in list_live() if isinstance(e, dict) and e.get("session_id") and not e.get("private")]
    except Exception:
        entries = []
    got: dict = {}
    threads = [threading.Thread(target=_probe, args=(e, got), daemon=True, name="halo-fleet-probe") for e in entries]
    for t in threads:
        t.start()
    deadline = time.monotonic() + WAIT_S
    for t in threads:
        t.join(max(0.0, deadline - time.monotonic()))
    rows = [session_row(e, *got.get(e["session_id"], (None, None))) for e in entries]
    return sorted(rows, key=lambda r: (r.get("started") or 0, r.get("session_id") or ""))


def today_cost(rows: list) -> float:
    day = time.strftime("%Y-%m-%d")
    total = 0.0
    for r in rows:
        cost, started = r.get("cost_usd"), r.get("started")
        if isinstance(cost, (int, float)) and isinstance(started, (int, float)) \
                and time.strftime("%Y-%m-%d", time.localtime(started)) == day:
            total += float(cost)
    return round(total, 6)


def harness_entry(rows: list, home_dir=None) -> dict:
    """The local harness as a member of its own hub: Studio's direct path, the owner's own controls."""
    return {**identity.harness(home_dir), "local": True, "share": "full", "allow_control": "all",
            "allow_answers": True, "online": True, "last_seen": time.time(), "cost_today": today_cost(rows),
            "version_mismatch": False, "sessions": rows}


def snapshot(list_live: Optional[Callable] = None) -> dict:
    now = time.monotonic()
    with _lock:
        hit = _cache.get("local")
    if list_live is None and hit is not None and now - hit[0] < CACHE_S:
        return hit[1]
    entry = harness_entry(sessions(list_live))
    if list_live is None:
        with _lock:
            _cache["local"] = (now, entry)
    return entry
