"""halo_harness.providers.governor -- Halo 2.0.5 round 4: the Governor.

A MACHINE-GLOBAL, cross-process adaptive rate limiter that keeps a fleet
of callers from stomping a shared API gateway (the "every process on the
box trips the same 429" problem), ported from the owner's vendored kit
(plans/governor-import/governor-kit -- never imported; port it) with the
REVIEW.md changes applied. Persistence and locking live in
`governor_state.py`; this module is the algorithm and the public API.

Five properties (the owner's report, verbatim intent):

- cross-process: one shared token bucket per gateway HOST (two models on
  one gateway share one limit, because the gateway enforces it per
  machine), state on disk under a file lock.
- adaptive (AIMD): an overload status cuts `rate *= backoff_mult`, sets a
  cooldown honouring Retry-After (delta-seconds OR HTTP-date, capped at
  `retry_after_cap`), drains the bucket; `ramp_after` consecutive OKs add
  `ramp_inc` back toward the ceiling, never below `rate_floor`.
- concurrency-capped: a hard cross-process in-flight cap, self-healing
  (dead pids reaped at 180 s, a LIVE pid's permit only at 1800 s).
- priority-fair: when permits are scarce the highest-priority live
  waiter goes first (main session / orchestrator 0; judge, reviewer,
  verifier, tester, planner 1; every other agent 2; `governor.priorities`
  overrides; an agent bio's `limits.priority` (0-2) wins over the role).
- observable: every call logged (agent, role, session, model, status);
  `inspect`/`inspect_all`/`recent_calls`/`health` read it back.

Fail-open is ONE half-open probe for the front waiter after `max_wait`,
never a bail-out; the in-flight cap is never bypassed. Transport errors
release the permit neutrally (a dead network is not an overloaded
gateway); two caller-side timeouts in a row count as overload (one is a
blip). `acquire()` takes an `abort` callable (the turn's abort event) so
`/stop` and a steer interrupt a waiting request; `GovernorAborted` is
the turn's "interrupted", never an error. Status 500 is NEUTRAL unless
the body says overloaded -- a plain server bug must not cut the fleet's
rate (REVIEW item 6). `cc:`/`cx:` drive a CLI child, not HTTP: not
governed (docs say so).

The Governor paces and fails over; it never declines a request.
"""

from __future__ import annotations

import os
import socket
import time
import uuid
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from halo_harness.providers import governor_state as gs

# lower number = higher priority; the main session and orchestrator are
# served first under scarcity (REVIEW item 9: priorities come from the
# roles; the kit's static brood roles are gone).
ROLE_PRIORITIES: Dict[str, int] = {
    "orchestrator": 0, "main": 0,
    "judge": 1, "reviewer": 1, "verifier": 1, "tester": 1, "planner": 1,
}
DEFAULT_PRIORITY = 2

#: REVIEW item 6: 500 is neutral unless the body says overloaded; the
#: set is configurable (`overload_statuses`).
DEFAULT_OVERLOAD_STATUSES = frozenset({429, 529, 502, 503, 504})
_OVERLOAD_BODY_RE_TEXT = ("overloaded", "rate limit", "capacity")

_STALE_CALL_SECS = 180.0        # an in-flight entry from a DEAD pid older than this is reaped
_ABANDONED_CALL_SECS = 1800.0   # a LIVE pid's permit is only reaped after this long
_WAITER_STALE = 30.0            # a waiter that stops heartbeating is dropped
_MAX_SLEEP = 2.0                # never sleep longer than this per loop (stay responsive)
_HEARTBEAT_WRITE_S = 1.0        # REVIEW item 7: refresh the waiter hb at most this often


class GovernorError(Exception):
    pass


class GovernorAborted(Exception):
    """`acquire()` was interrupted through its `abort` callable -- the
    turn reports "interrupted", never an error."""


def pid_alive(pid: "Optional[int]") -> bool:
    """One implementation in the tree (REVIEW item 11): the existing
    zombie-aware, Windows-aware `bg_run.pid_alive`."""
    from halo_harness.bg_run import pid_alive as _alive
    return _alive(pid)


