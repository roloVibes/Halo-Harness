"""tests.helpers.studio_session_links -- the links into the Session dashboard
(Halo 3.1.4.0 R2), the `links` step of tests/helpers/studio_session.py: a
click on this harness's agent in the Fleet rail opens Session on it while a
member's opens Fleet; a map node's `...` menu has Open in Session on this
harness's nodes only; the Roles Live tab's header has Watch in Session for a
working card's agent; a live Orchestra run's line has it for the run's
session (a run folder whose lead is this harness's session, marked live the
way studio/orchestra_live.py marks the one it drives)."""
from __future__ import annotations

import threading

from tests.helpers.studio_session import AGENT, COST, TAB, inside, url

FLEET_AGENT = "document.querySelector('[data-section=\"fleet\"] [data-testid=\"fleet-agent-detail\"]')"


def rail_node(harness: str, aid: str) -> str:
    return (f"[...document.querySelectorAll('[data-testid=\"fleet-rail-node\"]')].find((n) => n.dataset.kind === 'agent' && n.dataset.id === '{aid}'"
            f" && n.closest('.fr-harness').querySelector('.fr-h').dataset.id === '{harness}')")


def fleet_node(name: str) -> str:
    return f"[...{inside('fleet', 'fleet-node')}].find((n) => n.querySelector('.fm-name').textContent.startsWith('{name}'))"


def menu_items(c) -> list:
    return c.wait("document.querySelector('[data-testid=\"fleet-node-menu\"]') && [...document.querySelectorAll('[data-testid=\"fleet-node-menu\"] [data-item]')].map((b) => b.dataset.item)", 10) or []


def live_run(rig):
    """A run of the rig's repo led by this harness's session, live as Studio's own run is."""
    from halo_harness.orchestra.goal import Goal, new_run
    from halo_harness.studio import orchestra_live as L
    goal = Goal(what="Ship the basket discount fix", done_when="the tests pass", stop_when="two returns", workers=2,
                return_cap=1, test="python -c pass", files=["basket.py"], test_timeout_s=30)
    run_dir = new_run(rig.proj, goal, lead_holder=f"{rig.act.session_id}/main")
    stop = threading.Event()
    keeper = threading.Thread(target=stop.wait, daemon=True, name="rig-live-run")
    keeper.start()
    with L._lock:
        L._live.update(thread=keeper, run_id=run_dir.name)
    rig.closers.append(stop.set)
    return run_dir


def links(c, rig) -> dict:
    from halo_harness.fleet.identity import harness
    from tests.helpers.studio_fleet import card, card_click
    out: dict = {}
    hid, sid = harness()["id"], rig.act.session_id
    impl, res = rig.agent("Implement").get("agent_id"), rig.agent("Research").get("agent_id")
    c.go(url(rig, "mode=fleet"))
    c.wait(f"{inside('fleet', 'fleet-box')}.length === 2 && !!({rail_node(hid, impl)})", 30)
    c.js(f"({rail_node(hid, impl)}).scrollIntoView({{block: 'center'}}); 1")  # 3.3.2.0 R1: the Fleet tree sits below the section rows
    c.click_on(rail_node(hid, impl))
    out["rail_local_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["rail_local_agent"] = c.wait(f"{AGENT}?.dataset.key === '{hid}|{sid}|{impl}' && 'implementer'", 15)
    c.js(f"({rail_node(rig.member_id, 'main')}).scrollIntoView({{block: 'center'}}); 1")
    c.click_on(rail_node(rig.member_id, "main"))
    out["rail_member_tab"] = c.wait(f"{TAB}.startsWith('Fleet') && {TAB}", 10)
    out["rail_member_agent"] = c.wait(f"{FLEET_AGENT}?.dataset.key?.startsWith('{rig.member_id}|') && 'member'", 15)
    c.click_on(f"{fleet_node('researcher')}.querySelector('.fm-more')")
    out["menu_local"] = menu_items(c)
    c.click_on("document.querySelector('[data-testid=\"fleet-node-menu\"] [data-item=\"session\"]')")
    out["menu_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["menu_agent"] = c.wait(f"{AGENT}?.dataset.key === '{hid}|{sid}|{res}' && 'researcher'", 15)
    c.go(url(rig, "mode=fleet&page=2"))  # another URL than the page's own, so it loads afresh
    c.wait(f"{inside('fleet', 'fleet-box')}.length === 2", 30)
    c.click_on(f"[...{inside('fleet', 'fleet-node')}].find((n) => n.dataset.key.startsWith('{rig.member_id}|')).querySelector('.fm-more')")
    out["menu_member"] = menu_items(c)
    c.key("Escape")
    c.go(url(rig, "mode=roles"))
    c.wait("document.querySelectorAll('[data-testid=\"roles-card\"][data-live]').length >= 3", 30)
    card_click(c, card("implementer"))
    out["watch_roles"] = c.wait("document.querySelector('[data-testid=\"roles-watch-session\"]')?.textContent", 15)
    c.click_on("document.querySelector('[data-testid=\"roles-watch-session\"]')")
    out["roles_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["roles_agent"] = c.wait(f"{AGENT}?.dataset.key === '{hid}|{sid}|{impl}' && 'implementer'", 15)
    live_run(rig)
    c.go(url(rig, "mode=orchestra"))
    out["watch_orchestra"] = c.wait("document.querySelector('[data-testid=\"orchestra-watch-session\"]')?.textContent", 30)
    c.click_on("document.querySelector('[data-testid=\"orchestra-watch-session\"]')")
    out["orchestra_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["orchestra_session"] = c.wait(f"{COST}?.dataset.session === '{sid}' && {COST}.dataset.session", 15)
    out["orchestra_agent"] = c.js(f"{AGENT}?.dataset.key?.startsWith('{hid}|{sid}|')")
    out["sid"] = sid
    return out
