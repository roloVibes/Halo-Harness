"""The design pack's Studio routes (docs/EXTENSION_API.md "A pack's own routes"): Studio imports this module once the
owner grants studio-routes and answers `/api/packs/design/design/<path>` with `handle`, behind its token.

    GET  ping                                  {ok, pack, projects}: the kit's probe
    GET  crafts[?probe=1]                      the craft apps: registered here or not, and (probe) do they answer
    GET  _files/<slug>/<artboard>/<file>        an artboard's own file for the page's sandboxed iframe (files.py's CSP)
    POST render, GET renders/<id>              a ComfyUI workflow into a project (render_api.py)
    everything else                            the projects, turns, comments, knobs, versions, system, exports (api.py)

The projects live in the pack's data folder (`projects/`); a `~/.halo/design` from before the design pack is moved
there once, and the first projects listing says so in one line (`moved`). A design asset is up to 15 MB as base64, so
this prefix takes a body up to MAX_BODY.
"""

from __future__ import annotations

import re
import shutil
import sys
import types
from pathlib import Path

MAX_BODY = 22_000_000
_MOVED: dict = {}  # data folder -> the line said once


def migrate(state_dir: Path, data_dir: Path) -> str:
    """Move `<state>/design` (Halo before 3.3.13.0) to `<data>/projects` once; the line saying so, or ''."""
    old, new = Path(state_dir) / "design", Path(data_dir) / "projects"
    if not old.is_dir() or new.exists() or not any(old.iterdir()):
        return ""
    try:
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old), str(new))
    except OSError as e:
        return f"your design projects stay in {old}: moving them to {new} failed ({e})"
    return f"moved your design projects from {old} to {new} (the design pack keeps them in its data folder)"


def _req(ctx, method: str, path: str, body, query):
    return types.SimpleNamespace(method=method, path="design/" + path, query=dict(query or {}), body=body or {},
                                 cwd=ctx.cwd, state_dir=ctx.data_dir, params={}, publish=ctx.publish, server=None)


def crafts(query) -> "tuple[int, dict]":
    from .crafts import APPS
    from .crafts_probe import craft_server_configs, probe_crafts, probe_lines
    configs = craft_server_configs()
    out = {"apps": [{"app": a, "for": spec["for"], "registered": a in configs} for a, spec in APPS.items()],
           "line": f"{len(configs)} of {len(APPS)} craft apps registered; a design turn allows every present one as tools"}
    if str(query.get("probe") or "") in ("1", "true"):
        rows = probe_crafts(configs)
        out.update(probe=rows, probe_lines=probe_lines(rows))
    return 200, out


def handle(ctx, method, path, body, query):
    key = str(ctx.data_dir)
    if key not in _MOVED:
        _MOVED[key] = migrate(ctx.state_dir, ctx.data_dir)
        if _MOVED[key]:
            print(f"halo studio: design: {_MOVED[key]}", file=sys.stderr)
    if method == "GET" and path == "ping":
        from .store import Project
        return 200, {"ok": True, "pack": ctx.pack_id, "projects": len(Project.list(state_dir=ctx.data_dir))}
    if method == "GET" and path == "crafts":
        return crafts(query)
    if path.startswith("_files/"):
        if method != "GET":
            return 405, {"error": "method not allowed"}
        from . import files
        status, data, ctype = files.read(ctx.data_dir, path, query or {})
        return status, data, ctype, {"Content-Security-Policy": files.csp_for(ctype)}
    from . import render_api
    if path == "render" and method == "POST":
        return render_api.post_render(_req(ctx, method, path, body, query))
    m = re.match(r"^renders/(?P<pid>[A-Za-z0-9_.-]+)$", path)
    if m and method == "GET":
        req = _req(ctx, method, path, body, query)
        req.params = m.groupdict()
        return render_api.get_render(req)
    from .api import dispatch_design
    status, out = dispatch_design(_req(ctx, method, path, body, query))
    if path == "projects" and method == "GET" and _MOVED.get(key) not in ("", "said") and isinstance(out, dict):
        out = {**out, "moved": _MOVED[key]}
        _MOVED[key] = "said"  # once
    return status, out
