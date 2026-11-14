"""The first-run pack's engine -- `halo start`, the guided first run (Halo 3.1.1.0
round R1; halo_harness/start/ until 3.4.0.0 B, the first-run pack's since).

Seven steps, one screen each (steps.py holds their titles, the one sentence
of why and the closing "where to go next" lines):

    1 lineup   the lineup it rehearses (the active one, read as it is; 3.3.15.0 R7), its cards as a table (lineup.py)
    2 repo     the sample repo: basket.py and its tests (sample_repo.py)
    3 goal     an Orchestra run with `plan: review` on it (run_steps.py)
    4 plan     the lead's plan, approved (or opened on Studio's plan canvas)
    5 run      the live lanes table until the run ends
    6 report   the report's checks and the coach's cards
    7 next     Agents: Cast, Run a goal and Local, each with its command

engine.py drives them (`StartRun`): every step is emitted as a frame dict
(`{step, key, title, why, command, state, lines}`), which screen.py prints in
a terminal and the pack's routes publish as `start` frames for its Studio panel
(server/start_job.py). `HALO_START_FAKE=1` swaps the model calls for
fake.py's lead, workers and judge, so the whole path runs without a model.
Halo's checks/provider.py says whether a model is configured; fresh.py whether this home
has never had a lineup of its own or a run. 3.2.2.0
R2: card.py is the card the start opens on (what it does, the models it will
call, the estimated cost, the time, what it writes).
"""

from .engine import Options, StartRun  # noqa: F401
