"""halo_harness.packs.cli_ask -- the questions `halo pack` asks in a terminal (moved out of packs/cli.py in 3.4.1.2):
`halo pack update`'s "Apply? [y/N]" (3.2.1.0 R4) and `halo pack enable --grant-all`'s "Grant these? [y/N]" for a pack
Halo does not ship (3.4.1.2, PACKS-6 / SERVERS-2: each grant that runs its code, said first)."""

from __future__ import annotations

import sys


def tty() -> bool:
    """A terminal on both ends: only there does `halo pack update` ask (a pipe, a script, CI: as before)."""
    try:
        return bool(sys.stdin and sys.stdin.isatty() and sys.stdout and sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def update_verb(args, cwd, done) -> int:
    """3.2.1.0 R4: in a terminal the dry run's lines first, then "Apply? [y/N]"; "n" or Enter leaves the pack as it
    is (exit 1). --yes, --json, --dry-run or no terminal: no question. The lines shown are not printed twice."""
    from halo_harness.packs.install import update
    shown: list = []

    def ask(look: "list[str]") -> bool:
        shown.extend(look)
        print("\n".join(look))
        try:
            return input("Apply? [y/N] ").strip().lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            print()
            return False

    asks = not (args.dry_run or args.json or args.yes) and tty()
    ok, lines = update(args.id, dry_run=args.dry_run, cwd=cwd, confirm=ask if asks else None)
    return done(args, ok, [ln for ln in lines if ln not in shown])


def grant_yes(args):
    """3.4.1.2: `--grant-all` on a pack Halo does not ship: its lines printed and one question in a terminal; --yes
    answers it without one; no terminal and no --yes: None (enable refuses and says how)."""
    if getattr(args, "yes", False):
        return lambda _lines: True
    if args.json or not tty():
        return None

    def ask(lines: "list[str]") -> bool:
        print("\n".join(lines))
        try:
            return input("Grant these? [y/N] ").strip().lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            print()
            return False
    return ask
