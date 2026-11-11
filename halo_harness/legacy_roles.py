"""halo_harness.legacy_roles -- the legacy role table becomes a lineup once (Halo 3.4.0.0 B2).

A `~/.halo/config.json` `roles` table from before lineups (role names with a model, no bio files behind them) becomes
one bio per distinct model and the lineup "migrated" (`teams_yaml.migrate_legacy_role_table`; the table itself is never
touched, nor is the active lineup). Until 3.4.0.0 the terminal wizard's lineup step did it the first time it opened;
with the wizard gone it runs at session start (an interactive session, tui/launch.py) and in `halo init`'s console
setup, and is a no-op once "migrated" exists or with no table.

    migrate_on_start(cwd) -> str      the one line to show, or '' (nothing migrated, or it failed: never raises)
"""

from __future__ import annotations


def migrate_on_start(cwd=None, state_dir=None) -> str:
    try:
        from halo_harness.roles import configured_role_table
        from halo_harness.teams_yaml import migrate_legacy_role_table
        name, notes = migrate_legacy_role_table(configured_role_table(), cwd=cwd, state_dir=state_dir)
    except Exception:
        return ""
    if not name:
        return ""
    return (f"Your role table from before lineups is now the lineup {name!r} ({len(notes)} file(s) written; the table "
            f"is unchanged): halo teams show {name}, halo teams use {name}")