def key_for(entry: Dict[str, Any]) -> str:
    """Bucket key = the gateway HOST (hostname, port stripped -- the same
    `urlparse(url).hostname` the http.py choke point keys on, so a base
    URL with a port can never mint a second bucket for the same server),
    so every model on one gateway shares one limit (documented: two
    accounts on one host share a bucket on purpose -- the gateway
    throttles per machine). Keyless/local kinds key on provider name +
    host so a LAN model host is its own bucket."""
    url = entry.get("base_url") or ""
    host = (urlparse(url).hostname or "").lower() if url else ""
    if not host:
        return "provider:" + str(entry.get("name") or entry.get("kind") or "unknown")
    return "host:" + host


def params_for(entry: Dict[str, Any], tuning: "Optional[Dict[str, Any]]" = None) -> Dict[str, Any]:
    """Per-gateway tuning: entry keys win, then the shared tuning dict
    (Halo's `governor.*` config), then the documented defaults."""
    tuning = tuning or {}
    rate = float(entry.get("rate_rps", tuning.get("rate_rps", 8.0)))
    return {
        "rate_rps": rate,
        "burst": float(entry.get("burst", tuning.get("burst", 8))),
        "max_inflight": int(entry.get("max_inflight", tuning.get("max_inflight", 6))),
        "rate_floor": float(entry.get("rate_floor", tuning.get("rate_floor", 0.25))),
        "ramp_after": int(tuning.get("ramp_after", entry.get("ramp_after", 5))),
        "ramp_inc": float(tuning.get("ramp_inc", entry.get("ramp_inc", 0.5))),
        "backoff_mult": float(tuning.get("backoff_mult", entry.get("backoff_mult", 0.5))),
        "cooldown_base": float(tuning.get("cooldown_base", entry.get("cooldown_base", 2.0))),
        "retry_after_cap": float(tuning.get("retry_after_cap", entry.get("retry_after_cap", 120.0))),
        "max_wait": float(tuning.get("max_wait", entry.get("max_wait", 120.0))),
        "max_retries": int(tuning.get("max_retries", entry.get("max_retries", 5))),
    }


def priority_for(role: "Optional[str]", *, overrides: "Optional[Dict[str, int]]" = None,
                 explicit: "Optional[int]" = None) -> int:
    """An agent bio's own `limits.priority` (0-2, validated) wins over
    the role mapping; `governor.priorities` (config) overrides the
    built-in role table; the table itself maps the standing role split."""
    if isinstance(explicit, int) and 0 <= explicit <= 2:
        return explicit
    if overrides and isinstance(overrides.get(role or ""), int):
        return int(overrides[role])
    return ROLE_PRIORITIES.get((role or "").lower(), DEFAULT_PRIORITY)


def default_state(key: str, params: Dict[str, Any], now: float) -> Dict[str, Any]:
    ceiling = float(params.get("rate_rps", 2.0))
    burst = float(params.get("burst", max(1, int(ceiling))))
    return {
        "key": key, "schema": gs.STATE_SCHEMA,
        "rate": ceiling, "rate_ceiling": ceiling,
        "rate_floor": float(params.get("rate_floor", 0.25)),
        "burst": burst, "tokens": burst, "last_refill": now,
        "max_inflight": int(params.get("max_inflight", 2)),
        "inflight": {},        # call_id -> {pid, ts, agent, role, session, model}
        "waiters": {},         # ticket -> {priority, ts, hb, pid, agent, role}
        "cooldown_until": 0.0,
        "consecutive_ok": 0, "consecutive_err": 0, "consecutive_timeouts": 0,
        "last_status": None, "last_event": None, "updated": now,
    }


def is_overload_status(status: "Optional[int]", *, statuses=None) -> bool:
    """429/529/502/503/504 (configurable). 500 is NOT in the set -- a
    plain server bug must not cut the fleet's rate unless the body says
    overloaded (`is_overload_body`)."""
    if not isinstance(status, int):
        return False
    return status in (statuses or DEFAULT_OVERLOAD_STATUSES)


