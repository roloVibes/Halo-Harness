"""halo_harness.studio.pool_api -- Halo 3.3.8.0 R1: the routes of Local -> Pool (docs/STUDIO-local.md "Pool"), reached
through studio/local_api.dispatch_local (prefix `local/`). The same loopback / origin / token guard as every Studio
route; never a model call; nothing here launches a process, loads a model or changes a host. Every answer carries
`cli`, the `halo pool` line that does the same.

    GET  local/pool/members          pool_cli.members_view: each member's GPU, free / total VRAM (its host card), link,
                                     RTT of the last scan, share of the split; the validation lines; `scan` {at, line}
                                     of the last scan (3.3.8.0 R3: Warm / Stop are studio/pool_act_api.py)
    GET  local/pool/recommend?batch=1   local_pool/recommend.recommend over the members' budgets
    GET  local/pool/verdict?model=   one catalog model's fit and its preview (404 for a name not in the catalog)
    POST local/pool/scan {port?, subnets?, own_subnet?}   the RPC-port scan (local_pool/scan.py): explicit, a button
    POST local/pool/members {op: add | remove, name, host?, port?, weight?, vram_gb?}   pool.json edited (422 with the
                                     validation lines when refused)
"""

from __future__ import annotations

TRUE = ("1", "true", "yes", "on")


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def get_members(req):
    from halo_harness.local_pool.scan import last
    from halo_harness.pool_cli import members_view
    got = last(req.state_dir)
    return 200, {**members_view(req.state_dir), "scan": {"at": got.get("at"), "line": got.get("line") or ""},
                 "cli": "halo pool members"}


def get_recommend(req):
    from halo_harness.local_pool.budget import budgets
    from halo_harness.local_pool.recommend import recommend
    batch = str(req.query.get("batch") or "").lower() in TRUE
    return 200, {**recommend(budgets(state_dir=req.state_dir), allow_batch=batch, state_dir=req.state_dir),
                 "cli": "halo pool recommend" + (" --batch" if batch else "")}


def get_verdict(req):
    from halo_harness.local_pool.budget import budgets
    from halo_harness.local_pool.catalog import names
    from halo_harness.local_pool.recommend import verdict
    model = str(req.query.get("model") or "").strip()
    if not model:
        return 422, {"error": "verdict takes ?model=", "problems": ["model: a pool catalog model"], "catalog": names()}
    v = verdict(model, budgets(state_dir=req.state_dir), state_dir=req.state_dir)
    if v is None:
        return 404, {"error": f"{model!r} is not in the pool catalog ({', '.join(names())})", "catalog": names()}
    return 200, {**v, "cli": f"halo pool verdict {v['model']}"}


def post_scan(req):
    from halo_harness.local_pool.scan import scan
    b = _body(req)
    port = int(b["port"]) if str(b.get("port") or "").isdigit() else None
    subnets = [str(s) for s in b["subnets"]] if isinstance(b.get("subnets"), list) else None
    got = scan(port=port, subnets=subnets, own_subnet=b.get("own_subnet") is not False, state_dir=req.state_dir)
    cli = " ".join(["halo pool scan"] + ([f"--port {port}"] if port else []) + [f"--subnet {s}" for s in subnets or []])
    return 200, {**got, "cli": cli}


def post_members(req):
    from halo_harness.local_pool import members as M
    b = _body(req)
    op, name = str(b.get("op") or "").strip(), str(b.get("name") or "").strip()
    if op == "remove":
        ok, lines, rows = M.remove(name, state_dir=req.state_dir)
        cli = f"halo pool remove {name}"
    elif op == "add":
        host = str(b.get("host") or "").strip()
        port = int(b["port"]) if str(b.get("port") or "").isdigit() else None
        weight, vram = _num(b.get("weight")), _num(b.get("vram_gb"))
        ok, lines, rows = M.add(name, host, weight=weight, vram_gb=vram, port=port, state_dir=req.state_dir)
        door = host if port is None else (f"[{host}]:{port}" if ":" in host else f"{host}:{port}")
        cli = " ".join(w for w in ("halo pool add", name, door, f"--weight {weight:g}" if weight is not None else "",
                                   f"--vram {vram:g}" if vram is not None else "") if w)
    else:
        return 422, {"error": "members takes {op: add | remove, name, host?, port?, weight?, vram_gb?}",
                     "problems": ["op: add or remove"]}
    if not ok:
        return 422, {"error": lines[0] if lines else "refused", "problems": lines, "members": rows, "cli": cli}
    return 200, {"ok": True, "lines": lines, "members": rows, "cli": cli}


ROUTES = {("GET", "local/pool/members"): get_members, ("GET", "local/pool/recommend"): get_recommend,
          ("GET", "local/pool/verdict"): get_verdict, ("POST", "local/pool/scan"): post_scan,
          ("POST", "local/pool/members"): post_members}


def dispatch_pool(req):
    """The answer for a `local/pool/*` path, or None for any other path."""
    if not req.path.startswith("local/pool/"):
        return None
    from halo_harness.studio.pool_act_api import ROUTES as ACTS  # 3.3.8.0 R3: run, preflight, warm, stop, rpc
    fn = ROUTES.get((req.method, req.path)) or ACTS.get((req.method, req.path))
    if fn is not None:
        return fn(req)
    if any(p == req.path for _m, p in list(ROUTES) + list(ACTS)):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
