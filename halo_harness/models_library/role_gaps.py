"""halo_harness.models_library.role_gaps -- Halo 3.3.6.0 R2: a lineup's gaps, each with "find a model for this
role" (plans/local-model-fit-brief.md F4): Roles -> Problems and `halo teams show` link a gap to the Library with
the role's preset applied (`halo models browse --for-role <role>`).

    gaps(role_table, state_dir, roles=()) -> [{role, ref, why, preset, cli}]

A gap: a role the lineup names (`roles`) with no model of its own ("your `verify` role has no model": the role
table leaves it out and it falls through to the session model), or a role on a probed local model that fails the
role's placement gate (providers/placement.role_warning: no tool calls, a 32k window for compaction ...). No
request: the role table and the capability cache only.
"""

from __future__ import annotations


def _ref(v) -> str:
    try:
        from halo_harness.roles import role_value_parts
        got = role_value_parts(v)[0]
    except Exception:
        got = v.get("model") if isinstance(v, dict) else v
    return str(got or "").strip()


def gaps(role_table: dict, state_dir, roles=()) -> list:
    from halo_harness.models_library.presets import PRESETS, preset_for_role
    out = []
    table = dict(role_table or {})
    for r in roles or ():
        if r and r != "main" and r not in table:
            table[r] = ""
    for role, v in sorted(table.items()):
        preset = preset_for_role(role)
        if not preset:
            continue
        ref = _ref(v)
        why = ""
        if not ref or ref.lower() in ("none", "null", "(none)"):
            why = f"your `{role}` role has no model of its own (it falls through to the session model)"
        elif ref.startswith("ol:"):
            from halo_harness.providers.placement import role_warning
            place = (PRESETS.get(preset) or {}).get("role") or role
            w = role_warning(ref, place, state_dir)
            why = f"`{role}` on {ref}: {w}" if w else ""
        if why:
            out.append({"role": role, "ref": ref, "why": why, "preset": preset,
                        "cli": f"halo models browse --for-role {role}"})
    return out
