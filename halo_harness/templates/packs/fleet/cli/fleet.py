"""The fleet pack's `halo fleet ...` (`contributes.cli`: Halo calls `main(argv)` with the words after the verb; the
verbs themselves are fleet/cli.py's, as they were in Halo's core until 3.4.0.0)."""

from __future__ import annotations


def main(argv) -> int:
    from ..fleet.cli import cmd_fleet
    return cmd_fleet(list(argv))
