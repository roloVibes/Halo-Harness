"""tools/capture_fleet.py -- the Fleet captures for tools/capture_studio.py
--mode fleet (Halo 3.0.5.0 round R3), through headless Chrome over the
DevTools protocol (tests/helpers/cdp.py) so the page can be driven before the
picture is taken. The scene is tests/helpers/studio_fleet_rig.py: this
harness's real session (a lead, an implementer and a researcher mid-work on
the shop repo) and a member harness `kali@lab` (its lead waiting on a
question, its reviewer done): two harnesses, five agents in three states.

    docs/media/studio-fleet.png       the map and the agent panel: the researcher's streams open, the
                                      implementer pinned (its mini stream floats over the map)
    docs/media/studio-roles-live.png  the Roles canvas glowing on the cards whose agents work, the
                                      implementer's Live tab open (3.0.7.0 R2: the React canvas)
    docs/media/studio-fleet-panels.png  (R4) the panels (eight since R6): People, Costs and Health compact on
                                      top, Attention with the member's two cards, the map with a
                                      conflict edge (both harnesses editing shop/basket.py), Activity's
                                      timeline and log, the researcher in Agent, and "While you were
                                      away" in the rail
    docs/media/studio-fleet-capabilities.png  (3.0.6.0 R6) Capabilities: "gridcraft" in Who can... ranks
                                      the member first and picks it (its card open, its map box lit), both
                                      spec cards (the rig seeds both catalogs: studio_fleet_member.seed_caps)
    docs/media/studio-fleet-mission.png  (3.0.6.0 R8) a planned mission (tests/helpers/studio_fleet_mseed.py:
                                      three parts, one pinned to each harness by capability, part 3 after
                                      part 1 because their claims overlap) drawn on the map, its table in
                                      the Mission panel, part 3 picked, its approval row in Attention

1500 x 900 CSS px at scale 2. With --dom the Fleet section, its Start view
(?view=start) and the Roles section are read and their data-testid values
counted (the last stdout line is the JSON).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

FLEET_IDS = ("section-tab", "fleet-map", "fleet-agent", "fleet-rail", "fleet-node", "fleet-start", "fleet-box", "fleet-session",
             "fleet-rail-node", "fleet-pip", "fleet-pair", "fleet-settings", "status-fleet",
             "fleet-people", "fleet-costs", "fleet-health", "fleet-attention", "fleet-activity",
             "fleet-capabilities", "fleet-mission")
LIVE_CARDS = "document.querySelectorAll('[data-testid=\"roles-card\"][data-live]')"  # 3.0.7.0 R2: the React Roles canvas


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(FLEET_IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def node(name: str) -> str:
    return f"[...document.querySelectorAll('[data-testid=\"fleet-node\"]')].find((n) => n.querySelector('.fm-name').textContent.startsWith('{name}'))"


def card(name: str) -> str:
    return f"[...document.querySelectorAll('[data-testid=\"roles-card\"]')].find((n) => n.dataset.agent === '{name}')"


def open_fleet(c, rig) -> None:
    c.go(rig.url("fleet"))
    c.wait("document.querySelectorAll('[data-testid=\"fleet-node\"]').length === 5 && document.querySelectorAll('[data-testid=\"fleet-box\"]').length === 2", 30)


def open_roles(c, rig) -> None:
    c.go(rig.url("roles"))
    c.wait(f"{LIVE_CARDS}.length >= 3", 30)
    time.sleep(1.0)  # the canvas fits itself after its first draw


def dom(c, rig) -> dict:
    open_fleet(c, rig)
    fleet = counts(c)
    c.go(rig.url("fleet", "&view=start"))
    c.wait("!!document.querySelector('[data-testid=\"fleet-start\"]') && !!document.querySelector('[data-testid=\"fleet-settings\"]')", 20)
    start = counts(c)
    open_roles(c, rig)
    roles = {"live-card": c.js(f"{LIVE_CARDS}.length"), "live-tab": c.js("document.querySelectorAll('[data-testid=\"roles-live-tab\"]').length"),
             "section-tab": counts(c)["section-tab"], "legacy-frame": c.js("document.querySelectorAll('iframe.legacy-frame').length")}
    return {"fleet": fleet, "start": start, "roles": roles}


def conflict(rig) -> None:
    """Both harnesses edit shop/basket.py: the implementer here (a feed frame), the member's reviewer (its relay)."""
    from halo_harness.fleet.identity import harness
    from tests.helpers.studio_fleet_member import REVIEWER
    from tests.helpers.studio_fleet_rig import MEMBER, MEMBER_SID
    a = rig.agent("Implement")
    rig.server.events.publish({"session_id": rig.act.session_id, "harness": harness()["id"], "event": "agent_state", "agent_id": a["agent_id"],
                               "ts": time.time(), "data": {**a, "current": f"Edit: {rig.proj / 'basket.py'}"}})
    rig.hub.state.frames(MEMBER, {"link": "rig-link", "frames": [{"session_id": MEMBER_SID, "event": "agent_state", "agent_id": REVIEWER["agent_id"],
                                                                 "ts": time.time(), "data": {**REVIEWER, "state": "running", "current": "Edit: /home/kali/shop/basket.py"}}]})


