"""The coach pack's routes module (`contributes.studio.routes: {module: server/routes.py, prefix: coach}`): Studio
imports it through the pack's folder and calls `handle` for every `/api/packs/coach/coach/<path>` request (the Coach
panel, studio/coach.js, is its one caller).

    GET  ping                                  {ok, pack}
    GET  runs                                  {runs: [{run_id, state, goal_what, cost_usd, created}]}: Studio's repo,
                                               newest first (the panel's run picker; the coach reads a finished one)
    GET  orchestra/<run>/coach | fleet/missions/<id>/coach and their POST verbs (ask, apply, undo, probe) and
    POST coach/library/<entry>/forget          server/coach_api.py (the routes the core answered until 3.4.0.0 B2)
"""

from __future__ import annotations

from types import SimpleNamespace

from halo_harness.ext import core as _core


def _runs(ctx) -> dict:
    OM = _core.module("studio.orchestra_model")
    rows = OM.run_rows(OM.repo_of(ctx.cwd), None)
    return {"runs": [{k: r.get(k) for k in ("run_id", "state", "goal_what", "cost_usd", "created")} for r in rows[:50]]}


def handle(ctx, method, path, body, query):
    if method == "GET" and path == "ping":
        return 200, {"ok": True, "pack": ctx.pack_id}
    if path == "runs":
        return (200, _runs(ctx)) if method == "GET" else (405, {"error": "GET runs"})
    from .coach_api import dispatch_coach
    req = SimpleNamespace(path=path, method=method, body=body if isinstance(body, dict) else {}, cwd=ctx.cwd,
                          state_dir=ctx.state_dir, server=None, bridge=getattr(ctx, "bridge", None))
    out = dispatch_coach(req)
    return out if out is not None else (404, {"error": f"no route for {method} {path}"})
