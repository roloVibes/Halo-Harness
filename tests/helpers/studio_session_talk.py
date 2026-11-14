"""tests.helpers.studio_session_talk -- the TALK steps of tests/helpers/studio_session_think.py `talk` (3.3.16.2
"agents talking"): TALK rows with both tags and the reason; the map's edge lights from the speaker to the listener; a
hand-back is one row (no OUT beside it); Conversations is not open on load, the "+" menu adds it, it lists the pair,
shows the thread, a bubble's click scrolls Live to its row, "show in Live" narrows Live to the pair. No model is called."""
from __future__ import annotations

import time

from tests.helpers.studio_session_think import BODY, COL, LINES, of_kind, overflow

CONV = "document.querySelector('[data-testid=\"conv-panel\"]')"


def talk(c, lv) -> dict:
    out: dict = {}
    main, res = lv.key("main"), lv.key("researcher")
    out["conv_on_load"] = c.js(f"!!{CONV}")
    lv.talk("main", "researcher", "Read the pricing notes and tell me when the discount applies, before or after tax.", "task", mid="tk-1")
    edge = "document.querySelector('[data-testid=\"session-map\"] [data-testid=\"fleet-lit-edge\"][data-kind=\"talk\"]')"
    out["edge"] = c.wait(f"{edge} && [{edge}.dataset.from === '{main}', {edge}.dataset.to === '{res}', !!{edge}.getAttribute('marker-end')]", 5)
    row = f"{of_kind('talk', main)}[0]"
    c.wait(f"!!{row}", 10)
    out["talk_row"] = c.js(f"[{row}.querySelector('[data-testid=\"session-live-kind\"]').textContent, {row}.querySelector('.slv-name').textContent, "
                           f"{row}.querySelector('[data-testid=\"live-talk-to\"]').textContent, {row}.querySelector('[data-testid=\"live-talk-why\"]').textContent]")
    lv.talk("researcher", "main", "The discount applies before tax: the notes say so twice.", "hand-back", mid="tk-2", re="tk-1")
    lv.talk("main", "docs", "Summarise the attached PDF in three lines.", "square", mid="tk-3", square="media")
    c.wait(f"{of_kind('talk')}.length >= 3", 10)
    lv.state("researcher", state="done", last_text="The discount applies before tax: the notes say so twice.")
    time.sleep(1.2)
    out["hand_back"] = c.js(f"{of_kind('talk', res)}.map((l) => [{BODY}.querySelector('[data-testid=\"live-talk-why\"]').textContent, "
                            f"!!{BODY}.querySelector('.slv-out')])")
    out["outs_for_res"] = c.js(f"{of_kind('output', res)}.length")
    out["square_why"] = c.js(f"{of_kind('talk', main)}.map((l) => l.querySelector('[data-testid=\"live-talk-why\"]').textContent)")
    out["overflow"] = overflow(c, "talk")
    return out


def conversations(c, lv) -> dict:
    out: dict = {}
    item = "document.querySelector('.section-view:not([hidden]) [data-testid=\"viewbar-btn\"][data-panel=\"session-conversations\"]')"  # 3.6.0.0 R0a: the view bar
    c.wait(f"!!{item}", 5)
    c.click_on(item)
    c.wait(f"!!{CONV}", 10)
    pairs = "[...document.querySelectorAll('[data-testid=\"conv-pair\"]')]"
    out["pairs"] = c.wait(f"{pairs}.length >= 2 && {pairs}.map((p) => p.querySelector('.conv-pair-names').textContent)", 5)
    first = f"{pairs}.find((p) => p.textContent.includes('researcher'))"
    c.js(f"{first}.scrollIntoView({{block: 'center'}}); 1")
    out["conv_rect"] = c.rect(CONV)
    c.click_on(first)
    c.wait(f"{first}.dataset.on === 'true'", 5)
    bubbles = "[...document.querySelectorAll('[data-testid=\"conv-bubble\"]')]"
    out["bubbles"] = c.wait(f"{bubbles}.length === 2 && {bubbles}.map((b) => [b.dataset.side, b.querySelector('.conv-why').textContent, !!b.dataset.nested])", 5)
    n = c.js(f"{bubbles}[0].dataset.n")
    for i in range(30):
        lv.tool(("tester", "docs")[i % 2], "Read", f"cv-fill-{i}")
    c.wait(f"{of_kind('tool')}.length >= 30", 15)
    scroll = "document.querySelector('[data-testid=\"session-live-scroll\"]')"
    c.js(f"{scroll}.scrollTop = {scroll}.scrollHeight; 1")
    time.sleep(0.3)
    target = f"document.querySelector('[data-testid=\"session-live-scroll\"] [data-n=\"{n}\"]')"
    vis = (f"(() => {{ const r = {target}.getBoundingClientRect(), s = {scroll}.getBoundingClientRect(); "
           "return r.bottom > s.top && r.top < s.bottom; })()")
    out["away"] = not c.js(vis)
    c.js(f"{bubbles}[0].scrollIntoView({{block: 'center'}}); 1")
    c.click_on(f"{bubbles}[0]")
    out["bubble_scrolls"] = c.wait(vis, 5)
    show = "document.querySelector('[data-testid=\"conv-show-live\"]')"
    c.js(f"{show}.scrollIntoView({{block: 'center'}}); 1")
    c.click_on(show)
    out["pair_chip"] = c.wait("document.querySelector('[data-testid=\"live-pair-chip\"]')?.textContent", 5)
    out["pair_rows"] = c.js(f"{LINES}.map((l) => {BODY}.dataset.kind)")
    chip = "document.querySelector('[data-testid=\"live-pair-chip\"]')"
    c.js(f"{chip}.scrollIntoView({{block: 'center'}}); 1")
    out["chip_hit"] = c.js(f"(() => {{ const r = {chip}.getBoundingClientRect(); const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !!e && {chip}.contains(e); }})()")
    c.click_on(chip)
    c.wait(f"!document.querySelector('[data-testid=\"live-pair-chip\"]') && {LINES}.length > 10", 5)
    return out
