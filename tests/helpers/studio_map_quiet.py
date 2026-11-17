"""tests.helpers.studio_map_quiet -- Agents -> 3 · Map is the plan (Halo 3.6.0.2 R24 R33 R55), steps of the driver
tests/helpers/studio_agents_live.py over the same rig (the map `shop` seeded, its box `check` runs the workflow
`review`; the rig's session on `starter`, the default). Each waits for the value it reads; no fixed sleep is a pass
condition.

    quiet     R55: the session runs the workflow review (its reviewer row tagged `crew.workflow`) from starter: on shop
              the one quiet line L3, box check marked "running now in {session}", nothing lit, nothing amber, the old
              live branch's controls gone; Agents' help and the Map panel's help in the new words; [Watch it in Live]
              lands on 4 · Live on that session; on starter, L1
    picker    R24: config crew.map = shop: the picker's options say "· running in {session}" / "· new sessions"; the
              switch "New sessions run on this" is on for shop; a second session on starter: "· running in 2 sessions"
    receipt   R55 S13: the hand switch's receipt names the open session; with none open, "New sessions run on {B}."
    away      R33: a builder_done for review-flow while the page is on Session: LAST written, no section change, no
              map fetched; Alt+2, 3 opens 3 · Map on review-flow
    waits     R33 L2 L4: shop open, a When card open; L2 in both forms; a build of review-flow says L4 in the reserved
              row, nothing moves (the canvas, the boxes, the When card, the switcher), [Open it] opens it; the canvas top
              equal with the row empty, with L2 and with L4
    reread    R33: the same map changed by a build: re-read in place, the When card and the zoom kept, no notice
    still     R55 at 1280 x 800: the canvas top with L3 / L1, without the session, with it again: equal
    race      the tab's first open answered after his pick: the pick stands (openMap: the latest request wins)
"""
from __future__ import annotations

import time
from contextlib import contextmanager

M = "[data-part=map]"
SW = f"document.querySelector('{M} [data-testid=map-switcher]')"
VIEW = "document.querySelector('[data-testid=agents]')?.dataset.view"
LIVE = "document.querySelector('[data-part=live] [data-testid=agents-live]')"
REVIEW = {"workflow": "review", "step": 1, "agent": "reviewer", "saved": True}
RF = {"name": "review-flow", "boxes": [{"id": "review", "workflow": "review"}], "lines": [{"from": "main", "to": "review", "when": "always"}]}
RF_YAML = "format: map/1\nname: review-flow\nboxes:\n- {id: review, workflow: review}\nlines:\n- {from: main, to: review, when: always}\n"
# P4 batch 12: what the top line hides inside its sentence or its row of controls (an unseen copy keeping a room) and
# whether a visible sentence has a gap of more than one space; [hidden parts, a gap, History's Replay drawn]
GAP = ("(() => { const p = document.querySelector('[data-part=map] [data-testid=map-topline]'); if (!p) return 'no line';"
       " const mine = (e) => !e.closest('.mp-notice-twin');"
       " const hid = [...p.querySelectorAll('.mp-topline, .mp-topline *, .mp-topline-acts *')].filter((e) => mine(e) && getComputedStyle(e).visibility === 'hidden').length;"
       " const gap = [...p.querySelectorAll('.mp-topline')].filter(mine).some((e) => /[^ ] {2,}[^ ]/.test(e.innerText));"
       " return [hid, gap, !!p.querySelector('[data-testid=map-lit-replay-last]')]; })()")
OPTS = f"[...({SW}?.options || [])].map((o) => o.textContent)"
TOP = f"document.querySelector('{M} [data-testid=map-scroll]')?.getBoundingClientRect().top"
BOXES = f"Object.fromEntries([...document.querySelectorAll('{M} [data-testid=map-world] [data-map-box]')].map((b) => {{ const r = b.getBoundingClientRect(); return [b.dataset.mapBox, [r.left, r.top]]; }}))"


def t(tid: str) -> str:
    return f"document.querySelector('{M} [data-testid={tid}]')"


def title_of(rig, sid: str) -> str:
    for h in rig.api("GET", "live")[1].get("harnesses") or []:
        for s in h.get("sessions") or []:
            if s.get("session_id") == sid:
                return str(s.get("title") or sid[:8])
    return sid[:8]


