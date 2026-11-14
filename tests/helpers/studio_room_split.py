"""tests.helpers.studio_room_split -- Halo 3.6.0.0 R4b, the owner's report on Session (2026-11-14: "I am unable to adjust
the sizes of the 2 views, i wanted to see the map more and shrink live view ... I cannot just see the map"): one step of
the room driver (tests/helpers/studio_room.py), over the same Session rig, at 1280 x 800, 1500 x 900 and 1920 x 1000:

* the line in the middle, dragged with real pointer events through CDP (Input.dispatchMouseEvent): it stays under the
  pointer at every move, the Map ends wider than Live, the width is saved, and after a reload it is still that width;
  dragged back the other way; Alt+Right / Alt+Left on the Map widen and narrow it by 40 px;
* the drawing while the line moves: it does not re-fit during the drag (its zoom and its count of re-fits stay); when
  the drag ends it re-fits once, to what Fit makes of the new box (a drawing nobody zoomed); a drawing zoomed by hand
  keeps its zoom throughout and is not re-fitted;
* the three arrangements -- Map and Live, Map only (Live mounted, hidden), Live only -- measured with the room measure
  (studio_room_js.MEASURE + DRAWINGS), each kept across a reload, in the view bar's words, and Show both back;
* the floating drawer under 1100 px drags too.

tests/test_studio_room.py reads `split` from the driver's JSON."""
from __future__ import annotations

import json

from tests.helpers.studio_room_js import btn, drawn

SIZES = ((1280, 800), (1500, 900), (1920, 1000))
V = ".section-view:not([hidden])"
MAP = f"{V} .stage-drawer[data-panel-in=session-map]"
SPLIT = f"document.querySelector('{MAP} [data-testid=stage-splitter]')"
WORDS = f"(document.querySelector('{V} [data-testid=viewbar-arrangement]')?.textContent || '')"
SAVED = "JSON.parse(localStorage.getItem('halo.studio.layout.session') || 'null')"
# the drawing's zoom and how many box changes it fitted itself to (lib/canvasNav.ts `data-refits` on its scroller)
ZOOM = (f"(() => {{ const m = document.querySelector('{MAP}'); if (!m) return null; const z = m.querySelector('[data-zoom]');"
        " const s = m.querySelector('.rc-scroll'); return [z ? z.dataset.zoom : '', +(s && s.dataset.refits || 0)]; })()")


def width(sel: str) -> str:
    return f"Math.round(document.querySelector('{sel}')?.getBoundingClientRect().width || 0)"


def widths(c) -> list:
    """[the Map drawer's width, Live's (the main thing's) width] now."""
    return c.js(f"[{width(MAP)}, {width(V + ' .stage-main')}]")


def line_x(c) -> float:
    x, _, w, _ = c.rect(SPLIT)
    return x + w / 2


def only(c, panel: str) -> None:
    """Press the title line's Only this / Show both on `panel`."""
    c.js(f"document.querySelector('{V} [data-panel={json.dumps(panel)}] [data-testid=panel-only]').click(); 1")


