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
     cost_complete, cost_unknown,
     agents_live, agents: [agent row, ...], turns, tokens_in, tokens_out, context_tokens, context_limit,
     composition, preflight (3.3.5.0 R4: the last request's parts, agent/prompt_composition.ledger_fields;
     the preflight card waiting for an answer, {id, line, switch_to, default})}

(3.3.3.1: `cost_usd` is the priced part of the spend, `cost_complete` False
when some model answered with no price, `cost_unknown` those models' refs;
None / [] when the session has not said.)

(3.1.4.0 R2: turns, the tokens and the context are the status's own, for
Studio's Session Cost panel; None when the session has not said. 3.1.5.0
R3: each agent row also carries its own `tokens_in` / `tokens_out`, summed
from its transcript's usage lines by fleet/agent_tokens.py.)

`snapshot()` keeps its answer CACHE_S; `forget()` drops it (3.1.8.0 R6:
studio/events.py calls it on a local session's turn_done, message_end and
status frame, so a GET right after one never answers from before it).
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from halo_harness.fleet import identity
from halo_harness.fleet.agent_tokens import with_tokens

TIMEOUT_S = 1.0
WAIT_S = 1.5
CACHE_S = 1.0
_cache: dict = {}
_gen = [0]  # bumped by forget(): a snapshot read while it moved is never cached
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
               cost_complete=data.get("cost_complete") if isinstance(data.get("cost_complete"), bool) else None,
               cost_unknown=[str(m) for m in data.get("cost_unknown") or [] if m] if isinstance(
                   data.get("cost_unknown"), list) else [],
               remote_attached=data.get("remote_attached") if isinstance(data.get("remote_attached"), int) else 0,
               agents_live=live if isinstance(live, int) and not isinstance(live, bool) else 0,
               agents=with_tokens([a for a in (agents or []) if isinstance(a, dict)]),
               turns=_num(data.get("turn")), tokens_in=_num(data.get("total_input_tokens")),
               tokens_out=_num(data.get("total_output_tokens")), context_tokens=_num(data.get("context_tokens")),
               context_limit=_num(data.get("context_limit")),
               effort=data.get("effort") if isinstance(data.get("effort"), str) else None,  # 3.3.5.0 R0 (e)
               composition=data.get("composition") if isinstance(data.get("composition"), dict) else None,  # R4
               preflight=data.get("preflight") if isinstance(data.get("preflight"), dict) else None)  # R4: the ask
    return row


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


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


def forget() -> None:
    """Drop the cached snapshot (3.1.8.0 R6: Studio's event bridge, on a local session's turn_done /
    message_end / status, so the next GET fleet reads the sessions again instead of a snapshot from before it)."""
    with _lock:
        _cache.clear()
        _gen[0] += 1


def snapshot(list_live: Optional[Callable] = None) -> dict:
    now = time.monotonic()
    with _lock:
        hit, gen = _cache.get("local"), _gen[0]
    if list_live is None and hit is not None and now - hit[0] < CACHE_S:
        return hit[1]
    entry = harness_entry(sessions(list_live))
    if list_live is None:
        with _lock:
            if _gen[0] == gen:
                _cache["local"] = (now, entry)
    return entry
