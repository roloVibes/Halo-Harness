"""tools/capture_session_anim.py -- the animated captures of Session and Roles
for the front page (Halo 3.1.5.0 R3), through headless Chrome on the driver
base over tests/helpers/studio_fleet_rig.py plus three extra agents
(tests/helpers/studio_live_rig.py) and scripted activity
(tools/capture_session_scenes.py): a frame every ~250 ms for ~7 s, written
as a looping GIF with Pillow (1500 x 900, at most 3 MB), and the stills.

    python tools/capture_session_anim.py                 docs/media/studio-session.gif, studio-session.png (the whole
                                                         dashboard) and studio-session-live.png (the Live column up close)
    python tools/capture_session_anim.py --mode roles    docs/media/studio-roles-live.gif and studio-roles-live.png (the
                                                         canvas glowing, the implementer's Live tab open)
    python tools/capture_session_anim.py --dom           both scenes, short, counted by data-testid: the last stdout line
                                                         is the JSON tests/test_studio_session_live.py pins

Options: --out DIR (default docs/media), --seconds N (default 7), --every S (default 0.25). Exit 2 without Chrome.
No model is called. 3.1.7.0 R2: the rig's harness is you@studio (tools/capture_identity.py; exit 2 when the
name would be this machine's) and every page is guarded before it is counted, filmed or shot.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

W, H = 1500, 900
MAX_GIF = 3 * 1024 * 1024
LIVE_CARDS = "document.querySelectorAll('[data-testid=\"roles-card\"][data-live]')"
COUNT_IDS = ("session-live", "session-live-line", "session-live-tag", "session-live-ask", "fleet-node", "fleet-edge", "session-cost-context",
             "session-cost-spark", "session-cost-share-seg", "roles-card", "roles-card-glyph", "roles-live-badge", "roles-tier", "roles-glow-legend-row")


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(COUNT_IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def open_session(c, rig) -> None:
    c.go(rig.url("session", "&open=session-map,session-cost"))  # 3.3.2.0 R3: Live fills the stage, the map and the cost beside it
    c.wait("!!document.querySelector('[data-testid=\"session-live-detail\"]') && document.querySelectorAll('[data-testid=\"fleet-node\"]').length >= 6", 40)
    time.sleep(1.0)


# The capture's own Roles arrangement (kept only while it films): the canvas wide, the Inspector beside it, the rest as strips.
ROLES_LAYOUT = {"v": 2, "panels": {
    "roles-graph": {"x": 0, "y": 0, "w": 18, "h": 86, "face": "detail", "collapsed": False},
    "roles-inspector": {"x": 18, "y": 0, "w": 6, "h": 66, "face": "detail", "collapsed": False},
    **{pid: {"x": 18, "y": 66 + 5 * i, "w": 6, "h": 20, "face": "detail", "collapsed": True}
       for i, pid in enumerate(("roles-problems", "roles-lineups", "roles-bios", "roles-models"))}}}


def open_roles(c, rig, wide: bool = False) -> None:
    c.go(rig.url("roles"))
    c.wait(f"{LIVE_CARDS}.length >= 3", 40)
    if wide:
        c.js(f"localStorage.setItem('halo.studio.layout.roles', {json.dumps(json.dumps(ROLES_LAYOUT))}); location.reload(); 1")
        time.sleep(1.0)
        c.wait(f"{LIVE_CARDS}.length >= 3", 40)
    time.sleep(1.2)  # the canvas fits itself after its first draw


def frame(c):
    from PIL import Image
    data = base64.b64decode(c.call("Page.captureScreenshot", format="png", captureBeyondViewport=False)["data"])
    return Image.open(io.BytesIO(data)).convert("RGB")


def film(c, steps: list, seconds: float, every: float, at: "dict | None" = None) -> list:
    """Play the scene and take a frame every `every` s for `seconds` s; `at` maps a frame index to an action (a hover)."""
    from capture_session_scenes import play
    c.call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=1, mobile=False)
    play(steps)
    shots, t0 = [], time.monotonic()
    for i in range(int(seconds / every)):
        if at and i in at:
            at[i]()
        time.sleep(max(0.0, t0 + i * every - time.monotonic()))
        shots.append(frame(c))
    return shots


# The state colours (styles/tokens.css, dark): weighted into the palette so a small amber, green or red mark keeps its colour.
STATE_HEX = ("#39d7ff", "#ffb347", "#4ef0a8", "#ff4d8d", "#7c8cff", "#dbe7ff", "#7d8fb3", "#04121c")


def palette_strip(shots: list):
    from PIL import Image
    picks = shots[:: max(1, len(shots) // 6)][:6]
    strip = Image.new("RGB", (W, H * len(picks) + 240))
    for k, im in enumerate(picks):
        strip.paste(im, (0, H * k))
    for j, hexv in enumerate(STATE_HEX):
        strip.paste(Image.new("RGB", (W // len(STATE_HEX), 240), hexv), (j * (W // len(STATE_HEX)), H * len(picks)))
    return strip


def write_gif(shots: list, path: Path, every: float) -> int:
    """The frames on one shared palette (the state colours kept), no dither, looping; fewer colours until it fits MAX_GIF."""
    from PIL import Image
    strip = palette_strip(shots)
    for colors in (128, 96, 64, 48):
        pal = strip.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
        frames = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in shots]
        buf = io.BytesIO()
        frames[0].save(buf, format="GIF", save_all=True, append_images=frames[1:], duration=int(every * 1000), loop=0, optimize=True, disposal=1)
        if buf.tell() <= MAX_GIF or colors == 48:
            path.write_bytes(buf.getvalue())
            return buf.tell()
    return 0


def crop_shot(c, expr: str, path: Path) -> int:
    """A scale-2 PNG of one element (the Live column up close)."""
    x, y, w, h = c.rect(expr)
    c.call("Emulation.setDeviceMetricsOverride", width=W, height=H, deviceScaleFactor=2, mobile=False)
    data = c.call("Page.captureScreenshot", format="png", captureBeyondViewport=False, clip={"x": x, "y": y, "width": w, "height": h, "scale": 1})["data"]
    raw = base64.b64decode(data)
    path.write_bytes(raw)
    return len(raw)


def session(c, rig, lv, out: Path, seconds: float, every: float) -> list:
    from capture_identity import guard_page
    from capture_session_scenes import session_scene
    open_session(c, rig)
    guard_page(c, "session")
    shots = film(c, session_scene(lv), seconds, every)
    guard_page(c, "studio-session")  # what the last frames drew, before any file is written
    g = write_gif(shots, out / "studio-session.gif", every)
    time.sleep(0.8)
    s = c.shot(out / "studio-session.png")
    live = crop_shot(c, "document.querySelector('[data-testid=\"session-live\"]')", out / "studio-session-live.png")
    return [("studio-session.gif", g), ("studio-session.png", s), ("studio-session-live.png", live)]


def roles(c, rig, lv, out: Path, seconds: float, every: float) -> list:
    from capture_identity import guard_page
    from capture_session_scenes import roles_scene
    from tests.helpers.studio_fleet import card_click
    open_roles(c, rig, wide=True)
    guard_page(c, "roles live")
    glyph = "document.querySelector('[data-testid=\"roles-card\"][data-agent=\"implementer\"] [data-testid=\"roles-card-glyph\"]')"

    def hover() -> None:
        x, y, w, h = c.rect(glyph)
        c.mouse("mouseMoved", x + w / 2, y + h / 2)
    n = int(seconds / every)
    shots = film(c, roles_scene(lv), seconds, every, at={int(n * 0.72): hover})
    guard_page(c, "studio-roles-live")  # what the last frames drew, before any file is written
    g = write_gif(shots, out / "studio-roles-live.gif", every)
    c.mouse("mouseMoved", 4, 4)
    card_click(c, "document.querySelector('[data-testid=\"roles-card\"][data-agent=\"implementer\"]')")
    c.wait("!!document.querySelector('[data-testid=\"roles-live\"]')", 15)
    time.sleep(1.2)
    guard_page(c, "studio-roles-live still")
    s = c.shot(out / "studio-roles-live.png")
    c.js("localStorage.removeItem('halo.studio.layout.roles'); 1")
    return [("studio-roles-live.gif", g), ("studio-roles-live.png", s)]


def dom(c, rig, lv) -> dict:
    from capture_identity import guard_page
    from capture_session_scenes import play, roles_scene, session_scene
    open_session(c, rig)
    play(session_scene(lv)[:16]).join(10)  # through the spawn and the ask
    time.sleep(1.0)
    guard_page(c, "session")
    got = {"session": counts(c)}
    open_roles(c, rig)
    play(roles_scene(lv)[:4]).join(10)
    time.sleep(1.0)
    x, y, w, h = c.rect("document.querySelector('[data-testid=\"roles-card-glyph\"]')")
    c.mouse("mouseMoved", x + w / 2, y + h / 2)
    c.wait("!!document.querySelector('[data-testid=\"roles-glow-legend\"]')", 5)
    guard_page(c, "roles live")
    got["roles"] = {**counts(c), "live-card": c.js(f"{LIVE_CARDS}.length")}
    return got


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Session and Roles, animated, for the front page")
    ap.add_argument("--mode", choices=("session", "roles"), default="session")
    ap.add_argument("--dom", action="store_true")
    ap.add_argument("--out", default=str(REPO / "docs" / "media"))
    ap.add_argument("--seconds", type=float, default=7.0)
    ap.add_argument("--every", type=float, default=0.25)
    a = ap.parse_args(argv)
    from capture_identity import begin, placeholder
    from tests.helpers.chrome_driver import find_chrome, open_chrome, scope_home
    begin()  # 3.1.7.0 R2: the neutral temp root and you@studio before the scratch home is made
    made = scope_home()
    if not find_chrome():
        print(json.dumps({"skip": "no Chrome found"}))
        return 2
    from tests.helpers.studio_fleet_rig import StudioFleetRig
    from tests.helpers.studio_live_rig import Live
    placeholder()
    with StudioFleetRig() as rig:
        rig.full = False  # 3.3.2.0 R3: the pictures show the quiet arrangement (each names the panels it opens)
        placeholder(rig.state)  # the rig's own home: you@studio
        rig.rail = ""  # 3.3.2.0 R1: the pictures show Studio as it opens, the icon rail
        lv = Live(rig)
        c = open_chrome(W, H)
        try:
            if a.dom:
                print(json.dumps(dom(c, rig, lv)))
                return 0
            out = Path(a.out).resolve()
            out.mkdir(parents=True, exist_ok=True)
            wrote = (session if a.mode == "session" else roles)(c, rig, lv, out, a.seconds, a.every)
        finally:
            c.close()
            if made is not None:
                import shutil
                shutil.rmtree(made, ignore_errors=True)
    ok = True
    for name, size in wrote:
        good = 10_000 < size <= MAX_GIF
        ok = ok and good
        print(f"{'wrote' if good else 'FAILED'} {out / name} ({size} bytes)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
