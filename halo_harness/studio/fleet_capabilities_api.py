"""halo_harness.studio.fleet_capabilities_api -- what every harness can do
(Halo 3.0.6.0 "Fleet Missions" round R6), appended to
studio/fleet_hub_api.py's ROUTES; the same loopback + token guard as every
Studio route. Computed in code, no model call.

    GET fleet/capabilities[?harness=<id | name | local>&refresh=1]
        -> {harnesses: [{harness, name, local, online, hash, summary, chips, at, received, catalog | null, note?}],
            at, stale_s}
        every harness's catalog (fleet/capabilities.py's shape): this one from its cache (gathered when
        missing, refreshed in the background after an hour), a member's as the hub last received it.
        refresh=1 gathers this harness's afresh, or asks the named member now (`capabilities {refresh}`);
        a catalog that changed is announced as a `fleet` frame {action: capabilities, harness, name, hash}.
    GET fleet/who?q=<words>
        -> {q, words, results: [{harness, name, local, score, matched, matches: [{kind, name, why, score}]}]}
        ranked by fleet/capabilities_who.py (exact name > a word of the name > a word of the description;
        tags count double); 422 when the query has no words.

The catalogs come from Studio's own hub, else from a `halo fleet serve` on
this machine (its loopback `local/capabilities` route), else this harness
alone.
"""

from __future__ import annotations

import time
from urllib.parse import quote

from halo_harness.fleet import capabilities as caps
from halo_harness.fleet import capabilities_who as who
from halo_harness.fleet.hub_capabilities import entry, local_catalog
from halo_harness.studio import fleet_watch_io as io


def _frame(server, home, hid: str, cat: dict) -> None:
    hub = getattr(server, "fleet_hub", None)
    if hub is not None:
        hub.state.caps.publish(hid, cat)
        return
    io.publish(server, {"event": "fleet", "harness": hid, "data": {
        "action": "capabilities", "harness": hid, "name": (cat.get("harness") or {}).get("name"), "hash": cat.get("hash")}})


def _refresh_local(req) -> None:
    cat, changed = caps.refresh(req.state_dir)
    if changed:
        _frame(req.server, req.state_dir, io.local_id(req.server), cat)


def _entries(req, refresh_member: str = "") -> "tuple[int, object]":
    """`(200, [entry...])`, or an error from asking a member."""
    hub = getattr(req.server, "fleet_hub", None)
    if hub is not None:
        if refresh_member:
            status, got = hub.state.caps.fetch_now(refresh_member)
            if status != 200:
                return status, got
        return 200, hub.state.caps.entries(io.view(req.server, req.state_dir))
    from halo_harness.fleet.hub import running_call
    route = "local/capabilities" + (f"?harness={quote(refresh_member)}&refresh=1" if refresh_member else "")
    got = running_call(req.state_dir, "GET", route, timeout=40.0 if refresh_member else 8.0)
    if got and got[0] == 200 and isinstance(got[1], dict):
        return 200, got[1].get("harnesses") or []
    if got and refresh_member:
        return got
    lid = io.local_id(req.server)
    view = io.view(req.server, req.state_dir)
    rows = []
    for h in view.get("harnesses") or []:
        if h.get("local"):
            rows.append(entry(h, local_catalog(req.state_dir, lambda c: _frame(req.server, req.state_dir, lid, c))))
    return 200, rows


def _find(rows: list, want: str) -> list:
    if not want:
        return rows
    low = want.strip().lower()
    return [r for r in rows if (low == "local" and r.get("local")) or str(r.get("harness")) == want
            or str(r.get("name") or "").lower() == low]


def get_capabilities(req):
    want = str(req.query.get("harness") or "").strip()
    refresh = str(req.query.get("refresh") or "") in ("1", "true", "yes")
    status, rows = _entries(req)
    if status != 200:
        return status, rows
    picked = _find(rows, want)
    if want and not picked:
        return 404, {"error": f"no harness {want!r} in this fleet", "harnesses": [r.get("name") for r in rows]}
    if refresh:
        targets = picked if want else [r for r in rows if r.get("local")]
        for r in targets:
            if r.get("local"):
                _refresh_local(req)
            else:
                status, got = _entries(req, refresh_member=str(r.get("harness")))
                if status != 200:
                    return status, {**(got if isinstance(got, dict) else {}), "harness": r.get("harness")}
        status, rows = _entries(req)
        picked = _find(rows, want) if want else rows
    return 200, {"harnesses": picked, "at": time.time(), "stale_s": caps.STALE_S}


def get_who(req):
    q = " ".join(str(req.query.get("q") or "").split())[:200]
    words = who.query_words(q)
    if not words:
        return 422, {"error": "a who query needs a word: a tool, an app, a skill, a model, a CLI or a GPU", "problems": []}
    status, rows = _entries(req)
    if status != 200:
        return status, rows
    ranked = who.rank([{"harness": r.get("harness"), "name": r.get("name"), "local": r.get("local"),
                        "catalog": r.get("catalog")} for r in rows], q)
    return 200, {"q": q, "words": words, "results": ranked}


ROUTES = [("GET", r"^fleet/capabilities$", get_capabilities),
          ("GET", r"^fleet/who$", get_who)]
