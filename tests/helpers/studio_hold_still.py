"""tests.helpers.studio_hold_still -- the Studio views a person clicks right after they open hold still while their data
lands (3.6.0.0 R5c; tests/helpers/hold_still.py does the holding), for tests/test_studio_hold_still.py:

    python -m tests.helpers.studio_hold_still
    python -m tests.helpers.studio_hold_still --fresh   (3.6.0.0 R5e: the views over a fresh home, see `fresh`)

Over a scratch home with two ended sessions and a finished goal run (the replay seeds: the Map's History has rows), in
headless Chrome, each with every /api/ answer held and then let go one at a time:
  map       Agents -> Map as it opens: the rail, the view bar, the Map bar, History under the map;
  map_all   the same in the drivers' arrangement (`open=all`) with the drawer of what they think and say;
  history   Map -> "Goal runs, files, Compare" clicked before anything landed: the drawer's controls;
  goal      Map -> Run a goal clicked before anything landed: the goal form's controls;
  session   Session as it opens with no live session (its Start view, drawn once the sessions are read): New session,
            Open the workspace anyway;
  session_all  Open the workspace anyway clicked with every panel open (its Live, Feed, Cost... drawers): their controls,
            the view-bar word's slot and the truth block (3.6.0.2 R29 R20);
  crew, workflows  Agents' Agents tab (the coder's form open) and Workflows tab;
  picker    the coder's MODEL picker opened before anything landed: its controls once its rows show;
  local, setup, settings  Local (its Models page), Setup, Settings. (Local's Library is not swept: on the Linux runner its
            filters grow to 2,400 px when the library lands -- a layout of its own to fix, not a small one.)
And "a choice made early survives" (hold_still.survives), each with the answers let go oldest first and newest first:
Best pressed in the picker while its catalog is on its way, the Library's search and source, Settings' search.
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
from tests.helpers.hold_still import clickables, release_until, still, survives  # noqa: E402

RAIL = '[data-testid="rail"]'
VIEWBAR = '[data-testid="viewbar"]'
MAP_BAR = '[data-testid="map-bar"]'
MAP_READY = "!!document.querySelector('[data-testid=\"map-bar\"]')"


def _click_expr(expr: str):
    def go(c):
        c.click_on(expr)
    return go


def _plus(read, *testids: str):
    """`controls` for `still`: `read`'s (clickables) and the elements of `testids` that are no control (a word slot, a
    block of text) measured too: 3.6.0.2 R29 the view-bar word's slot, R20 the truth block."""
    def both(c) -> dict:
        return {**read(c), **{f'[data-testid="{t}"]': f"document.querySelector('[data-testid={t}]')" for t in testids}}
    return both


def _click(testid: str):
    def go(c):
        c.click_on(f"document.querySelector('[data-testid=\"{testid}\"]')")
    return go


FORM = "!!document.querySelector('[data-testid=\"orchestra-model\"]')"
CREW_FORM = "document.querySelector('[data-part=crew] [data-testid=\"crew-form\"]')"
CREW_READY = f"{CREW_FORM}?.dataset.name === 'coder'"
TRIG = f"{CREW_FORM}?.querySelector('[data-testid=\"crew-model\"] [data-testid=\"model-select\"]')"
BEST = "document.querySelector('[data-testid=\"model-sort-best\"]')"
ROWS_READY = "document.querySelectorAll('[data-testid=\"model-row\"]').length > 0"
START = "!!document.querySelector('[data-testid=\"session-start\"]')"
VIEWBAR_READY = "!!document.querySelector('[data-testid=\"viewbar\"]')"

# name: (query, the containers whose controls are measured, ready, a first click, what that click needs drawn)
VIEWS = {
    "map": ("mode=agents&view=map", (RAIL, VIEWBAR, MAP_BAR, '[data-testid="map-history"]'), MAP_READY, None, None),
    "map_all": ("mode=agents&view=map&open=all", (RAIL, VIEWBAR, MAP_BAR, '[data-testid="map-history"]', '[data-testid="map-drawer-panel"]'), MAP_READY, None, None),
    "history": ("mode=agents&view=map", ('[data-testid="map-drawer-panel"]',), "!!document.querySelector('[data-testid=\"map-history-all\"]')",
                _click("map-history-all"), None),
    "goal": ("mode=agents&view=map", ('[data-testid="map-drawer-panel"]',), MAP_READY, _click("map-run-goal"), FORM),
    "session": ("mode=session", (RAIL, ".section-view"), START, None, None),
    "session_all": ("mode=session&open=all", _plus(clickables(".section-view"), "viewbar-word", "session-truth"), START, _click("session-open-workspace"), VIEWBAR_READY),
    "crew": ("mode=agents&view=crew&agent=coder", (RAIL, VIEWBAR, ".section-view"), CREW_READY, None, None),
    "workflows": ("mode=agents&view=workflows", (RAIL, VIEWBAR, ".section-view"), "!!document.querySelector('[data-testid=\"agents\"]')", None, None),
    "picker": ("mode=agents&view=crew&agent=coder", ('[role="dialog"]',), f"!!{TRIG}", _click_expr(TRIG), ROWS_READY),
    "local": ("mode=local", (RAIL, ".section-view"), "!!document.querySelector('.section-view')", None, None),
    "setup": ("mode=setup", (RAIL, ".section-view"), "!!document.querySelector('.section-view')", None, None),
    "settings": ("mode=settings", (RAIL, ".section-view"), "!!document.querySelector('[data-testid=\"settings-search\"]')", None, None),
}


