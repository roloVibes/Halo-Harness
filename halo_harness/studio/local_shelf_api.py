"""halo_harness.studio.local_shelf_api -- Halo 3.3.6.0 R4: the model shelf's routes (models_library/shelf.py;
dispatched by studio/local_api.dispatch_local; docs/STUDIO-local.md).

    GET  local/shelf?host=                     the retired models still off their host: {shelf [{model, host, size,
                                               retired_at, why, repull}], cli}
    GET  local/host/<name>/shelf               per installed model: {facts {model: {last_used, size, picked,
                                               never_used, idle_days, hint}}}
    POST local/host/<name>/retire {name, why?, force?}
                                               the existing delete (the uses card first: 409 while a live session is
                                               on it, 422 with the card when something uses it and no force) and one
                                               shelf line; a host a fleet member serves answers 409 (retire it there)
    POST local/shelf/repull {host, model}      the existing pull job (studio/local_pull_job.py); a fitted twin's
                                               line is its recipe (409 with `halo models twin ...`)
Every answer carries `cli`, the `halo models retire | shelf` line that does the same.
"""

from __future__ import annotations

import re
import urllib.parse

_HOST = re.compile(r"^local/host/(?P<name>[^/]+)/(?P<act>retire|shelf)$")


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _row(host, model: str):
    from halo_harness.providers.model_card import _row_for
    from halo_harness.studio.ollama_hosts_view import catalog_of
    try:
        return _row_for(catalog_of(host), model)
    except Exception:
        return None


def get_shelf(req):
    from halo_harness.models_library.shelf import shelf
    host = str((req.query or {}).get("host") or "").strip() or None
    return 200, {"shelf": shelf(req.state_dir, host), "cli": "halo models shelf"}


def post_retire(req, name: str):
    from halo_harness.models_library.shelf import retire
    from halo_harness.studio.local_control_api import _target, _refused
    body = _body(req)
    model = str(body.get("name") or body.get("model") or "").strip()
    if not model:
        return 422, {"error": "retire takes {name}", "problems": ["name: the model to retire"]}
    host, ctl, here = _target(req, name)
    cli = f"halo models retire {model} --host {name}"
    if ctl is None:
        return 404, {"error": f"no host named {name!r} here"}
    if not ctl.get("ok"):
        return _refused(ctl)
    if not here or host is None:
        return 409, {"error": f"{name} is served by a fleet member: retire it on that machine ({cli})", "cli": cli}
    got = retire(host, model, state_dir=req.state_dir, why=str(body.get("why") or ""), force=body.get("force") is True,
                 cwd=req.cwd, row=_row(host, model))
    if got.get("ok"):
        from halo_harness.studio.local_pull_job import after_change
        after_change()
        return 200, {**got, "cli": cli}
    return got.get("status") or 502, {"error": got.get("say") or "it did not work", **got,
                                      "cli": cli + (" --force" if got.get("status") == 422 else "")}


def get_host_shelf(req, name: str):
    from halo_harness.models_library.shelf import facts
    from halo_harness.providers.ollama import resolve_ollama_host
    from halo_harness.studio.ollama_hosts_view import catalog_of
    host = resolve_ollama_host(name)
    if host is None:
        return 404, {"error": f"no configured Ollama host named {name!r}"}
    rows = (catalog_of(host) or {}).get("models") or []
    return 200, {"facts": facts(req.state_dir, host, rows), "cli": "halo models shelf"}


def post_repull(req):
    from halo_harness.models_library.shelf import mark_repulled, shelf
    from halo_harness.studio.local_control_api import _pub, _target
    body = _body(req)
    name, model = str(body.get("host") or "").strip(), str(body.get("model") or "").strip()
    hit = next((r for r in shelf(req.state_dir, name or None) if r.get("model") == model), None)
    if hit is None:
        return 404, {"error": f"{model or '(no model)'} is not on the shelf" + (f" of {name}" if name else "")}
    name = name or hit.get("host")
    cli = f"halo models shelf --repull {model} --host {name}"
    if not str(hit.get("repull") or "").startswith("ollama pull "):
        return 409, {"error": f"{model} was a fitted twin: re-make it with {hit['repull']}", "cli": hit["repull"]}
    host, ctl, here = _target(req, name)
    if host is None or not here or not (ctl or {}).get("ok"):
        return 409, {"error": f"{name} is not a host this Studio pulls on ({cli})", "cli": cli}
    from halo_harness.studio import local_pull_job as J
    job = J.start(host, model, _pub(req), state_dir=req.state_dir)
    mark_repulled(req.state_dir, name, model)
    return 200, {**job, "cli": cli}


def dispatch_shelf(req):
    """The answer for a route of this file, else None."""
    if req.path == "local/shelf":
        return get_shelf(req) if req.method == "GET" else (405, {"error": "method not allowed"})
    if req.path == "local/shelf/repull":
        return post_repull(req) if req.method == "POST" else (405, {"error": "method not allowed"})
    m = _HOST.match(req.path)
    if not m:
        return None
    name, act = urllib.parse.unquote(m.group("name")), m.group("act")
    if act == "retire":
        return post_retire(req, name) if req.method == "POST" else (405, {"error": "method not allowed"})
    return get_host_shelf(req, name) if req.method == "GET" else (405, {"error": "method not allowed"})
