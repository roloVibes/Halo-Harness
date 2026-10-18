"""halo_harness.studio.design_system_api -- a Design project's design system
in Studio (Halo 3.0.1.0 round D3; 3.1.0.0 R2 cut it out of
design_api_io.py): save it as edited, and sync it from a codebase folder or
a URL (design/sync.py finds the tokens). Routed from design_api.py.
"""

from __future__ import annotations

from pathlib import Path

from halo_harness.studio.design_request import _bad, _project


def put_system(req):
    p, err = _project(req)
    if err:
        return err
    system = req.body.get("system", req.body)
    if not isinstance(system, dict) or not isinstance(system.get("tokens", {}), dict):
        return _bad("system is {tokens: {group: {name: value}}, components, sources}")
    p.save_system(system)
    return 200, {"system": p.system()}


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
