"""halo_harness.teams_yaml -- Halo 2.0.4 round 4 (deliverables 6-7, the
two-layer + lineup design approved 2026-10-05/06 by the owner, relayed
mid-round): a TEAM TEMPLATE ("lineup") is one YAML file that ASSIGNS
agent BIOS (`agents_yaml.py`) to roles/positions -- `agents:` is a LIST
of assignments (several entries may share a `role`; exactly one has
`role: main`), each entry naming a bio plus an optional alias (`as`),
`instances`, `use_for`, and per-assignment overrides (`models`/`tools`/
`limits`). The older `roles: {ROLE: agent_name_or_{agent,...}}` mapping
is accepted as SUGAR for the common one-assignment-per-role case and
expanded into the same `agents:` list on load -- a minimal template
stays five lines.

This module owns storage/validation/the two resolution functions that
turn a template's assignments into shapes `roles.py`/`orgs.py` already
understand (`resolve_role_table`/`resolve_org`) -- applying a team
template never needs a parallel runtime of its own; it just fills the
EXISTING role table / builds an EXISTING org dict, through the EXISTING
editors and Auto tab. `delegation`/`routing`/`budget`/`escalation`/
`pipeline`/`permissions`/`context` are stored, validated for shape, and
shown (`halo teams show`, `/teams`, `halo doctor --teams`) -- deliberately
NOT enforced by the live agent loop this round (the roadmap's own
"Deferred to 2.0.5 with the Governor" call, extended here to the whole
lineup-orchestration layer, not just `hooks`/`schedule`)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

from halo_harness.agents_yaml import _read_yaml_file, _write_yaml_file  # noqa: F401 (shared YAML I/O)

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

TOP_SECTIONS = ("delegation", "routing", "budget", "escalation", "context", "permissions", "org", "pipeline",
                "acceptance")
DELEGATION_MODES = ("manual", "by-skill", "round-robin")
HANDOFF_SHAPES = ("summary", "full", "structured")
GATE_KINDS = ("required", "optional")
ASSIGNMENT_OVERRIDE_KEYS = ("models", "tools", "limits")


def is_valid_team_name(name: str) -> bool:
    return bool(name) and bool(_NAME_RE.match(name)) and ".." not in name


def bundled_team_templates_dir() -> Path:
    return Path(__file__).resolve().parent / "templates" / "teams"


def user_teams_dir(state_dir=None) -> Path:
    from halo_harness.config.paths import bridge_home
    base = state_dir if state_dir is not None else bridge_home()
    return Path(base) / "teams"


def project_teams_dir(cwd=None) -> Path:
    base = cwd if cwd is not None else Path.cwd()
    return Path(base) / ".halo" / "teams"


def team_search_dirs(*, cwd=None, state_dir=None) -> "list[tuple[Path, str]]":
    return [(project_teams_dir(cwd), "project"), (user_teams_dir(state_dir), "user"),
            (bundled_team_templates_dir(), "template")]


def list_team_templates(*, cwd=None, state_dir=None, include_templates: bool = True) -> "list[str]":
    names: "set[str]" = set()
    dirs = team_search_dirs(cwd=cwd, state_dir=state_dir)
    if not include_templates:
        dirs = [d for d in dirs if d[1] != "template"]
    for d, _source in dirs:
        try:
            names.update(p.stem for p in d.glob("*.yaml") if p.is_file())
        except OSError:
            pass
    return sorted(names)


def find_team_template_path(name: str, *, cwd=None, state_dir=None) -> "Optional[tuple[Path, str]]":
    for d, source in team_search_dirs(cwd=cwd, state_dir=state_dir):
        path = d / f"{name}.yaml"
        if path.is_file():
            return path, source
    return None


def _expand_assignment(role: str, value) -> "Optional[dict]":
    """One `roles:` shorthand entry -> one `agents:` list entry. `value`
    is either a bare agent-name string, or a mapping with its own
    `agent` key plus any per-assignment override -- the SAME override
    shape a full `agents:` entry carries."""
    if isinstance(value, str):
        return {"agent": value, "role": role}
    if isinstance(value, dict) and isinstance(value.get("agent"), str):
        entry = {"role": role}
        entry.update(value)
        return entry
    return None


def _expand_roles_shorthand(data: dict) -> dict:
    """Non-destructive: returns a NEW dict with `agents:` filled in from
    `roles:` when `agents:` wasn't already given directly (an explicit
    `agents:` list always wins outright -- the two are never merged
    together, matching every other "shorthand vs. full form" rule this
    codebase already uses, e.g. a role template's `{"model","effort"}`
    vs. a bare model string)."""
    if data.get("agents") is not None:
        return data
    roles = data.get("roles")
    if not isinstance(roles, dict):
        return data
    out = dict(data)
    agents = []
    for role, value in roles.items():
        entry = _expand_assignment(role, value)
        if entry is not None:
            agents.append(entry)
    out["agents"] = agents
    return out


def load_team_template_raw(name: str, *, cwd=None, state_dir=None) -> "Optional[dict]":
    found = find_team_template_path(name, cwd=cwd, state_dir=state_dir)
    if found is None:
        return None
    path, source = found
    data = _read_yaml_file(path)
    if data is None:
        return None
    data = _expand_roles_shorthand(dict(data))
    data["_source"] = source
    data["_path"] = str(path)
    return data


def _merge_section(parent_section, child_section):
    if not isinstance(parent_section, dict):
        return child_section if child_section is not None else parent_section
    if not isinstance(child_section, dict):
        return parent_section if child_section is None else child_section
    merged = dict(parent_section)
    merged.update(child_section)
    return merged


def resolve_team_template(name: str, *, cwd=None, state_dir=None, _chain: "Optional[list]" = None) -> "Optional[dict]":
    """Follows `extends:` (template inheritance): every section in
    `TOP_SECTIONS` merges key-by-key (child's key wins; a child that
    never mentions a section inherits the parent's whole); `agents:`
    (the lineup itself) does NOT merge -- a child that defines its own
    `agents:`/`roles:` REPLACES the parent's lineup entirely (a template
    that only wants to tweak `delegation`/`budget` and reuse the SAME
    lineup omits `agents:`/`roles:` and inherits it whole instead)."""
    chain = _chain if _chain is not None else []
    if name in chain:
        return None
    raw = load_team_template_raw(name, cwd=cwd, state_dir=state_dir)
    if raw is None:
        return None
    parent_name = raw.get("extends")
    parent = None
    if isinstance(parent_name, str) and parent_name.strip():
        parent = resolve_team_template(parent_name.strip(), cwd=cwd, state_dir=state_dir, _chain=chain + [name])
    resolved = dict(parent) if parent else {}
    for section in TOP_SECTIONS:
        resolved[section] = _merge_section((parent or {}).get(section), raw.get(section))
    resolved["agents"] = raw.get("agents") if raw.get("agents") is not None else (parent or {}).get("agents")
    # Halo 2.0.5 round 2 (deliverable 3): `about` ("How the pieces work
    # together", free text) is an identity field like `description` --
    # never merged key-by-key (it's a single string, not a section), only
    # `extends` itself chains past it when a child never sets its own.
    for field in ("description", "version", "tags", "about"):
        if field in raw:
            resolved[field] = raw[field]
    resolved["name"] = name
    resolved["extends"] = raw.get("extends")
    resolved["_source"] = raw.get("_source")
    resolved["_path"] = raw.get("_path")
    return resolved


def _known_targets(agents: "list") -> "set[str]":
    """Every ROLE name and ALIAS an `agents:` list actually defines --
    `routing`/`pipeline.stages` entries may name either one (confirmed
    against the shipped `halo-dev-cycle` example: `routing.release:
    release` names an ALIAS, `pipeline.stages[0].role: main` names a
    bare ROLE with no alias of its own)."""
    targets: "set[str]" = set()
    for e in agents:
        if isinstance(e, dict):
            if e.get("as"):
                targets.add(e["as"])
            if e.get("role"):
                targets.add(e["role"])
    return targets


def _agent_exists(agent_name: str, *, cwd=None, state_dir=None) -> bool:
    from halo_harness.agents_yaml import load_agent_bio_raw
    return load_agent_bio_raw(agent_name, cwd=cwd, state_dir=state_dir) is not None


def validate_team_template(data, *, name: "Optional[str]" = None, cwd=None, state_dir=None) -> "list[str]":
    """One plain sentence per problem; `[]` means valid. Never raises.
    Refinement 3's own rule set: "every referenced agent exists, exactly
    one main, aliases unique, routing targets exist" -- plus light shape
    checks (a known enum value, a list where a list is required) on
    `delegation`/`pipeline.stages[].gate`, same "store the shape, don't
    enforce the behaviour" boundary the roadmap's own Governor deferral
    already draws for this whole layer."""
    if not isinstance(data, dict):
        return ["team template must be a YAML mapping (top-level key: value)"]
    # The "roles:" shorthand is expanded here too (not just on load) --
    # otherwise data built straight from `roles:` (no `agents:` key at
    # all yet) validates its ASSIGNMENTS as a trivially-empty list, the
    # exact gap that let `migrate_legacy_role_table`'s own output pass
    # validation while silently carrying NO assignments at all (found
    # live, fixed before this round's first test was even written).
    data = _expand_roles_shorthand(data)
    problems: "list[str]" = []
    if "about" in data and data["about"] is not None and not isinstance(data["about"], str):
        problems.append('"about" must be a string')
    agents = data.get("agents")
    if agents is not None and not isinstance(agents, list):
        return problems + ['"agents" must be a list (or use the "roles:" shorthand mapping)']
    agents = agents or []
    main_count = 0
    seen_aliases: "set[str]" = set()
    for i, entry in enumerate(agents):
        if not isinstance(entry, dict):
            problems.append(f"agents[{i}] must be a mapping")
            continue
        agent_name = entry.get("agent")
        if not isinstance(agent_name, str) or not agent_name:
            problems.append(f'agents[{i}]: "agent" is required')
        elif not _agent_exists(agent_name, cwd=cwd, state_dir=state_dir):
            problems.append(f"agents[{i}]: no such agent bio: {agent_name!r}")
        role = entry.get("role")
        if not isinstance(role, str) or not role:
            problems.append(f'agents[{i}]: "role" is required')
        elif role == "main":
            main_count += 1
        alias = entry.get("as")
        if alias is not None:
            if not isinstance(alias, str) or not alias:
                problems.append(f'agents[{i}]: "as" must be a non-empty string')
            elif alias in seen_aliases:
                problems.append(f'duplicate "as" alias: {alias!r}')
            else:
                seen_aliases.add(alias)
        instances = entry.get("instances", 1)
        if not isinstance(instances, int) or isinstance(instances, bool) or instances < 1:
            problems.append(f'agents[{i}]: "instances" must be a positive integer')
        for key in ASSIGNMENT_OVERRIDE_KEYS:
            if key in entry and entry[key] is not None and not isinstance(entry[key], dict):
                problems.append(f'agents[{i}]: "{key}" override must be a mapping')
    if agents and main_count != 1:
        problems.append(f"exactly one agents[] entry must have role: main (found {main_count})")
    delegation = data.get("delegation")
    if delegation is not None and not isinstance(delegation, dict):
        problems.append('"delegation" must be a mapping')
    elif isinstance(delegation, dict):
        mode = delegation.get("mode")
        if mode is not None and mode not in DELEGATION_MODES:
            problems.append(f'"delegation.mode" {mode!r} is not one of {", ".join(DELEGATION_MODES)}')
        handoff = delegation.get("handoff")
        if handoff is not None and handoff not in HANDOFF_SHAPES:
            problems.append(f'"delegation.handoff" {handoff!r} is not one of {", ".join(HANDOFF_SHAPES)}')
    routing = data.get("routing")
    if routing is not None and not isinstance(routing, dict):
        problems.append('"routing" must be a mapping')
    elif isinstance(routing, dict):
        targets = _known_targets(agents)
        for kind, target in routing.items():
            if not isinstance(target, str):
                problems.append(f'"routing.{kind}" must be a string')
            elif targets and target not in targets:
                problems.append(f'"routing.{kind}" names an unknown role/alias: {target!r}')
    for section in ("budget", "escalation", "context", "permissions"):
        if section in data and data[section] is not None and not isinstance(data[section], dict):
            problems.append(f'"{section}" must be a mapping')
    org = data.get("org")
    if org is not None and not isinstance(org, dict):
        problems.append('"org" must be a mapping')
    elif isinstance(org, dict):
        positions = org.get("positions")
        if positions is not None and not isinstance(positions, list):
            problems.append('"org.positions" must be a list')
        for i, p in enumerate(positions or []):
            if not isinstance(p, dict) or not p.get("title"):
                problems.append(f'org.positions[{i}]: "title" is required')
                continue
            agent_name = p.get("agent")
            if agent_name and not _agent_exists(agent_name, cwd=cwd, state_dir=state_dir):
                problems.append(f"org.positions[{i}]: no such agent bio: {agent_name!r}")
    pipeline = data.get("pipeline")
    if pipeline is not None and not isinstance(pipeline, dict):
        problems.append('"pipeline" must be a mapping')
    elif isinstance(pipeline, dict):
        stages = pipeline.get("stages")
        if stages is not None and not isinstance(stages, list):
            problems.append('"pipeline.stages" must be a list')
        for i, s in enumerate(stages or []):
            if not isinstance(s, dict) or not s.get("name"):
                problems.append(f'pipeline.stages[{i}]: "name" is required')
                continue
            gate = s.get("gate")
            if gate is not None and gate not in GATE_KINDS:
                problems.append(f'pipeline.stages[{i}]: "gate" {gate!r} is not one of {", ".join(GATE_KINDS)}')
    extends = data.get("extends")
    if extends is not None:
        if not isinstance(extends, str) or not extends.strip():
            problems.append('"extends" must be a non-empty string')
        elif resolve_team_template(extends.strip(), cwd=cwd, state_dir=state_dir) is None \
                and load_team_template_raw(extends.strip(), cwd=cwd, state_dir=state_dir) is None:
            problems.append(f'"extends" names a team template that does not exist: {extends!r}')
    # Halo 2.0.5 round 4: the lanes rule over a template's RESOLVED role
    # table (the same one `apply_team_template` would write) -- a verifier
    # role resolving to a weaker tier than coder is one plain line, same
    # as `roles.validate_role_template` produces for a bare roles map.
    try:
        from halo_harness.providers.gateway_routing import validate_lanes
        role_table, _notes = resolve_role_table(data, cwd=cwd, state_dir=state_dir)
        lanes = data.get("lanes") if isinstance(data.get("lanes"), dict) else None
        problems.extend(validate_lanes(role_table, lanes=lanes))
    except Exception:
        pass
    return problems


def resolve_role_table(template: dict, *, cwd=None, state_dir=None) -> "tuple[dict, list[str]]":
    """`agents:` -> a `roles.py`-shaped role table: `{role_or_alias:
    model_ref_or_{"model","effort"}}` -- the ONE function that lets the
    Auto tab/`/roles` fill real, usable roles from a team template with
    NO changes to `roles.py` itself. Precedence per assignment: this
    entry's own `models` override -> the resolved agent bio's own
    `models` -> (nothing; a CLI-flag override, when one exists, is the
    CALLER's job same as it already is for every other role source).
    `key` is the entry's own `as` alias when it has one, else its bare
    `role` -- two entries that SHARE a role (refinement 3: "several
    entries may share a role") need an alias to both survive into one
    flat role table; an entry with neither a resolvable agent nor any
    model anywhere is left OUT (never a crash, never a null placeholder,
    same "no candidate" rule `gym_propose.best_candidate_for_role`
    already follows), reported as a plain-English note instead."""
    from halo_harness.agents_yaml import resolve_agent_bio
    role_table: dict = {}
    notes: "list[str]" = []
    for entry in template.get("agents") or []:
        if not isinstance(entry, dict):
            continue
        agent_name, role = entry.get("agent"), entry.get("role")
        if not agent_name or not role:
            continue
        key = entry.get("as") or role
        bio = resolve_agent_bio(agent_name, cwd=cwd, state_dir=state_dir)
        if bio is None:
            notes.append(f"{key}: agent bio {agent_name!r} not found -- left out of the role table")
            continue
        bio_models = bio.get("models") or {}
        override = entry.get("models") or {}
        model_ref = override.get("preference") or bio_models.get("preference") \
            or override.get("fallback") or bio_models.get("fallback")
        effort = override.get("effort") or bio_models.get("effort")
        if not model_ref:
            notes.append(f"{key}: agent {agent_name!r} has no models.preference/fallback of its own -- "
                         f"left out of the role table (falls through to the session model)")
            continue
        role_table[key] = {"model": model_ref, "effort": effort} if effort else model_ref
    return role_table, notes


def resolve_org(template: dict, *, cwd=None, state_dir=None) -> "tuple[Optional[dict], list[str]]":
    """`org.positions` -> an `orgs.py`-shaped org dict (`{"name",
    "description", "positions": [{"title", "model", "reports",
    "instructions"}, ...]}`) -- lets the EXISTING `OrgEditor`/`OrgsStep`
    open and apply an org-shaped team template with no changes of their
    own. `None` (not an error -- `[]` notes) when the template has no
    `org:` section at all (a plain role-table template, the common
    case). `delegates_to` maps onto `orgs.py`'s own `reports` field
    (the children a position may delegate to); `reports_to` (the
    parent) is accepted in the YAML for readability but not separately
    stored here -- `orgs.py` already derives the tree's parent/child
    shape purely from each position's own `reports` list."""
    org_section = template.get("org")
    if not isinstance(org_section, dict) or not org_section.get("positions"):
        return None, []
    from halo_harness.agents_yaml import resolve_agent_bio
    positions_out: "list[dict]" = []
    notes: "list[str]" = []
    for p in org_section.get("positions") or []:
        if not isinstance(p, dict) or not p.get("title"):
            continue
        title = p["title"]
        agent_name = p.get("agent")
        model_ref = None
        if agent_name:
            bio = resolve_agent_bio(agent_name, cwd=cwd, state_dir=state_dir)
            if bio is not None:
                bio_models = bio.get("models") or {}
                model_ref = bio_models.get("preference") or bio_models.get("fallback")
            if model_ref is None:
                notes.append(f"{title}: agent {agent_name!r} has no resolvable model -- "
                             f"position saved with no model of its own")
        position = {"title": title, "reports": list(p.get("delegates_to") or []),
                    "instructions": p.get("instructions") or ""}
        if model_ref:
            position["model"] = model_ref
        positions_out.append(position)
    return {"name": template.get("name") or "", "description": template.get("description") or "",
            "positions": positions_out}, notes


def save_team_template(name: str, data: dict, *, cwd=None, state_dir=None, project: bool = False) -> "tuple[bool, list[str]]":
    """Accepts EITHER the `roles:` shorthand or a direct `agents:` list
    (`validate_team_template` already expands the former to validate
    it) -- always WRITES the canonical `agents:` form to disk, never
    the shorthand spelling, so a file this function wrote is never
    ambiguous about which key actually holds the lineup."""
    if not is_valid_team_name(name):
        return False, [f"invalid team template name {name!r}"]
    problems = validate_team_template(data, name=name, cwd=cwd, state_dir=state_dir)
    if problems:
        return False, problems
    expanded = _expand_roles_shorthand(data)
    payload = {k: v for k, v in expanded.items() if not k.startswith("_") and k != "roles"}
    payload["name"] = name
    d = project_teams_dir(cwd) if project else user_teams_dir(state_dir)
    _write_yaml_file(d / f"{name}.yaml", payload)
    return True, []


def delete_team_template(name: str, *, cwd=None, state_dir=None, project: bool = False) -> bool:
    d = project_teams_dir(cwd) if project else user_teams_dir(state_dir)
    try:
        (d / f"{name}.yaml").unlink()
        return True
    except OSError:
        return False


def list_bundled_team_templates() -> "list[str]":
    try:
        return sorted(p.stem for p in bundled_team_templates_dir().glob("*.yaml") if p.is_file())
    except OSError:
        return []


def new_team_template_from_template(name: str, template_name: "Optional[str]" = None, *, cwd=None, state_dir=None,
                                     project: bool = False) -> "tuple[bool, list[str]]":
    base: dict = {}
    if template_name:
        base = load_team_template_raw(template_name, cwd=cwd, state_dir=state_dir) or {}
        base = {k: v for k, v in base.items() if not k.startswith("_") and k != "roles"}
    base.setdefault("description", "")
    return save_team_template(name, base, cwd=cwd, state_dir=state_dir, project=project)


def migrate_legacy_role_table(role_table: dict, *, cwd=None, state_dir=None) -> "tuple[Optional[str], list[str]]":
    """Deliverable 7 (migration): the first wizard save that sees a REAL
    legacy role table (`roles.py`'s own `~/.halo/config.json` `roles.*`
    table -- role names and model/effort values with no files behind
    them at all) and no "migrated" team template of its own yet builds
    one agent bio per DISTINCT model the table names (`migrated-<slug>`,
    just `models.preference` pinned) and ONE team template named
    "migrated" assigning each role to its own bio -- a working, fully
    file-backed EQUIVALENT of the table that existed before, never
    touching the table itself. `(None, [])` when there's nothing to
    migrate (an empty table) or a "migrated" template already exists
    (never overwritten -- "copy/build on first use" rule, same as every
    other builtin here); else `(team_name, notes)`, one note per bio
    created plus the final template, for the caller's own "announced in
    one line" (a caller that wants ONE line joins `notes` itself)."""
    if not role_table:
        return None, []
    if find_team_template_path("migrated", cwd=cwd, state_dir=state_dir) is not None:
        return None, []
    import re as _re

    from halo_harness.agents_yaml import is_valid_agent_name, save_agent_bio
    from halo_harness.roles import role_value_parts
    model_to_bio: "dict[str, str]" = {}
    roles_shorthand: dict = {}
    notes: "list[str]" = []

    def _bio_for_model(model: str) -> "Optional[str]":
        bio_name = model_to_bio.get(model)
        if bio_name is not None:
            return bio_name
        slug = _re.sub(r"[^A-Za-z0-9_-]+", "-", model).strip("-").lower() or "model"
        bio_name = f"migrated-{slug}"[:60].rstrip("-") or "migrated-model"
        if not is_valid_agent_name(bio_name):
            bio_name = "migrated-model"
        ok, problems = save_agent_bio(
            bio_name, {"description": f"Migrated from the legacy role table -- {model}.",
                       "models": {"preference": model}},
            cwd=cwd, state_dir=state_dir)
        if not ok:
            notes.append(f"could not create a bio for {model!r}: {'; '.join(problems)}")
            return None
        model_to_bio[model] = bio_name
        notes.append(f"created agent bio {bio_name!r} for {model}")
        return bio_name

    # Team templates require EXACTLY one `role: main` -- `roles.py`'s own
    # ten built-in role names never include "main" (the session's own
    # model is `config.json`'s plain "model" key, never a role-table
    # entry), so there is no legacy "main" to carry over; synthesized
    # from the session's CURRENT default model instead, same semantic
    # ("the model used when nothing more specific applies") either way.
    from halo_harness.theme import get_config_value
    default_model = get_config_value("model", default=None)
    if isinstance(default_model, str) and default_model.strip():
        main_bio = _bio_for_model(default_model.strip())
        if main_bio:
            roles_shorthand["main"] = main_bio
    for role_name, value in sorted(role_table.items()):
        model, effort = role_value_parts(value)
        if not model:
            continue
        bio_name = _bio_for_model(model)
        if bio_name is None:
            continue
        roles_shorthand[role_name] = {"agent": bio_name, "models": {"effort": effort}} if effort else bio_name
    if "main" not in roles_shorthand:
        notes.append("no session default model to synthesize a \"main\" assignment -- "
                      "team templates require exactly one, migration skipped")
        return None, notes
    ok, problems = save_team_template(
        "migrated", {"description": "Migrated from this box's own legacy role table.", "roles": roles_shorthand},
        cwd=cwd, state_dir=state_dir)
    if not ok:
        notes.append(f"could not save the migrated team template: {'; '.join(problems)}")
        return None, notes
    notes.append('saved as team template "migrated"')
    return "migrated", notes


def ensure_builtin_team_templates(*, state_dir=None) -> None:
    """Copies every shipped `templates/teams/*.yaml` into `user_teams_
    dir()` the first time its name is missing there -- never overwritten
    after (same "copy on first use" rule `orgs.ensure_builtin_orgs`/
    `roles.ensure_builtin_role_presets` already follow). A literal copy,
    never computed -- unlike `roles.py`'s own three presets (no "cheapest
    configured model" probe makes sense for a STATIC shipped file); a
    user who wants a template's own model pins to reflect what's
    actually configured edits the copy directly, same as any other
    agent bio."""
    d = user_teams_dir(state_dir)
    d.mkdir(parents=True, exist_ok=True)
    for path in bundled_team_templates_dir().glob("*.yaml"):
        target = d / path.name
        if not target.exists():
            try:
                target.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                pass


def apply_team_template(name: str, *, cwd=None, state_dir=None) -> "tuple[bool, list[str], list[str]]":
    """Halo 2.0.5 round 2 (deliverable 3, the wizard's "Use this lineup"):
    the team-template counterpart of `roles.apply_role_template` -- an
    explicit, deliberate user action that OVERWRITES whatever `roles.*`
    config.json already had (same precedence rule: a freshly-applied
    lineup outranks a stale local value). Resolves `name` through `resolve_
    role_table` (the ONE function that turns a lineup's `agents:` into a
    `roles.py`-shaped table, unchanged by this round) and writes each
    entry via `theme.set_config_value`, then sets `team: <name>` as the
    active lineup (`teams_cli.py`'s own `_cmd_use` does the second half
    alone today; this adds the first half for the one caller -- the
    wizard -- that needs both in one step). `(True, [], notes)` on
    success (`notes`: one `resolve_role_table` note per role left out,
    e.g. a bio with no resolvable model); `(False, problems, [])` for an
    unknown/invalid template name -- never raises, never writes a partial
    table."""
    from halo_harness.theme import set_config_value
    template = resolve_team_template(name, cwd=cwd, state_dir=state_dir)
    if template is None:
        return False, [f"no such team template: {name!r} (or it failed validation)"], []
    problems = validate_team_template(template, name=name, cwd=cwd, state_dir=state_dir)
    if problems:
        return False, problems, []
    role_table, notes = resolve_role_table(template, cwd=cwd, state_dir=state_dir)
    for role_name, value in role_table.items():
        set_config_value(f"roles.{role_name}", value)
    set_config_value("team", name)
    return True, [], notes


def member_system_context_addition(agent_name: str, *, team_name: "Optional[str]" = None, cwd=None,
                                    state_dir=None) -> str:
    """Halo 2.0.5 round 2 (deliverable 3 fold-in): the EXTRA system-
    context text `agent_name` (a bio) should receive on top of its own
    prompt -- the bio's own `context.files` (read and concatenated, best-
    effort; an unreadable file is skipped, never fatal) and `context.
    system_prompt` (inline, or read from `system_prompt_file`), THEN --
    when `agent_name` is actually assigned inside `team_name` (default:
    config's own active `team:`) -- that template's own `about:` text,
    appended under the heading "How this team works" (the SAME heading
    `halo teams show` prints above it, docs/AGENTS.md's own wording).
    `""` when there's nothing to add. Pure, local-file-only -- no network,
    safe to call from a live loop; THIS round builds and unit-tests the
    assembly itself (the brief's own Tests section), wiring it into the
    real `agent/subagent.py` child-session builder stays the Governor
    round's job, same "compose now, enforce later" boundary every other
    lineup section here already draws (see this module's own docstring)."""
    from halo_harness.agents_yaml import resolve_agent_bio
    bio = resolve_agent_bio(agent_name, cwd=cwd, state_dir=state_dir)
    parts: "list[str]" = []
    if bio:
        context = bio.get("context") or {}
        for rel in context.get("files") or []:
            try:
                from pathlib import Path
                base = Path(cwd) if cwd is not None else Path.cwd()
                path = Path(rel)
                path = path if path.is_absolute() else base / path
                parts.append(path.read_text(encoding="utf-8"))
            except OSError:
                continue
        system_prompt = context.get("system_prompt")
        if isinstance(system_prompt, str) and system_prompt.strip():
            parts.append(system_prompt.strip())
        elif context.get("system_prompt_file"):
            try:
                from pathlib import Path
                base = Path(cwd) if cwd is not None else Path.cwd()
                path = Path(context["system_prompt_file"])
                path = path if path.is_absolute() else base / path
                parts.append(path.read_text(encoding="utf-8"))
            except OSError:
                pass
    if team_name is None:
        from halo_harness.theme import get_config_value
        team_name = get_config_value("team", default=None)
    if isinstance(team_name, str) and team_name.strip():
        template = resolve_team_template(team_name.strip(), cwd=cwd, state_dir=state_dir)
        about = (template or {}).get("about")
        member_names = {e.get("agent") for e in (template or {}).get("agents") or []
                        if isinstance(e, dict)}
        if isinstance(about, str) and about.strip() and agent_name in member_names:
            parts.append(f"## How this team works\n\n{about.strip()}")
    return "\n\n".join(p for p in parts if p)
