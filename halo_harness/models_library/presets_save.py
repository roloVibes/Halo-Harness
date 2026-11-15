"""halo_harness.models_library.presets_save -- Halo 3.3.6.0 R2: Save as role template, and the role offer after
Download and verify (3.6.0.0 R5c: an agent file and the model table, where both wrote a lineup through the teams
path; a session reads neither lineups nor bios now).

    save(preset, *, state_dir, cwd=None, model="", lineup="", bundle_over=None) -> (ok, lines, agent name)
        the agent file `local-<preset>` (crew/agents/, agent/1) on the model picked: what the preset's role does, the
        tools that role needs, `careful: ask-changes`; any session can hand it work by name. Refused in one line, with
        what to do instead: no model picked (a role template is a model for a role now), a preset that fills no role
        (Embeddings, Pool), Offline-only (main's model: `halo config set model`), a lineup named (3.6 reads none)
    assign(role, ref, *, state_dir, cwd=None, lineup="") -> (ok, lines, "")
        "assign `verify` to <model>?": `roles.<role> = <ref>` in the model table a session reads (as `halo roles
        point`), and nothing else
    LINEUP_ROLE: the role each preset fills (verify, planner, small, ...)
"""

from __future__ import annotations

from typing import Optional

LINEUP_ROLE = {"coder": "coder", "reasoner": "planner", "bulk": "small", "compactor": "compaction",
               "verifier": "verify", "security": "security", "multimodal": "eyes", "offline": "main", "embeddings": ""}
USES = {"coder": ["read", "edit", "bash"], "security": ["read", "bash", "web"]}  # the rest read only


def _agent(preset: str, b: dict, model: str) -> dict:
    role = LINEUP_ROLE.get(preset, "")
    return {"format": "agent/1", "name": f"local-{preset}",
            "does": (f"The {role} role on {model}, a local model the Library's {b['title']} preset found "
                     f"({b.get('why') or 'its filters'})."),
            "model": model, "uses": list(USES.get(preset, ["read"])), "careful": "ask-changes"}


def save(preset: str, *, state_dir=None, cwd=None, model: str = "", lineup: str = "",
         bundle_over: Optional[dict] = None) -> "tuple[bool, list, str]":
    from halo_harness.models_library.presets import PRESETS, bundle
    if preset not in PRESETS:
        return False, [f"no preset {preset!r}: one of {', '.join(PRESETS)}"], ""
    if preset == "pool":  # 3.3.8.0 R1: the pool serves one model across several hosts; it is no role's filters
        return False, ["the Pool preset fills no role: the pool serves one model across its members "
                       "(halo pool recommend)"], ""
    b = bundle(preset, **(bundle_over or {}))
    role, name = LINEUP_ROLE.get(preset, ""), f"local-{preset}"
    if lineup:
        return False, [f"Halo 3.6 reads no lineup ({lineup}): save it as the agent {name} (pick a model), or point the "
                       f"role yourself: halo roles point {role or '<role>'} <model>"], ""
    if not role:
        return False, [f"{b['title']} fills no role: its filters stay in the Library"], ""
    if role == "main":
        return False, [f"{b['title']} is main's model: halo config set model <model>" + (f" ({model})" if model else "")], ""
    if not model:
        return False, [f"pick a model first: Save as role template writes the agent {name} on it (or Download and "
                       f"verify a row, whose offer points roles.{role})"], ""
    from halo_harness.crew import store
    from halo_harness.crew.formats import PROBLEMS
    body = _agent(preset, b, model)
    problems = PROBLEMS["agent"](body, name=name)
    if problems:
        return False, list(problems), name
    path = store.path_for("agent", name, state_dir=state_dir)
    had = path.is_file()
    try:
        store.write_text(path, store.dump(body))
    except OSError as e:
        return False, [f"could not write {path}: {e}"], name
    return True, [f"agent {name} {'replaced' if had else 'written'}: the {role} role on {model} "
                  f"(hand it work by name: {name})"], name


def assign(role: str, ref: str, *, state_dir=None, cwd=None, lineup: str = "") -> "tuple[bool, list, str]":
    from halo_harness.roles import assign_role
    if not role or not ref:
        return False, ["assign takes a role and a model"], ""
    ok, problems = assign_role(role, ref)
    if not ok:
        return False, list(problems), ""
    return True, [f"roles.{role} = {ref}: the model table new sessions read (as halo roles point {role} {ref})"], ""
