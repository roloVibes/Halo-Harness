"""tests.helpers.studio_live_feed -- the Feed on Agents -> 4 · Live (Halo 3.6.0.2 R57: what the agents say and do, line by
line, is Live's right drawer titled "Feed", keyed to Live's session; 3 · Map has no feed), shared by the drivers that read
it (tests/helpers/studio_agents_live.py's `feed` step, tests/helpers/studio_map_live_steps.py's `feed`,
tests/helpers/studio_map_takeover_steps.py). Each waits for the value it reads.

    feed_step   the agents_live driver's step: the view bar's Feed button, opened by his hand only, its title; THINK /
                SAY / TALK rows of Live's session; a click on code's box in Live sets the Feed to it (the step-in card
                opens too); 3 · Map has no feed drawer and no "What they think and say" anywhere; Run a goal and History
                open in the Map's own drawer, its title following the page, its button holding still; the palette's
                "Agents: follow agent implementer" (openAgentPanel) from 3 · Map lands on Live's Feed for that agent
"""
from __future__ import annotations

LP = "[data-part=live] "
VIEW = "document.querySelector('[data-testid=agents]')?.dataset.view"
FD = "document.querySelector('[data-testid=map-feed]')"
FEED_BTN = f"document.querySelector('{LP}[data-testid=viewbar-btn][data-panel=live-feed]')"
FEED_PANEL = f"document.querySelector('{LP}[data-testid=live-feed-panel]')"
FEED_SHOWN = f"!!{FD}?.offsetParent"  # the Feed's words on screen (a closed panel stays mounted, hidden; the drivers' full
# mode keeps every panel in one drawer)
LIVE = f"document.querySelector('{LP}[data-testid=agents-live]')"
FILTER = f"{FD}?.querySelector('[data-testid=map-feed-filter]')?.value"


def choose(c, sel: str, value: str) -> None:
    """A select set the way a person's pick reaches React: the value setter, then `change`."""
    c.js(f"(() => {{ const s = document.querySelector('{sel}'); const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, '{value}'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")


def open_feed(c, sid: str) -> None:
    """4 · Live on the session `sid` (picked in "Which session" when another is open too), its Feed opened from the view
    bar's button when it is closed."""
    c.wait(f"{VIEW} === 'live'", 20)
    pick = f"{LP}[data-testid=live-pick]"
    c.wait(f"!!{LIVE}", 20)
    if c.js(f"!!document.querySelector('{pick}') && document.querySelector('{pick}').value !== '{sid}'"):
        choose(c, pick, sid)
    c.wait(f"{LIVE}?.dataset.sid === '{sid}'", 20)
    if not c.js(FEED_SHOWN):
        c.click_on(FEED_BTN)
    try:
        c.wait(FEED_SHOWN, 15)
    except TimeoutError:
        probe = (f"[[...document.querySelectorAll('{LP}.stage-drawer')].map((d) => d.dataset.panelIn), {FEED_BTN}?.getAttribute('aria-pressed'),"
                 f" {FEED_BTN}?.getBoundingClientRect().width, (() => {{ try {{ return localStorage.getItem('halo.studio.layout.agents-live'); }} catch {{ return ''; }} }})(),"
                 f" !!{FD}, {FD}?.offsetParent?.className]")
        raise TimeoutError(f"the Feed did not open: drawers, pressed, width, saved, feed, its parent: {c.js(probe)}")


def live_box(bid: str) -> str:
    return f"document.querySelector('{LP}[data-testid=live-world] [data-map-box=\"{bid}\"]')"


def click_live_box(c, bid: str) -> None:
    """A click on a box of Live's drawing (on its face, clear of its rows' buttons)."""
    b = live_box(bid)
    c.wait(f"!!{b}", 20)
    c.js(f"{b}.scrollIntoView({{block: 'nearest', inline: 'nearest'}}); 1")
    c.click_on(b, 0.5, 0.12)


def close_card(c) -> None:
    """The step-in card a box click opened, closed (its ×), so it covers nothing a later click needs."""
    x = f"document.querySelector('{LP}[data-testid=map-step-in-close]')"
    if c.js(f"!!{x}"):
        c.click_on(x)
        c.wait(f"!document.querySelector('{LP}[data-testid=map-step-in]')", 10)


