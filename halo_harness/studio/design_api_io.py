"""halo_harness.studio.design_api_io -- the project-level handlers of Studio's
Design mode that touch files rather than turns (Halo 3.0.1.0 round D3): the
shared lookups, the design system, versions and restore, sync, export and the
handoff bundle. Routed from design_api.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from halo_harness.design.store import Project

_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_EXPORTS = ("folder", "html", "png", "svg", "pdf")


def _bad(lines, status: int = 422):
    lines = [lines] if isinstance(lines, str) else list(lines)
    return status, {"error": lines[0], "problems": lines}


def _project(req):
    slug = req.params.get("slug", "")
    p = Project.open(slug, state_dir=req.state_dir) if _SLUG.match(slug) else None
    return p, ((404, {"error": f"no design project named {slug!r}"}) if p is None else None)


def _artboard(req, p):
    aid = str(req.body.get("artboard") or req.params.get("aid") or "")
    hit = next((a for a in p.artboards() if a["id"] == aid), None)
    return hit, (None if hit else (404, {"error": f"no artboard {aid!r} in {p.slug}"}))


def put_system(req):
    p, err = _project(req)
    if err:
        return err
    system = req.body.get("system", req.body)
    if not isinstance(system, dict) or not isinstance(system.get("tokens", {}), dict):
        return _bad("system is {tokens: {group: {name: value}}, components, sources}")
    p.save_system(system)
    return 200, {"system": p.system()}


def versions(req):
    p, err = _project(req)
    if err:
        return err
    a, err = _artboard(req, p)
    if err:
        return err
    out = []
    for n in sorted(a["versions"]):
        meta = _json_file(p.artboard_dir(a["id"]) / f"v{n}" / "version.json")
        out.append({"version": n, "created": meta.get("created", ""), "note": meta.get("note", "")})
    return 200, out


def _json_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def restore(req):
    p, err = _project(req)
    if err:
        return err
    a, err = _artboard(req, p)
    if err:
        return err
    try:
        n = int(req.body.get("version"))
    except (TypeError, ValueError):
        return _bad("version is a number")
    if not p.restore(a["id"], n):
        return _bad(f"{a['id']} has no version v{n}", 404)
    return 200, {"versions": p.snapshot(note=f"restore v{n}")}


def sync(req):
    from halo_harness.design import sync as S
    p, err = _project(req)
    if err:
        return err
    src = str(req.body.get("source") or "").strip()
    if not src:
        return _bad("source is a folder path or a URL")
    if src.startswith(("http://", "https://")):
        try:
            found = S.capture_url(src)
        except Exception as e:
            return _bad(f"could not read {src}: {e}")
    elif Path(src).expanduser().is_dir():
        found = S.scan_codebase(Path(src).expanduser().resolve())
    else:
        return _bad(f"{src} is not a folder or a URL")
    merged = S.write_system(p, found)
    return 200, {"system": merged, "tokens": sum(len(v) for v in merged["tokens"].values())}


def export(req):
    from halo_harness.design.export import export_project
    p, err = _project(req)
    if err:
        return err
    kind = str(req.body.get("as") or "folder")
    if kind not in _EXPORTS:
        return _bad(f"as is one of {', '.join(_EXPORTS)}")
    return 200, {"lines": export_project(p, kind, artboard=str(req.body.get("artboard") or ""))}


def handoff(req):
    from halo_harness.design.export import handoff_bundle
    p, err = _project(req)
    if err:
        return err
    return 200, {"path": str(handoff_bundle(p))}
