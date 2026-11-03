"""halo_harness.studio.setup_packs_api -- a pack's own Setup blocks in Studio's Setup section (Halo 3.3.11.0 R3;
docs/STUDIO-setup.md "A pack's blocks", docs/EXTENSION_API.md "Setup blocks"), reached from
studio/setup_api.dispatch_setup. Same loopback / origin / token guard as every Studio route.

    GET  setup/packs                    {packs: [pack]}: the enabled packs' blocks (`pack_blocks`)
    GET  setup/packs/<id>/<block>       the block; a form's as packs_studio_api.get_config answers (its fields only)
    POST setup/packs/<id>/<block>       a form: {values} -> checked against config.schema, written to
                                        packs.settings.<id>, the block marked done -> 200 the form's config, state, lines;
                                        422 {error, problems} and nothing written (a key the block does not show too)
                                        a note: {} -> dismissed (done) -> 200 {...setup state, lines}
                                        a check: {} -> the checks job on `pack:<id>:<block>` -> 202 {job}; 409 while one runs
                                        any: {skip: true} -> skipped -> 200 {...setup state, lines}

    pack = {id, name, help, blocks: [{key: "pack:<id>:<block>", id, title, kind, after, help, state, at,
             fields?, values?, config_key? (form), what?, cost?, time?, writes? (check), text? (note)}]}

Nothing private: an answer carries the pack's own manifest lines, its own settings for the form's keys and its own
note file -- never an environment value, a key, the provider state or another pack's settings. A pack that is not
running here (not installed, disabled, a problem) has no blocks and answers 404.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

_ROUTE = re.compile(r"^setup/packs/(?P<id>[a-z][a-z0-9-]*)/(?P<block>[a-z][a-z0-9_-]*)$")
NOTE_MAX = 20000


def _note_text(pack, rel) -> str:
    try:
        root = Path(pack.root).resolve()
        target = (root / str(rel)).resolve()
        if root not in target.parents:
            return ""
        return target.read_text(encoding="utf-8", errors="replace")[:NOTE_MAX]
    except (OSError, ValueError):
        return ""


def _form(pack, e: dict) -> dict:
    from halo_harness.packs import settings as ST
    from halo_harness.packs.manifest_setup import form_fields
    from halo_harness.studio.packs_studio_api import _fields
    keys = form_fields(pack.manifest, e)
    values = ST.values(pack)
    return {"fields": [f for f in _fields(pack) if f["key"] in keys], "values": {k: values.get(k) for k in keys},
            "config_key": f"packs.settings.{pack.id}"}


def block_view(pack, e: dict, seen: dict) -> dict:
    from halo_harness.packs.manifest_setup import key_of
    from halo_harness.packs.setup_state import state_of
    rec = state_of(pack.id, str(e["id"]), data=seen)
    kind = str(e.get("kind"))
    out = {"key": key_of(pack.id, str(e["id"])), "id": str(e["id"]), "title": str(e.get("title") or e["id"]),
           "kind": kind, "after": str(e.get("after") or ""),
           "help": str(e.get("help") or pack.manifest.get("description") or ""), "state": rec["state"], "at": rec["at"]}
    if kind == "form":
        out.update(_form(pack, e))
    elif kind == "check":
        out.update({w: str(e.get(w) or "") for w in ("what", "cost", "time", "writes")})
    elif kind == "note":
        out["text"] = _note_text(pack, e.get("text"))
    return out


def pack_blocks(cwd=None, state_dir=None) -> "list[dict]":
    """Each enabled pack with Setup blocks, in the packs' running order (`[]` when none has any)."""
    from halo_harness.packs.manifest_setup import setup_of
    from halo_harness.packs.registry import active
    from halo_harness.packs.setup_state import read
    out = []
    for pack in active(cwd=cwd, state_dir=state_dir):
        entries = [e for e in setup_of(pack.manifest) if isinstance(e.get("id"), str)]
        if entries:
            seen = read(pack.id, state_dir)
            out.append({"id": pack.id, "name": str(pack.name or pack.id),
                        "help": str(pack.manifest.get("description") or ""),
                        "blocks": [block_view(pack, e, seen) for e in entries]})
    return out


