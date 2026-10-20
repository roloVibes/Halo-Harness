"""halo_harness.studio.coach_probe_job -- the coach's probe in Studio (Halo
3.1.6.0 R2): `POST orchestra/<run>/coach/probe {confirm: true, k?}`
(studio/coach_api.py) starts it.

The probe runs in this process on a daemon thread
(orchestra/coach_probe.start), never through the Orchestra console's one
live run slot (studio/orchestra_live.py), so a run started in Studio and a
probe go side by side. Each step line is published on Studio's live feed as
an `orchestra_state` frame that names no run of the console (no `run` in its
data, a session id that is not `orchestra:<id>`), so the console's own views
are not refreshed by it and the Coach tab's progress line follows it
(ui/src/lib/coach/probe.ts):

    {session_id: "coach-probe:<run id>", event: "orchestra_state", ts,
     data: {probe_of: "<run id>", step: draft|runs|compare|done|failed, line, cand?}}

The last frame's step is `done` (or `failed`); the Coach tab then reads the
run's card again, which the probe's card now leads.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional


def frame(run_id: str, line: str, step: str = "", **data) -> dict:
    return {"session_id": f"coach-probe:{run_id}", "event": "orchestra_state", "ts": time.time(),
            "data": dict(data, probe_of=run_id, step=step, line=line)}


def start(run_dir, *, k=None, cwd=None, state_dir=None, publish: Optional[Callable] = None) -> bool:
    """Start the probe of `run_dir` on a thread; False when one already runs for it in this process."""
    from halo_harness.orchestra import coach_probe as CP
    run_id = Path(run_dir).name

    def on_step(line: str, step: str = "", **data) -> None:
        if publish is None:
            return
        try:
            publish(frame(run_id, line, step, **data))
        except Exception:  # a feed with no listener never stops the probe
            pass
    return CP.start(run_dir, k=k, cwd=cwd, state_dir=state_dir, on_step=on_step)
