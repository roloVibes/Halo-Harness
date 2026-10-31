"""halo_harness.studio.local_api -- the routes of Studio's Local section (Halo 3.3.5.0 R1; docs/STUDIO-local.md),
reached through studio/api.py's `_PREFIXES` (`local/`). The same loopback / origin / token guard as every Studio
route. Never a model call; nothing here writes a server's settings.

    GET  local/hosts                    studio/local_hosts_view.hosts: every host Halo knows as a card
    POST local/host/<name>/load {model, num_ctx?, keep_alive?}   a warm generate (providers/ollama_load.load) on a
                                        host this machine serves, or through the fleet member that serves it
    POST local/host/<name>/unload {model}                         the same with keep_alive 0
    POST local/host/add {url, name}     the discovered server as an ollama.hosts entry, through Setup's own writer
                                        (studio/setup_providers_api.post_ollama_host)
    GET  local/resources?host=          the last 5 minutes of samples (ollama_steward/resources.py) and the sampler's state
    POST local/resources/watch {on}     the tab's lease on the sampler (renewed by the page; the steward job holds its own)
    GET  local/traffic?host=&since=15m  studio/local_traffic.traffic: the ledger's rows, the server events, the sparklines
    POST local/traffic {lines, events}  another process's ledger tap (ollama_steward/ledger_tap.py): `traffic` frames
    GET  local/models?host=             studio/local_models_view.models: per host every model, its card and meter
    local/library*                      3.3.5.0 R2: studio/models_library_api.py (the library browser and the fit badge)
    local/pull*, local/host/<name>/pull | delete | show | copy | rename | twin | loaded
    3.3.6.0 R3 (studio/local_logs_api.py): local/host/<name>/log, /log/status, /log/models
                                        3.3.5.0 R3: studio/local_control_api.py (Ollama, controlled)
    local/hf/*, local/download*, local/servers, local/server/<id>/*
                                        3.3.5.0 R5: studio/local_hf_api.py + local_server_api.py (Hugging Face local)
    local/host/<name>/bench, local/benches   3.3.6.0 R5: studio/local_bench_api.py (the bench, the speed cards)
    local/host/<name>/tune[/apply], local/changes[/revert|/scope|/apply]   3.3.6.0 R5: studio/local_tune_api.py
    local/host/<name>/request-control, local/host-pending[/<id>/allow|deny]   3.3.7.0 R2: studio/local_host_api.py
"""

from __future__ import annotations

import re

_HOST_ACT = re.compile(r"^local/host/(?P<name>[^/]+)/(?P<act>load|unload)$")
MAX_SINCE_S = 86400.0


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _hub(req):
    return getattr(req.server, "fleet_hub", None) if req.server is not None else None


def _publish(req):
    if req.server is None:
        return None
    from halo_harness.studio.events import bridge_for
    return bridge_for(req.server).publish_local


def get_hosts(req):
    from halo_harness.studio.local_hosts_view import hosts
    return 200, hosts(req.state_dir, hub=_hub(req))


def _remote(req, card: dict, act: str, fields: dict):
    """Through the fleet member that serves the host (fleet/control_models.py on its side); 3.3.7.0 R2: through the
    paired halo host that serves it (studio/local_host_acts.send: its typed vocabulary, no member session)."""
    from halo_harness.fleet.identity import fleet_name
    from halo_harness.studio.local_hosts_view import _member
    hub = _hub(req)
    c = card["controls"]
    if c.get("via") == "host":
        from halo_harness.studio.local_host_acts import send
        return send(c, act, fields)
    m = _member(hub, c.get("member") or "")
    sessions = m.sessions() if m is not None else []
    if m is None or not sessions:
        return 409, {"error": c.get("why") or "no fleet member takes this command now"}
    sid = str(sessions[0].get("id") or sessions[0].get("session_id") or "")
    body = {"host": c.get("member_host") or "", **fields}
    return hub.state.commands.send(m.id, sid, f"ollama_{act}", body, by=fleet_name(hub.home), wait_s=10.0)


def post_host_act(req, name: str, act: str):
    from halo_harness.providers.ollama import resolve_ollama_host
    from halo_harness.studio.local_hosts_view import hosts
    body = _body(req)
    model = str(body.get("model") or "").strip()
    if not model:
        return 422, {"error": f"{act} takes {{model}}", "problems": ["model: the model to " + act]}
    card = next((h for h in hosts(req.state_dir, hub=_hub(req))["hosts"] if h["name"] == name), None)
    if card is None:
        return 404, {"error": f"no host named {name!r} here"}
    if not card["controls"]["ok"]:
        return 409, {"error": card["controls"]["why"]}
    fields = {"model": model}
    if act == "load":
        if isinstance(body.get("num_ctx"), int) and body["num_ctx"] > 0:
            fields["num_ctx"] = body["num_ctx"]
        if body.get("keep_alive") not in (None, ""):
            fields["keep_alive"] = body["keep_alive"]
    if card["controls"]["via"] != "this machine":
        code, out = _remote(req, card, act, fields)
        from halo_harness.studio import ollama_hosts_view as V
        V.reset_cache()
        return code, out
    from halo_harness.providers.ollama_load import load, unload
    host = resolve_ollama_host(name)
    out = load(host, model, num_ctx=fields.get("num_ctx"), keep_alive=fields.get("keep_alive")) if act == "load" \
        else unload(host, model)
    from halo_harness.studio import ollama_hosts_view as V
    V.reset_cache()  # the next read shows what /api/ps has now
    return (200 if out["ok"] else 502), ({**out, "via": "this machine"} if out["ok"] else {"error": out["say"], **out})


