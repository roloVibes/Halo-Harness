"""tests.helpers.studio_canvas_nav -- zoom and pan, the same on every drawing (Halo 3.4.1.3, lib/canvasNav.ts), in
headless Chrome over tests/helpers/studio_fleet_rig.py: the halo-dev-cycle session (main, an implementer, a researcher)
and four agents an Auto main spawned -- a seven-agent tree. tests/test_studio_canvas_nav.py runs it:

    python -m tests.helpers.studio_canvas_nav nav

Per canvas kind -- Session's Map, Agents -> Live, Agents -> Cast -- a Ctrl + wheel notch at a known point zooms and the
drawing under the pointer stays put; Cmd (metaKey) does the same; a pinch-shaped event (ctrlKey, a small pixel delta)
zooms a little; a plain wheel does not zoom; the page's own zoom never changes. Session's Map with the seven agents opens
with its text at or above the readable size. On Cast the keys + and 0, a drag on the background (it pans) and a
double-click there (it fits). The last stdout line is the JSON of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402

SPAWNED = (("a1b2c3d4", "wrangler", "data-wrangler", "or:mock/cheap-coder", "Clean the basket fixtures"),
           ("e5f6a7b8", "triage", "triager", "or:mock/cheap-fast", "Sort the failing cases"),
           ("c9d0e1f2", "scribe", "scribe", "or:mock/glm-5-coder", "Write up the basket change"),
           ("a3b4c5d6", "checker", "verifier", "or:mock/cheap-fast", "Check the basket totals"))
PAGE = "[window.visualViewport ? window.visualViewport.scale : 1, window.devicePixelRatio, document.documentElement.clientWidth]"


def _wheel(c, x: float, y: float, dy: float, mods: int) -> None:
    c.call("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=0, deltaY=dy, modifiers=mods)


def wheels(c, scroller: str, world: str, target: str) -> dict:
    """Ctrl, Cmd, a pinch and a plain wheel over `scroller` at the middle of `target`; the zoom from `world`."""
    out: dict = {"page_before": c.js(PAGE)}
    zoom = lambda: float(c.js(f"+{world}.dataset.zoom") or 0)  # noqa: E731
    c.js(f"{target}.scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    x, y, w, h = c.rect(target)
    import time
    roomy = f"(() => {{ const s = {scroller}; return s.scrollWidth > s.clientWidth + 40 && s.scrollHeight > s.clientHeight + 40; }})()"
    while zoom() > 1.3:  # room to zoom in
        _wheel(c, x + w * 0.5, y + h * 0.5, 120, 2)
        time.sleep(0.15)
    for _ in range(6):  # a drawing bigger than its view: a point can only stay put where there is room to scroll
        if c.js(roomy):
            break
        _wheel(c, x + w * 0.5, y + h * 0.5, -120, 2)
        time.sleep(0.15)
    c.js(f"{target}.scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    for i, (dy, mods, name) in enumerate(((-120, 2, "ctrl"), (-120, 4, "meta"), (-8, 2, "pinch"), (120, 0, "plain"))):
        x, y, w, h = c.rect(target)
        px, py = x + w * 0.5, y + h * 0.5
        z0 = zoom()
        c.mouse("mouseMoved", px, py)
        _wheel(c, px, py, dy, mods)
        if name == "plain":
            import time
            time.sleep(0.6)
            out["plain"] = [z0, zoom()]
            continue
        c.wait(f"Math.abs(+{world}.dataset.zoom - {z0}) > 0.001", 10)
        x2, y2, w2, h2 = c.rect(target)
        # the point under the pointer stays: the same spot of the same box (within 6% of its size)
        out[name] = {"from": z0, "to": zoom(), "kept": abs((px - x2) / w2 - 0.5) < 0.06 and abs((py - y2) / h2 - 0.5) < 0.06,
                     "under": c.js(f"document.elementFromPoint({px}, {py}) && ({target}).contains(document.elementFromPoint({px}, {py}))")}
    out["page_after"] = c.js(PAGE)
    return out


def session_map(c, rig) -> dict:
    from tests.helpers.studio_live_rig import Live
    lv = rig.canvas_live = Live(rig, extra=())
    for aid, name, role, model, task in SPAWNED:
        lv.spawn(aid, name, role, model, task)
        lv.state(name, lineup="auto", bio=role, kind="member")
    c.go(rig.url("session"))
    sm = "document.querySelector('[data-testid=\"session-map\"]')"
    c.wait(f"{sm}?.querySelectorAll('[data-testid=\"roles-live-node\"]').length >= 7", 40)
    world = f"{sm}.querySelector('[data-testid=\"roles-live-world\"]')"
    node = f"{sm}.querySelector('[data-testid=\"roles-live-node\"][data-agent=\"main\"]')"
    out = {"map_nodes": c.js(f"{sm}.querySelectorAll('[data-testid=\"roles-live-node\"]').length")}
    out["map_open_zoom"] = c.wait(f"+{world}.dataset.zoom", 10)
    out["map_text_px"] = c.js(f"(() => {{ const n = {node} || {sm}.querySelector('[data-testid=\"roles-live-node\"]'); "
                              f"return parseFloat(getComputedStyle(n).fontSize) * +{world}.dataset.zoom; }})()")
    out["map_buttons"] = c.js(f"!!{sm}.querySelector('[data-testid=\"canvas-zoom\"]') && !!{sm}.querySelector('[data-testid=\"canvas-fit\"]')")
    out["map"] = wheels(c, f"{sm}.querySelector('.rlm-scroll')", world, node)
    return out


def live(c, rig) -> dict:
    c.go(rig.url("roles", "&view=live"))
    mp = "document.querySelector('[data-testid=\"roles-live-map\"]')"
    c.wait(f"{mp} && +{mp}.dataset.nodes >= 7", 40)
    if c.js("!!document.querySelector('[data-testid=\"live-scope-here\"]')"):
        c.click_on("document.querySelector('[data-testid=\"live-scope-here\"]')")
    world = "document.querySelector('[data-testid=\"agents\"] [data-testid=\"roles-live-world\"]')"
    node = "document.querySelector('[data-testid=\"agents\"] [data-testid=\"roles-live-node\"][data-agent=\"main\"]')"
    c.wait(f"!!{node}", 20)
    return {"live": wheels(c, "document.querySelector('[data-testid=\"agents\"] .rlm-scroll')", world, node)}


def cast(c, rig) -> dict:
    c.click_on("document.querySelector('[data-testid=\"agents-view-cast\"]')")
    world = "document.querySelector('[data-testid=\"roles-world\"]')"
    scroller = "document.querySelector('[data-testid=\"roles-canvas\"] .rc-scroll')"
    card = "document.querySelector('[data-testid=\"roles-card\"]')"
    c.wait(f"!!{world} && !!{card}", 30)
    out = {"cast": wheels(c, scroller, world, card)}
    c.js(f"{scroller}.focus(); 1")
    z0 = float(c.js(f"+{world}.dataset.zoom"))
    c.key("+")
    out["key_plus"] = [z0, c.wait(f"+{world}.dataset.zoom > {z0} && +{world}.dataset.zoom", 5)]
    for _ in range(3):
        c.key("+")
    x, y, w, h = c.rect(scroller)
    # the background: a spot of the scroller with no card, tier box or button under it
    spot = c.js(f"""(() => {{ const s = {scroller}, r = s.getBoundingClientRect();
      for (let fy = 0.95; fy > 0.3; fy -= 0.05) for (let fx = 0.95; fx > 0.3; fx -= 0.05) {{
        const x = r.left + r.width * fx, y = r.top + r.height * fy, e = document.elementFromPoint(x, y);
        if (e === s || e?.matches?.('.rc-world, .rc-inner, .rc-tier')) return [x, y]; }} return null; }})()""")
    out["bg_spot"] = bool(spot)
    if spot:
        before = c.js(f"[{scroller}.scrollLeft, {scroller}.scrollTop]")
        c.drag(spot[0], spot[1], spot[0] - 60, spot[1] - 40)
        out["pan"] = [before, c.js(f"[{scroller}.scrollLeft, {scroller}.scrollTop]")]
        z1 = float(c.js(f"+{world}.dataset.zoom"))
        for kind in ("mousePressed", "mouseReleased"):
            c.call("Input.dispatchMouseEvent", type=kind, x=spot[0] - 60, y=spot[1] - 40, button="left", clickCount=2)
        out["dbl_fit"] = [z1, c.wait(f"+{world}.dataset.zoom < {z1} && +{world}.dataset.zoom", 5)]
    c.js(f"{scroller}.focus(); 1")
    c.key("+")
    z2 = float(c.js(f"+{world}.dataset.zoom"))
    c.key("0")
    out["key_zero"] = [z2, c.wait(f"+{world}.dataset.zoom < {z2} && +{world}.dataset.zoom", 5)]
    return out


class NavDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        c.call("Emulation.setFocusEmulationEnabled", enabled=True)
        with StudioFleetRig() as rig:
            args = (c, rig)
            yield ((session_map, args), (live, args), (cast, args))


if __name__ == "__main__":
    if sys.argv[1:2] != ["nav"]:
        print("usage: python -m tests.helpers.studio_canvas_nav nav", file=sys.stderr)
        sys.exit(2)
    sys.exit(NavDriver(sys.argv[2:]).main())
