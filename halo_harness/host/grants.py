"""halo_harness.host.grants -- per-peer grants on a halo host (Halo 3.3.7.0 R2; docs/HOST.md "Grants").

A peer holds `view` from its join on. The host's owner adds `control`, `manage` or `admin` per peer (`halo host grant
<peer> <grant>`, peers.json's per-peer `grants` list). `manage` carries `control`'s operations too; `admin` is never
implied by `manage` (its own grant, and its operations are not part of this version). The host machine's
`fleet.allow_control` caps every grant:

    none   view only, for every peer: the host is strictly a monitor
    ask    (the default) a control / manage request is queued as a pending row in <state>/host/pending.jsonl for
           `host.ask_ttl_s` (600 s); the owner answers it (`halo host pending`, `halo host allow <id> | deny <id>`, or
           the Hosts card of that machine's Studio); once allowed, the same request from that peer within the TTL
           runs. A dry preview lands nothing and is not queued.
    all    the grants apply as given

The duty steward's own peer record carries `duty: true` (`halo host steward on`: the owner's own choice), so `ask`
does not queue its requests; `none` caps it like any peer.

    holds(grants, grant) / cap(home) / decide(home, hid, rec, grant, op, body) -> (200, None) | (403 | 202, payload)
    grant(home, who, g) / revoke(home, who, g) -> (ok, line)     peers(home) -> [{name, id, grants, last_seen, ...}]
    request(home, hid, rec, grant, why) / pending(home) / answer(home, id, allow) / me(home, hid)
"""

from __future__ import annotations

import time
from typing import Optional

from halo_harness.host import pending as P
from halo_harness.host import state as S

LEVELS = ("none", "ask", "all")


def holds(grants, grant: str) -> bool:
    have = set(grants or ())
    return grant in have or (grant == "control" and "manage" in have) or grant == "view"


def cap(home) -> str:
    raw = S._cfg("fleet.allow_control", "ask", home)
    return raw if raw in LEVELS else "ask"


def grants_of(rec: Optional[dict]) -> tuple:
    got = (rec or {}).get("grants")
    return tuple(g for g in got if g in S.GRANTS) if isinstance(got, list) else S.DEFAULT_GRANTS


def _host_name(home) -> str:
    from halo_harness.fleet import identity
    return identity.fleet_name(home)


def _name(rec: Optional[dict], hid: str = "") -> str:
    return str((rec or {}).get("name") or hid[:8] or "this peer")


def missing_line(grant: str, op: str, rec: Optional[dict], home) -> str:
    who = _name(rec)
    return (f"{who} holds no `{grant}` grant on {_host_name(home)}: {op} is a {grant} operation; the owner runs "
            f"`halo host grant {who} {grant}` there")


def none_line(home) -> str:
    return (f"fleet.allow_control is none on {_host_name(home)}: the host is strictly a monitor, view only for every "
            "peer (`halo config set fleet.allow_control ask` or `all` there)")


def decide(home, hid: str, rec: Optional[dict], grant: str, op: str, body: dict, *,
           now: Optional[float] = None) -> "tuple[int, Optional[dict]]":
    """(200, None): go ahead; (403, {error, grant}) or (202, {pending, line, expires})."""
    now = time.time() if now is None else now
    if not holds(grants_of(rec), grant):
        return 403, {"error": missing_line(grant, op, rec, home), "grant": grant}
    level = cap(home)
    if level == "none":
        return 403, {"error": none_line(home), "grant": grant, "cap": "none"}
    if level == "ask" and grant in ("control", "manage") and not (rec or {}).get("duty") and body.get("dry") is not True:
        params = body.get("params") if isinstance(body.get("params"), dict) else {}
        if P.spend(home, hid, op, params, now):
            return 200, None
        row = P.queue(home, hid, rec or {}, "op", grant, op, body, now)
        return 202, {"pending": row["id"], "line": P.queued_line(home, row, now), "expires": row["expires"],
                     "cap": "ask", "grant": grant}
    return 200, None


