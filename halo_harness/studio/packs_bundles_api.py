"""halo_harness.studio.packs_bundles_api -- the Pack Manager's Bundles group (Halo 3.3.7.0 R5; docs/STUDIO-packs.md
"Bundles"; packs_manager_api.dispatch sends `pack/bundles` and `pack/bundle/<id>/<verb>` here). The same loopback /
origin / token guard as every Studio route.

    GET  pack/bundles?host=           {bundles: [{id, name, description, scope, installed, on, verdict}], host}
                                      every bundle here and shipped, each with its verdict (local_sched/bundle_fit.py)
    POST pack/bundle/<id>/on {host?}  the tick: halo pack on <id> -- a ready bundle is claimed, held by this Studio
                                      (undone when it is unticked or this Studio exits); any other state answers 422
                                      with the verdict's own line
    POST pack/bundle/<id>/off         the untick: halo pack off <id>

The verdict's one button ("download 2 (4.1 GB, ~6 min)") is the existing Download and verify job: the page posts
local/library/verify {host, name} for each tag (studio/local_search_api.py). Nothing downloads here.
"""

from __future__ import annotations

import re

_VERB = re.compile(r"^pack/bundle/(?P<id>[a-z][a-z0-9-]*)/(?P<verb>on|off)$")


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def get_bundles(req):
    from halo_harness.local_sched.bundle_fit import verdict
    from halo_harness.local_sched.reserve import claims
    from halo_harness.packs.bundles import listing
    host = str((req.query or {}).get("host") or "").strip() or None
    on = {c["bundle"] for c in claims(None, state_dir=req.state_dir)}
    rows = []
    for e in listing(cwd=req.cwd, state_dir=req.state_dir):
        v = verdict(e["block"], host, state_dir=req.state_dir) if e["block"] else None
        rows.append({k: e[k] for k in ("id", "name", "description", "scope", "installed", "problems")} |
                    {"on": e["id"] in on, "verdict": v, "cli": {"verdict": f"halo pack verdict {e['id']}",
                                                                "on": f"halo pack on {e['id']}",
                                                                "off": f"halo pack off {e['id']}"}})
    return 200, {"bundles": rows, "host": host or ""}


def _notify() -> None:
    try:
        from halo_harness.studio.packs_studio_live import notify
        notify("bundle")
    except Exception:
        pass


def post_verb(req, bundle_id: str, verb: str):
    from halo_harness.local_sched.reserve_act import claim, release
    if verb == "on":
        host = str(_body(req).get("host") or "").strip() or None
        ok, lines, v = claim(bundle_id, host=host, holder="process", cwd=req.cwd, state_dir=req.state_dir)
        _notify()
        if not ok:
            code = 404 if lines and lines[0].startswith("no bundle ") else 422
            return code, {"ok": False, "error": lines[0] if lines else "not turned on", "problems": lines, "verdict": v}
        return 200, {"ok": True, "lines": lines, "verdict": v}
    ok, lines = release(bundle_id, cwd=req.cwd, state_dir=req.state_dir)
    _notify()
    return 200, {"ok": ok, "lines": lines}


def dispatch(req):
    """The answer for a bundle route, else None."""
    if req.path == "pack/bundles":
        return get_bundles(req) if req.method == "GET" else (405, {"error": "method not allowed"})
    m = _VERB.match(req.path)
    if not m:
        return None
    if req.method != "POST":
        return 405, {"error": "method not allowed"}
    return post_verb(req, m["id"], m["verb"])
