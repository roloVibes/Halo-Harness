"""tests.helpers.studio_room -- Halo 3.6.0.0 R0a "room for everything in Studio" (the owner, 2026-11-12: "the panel is
cramped ... the cramping is very confusing and makes it hard to use"): the density pass extended to the room rules.
Headless Chrome over the Session rig (this harness's real session: the main agent and two sub-agents at work,
tests/helpers/studio_session_rig.py) plus the long-names seed (24 agents and a 20-card lineup with long names, a
40-row model catalog with long refs, the Local seed: tests/helpers/studio_room_seed.py). Every view at 1280 x 800,
1500 x 900 and 1920 x 1000 on its default layout (nothing saved), then each drawer opened from the view bar in turn;
then the breakpoints (R9: 1280, 1920, 1024, 390) and what is kept (R10). Measured in the page with
tests/helpers/studio_room_js.py. Pages are opened one from another directly (no about:blank hop: the boot fix of
studio/shell_assets.py is exercised on every view).

    python -m tests.helpers.studio_room         the JSON of what it saw on the last stdout line (exit 2: no Chrome)
    python -m tests.helpers.studio_room DIR     the same, and a capture of each view into DIR

tests/test_studio_room.py reads it. No model is called beyond the rig's scripted mock."""
from __future__ import annotations

import base64
import json
import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_room_js import CANVASES, DRAWER_BTNS, DRAWINGS, MEASURE, btn, drawn  # noqa: E402

SIZES = ((1280, 800), (1500, 900), (1920, 1000))
VIEWS = (("session", "session", ""), ("agents", "agents", "&view=cast"), ("crew", "agents", "&view=crew&agent=storefront-checkout-regression-reviewer"), ("packs", "packs", ""), ("local", "local", ""),
         ("setup", "setup", ""), ("settings", "settings", ""))
READY = {"session": ".stage-main [data-testid=session-live] .panel-body", "agents": ".stage-main [data-testid=roles-graph] .rc-scroll [data-testid=roles-card]",  # 3.6.0.0: its drawing drawn
         "crew": ".stage-main [data-testid=crew-form][data-name=storefront-checkout-regression-reviewer] [data-testid=crew-try-estimate]",  # 3.6.0.0 R1: 1 · Agents
         "packs": ".stage-main [data-testid=pm-installed] .panel-body", "local": "[data-testid=local-rail-page]",
         "setup": "[data-testid=setup-rail]", "settings": "[data-testid=settings-rail-group]"}
SHOTS: list = []
BOOTED = "!!document.querySelector('#root > *') && !document.documentElement.hasAttribute('data-owner-salt')"


def size(c, w: int, h: int) -> None:
    c.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)
    c.wait(f"innerWidth === {w} && innerHeight === {h}", 10)


def measure(c, timeout: float = 20, expr: str = "") -> dict:
    """The page's room once two reads 300 ms apart agree (a view lays out a moment after its first paint); with `expr`,
    that read instead (3.6.0.0 R8: the drawings, once a drawer's re-fit has settled), its record under "drawings"."""
    if not expr:
        got = measure(c, timeout, f"{MEASURE}({json.dumps(list(CANVASES))})")
        return {**got, "drawings": measure(c, timeout, DRAWINGS)} if isinstance(got, dict) and got else got
    end, last = time.time() + timeout, None
    while time.time() < end:
        got = c.js(expr)
        if got == last and (got or isinstance(got, list)):  # no drawing on a view is an answer too
            return got
        last = got
        time.sleep(0.3)
    return last or {}


def shot(c, name: str) -> None:
    if SHOTS:
        data = c.call("Page.captureScreenshot", format="png")["data"]
        (Path(SHOTS[0]) / f"room-{name}.png").write_bytes(base64.b64decode(data))


def load(c, url: str, name: str) -> None:
    """`url` straight from the page before (no about:blank hop); never the page's own address (a fragment hop)."""
    c.go(url)
    c.wait(BOOTED, 40)
    c.wait(f"!!document.querySelector('{READY[name]}')", 40)


