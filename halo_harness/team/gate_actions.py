"""halo_harness.team.gate_actions -- the three answers a human gate takes.

A Team stage gate (team/stages.py) offers `accept`, `redo` and `stop`;
`normalize_action` folds the short and spoken forms ("a", "approve",
"yes", "r", "edit", "s", "no") onto one of the three, or returns None.
"""

from __future__ import annotations

from typing import Optional

ACTIONS = ("accept", "redo", "stop")
_ALIASES = {"a": "accept", "approve": "accept", "yes": "accept", "y": "accept", "ok": "accept",
            "r": "redo", "edit": "redo", "e": "redo", "s": "stop", "no": "stop"}


def normalize_action(action: str) -> Optional[str]:
    a = str(action or "").strip().lower()
    a = _ALIASES.get(a, a)
    return a if a in ACTIONS else None
