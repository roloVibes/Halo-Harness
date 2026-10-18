"""halo_harness.studio.design_assets_api -- a Design project's assets folder
in Studio (Halo 3.0.1.0 round D5; 3.1.0.0 R2 cut it out of
design_api_more.py): list it, and save an upload into it. Routed from
design_api.py.
"""

from __future__ import annotations

from halo_harness.design import assets as A
from halo_harness.studio.design_request import _bad, _project


def assets_list(req):
    p, err = _project(req)
    return err or (200, {"assets": A.list_assets(p)})


def assets_post(req):
    p, err = _project(req)
    if err:
        return err
    if not str(req.body.get("name") or "").strip():
        return _bad("an asset needs a name")
    try:
        row = A.save_asset(p, str(req.body["name"]), req.body.get("data_base64"))
    except A.TooBig as e:
        return 413, {"error": str(e), "problems": [str(e)]}
    except ValueError as e:
        return _bad(str(e))
    return 201, row
