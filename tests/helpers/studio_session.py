"""tests.helpers.studio_session -- the Session dashboard (Halo 3.1.4.0 R2)
driven through real keys and clicks in headless Chrome on the driver base
(tests/helpers/chrome_driver.Driver), over tests/helpers/studio_fleet_rig.py
(this harness's real session with three agents mid-work, a member harness
`kali@lab` with two) plus a second local session (the remote tests' fake
session behind the real Controller). tests/test_studio_session.py and
tests/test_studio_session_links.py run it as a subprocess with a scrubbed
environment:

    python -m tests.helpers.studio_session dash    landing (live / nothing live), the six panels, the map of this
                                                   harness only, the working node lit and selected, Cost, Activity,
                                                   Attention, `&session=<id>`, J / K, Alt+4 (Fleet keeps both
                                                   harnesses) and Alt+6; `/studio`'s opener focusing the open page
    python -m tests.helpers.studio_session links   the rail click rule, the map menu's Open in Session, the Roles Live
                                                   tab's Watch in Session, the Orchestra run line's (studio_session_links.py)

The last stdout line is a JSON object of what it saw (exit 2: no Chrome).
No model is called."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402

FAKE_SID = "fakesecond0000000000000000000002"
TAB = "document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent || ''"
LIVE = ("queued", "running", "waiting", "paused")


def inside(scope: str, testid: str) -> str:
    """Every `testid` inside the panel (or section) `scope`."""
    return f"document.querySelectorAll('[data-testid=\"{scope}\"] [data-testid=\"{testid}\"], [data-section=\"{scope}\"] [data-testid=\"{testid}\"]')"


# 3.1.5.0 R3: Agent starts as a strip; the selected agent is the map's selected node (its key and state)
AGENT = "document.querySelector('[data-testid=\"session-map\"] [data-testid=\"fleet-node\"][data-selected]')"
COST = "document.querySelector('[data-testid=\"session-cost-detail\"]')"


def url(rig, query: str = "") -> str:
    """The rig's Studio at `/?<query>&tour=off` (no welcome card), with its token."""
    q = f"?{query}&tour=off" if query else "?tour=off"
    return f"http://127.0.0.1:{rig.server.server_address[1]}/{q}#t={rig.server.token}"


def alt(c, n: int) -> None:
    """Alt+<n>, the section keys."""
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key=str(n), code=f"Digit{n}", windowsVirtualKeyCode=48 + n, modifiers=1)


def second_session(rig):
    """A second session of this harness (idle, its main agent only), registered the way the TUI registers."""
    from halo_harness.controller import Controller
    from halo_harness.remote import runtime
    from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
    from tests.helpers.studio_fleet_rig import wait_for
    ctl = Controller(session=FakeSession(FAKE_SID), cwd=rig.proj, registry=FakeRegistry()).start()
    act = runtime.start_for_controller(ctl)
    rig.closers.append(lambda: (runtime.stop_for(ctl), ctl.quit()))
    wait_for(lambda: any(s.get("session_id") == FAKE_SID for h in rig.api("GET", "fleet")[1].get("harnesses", []) if h.get("local")
                         for s in h.get("sessions") or []), 20)
    return act


def local_view(rig) -> dict:
    return next((h for h in rig.api("GET", "fleet")[1].get("harnesses", []) if h.get("local")), {})


def landing(c, rig) -> dict:
    """Nothing saved: a live session here lands on Session; nothing live lands on Roles (the boot mark, pinned)."""
    from halo_harness.studio import session_open
    out: dict = {}
    c.go(url(rig))
    out["landing_live"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 30) or c.js(TAB)
    out["boot_live"] = c.js("document.documentElement.dataset.liveSession || ''")
    saved = session_open.newest_live
    session_open.newest_live = lambda: ""
    try:
        c.js("localStorage.clear(); 1")
        c.go(url(rig, "again=1"))
        out["landing_none"] = c.wait(f"{TAB}.startsWith('Roles') && {TAB}", 30) or c.js(TAB)
        out["boot_none"] = c.js("document.documentElement.dataset.liveSession")
    finally:
        session_open.newest_live = saved
    c.js("localStorage.clear(); 1")
    return out


