"""tools/capture_orchestra.py -- the Orchestra and Roles captures for
tools/capture_studio.py --mode orchestra (Halo 3.0.4.0 round R6b): the run
console over the seeded finished run (the R2 fixture: basket.py, five lanes,
one judged conflict, the report; 3.0.9.0: lane 2 takes lane 1's summary) in a temp git repo
(docs/media/studio-orchestra.png), the Start view over a second repo with no
run (studio-orchestra-start.png). With --dom each is dumped and its
data-testid values counted, plus the Roles section (3.0.7.0 R2: React, its
canvas; tools/capture_roles.py takes its picture) and the shell without
`tour=off` (the first-visit welcome). 3.0.9.0 R2: a review run waiting for
its plan (tests/helpers/studio_plan_rig.py: lane 2 takes lane 1's summary)
draws the plan canvas (docs/media/studio-orchestra-plan.png; --dom: "plan"). 3.0.9.0 R3: the
finished run with three coach findings (tests/helpers/studio_coach_rig.py), its Report panel
floated wide on the Coach tab (docs/media/studio-orchestra-coach.png, through the DevTools protocol).
"""

from __future__ import annotations

import json
from pathlib import Path

ORCH_IDS = ("orchestra-root", "orchestra-graph", "gate", "lane", "claim-region", "report-check", "grid-tile", "section-tab",
            "start-view", "panel-about", "panel-help", "section-help", "orchestra-goal-form", "orchestra-rail-run",
            "orchestra-open-workspace", "roles-canvas", "roles-card", "roles-tier", "legacy-frame", "lane-edge", "lane-base",
            "orchestra-plan", "plan-canvas", "plan-lane", "plan-layer", "plan-edge", "plan-problem", "plan-approve",
            "plan-inspector", "orchestra-review")
WINDOW = "--window-size=1500,900"


def counts(dom: str) -> dict:
    return {k: dom.count(f'data-testid="{k}"') for k in ORCH_IDS}


def goal_overflow(dom: str) -> bool:
    """Whether the Goal panel's body scrolls (its `data-overflow` edge) at the default size."""
    if 'data-panel="goal"' not in dom:
        return True
    goal = dom.split('data-panel="goal"', 1)[1].split("data-panel=", 1)[0]
    return "data-overflow" in goal


def plan_capture(out: "Path | None", chrome) -> "dict | int":
    """The planned run's canvas: its counts (`out` None) or its picture at `out`."""
    from tests.helpers.studio_plan_rig import PlanRig
    with PlanRig() as rig:
        url = rig.url().replace("#t=", "&feed=off#t=")
        if out is None:
            r = chrome(["--dump-dom", WINDOW, url])
            return counts(r.stdout) if r is not None else 2
        r = chrome([f"--screenshot={out}", WINDOW, "--force-device-scale-factor=2", url])
        if r is None:
            return 2
        good = out.is_file() and out.stat().st_size > 10_000
        print(f"{'wrote' if good else 'FAILED'} {out} ({out.stat().st_size if out.is_file() else 0} bytes)")
        return 0 if good else 1


COACH_LAYOUT = {"v": 2, "panels": {"report": {"x": 14, "y": 64, "w": 5, "h": 30, "collapsed": False, "floating": True,
                                             "fx": 330, "fy": 36, "fw": 760, "fh": 780, "face": "detail", "z": 60}}}


def coach_capture(out: Path) -> int:
    """The Coach tab of a finished run's report, its panel floated wide, as a picture at `out`."""
    from capture_studio import find_chrome
    exe = find_chrome()
    if not exe:
        return 2
    from tests.helpers.cdp import Chrome
    from tests.helpers.studio_coach_rig import CoachRig
    c = Chrome(exe)
    try:
        with CoachRig() as rig:
            c.go(rig.url())
            c.js(f"localStorage.setItem('halo.studio.layout.orchestra', {json.dumps(json.dumps(COACH_LAYOUT))}); 1")
            c.go("about:blank")
            c.go(rig.url())
            c.wait("!!document.querySelector('[data-testid=\"report-tab-coach\"]')", 30)
            c.click_on("document.querySelector('[data-testid=\"report-tab-coach\"]')")
            c.wait("document.querySelectorAll('[data-testid=\"coach-card\"]').length === 3", 20)
            size = c.shot(out)
            c.go("about:blank")
    finally:
        c.close()
    good = out.is_file() and size > 10_000
    print(f"{'wrote' if good else 'FAILED'} {out} ({size} bytes)")
    return 0 if good else 1


def capture(out: str, dom: bool, chrome, serve, state: Path) -> int:
    """Seed, serve, render; the exit code capture_studio.py returns."""
    from tests.helpers import orchestra_fixtures as F
    from tests.helpers.orchestra_studio_rig import cleanup, finished_run
    repo, _run_dir = finished_run(chain=True)  # 3.0.9.0: lane 2 takes lane 1's summary (one lane-edge)
    empty = F.make_repo("orch-empty-")  # a git repo without a run: the Start view
    srv, url = serve(state, True, repo)  # /?mode=orchestra&feed=off#t=
    srv2, url2 = serve(state, True, empty)
    try:
        grid = url.replace("feed=off", "feed=off&tour=off")
        start = url2.replace("feed=off", "feed=off&tour=off")
        roles = grid.replace("mode=orchestra", "mode=roles")
        if dom:
            got = [chrome(["--dump-dom", WINDOW, u]) for u in (grid, start, roles, url)]
            if any(r is None for r in got):
                print("no Chrome found")
                return 2
            a, b, c, e = (r.stdout for r in got)
            plan = plan_capture(None, chrome)
            print(json.dumps({**counts(a), "goal-overflow": goal_overflow(a), "start": counts(b),
                              "roles": counts(c), "welcome": counts(e), "plan": plan}))
            return 0
        grid_png = Path(out).resolve()
        start_png = grid_png.with_name(grid_png.stem + "-start.png")
        ok = True
        for target, page in ((grid_png, grid), (start_png, start)):
            r = chrome([f"--screenshot={target}", WINDOW, "--force-device-scale-factor=2", page])
            if r is None:
                print("no Chrome found: nothing rendered")
                return 2
            good = target.is_file() and target.stat().st_size > 10_000
            ok = ok and good
            print(f"{'wrote' if good else 'FAILED'} {target} ({target.stat().st_size if target.is_file() else 0} bytes)")
        ok = plan_capture(grid_png.with_name(grid_png.stem + "-plan.png"), chrome) == 0 and ok
        ok = coach_capture(grid_png.with_name(grid_png.stem + "-coach.png")) == 0 and ok  # 3.0.9.0 R3
        return 0 if ok else 1
    finally:
        for s in (srv, srv2):
            s.shutdown()
            s.server_close()
        cleanup(repo, empty)
