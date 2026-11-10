"""tests.helpers.studio_fleet_panels -- the Studio Fleet panels of Halo 3.0.5.0
round R4, driven through real clicks and keys in headless Chrome over the
DevTools protocol, over tests/helpers/studio_fleet_rig.py (this harness's
real session, the member `kali@lab` with an open approval card, the finished
past session PAST_SID). Run through tests/helpers/studio_fleet.py:

    python -m tests.helpers.studio_fleet panels

* 3.3.16.0 R2 "the Fleet fold": ?mode=fleet is Agents -> Live on the fleet (the tree, the Attention chip, the
  inspector strip; the Fleet section and its nine panels went); the attention queue is the chip's panel, its count
  the chip's (amber) and the glance's "waits on you" line; A on the approval row answers it on the member (and the
  row leaves the queue);
* Activity (Live's optional panel, the header's "+") draws one lane per live agent, hover says who, a click on a
  lane selects that agent (the inspector says it);
* the digest card after a simulated absence (halo.fleet.lastSeen two hours
  back, then the tab regains focus): the Agents icon's dot, a click on it opens
  Live on the fleet with the card at the top of the inspector's glance, and Dismiss;
* the replay: the reviewer card's history row "replay" opens the scrub bar on
  the Roles canvas, the scrub lights the reviewer only while it worked, x
  goes back to what runs now;
* a conflict (two harnesses editing shop/basket.py): the amber edge on
  Live, the session nodes' chips, the attention row; each session node's git chips;
* Record on the agent inspector and its download, Take over's dialog, the member machine's summary's Message
  (People's row) reaching the member's owner as a `note`.
"""
from __future__ import annotations

import time

from tests.helpers.studio_fleet import CANVAS, DETAIL, LIVE_CARDS, NODE, card, card_click
from tests.helpers.studio_header_menus import plus

HOMES = ("roles-live-map", "agents-attention", "roles-inspector")  # 3.3.16.0 R2: Live, the chip, the inspector strip
CHIP = "document.querySelector('[data-testid=\"agents-attention\"]')"
ROW = "document.querySelector('[data-testid=\"fleet-attn-row\"][data-kind=\"{}\"]')"
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


def attention(c, rig, out: dict) -> None:
    from tests.helpers.studio_fleet_member import APPROVAL_ID
    from tests.helpers.studio_fleet_rig import wait_for
    out["panels"] = c.js("[" + ",".join(f"document.querySelectorAll('[data-testid=\"{p}\"]').length" for p in HOMES) + "]")
    out["closed_on_load"] = c.js("!document.querySelector('[data-testid=\"fleet-attention\"]')")
    c.click_on(CHIP)
    out["abouts"] = c.wait("document.querySelector('[data-panel=\"fleet-attention\"] .panel-title')?.textContent", 10)
    out["attn_kinds"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-attn-row\"][data-kind=\"approval\"]').length && [...document.querySelectorAll('[data-testid=\"fleet-attn-row\"]')].map((r) => r.dataset.kind)", 30)
    out["attn_rows"] = len(out["attn_kinds"] or [])
    out["status_attn"] = c.wait(f"{CHIP}.dataset.count === '2' && [{CHIP}.textContent, {CHIP}.dataset.tone]", 15)
    open_strip(c, "roles-inspector")  # the count's other home: the glance's line (the inspector, a strip on load)
    out["rail_attn"] = c.wait("document.querySelector('[data-testid=\"live-glance-waiting\"] dd')?.textContent", 15)
    row = ROW.format("approval")
    seen(c, row)
    c.click_on(f"{row}.querySelector('.fat-what')")
    out["approval_selected"] = c.wait(f"{row}?.getAttribute('aria-selected') === 'true' && 'selected'", 10)
    c.key("a")
    got = wait_for(lambda: [d for d in rig.member_cmds if d.get("cmd") == "answer"], 15)
    out["approval_sent"] = (got or [{}])[-1].get("fields")
    out["approval_gone"] = c.wait(f"!{row} && 'gone'", 10)
    out["approval_id"] = APPROVAL_ID


