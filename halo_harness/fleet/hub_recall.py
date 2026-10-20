"""halo_harness.fleet.hub_recall -- the hub's side of recall across the fleet
(Halo 3.1.2.0 R3; recall_fleet.py is the member's side and the CLI).

`merged(hub, query, k, by=...)` sends the read-only `recall` command
`{query, k}` to one live session of every online member at once, waits at
most WAIT_S for each, labels every hit with the hub's name for that
harness, and merges them by score with this harness's own hits:

    {"query", "k", "hits": [{score, title, kind, excerpt, harness}], "at",
     "harnesses": [{harness, name, local?, state: answered | not_shared | offline | no_session | timeout | error,
                    hits, note?, seconds?}]}

Routes on the hub port (fleet/hub_http.py hands them here):

    POST /fleet/v1/local/recall  loopback + the hub's admin token: `{query, k}` from this machine's
                                 `halo recall --fleet` (a `halo fleet serve` or Studio in another process)
    POST /fleet/v1/recall        a member's signed `{query, k}`: every OTHER member and this harness
                                 (when it shares) answer; the asking member adds its own hits
    POST /fleet/v1/local/coach-library  3.1.6.0 R3, loopback + the admin token: `{harness, entry}` from this
                                 machine's `halo coach library fetch`; one live session of that member answers its
                                 `coach_library {entry}` command (orchestra/coach_library_share.py), passed back as is
"""

from __future__ import annotations

import threading
import time
from typing import Optional

WAIT_S = 8.0
SKIP_KINDS = ("mission-worker", "orchestra-worker")


def _session(h: dict) -> Optional[str]:
    rows = list(h.get("sessions") or [])
    rows.sort(key=lambda s: (s.get("kind") in SKIP_KINDS, s.get("kind") != "tui", -(s.get("started") or 0)))
    return rows[0].get("session_id") if rows else None


def _ask_one(state, h: dict, query: str, k: int, by: str, wait_s: float, out: dict) -> None:
    row = {"harness": h.get("id"), "name": h.get("name"), "state": "answered", "hits": 0}
    t0 = time.monotonic()
    try:
        status, body = state.commands.send(str(h.get("id")), out["sid"], "recall", {"query": query, "k": k},
                                           by=by, wait_s=wait_s)
    except Exception as e:  # one member never stops the others' answers
        status, body = 500, {"error": f"{type(e).__name__}: {e}"}
    row["seconds"] = round(time.monotonic() - t0, 2)
    hits = []
    if status == 200:
        result = (body or {}).get("result") if isinstance((body or {}).get("result"), dict) else {}
        for x in result.get("hits") or []:
            if isinstance(x, dict):
                hits.append({"score": round(float(x.get("score") or 0.0), 4), "title": str(x.get("title") or "")[:200],
                             "kind": str(x.get("kind") or "memory")[:20], "excerpt": str(x.get("excerpt") or "")[:300],
                             "harness": h.get("name")})
        row["hits"] = len(hits)
    elif status == 403:
        row.update(state="not_shared", note=str((body or {}).get("error") or "")[:300])
    elif status == 504 or status == 202:
        row.update(state="timeout", note=f"no answer in {wait_s:g} s")
    elif status == 409:
        row.update(state="offline", note=str((body or {}).get("error") or "")[:300])
    else:
        row.update(state="error", note=str((body or {}).get("error") or status)[:300])
    out.update(row=row, hits=hits)


def fan_out(state, query: str, k: int, *, by: str, exclude=(), wait_s: Optional[float] = None) -> "tuple[list, list]":
    """`(hits, rows)` from every online member but `exclude`, asked at the same time."""
    wait_s = WAIT_S if wait_s is None else float(wait_s)
    view = state.view()
    rows, jobs = [], []
    for h in view.get("harnesses") or []:
        if h.get("local") or h.get("id") in exclude:
            continue
        if not h.get("online"):
            rows.append({"harness": h.get("id"), "name": h.get("name"), "state": "offline", "hits": 0})
            continue
        sid = _session(h)
        if sid is None:
            rows.append({"harness": h.get("id"), "name": h.get("name"), "state": "no_session", "hits": 0,
                         "note": "no live session to answer"})
            continue
        out = {"sid": sid}
        t = threading.Thread(target=_ask_one, args=(state, h, query, k, by, wait_s, out), daemon=True,
                             name="halo-hub-recall")
        t.start()
        jobs.append((h, t, out))
    hits = []
    for h, t, out in jobs:
        t.join(wait_s + 5.0)
        row = out.get("row") or {"harness": h.get("id"), "name": h.get("name"), "state": "timeout", "hits": 0,
                                 "note": f"no answer in {wait_s:g} s"}
        rows.append(row)
        hits += out.get("hits") or []
    return hits, rows


