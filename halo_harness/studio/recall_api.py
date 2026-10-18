"""halo_harness.studio.recall_api -- Studio's recall box (Halo 3.1.2.0 R3), the
same loopback + token guard as every Studio route.

    GET recall?q=<words>&k=8[&fleet=1]
        -> {query, k, fleet, hits: [{score, title, kind, excerpt, harness}],
            harnesses: [{harness, name, local?, state, hits, note?, seconds?}], at}
        this harness's own index; `fleet=1` (the box's Fleet switch) asks the hub, which asks every online
        member at once and merges their hits by score with these (fleet/hub_recall.py)
    GET fleet/recall?q=<words>&k=8   the hub's merged view (appended to studio/fleet_hub_api.py's ROUTES);
                                     409 when no hub runs in Studio, on this machine, or as a joined one

The hub is Studio's own (`halo studio --fleet`), else a `halo fleet serve` on
this machine, else the first hub this harness joined (recall_fleet.ask).
422 when the query has no words.
"""

from __future__ import annotations

import time


def _query(req) -> "tuple[str, int]":
    from halo_harness import recall_fleet as RF
    return RF.clean_query(req.query.get("q")), RF.clamp_k(req.query.get("k"))


def _fleet(req, q: str, k: int) -> "tuple[int, dict]":
    hub = getattr(req.server, "fleet_hub", None)
    if hub is not None:
        from halo_harness.fleet.hub_recall import merged
        from halo_harness.remote.fleet_identity import fleet_name
        return 200, merged(hub, q, k, by=fleet_name())
    from halo_harness import recall_fleet as RF
    return RF.ask(q, k)


def get_recall(req):
    q, k = _query(req)
    if not q:
        return 422, {"error": "a recall needs a query: some words", "problems": ["q"]}
    if str(req.query.get("fleet") or "") in ("1", "true", "yes"):
        status, body = _fleet(req, q, k)
        return status, {**body, "fleet": True}
    from halo_harness import recall_fleet as RF
    from halo_harness.fleet.identity import fleet_name, harness
    hits, note = RF.local_hits(q, k, req.state_dir)
    row = {"harness": harness(req.state_dir)["id"], "name": fleet_name(req.state_dir), "local": True,
           "state": "answered", "hits": len(hits)}
    if note:
        row["note"] = note
    return 200, {"query": q, "k": k, "fleet": False, "hits": RF.merge([hits], k), "harnesses": [row], "at": time.time()}


def get_fleet_recall(req):
    q, k = _query(req)
    if not q:
        return 422, {"error": "a recall needs a query: some words", "problems": ["q"]}
    return _fleet(req, q, k)


def dispatch_recall(req):
    if req.path == "recall":
        if req.method != "GET":
            return 405, {"error": "method not allowed"}
        return get_recall(req)
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}


ROUTES = [("GET", r"^fleet/recall$", get_fleet_recall)]