def use(rig, name: "str | None") -> None:
    """config crew.map = `name` (None: unset) through the switch's own endpoint."""
    if name:
        rig.api("POST", f"crew/map/{name}/use", {"on": True})
        return
    now = rig.api("GET", "crew/maps")[1].get("next")
    if now:
        rig.api("POST", f"crew/map/{now}/use", {"on": False})


def setup(rig, lv, rows, flow: bool) -> str:
    rows.reset()
    use(rig, None)
    lv.rows["r3v1e2w0"].update(crew=dict(REVIEW) if flow else None, state="running" if flow else "done")
    lv.refresh(map="starter", map_plain=True, map_next=None)
    return title_of(rig, lv.sid)


def to_map(c, rig, name: str) -> None:
    from tests.helpers.studio_agents_live_draw import choose
    c.go("about:blank")
    c.wait("location.href === 'about:blank'", 10)
    c.go(rig.url("agents", "&view=map"))
    c.wait(f"{VIEW} === 'map' && [...({SW}?.options || [])].some((o) => o.value === {name!r})", 40)
    choose(c, f"{M} [data-testid=map-switcher]", name)
    c.wait(f"{SW}.value === {name!r} && !!document.querySelector('{M} [data-testid=map-world] [data-map-box]')", 20)


@contextmanager
def second_session(lv, title: str = "second"):
    """A second open session on this machine (a copy of the rig's row) in GET live."""
    from halo_harness.studio import live_api
    orig = live_api.view_for

    def view_for(server, state_dir):
        v = orig(server, state_dir)
        hs = []
        for h in v.get("harnesses") or []:
            rows = list(h.get("sessions") or [])
            mine = next((r for r in rows if r.get("session_id") == lv.sid), None)
            if mine is not None:
                rows.append({**mine, "session_id": "two-0001", "title": title, "started": (mine.get("started") or 0) - 60})
            hs.append({**h, "sessions": rows})
        return {**v, "harnesses": hs}
    live_api.view_for = view_for
    lv.refresh()
    try:
        yield
    finally:
        live_api.view_for = orig
        lv.refresh()


def built(lv, name: str, added: bool = True, body: "dict | None" = None) -> None:
    lv.frame("main", "builder_done", {"id": f"c-{name}", "outcome": "applied", "wrote": [{"kind": "map", "name": name, "added": added}],
                                      "undo": f"u-{name}", "next": None, "this_session": "starter", "maps": {name: body} if body else {},
                                      "t": time.time()})


def warn_color(sel: str) -> str:
    return (f"(() => {{ const t = {sel}; const p = document.createElement('span'); p.style.color = 'var(--warn)'; t.appendChild(p);"
            f" const warn = getComputedStyle(p).color; p.remove(); return [getComputedStyle(t).color, warn]; }})()")


def quiet(c, rig, lv, rows) -> dict:
    from tests.helpers.studio_agents import key
    out: dict = {"title": setup(rig, lv, rows, flow=True), "sid": lv.sid}
    to_map(c, rig, "shop")
    q = t("map-quiet")
    try:
        out["l3"] = c.wait(f"{q}?.textContent.includes('running the workflow') && {q}.textContent", 30)
    except TimeoutError:
        raise TimeoutError(f"the Map's top line says {c.js(t('map-topline') + '?.textContent')!r}")
    chk = f"document.querySelector('{M} [data-testid=map-world] [data-map-box=check]')"
    out["mark"] = c.wait(f"{chk}?.dataset.runningIn && [{chk}.dataset.runningIn, {chk}.querySelector('[data-testid=map-running-in]')?.textContent || '']", 15)
    out["lit"] = c.js(f"document.querySelectorAll('{M} [data-testid=map-world] [data-map-box][data-lit]').length")
    out["gone"] = c.js("document.querySelectorAll('[data-testid=map-lit-pick], [data-testid=map-show-running], [data-testid=map-lit-show-nomap], .mp-amber').length")
    out["color"] = c.js(warn_color(q))
    c.js("document.activeElement?.blur(); 1")
    key(c, "?")
    out["help"] = c.wait("document.querySelector('[data-testid=section-help]')?.textContent", 10)
    c.click_on("document.querySelector('[data-testid=section-help-ok]')")
    c.wait("!document.querySelector('[data-testid=section-help]')", 10)
    c.click_on(f"document.querySelector('{M} [data-testid=map-main-panel] [data-testid=panel-help-btn]')")
    out["panel_help"] = c.wait("document.querySelector('[data-testid=panel-help]')?.textContent", 10)
    c.click_on(f"document.querySelector('{M} [data-testid=map-main-panel] [data-testid=panel-help-btn]')")
    c.click_on(t("map-watch-live"))
    out["watch"] = c.wait(f"{VIEW} === 'live' && {LIVE}?.dataset.sid === {lv.sid!r} && [{VIEW}, {LIVE}.dataset.sid]", 20)
    from tests.helpers.studio_agents_live_draw import choose
    c.click_on("document.querySelector('[data-part=live] [data-testid=agents-view-map]')")
    c.wait(f"{VIEW} === 'map'", 15)
    choose(c, f"{M} [data-testid=map-switcher]", "starter")
    out["l1"] = c.wait(f"{SW}.value === 'starter' && {q}?.textContent.includes('runs on this map now') && {q}.textContent", 20)
    return out


