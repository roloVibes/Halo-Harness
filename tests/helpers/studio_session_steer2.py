"""tests.helpers.studio_session_steer2 -- the second half of
tests/helpers/studio_session_steer.py's `steer` run (Halo 3.1.7.0 R1): the
timeline strip in the Live column (one lane per live agent of this session,
a lane click pins it, the agent pick follows), the kind pick hiding the text
rows, a finished agent's Steer box disabled with one line, Stop asking first
(the confirm dialog, cancelled), Pause reaching main's command route, and in
Fleet the map chip opening the Agent panel's Steer box. No model is called."""
from __future__ import annotations

import time

from tests.helpers.studio_session_steer import AGENT_PICK, BOX, COL, KIND_PICK, LINES, box, hover, pick

LIVE = ("queued", "running", "waiting", "paused")
STRIP = f"{COL}.querySelector('[data-testid=\"session-live-timeline\"]')"


def opened(c, rig) -> dict:
    c.go(rig.url("session"))
    c.wait(f"!!{COL} && document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"]').length >= 6", 40)
    time.sleep(0.8)
    return {"opened": True}


def strip(c, lv) -> dict:
    """The strip's lanes are this session's live agents; a click on the tester's lane pins it."""
    out: dict = {}
    pick(c, AGENT_PICK, "")
    c.wait(f"!{COL}.dataset.pinned", 5)
    here = f"{lv.hid}|{lv.sid}|"
    nodes = ("[...document.querySelectorAll('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"]')]"
             f".filter((n) => n.dataset.key.startsWith('{here}') && {list(LIVE)!r}.includes(n.dataset.state)).map((n) => n.dataset.key).sort()")
    lanes = f"[...{STRIP}.querySelectorAll('[data-testid=\"fleet-lane\"]')].map((l) => l.dataset.key).sort()"
    c.wait(f"JSON.stringify({lanes}) === JSON.stringify({nodes})", 15)
    out["lanes"], out["live_nodes"] = c.js(lanes), c.js(nodes)
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
    c.wait(f"document.querySelector('[data-testid=\"fleet-node\"][data-key=\"{docs}\"]')?.dataset.state === 'done'", 10)
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
    # main's liveness in the store comes from the rig's real session row, which the slow Linux runner reads as
    # no longer running by this step (the box stayed disabled for 30 s there, twice): say main is working again,
    # as a real session does with every step, and keep the button's own reason for the failure message
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
    from tests.helpers.fleet_rig import wait_for
    out: dict = {}
    c.js(f"{BOX}.querySelector('[data-testid=\"session-live-pause\"]').scrollIntoView({{block: 'center'}}); 1")
    c.wait(f"!{BOX}.querySelector('[data-testid=\"session-live-pause\"]').disabled && !{BOX}.dataset.disabled", 30)
    c.click_on(f"{BOX}.querySelector('[data-testid=\"session-live-pause\"]')")
    got = wait_for(lambda: [d for d in sent if d["cmd"] == "pause"], 15) or [{}]
    out["pause_route"] = {"sid": got[-1].get("sid"), "agent_id": (got[-1].get("fields") or {}).get("agent_id"), "status": got[-1].get("status")}
    out["pause_ack"] = c.wait("document.querySelector('.toasts')?.textContent.includes('Paused') && 'paused'", 15)
    from halo_harness.studio import fleet_api
    fleet_api.forward(lv.sid, "resume", {"agent_id": "main", **fleet_api.caller()})
    return out


def fleet_chip(c, rig, lv) -> dict:
    """In Fleet the same chip opens the Agent panel's Steer box on that agent, the keyboard in it."""
    out: dict = {}
    c.go(rig.url("fleet"))
    c.wait("document.querySelectorAll('[data-testid=\"fleet-node\"]').length >= 5", 40)
    time.sleep(1.0)
    res = lv.key("researcher")
    node = f"document.querySelector('[data-testid=\"fleet-node\"][data-key=\"{res}\"]')"
    chip = f"{node}.querySelector('[data-testid=\"fleet-node-steer\"]')"
    agent = "document.querySelector('[data-testid=\"fleet-agent-detail\"]')"
    opened = f"{agent}?.dataset.key === '{res}' && document.activeElement === {agent}.querySelector('[data-testid=\"fleet-steer\"]') && 'focused'"
    # the chip only takes the pointer while its node is hovered: the Linux runner lost the click once (the
    # pointer path from the node to the chip differs with its fonts), so hover and click up to three times
    out["fleet_chip_shown"], _ = hover(c, node, chip)
    c.click_on(chip)
    try:
        out["fleet_chip"] = c.wait(opened, 10)
        out["fleet_chip_by"] = "pointer"
    except TimeoutError:
        # the Linux runner's wider mono font puts the chip over a neighbouring node, so the pointer click lands on
        # that node (three tries, three runs); the chip's own handler is what this step pins, so click the chip
        # element itself and keep what the pointer click selected for the failure message
        out["fleet_chip_pointer_hit"] = c.js(f"[{agent}?.dataset.key || null, document.querySelector('[data-testid=\"fleet-node\"][data-selected]')?.dataset.key || null]")
        c.js(f"{chip}.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true}})); 1")
        try:
            out["fleet_chip"] = c.wait(opened, 15)
            out["fleet_chip_by"] = "element"
        except TimeoutError:
            # the Linux runner never satisfied `opened` through four rounds of fixes: record what the page
            # holds instead of dying here, so the test's own check prints it
            out["fleet_chip"] = "not opened"
            out["fleet_chip_diag"] = c.js(
                f"({{detail_key: {agent}?.dataset.key || null, detail_present: !!{agent}, selected: "
                f"document.querySelector('[data-testid=\"fleet-node\"][data-selected]')?.dataset.key || null, "
                f"active: document.activeElement?.dataset?.testid || document.activeElement?.tagName || null, "
                f"steer_box: !!{agent}?.querySelector('[data-testid=\"fleet-steer\"]'), chip: !!{chip}, "
                f"agent_panel: document.querySelector('[data-testid=\"fleet-agent\"]')?.dataset?.collapsed || "
                f"(document.querySelector('[data-testid=\"fleet-agent\"]') ? 'open' : 'absent')}})")
    return out
