"""The coach pack's `/improve` (`contributes.slash`): what `halo improve` prints, in the session (cli/slash.py)."""

from __future__ import annotations

from .slash import improve


def run(args_text: str, facade) -> str:
    return improve(args_text, facade)
