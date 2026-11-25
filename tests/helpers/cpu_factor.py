"""tests/helpers/cpu_factor.py -- how much slower THIS machine is, now, than the reference machine (3.6.0.21 T3/T4).

A budget of CPU seconds a check sets for a process (Studio idle with Agents -> Live open, launch to idle) is kept on
the reference machine and broken on a hosted runner that is several times slower that day, with the product right.
So such a budget is set against a baseline measured IN THE SAME RUN: a fixed piece of pure-Python work is timed by
the measuring thread's own CPU clock (CPU seconds, the unit those budgets count in), and the factor is that time over the reference time,
never under 1 (a faster machine keeps the plain budget) and capped at 4 (a busy product still fails: tens of percent
of a core is over 4 x 5 %).

Used by `tests.test_studio_first_minute` (launch to idle) and by `scripts/realcheck/steps_close.py` (`idle-cpu`), which
imports it from here: one helper for both.
"""
from __future__ import annotations

import time

# The CPU time of `work()` on the reference machine. Never lower it to make a check pass: the factor is never under 1
# anyway.
REFERENCE_S = 0.20
CAP = 4.0
ROUNDS = 4_000_000


def work() -> int:
    """The fixed piece of work: integer arithmetic in a plain loop (no allocation that grows, no I/O)."""
    h = 0
    for i in range(ROUNDS):
        h = (h * 31 + i) & 0xFFFFFFFF
    return h


def measure(repeats: int = 5) -> float:
    """The median CPU seconds of `work()` over `repeats` runs, by the CALLING THREAD's own clock: another busy thread of
    this process (the realcheck's terminal reader, a thread an earlier test left) is not this machine's speed."""
    times = []
    for _ in range(max(1, repeats)):
        t0 = time.thread_time()
        work()
        times.append(time.thread_time() - t0)
    times.sort()
    return times[len(times) // 2]


def factor(measured: float | None = None, reference_s: float = REFERENCE_S, cap: float = CAP) -> float:
    """measured / reference, never under 1, at most `cap` (rounded to two places; `measured` None measures now)."""
    m = measure() if measured is None else measured
    if not isinstance(m, (int, float)) or m <= 0 or reference_s <= 0:
        return 1.0
    return round(min(cap, max(1.0, m / reference_s)), 2)


def said(budget: str, f: float) -> str:
    """The budget as a line says it: `budget` alone when the factor is 1, else with the factor named."""
    return budget if f == 1.0 else f"{budget} x {f:g} for this machine's speed"
