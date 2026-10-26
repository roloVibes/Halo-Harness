"""tests.helpers.studio_session_target -- Session's Live column, Halo 3.3.0.0
R6 "the steer knows its target, and the timeline exports a trace", through
real clicks and keys in headless Chrome on the driver base
(tests/helpers/chrome_driver.Driver), over tests/helpers/studio_fleet_rig.py
(this harness's real session behind the real Controller) with three extra
agents and scripted feed frames (tests/helpers/studio_live_rig.py).
tests/test_studio_session_target.py runs it as a subprocess:

    python -m tests.helpers.studio_session_target target   the target line naming main and its call; a row click making
                                                            the researcher the target (its row and its map node outlined,
                                                            the lane lit, the line saying what it was); the row held while
                                                            rows arrive; with the field focused twenty new rows not moving
                                                            the view and the pill counting them; a steer landing under its
                                                            target and the next row marked; the turn-end marker in the list;
                                                            Tab / Shift+Tab cycling; `s` on a focused row; Escape following
                                                            again; Export's download read back through the page
                                                            (tests/helpers/studio_session_target2.py)

The last stdout line is a JSON object of what it saw (exit 2: no Chrome).
No model is called."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_session_steer import AREA, BOX, COL, LINES  # noqa: E402

SCROLL = "document.querySelector('[data-testid=\"session-live-scroll\"]')"
TARGET = f"{COL}.querySelector('[data-testid=\"live-target\"]')"
PILL = f"{COL}.querySelector('[data-testid=\"live-follow\"]')"
HELD = f"{SCROLL}.querySelector('[data-target]')"
SENT = "STEER-T keep the tax rule"


def press(c, key: str, code: str, vk: int, shift: bool = False) -> None:
    """One key through the DevTools input domain (Tab, Shift+Tab, `s`)."""
    mods = 8 if shift else 0
    text = key if len(key) == 1 else ""
    c.call("Input.dispatchKeyEvent", type="keyDown", key=key, code=code, windowsVirtualKeyCode=vk, modifiers=mods, text=text)
    c.call("Input.dispatchKeyEvent", type="keyUp", key=key, code=code, windowsVirtualKeyCode=vk, modifiers=mods)


def line_of(c) -> dict:
    """The target line: the agent it names, the call, what it was, and the box's key."""
    return c.js(f"(() => {{ const t = {TARGET}; if (!t) return null; const q = (id) => t.querySelector(`[data-testid=\"${{id}}\"]`)?.textContent || ''; "
                f"return {{key: t.dataset.key, name: q('live-target-name'), call: q('live-target-call'), was: q('live-target-was'), "
                f"text: t.textContent, box: {BOX}.dataset.key, col: {COL}.dataset.target || ''}}; }})()") or {}


def in_view(c, expr: str) -> bool:
    return bool(c.js(f"(() => {{ const e = {expr}; if (!e) return false; const r = e.getBoundingClientRect(), s = {SCROLL}.getBoundingClientRect(); "
                     "return r.bottom > s.top + 2 && r.top < s.bottom - 2; })()"))


def opened(c, rig) -> dict:
    c.go(rig.url("session"))
    c.wait(f"!!{COL} && document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"]').length >= 6", 40)
    time.sleep(0.8)
    return {"opened": True}


def target_line(c, lv) -> dict:
    """Nothing chosen: the line names main and its call, live from the feed."""
    out: dict = {"main_key": lv.key("main"), "res_key": lv.key("researcher")}
    lv.state("main", state="running", current="Bash: pytest -q")
    lv.tool("main", "Bash", "tg-main-1")
    out["line_main"] = c.wait(f"(() => {{ const t = {TARGET}; return t && t.dataset.key === '{lv.key('main')}' && "
                              "/^Bash \\(pytest -q\\), \\d+ s$/.test(t.querySelector('[data-testid=\"live-target-call\"]').textContent) && 1; })()", 15) and line_of(c)
    time.sleep(1.2)
    out["line_ticks"] = line_of(c).get("call")
    out["main_row_outlined"] = c.js(f"{HELD}?.dataset.key === '{lv.key('main')}'")
    return out


