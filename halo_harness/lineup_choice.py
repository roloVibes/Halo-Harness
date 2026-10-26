"""halo_harness.lineup_choice -- the Team step's three writes as one plain
function (Halo 3.3.0.0 R1): the terminal wizard's Team step
(tui/dialogs/team_step_actions.py `commit`) and Studio's Setup section
(`POST setup/team`, studio/setup_api.py) both call `apply_lineup_choice`, so
picking a row writes the same keys from either place.

The three choices:

* One model for everything (`ONE_MODEL_ID`, or Studio's word `one-model`):
  `team` removed from config.json and `roles.enabled` false -- no lineup.
* The default `auto` lineup while no `team:` is set: `roles.enabled` true and
  nothing else written, so a future default follows (lineup_default.py).
* Any other lineup (and `auto` over a set `team:`): `apply_team_template`
  writes `roles.*` and `team: <name>`, then `roles.enabled` true.

Each answer is `(ok, line, kind)`: `line` is the one line the wizard keeps in
its Summary's "written" list and Studio shows under the block; `kind` is
`one-model`, `default` or `lineup`.
"""

from __future__ import annotations

ONE_MODEL_WORD = "one-model"  # Studio's id for "One model for everything" (the wizard's is team_preview.ONE_MODEL_ID)


def is_one_model(name: str) -> bool:
    from halo_harness.tui.dialogs.team_preview import ONE_MODEL_ID
    return name in (ONE_MODEL_ID, ONE_MODEL_WORD)


def apply_lineup_choice(name: str, *, cwd=None, state_dir=None) -> "tuple[bool, str, str]":
    """Write the Team step's choice `name` (see the module docstring)."""
    from halo_harness.lineup_default import DEFAULT_LINEUP, configured_team
    from halo_harness.roles import set_roles_enabled
    from halo_harness.theme import unset_config_value
    if is_one_model(name):
        # 3.1.9.0 R2: one model = roles off and no lineup (no longer `team: standard`)
        unset_config_value("team")
        set_roles_enabled(False)
        return True, "one model for everything (roles off, no lineup)", "one-model"
    if name == DEFAULT_LINEUP and configured_team() is None:
        # 3.1.9.0 R2: the default lineup needs nothing written; a future default follows
        set_roles_enabled(True)
        return True, f"lineup {DEFAULT_LINEUP!r} in use (the default: no team: written)", "default"
    from halo_harness.teams_yaml import apply_team_template, ensure_builtin_team_templates
    ensure_builtin_team_templates(state_dir=state_dir)
    ok, problems, notes = apply_team_template(name, cwd=cwd, state_dir=state_dir)
    if not ok:
        return False, f"could not apply lineup {name!r}: {'; '.join(problems)}", "lineup"
    set_roles_enabled(True)
    return True, (f"lineup {name!r} applied (roles.*, team: {name!r})" + (f" -- {'; '.join(notes)}" if notes else "")), "lineup"
