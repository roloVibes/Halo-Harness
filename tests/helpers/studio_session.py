"""tests.helpers.studio_session -- the Session dashboard (Halo 3.1.4.0 R2)
driven through real keys and clicks in headless Chrome on the driver base
(tests/helpers/chrome_driver.Driver), over tests/helpers/studio_session_rig.py
(this harness's real session with three agents mid-work) plus a second local session (the remote tests' fake
session behind the real Controller). tests/test_studio_session.py and
tests/test_studio_session_links.py run it as a subprocess with a scrubbed
environment:

    python -m tests.helpers.studio_session dash    landing (live / nothing live), the six panels, the map of this
                                                   harness only, the working node lit and selected, Cost, Activity,
                                                   Attention, `&session=<id>`, J / K, Alt+2 (Agents -> Live: the same
                                                   two sessions) and Alt+1 (Session, the first tab); `/studio`'s opener focusing the open page
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
# parenthesised: `{TAB}.startsWith(...)` used to parse as `textContent || ''.startsWith(...)`, which answered the
# CURRENT tab's text at once, so every wait on a tab switch never waited (the /studio focus check flaked on
# the slow runners whenever the switch had not landed yet)
TAB = "(document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent || '')"
LIVE = ("queued", "running", "waiting", "paused")


def open_strip(c, pid: str) -> None:
    """3.1.4.0 R1: a panel that starts closed opens with one click; 3.6.0.0 R0a: its button in the view bar (the strips
    went). A panel already open stays as it is. (3.6.0.0 R5: moved here from studio_live_panels.py, which went with Live.)"""
    btn = f"document.querySelector('.section-view:not([hidden]) [data-testid=\"viewbar-btn\"][data-panel=\"{pid}\"]')"
    cell = f"document.querySelector('.section-view:not([hidden]) .ws-cell[data-panel=\"{pid}\"] .panel-body:not([hidden])')"
    c.wait(f"!!{btn} || !!{cell}", 30)
    if not c.js(f"!!{cell}"):
        c.js(f"(() => {{ const el = {btn}; if (el) el.scrollIntoView({{block: 'center', inline: 'nearest'}}); return !!el; }})()")
        c.click_on(btn)
        c.wait(f"!!{cell}", 10)


def inside(scope: str, testid: str) -> str:
    """Every `testid` inside the panel (or section) `scope`."""
    return f"document.querySelectorAll('[data-testid=\"{scope}\"] [data-testid=\"{testid}\"], [data-section=\"{scope}\"] [data-testid=\"{testid}\"]')"


# BOOT_HOP (3.4.1.3, CI red on 30cc5bcc): a Studio page opened straight from another Studio page now and then (1 in 12
# runs at HALO_STUDIO_SLOW_MS=400, on 3.4.1.2 too) took studio.js from Chrome's memory cache and never ran it: no
# error, the owner salt still on <html>, an empty #root. Through about:blank first, the old page is gone before it loads.
def boot_go(c, u: str) -> None:
    c.go("about:blank")
    c.wait("location.href === 'about:blank'", 10)
    c.go(u)


# the page's errors, for the message of a page that did not boot
ERRS_JS = ("window.__errs = []; addEventListener('error', (e) => window.__errs.push(String(e.message || e.error)));"
           " addEventListener('unhandledrejection', (e) => window.__errs.push('rejected: ' + String(e.reason)));")
# 3.1.5.0 R3: Agent starts as a strip; the selected agent is the map's selected node (its key and state)
# 3.6.0.0 R5: the selected agent is the Agent panel's (the old tree's selected node went with the tree)
AGENT = "document.querySelector('[data-section=\"session\"] [data-testid=\"fleet-agent-detail\"]')"
COST = "document.querySelector('[data-testid=\"session-cost-detail\"]')"


def url(rig, query: str = "") -> str:
    """The rig's Studio at `/?<query>&tour=off`, with its token (3.3.2.0 R2: no expanded rail is needed; 3.3.16.0 R2:
    the fleet's tree is Agents -> Live)."""
    from tests.helpers.studio_full import full  # 3.3.2.0 R3: every panel open, the arrangement these checks read
    q = f"?{query}&tour=off" if query else "?tour=off"
    return full(f"http://127.0.0.1:{rig.server.server_address[1]}/{q}#t={rig.server.token}")


