"""halo_harness.studio.fleet_panels_api -- the Fleet panels' routes (Halo
3.0.5.0 "Fleet" round R4), appended to studio/fleet_hub_api.py's ROUTES; the
same loopback + token guard as every Studio route. The first call starts the
server's fleet watcher (studio/fleet_watch.py).

    GET  fleet/attention             {rows: [row, ...], count, at}    fleet/attention.py's rows, oldest first
    POST fleet/attention/answer {id, key: a|r|s|o, text?}
                                     -> {ok, id, kind, key, answer, result | open | set_aside | lifted}
                                        routed by studio/fleet_answer.py; the decision is journaled with `by`
    GET  fleet/costs                 {fleet, harnesses, projects, sessions, caps, reached, lifted, balances}
    GET  fleet/caps                  {caps: {per_harness_usd_per_day, per_project_usd_per_day, fleet_usd_per_day},
                                      keys, reached, lifted}
    POST fleet/caps {<key>: dollars | 0 | null, ...}   writes fleet.caps.<key> (0 or null: no cap)
    GET  fleet/health[?refresh=1]    {harnesses: [{id, name, local, online, cached, status, version, providers,
                                                   disk, sockets, studio, checked, note?}]}  60 s cache
    GET  fleet/conflicts             {conflicts: [...], rooms: [...], touches: [...]}
    GET  fleet/digest?since=<2h | 45m | 1d | unix seconds or ms | ISO>   fleet/digest.py's digest (default 1d)

A member's health is its `status` and `doctor` answers through the hub (one
live session of it, read-only: `doctor` is in the protocol's READ_CMDS).
"""

from __future__ import annotations

import threading
import time

from halo_harness.fleet import caps, journal
from halo_harness.studio import fleet_watch_sources as sources
from halo_harness.studio import fleet_send as send

MEMBER_WAIT_S = 8.0


def _watcher(req):
    from halo_harness.studio.fleet_watch import watcher_for
    return watcher_for(req.server, req.state_dir)


def get_attention(req):
    rows = _watcher(req).snapshot()
    return 200, {"rows": rows, "count": len(rows), "at": time.time()}


def post_answer(req):
    from halo_harness.studio.fleet_answer import NEEDS_TEXT, act
    body = req.body if isinstance(req.body, dict) else {}
    rid, key, text = str(body.get("id") or ""), str(body.get("key") or ""), str(body.get("text") or "").strip()
    w = _watcher(req)
    row = next((r for r in w.rows if r["id"] == rid), None) or next((r for r in w.snapshot(0.0) if r["id"] == rid), None)
    if row is None:
        return 404, {"error": f"no attention row {rid!r} (answered already, or gone)"}
    if key not in row["keys"]:
        return 422, {"error": f"a {row['kind']} row takes {', '.join(row['keys'])}, got {key!r}", "problems": []}
    if (row["kind"], key) in NEEDS_TEXT and not text and row.get("text_for"):  # 3.3.5.0 R4: a preflight row takes none
        return 422, {"error": f"{row['keys'][key]} needs text", "problems": []}
    status, got, label = act(req, w, row, key, text)
    out = {"ok": status < 300, "id": rid, "kind": row["kind"], "key": key, "answer": label}
    if status >= 300:
        return status, {**out, "error": (got or {}).get("error") or f"{label} failed", "result": got}
    if key != "o":
        w.done(rid)
        journal.append(w.home, "decision", harness=row.get("harness"), harness_name=row.get("harness_name"),
                       session_id=row.get("session_id"), agent_id=row.get("agent_id"), row_kind=row["kind"],
                       what=row.get("what"), answer=label + (f": {text[:200]}" if text else ""), by=sources.by(req.state_dir))
    extra = {k: got[k] for k in ("open", "set_aside", "lifted", "resumed") if isinstance(got, dict) and k in got}
    return status, {**out, **extra, "result": got}


def _caps_state(w, view: dict) -> dict:
    cfg = caps.config(w.home)
    reached = caps.reached(view, cfg)
    day = journal.day()
    lifted = sorted(k for k, d in w.lifted.items() if d == day)
    return {"caps": cfg, "keys": list(caps.KEYS), "reached": [{**r, "lifted": caps.cap_id(r["scope"], r["key"]) in lifted}
                                                              for r in reached], "lifted": lifted}


def get_costs(req):
    w = _watcher(req)
    w.snapshot()
    try:
        from halo_harness.providers.balances import cached_balances
        balances = cached_balances(req.state_dir)  # read-only: the balances workers' last answers
    except Exception:
        balances = {}
    return 200, {**caps.spend(w.view), **_caps_state(w, w.view), "balances": balances}


