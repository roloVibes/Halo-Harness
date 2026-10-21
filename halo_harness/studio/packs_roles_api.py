"""halo_harness.studio.packs_roles_api -- Studio's Roles over packs (Halo
3.2.0.0 R2): the active packs the Lineups and Bios panels group by, and
Clone (Customize is Clone, then the copy opened).

    GET  roles/packs                 [{id, name, version, scope}] -- the packs that run here (a disabled one is absent)
    POST roles/clone?scope=user|project  {kind: bio|lineup, name: <id>--<name>, as?: <name>, replace?: true}
         201 {ok, name, path, from_pack, replaced}
         409 {error, exists: true, name, path}     a file of yours has that name: ask, then send replace: true
         404 / 422 {error, problems}

Clone never writes into a file of yours unless the request says `replace`
(Studio sends it only from the confirm), and never into the pack's folder.
"""

from __future__ import annotations


def active_packs(cwd=None, state_dir=None) -> "list[dict]":
    from halo_harness.packs.contribute import _active
    return [{"id": p.id, "name": p.name, "version": p.version, "scope": p.scope} for p in _active(cwd, state_dir)]


def row_fields(kind: str, name: str, data: dict, *, cwd=None, state_dir=None) -> dict:
    """What a Lineups / Bios row adds: the pack name a file of yours shadows (and where yours is), the pack a
    clone came from, and for a bio its capability tags and the line when no catalog model has them."""
    from halo_harness.packs.roles import shadow_of, shown_path
    out = {"shadows": "", "shadowed_by": "", "from_pack": str(data.get("from_pack") or "")}
    pack_id = shadow_of(kind, name, str(data.get("_source") or ""), cwd=cwd, state_dir=state_dir)
    if pack_id:
        out.update(shadows=pack_id, shadowed_by=shown_path(str(data.get("_path") or ""), cwd=cwd))
    if kind == "bios":
        info = data.get("_model") if isinstance(data.get("_model"), dict) else {}
        out.update(capabilities=list(info.get("capabilities") or []), model_problem=str(info.get("problem") or ""))
    return out


def get_packs(req):
    return 200, active_packs(req.cwd, req.state_dir)


def post_clone(req):
    from halo_harness.packs.clone import clone
    body = req.body if isinstance(req.body, dict) else {}
    kind, name = str(body.get("kind") or ""), str(body.get("name") or "").strip()
    out = clone(kind, name, as_name=(str(body.get("as") or "").strip() or None), project=req.project,
                replace=body.get("replace") is True, cwd=req.cwd, state_dir=req.state_dir)
    if out.get("ok"):
        return 201, out
    if out.get("exists"):
        return 409, out
    status = 404 if "not a pack's" in out.get("error", "") else 422
    return status, {"error": out.get("error") or "not cloned", "problems": list(out.get("problems") or [])}


ROUTES = [("GET", r"^roles/packs$", get_packs), ("POST", r"^roles/clone$", post_clone)]