MP = "[data-part=map] "
MD = f"document.querySelector('{MP}[data-testid=map-drawer-panel]')"
MD_SHOWN = f"!!document.querySelector('{MP}[data-testid=map-drawer]')?.offsetParent"  # the Map drawer's page on screen
MD_BTN = f"document.querySelector('{MP}[data-testid=viewbar-btn][data-panel=map-drawer]')"
RECT = "((e) => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height].map((v) => Math.round(v * 2) / 2); })"


def feed_step(c, rig, lv, rows) -> dict:
    from tests.helpers.studio_agents import key
    out: dict = {}
    rows.reset()
    lv.refresh(map="shop", map_next="shop")
    c.go("about:blank")
    c.wait("location.href === 'about:blank'", 10)
    full, rig.full = rig.full, False  # a person's layout, not the drivers' every-drawer-open door: what opens is read
    try:
        c.go(rig.url("agents", "&view=live"))
    finally:
        rig.full = full
    c.wait(f"{VIEW} === 'live' && {LIVE}?.dataset.sid === '{lv.sid}'", 40)
    c.wait(f"!!{FEED_BTN}", 15)
    out["button"] = c.js(f"[{FEED_BTN}.querySelector('.viewbar-name')?.textContent, {FEED_BTN}.getAttribute('aria-pressed'), {FEED_SHOWN}]")
    open_feed(c, lv.sid)
    out["title"] = c.js(f"{FEED_PANEL}.querySelector('[data-testid=panel-title]')?.textContent")
    lv.think("implementer", "tF1", "The discount has to come before tax.", end=True, ms=600)
    lv.say("implementer", "Applying the discount before tax now.")
    lv.talk("main", "implementer", "Apply the discount before tax in basket.py.", "task", mid="tk-f1")
    kinds = f"[...({FD}?.querySelectorAll('[data-testid=live-row]') || [])].map((r) => r.dataset.kind)"
    try:
        out["kinds"] = c.wait(f"(() => {{ const k = {kinds}; return ['think', 'text', 'talk'].every((x) => k.includes(x)) && k; }})()", 20)
    except TimeoutError:
        raise TimeoutError(f"the Feed's rows: {c.js(kinds)}; it says {c.js(f'{FD}?.innerText.slice(0, 300)')!r}")
    out["sids"] = c.js(f"[{FD}.dataset.sid, {LIVE}.dataset.sid]")
    click_live_box(c, "code")
    out["filter"] = c.wait(f"{FILTER} === 'code' && {FD}.dataset.filter === 'code' && 'code'", 15)
    out["feed_card"] = c.wait(f"document.querySelector('{LP}[data-testid=map-step-in]')?.dataset.target", 10)
    close_card(c)
    c.js("document.activeElement?.blur(); 1")
    key(c, "3")
    c.wait(f"{VIEW} === 'map' && !!document.querySelector('{MP}[data-testid=map-run-goal]')", 30)
    out["map_feed"] = c.js(f"document.querySelectorAll('{MP}[data-testid=map-feed-panel], {MP}[data-testid=map-feed], {MP}[data-panel=map-feed]').length")
    out["map_words"] = c.js("document.body.innerText.includes('What they think and say') || [...document.querySelectorAll('[title], [aria-label]')]"
                            ".some((e) => (e.title + ' ' + (e.getAttribute('aria-label') || '')).includes('What they think and say'))")
    c.wait(f"!!{MD_BTN}", 10)
    before = c.js(f"{RECT}({MD_BTN})")
    out["md_closed"] = c.js(f"[{MD_BTN}.querySelector('.viewbar-name')?.textContent, {MD_SHOWN}]")
    c.click_on(f"document.querySelector('{MP}[data-testid=map-run-goal]')")
    out["goal"] = c.wait(f"!!{MD}?.querySelector('[data-testid=run-goal-drawer]') && !!{MD}.closest('.stage-drawer[data-side=right][data-panel-in=map-drawer]')"
                         f" && [{MD}.querySelector('[data-testid=panel-title]')?.textContent, {MD_BTN}.querySelector('.viewbar-name')?.textContent]", 15)
    out["goal_btn"] = c.js(f"{RECT}({MD_BTN})")
    c.click_on(f"document.querySelector('{MP}[data-testid=map-history-all]')")
    out["history"] = c.wait(f"!!{MD}?.querySelector('[data-testid=live-history-drawer]') && !{MD}.querySelector('[data-testid=run-goal-drawer]')"
                            f" && [{MD}.querySelector('[data-testid=panel-title]')?.textContent, {MD_BTN}.querySelector('.viewbar-name')?.textContent]", 15)
    out["history_btn"] = c.js(f"{RECT}({MD_BTN})")
    out["btn_before"] = before
    c.click_on(f"{MD}.querySelector('[data-testid=live-history-close]')")
    try:
        out["closed"] = c.wait(f"!({MD_SHOWN}) && 'closed'", 10)
    except TimeoutError:
        probe = f"[!!{MD}, !!{MD}?.querySelector('[data-testid=live-history-drawer]'), {MD}?.querySelector('[data-testid=map-drawer]')?.dataset.page]"
        raise TimeoutError(f"History's x: the drawer, History's list, its page: {c.js(probe)}")
    c.click_on(f"document.querySelector('[data-testid=palette-btn], .palette-btn')")
    c.wait("document.activeElement?.classList.contains('palette-input')", 10)
    c.type_text("Agents: follow agent implementer")
    c.wait("[...document.querySelectorAll('[data-testid=palette] .palette-item .palette-label')].some((x) => x.textContent === 'Agents: follow agent implementer')", 15)
    c.key("Enter")
    aid = lv.aid("implementer")
    out["agent_door"] = c.wait(f"{VIEW} === 'live' && {FEED_SHOWN} && {FD}?.dataset.filter === 'agent:{aid}' && [{VIEW}, {FD}.dataset.filter, {FD}.dataset.sid]", 15)
    out["aid"] = aid
    out["away_door"] = away_door(c, rig)
    return out


