"""tests.helpers.studio_plan_rig -- a Studio server over a temp git repo
(the R2 fixture: basket.py) whose Orchestra runner is the fakes
(tests/helpers/studio_plan.py `runner`: the lead's split chains job-2 on
job-1, the workers wait for `hold`), with one review run already started
and waiting for its plan. For the plan canvas's Chrome run and its capture
(tools/capture_orchestra.py). No model is ever called."""
from __future__ import annotations

import threading
import time


class PlanRig:
    def __init__(self, start: bool = True):
        self.start = start
        self.hold = threading.Event()

    def __enter__(self):
        from halo_harness.studio import orchestra_api
        from tests.helpers import orchestra_fixtures as F
        from tests.helpers.orchestra_studio_rig import Studio
        from tests.helpers.studio_plan import runner
        self.repo = F.make_repo("orch-plan-ui-")
        self.saved, orchestra_api.RUNNER = orchestra_api.RUNNER, runner(self.hold)
        self.studio = Studio(self.repo).__enter__()
        self.run_id = ""
        if self.start:
            goal = {"what": "Write the five functions of basket.py", "done_when": "the tests pass", "stop_when": "two returns",
                    "workers": 5, "files": ["basket.py"], "review": True, "test": f"{F.PY} -m unittest -q test_basket"}
            st, ok = self.studio.post("orchestra/run", goal)
            assert st == 201, ok
            self.run_id = ok["run_id"]
            end = time.monotonic() + 30
            while time.monotonic() < end and self.studio.get(f"orchestra/{self.run_id}")[1]["run"]["state"] != "planned":
                time.sleep(0.1)
        return self

    def __exit__(self, *a):
        from halo_harness.studio import orchestra_api, orchestra_live
        from tests.helpers.orchestra_studio_rig import cleanup
        self.hold.set()
        for rid in [r["run_id"] for r in self.studio.get("orchestra/runs")[1] if r["state"] == "planned"]:
            self.studio.post(f"orchestra/{rid}/reject", {"reason": "the test is over"})
        orchestra_live.wait(60)
        orchestra_api.RUNNER = self.saved
        self.studio.__exit__(*a)
        cleanup(self.repo)

    def url(self, mode: str = "orchestra") -> str:
        from halo_harness.studio.server import url_for
        return url_for(self.studio.srv, mode).replace("#t=", "&tour=off#t=")

    def plan_jobs(self, run_id: str = "") -> list:
        return self.studio.get(f"orchestra/{run_id or self.run_id}/plan")[1].get("jobs") or []

    def last_report(self) -> dict:
        rows = self.studio.get("orchestra/runs")[1]
        return (self.studio.get(f"orchestra/{rows[0]['run_id']}")[1].get("report") or {}) if rows else {}
