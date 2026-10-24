"""halo_harness.isolation.declared -- which of your lineups and bios declare an opt-in.

`halo doctor`'s isolation and secrets rows and `halo secrets check` (no
flag) read this: every lineup and bio of the project and user tiers (the
shipped templates and packs never declare one) with its `isolation` and
`secrets` as isolation/spec.py resolves them. Never raises.
"""

from __future__ import annotations

from typing import Optional


def declared(*, cwd=None, state_dir=None) -> "list[tuple[str, Optional[dict], Optional[dict]]]":
    """`[(label, isolation or None, secrets or None)]` for each lineup and bio that declares either."""
    out: list = []
    try:
        from halo_harness import agents_yaml as A, teams_yaml as T
        from halo_harness.isolation import spec
        for name in T.list_team_templates(cwd=cwd, state_dir=state_dir, include_templates=False):
            tpl = T.resolve_team_template(name, cwd=cwd, state_dir=state_dir) or {}
            got = spec.resolve(tpl, name, None, "")
            if got.isolation or got.secrets:
                out.append((f"lineup {name}", got.isolation, got.secrets))
        for name in A.list_agent_bios(cwd=cwd, state_dir=state_dir, include_templates=False):
            got = spec.resolve(None, "", A.resolve_agent_bio(name, cwd=cwd, state_dir=state_dir), name)
            if got.isolation or got.secrets:
                out.append((f"bio {name}", got.isolation, got.secrets))
    except Exception:
        return out
    return out
