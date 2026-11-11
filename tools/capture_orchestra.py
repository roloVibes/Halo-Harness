"""tools/capture_orchestra.py -- a goal run's captures for tools/capture_studio.py --mode orchestra (Halo 3.0.4.0 round
R6b; 3.4.0.0 D "the runs fold": Runs' console, its Start view and its plan canvas pictures went with that view).

* the seeded finished run (the R2 fixture: basket.py, five lanes, one judged conflict, the report; lane 2 takes lane
  1's summary) in a temp git repo, opened by its door `?mode=agents&run=<id>`: its report as a page of History
  (docs/media/studio-run-report.png);
* a review run waiting for its plan (tests/helpers/studio_plan_rig.py): Agents -> Live draws its lead waiting on you
  with Review the plan, nothing else open (docs/media/studio-run-live.png);
* with --dom each page is dumped and its data-testid values counted, plus the Roles section (`roles`: its canvas).

Every run's goal has a repo-relative test command (`rel_test`), every Studio draws you@studio
(tools/capture_identity.py) and every page is guarded before it is counted or shot.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from capture_identity import checked_dump, placeholder

IDS = ("section-tab", "orchestra-root", "start-view", "roles-live-map", "live-run-goal", "live-history", "history-report",
       "history-page", "report-check", "report-lane", "history-report-replay", "history-report-again", "agents-live-lead",
       "agents-live-lane", "agents-live-review", "orchestra-plan", "plan-canvas", "run-goal-drawer", "roles-canvas", "roles-card",
       "roles-tier", "legacy-frame", "panel-title", "section-help")
WINDOW = "--window-size=1500,900"


def rel_test() -> str:
    """The goal's test command, repo-relative: this interpreter by name, its folder first on PATH (3.1.7.0 R2:
    the fixture's own command names the interpreter's absolute path, which a page would draw)."""
    exe = Path(sys.executable)
    os.environ["PATH"] = str(exe.parent) + os.pathsep + os.environ.get("PATH", "")
    return f"{exe.stem if os.name == 'nt' else exe.name} -m unittest -q test_basket"


def counts(dom: str) -> dict:
    return {k: dom.count(f'data-testid="{k}"') for k in IDS}


def shoot(chrome, url: str, target: Path) -> int:
    checked_dump(chrome, url, target.stem, WINDOW)  # the DOM first: no real path or name in the picture
    r = chrome(["--virtual-time-budget=20000", f"--screenshot={target}", WINDOW, "--force-device-scale-factor=2", url])
    if r is None:
        print("no Chrome found: nothing rendered")
        return 2
    good = target.is_file() and target.stat().st_size > 10_000
    print(f"{'wrote' if good else 'FAILED'} {target} ({target.stat().st_size if target.is_file() else 0} bytes)")
    return 0 if good else 1


def planned(out: "Path | None", chrome) -> "dict | int":
    """A run waiting for its plan, on Live: its counts (`out` None) or its picture at `out`."""
    from tests.helpers.studio_plan_rig import PlanRig
    placeholder()
    with PlanRig(test=rel_test()) as rig:
        placeholder(rig.studio.state)
        url = rig.url("agents").replace("#t=", "&feed=off&tour=off#t=")
        if out is None:
            r = checked_dump(chrome, url, "run live", WINDOW, "--virtual-time-budget=20000")
            return counts(r.stdout) if r is not None else 2
        return shoot(chrome, url, out)


def capture(out: str, dom: bool, chrome, serve, state: Path) -> int:
    """Seed, serve, render; the exit code capture_studio.py returns."""
    from tests.helpers.orchestra_studio_rig import cleanup, finished_run
    placeholder(state)
    repo, run_dir = finished_run(chain=True, test=rel_test())  # lane 2 takes lane 1's summary
    srv, url = serve(state, True, repo)  # /?mode=orchestra&feed=off#t=
    try:
        report = url.replace("mode=orchestra&feed=off", f"mode=agents&run={Path(run_dir).name}&feed=off&tour=off")
        roles = url.replace("mode=orchestra&feed=off", "mode=roles&feed=off&tour=off")
        old = url.replace("feed=off", "feed=off&tour=off")  # the old door: Live, Runs' line once
        if dom:
            got = [checked_dump(chrome, u, f"run {k}", WINDOW, "--virtual-time-budget=20000") for k, u in (("report", report), ("roles", roles), ("old", old))]
            if any(r is None for r in got):
                print("no Chrome found")
                return 2
            a, b, c = (r.stdout for r in got)
            print(json.dumps({**counts(a), "roles": counts(b), "old_door": counts(c), "plan": planned(None, chrome)}))
            return 0
        png = Path(out).resolve()
        ok = shoot(chrome, report, png.with_name("studio-run-report.png")) == 0
        ok = planned(png.with_name("studio-run-live.png"), chrome) == 0 and ok
        return 0 if ok else 1
    finally:
        srv.shutdown()
        srv.server_close()
        cleanup(repo)
