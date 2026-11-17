"""halo_harness.agent.ask_claim -- 3.6.0.2 P73: one answer per waiting ask.

An ask (a permission, a question, a plan review, an approval) parks the worker on a slot in one of the session's
`_*_waiters` dicts. The terminal's card and the control socket (Studio, the phone) can both answer it, each on its
own thread. `claim(table, key)` takes the slot for the first caller only, under one lock, so two answers that cross
give one decision: the winner gets the slot, every later caller gets None and changes nothing. One lock for the
process, not one per session: a sub-agent's waiters are the SAME dict object as its parent's, and stub sessions in
tests carry no lock of their own.
"""

from __future__ import annotations

import threading
from typing import Optional

_LOCK = threading.Lock()


def claim(table: dict, key) -> Optional[dict]:
    """The slot `table[key]` when this caller is the first to claim it, else None."""
    with _LOCK:
        slot = table.get(key) if key is not None else None
        if slot is None or slot.get("claimed"):
            return None
        slot["claimed"] = True
        return slot


def unclaimed(table: dict, key) -> Optional[dict]:
    """The slot when it is there and nobody claimed it yet (a read; it claims nothing)."""
    with _LOCK:
        slot = table.get(key) if key is not None else None
        return None if slot is None or slot.get("claimed") else slot
