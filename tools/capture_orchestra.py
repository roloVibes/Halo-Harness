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
draws the plan canvas (docs/media/studio-orchestra-plan.png; --dom: "plan"). (3.0.9.0 R3's Coach tab
picture left with the coach in 3.4.0.0 B2: the coach is a pack.)
3.1.7.0 R2: every run's goal has a repo-relative test command (`rel_test`), every Studio draws
you@studio (tools/capture_identity.py) and every page is guarded before it is counted or shot.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from capture_identity import checked_dump, placeholder

ORCH_IDS = ("orchestra-root", "orchestra-graph", "gate", "lane", "claim-region", "report-check", "grid-tile", "section-tab",
            "start-view", "panel-title", "panel-help", "section-help", "orchestra-goal-form", "orchestra-menu-run",
            "orchestra-open-workspace", "roles-canvas", "roles-card", "roles-tier", "legacy-frame", "lane-edge", "lane-base",
            "orchestra-plan", "plan-canvas", "plan-lane", "plan-layer", "plan-edge", "plan-problem", "plan-approve",
            "plan-inspector", "orchestra-review")
WINDOW = "--window-size=1500,900"


def rel_test() -> str:
    """The goal's test command, repo-relative: this interpreter by name, its folder first on PATH (3.1.7.0 R2:
    the fixture's own command names the interpreter's absolute path, which the Goal panel draws)."""
    exe = Path(sys.executable)
    os.environ["PATH"] = str(exe.parent) + os.pathsep + os.environ.get("PATH", "")
    return f"{exe.stem if os.name == 'nt' else exe.name} -m unittest -q test_basket"


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
    placeholder()
    with PlanRig(test=rel_test()) as rig:
        placeholder(rig.studio.state)
        url = rig.url().replace("#t=", "&feed=off#t=")
        if out is None:
            r = checked_dump(chrome, url, "orchestra plan", WINDOW)
            return counts(r.stdout) if r is not None else 2
        checked_dump(chrome, url, "orchestra plan", WINDOW)
        r = chrome([f"--screenshot={out}", WINDOW, "--force-device-scale-factor=2", url])
        if r is None:
            return 2
        good = out.is_file() and out.stat().st_size > 10_000
        print(f"{'wrote' if good else 'FAILED'} {out} ({out.stat().st_size if out.is_file() else 0} bytes)")
        return 0 if good else 1


def capture(out: str, dom: bool, chrome, serve, state: Path) -> int:
    """Seed, serve, render; the exit code capture_studio.py returns."""
    from tests.helpers import orchestra_fixtures as F
    from tests.helpers.orchestra_studio_rig import cleanup, finished_run
    placeholder(state)
    repo, _run_dir = finished_run(chain=True, test=rel_test())  # 3.0.9.0: lane 2 takes lane 1's summary (one lane-edge)
    empty = F.make_repo("orch-empty-")  # a git repo without a run: the Start view
    srv, url = serve(state, True, repo)  # /?mode=orchestra&feed=off#t=
    srv2, url2 = serve(state, True, empty)
    try:
        grid = url.replace("feed=off", "feed=off&tour=off")
        start = url2.replace("feed=off", "feed=off&tour=off")
        roles = grid.replace("mode=orchestra", "mode=roles")
        from tests.helpers.studio_full import full  # 3.3.2.0 R3: the counts read every panel; the picture is the plan, its lanes and report
        if dom:
            got = [checked_dump(chrome, u, f"orchestra {k}", WINDOW) for k, u in (("grid", full(grid)), ("start", start), ("roles", roles), ("welcome", url))]
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
        for target, page in ((grid_png, grid.replace("#", "&open=lanes,report#", 1)), (start_png, start)):
            checked_dump(chrome, page, target.stem, WINDOW)  # the DOM first: no real path or name in the picture
            r = chrome([f"--screenshot={target}", WINDOW, "--force-device-scale-factor=2", page])
            if r is None:
                print("no Chrome found: nothing rendered")
                return 2
            good = target.is_file() and target.stat().st_size > 10_000
            ok = ok and good
            print(f"{'wrote' if good else 'FAILED'} {target} ({target.stat().st_size if target.is_file() else 0} bytes)")
        ok = plan_capture(grid_png.with_name(grid_png.stem + "-plan.png"), chrome) == 0 and ok
        return 0 if ok else 1
    finally:
        for s in (srv, srv2):
            s.shutdown()
            s.server_close()
        cleanup(repo, empty)