def choose_row(c, lv) -> dict:
    """A click on the researcher's row: it becomes the target, outlined, its node too; the line says what it was."""
    out: dict = {}
    res = lv.key("researcher")
    lv.state("researcher", state="running", current="Grep: discount")
    lv.say("researcher", "ECHO reads the pricing notes. ")
    row = f"{LINES}.filter((l) => l.dataset.key === '{res}' && l.textContent.includes('ECHO')).pop()"
    c.wait(f"!!{row}", 10)
    c.js(f"{row}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.3)
    c.click_on(f"{row}.querySelector('[data-testid=\"session-live-time\"]')")
    c.wait(f"{COL}.dataset.target === '{res}'", 5)
    time.sleep(0.3)
    out["chosen"] = line_of(c)
    out["held_n"] = c.js(f"{HELD}?.dataset.n || ''")
    out["row_n"] = c.js(f"{row}.dataset.n")
    out["outline"] = c.js(f"getComputedStyle({HELD}).outlineStyle")
    node = f"document.querySelector('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"][data-key=\"{res}\"]')"
    out["node_target"] = c.js(f"{node}.hasAttribute('data-target') && !!{node}.querySelector('[data-testid=\"fleet-node-target\"]')")
    out["node_chip"] = c.js(f"getComputedStyle({node}.querySelector('[data-testid=\"fleet-node-steer\"]')).opacity")
    out["lane_lit"] = c.js(f"!!{COL}.querySelector('[data-testid=\"fleet-lane\"][data-key=\"{res}\"][data-selected]')")
    for i in range(10):  # rows arrive from two other agents: the held row stays the held row, in view
        lv.tool(("tester", "docs")[i % 2], "Read", f"tg-fill-{i}", f"fill-{i}.py")
    c.wait(f"{LINES}.filter((l) => l.textContent.includes('fill-9.py')).length >= 1", 10)
    time.sleep(0.4)
    out["held_after"] = c.js(f"{HELD}?.dataset.n || ''")
    out["held_in_view"] = in_view(c, HELD)
    return out


def compose(c, lv) -> dict:
    """The field focused: twenty new rows do not move the view and the pill counts them; a steer lands under its target."""
    out: dict = {}
    # following first (a scroll to the newest row lets the held row go), so the pill counts from the focus on
    c.js(f"{SCROLL}.scrollTop = {SCROLL}.scrollHeight; {SCROLL}.dispatchEvent(new Event('scroll')); 1")
    c.wait(f"{COL}.dataset.follow === 'true'", 5)
    c.click_on(AREA)
    c.wait(f"document.activeElement === {AREA} && !{COL}.dataset.follow && 1", 5)
    top0 = c.js(f"{SCROLL}.scrollTop")
    n0 = c.js(f"{LINES}.length")
    for i in range(20):
        lv.tool("reviewer", "Read", f"tg-new-{i}", f"new-{i}.py")
    c.wait(f"{LINES}.length >= {n0 + 20}", 15)
    time.sleep(0.5)
    out["top_moved"] = abs((c.js(f"{SCROLL}.scrollTop") or 0) - (top0 or 0))
    out["pill"] = c.js(f"{PILL}?.textContent || ''")
    out["still_focused"] = c.js(f"document.activeElement === {AREA}")
    c.type_text(SENT)
    c.key("Enter")
    steer = f"{LINES}.find((l) => l.dataset.kind === 'you' && l.textContent.includes('{SENT}'))"
    c.wait(f"!!{steer}", 8)
    out["steer_text"] = c.js(f"{steer}.querySelector('[data-testid=\"live-steer-row\"]').textContent")
    out["steer_under"] = c.js(f"{steer}.previousElementSibling?.hasAttribute('data-target') && {steer}.previousElementSibling.dataset.key === {steer}.dataset.key")
    lv.say("researcher", "FOXTROT answers the steer.")
    after = f"{LINES}.find((l) => l.textContent.includes('FOXTROT'))"
    c.wait(f"!!{after}", 8)
    out["after_mark"] = c.js(f"[{after}.dataset.after || '', {after}.querySelector('[data-testid=\"live-after-steer\"]')?.textContent || '']")
    lv.frame("main", "turn_marker", {"state": "done", "text": "◼ done · 42 s · 3 tools", "turn": 1})
    out["marker_row"] = c.wait(f"{LINES}.filter((l) => l.dataset.kind === 'state' && l.textContent.includes('◼ done · 42 s · 3 tools')).length", 8)
    return out


class TargetDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        from tests.helpers.studio_live_rig import Live
        from tests.helpers.studio_session_target2 import export, keys
        with StudioFleetRig() as rig:
            lv = Live(rig)
            yield ((opened, (c, rig)), (target_line, (c, lv)), (choose_row, (c, lv)), (compose, (c, lv)), (keys, (c, lv)),
                   (export, (c, rig)))


if __name__ == "__main__":
    sys.exit(TargetDriver(sys.argv[1:]).main())