def _type(testid: str, text: str):
    def go(c):
        c.js(f"""(() => {{ const s = document.querySelector('[data-testid="{testid}"]'); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
          set.call(s, {text!r}); s.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()""")
    return go


def _picker_best(c):
    """Open the coder's MODEL picker and press Best at once, the catalog still on its way."""
    c.click_on(TRIG)
    release_until(c, f"!!{BEST}")
    c.click_on(BEST)


def _second(sel: str):
    """Press the second of the buttons `sel` finds (the first is the default)."""
    def go(c):
        release_until(c, f"document.querySelectorAll({sel!r}).length > 1")
        c.click_on(f"document.querySelectorAll({sel!r})[1]")
        c.js(f"document.querySelectorAll({sel!r})[1].dataset.chosen = '1'; 1")
    return go


PRESSED = "document.querySelector('[data-chosen=\"1\"]')?.getAttribute('aria-pressed') === 'true'"
# name: (query, ready, the choice made as soon as it can be, the expression that holds while it is in effect)
CHOICES = {
    "picker_best": ("mode=agents&view=crew&agent=coder", f"!!{TRIG}", _picker_best,
                    f"{BEST}?.getAttribute('aria-pressed') === 'true' && !!document.querySelector('[data-testid=\"model-select-dialog\"]')"),
    "library_search": ("mode=local&page=library", "!!document.querySelector('[data-testid=\"local-library-search\"]')",
                       _type("local-library-search", "qwen"), "document.querySelector('[data-testid=\"local-library-search\"]')?.value === 'qwen'"),
    "library_source": ("mode=local&page=library", "!!document.querySelector('[data-testid=\"local-library-search\"]')",
                       _second('[data-testid="local-library-source-btn"]'), PRESSED),
    "settings_search": ("mode=settings", "!!document.querySelector('[data-testid=\"settings-search\"]')", _type("settings-search", "theme"),
                        "document.querySelector('[data-testid=\"settings-search\"]')?.value === 'theme'"),
}


def choices(c, page) -> dict:
    out = {}
    for name, (query, ready, choose, holds) in CHOICES.items():
        for order in ("oldest", "newest"):
            try:
                out[f"{name}/{order}"] = survives(c, page(query), ready, choose, holds, order=order)
            except Exception as e:
                out[f"{name}/{order}"] = {"error": f"{type(e).__name__}: {e}"[:300]}
    return out


def views(c, page) -> dict:
    out = {}
    for name, (query, boxes, ready, before, then) in VIEWS.items():
        try:
            out[name] = still(c, page(query), boxes if callable(boxes) else clickables(*boxes), ready, before=before, then=then)
        except Exception as e:  # one view that cannot be read says why; the others still run
            out[name] = {"error": f"{type(e).__name__}: {e}"[:300]}
    return out


FRESH_VIEWS = ("session", "crew", "workflows", "map", "local", "setup", "settings")
FRESH_CHOICES = ("settings_search", "library_search")


def fresh(c, page) -> dict:
    """3.6.0.0 R5e: the same views and choices over a FRESH home (nothing seeded, a provider key set and no catalog yet),
    the home a person starts with. The seeded home above did not see: the agent's form and Settings moving 38-77 px when
    the empty catalog's line landed under each MODEL field, Session's Setup giving way to Refresh once the providers'
    status was read, Local's traffic host moving when its options landed."""
    out = {}
    for name in FRESH_VIEWS:
        query, boxes, ready, before, then = VIEWS[name]
        try:
            out[name] = still(c, page(query), clickables(*boxes), ready, before=before, then=then)
        except Exception as e:
            out[name] = {"error": f"{type(e).__name__}: {e}"[:300]}
    for name in FRESH_CHOICES:
        query, ready, choose, holds = CHOICES[name]
        for order in ("oldest", "newest"):
            try:
                out[f"{name}/{order}"] = survives(c, page(query), ready, choose, holds, order=order)
            except Exception as e:
                out[f"{name}/{order}"] = {"error": f"{type(e).__name__}: {e}"[:300]}
    return out


class HoldStillDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from halo_harness.config.paths import bridge_home
        from halo_harness.studio.server import url_for
        if "--fresh" in self.argv:
            import os
            state = bridge_home()
            state.mkdir(parents=True, exist_ok=True)
            # a provider is set up (its key in the env) and nothing is listed yet; its address answers nothing (no network)
            os.environ["OPENROUTER_API_KEY"] = "sk-or-test-not-a-key"
            os.environ["BRIDGE_OPENROUTER_BASE_URL"] = "http://127.0.0.1:9"
            proj = state.parent / "project"
            proj.mkdir(parents=True, exist_ok=True)
            srv, _url = serve(state, proj=proj)
            base = url_for(srv)
            try:
                yield ((fresh, (c, lambda query: base.replace("/#t=", f"/?{query}&tour=off#t="))),)
            finally:
                srv.shutdown()
                srv.server_close()
            return
        from tests.helpers.compare_seed import seed_b, seed_run
        from tests.helpers.catalog_facts_seed import seed as seed_catalog
        from tests.helpers.replay_seed import seed
        state = bridge_home()
        state.mkdir(parents=True, exist_ok=True)
        seed(state)
        seed_catalog(state)  # a catalog of every provider (fixture caches; no network) for the model picker
        seed_b(state)
        proj = state.parent / "project"
        seed_run(proj)
        srv, _url = serve(state, proj=proj)
        base = url_for(srv)

        def page(query: str) -> str:
            return base.replace("/#t=", f"/?{query}&tour=off&level=mid&feed=off#t=")
        try:
            yield ((views, (c, page)), (choices, (c, page)))
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    sys.exit(HoldStillDriver(sys.argv[1:]).main())
