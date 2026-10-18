"""halo_harness.studio.design_export_api -- what leaves a Design project in
Studio (Halo 3.0.1.0 round D3; 3.1.0.0 R2 cut it out of design_api_io.py):
an export (folder, html, png, svg or pdf; one artboard or all) and the
handoff bundle (design/export.py). Routed from design_api.py.
"""

from __future__ import annotations

from halo_harness.studio.design_request import _bad, _project

_EXPORTS = ("folder", "html", "png", "svg", "pdf")


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
