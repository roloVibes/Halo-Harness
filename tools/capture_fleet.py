"""tools/capture_fleet.py -- the fleet captures for tools/capture_studio.py --mode fleet (Halo 3.0.5.0 round R3;
3.3.16.0 R2 "the Fleet fold": the Fleet section went, so the pictures are where its pieces live now), through headless
Chrome over the DevTools protocol (tests/helpers/cdp.py) so the page can be driven before the picture is taken. The
scene is tests/helpers/studio_fleet_rig.py: this harness's real session (a lead, an implementer and a researcher
mid-work on the shop repo) and a member harness `kali@lab` (its lead waiting on a question, its reviewer done): two
machines, five agents in three states.

    docs/media/studio-fleet.png               Agents -> Live on the fleet: both machines as boxes, their sessions and
                                              agents, a conflict edge (both editing shop/basket.py), the inspector's
                                              glance (the machines, what waits on you, today's spend)
    docs/media/studio-fleet-panels.png        Setup -> Machines: the pair card (Make a pair code), the share and
                                              control rows, the People table
    docs/media/studio-fleet-capabilities.png  a machine's Specs and who can... page on Live: "gridcraft" ranks the member
                                              first and picks it (its box lit, its spec card, its gridcraft server open)
    docs/media/studio-fleet-mission.png       a planned mission (tests/helpers/studio_fleet_mseed.py: three parts, one
                                              pinned to each machine, part 3 after part 1 because their claims
                                              overlap) drawn on Live, part 3's card in the inspector
    (3.1.5.0 R3: studio-roles-live.png and studio-session.png are tools/capture_session_anim.py's.)

1500 x 900 CSS px at scale 2. With --dom, Live on the fleet, Setup -> Machines and Cast with its glowing cards are read
and their data-testid values counted (the last stdout line is the JSON). 3.1.7.0 R2: this harness is `you@studio`
(tools/capture_identity.py), the conflict's edits are repo-relative, and every page is guarded before it is counted or
shot.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from capture_identity import guard_page, placeholder

LIVE_IDS = ("section-tab", "roles-live-map", "live-machine", "fleet-box", "fleet-session", "roles-live-node", "live-inspector",
            "live-glance", "live-glance-machine", "agents-attention", "fleet-activity", "status-fleet")
MACHINES_IDS = ("section-tab", "setup-machines", "setup-machines-lead", "fleet-pair", "fleet-settings", "fleet-people-list",
                "fleet-person", "roles-live-map")
LIVE_CARDS = "document.querySelectorAll('[data-testid=\"roles-card\"][data-live]')"
MAP = "document.querySelector('[data-testid=\"roles-live-map\"]')"


def counts(c, ids) -> dict:
    return c.js("Object.fromEntries(" + json.dumps(list(ids)) + ".map((k) => [k, document.querySelectorAll(`[data-testid=\"${k}\"]`).length]))")


def open_live(c, rig, extra: str = "") -> None:
    """Agents -> Live on the fleet (`?mode=fleet`), the inspector strip opened on the glance. The saved layout of the
    last picture is forgotten first."""
    from tests.helpers.studio_fleet_panels import open_strip
    c.js("try { localStorage.removeItem('halo.studio.layout.roles'); } catch (e) {} 1")
    c.go("about:blank")
    c.go(rig.url("fleet", extra))
    c.wait(f"{MAP}?.dataset.scope === 'fleet' && +{MAP}.dataset.nodes >= 4 && +{MAP}.dataset.machines === 2", 60)  # 3.3.18.0: the past reviewer is not drawn (until the conflict scene)
    open_strip(c, "roles-inspector")
    c.wait("!!document.querySelector('[data-testid=\"live-inspector\"]')", 15)


def open_machines(c, rig) -> None:
    c.go("about:blank")
    c.go(rig.url("setup", "&block=machines"))
    # every piece the --dom counts read: the settings come from their own GET, which a slow runner answers after the
    # people (GitHub's Linux runner at 123feae3 counted fleet-settings 0)
    c.wait("document.querySelectorAll('[data-testid=\"fleet-person\"]').length === 2 && !!document.querySelector('[data-testid=\"fleet-pair\"]')"
           " && !!document.querySelector('[data-testid=\"fleet-settings\"]')", 30)


def dom(c, rig) -> dict:
    from tests.helpers.studio_header_menus import plus
    open_live(c, rig, "&open=all")  # the counts read every panel
    plus(c, "fleet-activity")  # the optional Activity panel, as a user adds it (the header's "+")
    c.wait("!!document.querySelector('[data-testid=\"fleet-log\"]')", 20)
    guard_page(c, "fleet live")
    live = counts(c, LIVE_IDS)
    open_machines(c, rig)
    guard_page(c, "setup machines")
    machines = counts(c, MACHINES_IDS)
    c.go(rig.url("roles", "&open=all"))  # Cast: the cards whose agents work glow
    c.wait(f"{LIVE_CARDS}.length >= 3", 30)
    time.sleep(1.0)
    guard_page(c, "fleet roles")
    roles = {"live-card": c.js(f"{LIVE_CARDS}.length"), "live-tab": c.js("document.querySelectorAll('[data-testid=\"roles-live-tab\"]').length"),
             "section-tab": counts(c, ("section-tab",))["section-tab"], "legacy-frame": c.js("document.querySelectorAll('iframe.legacy-frame').length")}
    return {"live": live, "machines": machines, "roles": roles}


def conflict(rig) -> None:
    """Both harnesses edit shop/basket.py: the implementer here (a feed frame), the member's reviewer (its relay);
    repo-relative, so no machine's path is drawn (3.1.7.0 R2)."""
    from halo_harness.peers.identity import harness
    from tests.helpers.studio_fleet_member import REVIEWER
    from tests.helpers.studio_fleet_rig import MEMBER, MEMBER_SID
    a = rig.agent("Implement")
    rig.server.events.publish({"session_id": rig.act.session_id, "harness": harness()["id"], "event": "agent_state", "agent_id": a["agent_id"],
                               "ts": time.time(), "data": {**a, "current": "Edit: basket.py"}})
    rig.hub.state.frames(MEMBER, {"link": "rig-link", "frames": [{"session_id": MEMBER_SID, "event": "agent_state", "agent_id": REVIEWER["agent_id"],
                                                                 "ts": time.time(), "data": {**REVIEWER, "state": "running", "current": "Edit: basket.py"}}]})


