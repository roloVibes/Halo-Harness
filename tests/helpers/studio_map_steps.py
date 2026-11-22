"""tests.helpers.studio_map_steps -- the steps of the Map tab's driver (tests/helpers/studio_map.py). Each waits for the
value it reads; a drag is real pointer events through CDP; the keyboard path is driven too. `follows` (3.6.0.9 V, the
owner's point 34): the open map follows its files -- its own, a box's workflow, a box's agent -- keeping what he has
open, and its own save reads nothing again."""
from __future__ import annotations

import base64
from pathlib import Path

from tests.helpers.scratch_seven import NAME as SEVEN, write_seven
from tests.helpers.studio_agents import key

P = '[data-part="map"] '
VIEW = "document.querySelector('[data-testid=agents]')?.dataset.view"
SHOTS: list = []


def q(sel: str) -> str:
    return f"document.querySelector('{P}{sel}')"


def qa(sel: str) -> str:
    return f"[...document.querySelectorAll('{P}{sel}')]"


def t(name: str) -> str:
    return q(f'[data-testid="{name}"]')


def box(bid: str) -> str:
    return q(f'[data-testid="map-world"] [data-map-box="{bid}"]')


def shot(c, name: str) -> None:
    if SHOTS:
        (Path(SHOTS[0]) / name).write_bytes(base64.b64decode(c.call("Page.captureScreenshot", format="png")["data"]))


def center(c, expr: str, fx: float = 0.5, fy: float = 0.5):
    c.js(f"({expr}).scrollIntoView({{block: 'nearest', inline: 'nearest'}}); 1")  # a person scrolls to what they grab
    x, y, w, h = c.rect(expr)
    return x + w * fx, y + h * fy


def both(c, a: str, b: str):
    """The centres of `a` and `b`, both scrolled into view first (one scroll must not move the other off its point)."""
    for e in (b, a):
        c.js(f"({e}).scrollIntoView({{block: 'nearest', inline: 'nearest'}}); 1")
    (ax, ay, aw, ah), (bx, by, bw, bh) = c.rect(a), c.rect(b)
    return (ax + aw / 2, ay + ah / 2), (bx + bw / 2, by + bh / 2)


def seed(rig) -> None:
    from halo_harness.crew import store
    raw = {"format": "agent/1", "name": "my-reviewer", "does": "Reviews auth changes.", "model": "auto", "uses": ["read"], "careful": "ask-changes"}
    store.write_text(store.path_for("agent", "my-reviewer", state_dir=rig.state), store.dump(raw))
    write_seven(rig.state)  # 3.6.0.5: the steps that edit, drag or lock do it on a map of his of seven boxes


GEOM = f"""(() => {{
  const r = (e) => e.getBoundingClientRect();
  const boxes = {qa('[data-testid="map-world"] [data-map-box]')}.map((b) => [b.dataset.mapBox, r(b)]);
  const labels = {qa('[data-testid="map-label"]')}.map(r);
  const hit = (a, b) => a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1;
  return {{ main: boxes.length && boxes.every(([id, b]) => id === 'main' || b.left > boxes.find(([i]) => i === 'main')[1].right),
            over: labels.filter((l) => boxes.some(([, b]) => hit(l, b))).length + labels.filter((l, i) => labels.some((m, j) => j > i && hit(l, m))).length,
            boxes: boxes.length, labels: labels.length }};
}})()"""