def alt(c, n: int) -> None:
    """Alt+<n>, the section keys."""
    for kind in ("keyDown", "keyUp"):
        c.call("Input.dispatchKeyEvent", type=kind, key=str(n), code=f"Digit{n}", windowsVirtualKeyCode=48 + n, modifiers=1)


def second_session(rig):
    """A second session of this harness (idle, its main agent only), registered the way the TUI registers. 3.6.0.2 R1:
    as started a minute BEFORE the rig's session, so the rig's (working) session is the newest open one, the one
    Session draws and Cost speaks of when nothing is picked."""
    from halo_harness.controller import Controller
    from halo_harness.peers import local_view
    from halo_harness.remote import registry, runtime
    from tests.helpers.fake_remote_session import FakeRegistry, FakeSession
    from tests.helpers.studio_session_rig import wait_for
    ctl = Controller(session=FakeSession(FAKE_SID), cwd=rig.proj, registry=FakeRegistry()).start()
    act = runtime.start_for_controller(ctl)
    rig.closers.append(lambda: (runtime.stop_for(ctl), ctl.quit()))
    first = (registry.entry_for(rig.act.session_id) or {}).get("started") or 0
    registry.update(FAKE_SID, started=float(first) - 60)
    local_view.forget()
    wait_for(lambda: any(s.get("session_id") == FAKE_SID for h in rig.api("GET", "live")[1].get("harnesses", []) if h.get("local")
                         for s in h.get("sessions") or []), 20)
    return act


def local_view(rig) -> dict:
    return next((h for h in rig.api("GET", "live")[1].get("harnesses", []) if h.get("local")), {})


def landing(c, rig) -> dict:
    """Nothing saved: a live session here lands on Session; nothing live lands on Roles (the boot mark, pinned)."""
    from halo_harness.studio import session_open
    out: dict = {}
    boot_go(c, url(rig))
    out["landing_live"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 30) or c.js(TAB)
    out["boot_live"] = c.js("document.documentElement.dataset.liveSession || ''")
    saved = session_open.newest_live
    session_open.newest_live = lambda: ""
    try:
        c.js("localStorage.clear(); 1")
        boot_go(c, url(rig, "again=1"))
        out["landing_none"] = c.wait(f"{TAB}.startsWith('Agents') && {TAB}", 30) or c.js(TAB)
        out["boot_none"] = c.js("document.documentElement.dataset.liveSession")
    finally:
        session_open.newest_live = saved
    c.js("localStorage.clear(); 1")
    return out


