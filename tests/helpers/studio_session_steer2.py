"""tests.helpers.studio_session_steer2 -- the second half of
tests/helpers/studio_session_steer.py's `steer` run (Halo 3.1.7.0 R1): the
timeline strip in the Live column (one lane per live agent of this session,
a lane click pins it, the agent pick follows), the kind pick hiding the text
rows, a finished agent's Steer box disabled with one line, Stop asking first
(the confirm dialog, cancelled), Pause reaching main's command route, and in
Fleet the map chip opening the Agent panel's Steer box. No model is called."""
from __future__ import annotations

import time

from tests.helpers.studio_session_steer import AGENT_PICK, AREA, BOX, COL, KIND_PICK, LINES, STEER_CLOSE, STEER_OPEN, box, clear_field, pick

LIVE = ("queued", "running", "waiting", "paused")
STRIP = f"{COL}.querySelector('[data-testid=\"session-live-timeline\"]')"
SCROLL = f"{COL}.querySelector('[data-testid=\"session-live-scroll\"]')"
FOOT = f"{COL}.querySelector('.slv-foot')"
DRAFT = "DRAFT not sent yet"


def opened(c, rig) -> dict:
    c.go(rig.url("session"))
    c.wait(f"!!{COL} && document.querySelectorAll('[data-testid=\"session-map\"] :is([data-testid=\"session-lit-box\"], [data-testid=\"session-map-row\"])').length >= 3", 40)  # 3.6.0.2 R15: boxes and the rows in them
    time.sleep(0.8)
    return {"opened": True}


def steer_off(c, lv) -> dict:
    """3.6.0.11 (the owner: "Keep it off as default, open it with the steer button, and add the ability to close it"):
    no box at load and the foot takes no room; the header's Steer opens it on main with the keyboard in it; x closes it
    and the rows take the room; the text typed and not sent is there on the next open; Esc in the field closes it."""
    out: dict = {"main_key": lv.key("main")}
    c.wait(f"!!{STEER_OPEN} && !{STEER_OPEN}.disabled && 1", 30)
    out["at_load"] = c.js(f"({{box: !!{BOX}, data_steer: {COL}.hasAttribute('data-steer'), foot_h: {FOOT}.getBoundingClientRect().height, "
                          f"pressed: {STEER_OPEN}.getAttribute('aria-pressed'), label: {STEER_OPEN}.textContent.trim(), title: {STEER_OPEN}.title}})")
    c.click_on(STEER_OPEN)
    try:
        c.wait(f"!!{AREA} && document.activeElement === {AREA} && 1", 10)
    except TimeoutError:
        pass  # the read below says what was there
    out["opened"] = {**box(c), "data_steer": c.js(f"{COL}.dataset.steer || ''"), "pressed": c.js(f"{STEER_OPEN}.getAttribute('aria-pressed')")}
    clear_field(c)
    c.type_text(DRAFT)
    c.wait(f"{AREA}.value === '{DRAFT}' && 1", 5)
    h0 = c.js(f"{SCROLL}.clientHeight") or 0
    out["close_words"] = c.js(f"[{STEER_CLOSE}.getAttribute('aria-label'), {STEER_CLOSE}.title]")
    c.click_on(STEER_CLOSE)
    out["closed"] = c.wait(f"!{BOX} && !{COL}.hasAttribute('data-steer') && {STEER_OPEN}.getAttribute('aria-pressed') === 'false' && 'closed'", 5) or False
    try:  # the rows take the foot's room once the grid has laid out again
        c.wait(f"{SCROLL}.clientHeight - {h0} >= 100 && 1", 5)
    except TimeoutError:
        pass
    out["grew"] = (c.js(f"{SCROLL}.clientHeight") or 0) - h0
    c.click_on(STEER_OPEN)
    c.wait(f"!!{AREA} && document.activeElement === {AREA} && 1", 10)
    out["draft_back"] = c.js(f"{AREA}.value")
    c.key("Escape")
    out["esc_closed"] = c.wait(f"!{BOX} && 'closed'", 5) or False
    return out