def picker(c, rig, lv, rows) -> dict:
    out: dict = {"title": setup(rig, lv, rows, flow=False)}
    to_map(c, rig, "starter")
    out["fresh"] = c.wait(f"{OPTS}.some((x) => x.includes(' · running in ')) && {OPTS}", 20)
    use(rig, "shop")
    out["options"] = c.wait(f"{OPTS}.some((x) => x.endsWith(' · new sessions')) && {OPTS}", 20)
    from tests.helpers.studio_agents_live_draw import choose
    choose(c, f"{M} [data-testid=map-switcher]", "shop")
    uses = t("map-uses")
    out["switch"] = c.wait(f"{SW}.value === 'shop' && [{uses}.getAttribute('aria-checked'), {uses}.closest('label').textContent]", 15)
    with second_session(lv):
        out["two"] = c.wait(f"{OPTS}.find((x) => x.startsWith('starter') && x.includes('running in 2 sessions')) || ''", 20)
    use(rig, None)
    return out


def receipt(c, rig, lv, rows) -> dict:
    out: dict = {"title": setup(rig, lv, rows, flow=False)}
    to_map(c, rig, "shop")
    line = f"{t('map-receipt')}?.querySelector('.cw-line')"
    c.click_on(t("map-uses"))
    out["s13"] = c.wait(f"{line}?.textContent.includes('keeps running') && [{line}.textContent, !!{t('map-undo')}]", 20)
    rows.hide(lv.sid)
    from tests.helpers.studio_agents_live_draw import choose
    c.wait(f"!{t('map-quiet')}", 20)  # the page has read that no session is open
    choose(c, f"{M} [data-testid=map-switcher]", "ship-it")
    c.wait(f"{SW}.value === 'ship-it' && {t('map-uses')}?.getAttribute('aria-checked') === 'false'", 15)
    c.click_on(t("map-uses"))
    out["none"] = c.wait(f"{line}?.textContent.includes('ship-it') && {line}.textContent", 20)
    rows.reset()
    use(rig, None)
    return out


def away(c, rig, lv, rows) -> dict:
    from halo_harness.crew import store
    from tests.helpers.studio_agents_live import alt
    from tests.helpers.studio_agents import key
    setup(rig, lv, rows, flow=False)
    store.write_text(store.path_for("map", "review-flow", state_dir=rig.state), RF_YAML)
    out: dict = {}
    c.go("about:blank")
    c.wait("location.href === 'about:blank'", 10)
    c.go(rig.url("session"))
    c.wait("!!document.querySelector('[data-testid=session-lit-line]')?.dataset.state", 40)
    c.js("localStorage.setItem('halo.studio.map-open', 'starter'); 1")
    time.sleep(2)  # the map file's own files_changed (written above) has passed: what is tapped is the frame's doing
    gets, untap = _tap_gets()
    try:
        built(lv, "review-flow", body=RF)
        out["last"] = c.wait("localStorage.getItem('halo.studio.map-open') === 'review-flow' && 'review-flow'", 10)
        time.sleep(1)  # a read the frame would start lands within this; what the server served is read, not timed
        # the Map's own read is `crew/map/<name>` (openMap); Session's just-built drawing reads softly (P3, R28: `soft=1`)
        out["fetched"] = [p for p in gets if p.startswith("crew/map/") and "soft" not in p]
        out["soft"] = [p for p in gets if p.startswith("crew/map/") and "soft" in p]
    finally:
        untap()
    out["section"] = c.js("document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent || ''")
    alt(c, 2)
    c.wait(f"!!{VIEW}", 20)
    c.js("document.activeElement?.blur(); 1")
    key(c, "3")
    out["opened"] = c.wait(f"{VIEW} === 'map' && {SW}?.value === 'review-flow' && {SW}.value", 30)
    return out


