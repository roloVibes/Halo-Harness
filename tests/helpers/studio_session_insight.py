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
    """Follow on again: the scroller at its newest line. Setting scrollTop fires no scroll event when the scroller
    already sits at its (new) bottom -- after the tool row closed, on the Linux runner (884ff0e) -- so the event is
    sent by hand, and the Follow pill is the fallback."""
    c.js(f"{SCROLL}.scrollTop = {SCROLL}.scrollHeight; {SCROLL}.dispatchEvent(new Event('scroll')); 1")
    try:
        c.wait(f"{COL}.dataset.follow === 'true'", 10)
    except TimeoutError:
        pill = f"{COL}.querySelector('[data-testid=\"session-live-follow\"]')"
        c.click_on(pill)
        c.wait(f"{COL}.dataset.follow === 'true'", 10)


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


def bang_stop(c, lv) -> dict:
    """3.6.0.17 N2: a running `!` command's row (the Controller names its call `inline_...`) carries its own Stop; a
    model's Bash row has none. A click asks the session's `interrupt` (recorded and answered at Studio's door to the
    session; tests/test_studio_prompt.py's Stop step ends a real `!` through the same stopBang), opens nothing, and when the result lands the Stop is gone while the row's first line keeps its height and
    the elapsed time its place. A step that fails is named in `bang_error`; the run goes on to the next steps."""
    out: dict = {}
    try:
        _bang(c, lv, out)
    except Exception as e:  # the test names the step and shows what it saw so far
        out["bang_error"] = f"{type(e).__name__}: {e}"[:300]
    return out


def _bang(c, lv, out: dict) -> None:
    from halo_harness.studio import sessions_api as S
    stop, calls, orig = "[data-testid=\"session-live-bang-stop\"]", [], S._client
    out["sid"] = lv.sid
    mine = f"{LINES}.filter((l) => l.dataset.kind === 'tool' && l.dataset.key === '{lv.key('main')}')"
    lv.tool("main", "Bash", "toolu_1")
    c.wait(f"{mine}.length >= 1", 10)
    out["model_row_stops"] = c.js(f"{mine}.pop().querySelectorAll('{stop}').length")
    lv.result("main", "toolu_1", "ok")
    n = c.js(f"{mine}.length")
    lv.tool("main", "Bash", "inline_abc123")
    row = f"{mine}[{n}]"
    out["bang_stop"] = c.wait(f"{mine}.length > {n} && {row}.querySelector('{stop}') && "
                              f"[{row}.querySelector('{stop}').textContent, {row}.querySelector('{stop}').title]", 10)
    c.wait(f"/^[1-9]/.test({row}.querySelector('[data-testid=\"session-live-elapsed\"]').textContent)", 10)  # a time to keep
    geo = (f"(() => {{ const l = {row}, h = l.querySelector('[data-testid=\"session-live-tool\"]').getBoundingClientRect(); "
           "const r = (s) => { const e = l.querySelector(s); if (!e) return null; const b = e.getBoundingClientRect(); "
           "return {top: b.top - h.top, bottom: b.bottom - h.top, right: b.right - h.left, height: b.height}; }; "
           f"return {{runs: r('.slv-runs'), elapsed: r('[data-testid=\"session-live-elapsed\"]'), stop: r('{stop}')}}; }})()")

    class Rec:  # Studio's door to the session: the call is recorded and answered here, the rig's session left alone
        def __init__(self, entry, timeout):
            self.sid = str(entry.get("session_id") or "")

        def call(self, cmd, **fields):
            calls.append([self.sid, cmd])
            return {"ok": True}

        def close(self):
            pass
    S._client = Rec
    try:
        c.js(f"{row}.scrollIntoView({{block: 'center'}}); 1")
        c.click_on(f"{row}.querySelector('{stop}')")
        for _ in range(300):  # the click's POST reaches the session's door (bounded: slow runners)
            if calls:
                break
            time.sleep(0.1)
    finally:
        S._client = orig
    out["bang_calls"] = calls
    out["bang_opened"] = c.js(f"!!({row}.querySelector('.slv-tool').dataset.open || {row}.querySelector('[data-testid=\"session-live-full\"]'))")
    out["bang_running"] = c.js(geo)
    lv.result("main", "inline_abc123", "slept")
    c.wait(f"!{row}.querySelector('{stop}') && !!{row}.querySelector('[data-testid=\"session-live-result\"]')", 10)
    out["bang_ended"] = c.js(geo)
    back_to_bottom(c)
