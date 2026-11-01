"""halo_harness.studio.pool_act_api -- Local -> Pool's acting routes (Halo 3.3.8.0 R3; docs/STUDIO-local-pool.md "Warm
and Stop"), reached through studio/pool_api.dispatch_pool. The same loopback / origin / token guard as every Studio
route; never a model call. Every answer carries `cli`, the `halo` line that does the same.

    GET  local/pool/run                    local_pool/degrade.status: running / loading / degraded (worker2 down) /
                                           down / stopped, each member's claim and its lease, the auto-revert judge;
                                           `warm` (the last Warm's lines while it runs), `cooldown` (one change per
                                           10 min). A pool this process does not hold yet is adopted: its claims are
                                           renewed by this Studio's heartbeat from now on
    GET  local/pool/preflight?model=&allow_wifi=1&window=   local_pool/preflight (the page enables Warm when green)
    POST local/pool/warm {model, allow_wifi?, window?}   ollama_steward/changes_pool.warm in the background (the
                                           launch waits for /health); 202 with `busy`, the run route says how it went
    POST local/pool/stop                   changes_pool.stop: llama-server stopped, the claims released, the
                                           pivoted-out models back (said line by line)
    POST local/pool/rpc {member, to}       a member's rpc-server through its halo host (to: on | off | status)
"""

from __future__ import annotations

import threading

TRUE = ("1", "true", "yes", "on")
_WARM: dict = {}
_LOCK = threading.Lock()


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _int(v):
    return int(v) if str(v or "").strip().isdigit() else None


def _adopt(state_dir) -> None:
    from halo_harness.local_pool import launch
    from halo_harness.local_pool.claims import hold, scope
    from halo_harness.local_sched import lease
    r = launch.run(state_dir)
    if r and launch.alive(r) and scope(r.get("model") or "") not in lease.held():
        hold(scope(r["model"]), r.get("placed") or [], state_dir)


def get_run(req):
    from halo_harness.local_pool.degrade import status
    from halo_harness.ollama_steward.changes_pool import cooldown
    _adopt(req.state_dir)
    st = status(req.state_dir)
    st.pop("rows", None)
    with _LOCK:
        warm = dict(_WARM)
    return 200, {**st, "warm": warm, "cooldown": cooldown(req.state_dir), "cli": "halo pool status"}


def get_preflight(req):
    from halo_harness.local_pool.catalog import names
    from halo_harness.local_pool.preflight import preflight
    model = str(req.query.get("model") or "").strip()
    wifi = str(req.query.get("allow_wifi") or "").lower() in TRUE
    pf = preflight(model, allow_wifi=wifi, window=_int(req.query.get("window")), state_dir=req.state_dir) if model else None
    if pf is None:
        return 404, {"error": f"{model!r} is not in the pool catalog ({', '.join(names())})", "catalog": names()}
    keep = {k: pf[k] for k in ("ok", "model", "display", "checks", "blocks", "line", "used", "excluded", "ctx", "q8",
                               "cache", "allow_wifi", "order", "split")}
    return 200, {**keep, "download": pf["gguf"].get("download"),
                 "cli": f"halo pool preflight {pf['model']}" + (" --allow-wifi" if wifi else "")}


def post_warm(req):
    from halo_harness.ollama_steward.changes_pool import cooldown, warm
    b = _body(req)
    model = str(b.get("model") or "").strip()
    if not model:
        return 422, {"error": "warm takes {model, allow_wifi?, window?}", "problems": ["model: a pool catalog model"]}
    wait = cooldown(req.state_dir)
    if wait:
        return 409, {"error": wait, "cooldown": True}
    with _LOCK:
        if _WARM.get("busy"):
            return 409, {"error": f"a Warm of {_WARM.get('model')} is already running"}
        _WARM.clear()
        _WARM.update(busy=True, model=model, lines=[], ok=None)
    wifi, window, state = b.get("allow_wifi") is True, _int(b.get("window")), req.state_dir

    def work() -> None:
        try:
            got = warm(model, allow_wifi=wifi, window=window, state_dir=state, by="studio")
        except Exception as e:  # the page says it; the server keeps going
            got = {"ok": False, "lines": [f"Warm did not finish: {type(e).__name__}: {str(e)[:200]}"]}
        with _LOCK:
            _WARM.update(busy=False, ok=bool(got.get("ok")), lines=list(got.get("lines") or []))
    threading.Thread(target=work, name="halo-pool-warm", daemon=True).start()
    cli = f"halo local serve --pool {model}" + (" --allow-wifi" if wifi else "") + (f" --window {window}" if window else "")
    return 202, {"ok": True, "busy": True, "model": model, "cli": cli}


def post_stop(req):
    from halo_harness.ollama_steward.changes_pool import stop
    got = stop(state_dir=req.state_dir, by="studio", why="Stop on the Pool page")
    return 200, {**got, "cli": "halo pool stop"}


def post_rpc(req):
    from halo_harness.local_pool.hosts import rpc
    from halo_harness.local_pool.members import load
    b = _body(req)
    name, to = str(b.get("member") or ""), str(b.get("to") or "status")
    m = next((x for x in load(req.state_dir) if x["name"].lower() == name.lower()), None)
    if m is None or to not in ("on", "off", "status"):
        return 422, {"error": "rpc takes {member: a member's name, to: on | off | status}"}
    got = rpc(m, to)
    cli = f"halo pool rpc {m['name']} {to}"
    return (200, {**got, "cli": cli}) if got["ok"] else (502, {**got, "error": got["say"], "cli": cli})


ROUTES = {("GET", "local/pool/run"): get_run, ("GET", "local/pool/preflight"): get_preflight,
          ("POST", "local/pool/warm"): post_warm, ("POST", "local/pool/stop"): post_stop,
          ("POST", "local/pool/rpc"): post_rpc}