def post_host_add(req):
    from halo_harness.studio.setup_providers_api import post_ollama_host
    body = _body(req)
    url, name = str(body.get("url") or "").strip(), str(body.get("name") or "").strip()
    if not url:
        return 422, {"error": "add takes {url, name}", "problems": ["url: the server's address"]}
    req.body = {"name": name, "url": url}
    code, answer = post_ollama_host(req)
    if code != 200:
        return code, answer
    return 200, {"ok": True, "lines": answer.get("lines") or [], "name": name or url}


def get_resources(req):
    from halo_harness.ollama_steward import resources
    host = str(req.query.get("host") or "").strip()
    rows = resources.STORE.recent(host)
    return 200, {"samples": rows, "hosts": sorted({s["host"] for s in rows}), **resources.status()}


def post_watch(req):
    from halo_harness.ollama_steward import resources
    on = _body(req).get("on") is not False
    return 200, resources.want(req.state_dir, "tab", on, publish=_publish(req))


def get_traffic(req):
    from halo_harness.ollama_steward.ledger import parse_since
    from halo_harness.studio.local_traffic import traffic
    try:
        since_s = parse_since(str(req.query.get("since") or "15m")) or 900.0
    except ValueError as e:
        return 422, {"error": str(e), "problems": [str(e)]}
    return 200, traffic(req.state_dir, str(req.query.get("host") or "").strip(), min(max(since_s, 60.0), MAX_SINCE_S))


def post_traffic(req):
    from halo_harness.studio.local_traffic import tap
    publish = _publish(req)
    body = _body(req)
    n = 0
    if publish is not None:
        on = tap(publish)
        for kind in ("lines", "events"):
            rows = body.get(kind) if isinstance(body.get(kind), list) else []
            if rows:
                on(kind, rows[:500])
                n += len(rows[:500])
    return 200, {"ok": True, "published": n}


def get_models(req):
    from halo_harness.studio.local_models_view import models
    return 200, models(req.state_dir, str(req.query.get("host") or "").strip())


ROUTES = {("GET", "local/hosts"): get_hosts, ("POST", "local/host/add"): post_host_add,
          ("GET", "local/resources"): get_resources, ("POST", "local/resources/watch"): post_watch,
          ("GET", "local/traffic"): get_traffic, ("POST", "local/traffic"): post_traffic,
          ("GET", "local/models"): get_models}


def dispatch_local(req):
    from halo_harness.studio.local_control_api import dispatch_control  # 3.3.5.0 R3: pull, delete, show, ...
    from halo_harness.studio.local_hf_api import dispatch_hf  # 3.3.5.0 R5: Hugging Face downloads and servers
    from halo_harness.studio.models_library_api import dispatch_library
    got = dispatch_hf(req)
    if got is not None:
        return got
    from halo_harness.studio.local_probe_api import dispatch_probe  # 3.3.6.0 R1: the battery
    got = dispatch_probe(req)
    if got is not None:
        return got
    from halo_harness.studio.local_logs_api import dispatch_logs  # 3.3.6.0 R3: Local -> Logs
    got = dispatch_logs(req)
    if got is not None:
        return got
    from halo_harness.studio.local_card_api import dispatch_card  # 3.3.6.0 R4: measured, the dialect record
    from halo_harness.studio.local_shelf_api import dispatch_shelf  # 3.3.6.0 R4: the shelf, Retire, Re-pull
    from halo_harness.studio.local_bench_api import dispatch_bench  # 3.3.6.0 R5: the bench, the speed cards
    from halo_harness.studio.local_tune_api import dispatch_tune  # 3.3.6.0 R5: the tuning report, the changes
    from halo_harness.studio.local_host_api import dispatch_host  # 3.3.7.0 R2: halo host grants and pending rows
    for fn in (dispatch_card, dispatch_shelf, dispatch_bench, dispatch_tune, dispatch_host):
        got = fn(req)
        if got is not None:
            return got
    got = dispatch_control(req)
    if got is not None:
        return got
    got = dispatch_library(req)
    if got is not None:
        return got
    fn = ROUTES.get((req.method, req.path))
    if fn is not None:
        return fn(req)
    m = _HOST_ACT.match(req.path)
    if m:
        if req.method != "POST":
            return 405, {"error": "method not allowed"}
        import urllib.parse
        return post_host_act(req, urllib.parse.unquote(m.group("name")), m.group("act"))
    if any(p == req.path for _m, p in ROUTES):
        return 405, {"error": "method not allowed"}
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