def _find(req, pack_id: str, block_id: str):
    from halo_harness.packs.manifest_setup import block
    from halo_harness.packs.studio_registry import active_pack
    pack = active_pack(pack_id, cwd=req.cwd, state_dir=req.state_dir)
    e = block(pack.manifest, block_id) if pack is not None else None
    return pack, e


def _state(req) -> dict:
    from halo_harness.studio.setup_state import setup_state
    return setup_state(req.cwd, req.state_dir)


def get_block(req, pack, e):
    from halo_harness.packs.setup_state import read
    view = block_view(pack, e, read(pack.id, req.state_dir))
    if view["kind"] != "form":
        return 200, view
    from halo_harness.packs import settings as ST
    return 200, {"pack": pack.id, "name": pack.name, "key": view["config_key"], "fields": view["fields"],
                 "values": view["values"], "problems": ST.problems(pack), "block": view}


def _save_form(req, pack, e):
    from halo_harness.packs.manifest_setup import form_fields
    from halo_harness.packs.setup_state import DONE, mark
    from halo_harness.studio.packs_studio_api import post_config
    body = req.body if isinstance(req.body, dict) else {}
    values = body.get("values")
    if not isinstance(values, dict) or not values:
        return 422, {"error": "the body needs values: {key: value}", "problems": []}
    shown = form_fields(pack.manifest, e)
    stray = [str(k) for k in values if k not in shown]
    if stray:
        lines = [f"packs.settings.{pack.id}.{k}: not a field of the {e.get('title') or e['id']} block "
                 f"({', '.join(shown)})" for k in stray]
        return 422, {"error": lines[0], "problems": lines}
    status, answer = post_config(dataclasses.replace(req, body={"values": dict(values)}), pack)
    if status != 200:
        return status, answer
    mark(pack.id, str(e["id"]), DONE, by="studio", state_dir=req.state_dir)
    _status, view = get_block(req, pack, e)
    saved = ", ".join(f"{k} = {values[k]}" for k in values)
    return 200, {**view, "lines": [f"packs.settings.{pack.id}: {saved} (saved to config.json)"]}


def _run_check(req, pack, e):
    from halo_harness.packs.manifest_setup import key_of
    from halo_harness.studio.setup_check_api import post_check
    return post_check(dataclasses.replace(req, body={"checks": [key_of(pack.id, str(e["id"]))]}))


def post_block(req, pack, e):
    from halo_harness.packs.setup_state import DONE, SKIPPED, mark
    body = req.body if isinstance(req.body, dict) else {}
    title = str(e.get("title") or e["id"])
    if body.get("skip") is True:
        mark(pack.id, str(e["id"]), SKIPPED, by="studio", state_dir=req.state_dir)
        return 200, {**_state(req), "lines": [f"{pack.id}: {title}: skipped (halo setup {pack.id} opens it again)"]}
    kind = e.get("kind")
    if kind == "form":
        return _save_form(req, pack, e)
    if kind == "check":
        return _run_check(req, pack, e)
    mark(pack.id, str(e["id"]), DONE, by="studio", state_dir=req.state_dir)
    return 200, {**_state(req), "lines": [f"{pack.id}: {title}: read"]}


def dispatch_setup_packs(req):
    """The answer for a route of this module, or None when the path is another module's."""
    if req.path == "setup/packs":
        if req.method != "GET":
            return 405, {"error": "method not allowed"}
        return 200, {"packs": pack_blocks(req.cwd, req.state_dir)}
    m = _ROUTE.match(req.path)
    if not m:
        return None
    pack, e = _find(req, m["id"], m["block"])
    if pack is None:
        return 404, {"error": f"no pack {m['id']!r} runs here (halo pack list; a disabled pack shows no Setup block)"}
    if e is None:
        return 404, {"error": f"{m['id']} has no Setup block {m['block']!r}"}
    if req.method == "GET":
        return get_block(req, pack, e)
    return post_block(req, pack, e) if req.method == "POST" else (405, {"error": "method not allowed"})
