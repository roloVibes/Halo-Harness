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
                                      implementer's Live tab open
    docs/media/studio-fleet-panels.png  (R4) the panels (eight since R6): People, Costs and Health compact on
                                      top, Attention with the member's two cards, the map with a
                                      conflict edge (both harnesses editing shop/basket.py), Activity's
                                      timeline and log, the researcher in Agent, and "While you were
                                      away" in the rail
    docs/media/studio-fleet-capabilities.png  (3.0.6.0 R6) Capabilities: "gridcraft" in Who can... ranks
                                      the member first and picks it (its card open, its map box lit), both
                                      spec cards (the rig seeds both catalogs: studio_fleet_member.seed_caps)

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
             "fleet-capabilities")
FRAME = "document.querySelector('.section-view[data-section=\"roles\"] iframe.legacy-frame')"
DOC = f"{FRAME}.contentDocument"


def counts(c) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(FLEET_IDS)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def node(name: str) -> str:
    return f"[...document.querySelectorAll('[data-testid=\"fleet-node\"]')].find((n) => n.querySelector('.fm-name').textContent.startsWith('{name}'))"


def card(name: str) -> str:
    return f"[...{DOC}.querySelectorAll('.node')].find((n) => n.querySelector('.agent')?.textContent === '{name}')"


def frame_click(c, expr: str) -> None:
    """Click an element of the framed page once it stops moving (the canvas lays its groups out and fits after it loads)."""
    import time
    fx, fy, _w, _h = c.rect(FRAME)
    last, end = None, time.time() + 5
    while time.time() < end:
        r = [round(v) for v in c.rect(expr)]
        if r == last:
            break
        last = r
        time.sleep(0.25)
    x, y, w, h = c.rect(expr)
    c.click(fx + x + w / 2, fy + y + min(h / 2, 30))


def open_fleet(c, rig) -> None:
    c.go(rig.url("fleet"))
    c.wait("document.querySelectorAll('[data-testid=\"fleet-node\"]').length === 5 && document.querySelectorAll('[data-testid=\"fleet-box\"]').length === 2", 30)


def open_roles(c, rig) -> None:
    c.go(rig.url("roles"))
    c.wait(f"{DOC}?.querySelectorAll('[data-testid=\"live-card\"]').length >= 3", 30)
    c.js(f"(() => {{ const w = {FRAME}.contentWindow; w.document.body.classList.add('rail-hidden'); setTimeout(() => w.app.canvas.fit(), 50); return 1; }})()")
    time.sleep(0.6)


def dom(c, rig) -> dict:
    open_fleet(c, rig)
    fleet = counts(c)
    c.go(rig.url("fleet", "&view=start"))
    c.wait("!!document.querySelector('[data-testid=\"fleet-start\"]') && !!document.querySelector('[data-testid=\"fleet-settings\"]')", 20)
    start = counts(c)
    open_roles(c, rig)
    roles = {"live-card": c.js(f"{DOC}.querySelectorAll('[data-testid=\"live-card\"]').length"),
             "live-tab": c.js(f"{DOC}.querySelectorAll('[data-testid=\"live-tab\"]').length"), "section-tab": counts(c)["section-tab"]}
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
         "'fleet-capabilities': {x: 16, y: 14, w: 8, h: 60, face: 'detail'}, 'fleet-agent': {x: 16, y: 74, w: 8, h: 32}}})); 1")
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
    frame_click(c, f"{card('implementer')}.querySelector('.card')")
    c.wait(f"[...{DOC}.querySelectorAll('[data-testid=\"live-text\"]')].some((e) => e.textContent.includes('discount'))", 15)
    time.sleep(1.2)
    b = c.shot(roles_png)
    panels_png = fleet_png.with_name("studio-fleet-panels.png")
    d = shoot_panels(c, rig, panels_png)
    caps_png = fleet_png.with_name("studio-fleet-capabilities.png")
    e = shoot_caps(c, rig, caps_png)
    for path, size in ((fleet_png, a), (roles_png, b), (panels_png, d), (caps_png, e)):
        print(f"{'wrote' if size > 10_000 else 'FAILED'} {path} ({size} bytes)")
    return min(a, b, d, e) > 10_000


def capture(out: str, as_dom: bool, find_chrome) -> int:
    """Seed, serve, render; the exit code capture_studio.py returns."""
    from tests.helpers.cdp import Chrome
    from tests.helpers.studio_fleet_rig import StudioFleetRig
    exe = find_chrome()
    if not exe:
        print("no Chrome found")
        return 2
    with StudioFleetRig() as rig:
        c = Chrome(exe)
        try:
            if as_dom:
                print(json.dumps(dom(c, rig)))
                return 0
            fleet_png = Path(out).resolve()
            return 0 if shoot(c, rig, fleet_png, fleet_png.with_name("studio-roles-live.png")) else 1
        finally:
            c.close()