def waits(c, rig, lv, rows) -> dict:
    out: dict = {"title": setup(rig, lv, rows, flow=False)}
    to_map(c, rig, "shop")
    q = t("map-quiet")
    c.wait(f"!{q} && !!{t('map-notice-row')}", 20)
    out["top_empty"] = c.js(TOP)
    use(rig, "shop")
    out["l2_one"] = c.wait(f"{q}?.textContent.includes('new sessions run on this map') && {q}.textContent", 20)
    out["top_l2"] = c.js(TOP)
    with second_session(lv):
        out["l2_two"] = c.wait(f"{q}?.textContent.startsWith('2 sessions') && {q}.textContent", 20)
        out["top_l2_two"] = c.js(TOP)
    c.wait(f"!{q}?.textContent.startsWith('2 sessions')", 20)
    label = f"document.querySelector('{M} [data-testid=map-world] [data-testid=map-label][data-from=main][data-to=code]')"
    c.js(f"{label}.click(); 1")  # pressed where it is: a scroll here would move the tops read before it (at 1280 x 800)
    card = "document.querySelector('[data-testid=map-when-card]')"
    c.wait(f"!!{card}", 10)
    before, top = c.js(BOXES), c.js(TOP)
    built(lv, "review-flow", body=RF)
    n = t("map-built-notice")
    out["notice"] = c.wait(f"{n}?.textContent", 20)
    after = c.js(BOXES)
    out["moved"] = sorted(k for k, r in after.items() if k in before and max(abs(a - b) for a, b in zip(r, before[k])) > 0.5)
    out["top_l4"] = [top, c.js(TOP)]
    out["still"] = [c.js(f"{SW}.value"), c.js(f"!!{card}"), c.js("document.querySelector('[data-testid=\"section-tab\"][aria-selected=\"true\"]')?.textContent || ''")]
    c.js(f"{t('map-built-open')}.click(); 1")  # the When card's pop-up may sit over the row: the button, pressed
    out["opened"] = c.wait(f"{SW}.value === 'review-flow' && !{n} && {SW}.value", 20)
    use(rig, None)
    return out


def reread(c, rig, lv, rows) -> dict:
    from halo_harness.crew import store
    from tests.helpers.studio_map_live import MAP
    setup(rig, lv, rows, flow=False)
    to_map(c, rig, "shop")
    label = f"document.querySelector('{M} [data-testid=map-world] [data-testid=map-label][data-from=main][data-to=code]')"
    c.js(f"{label}.scrollIntoView({{block: 'center', inline: 'center'}}); {label}.click(); 1")
    card = "document.querySelector('[data-testid=map-when-card]')"
    c.wait(f"!!{card}", 10)
    zoom = f"document.querySelector('{M} [data-testid=map-world]')?.dataset.zoom"
    out: dict = {"zoom_before": c.js(zoom)}
    path = store.path_for("map", "shop", state_dir=rig.state)
    store.write_text(path, MAP.replace("- {id: notes, agent: writer}", "- {id: notes, agent: writer}\n- {id: extra, agent: tester}"))
    try:
        built(lv, "shop", added=False)
        out["drawn"] = c.wait(f"!!document.querySelector('{M} [data-map-box=extra]') && 'extra'", 20)
        out["card"] = c.js(f"{card}?.querySelector('b')?.textContent || ''")
        out["zoom_after"] = c.js(zoom)
        out["notice"] = c.js(f"!!{t('map-built-notice')}")
    finally:
        store.write_text(path, MAP)
    return out


