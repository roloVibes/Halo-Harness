"""halo_harness.studio.models_resolve -- `GET models/resolve` (Halo 3.1.4.0 R4; 3.6.0.0 R5b: a map's agent, where
it was a lineup's card): the model a role runs on, for the model select's "the map's (<model>)" / "the default
(<model>)".

    GET models/resolve?lineup=<map>&role=<agent>   that map's agent and its own model (`map` is the same key)
    GET models/resolve?role=<r>                    the model table (`roles.*`: what an Orchestra run's lead and
                                                   workers use), the map in use's agent named for a link
    GET models/resolve                             the default model

Answers {ref, source: lineup | roles | default | none, role, lineup, card}.
"""

from __future__ import annotations


def _card(name: str, role: str, req):
    """The map's agent `role`: {id, model}, {} without one, None without the map."""
    from halo_harness.crew.compile import compile_map
    try:
        c = compile_map(name, cwd=req.cwd, state_dir=req.state_dir)
    except Exception:
        return None
    if c.problems and not c.specs:
        return None
    spec = c.specs.get(role)
    return {"id": role, "model": spec.model if spec is not None and spec.model != "auto" else ""} if spec is not None else {}


def get_models_resolve(req):
    from halo_harness.theme import get_config_value
    role = str(req.query.get("role") or "").strip()
    lineup = str(req.query.get("map") or req.query.get("lineup") or "").strip()
    out = {"ref": "", "source": "none", "role": role, "lineup": lineup, "card": ""}
    if role and lineup:
        card = _card(lineup, role, req)
        if card is None:
            return 404, {"error": f"no map named {lineup!r}", "problems": [f"no map named {lineup!r}"]}
        if card.get("model"):
            return 200, {**out, "ref": card["model"], "source": "lineup", "card": card["id"]}
        out["card"] = card.get("id", "")
    if role and not lineup:
        from halo_harness.crew.in_use import map_name
        active = str(map_name(req.cwd) or "")
        card = _card(active, role, req) if active else None
        if card is not None:  # the map in use, and its agent of that name when it has one
            out.update(lineup=active, card=card.get("id", ""))
        from halo_harness.orchestra.adapters import role_model
        ref = role_model(role)
        if ref:
            return 200, {**out, "ref": ref, "source": "roles"}
    ref = str(get_config_value("model", "") or "")
    return 200, {**out, "ref": ref, "source": "default" if ref else "none"}