def first(c, rig) -> dict:
    c.go(rig.url("&view=crew"))
    c.wait(f"{VIEW} === 'crew'", 40)
    c.js("document.activeElement?.blur(); 1")
    key(c, "3")
    out = {"view": c.wait(f"{VIEW} === 'map' && {VIEW}", 30)}
    # 3.6.0.5 A11: Auto's tab draws main alone and M1 (AutoPlan.tsx): no box to edit, no line, no switch, no Lock
    c.wait(f"!!{t('map-auto-plan')} && !!{t('map-auto-main')} && !!{t('builder-meta')}", 30)
    out["switch"] = c.js("[...document.querySelectorAll('[data-part=map] [data-testid=agents-views] button')].map((b) => b.innerText)")
    out["first"] = c.js(f"({{map: {t('map-switcher')}.value, dialogs: document.querySelectorAll('[role=dialog]').length,"
                        f" conversation: !!{t('builder-conversation')}, drawer: !!{q('.stage-drawer[data-panel-in=map-add]')},"
                        f" main: !!{t('map-auto-main')}, labels: {qa('[data-testid=map-label]')}.length,"
                        f" boxes: {qa('[data-map-box]')}.map((b) => b.dataset.mapBox), plan: {t('map-auto-plan')}.textContent,"
                        f" uses: !!{t('map-uses')}, lock: !!{t('map-lock')}, goal: !!{t('map-run-goal')}}})")
    shot(c, "studio-map.png")
    # 3.6.0.5: Auto is never edited: the seven labels, the geometry and the builder's hint are read on the scratch map of
    # seven boxes, opened from the switcher right after; the steps after this one drag, chain, key and zoom on it
    c.js(f"(() => {{ const s = {t('map-switcher')}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, '{SEVEN}'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    c.wait(f"{t('map-switcher')}?.value === '{SEVEN}' && {qa('[data-testid=map-label]')}.length === 7", 20)
    out["seven"] = c.js(f"({{labels: {qa('[data-testid=map-label]')}.map((l) => l.innerText), hint: {t('builder-input')}.placeholder}})")
    out["geom"] = c.js(GEOM)
    return out


def open_list(c) -> None:
    btn = f"document.querySelector('{P}[data-testid=viewbar-btn][data-panel=map-add]')"
    if not c.js(f"!!{q('.stage-drawer[data-panel-in=map-add]')}"):
        c.wait(f"!!{btn}", 10)
        c.js(f"{btn}.click(); 1")
    c.wait(f"{qa('[data-testid=map-add-row]')}.length >= 10", 20)


def drag(c, rig) -> dict:
    open_list(c)
    row = q('[data-testid="map-add-row"][data-ref="tester"]')
    (x0, y0), (x1, y1) = both(c, row, box("main"))
    x0 -= c.rect(row)[2] * 0.2  # on the row's text, away from its Add
    c.mouse("mouseMoved", x0, y0)
    c.mouse("mousePressed", x0, y0)
    for i in range(1, 7):
        c.mouse("mouseMoved", x0 + (x1 - x0) * i / 6, y0 + (y1 - y0) * i / 6)
    out = {"lit": c.wait(f"({box('main')}?.dataset.drop && {t('map-strip')}?.dataset.drop) ? [{box('main')}.dataset.drop, {t('map-strip')}.dataset.drop,"
                         f" !!{box('main')}.dataset.dropOn] : null", 10)}
    shot(c, "studio-map-drag.png")
    c.mouse("mouseReleased", x1, y1)
    c.wait(f"!!{t('map-when-card')}", 20)
    out["card"] = c.js(f"{t('map-when-card')}.querySelector('b').innerText")
    c.js(f"{t('map-when-words')}.focus(); 1")
    c.type_text("test")
    shot(c, "studio-map-when.png")
    c.js(f"{t('map-when-save')}.click(); 1")
    out["label"] = c.wait(f"{q('[data-testid=map-label][data-to=tester]')}?.innerText === 'says test' && 'says test'", 20)
    out["receipt"] = c.wait(f"{t('map-receipt')}?.innerText.includes('says test') && {t('map-receipt')}.innerText.split('\\n')[0]", 20)
    out["file"] = [ln for ln in rig.api("GET", f"crew/map/{SEVEN}")[1]["map"]["lines"] if ln["to"] == "tester"]
    return out


def chain(c, rig) -> dict:
    """P8 batch 3 repair (the coordinator's ruling: a goal run's line is in the Map's first draw, a line of its own): the
    drawing is that line (28 px) shorter, and at this rig's 1500 x 900 window (813 px inside) coder's dot and reviewer
    no longer fit in it together. The same two drags and the same checks, in a viewport 900 px tall inside."""
    c.call("Emulation.setDeviceMetricsOverride", width=1500, height=900, deviceScaleFactor=1, mobile=False)
    try:
        return _chain(c, rig)
    finally:
        c.call("Emulation.clearDeviceMetricsOverride")


def _chain(c, rig) -> dict:
    dot = q('[data-testid="map-world"] [data-map-box="coder"] [data-testid="map-dot"]')
    c.wait(f"!!{dot}", 10)
    (x0, y0), (x1, y1) = both(c, dot, box("reviewer"))
    c.drag(x0, y0, x1, y1, steps=8)
    c.wait(f"!!{t('map-when-card')}", 20)
    c.js(f"{t('map-when-always')}.click(); {t('map-when-save')}.click(); 1")
    out = {"chain": c.wait(f"{q('[data-testid=map-label][data-from=coder][data-to=reviewer]')}?.innerText === 'always'", 20)}
    out["cols"] = c.js(f"[{box('coder')}.getBoundingClientRect().left < {box('reviewer')}.getBoundingClientRect().left]")
    dot2 = q('[data-testid="map-world"] [data-map-box="reviewer"] [data-testid="map-dot"]')
    (x0, y0), (x1, y1) = both(c, dot2, box("coder"))
    c.drag(x0, y0, x1, y1, steps=8)
    out["circle"] = c.wait(f"{t('map-error')}?.innerText.includes('circle') && {t('map-error')}.innerText.split('\\n')[0]", 20)
    c.js(f"{t('map-error')}.querySelector('button').click(); 1")
    c.js(f"{t('map-undo')}.click(); 1")
    out["undone"] = c.wait(f"{q('[data-testid=map-label][data-from=coder][data-to=reviewer]')}?.innerText === 'main decides per task'"
                           f" && !{t('map-receipt')} && 'main decides per task'", 20)  # Undo puts back the last change: the When
    return out


def keys(c, rig) -> dict:
    row = q('[data-testid="map-add-row"][data-ref="review"][data-kind="workflow"]')
    c.wait(f"!!{row}", 10)
    c.js(f"{row}.focus(); 1")
    c.key("Enter")
    strip_box = q('[data-testid="map-strip"] [data-map-box="review"]')
    out = {"strip": c.wait(f"!!{strip_box} && {strip_box}.dataset.new === 'true'", 20)}
    c.js(f"{strip_box}.querySelector('[data-testid=map-dot]').focus(); 1")
    c.key("Enter")
    c.wait(f"!!{t('map-pick')}", 10)
    out["pick"] = c.js(f"{qa('[data-testid=map-pick-row]')}.map((b) => b.dataset.to).slice(0, 3)")
    c.js(f"{q('[data-testid=map-pick-row][data-to=main]')}.click(); 1")
    c.wait(f"!!{t('map-when-card')}", 20)
    c.js(f"{t('map-when-ask')}.click(); {t('map-when-save')}.click(); 1")
    c.wait(f"{q('[data-testid=map-label][data-to=review]')}?.innerText === 'only when I ask'", 20)
    c.js(f"{box('review')}.click(); 1")
    out["steps"] = c.wait(f"{box('review')}.querySelector('[data-testid=map-box-steps]')?.innerText.split('\\n')", 10)
    c.mouse("mouseMoved", 5, 5)  # off the map first: the pointer may rest on tester already (Linux fonts), so it enters it
    c.mouse("mouseMoved", *center(c, box("tester")))
    out["hover"] = c.wait(f"{q('[data-testid=map-line][data-to=tester]')}?.classList.contains('hot') && "
                          f"{q('[data-testid=map-line][data-to=coder]')}?.classList.contains('dim')", 10)
    c.mouse("mouseMoved", 5, 5)
    c.js(f"{q('[data-testid=map-label][data-to=review]')}.click(); 1")
    c.wait(f"!!{t('map-when-card')}", 10)
    c.js(f"{t('map-when-remove')}.click(); 1")
    out["back"] = c.wait(f"!!{strip_box} && !{q('[data-testid=map-label][data-to=review]')}", 20)
    return out


def maps(c, rig) -> dict:
    c.js(f"(() => {{ const s = {t('map-switcher')}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, '+'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    c.wait(f"!!{t('map-new-name')}", 10)
    c.js(f"{t('map-new-name')}.focus(); 1")
    c.type_text("release-day")
    c.key("Enter")
    out = {"new": c.wait(f"{t('map-switcher')}?.value === 'release-day' && {qa('[data-testid=map-world] [data-map-box]')}.length", 20)}
    c.js(f"(() => {{ const s = {t('map-switcher')}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, 'auto'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    c.wait(f"{t('map-switcher')}?.value === 'auto' && !!{t('map-uses-default')}", 20)
    opts = f"[...{t('map-switcher')}.options].map((o) => o.textContent)"
    out["fresh_tags"] = c.js(opts)  # 3.6.0.2 R24: a fresh home (crew.map unset) tags no map
    # P4 batch 12: on the default map with none set the switch could change nothing: no switch, the plain sentence
    out["uses_off"] = [c.js(f"!!{t('map-uses')}"), c.js(f"{t('map-uses-default')}?.textContent || ''")]
    # none set: new sessions run on the default, Auto (config never holds it): no switch there; ship-it switched on
    # is config crew.map and tagged; switched off again, new sessions are back on Auto
    c.js(f"(() => {{ const s = {t('map-switcher')}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, 'ship-it'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    c.wait(f"{t('map-switcher')}?.value === 'ship-it' && {t('map-uses')}.getAttribute('aria-checked') === 'false'", 20)
    c.js(f"{t('map-uses')}.click(); 1")
    c.wait(f"{t('map-uses')}.getAttribute('aria-checked') === 'true'", 20)
    out["in_use"] = rig.api("GET", "crew/maps")[1]["next"]
    out["tagged"] = c.wait(f"{opts}.find((x) => x.startsWith('ship-it') && x.endsWith(' · new sessions')) || ''", 20)
    c.js(f"{t('map-uses')}.click(); 1")
    c.wait(f"{t('map-uses')}.getAttribute('aria-checked') === 'false'", 20)
    c.js(f"(() => {{ const s = {t('map-switcher')}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, '{SEVEN}'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    c.wait(f"{t('map-switcher')}?.value === '{SEVEN}' && {qa('[data-testid=map-label]')}.length >= 8", 20)
    c.js(f"{t('map-lock')}.click(); 1")
    out["locked"] = c.wait(f"{t('map-lock')}.getAttribute('aria-checked') === 'true' && {qa('[data-testid=map-dot]')}.length === 0"
                           f" && {qa('[data-testid=map-add]')}.every((b) => b.disabled)", 10)
    c.js(f"{t('map-lock')}.click(); 1")
    c.wait(f"{qa('[data-testid=map-dot]')}.length > 0", 10)
    return out


def zoom(c, rig) -> dict:
    z = f"{t('map-world')}.dataset.zoom"
    c.js(f"{t('canvas-zoom-in')}.click(); 1")
    hand = c.wait(f"{z}", 10)
    btn = f"document.querySelector('{P}[data-testid=viewbar-btn][data-panel=map-add]')"
    c.js(f"{btn}.click(); 1")
    c.wait(f"!{q('.stage-drawer[data-panel-in=map-add]')}", 10)
    out = {"hand": [hand, c.wait(f"{z}", 10)]}
    c.js(f"{t('canvas-fit')}.click(); 1")
    out["fit"] = float(c.wait(f"{z} !== '{hand}' && {z}", 10))
    return out


def builder(c, rig) -> dict:
    c.js(f"(() => {{ const s = {t('map-switcher')}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, 'ship-it'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    c.wait(f"{t('map-switcher')}?.value === 'ship-it' && !!{box('plan')}", 20)
    c.js(f"{t('builder-input')}.focus(); 1")
    c.type_text("send anything touching auth to my-reviewer after the code workflow")
    c.key("Enter")
    out = {"ghost": c.wait(f"{q('[data-testid=map-world] [data-map-box=my-reviewer][data-ghost]')} &&"
                           f" {q('[data-testid=map-line][data-to=my-reviewer][data-ghost]')} &&"
                           f" {q('[data-testid=map-label][data-to=my-reviewer]')}.innerText", 30)}
    out["lines"] = c.js(f"{qa('[data-testid=builder-line]')}.map((l) => l.innerText)")
    c.js(f"{t('builder-apply')}.click(); 1")
    out["applied"] = c.wait(f"!!{box('my-reviewer')} && !{box('my-reviewer')}.dataset.ghost && !!{t('builder-undo')}", 30)
    c.js(f"{t('builder-undo')}.click(); 1")
    out["b_undone"] = c.wait(f"!{box('my-reviewer')}", 30)
    return out


FOLLOW_MAP = """format: map/1
name: follow-map
boxes:
- {id: fw, workflow: follow-flow}
- {id: fa, agent: my-reviewer}
%s
lines:
- {from: main, to: fw, when: always}
- {from: main, to: fa, when: always}
"""


def _pick_map(c, name: str) -> None:
    c.wait(f"[...{t('map-switcher')}.options].some((o) => o.value === '{name}')", 20)
    c.js(f"(() => {{ const s = {t('map-switcher')}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, '{name}'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    c.wait(f"{t('map-switcher')}?.value === '{name}'", 20)


def _until(c, expr: str, timeout: float = 12):
    """True once `expr` holds within `timeout` (a STATE, never a time), else False."""
    try:
        c.wait(f"!!({expr})", timeout)
        return True
    except TimeoutError:
        return False


def follows(c, rig) -> dict:
    import threading
    from halo_harness.crew import store
    from halo_harness.studio import api as A
    from halo_harness.studio.events import bridge_for
    me = dict(store.read(store.path_for("agent", "my-reviewer", state_dir=rig.state)) or {})
    flow = {"format": "workflow/1", "name": "follow-flow", "for": "follow", "steps": []}
    fpath, mpath = store.path_for("workflow", "follow-flow", state_dir=rig.state), store.path_for("map", "follow-map", state_dir=rig.state)

    def steps(n: int) -> None:
        store.write_text(fpath, store.dump({**flow, "steps": [{"name": f"s{i}", "agents": ["my-reviewer"]} for i in range(n)]}))

    def boxes(*ids: str) -> None:
        store.write_text(mpath, FOLLOW_MAP % "\n".join(f"- {{id: {b}, agent: writer}}" for b in ids))
    steps(2)
    boxes()
    _pick_map(c, "follow-map")
    c.wait(f"!!{box('fw')} && !!{box('fa')} && {box('fw')}.innerText.includes('2 steps')", 20)
    out: dict = {}
    boxes("fx")  # (1) its own file, written with one more box
    anywhere = lambda b: q(f'[data-map-box="{b}"]')  # noqa: E731 -- a box with no line is drawn under "Not connected yet"
    out["box"] = _until(c, f"!!{anywhere('fx')}")
    steps(3)  # (2) a box's workflow, one more step
    out["steps"] = _until(c, f"{box('fw')}?.innerText.includes('3 steps')")
    store.write_text(store.path_for("agent", "my-reviewer", state_dir=rig.state), store.dump({**me, "model": "gpu-model-b"}))  # (3)
    out["model"] = _until(c, f"{box('fa')}?.innerText.includes('gpu-model-b')")
    # (4) a box open and a When card open: another write of the map keeps both
    c.js(f"{box('fw')}.click(); 1")
    c.wait(f"{box('fw')}?.dataset.open !== undefined", 10)
    c.js(f"{q('[data-testid=map-label][data-to=fa]')}.click(); 1")
    c.wait(f"!!{t('map-when-card')}", 10)
    boxes("fx", "fy")
    out["kept"] = [_until(c, f"!!{anywhere('fy')}"), c.js(f"{box('fw')}?.dataset.open !== undefined"), c.js(f"!!{t('map-when-card')}")]
    # the tab's own save (the When card's) comes back from the watcher: the map is not read again
    asked, seen, orig = [], threading.Event(), A.dispatch

    def counted(req):
        if req.method == "GET":
            asked.append(str(req.path))
        return orig(req)

    def tap(f: dict) -> None:
        d = f.get("data") or {}
        if f.get("event") == "files_changed" and d.get("kind") == "maps" and "follow-map" in (d.get("names") or []):
            seen.set()
    taps = bridge_for(rig.server).taps
    A.dispatch = counted
    try:
        c.js(f"{t('map-when-always')}.click(); {t('map-when-save')}.click(); 1")
        c.wait(f"!!{t('map-undo')} && !{t('map-when-card')}", 20)
        taps.append(tap)
        n0 = len(asked)
        out["own_frame"] = seen.wait(15)
        store.write_text(store.path_for("map", "zz-map-mark", state_dir=rig.state), "format: map/1\nname: zz-map-mark\nboxes: []\nlines: []\n")
        c.wait(f"[...{t('map-switcher')}.options].some((o) => o.value === 'zz-map-mark')", 20)  # a later frame, handled
        out["own_reads"] = asked[n0:].count("crew/map/follow-map")
    finally:
        A.dispatch = orig
        if tap in taps:
            taps.remove(tap)
    # (5) the chain's Undo offered: a box's workflow written again keeps it
    steps(4)
    out["undo_kept"] = [_until(c, f"{box('fw')}?.innerText.includes('4 steps')"), c.js(f"!!{t('map-undo')}")]
    out.update(_held(c, rig, fpath, boxes, steps, taps, A, orig))
    return {"follows": out}


def _held(c, rig, fpath, boxes, steps, taps, A, orig) -> dict:
    """(6) a drag in hand while the map and its workflow are written: nothing is read until it ends; a drag whose
    pointerup never comes ends with the window's blur (as Escape does), and the two changes heard (each its own call:
    the page merges frames that land together) make ONE read."""
    import threading
    from halo_harness.crew import store
    asked, heard = [], {"maps:follow-map": threading.Event(), "workflows:follow-flow": threading.Event()}

    def counted(req):
        if req.method == "GET":
            asked.append(str(req.path))
        return orig(req)

    def tap(f: dict) -> None:
        d = f.get("data") or {}
        for n in d.get("names") or [] if f.get("event") == "files_changed" else []:
            if f"{d.get('kind')}:{n}" in heard:
                heard[f"{d.get('kind')}:{n}"].set()

    def handled(key: str, mark: str) -> bool:  # its frame sent, then a later frame shown: the page has handled it
        ok = heard[key].wait(20)
        store.write_text(store.path_for("map", mark, state_dir=rig.state), f"format: map/1\nname: {mark}\nboxes: []\nlines: []\n")
        c.wait(f"[...{t('map-switcher')}.options].some((o) => o.value === '{mark}')", 20)
        return ok
    open_list(c)  # a row of the Add list in hand, as `drag` holds one; moved and let go inside the list, it adds nothing
    row = q('[data-testid="map-add-row"][data-ref="tester"]')
    x, y = center(c, row)
    x -= c.rect(row)[2] * 0.2  # on the row's text, away from its Add
    out: dict = {}
    A.dispatch = counted
    taps.append(tap)
    try:
        c.mouse("mouseMoved", x, y)
        c.mouse("mousePressed", x, y)
        c.mouse("mouseMoved", x, y + 20)
        out["in_hand"] = c.js(f"{t('map-drag-ghost')}?.hidden === false")  # the drag's ghost follows the pointer
        n0 = len(asked)
        boxes("fx", "fy", "fz")
        first = handled("maps:follow-map", "zz-map-held-1")
        steps(5)
        out["held_frames"] = first and handled("workflows:follow-flow", "zz-map-held-2")
        out["held"] = not c.js(f"!!{q('[data-map-box=fz]')}") and asked[n0:].count("crew/map/follow-map") == 0
        c.js("window.dispatchEvent(new Event('blur')); 1")
        out["after_blur"] = _until(c, f"!!{q('[data-map-box=fz]')} && {box('fw')}?.innerText.includes('5 steps')")
        c.mouse("mouseMoved", x, y)
        c.mouse("mouseReleased", x, y)
        handled("maps:follow-map", "zz-map-held-3")  # (already heard) a later frame, handled: every read is counted
        out["held_reads"] = asked[n0:].count("crew/map/follow-map")
    finally:
        A.dispatch = orig
        if tap in taps:
            taps.remove(tap)
    return out


def _open(c, name: str) -> None:
    c.js(f"(() => {{ const s = {t('map-switcher')}; const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;"
         f" set.call(s, '{name}'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")


def _crew(rig) -> dict:
    import json
    cfg = rig.state / "config.json"
    return (json.loads(cfg.read_text(encoding="utf-8")) if cfg.is_file() else {}).get("crew") or {}


def use_this(c, rig) -> dict:
    """3.6.0.11 SM: the select only opens a map; the open map that new sessions do not run says so, with [Run new
    sessions on {open}] (map-use-this), which writes crew.map; on Auto (no switch) the button takes crew.map out. Main's
    box names the model a new session starts on and why. Runs last: none set before and after."""
    c.js("document.activeElement?.blur(); 1")
    key(c, "c")
    c.wait(f"{VIEW} === 'map'", 20)
    _open(c, "ship-it")
    said = t("map-topline-said")
    out = {"use_line": c.wait(f"{t('map-switcher')}?.value === 'ship-it' && !!{t('map-use-this')} && {said}.textContent", 20),
           "use_label": c.js(f"{t('map-use-this')}?.textContent || ''"),
           "use_acts_top": c.js(f"Math.round({t('map-topline-acts')}.getBoundingClientRect().top - {t('map-topline')}.getBoundingClientRect().top)")}
    out["use_start"] = c.wait(f"{q('[data-map-box=main] .mp-meta')}?.textContent || ''", 20)
    c.js(f"{t('map-use-this')}.click(); 1")
    out["use_gone"] = c.wait(f"!{t('map-use-this')} && {t('map-uses')}?.getAttribute('aria-checked') === 'true' && {said}.textContent", 20)
    out["use_acts_top_after"] = c.js(f"Math.round({t('map-topline-acts')}.getBoundingClientRect().top - {t('map-topline')}.getBoundingClientRect().top)")
    out["use_crew_after"] = _crew(rig).get("map")
    _open(c, "auto")
    out["use_auto_line"] = c.wait(f"{t('map-switcher')}?.value === 'auto' && !!{t('map-use-this')} && {t('map-auto-next')}?.textContent", 20)
    out["use_auto_start"] = c.wait(f"{q('[data-testid=map-auto-main] .mp-meta')}?.textContent || ''", 20)
    c.js(f"{t('map-use-this')}.click(); 1")
    out["use_auto_gone"] = c.wait(f"!{t('map-auto-next')} && !{t('map-use-this')}", 20)
    out["use_crew_auto"] = _crew(rig).get("map", "")
    return out
