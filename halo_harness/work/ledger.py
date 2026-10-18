"""halo_harness.work.ledger -- one ledger line for every engine's log (Halo
3.1.2.0 R1, docs/WORK.md).

    {"ts": 1760300000.1, "kind": "state|claim|gate|change|handoff|note",
     "unit": "2" | null, "run": "<run id>", "by": "<who>" | "", "key": "<claim key>" | null,
     "text": "the line's text", "native": "<the engine's own kind word>", "data": {...}}

Each engine keeps its file (orchestra `events.jsonl`, a mission's
`log.jsonl`, a team run's `events.jsonl`, a flow's `events.jsonl`); its
adapter (work/adapters/<kind>.py `ledger_lines`) reads every line as a
LedgerLine. `unit` is the unit the line is about (null for a run-wide line),
`by` the holder, member, harness or runner that wrote it, `key` the claim
key or the file the line names.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

KINDS = ("state", "claim", "gate", "change", "handoff", "note")


@dataclass
class LedgerLine:
    ts: float
    kind: str
    unit: Optional[str]
    run: str
    by: str = ""
    key: Optional[str] = None
    text: str = ""
    native: str = ""
    data: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"a ledger line's kind is one of {', '.join(KINDS)}, got {self.kind!r}")

    def to_dict(self) -> dict:
        return asdict(self)


def line(entry: dict, kind: str, run: str, *, unit=None, by="", key=None, native: str = "", data=None) -> LedgerLine:
    """A LedgerLine from one engine line (`ts` and `text` read from it)."""
    try:
        ts = float(entry.get("ts") or 0.0)
    except (TypeError, ValueError):
        ts = 0.0
    return LedgerLine(ts=ts, kind=kind, unit=None if unit in (None, "") else str(unit), run=str(run),
                      by=str(by or ""), key=None if key in (None, "") else str(key), text=str(entry.get("text") or ""),
                      native=str(native or entry.get("kind") or ""),
                      data=dict(data if data is not None else entry.get("data") or {}))


def read(run_dir, kind: Optional[str] = None) -> list:
    """Every line of the run's log as LedgerLines, oldest first (`kind`: lane|part|stage|step, else read from the folder)."""
    from halo_harness.work.store import adapter_for, unit_kind
    k = kind or unit_kind(run_dir)
    if k is None:
        return []
    return adapter_for(k).ledger_lines(run_dir)


def of_unit(lines: list, uid) -> list:
    return [x for x in lines if x.unit == str(uid)]


def of_kind(lines: list, kind: str) -> list:
    return [x for x in lines if x.kind == kind]
