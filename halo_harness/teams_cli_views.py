"""halo_harness.teams_cli_views -- Halo 2.1.0 round B2: the plain-text views
behind `halo teams` (overview, preview, diff, apply) and `halo agents` (the
grouped bios list). Pure functions that return lines, so `halo teams`, the
headless `/teams` and `/agents`, and the TUI all print the same words.

The tree itself is `tui/dialogs/team_preview.py`'s `preview_lines` -- reused,
never re-implemented."""

from __future__ import annotations

import shutil

_SCOPE_ORDER = ("project", "user", "template")
_SCOPE_LABEL = {"project": "project", "user": "user", "template": "shipped"}


def _width() -> int:
    return max(40, min(shutil.get_terminal_size((80, 24)).columns, 100))


def lineup_rows(*, cwd=None, state_dir=None) -> "list[dict]":
    """`[{name, scope, description}]` for every reachable lineup."""
    from halo_harness.teams_yaml import ensure_builtin_team_templates, find_team_template_path, \
        list_team_templates, resolve_team_template
    try:
        ensure_builtin_team_templates(state_dir=state_dir)
    except Exception:
        pass
    rows = []
    for name in list_team_templates(cwd=cwd, state_dir=state_dir):
        found = find_team_template_path(name, cwd=cwd, state_dir=state_dir)
        template = resolve_team_template(name, cwd=cwd, state_dir=state_dir) or {}
        scope = _SCOPE_LABEL.get(found[1], found[1]) if found else "?"
        rows.append({"name": name, "scope": scope, "description": template.get("description") or ""})
    return rows


def overview_lines(*, cwd=None, state_dir=None, default_model: str = "") -> "list[str]":
    """`halo teams` with no arguments: the lineup in force, its tree, then
    one line per other lineup."""
    from halo_harness.roles import roles_mode_enabled
    from halo_harness.theme import get_config_value
    from halo_harness.tui.dialogs import team_preview as tp
    team = get_config_value("team", default=None)
    team = team if isinstance(team, str) and team.strip() else None
    out: "list[str]" = []
    if not roles_mode_enabled():
        out.append(f"{tp.ONE_MODEL_LABEL}: {tp.default_model_label(default_model)}")
        out.append(tp.one_model_sentence(default_model))
        active = None
    elif team:
        out.append(f"Active lineup: {team}")
        out.extend(tp.preview_lines(team, cwd=cwd, state_dir=state_dir, width=_width(),
                                    default_model=default_model))
        active = team
    else:
        out.append("No lineup applied yet. Pick one with `halo teams apply <name>`.")
        active = None
    others = [r for r in lineup_rows(cwd=cwd, state_dir=state_dir) if r["name"] != active]
    if others:
        out.extend(["", "Other lineups (`halo teams preview <name>` to look, `halo teams apply <name>` to use):"])
        for r in others:
            desc = f" -- {r['description']}" if r["description"] else ""
            out.append(f"  {r['name']} [{r['scope']}]{desc}")
    return out