def away_door(c, rig) -> list:
    """An agent of ANOTHER machine's session, opened from 3 · Map (the palette's "Agents: follow agent night-runner"):
    Live lands on that session (T9, its drawing is in that machine's Studio), never on this machine's session with a
    Feed filtered to an id it does not have (its id `main` is this session's main's too)."""
    from halo_harness.studio import live_api
    from tests.helpers.studio_agents_live_draw import AWAY
    far = {**AWAY, "sessions": [{**AWAY["sessions"][0], "busy": True,
                                 "agents": [{"agent_id": "main", "name": "night-runner", "state": "running"}]}]}
    orig = live_api.view_for

    def view_for(server, state_dir):
        v = orig(server, state_dir)
        return {**v, "harnesses": list(v.get("harnesses") or []) + [far]}
    live_api.view_for = view_for
    try:
        c.go("about:blank")
        c.wait("location.href === 'about:blank'", 10)
        c.go(rig.url("agents", "&view=map"))
        c.wait(f"{VIEW} === 'map'", 40)
        c.click_on("document.querySelector('[data-testid=palette-btn], .palette-btn')")
        c.wait("document.activeElement?.classList.contains('palette-input')", 10)
        c.type_text("Agents: follow agent night-runner")
        c.wait("[...document.querySelectorAll('[data-testid=palette] .palette-item .palette-label')].some((x) => x.textContent === 'Agents: follow agent night-runner')", 30)
        c.key("Enter")
        truth = f"document.querySelector('{LP}[data-testid=live-truth]')"
        try:
            return c.wait(f"{VIEW} === 'live' && {LIVE}?.dataset.sid === 'away-1' && [{VIEW}, {LIVE}.dataset.sid, {truth}?.dataset.state, {FD}?.dataset.filter ?? null]", 20)
        except TimeoutError:
            return c.js(f"[{VIEW}, {LIVE}?.dataset.sid, {truth}?.dataset.state, {FD}?.dataset.filter ?? null]")
    finally:
        live_api.view_for = orig
