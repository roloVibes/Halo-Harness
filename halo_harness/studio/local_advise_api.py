"""halo_harness.studio.local_advise_api -- Halo 3.3.7.0 R4: the roster adviser's route for Local -> Models' Adviser
panel (models_library/advise.py; dispatched by studio/local_api.dispatch_local; docs/STUDIO-local.md).

    GET local/advise?host=<name>&lineup=<name>   {suggestions [{id, rank, kind, says, unlocks | frees, cost, value,
                                                  value_per_gb, host, action {verb, what, model, host, role, cli}}],
                                                  lines, head, kinds, fingerprint, due, due_why, at}
Each suggestion's one button goes to the route that already does that one thing: add -> POST local/library/verify
{host, name, role?} (the download, then the battery), retire -> POST local/host/<host>/retire {name} (the shelf's
retire), point -> POST roles/<role>/point {to} (the role write). This route runs nothing.
"""

from __future__ import annotations


def get_advise(req):
    from halo_harness.models_library.advise import advise, due, inputs, remember
    host = str(req.query.get("host") or "").strip() or None
    lineup = str(req.query.get("lineup") or "").strip() or None
    inp = inputs(req.state_dir, host, lineup)
    was_due, why = due(req.state_dir, inp)
    got = advise(req.state_dir, host, inp=inp)
    remember(req.state_dir, got)
    return 200, {**got, "due": was_due, "due_why": why}


def dispatch_advise(req):
    if req.path != "local/advise":
        return None
    return get_advise(req) if req.method == "GET" else (405, {"error": "method not allowed"})
