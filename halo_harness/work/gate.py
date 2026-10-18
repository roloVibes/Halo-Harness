"""halo_harness.work.gate -- a unit's gate, the same calls for every kind
(Halo 3.1.2.0 R1, docs/WORK.md).

    {"mode": "required|optional|none", "id": "<open gate id>" | null, "round": n,
     "answer": {"action": "accept|redo|stop", "text", "ts"} | null}

What each kind's gate is:

* lane: the merge and the quality gate, run by code (`required`); the gate
  sends a piece back (`send_back`: one more attempt, the lane `waiting`).
* part: none (a mission's gate is its plan's approval, not a part's).
* stage: `stages/<id>/gate.json` + `answer.json` (team/stages.py), mode
  the stage's `gate:`.
* step: `steps/<n>.gate.json` + `<n>.answer.json` (flows/gates.py), a
  `confirm` step's human gate (`required`).

`read(kind, run_dir, uid)` is the unit's gate with the open gate's id and
round; `answer(...)` writes the answer the engine's runner takes;
`send_back(...)` is the gate's loop for a lane. Each call goes to the
kind's adapter, which calls the engine's own functions.
"""

from __future__ import annotations

import time
from typing import Callable

from halo_harness.work.unit import gate as gate_dict


def _adapter(kind: str):
    from halo_harness.work.store import adapter_for
    return adapter_for(kind)


def read(kind: str, run_dir, uid) -> dict:
    """The unit's gate: mode, the open gate's id and round, the last answer."""
    fn = getattr(_adapter(kind), "read_gate", None)
    return fn(run_dir, uid) if fn is not None else gate_dict("none")


def is_open(kind: str, run_dir, uid) -> bool:
    return bool(read(kind, run_dir, uid).get("id"))


def answer(kind: str, run_dir, uid, action: str, text: str = "") -> "tuple[bool, str]":
    """Answer the unit's open gate (accept | redo | stop): `(ok, message)`."""
    fn = getattr(_adapter(kind), "answer_gate", None)
    if fn is None:
        return False, f"a {kind} has no gate to answer"
    return fn(run_dir, uid, action, text)


def send_back(kind: str, run_dir, uid, text_of: Callable[[int], str], *, clock: Callable = time.time) -> int:
    """The gate's loop: the unit runs again (`text_of(attempts)` is its state line). Returns the attempts."""
    fn = getattr(_adapter(kind), "send_back", None)
    if fn is None:
        raise ValueError(f"a {kind}'s gate sends nothing back: answer it with redo")
    return fn(run_dir, uid, text_of, clock=clock)

