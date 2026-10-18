"""halo_harness.start.steps -- the seven steps of `halo start`: key, title and
the one sentence of why each screen shows, plus the fixed goal and the
closing lines (Halo 3.1.1.0 R1)."""

from __future__ import annotations

STEPS = (
    ("lineup", "The lineup",
     "A lineup says which agent, on which model, plays each part; a copy of a shipped one is yours to edit."),
    ("repo", "The sample repo",
     "A small git repo with five empty functions and their tests gives the agents real work that ends in minutes."),
    ("goal", "The goal",
     "An Orchestra run starts from one goal; with --review it pauses after the lead's plan, before anything is written."),
    ("plan", "The plan",
     "The lead split the goal into lanes; you approve the plan (or change it on Studio's plan canvas) before it runs."),
    ("run", "The run",
     "Each lane's worker writes its part in its own git worktree, then the parts merge and the tests run."),
    ("report", "The report and the coach",
     "The report ticks every check of DONE WHEN; the coach reads the run's files and says what to change next time."),
    ("next", "Where to go next",
     "The same pieces grow with you: your own lineup, a team file for a project, a fleet of machines."),
)
KEYS = tuple(k for k, _t, _w in STEPS)
TOTAL = len(STEPS)

GOAL_WHAT = "Write the five functions of basket.py"
GOAL_DONE = "the tests in test_basket.py pass"
GOAL_STOP = "a piece comes back twice"
GOAL_FILES = ("basket.py",)

PLAN_EXPLAIN = (
    "Lanes in one layer run at the same time; a lane with an `after` waits in a later layer until those lanes are done.",
    "A hand-off (`needs`) passes what an earlier lane left, its summary, its units or a file, to the lane that takes it.",
)

COACH_APPLY = "Apply opens the bio in Studio: halo studio --mode orchestra, the report's Coach tab."

NEXT = (
    ("Roles", "edit your lineup's cards, their models and tiers", "halo studio --mode roles"),
    ("Team", "put a team file in your own repo: members, blocks and stages", "halo team init"),
    ("Fleet", "join another machine and give the fleet one goal", "halo fleet pair"),
)

DEFAULT_LINEUP = "halo-dev-cycle"
OWN_PREFIX = "my-"


def step_info(key: str) -> tuple:
    """`(n, title, why)` for a step key (n is 1-based)."""
    for i, (k, title, why) in enumerate(STEPS, 1):
        if k == key:
            return i, title, why
    raise KeyError(key)
