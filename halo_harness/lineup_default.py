"""halo_harness.lineup_default -- the lineup a session runs when nothing names
one (Halo 3.1.9.0 R2, "the Auto lineup").

The order: `--team <name>` (this one run), else config's `team:`, else -- with
roles on -- the shipped `auto` lineup (templates/teams/auto.yaml: main on the
session's model, a pool whose models are picked at spawn). Roles off ("One
model for everything", `halo roles off`) means no lineup at all. Nothing here
writes config: a set `team:` is never changed, and picking another lineup
(`halo config set team <name>`, `halo teams use <name>`, Studio Roles ->
Apply) replaces the default. Halo reads only `~/.halo/config.json`, so there
is no project-level `team:` to consult (doctor_config says so for a repo's
`.halo/config.json`).

`lineup_in_use()` -> `(name, source)`, source one of `flag`, `config`,
`default`, `none`; `lineup_words()` -> "auto (default)" / "quality" / "none
(roles off: one model for everything)"; `lineup_line()` is the one line
`halo doctor`, the init wizard's Summary and `/status` print.
"""

from __future__ import annotations

from typing import Optional

DEFAULT_LINEUP = "auto"
HOW_TO_CHANGE = "`halo config set team <name>` or Studio Roles -> Apply"


def configured_team() -> Optional[str]:
    """Config's own `team:` (stripped), None when unset or blank."""
    try:
        from halo_harness.theme import get_config_value
        name = get_config_value("team", default=None)
    except Exception:
        return None
    return name.strip() if isinstance(name, str) and name.strip() else None


def _roles_on() -> bool:
    try:
        from halo_harness.roles import roles_mode_enabled
        return bool(roles_mode_enabled())
    except Exception:
        return True


def lineup_in_use(cli_flag: Optional[str] = None) -> "tuple[Optional[str], str]":
    """`(name, source)` -- see the module docstring."""
    if isinstance(cli_flag, str) and cli_flag.strip():
        return cli_flag.strip(), "flag"
    team = configured_team()
    if team:
        return team, "config"
    if _roles_on():
        return DEFAULT_LINEUP, "default"
    return None, "none"


def is_default(cli_flag: Optional[str] = None) -> bool:
    return lineup_in_use(cli_flag)[1] == "default"


def lineup_words(cli_flag: Optional[str] = None) -> str:
    name, source = lineup_in_use(cli_flag)
    if name is None:
        return "none (roles off: one model for everything)"
    return f"{name} (default)" if source == "default" else (f"{name} (--team, this run)" if source == "flag" else name)


def lineup_line(cli_flag: Optional[str] = None, *, name: Optional[str] = None, default: bool = False) -> str:
    """`Lineup: auto (default) -- every sub-agent's model is picked for its
    task; change it with ...`. `name`/`default` describe a live session's
    own lineup (its TeamControl; "" = it runs none) instead of reading config."""
    if name is not None:
        words = (f"{name} (default)" if default else name) or "none (this session runs no lineup)"
        auto = name == DEFAULT_LINEUP
    else:
        words, auto = lineup_words(cli_flag), lineup_in_use(cli_flag)[0] == DEFAULT_LINEUP
    what = "main delegates to a pool whose models are picked for each task; " if auto else ""
    return f"Lineup: {words} -- {what}change it with {HOW_TO_CHANGE}"
