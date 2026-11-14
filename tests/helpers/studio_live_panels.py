"""tests.helpers.studio_live_panels -- the Studio live panels of Halo 3.0.5.0 round R4, driven through real clicks and
keys in headless Chrome over the DevTools protocol, over tests/helpers/studio_session_rig.py (this harness's real
session, the finished past session PAST_SID). Run through tests/helpers/studio_live.py:

    python -m tests.helpers.studio_live panels

* Activity (Live's optional panel, the header's "+") draws one lane per live agent, hover says who, a click on a
  lane selects that agent (the inspector says it);
* Record on the agent inspector and its download, Take over's dialog;
* the replay: the reviewer card's history row "replay" opens the session on Agents -> Live with the scrubber
  (3.4.1.0 R1), the scrub draws the reviewer only while it existed, Now goes back to what runs now.
"""
from __future__ import annotations

import time

from tests.helpers.studio_live import DETAIL, LIVE_CARDS, NODE, card, card_click
from tests.helpers.studio_header_menus import plus

LIVE = ("queued", "running", "waiting", "paused")


def seen(c, expr: str) -> None:
    c.js(f"(() => {{ const el = {expr}; if (el) el.scrollIntoView({{block: 'center', inline: 'nearest'}}); return !!el; }})()")
    time.sleep(0.2)


def open_strip(c, pid: str) -> None:
    """3.1.4.0 R1: Health, Capabilities, Agent and Mission start as title strips down the right edge; the one
    click that opens one is the chevron on its title bar ("Open the panel"). A panel already open stays as it is."""
    btn = f"document.querySelector('.ws-cell[data-panel=\"{pid}\"] .panel-bar button[aria-label=\"Open\"]')"
    c.wait(f"!!document.querySelector('.ws-cell[data-panel=\"{pid}\"]')", 30)
    if c.js(f"!!{btn}"):
        seen(c, btn)
        c.click_on(btn)
        c.wait(f"!!document.querySelector('.ws-cell[data-panel=\"{pid}\"] .panel-body:not([hidden])')", 10)


def timeline(c, rig, out: dict) -> None:
    lanes = "document.querySelectorAll('[data-testid=\"fleet-lane\"]')"
    live = f"[...document.querySelectorAll('{NODE}')].filter((n) => " + " || ".join(f"n.dataset.state === '{s}'" for s in LIVE) + ").length"
    plus(c, "fleet-activity")  # 3.3.16.0 R2: Live's optional panel
    out["live_nodes"] = c.js(live)
    out["lanes"] = c.wait(f"{lanes}.length === {live} && {lanes}.length", 15)
    out["segs"] = c.js("document.querySelectorAll('[data-testid=\"fleet-lane\"] .ftl-seg').length")
    key_b = rig.key("Research")
    lane = f"document.querySelector('[data-testid=\"fleet-lane\"][data-key=\"{key_b}\"]')"
    seen(c, "document.querySelector('[data-testid=\"fleet-timeline\"]')")
    c.click_on("document.querySelector('[data-testid=\"fleet-span-5\"]')")  # 5 minutes: the young bars are wider
    time.sleep(0.3)
    x, y, w, h = c.rect(f"{lane}.querySelector('.ftl-seg')")
    out["hover_on"] = c.js(f"document.elementFromPoint({x + w / 2}, {y + h / 2})?.getAttribute('class')")
    c.mouse("mouseMoved", x + w / 2, y + h / 2)
    tip = "document.querySelector('[data-testid=\"fleet-timeline-tip\"]')?.textContent"
    try:
        out["tip"] = c.wait(tip, 10)
    except TimeoutError:  # wait raises, so the fallback below never ran before 6652a9b
        out["tip"] = None
    if not out["tip"]:
        # the Linux runner's pointer path misses the segment at times (e7c30a5, 6652a9b): the tip is the
        # segment's own hover handler, so send it the pointer events by hand; the message keeps what the pointer hit
        seg = f"{lane}.querySelector('.ftl-seg')"
        out["tip_pointer_hit"] = out.get("hover_on")
        c.js(f"for (const t of ['pointerenter', 'mouseenter', 'pointermove', 'mousemove', 'mouseover']) "
             f"{seg}.dispatchEvent(new MouseEvent(t, {{bubbles: true, clientX: {x + w / 2}, clientY: {y + h / 2}}})); 1")
        out["tip"] = c.wait(tip, 10)
        out["tip_by"] = "element"
    c.click(x + w / 2, y + h / 2)
    out["lane_selects"] = c.wait(f"{DETAIL}?.dataset.key === '{key_b}' && 'researcher'", 10)


