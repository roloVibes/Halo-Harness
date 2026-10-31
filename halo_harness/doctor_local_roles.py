"""halo_harness.doctor_local_roles -- Halo 3.3.6.0 R1: `halo doctor --local`'s
role check (plans/local-model-fit-brief.md E6): every role whose model is a
probed local model is held to the placement rules (providers/placement.py);
a role whose model lacks the capability it needs FAILs with the fix.

    role_steps(state_dir, *, role_table=None, main_ref=None) -> [{step, ok, reason, elapsed_s}]

The main model is checked as `main`, each `roles.<name>` entry as its role.
A role on a model the battery never ran on passes with the line that runs
it ("not probed yet: halo models probe <ref>"); a cloud role is not listed.
No request: the capability cache only.
"""

from __future__ import annotations

from typing import Optional


def _main_ref(state_dir) -> Optional[str]:
    try:
        from halo_harness.doctor_local import _resolve_default_ref
        return _resolve_default_ref(state_dir)
    except Exception:
        return None


def role_steps(state_dir, *, role_table: Optional[dict] = None, main_ref: Optional[str] = None) -> list:
    from halo_harness.providers.battery_profile import date_of
    from halo_harness.providers.placement import profile_for_ref, verdict
    from halo_harness.roles import configured_role_table, role_value_parts
    table = dict(role_table if role_table is not None else configured_role_table())
    main = main_ref if main_ref is not None else _main_ref(state_dir)
    pairs = ([("main", main)] if main else []) + [(r, role_value_parts(v)[0]) for r, v in sorted(table.items())]
    out = []
    for role, ref in pairs:
        if not isinstance(ref, str) or not ref.startswith("ol:"):
            continue
        p = profile_for_ref(ref, state_dir)
        if not p:
            out.append({"step": f"role {role}", "ok": True, "elapsed_s": 0.0, "tag": "INFO",
                        "reason": f"{ref}: not probed yet: halo models probe {ref}"})
            continue
        v = verdict(p, role, state_dir=state_dir)
        if v["ok"] is False:
            out.append({"step": f"role {role}", "ok": False, "elapsed_s": 0.0,
                        "reason": f"{ref}: {v['why']}; fix: {v['fix']}"})
        else:
            notes = f" ({'; '.join(v['notes'])})" if v["notes"] else ""
            out.append({"step": f"role {role}", "ok": True, "elapsed_s": 0.0,
                        "reason": f"{ref}: {p.get('sits')} (probed {date_of(p)}){notes}"})
    return out