def is_overload_body(body_text: "Optional[str]") -> bool:
    text = (body_text or "").lower()
    return any(k in text for k in _OVERLOAD_BODY_RE_TEXT)


def retry_after_seconds(headers: "Optional[Dict[str, str]]", *, cap: float = 120.0) -> "Optional[float]":
    """REVIEW item 2: both delta-seconds AND the HTTP-date form, capped
    at `retry_after_cap` (default 120 s) so one hostile header cannot
    freeze the fleet. None when absent or unparseable."""
    for k, v in (headers or {}).items():
        if k.lower() == "retry-after":
            try:
                return min(max(0.0, float(v)), cap)
            except (TypeError, ValueError):
                try:
                    from datetime import datetime, timezone
                    dt = parsedate_to_datetime(str(v))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    delta = (dt - datetime.now(timezone.utc)).total_seconds()
                    return min(max(0.0, delta), cap) if delta >= 0 else 0.0
                except (TypeError, ValueError):
                    return None
    return None


def _reap(st: Dict[str, Any], now: float) -> None:
    """Self-healing: a killed caller cannot leak a permit. A LIVE
    process is only reaped at _ABANDONED_CALL_SECS (reaping it earlier
    silently exceeded max_inflight for any call slower than that)."""
    for cid in list(st["inflight"].keys()):
        e = st["inflight"][cid]
        age = now - e.get("ts", now)
        if not pid_alive(e.get("pid")):
            del st["inflight"][cid]
        elif age > _ABANDONED_CALL_SECS:
            import warnings
            warnings.warn(f"governor: reaping an in-flight entry {age:.0f}s old whose process "
                          "is still alive -- assuming it was abandoned")
            del st["inflight"][cid]
    for tk in list(st["waiters"].keys()):
        w = st["waiters"][tk]
        if not pid_alive(w.get("pid")) or (now - w.get("hb", w.get("ts", now))) > _WAITER_STALE:
            del st["waiters"][tk]


def _refill(st: Dict[str, Any], now: float) -> None:
    dt = max(0.0, now - st.get("last_refill", now))
    st["tokens"] = min(st["burst"], st.get("tokens", 0.0) + st["rate"] * dt)
    st["last_refill"] = now


def _is_front(st: Dict[str, Any], ticket: str) -> bool:
    """The highest-priority (then earliest) live waiter takes a scarce
    permit: orchestrator before worker, FIFO within a level."""
    mine = st["waiters"].get(ticket)
    if mine is None:
        return True
    best = min(st["waiters"].values(), key=lambda w: (w.get("priority", 9), w.get("ts", 0.0)))
    return (mine.get("priority", 9), mine.get("ts", 0.0)) == (best.get("priority", 9), best.get("ts", 0.0))


class Handle:
    def __init__(self, key: str, call_id: str, agent: str, role: str, start: float, waited: float,
                 session: "Optional[str]" = None, model: "Optional[str]" = None):
        self.key = key
        self.call_id = call_id
        self.agent = agent
        self.role = role
        self.session = session
        self.model = model
        self.start = start
        self.waited = waited