def shoot_panels(c, rig, png: Path) -> int:
    open_fleet(c, rig)
    c.js("localStorage.setItem('halo.fleet.lastSeen', String(Date.now() - 3 * 3600 * 1000)); window.dispatchEvent(new Event('focus')); 1")
    c.wait("!!document.querySelector('[data-testid=\"fleet-digest\"]')", 15)
    c.wait("document.querySelectorAll('[data-testid=\"fleet-attn-row\"]').length >= 2", 20)
    conflict(rig)
    c.wait("!!document.querySelector('[data-testid=\"fleet-conflict-edge\"]')", 30)
    c.click_on(node("researcher"))
    c.wait("[...document.querySelectorAll('[data-testid=\"fleet-text\"]')].some((e) => e.textContent.includes('tax rule'))", 15)
    c.wait("!document.querySelector('.toast')", 10)
    time.sleep(1.5)
    return c.shot(png)


def shoot_caps(c, rig, png: Path) -> int:
    """R6: Capabilities expanded (a layout saved for the picture, removed after), Who can... gridcraft,
    the member picked (its card focused, its map box lit), its gridcraft server open."""
    from tests.helpers.studio_fleet_member import MEMBER
    open_fleet(c, rig)
    c.js("localStorage.setItem('halo.studio.layout.fleet', JSON.stringify({v: 2, panels: {"
         "'fleet-capabilities': {x: 18, y: 0, w: 6, h: 70, face: 'detail', collapsed: false}}})); 1")  # 3.1.4.0 R1: its strip's column, open
    c.js("location.reload(); 1")  # the same URL: navigating would keep the page
    time.sleep(1.0)
    c.wait("document.querySelectorAll('[data-testid=\"fleet-node\"]').length === 5", 30)
    c.wait("document.querySelectorAll('[data-testid=\"fleet-caps-card\"] .fcap-facts').length === 2", 30)
    c.click_on("document.querySelector('[data-testid=\"fleet-who-input\"]')")
    c.type_text("gridcraft")
    c.wait("document.querySelectorAll('[data-testid=\"fleet-who-result\"]').length", 15)
    c.click_on("document.querySelector('[data-testid=\"fleet-who-result\"]')")
    c.js(f"document.querySelector('[data-testid=\"fleet-caps-card\"][data-id=\"{MEMBER}\"] [data-testid=\"fleet-caps-server\"]').open = true")
    c.wait("!!document.querySelector('[data-testid=\"fleet-box\"][data-who]')", 10)
    c.wait("!document.querySelector('.toast')", 10)
    time.sleep(1.5)
    size = c.shot(png)
    c.js("localStorage.removeItem('halo.studio.layout.fleet'); 1")
    return size


def shoot_mission(c, rig, png: Path) -> int:
    """R8: the plan on the map and in the Mission panel's table (no model: the seeded fake lead)."""
    from tests.helpers.studio_fleet_mseed import MissionFakes, plan_by_api
    from tests.helpers.studio_fleet_panels import open_strip, seen
    MissionFakes(rig)
    mid = plan_by_api(rig)["mission"]["id"]
    open_fleet(c, rig)
    open_strip(c, "fleet-mission")  # 3.1.4.0 R1: Mission starts as a strip on the right edge
    row = f"document.querySelector('[data-testid=\"fleet-mission-row\"][data-id=\"{mid}\"] [data-testid=\"fleet-mission-open\"]')"
    c.wait(f"!!{row}", 20)
    seen(c, row)
    c.click_on(row)
    part = "document.querySelector('[data-testid=\"fleet-part\"][data-part=\"3\"]')"
    c.wait("document.querySelectorAll('[data-testid=\"fleet-part\"]').length === 3", 20)
    seen(c, part)  # the Mission strip opened below the fold: bring the map's part back into view
    c.click_on(part)
    c.wait("!!document.querySelector('[data-testid=\"fleet-mission-part-row\"][aria-selected=\"true\"]')", 10)
    c.wait("!!document.querySelector('[data-testid=\"fleet-attn-row\"][data-kind=\"mission_plan\"]')", 20)
    c.js("document.querySelector('[data-testid=\"fleet-mission-detail\"]').scrollTop = 0; 1")
    c.wait("!document.querySelector('.toast')", 10)
    time.sleep(1.5)
    return c.shot(png)