def dash(c, rig) -> dict:
    from halo_harness.peers.identity import harness
    from tests.helpers.studio_session_map_down import Rows
    out: dict = {}
    hid, sid = harness()["id"], rig.act.session_id
    c.call("Page.addScriptToEvaluateOnNewDocument", source=ERRS_JS)  # a blank page says why
    rows = Rows(rig)
    rows.idle(sid)
    boot_go(c, url(rig, "mode=session"))
    panels = ["session-map", "session-activity", "session-attention", "session-agent", "session-cost", "session-live",
              "session-prompt"]  # 3.3.11.0 R1
    counts = "[" + ", ".join(f"document.querySelectorAll('[data-testid=\"{p}\"]').length" for p in panels) + "]"
    try:
        c.wait(" && ".join(f"document.querySelectorAll('[data-testid=\"{p}\"]').length === 1" for p in panels), 30)
    except TimeoutError:  # say WHICH panel count was wrong (0: not mounted, 2: mounted twice)
        got = dict(zip(panels, c.js(counts) or []))
        page = c.js("[(window.__errs || []).slice(0, 3), document.getElementById('root')?.childElementCount, "
                    "'ownerSalt' in document.documentElement.dataset ? 'the shell never ran' : 'the shell ran']")
        bad = ", ".join(f"{p}={n}" for p, n in got.items() if n != 1)
        raise TimeoutError(f"Session panels not one each: {bad}; tab {c.js(TAB)!r}; errors, #root children, boot: {page!r}")
    out["panels"] = c.js(counts)
    out["abouts"] = c.js("document.querySelectorAll('[data-section=\"session\"] [data-testid=\"panel-title\"][title]:not([title=\"\"])').length")  # 3.3.2.0 R3: the title's tooltip
    # 3.6.0.2 R35: the drawer is Live (hover: was Map), the line-by-line panel Feed (hover: was Live); ids unchanged
    out["titles"] = c.js("""Object.fromEntries(['session-map', 'session-live'].map((p) => {
      const t = document.querySelector(`[data-testid="${p}"] [data-testid="panel-title"]`);
      const b = document.querySelector(`[data-testid="viewbar-btn"][data-panel="${p}"]`);
      return [p, { text: (t?.textContent || '').trim(), title: t?.getAttribute('title') || '',
                   bar: b?.querySelector('.viewbar-name')?.textContent || '', barTitle: b?.getAttribute('title') || '' }]; }))""")
    # 3.6.0.2 R2: an open session between turns is drawn: the rig's session idle first (every agent done, not busy)
    # 3.6.0.2 R15: its agents are the drawing's boxes and the rows inside them (a child is a row in its box, no box of its own)
    drawn = f"[...{inside('session-map', 'session-lit-box')}, ...{inside('session-map', 'session-map-row')}]"
    c.wait(f"{drawn}.length >= 3", 30)
    out["idle_nodes"] = c.js(f"{drawn}.length")
    out["idle_working"] = c.js(f"{drawn}.filter((n) => n.dataset.state === 'working').length")
    rows.reset()  # 3.6.0.0 R5: then at work: the working boxes lit
    c.wait(f"{drawn}.filter((n) => n.dataset.state === 'working').length >= 2", 30)
    out["boxes"] = c.js(f"{inside('session-map', 'fleet-box')}.length")  # 3.5.0.0: no harness box (one machine)
    out["nodes"] = c.js(f"{drawn}.length")
    out["working"] = c.js(f"{drawn}.filter((n) => n.dataset.state === 'working').length")
    out["sid"], out["hid"] = sid, hid
    out["cost_session"] = c.wait(f"{COST}?.dataset.session", 15)
    out["cost_model"] = c.js("document.querySelector('[data-testid=\"session-cost-model\"]')?.textContent")
    out["cost_agents"] = c.js("document.querySelector('[data-testid=\"session-cost-agents\"]')?.textContent")
    out["cost_usd"] = c.js("document.querySelector('[data-testid=\"session-cost-usd\"]')?.textContent")
    open_strip(c, "session-activity")  # 3.1.5.0 R3: Activity and Attention start as strips under Cost
    open_strip(c, "session-attention")
    live = [a for a in rig.agents() if a.get("state") in LIVE]
    out["want_lanes"] = len(live)
    out["lanes"] = c.wait(f"{inside('session-activity', 'fleet-lane')}.length === {len(live)} && {len(live)}", 20) or c.js(f"{inside('session-activity', 'fleet-lane')}.length")
    out["lane_keys_here"] = c.js(f"[...{inside('session-activity', 'fleet-lane')}].every((l) => l.dataset.key.startsWith('{hid}|{sid}|'))")
    c.wait(f"{inside('session-activity', 'fleet-log-line')}.length > 0", 20)
    out["log_who"] = c.js(f"[...new Set([...{inside('session-activity', 'fleet-log-line')}].map((l) => l.querySelector('.fac-who').textContent.split(' · ')[0]))]")
    try:  # the strip's body paints a moment after it opens; GitHub's Windows runner read it before either marker was there
        c.wait(f"{inside('session-attention', 'fleet-attn-row')}.length + {inside('session-attention', 'fleet-attn-empty')}.length > 0", 15)
    except TimeoutError:
        pass  # the counts below say what was there
    out["attn_here"] = c.js(f"{inside('session-attention', 'fleet-attn-row')}.length")
    out["attn_empty"] = c.js(f"{inside('session-attention', 'fleet-attn-empty')}.length")
    boot_go(c, url(rig, f"mode=session&session={FAKE_SID}"))
    out["deep_cost"] = c.wait(f"{COST}?.dataset.session === '{FAKE_SID}' && {COST}.dataset.session", 15)
    # 3.6.0.2 R1: Session draws the session chosen in it, so the Alt keys start from the rig's session chosen (the
    # `&session=` page above draws the second session, main alone; "its map still lit" speaks of the rig's)
    boot_go(c, url(rig, f"mode=session&session={sid}"))
    c.wait(f"{drawn}.length >= 3", 30)  # 3.6.0.2 R15: its boxes and the rows in them
    alt(c, 2)  # 3.6.0.2 R56: Alt+2 opens Agents on Live (a session talked to is open); 3.5.0.0: this machine's sessions only
    out["alt4"] = c.wait(f"{TAB}.startsWith('Agents') && {TAB}", 10)
    out["agents_view"] = c.wait("document.querySelector('[data-testid=\"agents\"]')?.dataset.view", 30)  # 3.6.0.2 R56: the first tab drawn
    out["agents_boxes"] = c.js(f"{inside('agents', 'fleet-box')}.length + {inside('agents', 'live-machine')}.length")
    alt(c, 1)  # 3.1.6.0 R6: Session is the first tab
    out["alt1"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 10)
    out["back_map"] = c.wait(f"{drawn}.length >= 3 && 'lit'", 15)
    return out