def timeline(c, rig, out: dict) -> None:
    lanes = "document.querySelectorAll('[data-testid=\"fleet-lane\"]')"
    live = f"[...document.querySelectorAll('{NODE}')].filter((n) => " + " || ".join(f"n.dataset.state === '{s}'" for s in LIVE) + ").length"
    c.key("Escape")  # the queue's panel closes (Esc in it) before Activity floats in
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


def digest(c, out: dict) -> None:
    c.js("localStorage.setItem('halo.fleet.lastSeen', String(Date.now() - 2 * 3600 * 1000)); window.dispatchEvent(new Event('focus')); 1")
    out["digest_dot"] = c.wait("!!document.querySelector('.rail [data-tab-id=agents] [data-testid=\"rail-away\"]')", 15)  # 3.3.16.0 R2: the Agents icon's dot
    c.click_on("document.querySelector('.rail [data-testid=section-tab][data-tab-id=agents]')")  # opens Live on the fleet, the glance open
    out["digest"] = c.wait("document.querySelector('[data-testid=\"live-glance\"] [data-testid=\"fleet-digest\"]')?.textContent", 15)
    out["digest_where"] = c.js("document.querySelector('[data-testid=\"fleet-digest\"]')?.dataset.where")
    c.js("document.querySelector('[data-testid=\"fleet-digest-dismiss\"]').scrollIntoView({block: 'center'}); 1")
    c.click_on("document.querySelector('[data-testid=\"fleet-digest-dismiss\"]')")
    out["digest_dismissed"] = c.wait("!document.querySelector('[data-testid=\"fleet-digest\"]') && Date.now() - Number(localStorage.getItem('halo.fleet.lastSeen')) < 60000 && 'dismissed'", 10)
    out["digest_dot_gone"] = c.js("!document.querySelector('[data-testid=\"rail-away\"]')")


def replay(c, rig, out: dict) -> None:
    """3.0.7.0 R2: the replay bar under the React Roles canvas."""
    bar = "document.querySelector('[data-testid=\"replay-bar\"]')"
    c.go(rig.url("roles"))
    c.wait(f"{LIVE_CARDS}.length >= 3", 30)
    card_click(c, card("reviewer"))
    c.click_on("document.querySelector('[data-testid=\"roles-live-tab\"]')")
    out["history_replay"] = c.wait("document.querySelectorAll('[data-testid=\"roles-history-replay\"]').length", 15)
    c.js("document.querySelector('[data-testid=\"roles-history-replay\"]').scrollIntoView({block: 'center'}); 1")  # 3.1.4.0 R4: below the MODEL strip
    c.click_on("document.querySelector('[data-testid=\"roles-history-replay\"]')")
    out["bar"] = c.wait(f"{bar}?.querySelector('.replay-title')?.textContent", 15)
    lit = "(() => { const g = " + card("reviewer") + "; return g ? (g.dataset.live || 'none') : 'no card'; })()"

    def scrub(v: int) -> dict:
        c.js(f"""(() => {{ const r = {bar}.querySelector('[data-testid="replay-scrub"]');
          Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(r, '{v}');
          r.dispatchEvent(new Event('input', {{bubbles: true}})); return 1; }})()""")
        time.sleep(0.4)
        return {"t": c.js(f"{bar}.dataset.t"), "lit": c.js(f"{bar}.dataset.lit"), "reviewer": c.js(lit), "playing": c.js(f"{bar}.dataset.playing === 'true'")}
    out["early"], out["mid"], out["end"] = scrub(20), scrub(500), scrub(1000)
    out["ignores_live"] = c.js(f"{CANVAS}.dataset.replaying === 'true' && !{card('implementer')}.dataset.live")
    c.click_on("document.querySelector('[data-testid=\"replay-close\"]')")
    out["closed"] = c.wait(f"!{bar} && {LIVE_CARDS}.length >= 3 && 'live again'", 15)