def request(home, hid: str, rec: Optional[dict], grant: str, why: str = "", *, now: Optional[float] = None) -> "tuple[int, dict]":
    """A peer asks the owner for a grant (the Hosts card's "request control"): a pending row of kind `grant`."""
    now = time.time() if now is None else now
    if grant not in S.GRANTS or grant == "view":
        return 422, {"error": f"{grant!r} is not a grant to ask for (control, manage, admin)"}
    if holds(grants_of(rec), grant):
        return 200, {"ok": True, "line": f"{_name(rec, hid)} already holds `{grant}` on {_host_name(home)}"}
    if cap(home) == "none":
        return 403, {"error": none_line(home), "cap": "none"}
    row = P.queue(home, hid, rec or {}, "grant", grant, f"grant {grant}", {"why": why}, now)
    return 202, {"pending": row["id"], "line": P.queued_line(home, row, now), "expires": row["expires"]}


# ---- the owner's commands -----------------------------------------------------------------------

def _find(home, who: str) -> "tuple[Optional[dict], str]":
    pairing = S.HostPairing(home)
    rec = pairing.member(who)
    hits = [rec] if rec else pairing.find(who)
    if not hits:
        return None, f"no peer of this host matches {who!r} (`halo host peers` lists them)"
    if len(hits) > 1:
        return None, f"{who!r} matches {len(hits)} peers: name one by its id"
    return hits[0], ""


def grant(home, who: str, g: str) -> "tuple[bool, str]":
    if g not in S.GRANTS:
        return False, f"{g!r} is not a grant ({', '.join(S.GRANTS)})"
    rec, why = _find(home, who)
    if rec is None:
        return False, why
    have = list(grants_of(rec))
    if g not in have:
        have.append(g)
    S.HostPairing(home).update_member(rec["id"], grants=have)
    line = f"{rec.get('name')} holds {', '.join(have)} on {_host_name(home)}"
    if g == "admin":
        line += " (admin operations are not part of this version: the grant only shows what it would mean)"
    level = cap(home)
    if level != "all" and g in ("control", "manage"):
        line += f"; fleet.allow_control is {level} here" + (": view only for every peer" if level == "none" else
                                                              ": each request is queued for you first")
    return True, line


def revoke(home, who: str, g: str) -> "tuple[bool, str]":
    if g == "view":
        return False, "view is every paired peer's grant (unpair the peer to take it away)"
    rec, why = _find(home, who)
    if rec is None:
        return False, why
    have = [x for x in grants_of(rec) if x != g]
    S.HostPairing(home).update_member(rec["id"], grants=have or list(S.DEFAULT_GRANTS))
    return True, f"{rec.get('name')} holds {', '.join(have or S.DEFAULT_GRANTS)} on {_host_name(home)}"


def peers(home) -> list:
    rows = S.HostPairing(home).members()
    seen: dict = {}
    for a in S.read_audit(home, limit=20000):
        who = str(a.get("peer") or "")
        s = seen.setdefault(who, {"last": None, "n": 0})
        s["n"] += 1
        s["last"] = a.get("at")
    out = []
    for hid, r in rows.items():
        s = seen.get(str(r.get("name") or "")) or seen.get(hid[:8]) or {"last": None, "n": 0}
        out.append({"name": r.get("name"), "id": hid, "grants": list(grants_of(r)), "last_seen": s["last"],
                    "requests": s["n"], "duty": bool(r.get("duty"))})
    return sorted(out, key=lambda r: str(r["name"] or "").lower())


def me(home, hid: str) -> dict:
    rec = S.HostPairing(home).member(hid) or {}
    have, level = list(grants_of(rec)), cap(home)
    acts = ["view"] if level == "none" else have
    return {"name": rec.get("name"), "id": hid, "grants": have, "cap": level, "effective": acts,
            "asks": level == "ask" and not rec.get("duty") and any(holds(have, g) for g in ("control", "manage")),
            "duty": bool(rec.get("duty")), "pending": P.pending(home, peer=hid)}


def answer(home, pid: str, allow: bool, **kw):
    return P.answer(home, pid, allow, **kw)


pending = P.pending
ask_ttl_s = P.ask_ttl_s
