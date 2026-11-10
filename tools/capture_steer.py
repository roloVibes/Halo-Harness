"""tools/capture_steer.py -- the two Studio stills behind the README's "Steering a running turn" and "Watching a model
think" (Halo 3.3.16.1 docs), through headless Chrome on the driver base over tests/helpers/studio_fleet_rig.py plus the
extra agents of tests/helpers/studio_live_rig.py and the scripted activity of tools/capture_session_scenes.py. No model
is called:

    python tools/capture_steer.py            docs/media/studio-steer.png and docs/media/studio-thinking.png
    python tools/capture_steer.py --dom      both pages, counted by data-testid (the last stdout line is the JSON)

    docs/media/studio-steer.png      Session: the Live column mid-run, a row clicked so its agent is the steer's target (the
                                     target line names it), a steer typed into the box with Pause and Stop beside it, the
                                     map and the cost on the right
    docs/media/studio-thinking.png   Session: the Live column on one agent (the agent pick): its thinking lines, a finished
                                     Read and an Edit whose time ticks, the phase line under it

1500 x 900 CSS px at scale 2. This harness is `you@studio` (tools/capture_identity.py) and every page is guarded before it
is counted or shot.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

W, H = 1500, 900
STEER = "Use the pricing notes, not the cached total: discount first, then tax."
COL = "document.querySelector('[data-testid=\"session-live-detail\"]')"
AREA = f"{COL}.querySelector('[data-testid=\"fleet-steer\"]')"
IDS = ("section-tab", "session-live-detail", "session-live-line", "session-live-tag", "live-target", "fleet-steer", "roles-card",
       "roles-live", "roles-live-node")


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def steer(c, rig, lv, png: Path) -> int:
    """Session mid-run, a row clicked so its agent is the steer's target, a steer typed (not sent)."""
    from capture_identity import guard_page
    from capture_session_anim import open_session
    from capture_session_scenes import play, session_scene
    open_session(c, rig)
    play(session_scene(lv)[:18]).join(10)  # the spawn, the ask, a finish: a column with something in it
    time.sleep(1.0)
    rows = "[...document.querySelectorAll('[data-testid=\"session-live-line\"]')]"
    c.wait(f"{rows}.length >= 6", 20)
    c.click_on(f"{rows}[{rows}.length - 1]", 0.9, 0.2)  # the implementer's last line: its agent is now the target
    c.wait(f"!!{COL}.querySelector('[data-testid=\"live-target\"]') && {COL}.querySelector('[data-testid=\"live-target-name\"]')?.textContent !== 'main'", 10)
    c.click_on(AREA)
    c.type_text(STEER)
    c.mouse("mouseMoved", 4, 4)
    time.sleep(0.8)
    guard_page(c, "studio-steer")
    return c.shot(png)


def thinking(c, rig, lv, png: Path) -> int:
    """Session's Live column on one agent: its thinking lines, a finished Read, an Edit whose time ticks."""
    from capture_identity import guard_page
    from capture_session_anim import open_session
    open_session(c, rig)
    pick = f"{COL}.querySelector('[data-testid=\"session-live-agent\"]')"
    c.js(f"(() => {{ const s = {pick}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; "
         f"set.call(s, {json.dumps(lv.key('implementer'))}); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})()")
    time.sleep(0.5)
    for text in ("The discount runs after the tax line, so a coupon is taxed. ", "The pricing notes say discount first. ",
                 "I will move the discount above the tax, then rerun the basket suite. "):
        lv.frame("implementer", "thinking_chunk", {"text": text})
        time.sleep(0.25)
    lv.tool("implementer", "Read", "k-1", "basket.py")
    time.sleep(0.6)
    lv.result("implementer", "k-1", "basket.py: 84 lines", tool="Read")
    lv.say("implementer", "Moving the discount above the tax line. ")
    time.sleep(0.4)
    lv.tool("implementer", "Edit", "k-2", "basket.py")
    time.sleep(1.0)
    pill = f"{COL}.querySelector('[data-testid=\"live-follow\"]')"
    if c.js(f"!!{pill}"):
        c.click_on(pill)  # back to following: the newest rows, no pill over them
    c.mouse("mouseMoved", 4, 4)  # no hover chip over a tag
    time.sleep(2.5)  # the Edit's time ticks while it runs
    guard_page(c, "studio-thinking")
    return c.shot(png)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Session's steer and Cast's thinking stream, as stills for the front page")
    ap.add_argument("--dom", action="store_true")
    ap.add_argument("--out", default=str(REPO / "docs" / "media"))
    a = ap.parse_args(argv)
    from capture_identity import begin, guard_page, placeholder
    from tests.helpers.chrome_driver import find_chrome, open_chrome, scope_home
    begin()
    made = scope_home()
    if not find_chrome():
        print(json.dumps({"skip": "no Chrome found"}))
        return 2
    from tests.helpers.studio_fleet_rig import StudioFleetRig
    from tests.helpers.studio_live_rig import Live
    placeholder()
    with StudioFleetRig() as rig:
        rig.full = False
        placeholder(rig.state)
        rig.rail = ""
        lv = Live(rig)
        c = open_chrome(W, H)
        try:
            out = Path(a.out).resolve()
            out.mkdir(parents=True, exist_ok=True)
            if a.dom:
                from capture_session_anim import open_session
                open_session(c, rig)
                guard_page(c, "steer")
                print(json.dumps({"session": counts(c)}))
                return 0
            wrote = [("studio-steer.png", steer(c, rig, lv, out / "studio-steer.png")),
                     ("studio-thinking.png", thinking(c, rig, lv, out / "studio-thinking.png"))]
        finally:
            c.close()
            if made is not None:
                import shutil
                shutil.rmtree(made, ignore_errors=True)
    ok = True
    for name, size in wrote:
        ok = ok and size > 10_000
        print(f"{'wrote' if size > 10_000 else 'FAILED'} {out / name} ({size} bytes)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
