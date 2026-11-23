"""tests.helpers.studio_live_fold_steps -- "fold and lanes" as a person sees it (Halo 3.6.0.15 LW, rules L9a and L9b), in
headless Chrome over tests/helpers/studio_session_rig.py, with the rig and steps of tests/helpers/studio_live_now_steps.py
(imported, never copied). Agents -> Live on Auto at 1440 x 900; Session's drawer at its default width. No model is called.
Every name is invented; every figure a test asserts is read from the page (the zoom from live-world's data-zoom, the view
from the scroll box's clientWidth).

    lanes    L9a: three groups at 1440 x 900: main's and each group's rect, the zoom, the view; then the pointer resting on
             main while the window narrows to 1100 x 800 (nothing may move), then the pointer leaves (every group takes
             the new width)
    three    L9b: a group of four members at 1440 x 900 (three a row), then at 1000 x 800 (two a row), then the same
             groups in Session's drawer at its default width

    python -m tests.helpers.studio_live_fold_steps [step ...]
The last stdout line is a JSON object of what it saw.
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.studio_auto_groups_draw import LSCROLL, LW, P, RECT  # noqa: E402
from tests.helpers.studio_live_now_steps import CLOCK, frames, go, mk, rest_on, to_live, wait_or  # noqa: E402
from tests.helpers.studio_session_map_down import MapDownDriver, Rows  # noqa: E402
from tests.helpers.studio_session_run import M, _main, _seed  # noqa: E402

FRAME = f"document.querySelector('{P} [data-testid=live-frame]')"
# Agents -> Live's geometry: the zoom, the view, the scroll box's scroll width, the world's, main's and each group's rect,
# each group's data-per and its members' rects (in the order drawn)
GEO = f"""(() => {{ const w = {LW}, s = {LSCROLL}; if (!w || !s) return null; const R = {RECT};
  return {{ zoom: +w.dataset.zoom, view: s.clientWidth, sw: s.scrollWidth, world: R(w), main: R(w.querySelector('[data-box=main]')),
    held: {FRAME}?.dataset.held || '',
    groups: Object.fromEntries([...w.querySelectorAll('[data-testid=live-group]')].map((g) => [g.dataset.group, {{ rect: R(g),
      per: g.querySelector('.mp-group-members')?.dataset.per || '', members: [...g.querySelectorAll('[data-member]')].map(R) }}])) }}; }})()"""
# L9a's rule, worked out on the page from what it reads: every group as wide as max(352, min(760, floor(view / zoom - 392)))
SETTLED = f"""(() => {{ const w = {LW}, s = {LSCROLL}; if (!w || !s) return false; const z = +w.dataset.zoom || 1;
  const want = Math.max(352, Math.min(760, Math.floor(s.clientWidth / z - 392)));
  const gs = [...w.querySelectorAll('[data-testid=live-group]')];
  return gs.length > 0 && gs.every((g) => Math.abs(g.getBoundingClientRect().width / z - want) <= 1); }})()"""
MAIN = f"{LW}.querySelector('[data-box=main]')"


def _size(c, w: int, h: int) -> None:
    c.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)


def _narrowed(c, was: float) -> None:
    """Waits until the scroll box is narrower than `was` (the window's new size reached it), then a few frames."""
    wait_or(c, f"({LSCROLL}?.clientWidth || 1e9) < {was} - 50", 15)
    frames(c, 6)


def lanes(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    t0 = time.time() - 5
    main = _main(rows, a, state="running", current="Agent: survey the TODOs", since=t0, started=t0)
    kids = [mk("u1", "researcher", "read part 1", "survey the TODOs", 1, since=t0),
            mk("u2", "coder", "fix the form", "fix the login bug", 2, model="glm-5", since=t0),
            mk("u3", "writer", "note the release", "write the changelog", 3, since=t0)]
    go(c, rig, rows, a, b, [main, *kids])
    c.wait(f"{M}.querySelectorAll('[data-member]').length === 3", 20)
    to_live(c, 3)
    out["settled"] = bool(wait_or(c, SETTLED, 15))
    frames(c, 4)
    out["wide"] = c.js(GEO)
    rest_on(c, MAIN)  # the pointer resting on the drawing: nothing may move while the window narrows
    frames(c, 2)
    before = c.js(GEO) or {}
    _size(c, 1100, 800)
    _narrowed(c, before.get("view") or 0)
    out["resting"] = [before, c.js(GEO)]
    c.mouse("mouseMoved", 2, 400)  # off the frame, on the rail: the new width is drawn
    out["settled_narrow"] = bool(wait_or(c, SETTLED, 15))
    frames(c, 2)
    out["narrow"] = c.js(GEO)
    return {"lanes": out}


def three(c, rig, rows: Rows, a: str, b: str) -> dict:
    out: dict = {}
    t0 = time.time() - 5
    main = _main(rows, a, state="running", current="Agent: survey the TODOs", since=t0, started=t0)
    kids = [mk(f"t{i}", "researcher", f"read part {i}", "survey the TODOs", 1, since=t0) for i in (1, 2, 3, 4)]
    kids += [mk("t5", "coder", "fix the form", "fix the login bug", 2, model="glm-5", since=t0)]
    go(c, rig, rows, a, b, [main, *kids])
    c.wait(f"{M}.querySelectorAll('[data-member]').length === 5", 20)
    to_live(c, 2)
    out["settled"] = bool(wait_or(c, SETTLED, 15))
    frames(c, 4)
    out["wide"] = c.js(GEO) or {}
    _size(c, 1000, 800)
    _narrowed(c, out["wide"].get("view") or 0)
    out["settled_narrow"] = bool(wait_or(c, SETTLED, 15))
    frames(c, 2)
    out["narrow"] = c.js(GEO)
    go(c, rig, rows, a, b, [main, *kids])  # Session's drawer at its default width (1440 x 900 again)
    c.wait(f"{M}.querySelectorAll('[data-member]').length === 5", 20)
    frames(c, 4)
    out["session"] = c.js(f"[...{M}.querySelectorAll('.mp-group-members')].map((e) => e.dataset.per || '')")
    return {"three": out}


STEPS = (lanes, three)


class LiveFoldDriver(MapDownDriver):
    width, height = 1440, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.chrome_driver import emulate_motion
        from tests.helpers.studio_session import FAKE_SID, collect_page_errors, second_session
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            _seed(rig)
            second_session(rig)
            rows = Rows(rig)
            collect_page_errors(c)
            c.call("Page.addScriptToEvaluateOnNewDocument", source=CLOCK)
            emulate_motion(c, "no-preference")
            args = (c, rig, rows, rig.act.session_id, FAKE_SID)
            yield tuple((fn, args) for fn in STEPS if not self.argv or fn.__name__ in self.argv)


if __name__ == "__main__":
    sys.exit(LiveFoldDriver(sys.argv[1:]).main())
