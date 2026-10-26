"""halo_harness.setup_cli -- `halo setup [team|roles] [--terminal]` (Halo 2.0.2
round 7, init wizard brief item 3; 3.3.0.0 R4: the door into Studio's Setup).

On a real terminal `halo setup` opens Halo Studio on its Setup section, the
Team block in view for `halo setup team` (`roles` is the same block's older
name): `?mode=setup&block=team` (studio/setup_door.py). `--terminal` keeps
the terminal screens: the wizard starting at the matching step (bare `halo
setup --terminal` chains roles -> a short summary); so does a box where no
browser can open (SSH, no DISPLAY, `HALO_NO_BROWSER`), after the URL and the
port-forward hint are printed. With no TTY (or if the Textual app itself
fails to run -- the same "interactive picker failed -> fallback" shape every
other picker in this package already uses), it prints the current roles table
instead of blocking, and exits 0. `/setup` (the TUI slash command,
`tui/slash.py::_handle_setup`) is the other way to reach this from a LIVE
session.
"""

from __future__ import annotations

import sys


def _print_roles_table() -> int:
    from halo_harness.roles_cli import _cmd_table
    return _cmd_table()


# Halo 2.0.5 round 2c (rule 11): "team" reaches the SAME merged step
# "roles" already aliases to (`init_wizard.STEP_FACTORIES`'s own alias
# map) -- added here too so `halo setup team` and `halo setup roles` are
# equally spelled, even though "roles" alone was already enough to keep
# working unchanged.
_STEP_KEYS = {"team": ("team",), "roles": ("roles",), "": ("roles", "summary")}
_NO_TTY_FALLBACK = {"team": _print_roles_table, "roles": _print_roles_table, "": _print_roles_table}
USAGE = "usage: halo setup [team|roles] [--terminal]"


def _open_in_studio(sub: str) -> bool:
    """3.3.0.0 R4: Studio's Setup on the block (`team` for team and roles); True when the browser has it."""
    from halo_harness.studio.setup_door import SetupTarget, block_word, cli_door
    block, _why = block_word(sub)
    cli = "halo setup" + (f" {sub}" if sub else "") + " --terminal"
    return cli_door(SetupTarget(block=block or ""), terminal_cli=cli, fallback="screen")


def cmd_setup(argv: list) -> int:
    words = [w for w in argv if w != "--terminal"]
    terminal = len(words) != len(argv)
    sub = words[0] if words else ""
    if sub in ("-h", "--help"):
        print(USAGE)
        print("Opens Halo Studio on its Setup section (the Team block for team or roles); --terminal runs the "
              "terminal screen instead, as does a box where no browser can open.")
        return 0
    if sub not in _STEP_KEYS or len(words) > 1:
        print(f"halo setup: unknown subcommand {' '.join(words)!r} (known: team, roles; --terminal)", file=sys.stderr)
        return 2
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return _NO_TTY_FALLBACK[sub]()
    if not terminal and _open_in_studio(sub):
        return 0
    try:
        from pathlib import Path
        from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
        state = WizardState(cwd=Path.cwd(), step_keys=_STEP_KEYS[sub])
        InitWizardApp(state).run()
        return 0
    except Exception as e:
        print(f"[WARN] the setup screen failed to run ({type(e).__name__}: {e}) -- "
              f"falling back to a plain listing.", file=sys.stderr)
        return _NO_TTY_FALLBACK[sub]()
