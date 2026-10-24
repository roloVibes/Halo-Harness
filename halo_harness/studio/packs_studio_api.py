"""halo_harness.studio.packs_studio_api -- `/api/pack/...`, what the active
packs add to Studio (Halo 3.2.0.0 R3; docs/EXTENSION_API.md "Studio
contributions"). Same loopback / origin / token guard as every Studio route.

    GET  pack/registry              {version, core, packs: [entry]}  (packs/studio_registry.py); the first read
                                    starts the pack_changed watch (studio/packs_studio_live.py)
    GET  pack/<id>/file/<path>      a file under the pack's folder: markdown or JSON, or its bundle module
                                    (declared, and only with studio-script granted); the shell's CSP
    GET  pack/<id>/data/<path>      a markdown or JSON file in the pack's data folder (~/.halo/packs/.data/<id>/)
    GET  pack/<id>/artifact/<schema> an artifact panel's latest: the newest run's artifact of that schema (3.2.0.0 R5,
                                    studio/workflow_api.py): {schema, view, columns, data, run, path}
    GET  pack/<id>/config           {pack, name, fields: [{key, type, enum, help, default, value}], values, problems}
    POST pack/<id>/config {values: {key: value}}   checked against config.schema, then packs.settings.<id>.<key>
                                    for each (422 {error, problems}: nothing written)

3.2.0.0 R6: `pack/manager`, `pack/install`, `pack/sources` and `pack/<id>/<verb>`
(enable, grant, disable, update, remove, settings) are the Pack Manager's,
answered first by studio/packs_manager_api.py.

A pack that is not running here (not installed, disabled, a problem) answers
404 on every pack/<id>/ route of this module. The bundle is a module the page imports; an
import() sends no header, so the file route also takes the token in `?t=`
(served by `serve_module` from studio/server.py, as `/api/events` is).
"""

from __future__ import annotations

import hmac
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from halo_harness.studio.raw_body import RawBody

TYPES = {".md": "text/markdown", ".markdown": "text/markdown", ".txt": "text/plain", ".json": "application/json"}
MODULE_TYPES = {".js": "text/javascript", ".mjs": "text/javascript"}
_ROUTE = re.compile(r"^pack/(?P<id>[a-z][a-z0-9-]*)/(?P<what>file|data|config|artifact)(?:/(?P<path>.+))?$")


def _pack(req, pack_id: str):
    from halo_harness.packs.studio_registry import active_pack
    return active_pack(pack_id, cwd=req.cwd, state_dir=req.state_dir)


def _gone(pack_id: str):
    return 404, {"error": f"no pack {pack_id!r} runs here (halo pack list; a disabled pack shows nothing)"}


def get_registry(req):
    from halo_harness.packs.studio_registry import registry
    from halo_harness.studio.packs_studio_live import watch
    if req.server is not None:
        watch(req.server)
    return 200, registry(cwd=req.cwd, state_dir=req.state_dir)


def _inside(base: Path, rel: str):
    p = Path(rel)
    if p.is_absolute() or ".." in p.parts or not rel.strip():
        return None
    root = base.resolve()
    target = (root / p).resolve()
    return target if root in target.parents and target.is_file() else None


def _module_ok(pack, rel: str, state_dir) -> "tuple[bool, str]":
    """A bundle module is served when a bundle panel names it and studio-script is granted."""
    from halo_harness.packs import state as S
    from halo_harness.packs import studio_rules as R
    from halo_harness.packs.studio_registry import grant_line
    sources = {Path(str(p.get("source") or "")).as_posix() for _k, _s, p in R.panels_of(pack.manifest) if p.get("kind") == "bundle"}
    if Path(rel).as_posix() not in sources:
        return False, f"{rel} is not a bundle panel's source in {pack.id}'s pack.yaml"
    if R.SCRIPT not in S.granted(pack.id, S.load(state_dir)):
        return False, f"{pack.id}'s Studio script runs once you grant it: {grant_line(pack.id)}"
    return True, ""


def file_body(pack, rel: str, state_dir, *, data: bool = False):
    """`(status, RawBody | error dict)` for one file of the pack (or of its data folder)."""
    from halo_harness.ext.files import data_dir
    from halo_harness.studio.server import SHELL_CSP
    base = Path(data_dir(pack.id)) if data else Path(pack.root)
    target = _inside(base, rel)
    if target is None:
        return 404, {"error": f"{rel!r} is not a file in {pack.id}'s {'data folder' if data else 'folder'}"}
    suffix = target.suffix.lower()
    if suffix in MODULE_TYPES and not data:
        ok, why = _module_ok(pack, rel, state_dir)
        if not ok:
            return 403, {"error": why}
        ctype = MODULE_TYPES[suffix]
    elif suffix in TYPES:
        ctype = TYPES[suffix]
    else:
        return 404, {"error": f"{rel}: Studio serves a pack's markdown, JSON and granted bundle files"}
    return 200, RawBody(target.read_bytes(), ctype + "; charset=utf-8", {"Content-Security-Policy": SHELL_CSP})