def shoot_session(c, rig, png: Path) -> int:
    """3.1.4.0 R2: the Session section (Alt+6): this harness's box only, the researcher's streams open."""
    c.go(rig.url("session"))
    c.wait("!!document.querySelector('[data-testid=\"session-map\"]') && document.querySelectorAll('[data-testid=\"fleet-node\"]').length >= 1", 30)
    c.wait("document.querySelectorAll('[data-testid=\"fleet-box\"]').length === 1", 20)
    c.click_on(node("researcher"))
    c.wait("[...document.querySelectorAll('[data-testid=\"fleet-text\"]')].some((e) => e.textContent.includes('tax rule'))", 15)
    c.wait("!document.querySelector('.toast')", 10)
    time.sleep(1.2)
    return c.shot(png)


def shoot(c, rig, fleet_png: Path, roles_png: Path) -> bool:
    open_fleet(c, rig)
    c.click_on(node("implementer"))
    x, y, w, h = c.rect("document.querySelector('.fm-scroll')")
    c.click(x + w - 30, y + h - 30)
    c.key(" ")  # pin the implementer: its mini stream stays on screen
    c.wait("!!document.querySelector('[data-testid=\"fleet-pip\"]') || true", 5)
    c.click_on(node("researcher"))
    c.wait("[...document.querySelectorAll('[data-testid=\"fleet-text\"]')].some((e) => e.textContent.includes('tax rule'))", 15)
    c.wait("!!document.querySelector('[data-testid=\"fleet-pip\"] .pip-text')", 10)
    c.wait("!document.querySelector('.toast')", 10)  # the toasts fade first: nothing covers the Steer box
    time.sleep(1.2)
    a = c.shot(fleet_png)
    open_roles(c, rig)
    c.click_on(card("implementer"), 0.5, 0.25)
    c.wait("[...document.querySelectorAll('[data-testid=\"roles-live\"] [data-testid=\"fleet-text\"]')].some((e) => e.textContent.includes('discount'))", 15)
    time.sleep(1.2)
    b = c.shot(roles_png)
    panels_png = fleet_png.with_name("studio-fleet-panels.png")
    d = shoot_panels(c, rig, panels_png)
    caps_png = fleet_png.with_name("studio-fleet-capabilities.png")
    e = shoot_caps(c, rig, caps_png)
    session_png = fleet_png.with_name("studio-session.png")
    s = shoot_session(c, rig, session_png)  # 3.1.4.0 R2: the sixth banner frame
    mission_png = fleet_png.with_name("studio-fleet-mission.png")
    m = shoot_mission(c, rig, mission_png)  # last: the planned mission stays in the rig
    for path, size in ((fleet_png, a), (roles_png, b), (panels_png, d), (caps_png, e), (session_png, s), (mission_png, m)):
        print(f"{'wrote' if size > 10_000 else 'FAILED'} {path} ({size} bytes)")
    return min(a, b, d, e, s, m) > 10_000


def capture(out: str, as_dom: bool, find_chrome) -> int:
    """Seed, serve, render; the exit code capture_studio.py returns."""
    from tests.helpers.chrome_driver import open_chrome
    from tests.helpers.studio_fleet_rig import StudioFleetRig
    exe = find_chrome()
    if not exe:
        print("no Chrome found")
        return 2
    with StudioFleetRig() as rig:
        c = open_chrome(exe=exe)  # the driver base: one headless Chrome at a time
        try:
            if as_dom:
                print(json.dumps(dom(c, rig)))
                return 0
            fleet_png = Path(out).resolve()
            return 0 if shoot(c, rig, fleet_png, fleet_png.with_name("studio-roles-live.png")) else 1
        finally:
            c.close()
