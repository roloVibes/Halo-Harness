"""halo_harness.supervise -- the supervisor (Halo 3.1.8.0 R1, docs/SUPERVISE.md).

`halo supervise` is a daemon that owns a goal queue and runs it without a
TUI: each goal is an Orchestra run or a plain `halo -p` job; it keeps every
lineup's schedules and triggers armed while it runs (no session has to be
open), resumes a run from its last checkpoint after a crash, stops a goal at
its budget, and parks every decision it cannot take in Studio's Attention
queue with one key each. In the morning Studio's Session landing says what
finished, what waits on you and what it cost.

    settings.py   the `supervise` config section and its defaults
    queue.py      the goal store: <state>/supervise/goals/<g-id>.json
    history.py    <state>/supervise/history.jsonl, one line per state change and decision
    pulse.py      the pulse <state>/supervise/pulse.json and the stop file
    heartbeat.py  <run>/runner.json: an Orchestra run's runner, across processes
    budget.py     a goal's and the queue's cap, checked before each lane starts
    runner.py     the goal runners (an Orchestra run, a background job) and their outcome
    decisions.py  the parked decisions: <state>/supervise/decisions/<rid>.json
    asks.py       a supervised job's asks, parked from its control socket's feed
    arm.py        the lineups' schedules and triggers, armed by the supervisor
    loop.py       the tick
    cli.py        `halo supervise [--daemon | --service] | status | stop`
    goal_cli.py   `halo goal add | list | show | rm | hold | release | pause | resume | cancel`
"""
