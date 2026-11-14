"""tests.helpers.studio_session_links -- the links into the Session dashboard
(Halo 3.1.4.0 R2), the `links` step of tests/helpers/studio_session.py: this harness's agent clicked on Agents ->
Live has Watch in Session in the inspector, which opens Session on it; a node's `...` menu has Open in Session; the
Roles Live tab's header has Watch in Session for a
working card's agent; a live Orchestra run's line has it for the run's
session (a run folder whose lead is this harness's session, marked live the
way studio/orchestra_live.py marks the one it drives)."""
from __future__ import annotations

import threading

from tests.helpers.studio_session import AGENT, COST, TAB, inside, url

FLEET_AGENT = "document.querySelector('[data-section=\"agents\"] [data-testid=\"fleet-agent-detail\"]')"


def rail_node(harness: str, aid: str) -> str:
    """An agent's node on Live, by its harness and agent id."""
    return f"document.querySelector('[data-section=\"agents\"] [data-testid=\"roles-live-node\"][data-key^=\"{harness}|\"][data-agent=\"{aid}\"]')"


def click_node(c, expr: str) -> None:
    """Scroll a node into view on the canvas, then click it."""
    c.wait(f"!!({expr})", 20)
    c.js(f"({expr}).scrollIntoView({{block: 'center', inline: 'center'}}); 1")
    c.click_on(expr)


def fleet_node(name: str) -> str:
    return f"[...{inside('agents', 'roles-live-node')}].find((n) => n.querySelector('.rlm-name').textContent.startsWith('{name}'))"


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
    from halo_harness.peers.identity import harness
    from tests.helpers.studio_live import card, card_click
    out: dict = {}
    hid, sid = harness()["id"], rig.act.session_id
    impl, res = rig.agent("Implement").get("agent_id"), rig.agent("Research").get("agent_id")
    c.go(url(rig, "mode=agents&view=live"))
    c.wait(f"{inside('agents', 'roles-live-node')}.length === 3", 30)
    click_node(c, rail_node(hid, impl))
    watch = "document.querySelector('[data-section=\"agents\"] [data-testid=\"roles-watch-session\"]')"
    c.wait(f"!!{watch}", 15)
    c.click_on(watch)  # the agent inspector's Watch in Session (a live agent of this harness)
    out["rail_local_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["rail_local_agent"] = c.wait(f"{AGENT}?.dataset.key === '{hid}|{sid}|{impl}' && 'implementer'", 15)
    c.click_on("document.querySelector('.rail [data-testid=section-tab][data-tab-id=agents]')")  # back to Agents, still on Live
    c.js(f"({fleet_node('researcher')}).scrollIntoView({{block: 'center'}}); 1")
    c.click_on(f"{fleet_node('researcher')}.querySelector('.rlm-more')")
    out["menu_local"] = menu_items(c)
    c.click_on("document.querySelector('[data-testid=\"fleet-node-menu\"] [data-item=\"session\"]')")
    out["menu_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["menu_agent"] = c.wait(f"{AGENT}?.dataset.key === '{hid}|{sid}|{res}' && 'researcher'", 15)
    c.go(url(rig, "mode=roles"))
    c.wait("document.querySelectorAll('[data-testid=\"roles-card\"][data-live]').length >= 3", 30)
    card_click(c, card("implementer"))
    out["watch_roles"] = c.wait("document.querySelector('[data-testid=\"roles-watch-session\"]')?.textContent", 15)
    c.click_on("document.querySelector('[data-testid=\"roles-watch-session\"]')")
    out["roles_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["roles_agent"] = c.wait(f"{AGENT}?.dataset.key === '{hid}|{sid}|{impl}' && 'implementer'", 15)
    live_run(rig)
    c.go(url(rig, "mode=agents&view=live&plan=off"))  # 3.4.0.0 D: the run's lead on Live; its summary carries Watch in Session
    lead = "document.querySelector('[data-testid=\"agents-live-lead\"]')"
    c.wait(f"!!{lead}", 30)
    c.click_on(lead)
    out["watch_orchestra"] = c.wait("document.querySelector('[data-testid=\"orchestra-watch-session\"]')?.textContent", 30)
    c.click_on("document.querySelector('[data-testid=\"orchestra-watch-session\"]')")
    out["orchestra_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["orchestra_session"] = c.wait(f"{COST}?.dataset.session === '{sid}' && {COST}.dataset.session", 15)
    out["orchestra_agent"] = c.js(f"{AGENT}?.dataset.key?.startsWith('{hid}|{sid}|')")
    out["sid"] = sid
    return out