def alt(c, key: str, vk: int) -> None:
    for kind in ("rawKeyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key=key, code=key, windowsVirtualKeyCode=vk, modifiers=1)


def drag(c, to_w: int, steps: int = 8) -> dict:
    """Drag the Map's line until the drawer is `to_w` px: after each move, wait until the line is under the pointer
    (the value asserted); the drawing's zoom read at each move and once the drag ended."""
    x0, w0 = line_x(c), widths(c)[0]
    _, y, _, h = c.rect(SPLIT)
    y += h / 2
    before = c.js(ZOOM)
    c.mouse("mouseMoved", x0, y)
    c.mouse("mousePressed", x0, y)
    off, during = [], []
    for i in range(1, steps + 1):
        x = x0 + (to_w - w0) * i / steps
        c.mouse("mouseMoved", x, y)
        c.wait(f"Math.abs((() => {{ const r = {SPLIT}.getBoundingClientRect(); return r.left + r.width / 2; }})() - {x}) < 2", 10)
        off.append(round(line_x(c) - x, 1))
        during.append(c.js(ZOOM))
    c.mouse("mouseReleased", x0 + (to_w - w0), y)
    c.wait(f"!document.documentElement.dataset.resizing && {SAVED}?.widths?.['session-map'] === {width(MAP)}", 10)
    return {"off": off, "before": before, "during": during, "after": settled(c, ZOOM)}


def settled(c, expr: str) -> object:
    """`expr` once two reads in a row agree (a re-fit lands a frame after the drag's end)."""
    last = object()
    for _ in range(60):
        got = c.js(expr)
        if got == last:
            return got
        last = got
        c.wait("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(true))))", 5)
    return last


def fit_now(c) -> object:
    """What Fit makes of the Map's box now (its Fit button)."""
    c.js(f"document.querySelector('{MAP} [data-testid=canvas-fit]').click(); 1")
    return settled(c, ZOOM)


def arrangement(c, measure, key: str, out: dict) -> None:
    out["arr"][key] = {**(measure(c) or {}), "words": c.js(WORDS)}


def at(c, rig, load, measure, w: int, h: int) -> dict:
    c.js("try { localStorage.clear(); } catch (e) {} 1")
    load(c, rig.url("session", f"&split={w}"), "session")
    c.js(f"{btn('session-map')}.click(); 1")
    c.wait(drawn("session-map"), 20)
    c.wait(f"!!document.querySelector('{MAP} .rc-scroll [data-zoom]')", 20)
    out: dict = {"arr": {}, "start": widths(c), "max": c.js(f"+document.querySelector('{MAP}').dataset.max")}
    arrangement(c, measure, f"session@{w}x{h}=map-and-live", out)
    stage = c.js(f"document.querySelector('{V} .stage-row').clientWidth")
    want = int((stage - 36) * 0.62)  # the Map wider than Live: 62 % of what the two share
    out["drag"] = drag(c, want)
    out["fit"] = fit_now(c)
    out["wider"] = widths(c)
    out["saved"] = (c.js(SAVED) or {}).get("widths", {}).get("session-map")
    load(c, rig.url("session", f"&split={w}&again=1"), "session")
    c.wait(drawn("session-map"), 20)
    c.wait(f"{width(MAP)} === {out['saved']}", 20)
    out["reloaded"] = widths(c)
    out["back"] = drag(c, out["saved"] - 120, 4)["off"]  # the other way, under the pointer too
    c.js(f"document.querySelector('{MAP} .panel').focus(); 1")
    w1 = widths(c)[0]
    alt(c, "ArrowRight", 39)
    c.wait(f"{width(MAP)} === {w1 + 40}", 10)
    alt(c, "ArrowLeft", 37)
    c.wait(f"{width(MAP)} === {w1}", 10)
    out["keys"] = [w1, w1 + 40, widths(c)[0]]
    # a zoom by hand survives the drag, and stays after it
    z0 = (c.js(ZOOM) or [""])[0]
    c.js(f"document.querySelector('{MAP} [data-testid=canvas-zoom-in]').click(); 1")
    hand = c.wait(f"(() => {{ const z = {ZOOM}; return z && z[0] !== {json.dumps(z0)} && z; }})()", 10)
    d = drag(c, w1 + 100, 4)
    out["hand"] = {"zoom": hand, "during": d["during"], "after": d["after"]}
    fit_now(c)
    # the three arrangements, each kept across a reload
    only(c, "session-map")
    c.wait(f"{WORDS} === 'Map only'", 10)
    out["mounted"] = c.js(f"[!!document.querySelector('{V} .stage-main[data-away] [data-testid=session-live] .panel-body'), {width(MAP)}]")
    arrangement(c, measure, f"session@{w}x{h}=map-only", out)
    load(c, rig.url("session", f"&split={w}&again=2"), "session")
    c.wait(f"{WORDS} === 'Map only'", 20)
    out["map_only_kept"] = c.js(f"[{WORDS}, !!document.querySelector('{V} .stage-drawer[data-alone][data-panel-in=session-map]')]")
    only(c, "session-map")  # Show both
    c.wait(f"{WORDS} === 'Map and Live'", 10)
    only(c, "session-live")
    c.wait(f"{WORDS} === 'Live only'", 10)
    out["live_only"] = c.js(f"[!!document.querySelector('{MAP}'), {btn('session-map')}.getAttribute('aria-pressed')]")
    arrangement(c, measure, f"session@{w}x{h}=live-only", out)
    load(c, rig.url("session", f"&split={w}&again=3"), "session")
    c.wait(f"{WORDS} === 'Live only'", 20)
    c.js(f"{btn('session-map')}.click(); 1")  # the Map's button brings both back
    c.wait(f"{WORDS} === 'Map and Live' && {drawn('session-map')}", 10)
    out["both_again"] = c.js(WORDS)
    return out


def floating(c, rig, load) -> dict:
    """Under 1100 px the drawer floats over the main thing: its line drags too."""
    c.call("Emulation.setDeviceMetricsOverride", width=1024, height=768, deviceScaleFactor=1, mobile=False)
    c.wait("innerWidth === 1024", 10)
    c.js("try { localStorage.clear(); } catch (e) {} 1")
    load(c, rig.url("session", "&split=float"), "session")
    c.js(f"{btn('session-map')}.click(); 1")
    c.wait(drawn("session-map"), 20)
    w0 = widths(c)[0]
    d = drag(c, w0 + 160, 4)
    return {"from": w0, "to": widths(c)[0], "off": d["off"], "floating": c.js(f"!!document.querySelector('{MAP}').dataset.floating")}


def split(c, rig, size, load, measure) -> dict:
    out = {}
    for w, h in SIZES:
        size(c, w, h)
        out[f"{w}x{h}"] = at(c, rig, load, measure, w, h)
    out["float"] = floating(c, rig, load)
    return {"split": out}
