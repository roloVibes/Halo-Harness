"""halo_harness.studio.recall_api -- Studio's recall box (Halo 3.1.2.0 R3), the same loopback + token guard as
every Studio route.

    GET recall?q=<words>&k=8
        -> {query, k, hits: [{score, title, kind, excerpt, harness}], harnesses: [{harness, name, local, state, hits,
            note?}], at}
        this harness's own index (recall_box.py); 422 when the query has no words
"""

from __future__ import annotations

import time


def get_recall(req):
    from halo_harness import recall_box as RF
    from halo_harness.peers.identity import harness, harness_name
    q, k = RF.clean_query(req.query.get("q")), RF.clamp_k(req.query.get("k"))
    if not q:
        return 422, {"error": "a recall needs a query: some words", "problems": ["q"]}
    hits, note = RF.local_hits(q, k, req.state_dir)
    row = {"harness": harness(req.state_dir)["id"], "name": harness_name(req.state_dir), "local": True,
           "state": "answered", "hits": len(hits)}
    if note:
        row["note"] = note
    return 200, {"query": q, "k": k, "hits": RF.merge([hits], k), "harnesses": [row], "at": time.time()}


def dispatch_recall(req):
    if req.path == "recall":
        if req.method != "GET":
            return 405, {"error": "method not allowed"}
        return get_recall(req)
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
