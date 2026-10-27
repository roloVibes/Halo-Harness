"""tests.helpers.studio_ui_panels_room -- the workspace makes room (Halo 3.2.2.0
R5; the owner, live in Studio: "When I move the parts in halo studio over
another block like in roles, they disappear. Moving one block should shrink
the ones next to them without things disappearing"). Real pointer drags in
headless Chrome through the driver base, over Roles at its default layout in
a fresh profile (a seeded catalog, the studio-tiers lineup active).
tests/test_studio_panels_room.py runs it:

    python -m tests.helpers.studio_ui_panels_room room

Steps: the default rectangles; the Canvas's east edge dragged left (a
splitter: the right-hand column moves and widens by the same columns);
Arrange (3.3.2.0 R2: the header's ... menu) puts the defaults back; the Inspector's title bar dragged
over the Canvas (every panel stays inside the viewport, nothing overlaps, the
Canvas is narrower); Arrange again. A drag the runner's pointer path loses is
done again with Alt+Left on the focused panel (`<step>_by: keys`). The last
stdout line is the JSON of what it saw (exit 2: no Chrome). No model is
called."""
from __future__ import annotations

import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_fleet_probe import OVERLAPS as FLEET_OVERLAPS  # noqa: E402  the Fleet layout's overlap check
from tests.helpers.studio_header_menus import more  # noqa: E402

WS = "document.querySelector('.workspace[data-section=\"roles\"]')"
OVERLAPS = FLEET_OVERLAPS.replace('data-section="fleet"', 'data-section="roles"')
assert OVERLAPS != FLEET_OVERLAPS
CELLS = f"""Object.fromEntries([...{WS}.querySelectorAll('.ws-cell')].map((c) => {{ const r = c.getBoundingClientRect();
  return [c.dataset.panel, {{x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height)}}]; }}))"""
# every panel inside the workspace's visible box, and nothing below it to scroll to
OUTSIDE = f"""(() => {{ const w = {WS}, b = w.getBoundingClientRect(), out = [];
  for (const c of w.querySelectorAll('.ws-cell')) {{ const r = c.getBoundingClientRect();
    if (r.left < b.left - 1 || r.top < b.top - 1 || r.right > b.right + 1 || r.bottom > b.bottom + 1) out.push(c.dataset.panel); }}
  if (w.scrollHeight > w.clientHeight + 2 || w.scrollTop > 0) out.push('scrolls:' + w.scrollHeight + '>' + w.clientHeight);
  return out; }})()"""
SAVED = "localStorage.getItem('halo.studio.layout.roles')"


def cell(pid: str) -> str:
    return f"document.querySelector('.ws-cell[data-panel=\"{pid}\"]')"


def settle(c) -> dict:
    """The panel rectangles once they stopped moving."""
    last, end = None, time.time() + 6
    while time.time() < end:
        got = c.js(CELLS)
        if got == last:
            return got
        last = got
        time.sleep(0.3)
    return last or c.js(CELLS)


def grid_of(c) -> dict:
    """The saved arrangement's grid rectangles ({} when nothing is saved)."""
    raw = c.js(SAVED)
    panels = (json.loads(raw) if raw else {}).get("panels") or {}
    return {k: [p["x"], p["y"], p["w"], p["h"]] for k, p in panels.items()}


def alt_left(c, pid: str, times: int) -> None:
    """Alt+Left on the focused panel (the keyboard way to move it) `times` times."""
    c.js(f"{cell(pid)}.querySelector('.panel').focus(); 1")
    for _ in range(times):
        for kind in ("rawKeyDown", "keyUp"):
            c.call("Input.dispatchKeyEvent", type=kind, key="ArrowLeft", code="ArrowLeft", windowsVirtualKeyCode=37, modifiers=1)
        time.sleep(0.05)


def arrange(c) -> dict:
    more(c, "layout-arrange")
    time.sleep(0.4)
    return settle(c)


def room(c, url: str, state: Path) -> dict:
    out: dict = {}
    c.go(url)
    c.wait(f"{WS} && {WS}.querySelectorAll('.ws-cell').length === 6 && document.querySelectorAll('[data-testid=\"roles-card\"]').length >= 7", 40)
    time.sleep(0.8)  # the first draw fits the canvas
    out["default"] = base = settle(c)
    out["default_outside"] = c.js(OUTSIDE)
    out["default_overlaps"] = c.js(OVERLAPS)
    # 1. the Canvas's east edge dragged three columns left: the right-hand column follows it
    col = base["roles-graph"]["w"] / 13
    x, y, w, h = c.rect(f"{cell('roles-graph')}.querySelector('.rz-e')")
    gx = x + 1.5  # the handle's inner half (the panel clips the half outside it)
    c.drag(gx, y + h / 2, gx - 3 * col, y + h / 2, steps=10)
    out["resized"] = r = settle(c)
    out["resize_by"] = "pointer"
    if r["roles-graph"]["w"] == base["roles-graph"]["w"]:  # the runner lost the pointer path: Alt+Shift+Left is the same splitter
        c.js(f"{cell('roles-graph')}.querySelector('.panel').focus(); 1")
        for _ in range(3):
            for kind in ("rawKeyDown", "keyUp"):
                c.call("Input.dispatchKeyEvent", type=kind, key="ArrowLeft", code="ArrowLeft", windowsVirtualKeyCode=37, modifiers=9)
            time.sleep(0.05)
        out["resized"] = r = settle(c)
        out["resize_by"] = "keys"
    out["resize_grid"] = grid_of(c)
    out["resize_overlaps"] = c.js(OVERLAPS)
    out["resize_outside"] = c.js(OUTSIDE)
    # 2. Arrange: the defaults again
    out["arranged"] = arrange(c)
    out["arranged_grid"] = grid_of(c)
    # 3. the Inspector's title bar dragged over the middle of the Canvas
    bar = f"{cell('roles-inspector')}.querySelector('.panel-bar .panel-title')"
    x, y, w, h = c.rect(bar)
    canvas = out["arranged"]["roles-graph"]
    tx = canvas["x"] + canvas["w"] * 0.45
    c.drag(x + w / 2, y + h / 2, tx, y + h / 2, steps=12)
    out["moved"] = m = settle(c)
    out["move_by"] = "pointer"
    if m["roles-inspector"] == out["arranged"]["roles-inspector"]:
        alt_left(c, "roles-inspector", 8)
        out["moved"] = m = settle(c)
        out["move_by"] = "keys"
    out["move_grid"] = grid_of(c)
    out["move_overlaps"] = c.js(OVERLAPS)
    out["move_outside"] = c.js(OUTSIDE)
    out["canvas_cards"] = c.js("document.querySelectorAll('[data-testid=\"roles-card\"]').length")
    # 4. Arrange once more
    out["arranged_again"] = arrange(c)
    return out


class PanelsRoomDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_roles import seed_catalog, seed_tiers
        from capture_studio import seeded_home, serve
        state = seeded_home()
        seed_catalog(state)
        seed_tiers(state)
        srv, url = serve(state, True)
        url = url.replace("mode=orchestra", "mode=roles").replace("feed=off", "feed=off&tour=off&view=workspace")
        try:
            yield ((room, (c, url, state)),)
        finally:
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(PanelsRoomDriver(sys.argv[1:]).main())
