"""halo_harness.themes.packs -- the enabled packs' palettes, read live (Halo 3.3.12.0 R2; docs/EXTENSION_API.md "Themes").

    live()        {"<pack-id>/<id>": palette} of every pack that runs here (packs/registry.py snapshot: discovered,
                  enabled, no problem), packs in run order, palettes in manifest order
    json_rows()   the same for `GET settings/themes`: each with `pack`, `pack_name`, its tokens, its -daltonized
                  tokens and the CSS variables Studio draws it (and its -daltonized variant) in

A palette is `{id: "<pack-id>/<id>", local_id, pack, pack_name, label, posture, tokens}`. No watcher and no import-time
read: the answer is cached on the packs registry's own snapshot, which is cached on what it depends on (each pack.yaml,
state.json: mtime and size), so enabling, disabling, removing or editing a pack shows at the next call, and a home
with no packs folder costs the two `stat` calls the snapshot makes. themes/registry.py asks here on every lookup of a
name with a `/`, so `/theme`, `halo config set theme`, the settings route, Setup, the schema and Studio all see the
same set at call time.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_last: dict = {"snap": None, "palettes": {}}


def _snapshot():
    try:
        from halo_harness.packs.registry import snapshot
        return snapshot()
    except Exception:  # an unreadable packs folder: no pack palettes, the ten as always
        return None


def _build(snap) -> dict:
    from halo_harness.packs.manifest_themes import palettes
    out: dict = {}
    for pack in snap.active if snap is not None else []:
        if pack is None:
            continue
        for p in palettes(pack.id, pack.manifest):
            out[p["id"]] = {**p, "pack_name": pack.name}
    return out


def live() -> dict:
    snap = _snapshot()
    if snap is None or not snap.order:
        return {}
    with _lock:
        if _last["snap"] is snap:
            return _last["palettes"]
    found = _build(snap)
    with _lock:
        _last["snap"], _last["palettes"] = snap, found
    return found


def json_rows() -> "list[dict]":
    from halo_harness.themes import registry
    from halo_harness.themes.studio_css import studio_vars
    out = []
    for name, p in registry.packs().items():
        dal = registry.daltonize(p["tokens"], p["posture"])
        out.append({"id": name, "label": p["label"], "posture": p["posture"], "tokens": dict(p["tokens"]),
                    "daltonized": dal, "pack": p["pack"], "pack_name": p.get("pack_name") or p["pack"],
                    "local_id": p["local_id"], "vars": dict(studio_vars(p["tokens"], p["posture"])),
                    "daltonized_vars": dict(studio_vars(dal, p["posture"]))})
    return out
