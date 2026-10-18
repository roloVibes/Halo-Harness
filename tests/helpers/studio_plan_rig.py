"""tests.helpers.studio_plan_rig -- a Studio server over a temp git repo
(the R2 fixture: basket.py) whose Orchestra runner is the fakes
(tests/helpers/studio_plan.py `runner`: the lead's split chains job-2 on
job-1, the workers wait for `hold`), with one review run already started
and waiting for its plan. For the plan canvas's Chrome run and its capture
(tools/capture_orchestra.py). 3.1.2.0 R2: the goal has a tiny `budget_usd`,
the Studio's catalog prices `or:vendor/mid` and the draft gives every lane
that model, so the canvas shows a priced cost chip per lane and the header's
total over the budget. No model is ever called."""
from __future__ import annotations

import json
import threading
import time

PRICED = "or:vendor/mid"
MODELS = {"vendor/mid": {"price_in_per_m": 1.0, "pricing": {"prompt": "0.000001", "completion": "0.000004"}}}


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
                    "workers": 5, "files": ["basket.py"], "review": True, "test": f"{F.PY} -m unittest -q test_basket",
                    "budget_usd": 0.0001}
            st, ok = self.studio.post("orchestra/run", goal)
            assert st == 201, ok
            self.run_id = ok["run_id"]
            end = time.monotonic() + 30
            while time.monotonic() < end and self.studio.get(f"orchestra/{self.run_id}")[1]["run"]["state"] != "planned":
                time.sleep(0.1)
            (self.studio.state / "models.json").write_text(json.dumps(MODELS), encoding="utf-8")
            jobs = [dict(j, model=PRICED) for j in self.plan_jobs()]
            st, _ok = self.studio.call("PUT", f"orchestra/{self.run_id}/plan", {"jobs": jobs})
            assert st == 200, _ok
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
