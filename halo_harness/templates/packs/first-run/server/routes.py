"""The first-run pack's routes module (`contributes.studio.routes: {module: server/routes.py, prefix: start}`): Studio
imports it through the pack's folder and calls `handle` for every `/api/packs/first-run/start/<path>` request.

    GET  ping       {ok, pack}: the kit's shape check
    GET  start | POST start | POST dismiss | POST stop    server/start_api.py
"""

from __future__ import annotations


def handle(ctx, method, path, body, query):
    if method == "GET" and path == "ping":
        return 200, {"ok": True, "pack": ctx.pack_id}
    from .start_api import ROUTES
    fn = ROUTES.get((method, path))
    if fn is not None:
        return fn(ctx)
    if any(p == path for _m, p in ROUTES):
        return 405, {"error": f"{method} {path}: this route answers another method"}
    return 404, {"error": f"no route for {method} {path}"}


def unload() -> None:
    """Studio unloads the routes (the pack was turned off): ask a running guided first run to stop."""
    from . import start_job
    start_job.stop()
