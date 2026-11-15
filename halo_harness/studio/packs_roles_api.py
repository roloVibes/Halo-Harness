"""halo_harness.studio.packs_roles_api -- what a pack's rows carry (Halo 3.2.0.0 R2; 3.6.0.0 R5: its routes, roles/packs
and roles/clone, went with Cast's Lineups and Bios panels): the active packs, and a row's shadow and clone origin
(studio/model.py reads `row_fields`). The lineup and bio layers it reads go in the next round.
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
