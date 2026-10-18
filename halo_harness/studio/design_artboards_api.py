"""halo_harness.studio.design_artboards_api -- the routes of one artboard in
Studio's Design mode (Halo 3.0.1.0 rounds D3 / D5, 3.0.7.0 R3; 3.1.0.0 R2
gathered them here from design_api_more.py and design_api_io.py): its
versions and a restore, the contrast check, rename and delete. Routed from
design_api.py.
"""

from __future__ import annotations

from halo_harness.design import contrast as K
from halo_harness.design.jsonio import project_lock
from halo_harness.studio import design_turns as turns
from halo_harness.studio.design_request import _artboard, _bad, _json_file, _project


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


def contrast(req):
    p, err = _project(req)
    if err:
        return err
    a, err = _artboard(req, p)
    if err:
        return err
    return 200, K.check_artboard(p, a["id"])


def artboard_rename(req):
    """POST artboard/<aid>/rename {name}: the artboard's title (its id, folder and versions stay)."""
    p, err = _project(req)
    if err:
        return err
    a, err = _artboard(req, p)
    if err:
        return err
    name = " ".join(str(req.body.get("name") or "").split())[:80]
    if not name:
        return _bad("an artboard needs a name")
    with project_lock(p.path):
        meta = p._meta_for_write()
        for row in meta.get("artboards") or []:
            if row.get("id") == a["id"]:
                row["title"] = name
        p.save_meta(meta)
    return 200, {"id": a["id"], "title": name}


def artboard_delete(req):
    """DELETE artboard/<aid>: the artboard, its files and versions; its open pins are resolved."""
    p, err = _project(req)
    if err:
        return err
    a, err = _artboard(req, p)
    if err:
        return err
    if turns.live_turn(p.slug):
        return 409, {"error": "a turn is running in this project: delete the artboard when it has finished"}
    pins = [c["id"] for c in p.comments() if c.get("artboard") == a["id"] and not c.get("resolved")]
    if pins:
        p.resolve_comments(pins)
    p.remove_artboard(a["id"])
    return 200, {"deleted": a["id"], "resolved": len(pins)}
