"""tests.helpers.studio_fleet_mission -- the Studio Fleet Mission panel of Halo
3.0.6.0 round R8 in headless Chrome over the DevTools protocol, over
tests/helpers/studio_fleet_rig.py with the mission fakes of
tests/helpers/studio_fleet_mseed.py (no model call). Run through
tests/helpers/studio_fleet.py:

    python -m tests.helpers.studio_fleet mission

* the panel is there with its about line and, with no mission yet, its five
  lines on how it works; a goal typed and Plan it draws the plan on the map:
  three part nodes, each inside its harness box, one depends_on edge and one
  sequenced edge with its chip, two locks; the table has three rows and
  Attention a mission_plan row;
* dragging part 3 into this harness's box posts the reassign and the node
  moves there; dragging part 1 (it needs gridcraft) there answers 422: the
  toast says why and the node snaps back;
* Approve, then Run: part 1 waits on the member's owner (asked), part 2 runs
  here; another hub's run_task on this harness opens a mission_ask row whose
  O opens the Mission panel on that mission; R denies it; the member's owner
  allows: part 1 runs, its agent's line shows, the rail has the mission chip,
  the status bar counts one mission; "Open the part's agent" selects it;
* Stop asks for a reason, the mission ends stopped and the report face lists
  the cost per harness.
"""
from __future__ import annotations

import time

MID = "document.querySelector('[data-testid=\"fleet-mission-layer\"]')?.dataset.mission"
PANEL = "document.querySelector('[data-testid=\"fleet-mission\"]')"
NODE = "document.querySelector('[data-testid=\"fleet-part\"][data-part=\"{}\"]')"
BOX = "document.querySelector('[data-testid=\"fleet-box\"][data-key=\"h:{}\"] .fm-box-shape')"
INSIDE = ("[...document.querySelectorAll('[data-testid=\"fleet-part\"]')].map((n) => { const b = document.querySelector(`[data-testid=\"fleet-box\"][data-key=\"h:${n.dataset.harness}\"] .fm-box-shape`);"
          " if (!b) return n.dataset.part + ':nobox'; const r = n.getBoundingClientRect(), q = b.getBoundingClientRect();"
          " return n.dataset.part + ':' + (r.left >= q.left && r.right <= q.right + 1 && r.top >= q.top && r.bottom <= q.bottom ? 'in' : 'out'); })")
LIVE = "document.querySelector('[data-testid=\"fleet-mission-live\"][data-part=\"{}\"]')"
ROW = "document.querySelector('[data-testid=\"fleet-attn-row\"][data-kind=\"{}\"]')"


def press(c, expr: str) -> None:
    """Scroll it into view, then click it."""
    from tests.helpers.studio_fleet_panels import seen
    seen(c, expr)
    c.click_on(expr)


def _drag(c, part: str, hid: str) -> None:
    from tests.helpers.studio_fleet_panels import seen
    seen(c, NODE.format(part))
    x, y, w, h = c.rect(NODE.format(part))
    bx, by, bw, bh = c.rect(BOX.format(hid))
    c.drag(x + 60, y + h / 2, bx + bw / 2, y + h / 2, steps=10)