def merged(hub, query: str, k: int = 8, *, by: str = "", exclude=(), for_member: bool = False,
           wait_s: Optional[float] = None) -> dict:
    """This harness's hits and every member's, merged by score (recall_fleet.merge)."""
    from halo_harness import recall_fleet as RF
    query, k = RF.clean_query(query), RF.clamp_k(k)
    state = hub.state
    local = next((h for h in state.view().get("harnesses") or [] if h.get("local")), {})
    mine, note = RF.local_hits(query, k, hub.home, for_member=for_member) if query else ([], "")
    for h in mine:
        h["harness"] = local.get("name") or h.get("harness")
    hits, rows = fan_out(state, query, k, by=by or state.name, exclude=exclude, wait_s=wait_s) if query else ([], [])
    head = {"harness": local.get("id"), "name": local.get("name"), "local": True,
            "state": "not_shared" if note.startswith("not shared") else "answered", "hits": len(mine)}
    if note:
        head["note"] = note
    return {"query": query, "k": k, "hits": RF.merge([mine, hits], k), "harnesses": [head] + rows, "at": time.time()}


def library(hub, harness: str, entry: str, *, by: str, wait_s: Optional[float] = None) -> "tuple[int, dict]":
    """3.1.6.0 R3: one live session of the member `harness` (its id or name) answers `coach_library {entry}`."""
    state = hub.state
    rows = state.view().get("harnesses") or []
    want = str(harness or "").strip()
    h = next((x for x in rows if want in (x.get("id"), x.get("name"))), None) or \
        next((x for x in rows if str(x.get("name") or "").lower() == want.lower()), None)
    if h is None:
        return 404, {"error": f"no harness {want!r} on this hub (halo fleet who lists them)"}
    if h.get("local"):
        return 422, {"error": f"{h.get('name')} is this harness: its library is here already", "harness": h.get("name")}
    if not h.get("online"):
        return 409, {"error": f"{h.get('name')} is offline", "harness": h.get("name")}
    sid = _session(h)
    if sid is None:
        return 409, {"error": f"{h.get('name')} has no live session to answer", "harness": h.get("name")}
    status, body = state.commands.send(str(h.get("id")), sid, "coach_library", {"entry": str(entry or "")}, by=by,
                                       wait_s=WAIT_S if wait_s is None else float(wait_s))
    return status, dict(body or {}, harness=h.get("name"))


def serve(handler, route: str):
    """`local/recall` (admin) and `recall` (a member's signed ask) on the hub port; 3.1.6.0 R3 `local/coach-library`
    (admin): `{harness, entry}` forwarded to that member's `coach_library` command."""
    from halo_harness.fleet import protocol
    try:
        raw = handler._raw_body()
    except ValueError as e:
        return handler._json(413, {"error": str(e)})
    hid = None
    if route == "local/coach-library":
        if not handler._admin():
            return None
        try:
            body = protocol.decode(raw)
        except ValueError as e:
            return handler._json(400, {"error": f"bad request: {e}"})
        from halo_harness.fleet.identity import fleet_name
        return handler._json(*library(handler.hub, str(body.get("harness") or ""), str(body.get("entry") or ""),
                                      by=fleet_name(handler.hub.home)))
    if route == "local/recall":
        if not handler._admin():
            return None
    else:
        hid = handler._signed(raw)
        if not hid:
            return None
    try:
        body = protocol.decode(raw)
    except ValueError as e:
        return handler._json(400, {"error": f"bad request: {e}"})
    from halo_harness import recall_fleet as RF
    query = RF.clean_query(body.get("query"))
    if not query:
        return handler._json(422, {"error": "a recall needs a query: some words"})
    hub = handler.hub
    if hid is None:
        from halo_harness.fleet.identity import fleet_name
        out = merged(hub, query, body.get("k") or 8, by=fleet_name(hub.home))
    else:
        member = hub.state.members.get(hid)
        out = merged(hub, query, body.get("k") or 8, by=getattr(member, "name", hid), exclude=(hid,), for_member=True)
    return handler._json(200, protocol.doc(**out) if hid else out)
