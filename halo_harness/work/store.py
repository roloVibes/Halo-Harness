"""halo_harness.work.store -- read and write the units of any run (Halo
3.1.2.0 R1, docs/WORK.md).

`UnitStore(run_dir)` reads the folder's kind from its marker file (an
Orchestra run's `goal.json`, a mission's `mission.json`, a team run's
`board.json`) and goes through that kind's
adapter (work/adapters/), so the same calls answer for all three:

    store.units()                   every unit, in the run's order
    store.unit(uid) / write(unit)   one unit; an unchanged unit writes its file back byte for byte
    store.state_of(uid)             its state on the one machine (work/states.py)
    store.set_state(uid, state)     move it (the engine's own setter writes the engine's word)
    store.gate(uid) / answer(...)   its gate (work/gate.py)
    store.claims(uid) / claim(...)  its claims (work/claims.py)
    store.ledger()                  the run's log as ledger lines (work/ledger.py)
    store.rows()                    the report rows (work/report.py)
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Optional

RUN_KINDS = {"orchestra": "lane", "mission": "part", "team": "stage", "supervise": "goal"}
UNIT_RUNS = {v: k for k, v in RUN_KINDS.items()}
# 3.1.8.0 R1: the supervisor's goal queue (`<state>/supervise/queue.json`) is checked LAST -- an Orchestra
# run's `goal.json` must never read as the queue.
_MARKERS = (("mission", "mission.json"), ("team", "board.json"), ("orchestra", "goal.json"),
            ("supervise", "queue.json"))


def run_kind(run_dir) -> Optional[str]:
    """orchestra | mission | team, read from the folder's marker file; None for anything else."""
    p = Path(run_dir)
    for kind, marker in _MARKERS:
        if (p / marker).is_file():
            return kind
    return None


def unit_kind(run_dir) -> Optional[str]:
    kind = run_kind(run_dir)
    return RUN_KINDS.get(kind) if kind else None


def kind_of(kind: str) -> str:
    """The unit kind for a unit kind or a run kind (`orchestra` -> `lane`)."""
    k = RUN_KINDS.get(kind, kind)
    if k not in UNIT_RUNS:
        raise ValueError(f"a unit kind is one of lane, part, stage (or orchestra, mission, team), got {kind!r}")
    return k


def adapter_for(kind: str):
    return importlib.import_module(f"halo_harness.work.adapters.{kind_of(kind)}")


class UnitStore:
    def __init__(self, run_dir, kind: Optional[str] = None):
        self.run_dir = Path(run_dir)
        k = kind or unit_kind(self.run_dir)
        if k is None:
            raise ValueError(f"{self.run_dir} is not an Orchestra, mission or team run folder")
        self.kind = kind_of(k)
        self.adapter = adapter_for(self.kind)

    @property
    def run_kind(self) -> str:
        return UNIT_RUNS[self.kind]

    def units(self) -> list:
        return self.adapter.units(self.run_dir)

    def unit(self, uid):
        return self.adapter.unit(self.run_dir, uid)

    def need(self, uid):
        u = self.unit(uid)
        if u is None:
            raise KeyError(f"run {self.run_dir.name} has no {self.kind} {uid!r}")
        return u

    def write(self, unit) -> None:
        if unit.kind != self.kind:
            raise ValueError(f"a {unit.kind} does not belong in a {self.run_kind} run")
        self.adapter.write(self.run_dir, unit)

    def state_of(self, uid) -> str:
        return self.need(uid).state

    def set_state(self, uid, state: str, text: str = "") -> None:
        """Move the unit to machine state `state` through the engine's own setter (its word, its log line)."""
        from halo_harness.work.states import native
        self.adapter.set_native(self.run_dir, uid, native(self.kind, state), text)

    def gate(self, uid) -> dict:
        from halo_harness.work import gate
        return gate.read(self.kind, self.run_dir, uid)

    def answer(self, uid, action: str, text: str = "") -> "tuple[bool, str]":
        from halo_harness.work import gate
        return gate.answer(self.kind, self.run_dir, uid, action, text)

    def claims(self, uid) -> dict:
        from halo_harness.work import claims
        return claims.of(self.kind, self.run_dir, uid)

    def claim(self, uid, key: str, holder: str):
        from halo_harness.work import claims
        return claims.claim(self.kind, self.run_dir, uid, key, holder)

    def ledger(self) -> list:
        return self.adapter.ledger_lines(self.run_dir)

    def rows(self) -> list:
        from halo_harness.work.report import row_of
        return [row_of(u) for u in self.units()]