def preview_text(name: str, *, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """`(found, lines)`: the wizard's tree for lineup `name`."""
    from halo_harness.teams_yaml import ensure_builtin_team_templates, resolve_team_template
    from halo_harness.tui.dialogs import team_preview as tp
    try:
        ensure_builtin_team_templates(state_dir=state_dir)
    except Exception:
        pass
    found = name == tp.ONE_MODEL_ID or resolve_team_template(name, cwd=cwd, state_dir=state_dir) is not None
    return found, tp.preview_lines(name, cwd=cwd, state_dir=state_dir, width=_width())


def _role_map(name: str, cwd, state_dir) -> "dict | None":
    """`{role_key: (agent, model)}` for lineup `name`, or None if unknown."""
    from halo_harness.teams_yaml import resolve_role_table, resolve_team_template
    from halo_harness.tui.dialogs.team_preview import _ref_of
    template = resolve_team_template(name, cwd=cwd, state_dir=state_dir)
    if template is None:
        return None
    table, _notes = resolve_role_table(template, cwd=cwd, state_dir=state_dir)
    out = {}
    for e in template.get("agents") or []:
        if isinstance(e, dict) and e.get("role"):
            key = e.get("as") or e["role"]
            out[key] = (e.get("agent") or "-", _ref_of(table.get(key)) or "session model")
    return out


def diff_lines(a: str, b: str, *, cwd=None, state_dir=None) -> "tuple[bool, list[str]]":
    """`(ok, lines)`: role-by-role comparison. `-` only in `a`, `+` only in
    `b`, `~` differs, two spaces when equal."""
    ma, mb = _role_map(a, cwd, state_dir), _role_map(b, cwd, state_dir)
    missing = [n for n, m in ((a, ma), (b, mb)) if m is None]
    if missing:
        return False, [f"No such lineup: {n!r} (or it failed validation)." for n in missing]
    out, differs = [f"Comparing {a} (left) with {b} (right):"], False
    for role in sorted(set(ma) | set(mb)):
        left, right = ma.get(role), mb.get(role)
        if left == right:
            out.append(f"  {role}: {left[0]} / {left[1]}")
        elif right is None:
            differs = True
            out.append(f"- {role}: {left[0]} / {left[1]}")
        elif left is None:
            differs = True
            out.append(f"+ {role}: {right[0]} / {right[1]}")
        else:
            differs = True
            out.append(f"~ {role}: {left[0]} / {left[1]}  ->  {right[0]} / {right[1]}")
    if not differs:
        out.append(f"No difference between {a} and {b}.")
    return True, out


def apply_lineup(name: str, *, cwd=None, state_dir=None, session=None) -> "tuple[bool, list[str], list[str]]":
    """The ONE apply path (`halo teams apply|use`, `/teams apply`): writes
    `roles.*` and `team:` exactly like the wizard, turns custom roles on
    (off for `standard` / the one-model row) and returns `(ok, lines,
    notes)`; on failure `lines` are the validator's own lines."""
    from halo_harness.roles import set_roles_enabled
    from halo_harness.teams_yaml import apply_team_template, ensure_builtin_team_templates, \
        resolve_role_table, resolve_team_template
    from halo_harness.tui.dialogs import team_preview as tp
    one_model = name in (tp.ONE_MODEL_ID, "standard")
    target = "standard" if name == tp.ONE_MODEL_ID else name
    try:
        ensure_builtin_team_templates(state_dir=state_dir)
    except Exception:
        pass
    ok, problems, notes = apply_team_template(target, cwd=cwd, state_dir=state_dir)
    if not ok:
        return False, list(problems), []
    set_roles_enabled(not one_model)
    template = resolve_team_template(target, cwd=cwd, state_dir=state_dir) if session is not None else None
    if template:
        table, _n = resolve_role_table(template, cwd=cwd, state_dir=state_dir)
        live = getattr(getattr(session, "agent_runtime", None), "role_table", None)
        if isinstance(live, dict):
            live.update(table)
    lines = tp.applied_summary_lines(cwd=cwd, state_dir=state_dir)
    return True, lines, list(notes)


def agent_group_lines(*, cwd=None, state_dir=None) -> "list[str]":
    """`halo agents` with no arguments: bios grouped by scope, one per line
    (name, kind, preferred model), ending with the show hint."""
    from halo_harness.agents_yaml import find_agent_bio_path, list_agent_bios, resolve_agent_bio
    groups: "dict[str, list[str]]" = {s: [] for s in _SCOPE_ORDER}
    for name in list_agent_bios(cwd=cwd, state_dir=state_dir):
        found = find_agent_bio_path(name, cwd=cwd, state_dir=state_dir)
        bio = resolve_agent_bio(name, cwd=cwd, state_dir=state_dir) or {}
        models = bio.get("models") or {}
        model = models.get("preference") or models.get("fallback") or "session model"
        desc = (bio.get("description") or "").strip().replace("\n", " ")
        desc = f" -- {desc[:60]}{'...' if len(desc) > 60 else ''}" if desc else ""
        groups.setdefault(found[1] if found else "template", []).append(
            f"  {name} ({bio.get('kind') or 'custom'}) {model}{desc}")
    out: "list[str]" = []
    for scope in _SCOPE_ORDER:
        if groups.get(scope):
            out.append(f"{_SCOPE_LABEL[scope].capitalize()} agents:")
            out.extend(groups[scope])
    if not out:
        out.append("No agents found.")
    out.append("halo agents show <name>")
    return out
