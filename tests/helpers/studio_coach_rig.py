"""tests.helpers.studio_coach_rig -- a Studio server over a temp git repo holding
the finished R2 run (tests/helpers/orchestra_studio_rig.py: five lanes, lane
5's import conflicting with lane 4's, a fresh judge, a report), its lane
files given the evidence of three coach cards (Halo 3.0.9.0 round R3):

* lane 2 ran as bio `coach-cheap` (or:vendor/cheap) and hit the return cap
  while lane 1 on bio `coach-strong` (or:vendor/strong) finished first try:
  a model card whose Apply opens bio coach-cheap with or:vendor/strong;
* lane 3 (bio `coach-deny`) was denied WebFetch: a tools card;
* the judged conflict between lanes 5 and 4: a structure card;

plus the bios and the catalog in the Studio's state dir and an ended
mission in its missions folder (tests/helpers/coach_seed.py). For the
coach's Chrome run (tests/helpers/studio_coach.py) and its capture
(tools/capture_orchestra.py). No model is ever called.
"""
from __future__ import annotations

import json
from pathlib import Path


def _lane(run_dir: Path, n: int, **fields) -> None:
    path = run_dir / "lanes" / f"{n}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update(fields)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


class CoachRig:
    def __enter__(self):
        from tests.helpers.coach_seed import mission_folder, seed_home
        from tests.helpers.orchestra_studio_rig import Studio, finished_run
        self.repo, self.run_dir = finished_run()
        self.studio = Studio(self.repo).__enter__()
        seed_home(self.studio.state)
        _lane(self.run_dir, 1, bio="coach-strong")
        _lane(self.run_dir, 2, bio="coach-cheap", pieces_returned=2)
        _lane(self.run_dir, 3, bio="coach-deny", denied=[{"tool_name": "WebFetch", "reason": "denied by rule 'WebFetch'"}])
        self.mission = mission_folder(self.studio.state).name
        return self

    def __exit__(self, *a):
        from tests.helpers.orchestra_studio_rig import cleanup
        self.studio.__exit__(*a)
        cleanup(self.repo)

    def url(self, mode: str = "orchestra") -> str:
        from halo_harness.studio.server import url_for
        return url_for(self.studio.srv, mode).replace("#t=", "&tour=off#t=")

    def coach(self) -> dict:
        return self.studio.get(f"orchestra/{self.run_dir.name}/coach")[1]
