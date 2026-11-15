"""tests.helpers.studio_canvas_nav -- zoom and pan, the same on every drawing (Halo 3.4.1.3, lib/canvasNav.ts), in
headless Chrome over tests/helpers/studio_session_rig.py: the halo-dev-cycle session (main, an implementer, a researcher)
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


# what a step ran on: the scroller's box, a mark that stays while it is the same element, the lineup it draws
SEEN = "(s => s ? [s.clientWidth, s.clientHeight, (s.__nav = s.__nav || Math.round(performance.now())), (s.closest('[data-lineup]') || s).dataset.lineup || ''] : null)"


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
    for dy, mods, name in ((-120, 2, "ctrl"), (-120, 4, "meta"), (-8, 2, "pinch"), (120, 0, "plain")):
        for again in range(4):
            x, y, w, h = c.rect(target)
            px, py = x + w * 0.5, y + h * 0.5
            z0, b0 = zoom(), c.js(f"{SEEN}({scroller})")
            c.mouse("mouseMoved", px, py)
            _wheel(c, px, py, dy, mods)
            if name == "plain":
                time.sleep(0.6)
                out["plain"] = [z0, zoom()]
                break
            c.wait(f"Math.abs(+{world}.dataset.zoom - {z0}) > 0.001", 10)
            x2, y2, w2, h2 = c.rect(target)
            b1 = c.js(f"{SEEN}({scroller})")
            # the point under the pointer stays: the same spot of the same box (within 6% of its size)
            out[name] = {"from": z0, "to": zoom(), "kept": abs((px - x2) / w2 - 0.5) < 0.06 and abs((py - y2) / h2 - 0.5) < 0.06,
                         "under": c.js(f"document.elementFromPoint({px}, {py}) && ({target}).contains(document.elementFromPoint({px}, {py}))"),
                         "box": [b0, b1], "again": again}  # a red row says what moved under the step
            # "the point stays" is a claim about a box that stays: when the SAME scroller with the SAME drawing changed
            # size under the step (a line or a bar arriving beside it), the step is taken again. A new element or
            # another lineup under the step is never forgiven: that row stays red and says so.
            resized = bool(b0 and b1) and b0[2:] == b1[2:] and b0[:2] != b1[:2]
            if out[name]["kept"] or not resized:
                break
    out["page_after"] = c.js(PAGE)
    return out


def session_map(c, rig) -> dict:
    from tests.helpers.studio_live_rig import Live
    lv = rig.canvas_live = Live(rig, extra=())
    for aid, name, role, model, task in SPAWNED:
        lv.spawn(aid, name, role, model, task)
        lv.state(name, lineup="auto", bio=role, kind="member")
    c.go(rig.url("session"))
    sm = "document.querySelector('[data-testid=\"session-map\"]')"  # 3.6.0.0 R5: the session drawn as its map (LitMini)
    c.wait(f"{sm}?.querySelectorAll('[data-testid=\"session-lit-box\"]').length >= 7", 40)
    world = f"{sm}.querySelector('.mp-mini-world')"
    node = f"{sm}.querySelector('[data-testid=\"session-lit-box\"][data-box=\"main\"]')"
    out = {"map_nodes": c.js(f"{sm}.querySelectorAll('[data-testid=\"session-lit-box\"]').length")}
    out["map_open_zoom"] = c.wait(f"+{world}.dataset.zoom", 10)
    out["map_text_px"] = c.js(f"(() => {{ const n = ({node} || {sm}.querySelector('[data-testid=\"session-lit-box\"]')).querySelector('.mp-name'); "
                              f"return parseFloat(getComputedStyle(n).fontSize) * +{world}.dataset.zoom; }})()")
    out["map_buttons"] = c.js(f"!!{sm}.querySelector('[data-testid=\"canvas-zoom\"]') && !!{sm}.querySelector('[data-testid=\"canvas-fit\"]')")
    out["map"] = wheels(c, f"{sm}.querySelector('.mp-mini-scroll')", world, node)
    return out


class NavDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_session_rig import StudioSessionRig
        c.call("Emulation.setFocusEmulationEnabled", enabled=True)
        with StudioSessionRig() as rig:
            args = (c, rig)
            yield ((session_map, args),)  # 3.6.0.0 R5: Live's and Cast's steps went with them


if __name__ == "__main__":
    if sys.argv[1:2] != ["nav"]:
        print("usage: python -m tests.helpers.studio_canvas_nav nav", file=sys.stderr)
        sys.exit(2)
    sys.exit(NavDriver(sys.argv[2:]).main())
