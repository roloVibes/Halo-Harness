"""halo_harness.studio.models_resolve -- `GET models/resolve` (Halo 3.1.4.0 R4):
the model a role runs on, for the model select's "the lineup's (<model>)" /
"the default (<model>)" and the Team stage's "runs on".

    GET models/resolve?lineup=<name>&role=<r>   that lineup's card for the role
                                                (its alias, else its role) and the
                                                model it resolves to (a Team member
                                                runs under it)
    GET models/resolve?role=<r>                 the role table (`halo roles`: what an
                                                Orchestra run's lead and workers use),
                                                the active lineup's card named for a link
    GET models/resolve                          the default model

Answers {ref, source: lineup | roles | default | none, role, lineup, card}.
"""

from __future__ import annotations


def _card(lineup: str, role: str, req):
    """The lineup's card for `role`: a graph node, {} without one, None without the lineup."""
    from halo_harness import teams_yaml as T
    from . import model as M
    try:
        resolved = T.resolve_team_template(lineup, cwd=req.cwd, state_dir=req.state_dir)
    except Exception:
        resolved = None
    if not resolved:
        return None
    nodes = M.graph_for(resolved, cwd=req.cwd, state_dir=req.state_dir, catalog={})["nodes"]
    return next((n for n in nodes if n["alias"] == role), None) or next((n for n in nodes if n["role"] == role), None) or {}


def get_models_resolve(req):
    from halo_harness.theme import get_config_value
    role = str(req.query.get("role") or "").strip()
    lineup = str(req.query.get("lineup") or "").strip()
    out = {"ref": "", "source": "none", "role": role, "lineup": lineup, "card": ""}
    if role and lineup:
        card = _card(lineup, role, req)
        if card is None:
            return 404, {"error": f"no lineup named {lineup!r}", "problems": [f"no lineup named {lineup!r}"]}
        if card.get("model"):
            return 200, {**out, "ref": card["model"], "source": "lineup", "card": card["id"]}
        out["card"] = card.get("id", "")
    if role and not lineup:
        active = str(get_config_value("team", "") or "")
        card = _card(active, role, req) if active else None
        if card:
            out.update(lineup=active, card=card.get("id", ""))
        from halo_harness.orchestra.adapters import role_model
        ref = role_model(role)
        if ref:
            return 200, {**out, "ref": ref, "source": "roles"}
    ref = str(get_config_value("model", "") or "")
    return 200, {**out, "ref": ref, "source": "default" if ref else "none"}
