"""The fleet pack's `/mission [id]` (`contributes.slash`): the fleet's missions, or one mission's parts by harness
(`halo fleet mission status`)."""

from __future__ import annotations


def run(args_text: str, facade) -> str:
    from ..fleet.cli_mission import slash_text
    return slash_text(args_text or "")
