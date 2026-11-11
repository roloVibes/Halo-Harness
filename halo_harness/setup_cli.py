"""halo_harness.setup_cli -- `halo setup [<page>|<pack>] [--terminal]` (Halo 2.0.2 round 7; 3.3.0.0 R4: the door into
Studio's Setup; 3.4.0.0 B2: every page, and the console line where no browser opens).

On a real terminal `halo setup <page>` opens Halo Studio on that page of its Setup section (`?mode=setup&block=<page>`,
studio/setup_door.py): providers, local, model, permissions, theme, team (`roles` is its older name), linux, check,
machines; bare `halo setup` the whole section. `--terminal`, no terminal, or a box where no browser can open (SSH, no
DISPLAY, `HALO_NO_BROWSER`, after the URL and the port-forward line) prints the console way to do the same instead:
the command that sets it (`CONSOLE` below; team and roles also print the current roles table). The terminal wizard's
screens left in 3.4.0.0. `/setup` (tui/slash.py `_handle_setup`) is the same from a live session. 3.3.11.0 R3: `halo
setup <pack>` opens an enabled pack's own Setup blocks (`?block=pack:<id>:<block>`, the first one waiting), or lists
them where no browser opens.
"""

from __future__ import annotations

import sys

USAGE = "usage: halo setup [providers|local|model|permissions|theme|team|linux|check|machines|<pack>] [--terminal]"
#: The console way to do what each Setup page does (3.4.0.0 B2: what `--terminal` and a box with no browser print).
CONSOLE = {
    "": "halo init --terminal: a provider and its key, the default model, the permission mode, doctor",
    "providers": "halo init --terminal (a provider and its key, by its variable's name in the env file); halo providers "
                 "(the table, enable / disable)",
    "local": "halo ollama discover (the Ollama servers here and on the network); halo local servers; halo models browse",
    "model": "halo config set model <ref> (halo models lists them); halo init --terminal picks one from a short list",
    "permissions": "halo config set permission_mode <default|acceptEdits|plan|auto|bypassPermissions>",
    "theme": "halo config set theme <name> (/theme in a session lists the palettes)",
    "team": "halo teams list; halo teams use <name>; halo teams show <name>",
    "linux": "halo doctor (its rg and ~/.local/bin lines end with the fix to run)",
    "check": "halo check (doctor, the catalog, a hello call; --all adds the rest)",
    "machines": "halo fleet pair (this machine's code); halo fleet join <code> (on the other one)",
}


def console_lines(page: str) -> "list[str]":
    """The lines `halo setup <page> --terminal` prints (and `/setup <page> --terminal`)."""
    from halo_harness.studio.setup_door import ALIASES
    page = ALIASES.get(page, page)
    return [f"Setup{(' -> ' + page) if page else ''} in a terminal: {CONSOLE[page]}"]


def _print_roles_table() -> int:
    from halo_harness.roles_cli import _cmd_table
    return _cmd_table()


def _pack_setup(pack_id: str, terminal: bool) -> "int | None":
    """3.3.11.0 R3: `halo setup <pack>` -- Studio's Setup on the pack's first block waiting (`?block=pack:<id>:<block>`);
    with no terminal, --terminal or no browser, the pack's blocks with their state. None: no pack has that id."""
    from halo_harness.packs.setup_state import door
    key, lines = door(pack_id)
    if key is None:
        return None
    if not key:
        print(lines[0], file=sys.stderr)
        return 1
    if not terminal and sys.stdin.isatty() and sys.stdout.isatty():
        from halo_harness.studio.setup_door import SetupTarget, cli_door
        if cli_door(SetupTarget(block=key), terminal_cli=f"halo setup {pack_id} --terminal", fallback="listing"):
            return 0
    for line in lines:
        print(line)
    print(f"open them in Studio: halo studio --edit setup:{key}")
    return 0


def cmd_setup(argv: list) -> int:
    from halo_harness.studio.setup_door import ALIASES, SetupTarget, cli_door
    words = [w for w in argv if w != "--terminal"]
    terminal = len(words) != len(argv)
    sub = (words[0] if words else "").lower()
    if sub in ("-h", "--help"):
        print(USAGE)
        print("Opens Halo Studio on that page of its Setup section (an enabled pack's first Setup block for its id); "
              "--terminal prints the console way to do the same instead, as does a box where no browser can open.")
        return 0
    page = ALIASES.get(sub, sub)
    if page not in CONSOLE and len(words) == 1:
        rc = _pack_setup(sub, terminal)  # 3.3.11.0 R3: a pack's own Setup blocks
        if rc is not None:
            return rc
    if page not in CONSOLE or len(words) > 1:
        print(f"halo setup: unknown page {' '.join(words)!r} (known: {', '.join(p for p in CONSOLE if p)}, roles = team, "
              "an enabled pack's id; --terminal)", file=sys.stderr)
        return 2
    tty = sys.stdin.isatty() and sys.stdout.isatty()
    if tty and not terminal and cli_door(SetupTarget(block=page), terminal_cli=f"halo setup {sub} --terminal".replace("  ", " "),
                                         fallback="listing"):
        return 0
    for line in console_lines(page):
        print(line)
    return _print_roles_table() if page == "team" else 0