def still(c, rig, lv, rows) -> dict:
    """R55 at 1280 x 800, no scroll made: the quiet line comes and goes as a session runs a workflow from shop (L3) or
    runs on starter (L1), and ends; the canvas top is read with the line, without the session, with the line again."""
    from tests.helpers.studio_agents_live_draw import choose
    c.call("Emulation.setDeviceMetricsOverride", width=1280, height=800, deviceScaleFactor=1, mobile=False)
    try:
        out: dict = {"title": setup(rig, lv, rows, flow=True)}
        to_map(c, rig, "shop")
        q = t("map-quiet")
        for name, words in (("shop", "running the workflow"), ("starter", "runs on this map now")):
            choose(c, f"{M} [data-testid=map-switcher]", name)
            said = f"{SW}.value === {name!r} && {q}?.textContent.includes({words!r})"
            c.wait(said, 20)
            tops, gaps = [c.js(TOP)], [c.js(GAP)]
            rows.hide(lv.sid)
            c.wait(f"!{q}", 20)
            tops.append(c.js(TOP))
            gaps.append(c.js(GAP))
            rows.reset()
            c.wait(said, 20)
            tops.append(c.js(TOP))
            gaps.append(c.js(GAP))
            out[name] = tops
            out[f"{name}_gaps"] = gaps
        return out
    finally:
        rows.reset()
        c.call("Emulation.setDeviceMetricsOverride", width=1500, height=900, deviceScaleFactor=1, mobile=False)


def race(c, rig, lv, rows) -> dict:
    """The tab's own first open (`&map=starter`) answered after his pick of shop: the pick stands (latest request wins)."""
    from halo_harness.studio import api as A
    from tests.helpers.studio_agents_live_draw import choose
    setup(rig, lv, rows, flow=False)
    import threading
    picked = threading.Event()
    orig, served, order = A.dispatch, [], []  # order: what happened, in turn (P4 batch 12: the test asserts it)

    def slow(req):
        if req.method == "GET" and str(req.path) == "crew/map/starter" and not req.query and not served:
            picked.wait(30)  # the first open's answer is held until his pick is drawn (an event, not a delay)
            try:
                return orig(req)
            finally:
                served.append(1)
                order.append("first open answered")
        return orig(req)
    A.dispatch = slow
    try:
        c.go("about:blank")
        c.wait("location.href === 'about:blank'", 10)
        c.go(rig.url("agents", "&view=map&map=starter"))
        c.wait(f"{VIEW} === 'map' && [...({SW}?.options || [])].some((o) => o.value === 'shop')", 40)
        choose(c, f"{M} [data-testid=map-switcher]", "shop")
        c.wait(f"{SW}.value === 'shop' && !!document.querySelector('{M} [data-map-box=check]')", 20)
        order.append("his pick drawn")
        picked.set()
        end = time.time() + 30
        while not served and time.time() < end:
            time.sleep(0.05)
        out: dict = {"served": bool(served), "order": list(order)}
        # the late answer has reached the page (its resource entry is complete), then two frames for React to draw it
        c.wait("performance.getEntriesByType('resource').some((e) => /\\/crew\\/map\\/starter$/.test(e.name))", 20)
        c.js("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => r(1))))")
        out["after"] = [c.js(f"{SW}.value"), c.js(f"!!document.querySelector('{M} [data-map-box=check]')")]
        return out
    finally:
        picked.set()
        A.dispatch = orig


def _tap_gets():
    """The GETs the page makes, at the server's dispatcher, each with its query's keys ("crew/map/x?soft")."""
    from halo_harness.studio import api as A
    seen, orig = [], A.dispatch

    def rec(req):
        if req.method == "GET":
            seen.append(str(req.path) + ("?" + ",".join(sorted(req.query or {})) if req.query else ""))
        return orig(req)
    A.dispatch = rec
    return seen, lambda: setattr(A, "dispatch", orig)


def _own(fn):
    """A step whose keys are its own ("quiet.l3"): the driver merges every step's dict into one."""
    def step(*a):
        return {f"{fn.__name__}.{k}": v for k, v in (fn(*a) or {}).items()}
    step.__name__ = fn.__name__
    return step


STEPS = tuple(_own(f) for f in (quiet, picker, receipt, away, waits, reread, still, race))
