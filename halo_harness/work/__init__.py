"""halo_harness.work -- the unit of work under lanes and
supervisor goals (Halo 3.1.2.0 R1, docs/WORK.md; 3.4.0.0 B: a team stage left with the team file).

One model, two front doors: an Orchestra lane and a supervisor goal are both a `Unit` (work/unit.py) on one state
machine (work/states.py, with each engine's words in an alias table), with
claims (work/claims.py), hand-offs (work/handoff.py) and a gate
(work/gate.py); every engine log line reads as a `LedgerLine`
(work/ledger.py) and every report carries a `UnitRow` per unit
(work/report.py). `UnitStore` (work/store.py) reads and writes them through
one adapter per kind (work/adapters/), the only place that knows each
engine's files. The engines keep their commands, routes and files.
"""