def acquire(key: str, params: Dict[str, Any], *, agent: str = "system", role: str = "worker",
            max_wait: "Optional[float]" = None, abort: "Optional[Callable[[], bool]]" = None,
            priority_overrides: "Optional[Dict[str, int]]" = None, explicit_priority: "Optional[int]" = None,
            session: "Optional[str]" = None, model: "Optional[str]" = None,
            on_event: "Optional[Callable[[Dict[str, Any]], None]]" = None) -> Handle:
    """Block (pacing, priority-fair) until a permit is granted. Fail-open
    after `max_wait`, but ONLY for the front-of-queue (highest-priority)
    waiter, as a single half-open probe; the in-flight cap is never
    bypassed. `abort` (REVIEW item 3, the turn's abort event) is checked
    every loop: on abort the waiter is deregistered and
    `GovernorAborted` raises -- "interrupted", never an error. A `waiting`
    event (queue position, cooldown remaining, current rate) goes through
    `on_event` so the liveness line can say "gateway cooling, 12 s, 2
    ahead of you"."""
    if max_wait is None:
        max_wait = float(params.get("max_wait", 120.0))
    ticket = uuid.uuid4().hex[:12]
    call_id = uuid.uuid4().hex[:12]
    prio = priority_for(role, overrides=priority_overrides, explicit=explicit_priority)
    t0 = time.time()
    last_hb_write = 0.0
    with gs._Lock(key):
        st = gs.load(key, params, t0)
        _reap(st, t0)
        st["waiters"][ticket] = {"priority": prio, "ts": t0, "hb": t0, "pid": os.getpid(),
                                 "agent": agent, "role": role}
        gs.save(key, st)
    try:
        while True:
            if abort is not None and abort():
                raise GovernorAborted(f"governor wait for {key} interrupted")
            now = time.time()
            took = False
            with gs._Lock(key):
                st = gs.load(key, params, now)
                _reap(st, now)
                mine = st["waiters"].get(ticket)
                if mine is None:
                    st["waiters"][ticket] = {"priority": prio, "ts": t0, "hb": now,
                                             "pid": os.getpid(), "agent": agent, "role": role}
                    # 2.0.5 release-review finding 7: a re-registered
                    # waiter (reaped by another process between passes)
                    # must persist NOW -- without `took` the write only
                    # happened on the 1 s "updated" fallback, so the
                    # re-registration itself was never saved and the
                    # next pass found the waiter gone again.
                    took = True
                elif now - mine.get("hb", 0) >= _HEARTBEAT_WRITE_S:
                    mine["hb"] = now  # REVIEW item 7: at most one hb write per second
                    last_hb_write = now
                    took = True
                _refill(st, now)
                cooling = now < st.get("cooldown_until", 0.0)
                inflight_full = len(st["inflight"]) >= st["max_inflight"]
                have_token = st["tokens"] >= 1.0
                front = _is_front(st, ticket)
                failopen = (now - t0) >= max_wait and front
                grant = front and not inflight_full and ((not cooling and have_token) or failopen)
                if grant:
                    if have_token and not failopen:
                        st["tokens"] -= 1.0
                    st["inflight"][call_id] = {"pid": os.getpid(), "ts": now, "agent": agent,
                                               "role": role, "session": session, "model": model}
                    st["waiters"].pop(ticket, None)
                    gs.save(key, st)
                    return Handle(key, call_id, agent, role, now, now - t0, session, model)
                if cooling:
                    wait = st["cooldown_until"] - now
                elif not front:
                    wait = 0.15
                elif inflight_full:
                    wait = 0.2
                else:
                    wait = (1.0 - st["tokens"]) / max(st["rate"], 1e-6)
                if on_event is not None and (now - t0) >= 0.5 and front:
                    ahead = sum(1 for w in st["waiters"].values()
                                if (w.get("priority", 9), w.get("ts", 0)) < (prio, t0))
                    on_event({"event": "waiting", "key": key, "position": ahead + 1,
                              "cooldown_remaining": round(max(0.0, st.get("cooldown_until", 0.0) - now), 1),
                              "rate": round(st["rate"], 3)})
                # REVIEW item 7: skip the save when nothing but the read
                # changed (no hb write this pass, no waiter mutation).
                if took or st.get("updated", 0) < now - 1.0:
                    gs.save(key, st)
            time.sleep(max(0.02, min(_MAX_SLEEP, wait)))
    except BaseException:
        try:
            with gs._Lock(key):
                st = gs.load(key, params, time.time())
                st["waiters"].pop(ticket, None)
                gs.save(key, st)
        except Exception:
            pass
        raise


