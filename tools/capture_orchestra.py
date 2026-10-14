"""tools/capture_orchestra.py -- the Orchestra and Roles captures for
tools/capture_studio.py --mode orchestra (Halo 3.0.4.0 round R6b): the run
console over the seeded finished run (the R2 fixture: basket.py, five lanes,
one judged conflict, the report) in a temp git repo
(docs/media/studio-orchestra.png), the Start view over a second repo with no
run (studio-orchestra-start.png), and the Roles section with its groups: the
classic page framed without its own header (studio-roles.png). With --dom
each is dumped and its data-testid values counted, plus the classic page on
its own in embedded mode (the toolbar, the groups, no logo, no mode buttons)
and the shell without `tour=off` (the first-visit welcome).
"""

from __future__ import annotations

import json
from pathlib import Path

ORCH_IDS = ("orchestra-root", "orchestra-graph", "gate", "lane", "claim-region", "report-check", "grid-tile", "section-tab",
            "start-view", "panel-about", "panel-help", "section-help", "orchestra-goal-form", "orchestra-rail-run",
            "orchestra-open-workspace", "legacy-frame")
WINDOW = "--window-size=1500,900"


def counts(dom: str) -> dict:
    return {k: dom.count(f'data-testid="{k}"') for k in ORCH_IDS}


def goal_overflow(dom: str) -> bool:
    """Whether the Goal panel's body scrolls (its `data-overflow` edge) at the default size."""
    if 'data-panel="goal"' not in dom:
        return True
    goal = dom.split('data-panel="goal"', 1)[1].split("data-panel=", 1)[0]
    return "data-overflow" in goal


def legacy_counts(dom: str) -> dict:
    """The classic page in embedded mode: the slim toolbar, the groups, and what it no longer draws."""
    return {"legacy-toolbar": dom.count('data-testid="legacy-toolbar"'), "canvas-group": dom.count('data-testid="canvas-group"'),
            "brand": dom.count('class="brand"'), "mode-buttons": dom.count("<button data-mode="),
            "nodes": dom.count('class="node'), "embedded": int('data-embedded="1"' in dom)}


def capture(out: str, dom: bool, chrome, serve, state: Path) -> int:
    """Seed, serve, render; the exit code capture_studio.py returns."""
    from halo_harness.studio.server import url_for
    from tests.helpers import orchestra_fixtures as F
    from tests.helpers.orchestra_studio_rig import cleanup, finished_run
    repo, _run_dir = finished_run()
    empty = F.make_repo("orch-empty-")  # a git repo without a run: the Start view
    srv, url = serve(state, True, repo)  # /?mode=orchestra&feed=off#t=
    srv2, url2 = serve(state, True, empty)
    try:
        grid = url.replace("feed=off", "feed=off&tour=off")
        start = url2.replace("feed=off", "feed=off&tour=off")
        roles = grid.replace("mode=orchestra", "mode=roles")
        if dom:
            legacy = url_for(srv, "roles", legacy=True).replace("?mode=roles", "?mode=roles&embedded=1&tour=off")
            got = [chrome(["--dump-dom", WINDOW, u]) for u in (grid, start, roles, legacy, url)]
            if any(r is None for r in got):
                print("no Chrome found")
                return 2
            a, b, c, d, e = (r.stdout for r in got)
            print(json.dumps({**counts(a), "goal-overflow": goal_overflow(a), "start": counts(b),
                              "roles": {**counts(c), **legacy_counts(d)}, "welcome": counts(e)}))
            return 0
        grid_png = Path(out).resolve()
        start_png = grid_png.with_name(grid_png.stem + "-start.png")
        roles_png = grid_png.with_name("studio-roles.png")
        ok = True
        for target, page in ((grid_png, grid), (start_png, start), (roles_png, roles)):
            r = chrome([f"--screenshot={target}", WINDOW, "--force-device-scale-factor=2", page])
            if r is None:
                print("no Chrome found: nothing rendered")
                return 2
            good = target.is_file() and target.stat().st_size > 10_000
            ok = ok and good
            print(f"{'wrote' if good else 'FAILED'} {target} ({target.stat().st_size if target.is_file() else 0} bytes)")
        return 0 if ok else 1
    finally:
        for s in (srv, srv2):
            s.shutdown()
            s.server_close()
        cleanup(repo, empty)
