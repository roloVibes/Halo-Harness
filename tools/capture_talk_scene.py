"""tools/capture_talk_scene.py -- the two 3.3.16.2 scenes tools/capture_steer.py shoots for the README's "Watching a
model think" and "Agents talking" (scripted feed frames over tests/helpers/studio_live_rig.py; no model is called):

    thinking(c, rig, lv, png)   docs/media/studio-thinking.png: Live on the implementer with the Thinking view on --
                                two thoughts, each with its length and tokens and linked to the Read or the Edit it
                                led to -- and its timeline lane in phase segments
    talk(c, rig, lv, png)       docs/media/studio-talk.png: Live with TALK rows (main hands the researcher a task, the
                                researcher hands back, main hands a square a PDF) and the Conversations panel open on
                                the main and researcher thread
"""
from __future__ import annotations

import json
import time
from pathlib import Path

COL = "document.querySelector('[data-testid=\"session-live-detail\"]')"
THOUGHTS = (
    ("k-t1", ("The basket test fails by one cent: the discount runs after the tax line. ",
              "I should read how basket.py orders the two."), 2600, 214, ("Read", "k-r1", "basket.py")),
    ("k-t2", ("total() adds the tax, checkout() takes the discount; the pricing notes say discount first. ",
              "Moving it into total(), above the tax line, fixes the order."), 3400, 388, ("Edit", "k-e1", "basket.py")),
)


def _pick(c, key: str) -> None:
    pick = f"{COL}.querySelector('[data-testid=\"session-live-agent\"]')"
    c.js(f"(() => {{ const s = {pick}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; "
         f"set.call(s, {json.dumps(key)}); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})()")


def thinking(c, rig, lv, png: Path) -> int:
    from capture_identity import guard_page
    from capture_session_anim import open_session
    open_session(c, rig)
    _pick(c, lv.key("implementer"))
    time.sleep(0.4)
    c.click_on(f"{COL}.querySelector('[data-testid=\"live-think-view\"]')")
    c.click_on(f"{COL}.querySelector('[data-testid=\"fleet-span-5\"]')")  # five minutes: the phases have room
    for tid, pieces, ms, tokens, (tool, call, target) in THOUGHTS:
        for p in pieces:
            lv.think("implementer", tid, p)
            time.sleep(1.6)
        lv.think("implementer", tid, "", end=True, ms=ms, tokens=tokens)
        lv.tool("implementer", tool, call, target)
        time.sleep(3.0)
        lv.result("implementer", call, f"{target}: ok", tool=tool)
        time.sleep(2.0)
    c.mouse("mouseMoved", 4, 4)
    time.sleep(1.2)
    guard_page(c, "studio-thinking")
    return c.shot(png)


def _talk_only(c) -> None:
    """The kind pick on talk: the TALK rows alone."""
    pick = f"{COL}.querySelector('[data-testid=\"session-live-kind-pick\"]')"
    c.js(f"(() => {{ const s = {pick}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set; "
         "set.call(s, 'talk'); s.dispatchEvent(new Event('change', {bubbles: true})); })()")


def _everyone(c) -> None:
    """Live on every agent, every row (the thinking scene before it pinned one and turned the Thinking view on)."""
    pinned = f"{COL}.querySelector('[data-testid=\"session-live-pinned\"]')"
    if c.js(f"!!{pinned}"):
        c.click_on(pinned)
    view = f"{COL}.querySelector('[data-testid=\"live-think-view\"]')"
    if c.js(f"{view}.getAttribute('aria-pressed') === 'true'"):
        c.click_on(view)
    c.wait(f"!{COL}.dataset.pinned && !{COL}.dataset.think", 5)


def talk(c, rig, lv, png: Path) -> int:
    from capture_identity import guard_page
    from capture_session_anim import open_session
    open_session(c, rig)
    _everyone(c)
    _talk_only(c)
    lv.talk("main", "researcher", "Read the pricing notes: does the discount apply before or after tax? Quote the line.",
            "task", mid="cv-1")
    time.sleep(1.0)
    lv.talk("main", "docs", "Summarise prices-2026.pdf in three lines: the totals and the discount rule.",
            "square", mid="cv-2", square="media")
    time.sleep(1.0)
    lv.talk("researcher", "main", "Before tax: pricing-notes.md line 12 says discount the subtotal, then add tax.", "hand-back",
            mid="cv-3", re="cv-1")
    time.sleep(1.0)
    lv.talk("docs", "main", "Three tiers: under 50 none, 50 to 200 five per cent, over 200 ten; prices exclude tax.",
            "square", mid="cv-4", square="media", re="cv-2")
    time.sleep(0.6)
    item = "document.querySelector('.section-view:not([hidden]) [data-testid=\"viewbar-btn\"][data-panel=\"session-conversations\"]')"  # 3.6.0.0 R0a
    c.wait(f"!!{item}", 5)
    c.click_on(item)
    c.wait("!!document.querySelector('[data-testid=\"conv-panel\"]')", 10)
    for panel in ("session-map", "session-cost"):  # Conversations takes the left column's height
        strip = f"document.querySelector('.stage-drawer [data-panel=\"{panel}\"] [data-testid=\"panel-collapse\"]')"  # 3.6.0.0 R0a: a drawer's close
        if c.js(f"!!{strip}"):
            c.click_on(strip)
    time.sleep(0.6)
    pair = "[...document.querySelectorAll('[data-testid=\"conv-pair\"]')].find((p) => p.textContent.includes('researcher'))"
    c.wait(f"!!{pair}", 5)
    c.js(f"{pair}.scrollIntoView({{block: 'nearest'}}); 1")
    c.click_on(pair)
    c.mouse("mouseMoved", 4, 4)
    time.sleep(1.0)
    guard_page(c, "studio-talk")
    return c.shot(png)
