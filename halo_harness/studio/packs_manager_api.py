"""halo_harness.studio.packs_manager_api -- the routes of Studio's Pack
Manager (Halo 3.2.0.0 R6, the Packs section; docs/STUDIO-packs.md). Same
loopback / origin / token guard as every Studio route. Each action runs the
function `halo pack` runs and answers its lines; an error is that command's
own lines (`problems`, the first as `error`), never other words. Every
change publishes `pack_changed` (studio/packs_studio_live.py), so each open
Studio -- this page too -- reads the manager and the registry again.

    GET  pack/manager                                  packs/manager.py payload: {packs, sources, problems, ...}
    POST pack/install {source | id, project?}          halo pack install <source|id> [--project]  201 {ok, lines, id}
    POST pack/sources {add | remove: <folder|url>}     halo pack sources add|remove
    POST pack/<id>/enable {grants?: [NAME], grant_all?}  halo pack enable <id> --grant NAME ... | --grant-all
    POST pack/<id>/grant {need, on}                    halo pack grant <id> <need> [--off]
    POST pack/<id>/disable | pack/<id>/update          halo pack disable | update <id>
    POST pack/<id>/remove {keep_config?}               halo pack remove <id> [--keep-config]
    GET|POST pack/<id>/settings                        R3's settings form (studio/packs_studio_api.py
                                                       get_config / post_config) for any pack installed here,
                                                       a disabled one too

`dispatch(req)` answers None for a path that is not one of these, so
packs_studio_api.dispatch_pack goes on with R3's routes. A "no pack ..."
line is a 404; every other refusal a 422.
"""

from __future__ import annotations

import re

VERBS = ("enable", "grant", "disable", "update", "remove", "settings")
_VERB = re.compile(r"^pack/(?P<id>[a-z][a-z0-9-]*)/(?P<verb>" + "|".join(VERBS) + r")$")


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _watched(req) -> None:
    """This server hears the frames the lifecycle's own `notify` sends (packs/grants.py notify_studio)."""
    from halo_harness.studio.packs_studio_live import watch
    if req.server is not None:
        watch(req.server)


def _answer(ok: bool, lines: list, *, status: int = 200, **extra):
    if ok:
        return status, {"ok": True, "lines": list(lines), **extra}
    code = 404 if lines and str(lines[0]).startswith("no pack ") else 422
    return code, {"ok": False, "error": lines[0] if lines else "not done", "problems": list(lines)}


def get_manager(req):
    from halo_harness.packs.manager import payload
    _watched(req)
    return 200, payload(cwd=req.cwd, state_dir=req.state_dir)


def post_install(req):
    from halo_harness.packs.fetch import source_for
    from halo_harness.packs.install import install
    body = _body(req)
    source = str(body.get("source") or body.get("id") or "").strip()
    if not source:
        return 422, {"ok": False, "error": "the body needs source (a folder or a git url) or id", "problems": []}
    _watched(req)
    ok, lines = install(source, project=body.get("project") is True, cwd=req.cwd, state_dir=req.state_dir)
    pack_id = _installed_id(lines) if ok else ""
    return _answer(ok, lines, status=201, id=pack_id, source=source_for(source))


def _installed_id(lines: list) -> str:
    m = re.match(r"^installed (\S+) ", str(lines[0]) if lines else "")
    return m.group(1) if m else ""


def post_sources(req):
    from halo_harness.packs import sources as SRC
    from halo_harness.studio.packs_studio_live import notify
    body = _body(req)
    if body.get("add"):
        ok, lines = SRC.add(str(body["add"]))
    elif body.get("remove"):
        ok, lines = SRC.remove(str(body["remove"]))
    else:
        return 422, {"ok": False, "error": "the body needs add or remove: a folder or a git url", "problems": []}
    _watched(req)
    if ok:
        notify("sources")  # config.json only: the registry's own signature does not move
    return _answer(ok, lines)


def _verb(req, pack_id: str, verb: str):
    from halo_harness.packs import grants as G
    body = _body(req)
    if verb == "enable":
        grants = [str(g) for g in body.get("grants") or [] if isinstance(g, str)]
        return G.enable_id(pack_id, grant=grants, grant_all=body.get("grant_all") is True, cwd=req.cwd, state_dir=req.state_dir)
    if verb == "grant":
        need = str(body.get("need") or "").strip()
        return G.grant(pack_id, [need] if need else [], on=body.get("on") is not False, cwd=req.cwd, state_dir=req.state_dir)
    if verb == "disable":
        return G.disable(pack_id, state_dir=req.state_dir)
    if verb == "update":
        from halo_harness.packs.install import update
        return update(pack_id, cwd=req.cwd, state_dir=req.state_dir)
    from halo_harness.packs.remove import remove
    return remove(pack_id, keep_config=body.get("keep_config") is True, cwd=req.cwd, state_dir=req.state_dir)


def settings(req, pack_id: str):
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import no_pack_line
    from halo_harness.studio.packs_studio_api import get_config, post_config
    pack = find(pack_id, cwd=req.cwd, state_dir=req.state_dir)
    if pack is None:
        return _answer(False, [no_pack_line(pack_id)])
    if req.method == "GET":
        return get_config(req, pack)
    return post_config(req, pack) if req.method == "POST" else (405, {"error": "method not allowed"})


def dispatch(req):
    """The manager's answer, or None for a pack/ path that is R3's."""
    if req.path == "pack/manager":
        return get_manager(req) if req.method == "GET" else (405, {"error": "method not allowed"})
    if req.path in ("pack/install", "pack/sources"):
        if req.method != "POST":
            return 405, {"error": "method not allowed"}
        return post_install(req) if req.path == "pack/install" else post_sources(req)
    m = _VERB.match(req.path)
    if not m:
        return None
    if m["verb"] == "settings":
        return settings(req, m["id"])
    if req.method != "POST":
        return 405, {"error": "method not allowed"}
    _watched(req)
    return _answer(*_verb(req, m["id"], m["verb"]))