def plan_and_drag(c, rig, out: dict) -> str:
    from tests.helpers.studio_fleet_mseed import GOAL
    from tests.helpers.studio_fleet_panels import open_strip, seen
    out["about"] = c.wait(f"{PANEL}?.querySelector('.panel-about')?.textContent", 30)
    open_strip(c, "fleet-mission")  # 3.1.4.0 R1: a strip on the right edge by default
    out["how"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-mission-how\"] li').length", 20)
    seen(c, "document.querySelector('[data-testid=\"fleet-mission-goal\"]')")
    c.click_on("document.querySelector('[data-testid=\"fleet-mission-goal\"]')")
    c.type_text(GOAL)
    press(c, "document.querySelector('[data-testid=\"fleet-mission-prefer\"][data-name=\"you@studio\"]')")
    out["prefer_on"] = c.js("document.querySelector('[data-testid=\"fleet-mission-prefer\"][data-name=\"you@studio\"]').getAttribute('aria-pressed')")
    press(c, "document.querySelector('[data-testid=\"fleet-mission-plan-it\"]')")
    out["nodes"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-part\"]').length === 3 && 3", 40)
    mid = c.wait(MID, 10)
    out["placed"] = c.js("Object.fromEntries([...document.querySelectorAll('[data-testid=\"fleet-part\"]')].map((n) => [n.dataset.part, n.dataset.harness]))")
    out["inside"] = c.js(INSIDE)
    out["edges"] = sorted(c.js("[...document.querySelectorAll('[data-testid=\"fleet-mission-edge\"]')].map((e) => e.dataset.kind + ':' + e.dataset.from + '>' + e.dataset.to)"))
    out["seq_chips"] = c.js("document.querySelectorAll('[data-testid=\"fleet-mission-seq-chip\"]').length")
    out["locks"] = c.js("document.querySelectorAll('[data-testid=\"fleet-part-lock\"]').length")
    out["edge_labels"] = c.js("[...document.querySelectorAll('[data-testid=\"part-edge-label\"]')].map((e) => e.dataset.from + '>' + e.dataset.to + ':' + e.querySelector('text').textContent)")
    out["part_bases"] = c.js("Object.fromEntries([...document.querySelectorAll('[data-testid=\"fleet-part\"]')].map((n) => [n.dataset.part, n.querySelector('[data-testid=\"part-base\"]')?.textContent || '']))")
    out["mission_base"] = (rig.api("GET", f"fleet/missions/{mid}")[1]["mission"].get("repo") or {}).get("base") or ""
    out["planned_dashed"] = c.js(f"getComputedStyle({NODE.format('1')}.querySelector('.fmi-node-shape')).strokeDasharray")
    out["table_rows"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-mission-part-row\"]').length", 10)
    out["plan_row"] = c.wait(f"{ROW.format('mission_plan')}?.querySelector('.fat-what')?.textContent", 20)
    hub = rig.hub.state.identity["id"]
    _drag(c, "3", hub)
    out["moved"] = c.wait(f"{NODE.format('3')}?.dataset.harness === '{hub}' && 'moved'", 20)
    out["moved_api"] = rig.api("GET", f"fleet/missions/{mid}")[1]["plan"]["parts"][2]["harness_name"]
    out["moved_inside"] = c.js(INSIDE)
    _drag(c, "1", hub)
    out["refused_toast"] = c.wait("[...document.querySelectorAll('.toast')].map((t) => t.textContent).find((t) => t.includes('stays'))", 20)
    out["snapped"] = c.wait(f"{NODE.format('1')}?.dataset.harness === '{rig.member_id}' && !{NODE.format('1')}.dataset.drag && 'back'", 10)
    out["snapped_inside"] = c.js(INSIDE)
    return mid


def run_and_ask(c, rig, fakes, mid: str, out: dict) -> None:
    from tests.helpers.studio_fleet import DETAIL
    from tests.helpers.studio_fleet_panels import seen
    from tests.helpers.studio_fleet_rig import wait_for
    seen(c, "document.querySelector('[data-testid=\"fleet-mission-approve\"]')")
    c.click_on("document.querySelector('[data-testid=\"fleet-mission-approve\"]')")
    out["approved"] = c.wait("document.querySelector('[data-testid=\"fleet-mission-state\"]')?.textContent === 'approved' && 'approved'", 15)
    seen(c, "document.querySelector('[data-testid=\"fleet-mission-run\"]')")
    c.click_on("document.querySelector('[data-testid=\"fleet-mission-run\"]')")
    out["run_face"] = c.wait("document.querySelector('[data-testid=\"fleet-mission-detail\"]')?.dataset.face === 'run' && 'run'", 15)
    out["asked"] = c.wait(f"{LIVE.format('1')}?.dataset.state === 'asked' && {LIVE.format('1')}.querySelector('[data-testid=\"fleet-mission-now\"]').textContent", 30)
    out["local_running"] = c.wait(f"{LIVE.format('2')}?.dataset.state === 'running' && 'running'", 30)
    out["node_states"] = c.wait(f"{NODE.format('1')}?.dataset.state === 'asked' && Object.fromEntries([...document.querySelectorAll('[data-testid=\"fleet-part\"]')].map((n) => [n.dataset.part, n.dataset.state]))", 15)
    out["running_solid"] = c.js(f"getComputedStyle({NODE.format('2')}.querySelector('.fmi-node-shape')).strokeDasharray")
    out["control_row"] = c.wait(f"{ROW.format('control_ask')}?.querySelector('.fat-what')?.textContent", 20)
    asked = fakes.ask_here()
    row = ROW.format("mission_ask")
    out["ask_row"] = c.wait(f"{row}?.querySelector('.fat-detail')?.textContent", 30)
    seen(c, row)
    c.click_on(f"{row}.querySelector('.fat-what')")
    c.key("o")
    out["ask_open"] = c.wait("document.querySelector('.fmi-nothere')?.textContent.includes('m-20261015-0b5e') && 'not here'", 15)
    press(c, f"{row}.querySelector('.fat-what')")
    c.key("r")
    out["ask_denied"] = wait_for(lambda: asked.get("state"), 20)
    out["ask_gone"] = c.wait(f"!{row} && 'gone'", 20)
    press(c, "document.querySelector('.fmi-nothere button')")
    press(c, f"document.querySelector('[data-testid=\"fleet-mission-row\"][data-id=\"{mid}\"] [data-testid=\"fleet-mission-open\"]')")
    out["reopened"] = c.wait("document.querySelector('[data-testid=\"fleet-mission-detail\"]')?.dataset.face === 'run' && 'run'", 15)
    out["allowed"] = fakes.allow_member(mid)
    out["member_line"] = c.wait(f"{LIVE.format('1')}?.dataset.state === 'running' && {LIVE.format('1')}.querySelector('[data-testid=\"fleet-mission-now\"]').textContent", 30)
    out["rail_chips"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-rail-mission\"]').length >= 2 && document.querySelectorAll('[data-testid=\"fleet-rail-mission\"]').length", 20)
    out["status_missions"] = c.wait("document.querySelector('[data-testid=\"status-missions\"]')?.textContent", 20)
    out["hcosts"] = c.js("[...document.querySelectorAll('[data-testid=\"fleet-mission-hcost\"]')].map((e) => e.dataset.name)")
    btn = f"{LIVE.format('1')}.querySelector('[data-testid=\"fleet-mission-open-agent\"]')"
    seen(c, btn)
    c.click_on(btn)
    out["agent_opened"] = c.wait(f"{DETAIL}?.dataset.key", 15)
    fakes.release_local()
    out["local_done"] = c.wait(f"{LIVE.format('2')}?.dataset.state === 'done' && 'done'", 30)