def conflict(c, rig, out: dict) -> None:
    from halo_harness.fleet.identity import harness
    from tests.helpers.studio_fleet_member import REVIEWER
    from tests.helpers.studio_fleet_rig import MEMBER, MEMBER_SID
    c.go(rig.url("fleet"))
    c.wait(f"document.querySelectorAll('{NODE}').length === 5", 30)
    a = rig.agent("Implement")
    rig.server.events.publish({"session_id": rig.act.session_id, "harness": harness()["id"], "event": "agent_state", "agent_id": a["agent_id"],
                               "ts": time.time(), "data": {**a, "current": f"Edit: {rig.proj / 'basket.py'}"}})
    rig.hub.state.frames(MEMBER, {"link": "rig-link", "frames": [{"session_id": MEMBER_SID, "event": "agent_state", "agent_id": REVIEWER["agent_id"],
                                                                 "ts": time.time(), "data": {**REVIEWER, "state": "running", "current": "Edit: /home/kali/shop/basket.py"}}]})
    out["conflict_edge"] = c.wait("document.querySelector('[data-testid=\"fleet-conflict-edge\"]')?.dataset.file", 30)
    out["conflict_chips"] = c.js("document.querySelectorAll('[data-testid=\"fleet-conflict-chip\"]').length")
    c.click_on(CHIP)  # the queue (closed on load)
    out["conflict_row"] = c.wait(f"{ROW.format('conflict')}?.querySelector('.fat-what')?.textContent", 15)
    out["git_chips"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-git-chips\"]').length", 10)  # 3.3.16.0 R2: on every session node
    out["edge_by_project"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-conflict-edge\"]').length", 10)
    c.click_on(CHIP)  # the queue closes: it floats over the inspector the next step presses in
    c.wait("!document.querySelector('[data-testid=\"fleet-attention\"]')", 10)


def extras(c, rig, out: dict) -> None:
    """Record the researcher and download the file; Take over opens its dialog; Message reaches the member's owner."""
    from tests.helpers.studio_fleet import node, wait_node
    from tests.helpers.studio_fleet_rig import wait_for
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
    from tests.helpers.studio_fleet_rig import MEMBER
    c.click_on(f"document.querySelector('[data-testid=\"live-machine\"][data-harness=\"{MEMBER}\"]')")  # its summary: People's row
    c.wait("!!document.querySelector('[data-testid=\"machine-summary\"] [data-testid=\"fleet-person-message\"]')", 10)
    seen(c, "document.querySelector('[data-testid=\"fleet-person-message\"]')")
    c.click_on("document.querySelector('[data-testid=\"fleet-person-message\"]')")
    c.wait("!!document.querySelector('[data-testid=\"fleet-message-text\"]')", 10)
    c.click_on("document.querySelector('[data-testid=\"fleet-message-text\"]')")
    c.type_text("lunch in ten")
    c.click_on("document.querySelector('[data-testid=\"fleet-message-send\"]')")
    got = wait_for(lambda: [d for d in rig.member_cmds if d.get("cmd") == "note"], 15)
    out["note"] = (got or [{}])[-1].get("fields", {}).get("text")


def panels(c, rig) -> dict:
    out: dict = {}
    c.go(rig.url("fleet"))
    c.wait(f"document.querySelectorAll('{NODE}').length === 5 && !!document.querySelector('[data-testid=\"agents-attention\"]')", 30)
    for step in (lambda: attention(c, rig, out), lambda: timeline(c, rig, out), lambda: digest(c, out),
                 lambda: replay(c, rig, out), lambda: conflict(c, rig, out), lambda: extras(c, rig, out)):
        try:
            step()
        except Exception as e:  # one step's miss is reported, the others still run
            out.setdefault("errors", []).append(f"{type(e).__name__}: {e}"[:400])
    return out
