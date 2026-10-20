"""tests.helpers.studio_session_insight -- Halo 3.1.7.0 R1 "Session has what
Fleet has": the Live column's Fleet columns and its tool rows' insight, as a
step of tests/helpers/studio_session_live.py's `live` run (headless Chrome on
the driver base, over tests/helpers/studio_live_rig.py's scripted frames):

* every line leads with Fleet's time (HH:MM:SS) and KIND: a tool row (TOOL,
  reading "runs Bash" + the target), a text row (TEXT), a state row (STATE);
* under 440 px the time, the kind and the tag share one row and the body runs
  full width under them (the container query of the Activity log): never a
  column of single letters;
* a click on a landed tool row opens its whole result inline, a second click
  closes it.

No model is called."""
from __future__ import annotations

import re
import time

COL = "document.querySelector('[data-testid=\"session-live-detail\"]')"
LINES = "[...document.querySelectorAll('[data-testid=\"session-live-line\"]')]"
SCROLL = "document.querySelector('[data-testid=\"session-live-scroll\"]')"
CLOCK = re.compile(r"^\d\d:\d\d:\d\d$")


def cols(c, line: str) -> list:
    """[time, KIND, agent name, body text] of the line `line` evaluates to."""
    return c.js(f"(() => {{ const l = {line}; return l ? [l.querySelector('[data-testid=\"session-live-time\"]').textContent, "
                "l.querySelector('[data-testid=\"session-live-kind\"]').textContent, l.querySelector('.slv-name').textContent, "
                "l.querySelector('.slv-body').textContent] : null; })()") or []


def stacked(c, line: str) -> dict:
    """Where the time, the kind, the tag and the body of `line` sit (their tops, the body's width)."""
    return c.js(f"(() => {{ const l = {line}; const r = (s) => l.querySelector(s).getBoundingClientRect(); "
                "const t = r('[data-testid=\"session-live-time\"]'), k = r('[data-testid=\"session-live-kind\"]'), g = r('.slv-who'), b = r('.slv-body'); "
                "return {time: Math.round(t.top), kind: Math.round(k.top), tag: Math.round(g.top), tag_bottom: Math.round(g.bottom), body: Math.round(b.top), "
                "body_w: Math.round(b.width), body_h: Math.round(b.height)}; })()") or {}


def back_to_bottom(c) -> None:
    """Follow on again: the scroller at its newest line."""
    c.js(f"{SCROLL}.scrollTop = {SCROLL}.scrollHeight; 1")
    c.wait(f"{COL}.dataset.follow === 'true'", 5)


def columns(c, lv, tool: str) -> dict:
    """The columns on a tool, a text and a state row; the narrow layout; the tool row's whole result."""
    out: dict = {}
    out["cols_tool"] = cols(c, tool)
    out["tool_reads"] = c.js(f"[{tool}.querySelector('.slv-runs').textContent, {tool}.querySelector('.slv-tool-name').textContent].join(' ')")
    out["cols_text"] = cols(c, f"{LINES}.find((l) => l.textContent.includes('ALPHA'))")
    lv.state("tester", state="paused")
    state = f"{LINES}.filter((l) => l.dataset.kind === 'state' && l.dataset.key === '{lv.key('tester')}').pop()"
    c.wait(f"!!{state}", 10)
    out["cols_state"] = cols(c, state)
    lv.state("tester", state="running")
    out["clock_ok"] = all(CLOCK.match(str((x or [""])[0])) for x in (out["cols_tool"], out["cols_text"], out["cols_state"]))
    out["wide"] = stacked(c, tool)
    c.js(f"{SCROLL}.style.width = '400px'; 1")  # the column under 440 px: Fleet's container query takes over
    time.sleep(0.3)
    out["narrow"] = stacked(c, tool)
    c.js(f"{SCROLL}.style.width = ''; 1")
    head = f"{tool}.querySelector('[data-testid=\"session-live-tool\"]')"
    c.js(f"{tool}.scrollIntoView({{block: 'center'}}); 1")
    out["tool_more"] = c.js(f"{tool}.querySelector('.slv-tool').dataset.more === 'true'")
    c.click_on(head, 0.3, 0.3)
    out["full"] = c.wait(f"{tool}.querySelector('[data-testid=\"session-live-full\"]')?.textContent", 5)
    c.click_on(head, 0.3, 0.3)
    out["full_closed"] = c.wait(f"!{tool}.querySelector('[data-testid=\"session-live-full\"]') && 'closed'", 5) or False
    back_to_bottom(c)
    return out