def report(handle: Handle, ok: "Optional[bool]", status: "Optional[int]" = None,
           retry_after: "Optional[float]" = None, params: "Optional[Dict[str, Any]]" = None,
           *, timeout_signal: bool = False) -> Dict[str, Any]:
    """Record the outcome and adapt; returns telemetry for the caller.

    ok=True  -> success; ramps the rate back after `ramp_after` in a row.
    ok=False -> overload; multiplicative cut + cooldown (honouring
                Retry-After), bucket drained.
    ok=None  -> NEUTRAL release: free the permit, touch NEITHER counter.
                A transport failure is not evidence about the server's
                load -- reporting it as success would ramp the rate up
                while the gateway is failing.

    `timeout_signal=True` with ok=None marks a caller-side timeout: TWO
    in a row count as overload (REVIEW item 7's twin from the round
    brief: one timeout is a network blip, two is a struggling gateway).
    """
    params = params or {}
    now = time.time()
    event: "Optional[str]" = None
    with gs._Lock(handle.key):
        st = gs.load(handle.key, params, now)
        st["inflight"].pop(handle.call_id, None)
        st["last_status"] = status
        prev_rate = st["rate"]
        if ok is None:
            if timeout_signal:
                st["consecutive_timeouts"] = st.get("consecutive_timeouts", 0) + 1
                if st["consecutive_timeouts"] >= 2:
                    st["consecutive_timeouts"] = 0
                    st["consecutive_err"] += 1
                    st["rate"] = max(st["rate_floor"], st["rate"] * float(params.get("backoff_mult", 0.5)))
                    base = float(params.get("cooldown_base", 2.0))
                    backoff = base * (2 ** min(st["consecutive_err"] - 1, 6))
                    st["cooldown_until"] = max(st.get("cooldown_until", 0.0), now + backoff)
                    st["tokens"] = 0.0
                    event = "throttle"
            else:
                st["consecutive_timeouts"] = 0
        elif ok:
            st["consecutive_ok"] += 1
            st["consecutive_err"] = 0
            st["consecutive_timeouts"] = 0
            if st["consecutive_ok"] >= int(params.get("ramp_after", 5)):
                st["consecutive_ok"] = 0
                inc = float(params.get("ramp_inc", 0.5))
                if st["rate"] < st["rate_ceiling"]:
                    st["rate"] = min(st["rate_ceiling"], st["rate"] + inc)
                    event = "recover"
        else:
            st["consecutive_err"] += 1
            st["consecutive_ok"] = 0
            st["consecutive_timeouts"] = 0
            st["rate"] = max(st["rate_floor"], st["rate"] * float(params.get("backoff_mult", 0.5)))
            base = float(params.get("cooldown_base", 2.0))
            backoff = base * (2 ** min(st["consecutive_err"] - 1, 6))
            cap = float(params.get("retry_after_cap", 120.0))
            cd = max(min(retry_after or 0.0, cap), backoff)
            st["cooldown_until"] = max(st.get("cooldown_until", 0.0), now + cd)
            st["tokens"] = 0.0
            event = "throttle"
        telem = {
            "key": handle.key, "event": event, "ok": ok, "status": status,
            "rate": round(st["rate"], 3), "rate_ceiling": st["rate_ceiling"],
            "prev_rate": round(prev_rate, 3),
            "cooldown_remaining": round(max(0.0, st.get("cooldown_until", 0.0) - now), 1),
            "inflight": len(st["inflight"]), "waited": round(handle.waited, 2),
            "agent": handle.agent, "role": handle.role,
            "session": handle.session, "model": handle.model,
            "degraded": gs.is_degraded(),
        }
        st["last_event"] = telem
        gs.save(handle.key, st)
        gs.append_log(handle.key, {**telem, "ts": now, "call_id": handle.call_id})
    return telem


