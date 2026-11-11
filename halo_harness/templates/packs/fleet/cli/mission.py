"""The fleet pack's `halo mission ...`: the same as `halo fleet mission ...` (fleet/cli_mission.py)."""

from __future__ import annotations


def main(argv) -> int:
    from ..fleet.cli import cmd_fleet
    return cmd_fleet(["mission", *list(argv)])