def get_caps(req):
    w = _watcher(req)
    w.snapshot()
    return 200, _caps_state(w, w.view)


def post_caps(req):
    from halo_harness.fleet import identity
    from halo_harness.studio.fleet_pair_api import _set_config
    body = req.body if isinstance(req.body, dict) else {}
    changes, bad = {}, []
    for k in caps.KEYS:
        if k not in body:
            continue
        v = body[k]
        try:
            f = None if v in (None, "") else float(v)
        except (TypeError, ValueError):
            f = -1.0
        if f is not None and f < 0:
            bad.append(f"{k} is dollars per day (0 or null: no cap), got {v!r}")
        changes[k] = None if not f else f
    if bad or not changes:
        return 422, {"error": bad[0] if bad else f"send one of {', '.join(caps.KEYS)}", "problems": bad}
    try:
        for k, v in changes.items():
            _set_config(_watcher(req).home, f"fleet.caps.{k}", v)
    except Exception as e:  # a config.json that does not parse is never overwritten
        return 409, {"error": f"config.json was not changed: {e}"}
    identity.forget_cache()
    w = _watcher(req)
    w.tick()
    return 200, _caps_state(w, w.view)


def _member_health(req, h: dict, refresh: bool) -> dict:
    from halo_harness.fleet import health
    sids = [s.get("session_id") for s in h.get("sessions") or [] if s.get("session_id")]
    if not h.get("online") or not sids:
        return {"status": "unknown", "note": "offline" if not h.get("online") else "no live session to ask", "cached": False}

    def fetch() -> dict:
        got = {}
        for cmd in ("status", "doctor"):
            status, body = send.member_cmd(req.server, req.state_dir, str(h["id"]), sids[0], cmd, {}, MEMBER_WAIT_S)
            got[cmd] = (body or {}).get("result") if status == 200 else None
        out = health.member_subset(got["status"], got["doctor"])
        if got["doctor"] is None:
            out["note"] = "the member did not answer `doctor` (an older Halo, or the hub could not reach it)"
        return out
    value, hit = health.cached(f"member:{h['id']}", fetch, refresh)
    return {**value, "cached": hit}


def get_health(req):
    from halo_harness.fleet import health
    refresh = str(req.query.get("refresh") or "") in ("1", "true", "yes")
    view = sources.view(req.server, req.state_dir)
    rows: list = [None] * len(view.get("harnesses") or [])

    def one(i: int, h: dict) -> None:
        base = {k: h.get(k) for k in ("id", "name", "local", "online", "version", "host", "os")}
        if h.get("local"):
            value, hit = health.cached("local", health.subset, refresh)
            rows[i] = {**value, **base, "cached": hit}
        else:
            rows[i] = {**base, **_member_health(req, h, refresh), "id": h.get("id"), "name": h.get("name")}
    threads = [threading.Thread(target=one, args=(i, h), daemon=True, name="halo-fleet-health")
               for i, h in enumerate(view.get("harnesses") or [])]
    for t in threads:
        t.start()
    for t in threads:
        t.join(2 * MEMBER_WAIT_S + 4)
    return 200, {"harnesses": [r for r in rows if r is not None], "cache_s": health.CACHE_S}


def get_conflicts(req):
    from halo_harness.fleet.conflicts import rooms
    w = _watcher(req)
    w.snapshot()
    touches = [{"harness": h, "session_id": s, "agent_id": a, "file": f, "repo": repo, "ts": ts}
               for h, s, a, f, repo, ts in w.touches.items()]
    return 200, {"conflicts": w.conflicts, "rooms": rooms(w.view), "touches": touches}


def get_digest(req):
    from halo_harness.fleet import digest, identity
    try:
        since = digest.parse_since(req.query.get("since") or "1d")
    except ValueError as e:
        return 422, {"error": str(e), "problems": []}
    w = _watcher(req)
    w.snapshot()
    live = [s.get("session_id") for h in w.view.get("harnesses") or [] if h.get("local") for s in h.get("sessions") or []]
    return 200, digest.compute(w.home, since, local_id=w.local_id, local_name=identity.fleet_name(w.home), live_ids=live)


ROUTES = [("GET", r"^fleet/attention$", get_attention),
          ("POST", r"^fleet/attention/answer$", post_answer),
          ("GET", r"^fleet/costs$", get_costs),
          ("GET", r"^fleet/caps$", get_caps),
          ("POST", r"^fleet/caps$", post_caps),
          ("GET", r"^fleet/health$", get_health),
          ("GET", r"^fleet/conflicts$", get_conflicts),
          ("GET", r"^fleet/digest$", get_digest)]
