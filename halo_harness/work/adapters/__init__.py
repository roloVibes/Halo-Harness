"""halo_harness.work.adapters -- one adapter per unit kind (Halo 3.1.2.0 R1).

`lane` (orchestra `lanes/<n>.json`) and `goal` (the supervisor's queue; 3.4.0.0 B: a team run's `stage` left with
the team file; 3.5.0.0: a fleet mission's `part` left with Fleet). Each adapter is the one place that knows its
engine's file: the record's shape, reading it as a `Unit`, writing a unit
back onto it, its ledger lines and its report row. Every adapter module
has `KIND`, `units(run_dir)`, `unit(run_dir, uid)`, `write(run_dir, unit)`,
`ledger_lines(run_dir)` and `row(unit)`.
"""

from __future__ import annotations

EMPTY = (None, "", [], {}, 0, 0.0)


def overlay(source: dict, fields: dict) -> dict:
    """`source` with `fields` written over it, its key order kept; a field the
    source never had is added only when it carries a value."""
    out = dict(source)
    for key, value in fields.items():
        if key in out or not any(value is e or (type(value) is type(e) and value == e) for e in EMPTY):
            out[key] = value
    return out