def governed(key: str, params: Dict[str, Any], do_call: Callable[[], Tuple[int, Any, Dict[str, str]]],
             *, agent: str = "system", role: str = "worker", session: "Optional[str]" = None,
             model: "Optional[str]" = None, on_event: "Optional[Callable[[Dict[str, Any]], None]]" = None,
             abort: "Optional[Callable[[], bool]]" = None) -> Tuple[int, Any]:
    """One gateway call under the Governor: acquire, execute, report,
    transparently pace+retry through 429/overload (the retry ladder the
    agent loop used to own for governed routes). Transport errors
    propagate after a NEUTRAL release; a timeout releases with
    `timeout_signal` (two in a row cut the rate) and propagates."""
    max_retries = int(params.get("max_retries", 5))
    attempt = 0
    while True:
        h = acquire(key, params, agent=agent, role=role, abort=abort,
                    session=session, model=model, on_event=on_event)
        try:
            status, body, headers = do_call()
        except (TimeoutError, socket.timeout):
            telem = report(h, ok=None, status=None, params=params, timeout_signal=True)
            if telem.get("event") and on_event:
                on_event(telem)
            raise
        except GovernorAborted:
            raise
        except Exception:
            report(h, ok=None, params=params)  # neutral: not evidence about load
            raise
        body_text = body if isinstance(body, str) else ""
        overloaded = is_overload_status(status, statuses=params.get("overload_statuses")) or \
            (status == 500 and is_overload_body(body_text))
        retry_after = retry_after_seconds(headers, cap=float(params.get("retry_after_cap", 120.0))) if overloaded else None
        telem = report(h, ok=not overloaded, status=status, retry_after=retry_after, params=params)
        if telem.get("event") and on_event:
            on_event(telem)
        if not overloaded:
            return status, body
        attempt += 1
        if attempt > max_retries:
            return status, body  # give the caller the last 429 to surface
        # loop: acquire() now waits out the cooldown just set


def inspect(key: str) -> "Optional[Dict[str, Any]]":
    """The bucket's current shape, for `/gov` and `halo gov`. Reads
    WITHOUT the lock (the atomic-replace retry in governor_state absorbs
    the transient PermissionError a racing writer causes on Windows)."""
    try:
        with open(gs.paths(key)[0], "r", encoding="utf-8") as fh:
            import json
            st = json.load(fh)
    except (FileNotFoundError, ValueError, OSError):
        st = gs._MEM_STATE.get(key)
        if st is None:
            return None
    now = time.time()
    return {
        "key": st.get("key", key), "rate": round(st.get("rate", 0), 3),
        "rate_ceiling": st.get("rate_ceiling"), "max_inflight": st.get("max_inflight"),
        "inflight": len(st.get("inflight", {})), "waiting": len(st.get("waiters", {})),
        "cooldown_remaining": round(max(0.0, st.get("cooldown_until", 0.0) - now), 1),
        "consecutive_err": st.get("consecutive_err", 0),
        "consecutive_ok": st.get("consecutive_ok", 0), "last_status": st.get("last_status"),
        "last_event": st.get("last_event"),
        "degraded": gs.is_degraded(),
    }


def health(key: str, open_cooldown: float = 8.0, degraded_err: int = 3) -> str:
    """`open` (in a real cooldown or erroring hard -- skip for pivots),
    `degraded` (paced well below ceiling), `ok`, `unknown`."""
    st = inspect(key)
    if st is None:
        return "unknown"
    if st["cooldown_remaining"] > open_cooldown or st.get("consecutive_err", 0) >= degraded_err:
        return "open"
    ceiling = st.get("rate_ceiling") or 0
    if ceiling and st["rate"] < 0.5 * ceiling:
        return "degraded"
    return "ok"


def inspect_all() -> List[Dict[str, Any]]:
    """Every bucket with state on disk, for `/gov`'s table."""
    out: List[Dict[str, Any]] = []
    d = gs.state_dir()
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return out
    for fn in names:
        if not fn.endswith(".json") or fn.endswith(".tmp"):
            continue
        try:
            import json
            with open(d / fn, "r", encoding="utf-8") as fh:
                st = json.load(fh)
        except (ValueError, OSError):
            continue
        got = inspect(st.get("key", fn))
        if got:
            out.append(got)
    return out


def recent_calls(key: str, limit: int = 30) -> List[Dict[str, Any]]:
    return gs.read_recent_calls(key, limit)