def focus(c, rig) -> dict:
    """`/studio` (and `halo studio --session`) on a running Studio: the open page, on Agents -> Live (`?mode=agents`), switches
    to Session on that session."""
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
    write_private_atomic(studio_info_path(rig.state), json.dumps({"pid": 0, "port": rig.server.server_address[1], "token": rig.server.token,
                                                                 "owner_salt": rig.server.owner_salt}))
    boot_go(c, url(rig, "mode=agents&focus=1"))
    c.wait(f"{TAB}.startsWith('Agents')", 30)
    # the state the opener acts on: THIS page's feed open (else the opener can find no page listening and open a tab)
    c.wait("globalThis.__haloStudioLib?.events?.feedState() === 'open'", 15)
    end = time.time() + 15
    while time.time() < end and bridge_for(rig.server).listeners() < 1:
        time.sleep(0.1)
    # A frame sent before the page's subscription reached the server is missed: the door is sent again until the page
    # moves (3 tries, 8 s each).
    for _ in range(3):
        r = open_edit(SectionTarget("session", FAKE_SID, "this session"), cwd=rig.proj, state_dir=rig.state)
        out["focus_how"], out["focus_line"] = r["how"], describe(r)
        try:
            out["focus_tab"] = c.wait(f"{TAB}.startsWith('Session') && {TAB}", 8)
            break
        except TimeoutError:
            out["focus_tab"] = None
    if not out["focus_tab"]:
        raise TimeoutError(f"the page stayed on {c.js(TAB)!r} ({c.js('location.search')!r}); open_edit: {out['focus_how']!r} {out['focus_line']!r}")
    out["focus_agent"] = c.wait(f"{COST}?.dataset.session === '{FAKE_SID}' && '|{FAKE_SID}|'", 20)  # R5: the chosen session
    out["focus_tabs_opened"] = len(opened)
    return out


class SessionDriver(Driver):
    """`dash` and `links` over tests/helpers/studio_session_rig.py and a second local session."""

    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.studio_session_rig import StudioSessionRig
        with StudioSessionRig() as rig:
            second_session(rig)
            if self.argv[:1] == ["links"]:
                from tests.helpers.studio_session_links import links
                yield ((links, (c, rig)),)
            else:
                yield ((landing, (c, rig)), (dash, (c, rig)), (focus, (c, rig)))


if __name__ == "__main__":
    sys.exit(SessionDriver(sys.argv[1:]).main())