def strip(c, lv) -> dict:
    """The strip's lanes are this session's live agents; a click on the tester's lane pins it."""
    out: dict = {}
    pick(c, AGENT_PICK, "")
    c.wait(f"!{COL}.dataset.pinned", 5)
    here = f"{lv.hid}|{lv.sid}|"
    # 3.6.0.0 R5: the old tree's nodes went; the session's live agents come from the rig's own record of them
    live = sorted(lv.key(n) for n in lv.live_names()) if hasattr(lv, "live_names") else None
    lanes = f"[...{STRIP}.querySelectorAll('[data-testid=\"fleet-lane\"]')].map((l) => l.dataset.key).sort()"
    c.wait(f"{lanes}.length >= 6 && {lanes}.every((k) => k.startsWith('{here}'))", 15)
    out["lanes"] = c.js(lanes)
    out["live_nodes"] = live if live is not None else out["lanes"]
    out["spans"] = c.js(f"[...{STRIP}.querySelectorAll('.segmented button')].map((b) => b.textContent)")
    tester = lv.key("tester")
    lane = f"{STRIP}.querySelector('[data-testid=\"fleet-lane\"][data-key=\"{tester}\"] .ftl-hit')"
    c.click_on(lane, 0.6, 0.5)
    out["lane_pinned"] = c.wait(f"{COL}.dataset.pinned === '{tester}' && {COL}.dataset.pinned", 5)
    out["lane_lit"] = c.js(f"!!{STRIP}.querySelector('[data-testid=\"fleet-lane\"][data-key=\"{tester}\"][data-selected]')")
    out["pick_after_lane"] = c.js(f"{AGENT_PICK}.value")
    out["tester_key"] = tester
    out["box_after_lane"] = box(c).get("key")
    out["pick_rows"] = c.js(f"[...{AGENT_PICK}.options].map((o) => o.value)")
    pick(c, AGENT_PICK, "")
    c.wait(f"!{COL}.dataset.pinned", 5)
    return out


def kinds(c, lv) -> dict:
    """With text lines in the column, the kind pick "tools" leaves only tool rows (and your own steers); "every kind" brings them back."""
    out: dict = {}
    lv.say("implementer", "DELTA writes the change. ")
    lv.tool("tester", "Read", "kind-t1", "tests/test_basket.py")
    c.wait(f"{LINES}.some((l) => l.textContent.includes('DELTA')) && {LINES}.some((l) => l.textContent.includes('tests/test_basket.py'))", 10)
    count = f"(() => {{ const k = {{}}; {LINES}.forEach((l) => k[l.dataset.kind] = (k[l.dataset.kind] || 0) + 1); return k; }})()"
    out["kinds_before"] = c.js(count)
    pick(c, KIND_PICK, "tool")
    c.wait(f"{COL}.dataset.kind === 'tool' && !{LINES}.some((l) => l.dataset.kind === 'text')", 5)
    out["kinds_tools"] = c.js(count)
    pick(c, KIND_PICK, "")
    c.wait(f"!{COL}.dataset.kind && {LINES}.some((l) => l.dataset.kind === 'text')", 5)
    out["kinds_after"] = c.js(count)
    return out


def done_box(c, lv) -> dict:
    """The docs agent finishes; picked, its box is disabled and says why in one line; Pause and Stop with it."""
    out: dict = {}
    docs = lv.key("docs")
    lv.state("docs", state="done", last_text="CHANGES.md: the discount applies before tax")
    c.wait(f"document.querySelector('[data-testid=\"session-map-row\"][data-row=\"{docs.split('|')[-1]}\"]')?.dataset.state === 'done'", 10)  # R5: the lit map (3.6.0.2 R15: its row in main's box)
    pick(c, AGENT_PICK, docs)
    c.wait(f"{BOX}.dataset.key === '{docs}'", 5)
    out["done_box"] = box(c)
    out["done_disabled"] = c.js(f"{BOX}.dataset.disabled === 'true'")
    pick(c, AGENT_PICK, "")
    out["back_to_main"] = c.wait(f"!{COL}.dataset.pinned && {BOX}.dataset.key === '{lv.key('main')}' && 'main'", 5) and box(c)
    return out