def view(c, rig, w: int, h: int, name: str, mode: str, extra: str) -> dict:
    c.js("try { localStorage.clear(); } catch (e) {} 1")
    load(c, rig.url(mode, extra), name)
    out = {f"{name}@{w}x{h}": measure(c)}
    shot(c, f"{name}-{w}x{h}")
    for pid in (c.js(DRAWER_BTNS) or []):
        if c.js(drawn(pid)):  # 3.6.0.0 R1: a drawer the view opens with itself (the Agents tab's list) is in the first measure
            continue
        c.js(f"{btn(pid)}.click(); 1")
        c.wait(drawn(pid), 20)
        out[f"{name}@{w}x{h}+{pid}"] = measure(c)
        if w == 1500:
            shot(c, f"{name}-{w}x{h}-{pid}")
        c.js(f"{btn(pid)}.click(); 1")
        c.wait(f"!{drawn(pid)}", 20)
    return out


def walk(c, rig) -> dict:
    out: dict = {}
    for w, h in SIZES:
        size(c, w, h)
        for name, mode, extra in VIEWS:
            out.update(view(c, rig, w, h, name, mode, extra))
    return {"room": out}


def opened(c) -> list:
    return c.js("[...document.querySelectorAll('.section-view:not([hidden]) .stage-drawer')].map((d) => [d.dataset.panelIn, !!d.dataset.floating])")


def press(c, pid: str) -> None:
    c.js(f"{btn(pid)}.click(); 1")
    c.wait(drawn(pid), 20)


def breakpoints(c, rig) -> dict:
    """R9: under 1440 one drawer at a time; at 1440 and up one per side while both leave the main thing its 60 % (at
    2560 a left and a right one together; at 1920 the older closes); under 1100 it floats; under 760 the rail is a menu."""
    out: dict = {}
    # 1920: two 360 px drawers would leave the main thing 59.7 % of the stage, so R1 closes the older (`full_hd`); a left and
    # a right drawer stand together on a wider window (`wide`, 2560 px: 3.6.0.0, the Map drawer is 560 px wide)
    for (w, h), key in (((1280, 800), "mid"), ((1920, 1000), "full_hd"), ((2560, 1300), "wide"), ((1024, 768), "narrow")):
        size(c, w, h)
        c.js("try { localStorage.clear(); } catch (e) {} 1")
        load(c, rig.url("session", f"&bp={key}"), "session")  # its own address: the same one again would be a fragment hop
        press(c, "session-map")
        press(c, "session-cost")
        c.wait(f"JSON.stringify({DRAWER_SET}) !== '[]'", 10)
        out[key] = {"open": opened(c), "room": measure(c)}
    size(c, 390, 844)
    load(c, rig.url("session", "&bp=phone"), "session")
    out["phone"] = c.js("[getComputedStyle(document.querySelector('.rail')).display, getComputedStyle(document.querySelector('[data-testid=rail-menu-btn]')).display,"
                        " document.documentElement.scrollWidth <= innerWidth + 1]")
    c.js("document.querySelector('[data-testid=rail-menu-btn]').click(); 1")
    c.wait("getComputedStyle(document.querySelector('.rail')).display !== 'none'", 10)
    out["phone_menu"] = c.js("getComputedStyle(document.querySelector('.rail')).display")
    c.js("document.querySelector('[data-testid=rail-menu-btn]').click(); 1")
    return {"bp": out}


CAST = ".section-view:not([hidden]) .rc"
PCT = f"document.querySelector('{CAST} .rc-zoom button:nth-child(2)')?.textContent"