def settle(c, png: Path) -> int:
    c.wait("!document.querySelector('.toast')", 10)  # the toasts fade first
    time.sleep(1.5)
    guard_page(c, png.stem)
    return c.shot(png)


def shoot_live(c, rig, png: Path) -> int:
    open_live(c, rig)
    conflict(rig)
    c.wait("!!document.querySelector('[data-testid=\"fleet-conflict-edge\"]')", 30)
    c.wait("document.querySelectorAll('[data-testid=\"live-glance-machine\"]').length === 2", 20)
    c.wait("(document.querySelector('[data-testid=\"agents-attention\"]')?.dataset.count || '0') !== '0'", 20)
    return settle(c, png)


def shoot_machines(c, rig, png: Path) -> int:
    open_machines(c, rig)  # the pair card as it opens (Make a pair code), the rows, both machines in People
    c.wait("!!document.querySelector('[data-testid=\"fleet-settings\"]')", 15)
    return settle(c, png)


def shoot_caps(c, rig, png: Path) -> int:
    """Who can... gridcraft on this machine's Specs page picks the member: its box lit, its card, its server open."""
    from tests.helpers.studio_fleet_caps import specs_of
    from tests.helpers.studio_fleet_member import MEMBER
    open_live(c, rig)
    specs_of(c, rig.hub.state.identity["id"])
    c.click_on("document.querySelector('[data-testid=\"fleet-who-input\"]')")
    c.type_text("gridcraft")
    c.wait("document.querySelectorAll('[data-testid=\"fleet-who-result\"]').length", 15)
    c.click_on("document.querySelector('[data-testid=\"fleet-who-result\"]')")
    card = f"document.querySelector('[data-testid=\"fleet-caps-card\"][data-id=\"{MEMBER}\"]')"
    c.wait(f"!!{card} && !!document.querySelector('[data-testid=\"fleet-box\"][data-who]')", 15)
    c.js(f"{card}.querySelector('[data-testid=\"fleet-caps-server\"]').open = true; 1")
    return settle(c, png)


def shoot_mission(c, rig, png: Path) -> int:
    """R8: the plan drawn on Live (no model: the seeded fake lead), part 3's card in the inspector."""
    from tests.helpers.studio_agents_fleet import press
    from tests.helpers.studio_fleet_mseed import MissionFakes, plan_by_api
    from tests.helpers.studio_fleet_panels import open_strip, seen
    MissionFakes(rig)
    mid = plan_by_api(rig)["mission"]["id"]
    c.go("about:blank")
    c.go(rig.url("fleet", f"&mission={mid}"))  # Runs' Mission panel on it; Live then draws its parts
    c.wait("document.querySelectorAll('[data-testid=\"fleet-mission-part-row\"]').length === 3", 40)
    c.click_on("document.querySelector('[data-testid=\"agents-view-live\"]')")
    part = "document.querySelector('[data-testid=\"fleet-part\"][data-part=\"3\"]')"
    c.wait("document.querySelectorAll('[data-testid=\"fleet-part\"]').length === 3", 40)
    open_strip(c, "roles-inspector")
    seen(c, part)
    press(c, part, "document.querySelector('[data-testid=\"live-inspector\"]')?.dataset.pick === 'part'", 15)
    c.wait("!!document.querySelector('[data-testid=\"live-part\"]')", 10)
    return settle(c, png)


def shoot(c, rig, fleet_png: Path) -> bool:
    shots = {fleet_png: shoot_live(c, rig, fleet_png)}
    for name, fn in (("studio-fleet-panels.png", shoot_machines), ("studio-fleet-capabilities.png", shoot_caps),
                     ("studio-fleet-mission.png", shoot_mission)):  # the mission last: it stays in the rig
        png = fleet_png.with_name(name)
        shots[png] = fn(c, rig, png)
    for path, size in shots.items():
        print(f"{'wrote' if size > 10_000 else 'FAILED'} {path} ({size} bytes)")
    return min(shots.values()) > 10_000


def capture(out: str, as_dom: bool, find_chrome) -> int:
    """Seed, serve, render; the exit code capture_studio.py returns."""
    from tests.helpers.chrome_driver import open_chrome
    from tests.helpers.studio_fleet_rig import StudioFleetRig
    exe = find_chrome()
    if not exe:
        print("no Chrome found")
        return 2
    placeholder()
    with StudioFleetRig() as rig:
        rig.full = False  # 3.3.2.0 R3: the pictures show the quiet arrangement
        placeholder(rig.state)  # the rig's own home: you@studio
        c = open_chrome(exe=exe)  # the driver base: one headless Chrome at a time
        try:
            if as_dom:
                print(json.dumps(dom(c, rig)))
                return 0
            return 0 if shoot(c, rig, Path(out).resolve()) else 1
        finally:
            c.close()
