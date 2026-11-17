"""tests.helpers.studio_map_steps -- the steps of the Map tab's driver (tests/helpers/studio_map.py). Each waits for the
value it reads; a drag is real pointer events through CDP; the keyboard path is driven too."""
from __future__ import annotations

import base64
from pathlib import Path

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
    c.wait(f"{qa('[data-testid=map-label]')}.length === 7 && !!{t('builder-meta')}", 30)
    out["switch"] = c.js("[...document.querySelectorAll('[data-part=map] [data-testid=agents-views] button')].map((b) => b.innerText)")
    out["first"] = c.js(f"({{map: {t('map-switcher')}.value, dialogs: document.querySelectorAll('[role=dialog]').length,"
                        f" conversation: !!{t('builder-conversation')}, drawer: !!{q('.stage-drawer[data-panel-in=map-add]')},"
                        f" labels: {qa('[data-testid=map-label]')}.map((l) => l.innerText), hint: {t('builder-input')}.placeholder}})")
    out["geom"] = c.js(GEOM)
    shot(c, "studio-map.png")
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
    out["file"] = [ln for ln in rig.api("GET", "crew/map/starter")[1]["map"]["lines"] if ln["to"] == "tester"]
    return out


def chain(c, rig) -> dict:
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
         f" set.call(s, 'starter'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    c.wait(f"{t('map-switcher')}?.value === 'starter' && {qa('[data-testid=map-label]')}.length >= 8", 20)
    opts = f"[...{t('map-switcher')}.options].map((o) => o.textContent)"
    out["fresh_tags"] = c.js(opts)  # 3.6.0.2 R24: a fresh home (crew.map unset) tags no map
    out["uses_off"] = [c.js(f"{t('map-uses')}.getAttribute('aria-checked')"), c.js(f"{t('map-uses')}.closest('label').textContent")]
    # none set: new sessions run on the default, starter (config never holds it): the switch is on there; ship-it switched on
    # is config crew.map and tagged; switched off again, new sessions are back on starter
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
         f" set.call(s, 'starter'); s.dispatchEvent(new Event('change', {{bubbles: true}})); }})(); 1")
    c.wait(f"{t('map-switcher')}?.value === 'starter' && {qa('[data-testid=map-label]')}.length >= 8", 20)
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