def replay(c, rig, out: dict) -> None:
    """3.0.7.0 R2; 3.4.1.0 R1 "Time": the reviewer card's history row "replay" opens the session on Agents -> Live with
    the scrubber under the canvas (the Cast bar went); the scrub draws who existed and each state at that moment."""
    bar = "document.querySelector('[data-testid=\"replay-bar\"]')"
    live_map = "document.querySelector('[data-testid=\"roles-live-map\"]')"
    c.go(rig.url("roles"))
    c.wait(f"{LIVE_CARDS}.length >= 3", 30)
    card_click(c, card("reviewer"))
    c.click_on("document.querySelector('[data-testid=\"roles-live-tab\"]')")
    out["history_replay"] = c.wait("document.querySelectorAll('[data-testid=\"roles-history-replay\"]').length", 15)
    c.js("document.querySelector('[data-testid=\"roles-history-replay\"]').scrollIntoView({block: 'center'}); 1")  # 3.1.4.0 R4: below the MODEL strip
    c.click_on("document.querySelector('[data-testid=\"roles-history-replay\"]')")
    c.wait(f"{bar}?.dataset.mode === 'replay' && {live_map}?.dataset.replay === 'true'", 20)
    out["bar"] = c.wait(f"{bar}?.querySelector('.replay-title')?.textContent", 15)
    from tests.helpers.studio_session_parts import PAST_REVIEWER
    node = f"document.querySelector('[data-testid=\"roles-live-node\"][data-agent=\"{PAST_REVIEWER}\"]')"
    rev = f"(() => {{ const n = {node}; return n ? (n.dataset.state || 'drawn') : 'none'; }})()"

    def scrub(frac: float) -> dict:
        v = c.js(f"Math.round({bar}.querySelector('[data-testid=\"replay-scrub\"]').max * {frac})")
        c.js(f"""(() => {{ const r = {bar}.querySelector('[data-testid="replay-scrub"]');
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(r, '{v}');
          r.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()""")
        c.wait(f"{bar}.dataset.t10 === '{v}'", 10)
        return {"t": c.js(f"{bar}.dataset.t"), "lit": c.js(f"{bar}.dataset.lit"), "reviewer": c.js(rev), "playing": c.js(f"{bar}.dataset.playing === 'true'")}
    out["early"], out["mid"], out["end"] = scrub(0.02), scrub(0.5), scrub(1.0)
    out["ignores_live"] = c.js(f"{live_map}.dataset.replay === 'true' && !document.querySelector('[data-testid=\"roles-live-node\"][data-state=\"waiting\"]')")
    c.click_on("document.querySelector('[data-testid=\"replay-close\"]')")
    out["closed"] = c.wait(f"!{live_map}?.dataset.replay && document.querySelectorAll('[data-testid=\"roles-live-node\"]').length > 0 && 'live again'", 15)


def extras(c, rig, out: dict) -> None:
    """Record the researcher and download the file; Take over opens its dialog."""
    from tests.helpers.studio_live import node, wait_node
    wait_node(c, "researcher")
    seen(c, node("researcher"))
    c.click_on(node("researcher"))
    c.wait(f"{DETAIL}?.dataset.key === '{rig.key('Research')}'", 10)
    rec = "document.querySelector('[data-testid=\"fleet-record\"]')"
    seen(c, rec)  # the agent inspector scrolls: its extras sit under the stream
    x, y, w, h = c.rect(rec)
    out["record_hit"] = c.js(f"document.elementFromPoint({x + w / 2}, {y + h / 2})?.closest('[data-testid]')?.dataset.testid")
    c.click_on(rec)
    out["recording"] = c.wait("document.querySelector('[data-testid=\"fleet-recording\"] .dialog-title')?.textContent", 20)
    try:  # the file is fetched and handed to the browser; the test browser keeps no copy anywhere
        c.call("Page.setDownloadBehavior", behavior="deny")
    except RuntimeError:
        pass
    c.click_on("document.querySelector('[data-testid=\"fleet-recording-download\"]')")
    out["downloaded"] = c.wait("[...document.querySelectorAll('.toast')].map((t) => t.textContent).find((t) => t.startsWith('Saved '))", 15)
    c.key("Escape")
    c.wait("!document.querySelector('[data-testid=\"fleet-recording\"]')", 10)
    c.click_on("document.querySelector('[data-testid=\"fleet-takeover-open\"]')")
    out["takeover"] = c.wait("document.querySelector('[data-testid=\"fleet-takeover\"] .dialog-title')?.textContent", 10)
    c.key("Escape")
    c.wait("!document.querySelector('[data-testid=\"fleet-takeover\"]')", 10)


def panels(c, rig) -> dict:
    out: dict = {}
    c.go(rig.url("agents"))
    c.wait(f"document.querySelectorAll('{NODE}').length === 3 && !!document.querySelector('[data-testid=\"agents-attention\"]')", 30)
    for step in (lambda: timeline(c, rig, out), lambda: extras(c, rig, out), lambda: replay(c, rig, out)):
        try:
            step()
        except Exception as e:  # one step's miss is reported, the others still run
            out.setdefault("errors", []).append(f"{type(e).__name__}: {e}"[:400])
    return out