def stop_and_report(c, rig, out: dict) -> None:
    from tests.helpers.studio_fleet_panels import seen
    seen(c, "document.querySelector('[data-testid=\"fleet-mission-stop\"]')")
    stop = "document.querySelector('[data-testid=\"fleet-mission-stop\"]')"
    ask = "document.querySelector('[data-testid=\"fleet-mission-stop-ask\"] .dialog-title')?.textContent"
    c.click_on(stop)
    try:
        out["stop_asks"] = c.wait(ask, 15)
    except TimeoutError:  # the Windows runner missed the pointer click once (8856816): click the button itself
        c.js(f"{stop}.click(); 1")
        out["stop_asks"] = c.wait(ask, 20)
        out["stop_asks_by"] = "element"
    c.click_on("document.querySelector('[data-testid=\"fleet-mission-stop-reason\"]')")
    c.type_text("seen enough for today")
    c.click_on("document.querySelector('[data-testid=\"fleet-mission-stop-yes\"]')")
    out["stopped"] = c.wait("document.querySelector('[data-testid=\"fleet-mission-state\"]')?.textContent === 'stopped' && 'stopped'", 40)
    out["report_face"] = c.wait("document.querySelector('[data-testid=\"fleet-mission-detail\"]')?.dataset.face === 'report' && 'report'", 15)
    out["report_harnesses"] = c.wait("document.querySelectorAll('[data-testid=\"fleet-mission-report-harness\"]').length === 2 && "
                                     "[...document.querySelectorAll('[data-testid=\"fleet-mission-report-harness\"]')].map((r) => [...r.children].map((td) => td.textContent).join('|'))", 20)
    out["report_total"] = c.js("document.querySelector('[data-testid=\"fleet-mission-total\"]')?.textContent")
    out["after_stop_status"] = c.wait("!document.querySelector('[data-testid=\"status-missions\"]') && 'none'", 20)
    out["agent_stop_sent"] = [d.get("fields", {}).get("agent_id") for d in rig.member_cmds if d.get("cmd") == "agent_stop"]


def mission(c, rig) -> dict:
    from tests.helpers.studio_fleet_mseed import MissionFakes
    fakes = MissionFakes(rig)
    fakes.hold_tasks()
    out: dict = {}
    c.go(rig.url("fleet"))
    c.wait("document.querySelectorAll('[data-testid=\"fleet-node\"]').length === 5", 30)
    mid = plan_and_drag(c, rig, out)
    out["mission"] = mid
    run_and_ask(c, rig, fakes, mid, out)
    stop_and_report(c, rig, out)
    time.sleep(0.2)
    return out
