"""halo_harness.host.routes_act -- the host's acting routes (Halo 3.3.7.0 R2; docs/HOST.md "The vocabulary").

    POST control/<op> | manage/<op>   {params, evidence: {finding?, lines?}, scope?, dry?, why?}
        the grant (host/grants.decide: 403 naming it; 202 + a pending row under fleet.allow_control: ask), the
        params (422), the guards for a fix (host/guards.py: 422 evidence, 409 one at a time / cooldown, 429 rate),
        the preview; `dry: true` answers {ok, dry, would, writes, takes, cost} and lands nothing; a preview that
        says the card would be breached refuses in its own words (422); else the op applies. A job-shaped op
        answers {ok, job, view} and its `job` frames go out on `GET stream`; `GET job/<id>` catches up.
    POST admin/<op>                   the grant, then 501: admin operations are not part of this version
    POST request {grant, why?}        a peer asks the owner for a grant (a pending row of kind grant)
    GET  me | job/<id> | jobs | changes | findings | pending

`act_audit` is the audit line's extra fields per request: {op, params, evidence, dry, ok, landed, fix, change_id?,
job?}. Nothing here runs a model, changes a server setting or restarts a server.
"""

from __future__ import annotations

from halo_harness.fleet import protocol

ADMIN_LINE = ("admin operations are not part of this version: nothing runs a shell on a host (the grant exists so an "
              "owner can see what it would mean)")
GET_ROUTES = ("me", "job", "jobs", "changes", "findings", "pending")


def _vocab_line(head: str) -> str:
    from halo_harness.host.ops import table
    names = sorted(o.name for o in table().values() if o.grant == head)
    return f"the {head} operations: {', '.join(names) or 'none in this version'}"


def post(svc, route: str, raw: bytes, hid: str) -> "tuple[int, dict, dict]":
    from halo_harness.host import grants, guards
    from halo_harness.host.jobs import of
    from halo_harness.host.ops import Ctx, table, validate
    try:
        body = protocol.decode(raw) if raw else {}
    except ValueError as e:
        return 400, {"error": f"bad request: {e}"}, {}
    rec = svc.pairing.member(hid)
    if route == "request":
        status, out = grants.request(svc.home, hid, rec, str(body.get("grant") or ""), str(body.get("why") or ""))
        return status, out, {"op": "request", "params": {"grant": body.get("grant")}}
    head, _, name = route.partition("/")
    audit = {"op": name or head, "params": body.get("params"), "evidence": body.get("evidence"),
             "dry": body.get("dry") is True}
    if head == "admin":
        status, out = grants.decide(svc.home, hid, rec, "admin", name or "admin", body)
        return (status, out, audit) if status != 200 else (501, {"error": ADMIN_LINE, "grant": "admin"}, audit)
    op = table().get(name)
    if op is None or op.grant != head:
        hint = f"{name} is a {op.grant} operation: POST {op.grant}/{name}" if op else f"no {head} operation {name!r}"
        return 404, {"error": f"{hint}; {_vocab_line(head)}"}, audit
    audit["fix"] = guards.is_fix(op, body)
    params, problems = validate(op, body.get("params"))
    if problems:
        return 422, {"error": f"{name}: " + "; ".join(problems), "problems": problems}, audit
    audit["params"] = params
    status, out = grants.decide(svc.home, hid, rec, op.grant, name, body)
    if status != 200:
        return status, out, audit
    ctx = Ctx(svc, hid, rec, body)
    if "host" in op.params:
        why = ctx.pick_host(params)
        if why:
            return 404, {"error": why}, audit
    model = params.get("model") or params.get("to")
    key = ctx.key(model) if model and ctx.host is not None else None
    status, out = guards.check(svc.home, ctx.peer, op, body, host=ctx.host.name if ctx.host else "", key=key)
    if status != 200:
        return status, out, audit
    try:
        prev = op.preview(ctx, params)
    except ValueError as e:
        return 422, {"error": f"{name}: {e}", "problems": [str(e)]}, audit
    if ctx.dry:
        return 200, {"ok": True, "dry": True, "op": name, "stated": op.stated, **prev}, audit
    if prev.get("breach"):
        return 422, {"error": prev["breach"], "breach": True, "op": name, "preview": prev}, audit
    if prev.get("busy"):
        return 409, {"error": prev["busy"], "op": name}, audit
    got = op.apply(ctx, params)
    if op.job and got.get("run"):
        view = of(svc).jobs.start(name, ctx.host.name, str(model or ""), got["run"], by=ctx.peer, say=got.get("say") or "")
        audit.update(job=view["job"], landed=True)
        return 200, {"ok": True, "op": name, "job": view["job"], "view": view, "say": view.get("say"),
                     "joined": view.get("joined")}, audit
    code = got.pop("status", None) or (200 if got.get("ok") else 502)
    audit.update(landed=bool(got.get("ok")) and not op.stated, change_id=got.get("change_id"))
    if code >= 400:
        return code, {"error": got.get("say") or f"{name} did not work", "op": name, **got}, audit
    return code, {**got, "op": name, "stated": op.stated}, audit


def get(svc, route: str, q: dict, hid: str):
    """(status, payload) for a GET route of this file, else None."""
    from halo_harness.host import grants, verify
    from halo_harness.host.jobs import of
    head, _, rest = route.partition("/")
    if head not in GET_ROUTES:
        return None
    if head == "me":
        from halo_harness.host.ops import vocabulary
        return 200, protocol.doc(**grants.me(svc.home, hid), vocabulary=vocabulary())
    if head == "job":
        view = of(svc).jobs.get(rest)
        return (200, protocol.doc(job=view)) if view else (404, {"error": f"no job {rest!r} on this host"})
    if head == "jobs":
        return 200, protocol.doc(jobs=of(svc).jobs.list())
    if head == "changes":
        return 200, protocol.doc(changes=verify.listing(svc.home))
    if head == "pending":
        mine = grants.pending(svc.home, peer=hid)
        return 200, protocol.doc(pending=mine)
    from halo_harness.host.findings import host_findings
    return 200, protocol.doc(findings=host_findings(svc.view))