def stop(c, lv, sent: list) -> dict:
    """Stop beside the box asks first: the confirm dialog names main; Cancel sends nothing."""
    out: dict = {}
    # main's liveness in the store comes from the rig's real session row. On the Linux runner every real agent
    # read "done" seconds after the first steer: the steer forwarded into the held children crashed them
    # (providers/stream.py, fixed in 3.1.7.0 R3) and main finished with them. Fixed at the root; this frame
    # stays as what a real session sends with every step, and the button's own reason is kept for the message
    lv.state("main", state="running", current="thinking")
    stop_btn = f"{BOX}.querySelector('[data-testid=\"session-live-stop\"]')"
    out["stop_why"] = c.js(f"[{BOX}.dataset.key, {BOX}.dataset.disabled || '', {stop_btn}?.title || '', {stop_btn}?.disabled]")
    # the foot of the column can sit below the panel's visible area on the Linux runner's layout: a click
    # on an off-screen button lands nowhere (the Linux run for the merge lost it), so bring it into view
    c.js(f"{BOX}.querySelector('[data-testid=\"session-live-stop\"]').scrollIntoView({{block: 'center'}}); 1")
    # Stop is disabled (and askStop opens nothing) until the box's agent is in the fleet store: on the Linux
    # runner that frame can land after the test reaches this step (the click on a disabled button did nothing
    # in two runs), so wait for the live button first and keep what the box said for the failure message
    out["stop_ready"] = c.wait(f"(() => {{ const b = {BOX}.querySelector('[data-testid=\"session-live-stop\"]'); "
                               f"return b && !b.disabled && !{BOX}.dataset.disabled && ({BOX}.dataset.key || 'no key'); }})()", 30)
    c.click_on(f"{BOX}.querySelector('[data-testid=\"session-live-stop\"]')")
    out["stop_dialog"] = c.wait("document.querySelector('[data-testid=\"fleet-confirm\"]')?.textContent", 15)
    cancel = "[...document.querySelectorAll('[data-testid=\"fleet-confirm\"] button')].find((b) => b.textContent.trim() === 'Cancel')"
    c.click_on(cancel)
    out["stop_cancelled"] = c.wait("!document.querySelector('[data-testid=\"fleet-confirm\"]') && 'closed'", 5) or False
    time.sleep(0.5)
    out["stop_sent"] = [d["cmd"] for d in sent if d["cmd"] == "agent_stop"]
    return out


def pause(c, lv, sent: list) -> dict:
    """Pause beside the box reaches main's command route (main holds at its next step; the rig resumes it)."""
    from tests.helpers.session_rig import wait_for
    out: dict = {}
    c.js(f"{BOX}.querySelector('[data-testid=\"session-live-pause\"]').scrollIntoView({{block: 'center'}}); 1")
    c.wait(f"!{BOX}.querySelector('[data-testid=\"session-live-pause\"]').disabled && !{BOX}.dataset.disabled", 30)
    c.click_on(f"{BOX}.querySelector('[data-testid=\"session-live-pause\"]')")
    got = wait_for(lambda: [d for d in sent if d["cmd"] == "pause"], 15) or [{}]
    out["pause_route"] = {"sid": got[-1].get("sid"), "agent_id": (got[-1].get("fields") or {}).get("agent_id"), "status": got[-1].get("status")}
    out["pause_ack"] = c.wait("document.querySelector('.toasts')?.textContent.includes('Paused') && 'paused'", 15)
    from halo_harness.studio import live_agents_api
    live_agents_api.forward(lv.sid, "resume", {"agent_id": "main", **live_agents_api.caller()})
    return out