def dash(c, rig) -> dict:
    from halo_harness.fleet.identity import harness
    out: dict = {}
    hid, sid = harness()["id"], rig.act.session_id
    c.go(url(rig, "mode=session"))
    panels = ["session-map", "session-activity", "session-attention", "session-agent", "session-cost", "session-live"]
    c.wait(" && ".join(f"document.querySelectorAll('[data-testid=\"{p}\"]').length === 1" for p in panels), 30)
    out["panels"] = c.js("[" + ", ".join(f"document.querySelectorAll('[data-testid=\"{p}\"]').length" for p in panels) + "]")
    out["abouts"] = c.js("document.querySelectorAll('[data-section=\"session\"] [data-testid=\"panel-about\"]').length")
    view = local_view(rig)
    want_nodes = sum(len(s.get("agents") or []) for s in view.get("sessions") or [])
    c.wait(f"{inside('session-map', 'fleet-node')}.length === {want_nodes} && {inside('session-map', 'fleet-session')}.length === 2", 30)
    out["boxes"] = c.js(f"[...{inside('session-map', 'fleet-box')}].map((b) => b.querySelector('.fm-box-label').textContent)")
    out["nodes"], out["want_nodes"] = c.js(f"{inside('session-map', 'fleet-node')}.length"), want_nodes
    out["cards"] = c.js(f"{inside('session-map', 'fleet-session')}.length")
    out["foreign"] = c.js(f"[...{inside('session-map', 'fleet-node')}].filter((n) => !n.dataset.key.startsWith('{hid}|')).length")
    out["working"] = c.js(f"[...{inside('session-map', 'fleet-node')}].filter((n) => n.dataset.motion === 'working').length")
    out["selected"] = c.wait(f"{AGENT}?.dataset.key", 20)
    out["selected_state"] = c.js(f"{AGENT}?.dataset.state")
    out["selected_lit"] = c.js(f"[...{inside('session-map', 'fleet-node')}].find((n) => n.dataset.selected)?.dataset.motion")
    out["chosen_card"] = c.wait(f"[...{inside('session-map', 'fleet-session')}].find((n) => n.dataset.chosen)?.dataset.sid", 10)
    out["sid"], out["hid"] = sid, hid
    out["cost_session"] = c.wait(f"{COST}?.dataset.session", 15)
    out["cost_model"] = c.js("document.querySelector('[data-testid=\"session-cost-model\"]')?.textContent")
    out["cost_agents"] = c.js("document.querySelector('[data-testid=\"session-cost-agents\"]')?.textContent")
    out["cost_usd"] = c.js("document.querySelector('[data-testid=\"session-cost-usd\"]')?.textContent")
    from tests.helpers.studio_fleet_panels import open_strip
    open_strip(c, "session-activity")  # 3.1.5.0 R3: Activity and Attention start as strips under Cost
    open_strip(c, "session-attention")
    live = [a for a in rig.agents() if a.get("state") in LIVE]
    out["want_lanes"] = len(live)
    out["lanes"] = c.wait(f"{inside('session-activity', 'fleet-lane')}.length === {len(live)} && {len(live)}", 20) or c.js(f"{inside('session-activity', 'fleet-lane')}.length")
    out["lane_keys_here"] = c.js(f"[...{inside('session-activity', 'fleet-lane')}].every((l) => l.dataset.key.startsWith('{hid}|{sid}|'))")
    c.wait(f"{inside('session-activity', 'fleet-log-line')}.length > 0", 20)
    out["log_who"] = c.js(f"[...new Set([...{inside('session-activity', 'fleet-log-line')}].map((l) => l.querySelector('.fac-who').textContent.split(' · ')[0]))]")
    out["attn_here"] = c.js(f"{inside('session-attention', 'fleet-attn-row')}.length")
    out["attn_empty"] = c.js(f"{inside('session-attention', 'fleet-attn-empty')}.length")
    x, y, w, h = c.rect("document.querySelector('[data-testid=\"session-map\"] .fm-scroll')")
    c.click(x + w - 20, y + h - 20)  # the map's empty corner: the panel takes J / K
    hops = []
    for _ in range(4):
        before = c.js(f"{AGENT}?.dataset.key")
        c.key("j")
        hops.append(c.wait(f"{AGENT}?.dataset.key !== '{before}' && {AGENT}.dataset.key", 5) or before)
    out["hops_here"] = all(str(k).startswith(hid + "|") for k in hops)
    c.go(url(rig, f"mode=session&session={FAKE_SID}"))
    out["deep_agent"] = c.wait(f"{AGENT}?.dataset.key?.includes('|{FAKE_SID}|') && {AGENT}.dataset.key", 30)
    out["deep_cost"] = c.wait(f"{COST}?.dataset.session === '{FAKE_SID}' && {COST}.dataset.session", 15)
    out["deep_card"] = c.js(f"[...{inside('session-map', 'fleet-session')}].find((n) => n.dataset.chosen)?.dataset.sid")
    alt(c, 4)
    out["alt4"] = c.wait(f"{TAB}.startsWith('Fleet') && {TAB}", 10)
    c.wait(f"{inside('fleet', 'fleet-box')}.length === 2", 30)
    out["fleet_boxes"] = c.js(f"[...{inside('fleet', 'fleet-box')}].map((b) => b.querySelector('.fm-box-label').textContent)")
    out["fleet_attn"] = c.wait(f"{inside('fleet', 'fleet-attn-row')}.length", 20)
    alt(c, 6)
    out["alt6"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["back_boxes"] = c.js(f"{inside('session-map', 'fleet-box')}.length")
    return out


def focus(c, rig) -> dict:
    """`/studio` (and `halo studio --session`) on a running Studio: the open page, on Fleet, switches to Session on that session."""
    import json
    import time
    from halo_harness.privateio import write_private_atomic
    from halo_harness.studio import launch
    from halo_harness.studio.edit_open import describe, open_edit
    from halo_harness.studio.events import bridge_for
    from halo_harness.studio.server import studio_info_path
    from halo_harness.studio.session_open import SectionTarget
    out: dict = {}
    opened: list = []
    launch._open = lambda u: opened.append(u) or True  # a focused page needs no new tab; record any
    write_private_atomic(studio_info_path(rig.state), json.dumps({"pid": 0, "port": rig.server.server_address[1], "token": rig.server.token}))
    c.go(url(rig, "mode=fleet&focus=1"))
    c.wait(f"{TAB}.startsWith('Fleet')", 30)
    end = time.time() + 15
    while time.time() < end and bridge_for(rig.server).listeners() < 1:
        time.sleep(0.1)
    r = open_edit(SectionTarget("session", FAKE_SID, "this session"), cwd=rig.proj, state_dir=rig.state)
    out["focus_how"], out["focus_line"] = r["how"], describe(r)
    out["focus_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 15)
    out["focus_agent"] = c.wait(f"{AGENT}?.dataset.key?.includes('|{FAKE_SID}|') && {AGENT}.dataset.key", 20)
    out["focus_tabs_opened"] = len(opened)
    return out


class SessionDriver(Driver):
    """`dash` and `links` over tests/helpers/studio_fleet_rig.py and a second local session."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_fleet_rig import StudioFleetRig
        with StudioFleetRig() as rig:
            second_session(rig)
            if self.argv[:1] == ["links"]:
                from tests.helpers.studio_session_links import links
                yield ((links, (c, rig)),)
            else:
                yield ((landing, (c, rig)), (dash, (c, rig)), (focus, (c, rig)))


if __name__ == "__main__":
    sys.exit(SessionDriver(sys.argv[1:]).main())