def _fields(pack) -> list:
    from halo_harness.packs import settings as ST
    schema = ST.schema_of(pack.manifest) or {}
    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    defaults, values = ST.defaults_of(pack.manifest), ST.values(pack)
    out = []
    for key, sub in props.items():
        sub = sub if isinstance(sub, dict) else {}
        kind = sub.get("type") if isinstance(sub.get("type"), str) else "string"
        out.append({"key": key, "type": kind, "enum": list(sub["enum"]) if isinstance(sub.get("enum"), list) else None,
                    "help": str(sub.get("description") or ""), "default": defaults.get(key), "value": values.get(key)})
    return out


def get_config(req, pack):
    from halo_harness.packs import settings as ST
    return 200, {"pack": pack.id, "name": pack.name, "fields": _fields(pack), "values": ST.values(pack),
                 "problems": ST.problems(pack), "key": f"packs.settings.{pack.id}"}


def post_config(req, pack):
    from halo_harness.packs import settings as ST
    from halo_harness.schemas.check import check
    values = req.body.get("values") if isinstance(req.body, dict) else None
    if not isinstance(values, dict) or not values:
        return 422, {"error": "the body needs values: {key: value}", "problems": []}
    schema = ST.schema_of(pack.manifest)
    trial = {**ST.user_values(pack.id), **values}
    found = [f"packs.settings.{pack.id}.{f['key']}: {f['text']}" for f in check(trial, schema)] if schema else []
    if found:
        return 422, {"error": found[0], "problems": found}
    problems = [ln for key, value in values.items() for ln in ST.set_value(pack, str(key), value)]
    if problems:
        return 422, {"error": problems[0], "problems": problems}
    return get_config(req, pack)


def dispatch_pack(req):
    if req.path == "pack/registry" and req.method == "GET":
        return get_registry(req)
    from halo_harness.studio.packs_manager_api import dispatch as manager  # 3.2.0.0 R6: the Pack Manager's routes
    managed = manager(req)
    if managed is not None:
        return managed
    m = _ROUTE.match(req.path)
    if not m:
        return 404, {"error": f"no route for {req.method} /api/{req.path}"}
    pack = _pack(req, m["id"])
    if pack is None:
        return _gone(m["id"])
    if m["what"] == "config" and not m["path"]:
        if req.method == "GET":
            return get_config(req, pack)
        return post_config(req, pack) if req.method == "POST" else (405, {"error": "method not allowed"})
    if req.method != "GET" or not m["path"]:
        return 405, {"error": "method not allowed"}
    if m["what"] == "artifact":  # 3.2.0.0 R5: the newest run's artifact of a schema (studio/workflow_api.py)
        from halo_harness.studio.workflow_api import pack_artifact
        return pack_artifact(req, pack, m["path"])
    return file_body(pack, m["path"], req.state_dir, data=m["what"] == "data")


def serve_module(handler) -> None:
    """`GET /api/pack/<id>/file/<bundle>?t=<token>`: the module an import() asks for (no Authorization header)."""
    from halo_harness.studio.api import Request
    if not handler._local_only():
        return
    origin = handler.headers.get("Origin")
    if origin and origin not in handler._own_origin():
        return handler._json(403, {"error": "foreign origin"})
    parts = urlsplit(handler.path)
    presented = {k: v[-1] for k, v in parse_qs(parts.query).items()}.get("t", "")
    if not presented or not hmac.compare_digest(presented, handler.server.token):
        return handler._json(403, {"error": "missing or wrong studio token in ?t="})
    req = Request(method="GET", path=unquote(parts.path)[len("/api/"):], query={}, body={}, cwd=handler.server.cwd,
                  state_dir=handler.server.state_dir, server=handler.server)
    try:
        status, obj = dispatch_pack(req)
    except Exception as e:  # a bad file never takes the server down
        status, obj = 500, {"error": f"{type(e).__name__}: {e}"}
    if isinstance(obj, RawBody):
        return handler._send(status, obj.body, obj.ctype, obj.headers)
    handler._send(status, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")
