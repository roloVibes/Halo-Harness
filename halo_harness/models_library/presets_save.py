"""halo_harness.models_library.presets_save -- Halo 3.3.6.0 R2: Save as role template, and the role offer after
Download and verify, both through the teams path (teams_yaml.save_team_template; R0b's `local-coder` lane is the
precedent, agent/main_model_check.write_lane).

    save(preset, *, state_dir, cwd=None, model="", lineup="", bundle_over=None) -> (ok, lines, lineup name)
        no lineup: `local-<preset>` -- main on the session model and the preset's role (its agent, the model when
        one is picked), the bundle kept as the lineup's `search: {<role>: bundle}`; a lineup named: that lineup's
        entry for the role gets the model (added when it has none) and the bundle
    assign(role, ref, *, state_dir, cwd=None, lineup="") -> (ok, lines, lineup name)
        "assign `verify` to <model>?": the role's entry in the lineup named, else the active one, else
        `local-<preset>`, gets `models.preference: <ref>`; an active lineup is applied again (roles.* follow)
    LINEUP_ROLE: the lineup role each preset fills (verify, planner, small, ...)
"""

from __future__ import annotations

import copy
from typing import Optional

LINEUP_ROLE = {"coder": "coder", "reasoner": "planner", "bulk": "small", "compactor": "compaction",
               "verifier": "verify", "security": "security", "multimodal": "eyes", "offline": "main", "embeddings": ""}


def _active(state_dir) -> str:
    try:
        from halo_harness.config_where import _active_lineup
        from halo_harness.config.paths import bridge_home
        return _active_lineup(state_dir if state_dir is not None else bridge_home())
    except Exception:
        return ""


def _template(preset: str, b: dict, model: str) -> dict:
    role = LINEUP_ROLE.get(preset, "")
    main = {"agent": "default-model", "role": "main"}
    agents = [main]
    if role == "main":
        if model:
            main["models"] = {"preference": model}
    elif role and b.get("agent"):
        entry = {"agent": b["agent"], "role": role, "use_for": [role]}
        if model:
            entry["models"] = {"preference": model}
        agents.append(entry)
    return {"description": f"local {b['title']}: the Library preset kept as a role template (Local -> Library)",
            "version": "1.0", "tags": ["local", "preset", preset],
            "about": (f"Main runs on the session model. The {role or 'search'} role's model is a local one found by "
                      f"the {b['title']} preset ({b.get('why')}); `search` keeps the filters, so Find a model for this "
                      "role opens the Library with them."),
            "agents": agents, "search": {role or preset: _clean(b)}}


def _clean(b: dict) -> dict:
    return {k: copy.deepcopy(b[k]) for k in ("id", "needs", "fit", "supply", "intent") if k in b}


def _entry_for(data: dict, role: str) -> Optional[dict]:
    return next((e for e in data.get("agents") or [] if isinstance(e, dict) and (e.get("as") or e.get("role")) == role), None)


def _into(name: str, role: str, model: str, b: Optional[dict], agent: str, *, state_dir, cwd) -> "tuple[bool, list]":
    from halo_harness.teams_yaml import _expand_roles_shorthand, load_team_template_raw, save_team_template
    raw = load_team_template_raw(name, cwd=cwd, state_dir=state_dir)
    if raw is None:
        return False, [f"no lineup named {name!r}"]
    data = _expand_roles_shorthand(copy.deepcopy(raw))
    data = {k: v for k, v in data.items() if not str(k).startswith("_") and k != "name"}
    entry = _entry_for(data, role)
    if entry is None:
        entry = {"agent": agent or "general", "role": role}
        data.setdefault("agents", []).append(entry)
    if model:
        entry["models"] = {**(entry.get("models") or {}), "preference": model}
    if b is not None:
        data["search"] = {**(data.get("search") or {}), role: _clean(b)}
    return save_team_template(name, data, cwd=cwd, state_dir=state_dir)


def _ensure(state_dir) -> None:
    try:
        from halo_harness.teams_yaml import ensure_builtin_team_templates
        ensure_builtin_team_templates(state_dir=state_dir)
    except Exception:
        pass


def save(preset: str, *, state_dir=None, cwd=None, model: str = "", lineup: str = "",
         bundle_over: Optional[dict] = None) -> "tuple[bool, list, str]":
    from halo_harness.models_library.presets import PRESETS, bundle
    if preset not in PRESETS:
        return False, [f"no preset {preset!r}: one of {', '.join(PRESETS)}"], ""
    b = bundle(preset, **(bundle_over or {}))
    _ensure(state_dir)
    role = LINEUP_ROLE.get(preset, "")
    if lineup:
        if not role:
            return False, [f"{b['title']} fills no lineup role: save it as local-{preset} instead"], lineup
        ok, lines = _into(lineup, role, model, b, b.get("agent") or "", state_dir=state_dir, cwd=cwd)
        return ok, ([f"{lineup}: the {role} role keeps the {b['title']} filters" + (f", on {model}" if model else "")]
                    if ok else list(lines)), lineup
    from halo_harness.teams_yaml import save_team_template
    name = f"local-{preset}"
    ok, problems = save_team_template(name, _template(preset, b, model), cwd=cwd, state_dir=state_dir)
    if not ok:
        return False, list(problems), name
    return True, [f"lineup {name} written (not active): the {role or 'search'} role keeps the {b['title']} filters"
                  + (f", on {model}" if model else "") + f"; halo teams apply {name} makes it active"], name


def assign(role: str, ref: str, *, state_dir=None, cwd=None, lineup: str = "") -> "tuple[bool, list, str]":
    from halo_harness.models_library.presets import PRESETS, preset_for_role
    if not role or not ref:
        return False, ["assign takes a role and a model"], ""
    _ensure(state_dir)
    preset = preset_for_role(role)
    name = lineup or _active(state_dir)
    if not name:
        ok, lines, name = save(preset or "coder", state_dir=state_dir, cwd=cwd, model=ref)
        if not ok:
            return False, lines, name
        if LINEUP_ROLE.get(preset or "coder") == role or role == "main":
            return True, [f"{role} is {ref} in {name} (not active): halo teams apply {name}"], name
    agent = (PRESETS.get(preset) or {}).get("agent") or "general"
    ok, lines = _into(name, role, ref, None, agent, state_dir=state_dir, cwd=cwd)
    if not ok:
        return False, list(lines), name
    out = [f"{role} is {ref} in {name}"]
    if name == _active(state_dir):
        from halo_harness.teams_cli_views import apply_lineup
        ok, applied, _notes = apply_lineup(name, cwd=cwd, state_dir=state_dir)
        out += [f"{name} applied again: roles.{role} follows"] if ok else list(applied)
    return ok, out, name