def hand(c, rig) -> dict:
    """3.6.0.0 R8: a zoom by hand survives a drawer opening (Agents' Cast at 1500 x 900); Fit makes the drawing automatic
    again, so the next box change fits it anew."""
    size(c, 1500, 900)
    c.js("try { localStorage.clear(); } catch (e) {} 1")
    load(c, rig.url("agents", "&view=cast&hand=1"), "agents")
    out = {"auto": measure(c, 10, PCT)}
    for _ in range(2):
        c.js(f"document.querySelector('{CAST} .rc-zoom button[aria-label=\"Zoom in\"]').click(); 1")
    out["hand"] = c.wait(f"{PCT} !== {json.dumps(out['auto'])} && {PCT}", 10)
    first = (c.js(DRAWER_BTNS) or [""])[0]
    press(c, first)
    out["after_drawer"] = measure(c, 10, PCT)
    c.js(f"document.querySelector('{CAST} button[title^=\"Fit the canvas\"]').click(); 1")
    out["fit"] = measure(c, 10, PCT)
    c.js(f"{btn(first)}.click(); 1")
    c.wait(f"!{drawn(first)}", 20)
    out["fit_after_close"] = measure(c, 10, PCT)
    return {"hand": out}


DRAWER_SET = "[...document.querySelectorAll('.section-view:not([hidden]) .stage-drawer')].map((d) => d.dataset.panelIn)"
SAVED = "JSON.parse(localStorage.getItem('halo.studio.layout.session') || 'null')"


def kept(c, rig) -> dict:
    """R10: a drawer opened is kept across a reload without a "custom layout"; an old grid arrangement is dropped with
    the one-time note; a saved view of an older layout version is kept and says so once."""
    size(c, 1500, 900)
    out: dict = {}
    c.js("try { localStorage.clear(); } catch (e) {} 1")
    load(c, rig.url("session", "&again=0"), "session")
    press(c, "session-cost")
    c.wait(f"!!{SAVED}", 10)
    out["saved"] = c.js(SAVED)
    load(c, rig.url("session", "&again=1"), "session")
    c.wait(drawn("session-cost"), 20)
    out["after_reload"] = c.js(f"[{DRAWER_SET}, !!document.querySelector('[data-testid=layout-badge]'), document.querySelector('.hud-strip')?.innerText.includes('layout yours')]")
    grid = {"v": 2, "panels": {"session-live": {"x": 0, "y": 0, "w": 24, "h": 60, "collapsed": False}}}
    c.js(f"localStorage.setItem('halo.studio.layout.session', {json.dumps(json.dumps(grid))}); 1")
    load(c, rig.url("session", "&again=2"), "session")
    c.wait("!!document.querySelector('[data-testid=layout-note]')", 20)
    out["dropped"] = c.js("[document.querySelector('[data-testid=layout-note]').dataset.note, localStorage.getItem('halo.studio.layout.session')]")
    load(c, rig.url("session", "&again=3"), "session")
    out["dropped_again"] = c.js("!!document.querySelector('[data-testid=layout-note]')")
    old = {"v": 3, "lv": 0, "open": ["session-cost"], "widths": {"session-cost": 420}, "tab": "", "added": []}
    c.js(f"localStorage.setItem('halo.studio.layout.session', {json.dumps(json.dumps(old))}); 1")
    load(c, rig.url("session", "&again=4"), "session")
    c.wait("!!document.querySelector('[data-testid=layout-note]')", 20)
    out["changed"] = c.js(f"[document.querySelector('[data-testid=layout-note]').dataset.note, {DRAWER_SET}, "
                          "Math.round(document.querySelector('.stage-drawer[data-panel-in=session-cost]')?.getBoundingClientRect().width || 0)]")
    c.js("document.querySelector('[data-testid=layout-note-new]').click(); 1")
    c.wait("!document.querySelector('[data-testid=layout-note]') && !document.querySelector('.stage-drawer')", 20)
    load(c, rig.url("session", "&again=5"), "session")
    out["changed_again"] = c.js("[!!document.querySelector('[data-testid=layout-note]'), !!document.querySelector('.stage-drawer')]")
    return {"kept": out}


class RoomDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_room_seed import seed_long_names
        from tests.helpers.studio_session_rig import StudioSessionRig
        SHOTS[:] = self.argv[:1]
        with StudioSessionRig() as rig:
            rig.full = False
            rig.plan = ""
            self.out["seed"] = seed_long_names(rig)
            yield ((walk, (c, rig)), (breakpoints, (c, rig)), (kept, (c, rig)), (hand, (c, rig)))


if __name__ == "__main__":
    sys.exit(RoomDriver(sys.argv[1:]).main())
