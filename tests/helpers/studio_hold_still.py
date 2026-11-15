"""tests.helpers.studio_hold_still -- the Studio views a person clicks right after they open hold still while their data
lands (3.6.0.0 R5c; tests/helpers/hold_still.py does the holding), for tests/test_studio_hold_still.py:

    python -m tests.helpers.studio_hold_still

Over a scratch home with two ended sessions and a finished goal run (the replay seeds: the Map's History has rows), in
headless Chrome, each with every /api/ answer held and then let go one at a time:
  map       Agents -> Map as it opens: the rail, the view bar, the Map bar, History under the map;
  map_all   the same in the drivers' arrangement (`open=all`) with the drawer of what they think and say;
  history   Map -> "Goal runs, files, Compare" clicked before anything landed: the drawer's controls;
  goal      Map -> Run a goal clicked before anything landed: the goal form's controls;
  session   Session as it opens with no live session (its Start view, drawn once the sessions are read): New session,
            Open the workspace anyway;
  session_all  Open the workspace anyway clicked with every panel open (its Map, Live, Cost... drawers): their controls.
Each says what it measured and what moved (and after which answer). The last stdout line is the JSON of it (exit 2: no
Chrome). No model is called."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.hold_still import clickables, still  # noqa: E402

RAIL = '[data-testid="rail"]'
VIEWBAR = '[data-testid="viewbar"]'
MAP_BAR = '[data-testid="map-bar"]'
MAP_READY = "!!document.querySelector('[data-testid=\"map-bar\"]')"


def _click(testid: str):
    def go(c):
        c.click_on(f"document.querySelector('[data-testid=\"{testid}\"]')")
    return go


FORM = "!!document.querySelector('[data-testid=\"orchestra-model\"]')"
START = "!!document.querySelector('[data-testid=\"session-start\"]')"
VIEWBAR_READY = "!!document.querySelector('[data-testid=\"viewbar\"]')"

# name: (query, the containers whose controls are measured, ready, a first click, what that click needs drawn)
VIEWS = {
    "map": ("mode=agents&view=map", (RAIL, VIEWBAR, MAP_BAR, '[data-testid="map-history"]'), MAP_READY, None, None),
    "map_all": ("mode=agents&view=map&open=all", (RAIL, VIEWBAR, MAP_BAR, '[data-testid="map-history"]', '[data-testid="map-feed-panel"]'), MAP_READY, None, None),
    "history": ("mode=agents&view=map", ('[data-testid="map-feed-panel"]',), "!!document.querySelector('[data-testid=\"map-history-all\"]')",
                _click("map-history-all"), None),
    "goal": ("mode=agents&view=map", ('[data-testid="map-feed-panel"]',), MAP_READY, _click("map-run-goal"), FORM),
    "session": ("mode=session", (RAIL, ".section-view"), START, None, None),
    "session_all": ("mode=session&open=all", (".section-view",), START, _click("session-open-workspace"), VIEWBAR_READY),
}


def views(c, page) -> dict:
    out = {}
    for name, (query, boxes, ready, before, then) in VIEWS.items():
        try:
            out[name] = still(c, page(query), clickables(*boxes), ready, before=before, then=then)
        except Exception as e:  # one view that cannot be read says why; the others still run
            out[name] = {"error": f"{type(e).__name__}: {e}"[:300]}
    return out


class HoldStillDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.studio.server import url_for
        from tests.helpers.compare_seed import seed_b, seed_run
        from tests.helpers.replay_seed import seed
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        seed(state)
        seed_b(state)
        proj = state.parent / "project"
        seed_run(proj)
        srv, _url = serve(state, proj=proj)
        base = url_for(srv)

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&tour=off&level=mid&feed=off#t=")
        try:
            yield ((views, (c, page)),)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    sys.exit(HoldStillDriver(sys.argv[1:]).main())
