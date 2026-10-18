"""halo_harness.tui.dialogs.lineup_view_text -- what the read-only lineup view
(lineup_editor.py) and the wizard's Team preview (team_preview.py) print for a
lineup (Halo 3.1.1.0 R3; the helpers came from the 2.0.5 lineup form): one
resolved line per assignment, the warnings that need no Governor, the about
text (drafted when the lineup has none) and the cost of each row.
"""

from __future__ import annotations

from typing import Optional


def _same_gateway(ref_a: str, ref_b: str) -> bool:
    """Same prefix before the first `:` (or:/dbx:/ol:/cc:/...): a fallback on the same gateway as
    the preference cannot help when that gateway is down. Advisory only."""
    prefix = lambda r: r.split(":", 1)[0] if ":" in r else r  # noqa: E731
    return bool(ref_a) and bool(ref_b) and prefix(ref_a) == prefix(ref_b)


def resolved_assignment_line(entry: dict, *, cwd=None, state_dir=None, models_by_ref: "Optional[dict]" = None) -> str:
    """The resolved truth of one row: agent, preferred model, fallback, price, context, tools, gym score."""
    from halo_harness.agents_yaml import resolve_agent_bio
    role, alias, agent_name = entry.get("role") or "?", entry.get("as"), entry.get("agent")
    label = alias or role
    if not agent_name:
        return f"{role} ({label}): (no agent)"
    bio = resolve_agent_bio(agent_name, cwd=cwd, state_dir=state_dir)
    if bio is None:
        return f"{role} ({label}): agent {agent_name!r} NOT FOUND"
    models = bio.get("models") or {}
    override = entry.get("models") or {}
    pref = override.get("preference") or models.get("preference")
    fallback = override.get("fallback") or models.get("fallback")
    parts = [f"{role} ({label}): agent={agent_name}", f"pref={pref or '?'}"]
    if fallback:
        parts.append(f"fallback={fallback}")
    row = (models_by_ref or {}).get(pref) if pref else None
    if row:
        from halo_harness.model_display import format_price_per_m, format_token_count
        price = format_price_per_m(row.get("price_in_per_m"))
        if price:
            parts.append(f"price={price}")
        ctx = format_token_count(row.get("context_tokens"))
        if ctx:
            parts.append(f"ctx={ctx}")
    parts.append(f"tools={len((bio.get('tools') or {}).get('allow') or [])}")
    if pref:
        try:
            from halo_harness.gym import picker_score_suffix
            gym = picker_score_suffix(pref, state_dir=state_dir).strip()
            if gym:
                parts.append(gym)
        except Exception:
            pass
    return "  ".join(parts)


def lineup_warnings(agents: "list", *, cwd=None, state_dir=None) -> "list[str]":
    """One plain sentence per problem: a missing bio, no reachable model for a slot, a fallback on the
    preference's gateway, a duplicate alias, two (or zero) rows with `role: main`."""
    from halo_harness.agents_yaml import resolve_agent_bio
    warnings: "list[str]" = []
    seen_alias: "dict[str, str]" = {}
    main_count = 0
    for i, e in enumerate(agents):
        if not isinstance(e, dict):
            continue
        agent_name, role, alias = e.get("agent"), e.get("role"), e.get("as")
        label = alias or role or f"#{i}"
        if agent_name:
            bio = resolve_agent_bio(agent_name, cwd=cwd, state_dir=state_dir)
            if bio is None:
                warnings.append(f"{label}: agent bio {agent_name!r} not found.")
            else:
                models = bio.get("models") or {}
                override = e.get("models") or {}
                pref = override.get("preference") or models.get("preference")
                fallback = override.get("fallback") or models.get("fallback")
                if not pref and not fallback:
                    warnings.append(f"{label}: no reachable model for this slot.")
                elif pref and fallback and _same_gateway(pref, fallback):
                    warnings.append(f"{label}: fallback {fallback!r} is on the same gateway as the "
                                    f"preference {pref!r} -- it can't help if that gateway is down.")
        if role == "main":
            main_count += 1
        if alias:
            if alias in seen_alias:
                warnings.append(f"duplicate alias {alias!r} (used by both {seen_alias[alias]!r} and {label!r}).")
            seen_alias[alias] = label
    if agents:
        if main_count > 1:
            warnings.append(f"{main_count} rows have role: main -- exactly one is expected.")
        elif main_count == 0:
            warnings.append("no row has role: main yet.")
    return warnings


def draft_about_text(template: dict) -> str:
    """One sentence per assignment plus the delegation and pipeline sections, never blank."""
    lines = []
    for e in template.get("agents") or []:
        if not isinstance(e, dict):
            continue
        label = e.get("as") or e.get("role") or "?"
        lines.append(f"{label} runs as {e.get('role') or '?'} using the {e.get('agent') or '(no agent)'!r} agent.")
    delegation = template.get("delegation") or {}
    if delegation.get("mode"):
        lines.append(f"Delegation is {delegation['mode']}.")
    stages = (template.get("pipeline") or {}).get("stages") or []
    if stages:
        order = " -> ".join(s.get("name", "?") for s in stages if isinstance(s, dict))
        lines.append(f"The pipeline runs {order}.")
    return " ".join(lines) or "This lineup has no assignments yet."


def cost_lines(agents: "list[dict]", models_by_ref: dict) -> "list[str]":
    """Per row, the model's catalog price (per 1M tokens, in and out), or 'free/unknown price'."""
    from halo_harness.model_display import format_price_per_m
    lines = []
    for e in agents:
        label = e.get("role") or e.get("as") or "?"
        ref = e.get("model") or e.get("agent") or ""
        row = models_by_ref.get(ref) if ref else None
        if row and (row.get("price_in_per_m") is not None or row.get("price_out_per_m") is not None):
            lines.append(f"{label}: {format_price_per_m(row.get('price_in_per_m'))} in / "
                         f"{format_price_per_m(row.get('price_out_per_m'))} out")
        else:
            lines.append(f"{label}: {ref or '(unset)'} -- free/unknown price")
    return lines


def section_yaml(value) -> str:
    """A section's body as the YAML its file holds."""
    import yaml
    return yaml.safe_dump(value, sort_keys=False, default_flow_style=False, allow_unicode=True).rstrip()


def roles_projection(template: dict, *, cwd=None, state_dir=None) -> str:
    """The role table the lineup resolves to (`teams_yaml.resolve_role_table`), one `role: model` per line."""
    from halo_harness.teams_yaml import resolve_role_table
    role_table, notes = resolve_role_table(template, cwd=cwd, state_dir=state_dir)
    lines = [f"{k}: {v if isinstance(v, str) else v.get('model')}" for k, v in sorted(role_table.items())]
    return "\n".join([*lines, *(f"(note) {n}" for n in notes)]) or "(no roles resolved yet)"
